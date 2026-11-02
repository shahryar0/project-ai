"""Transactional approval state machine and append-only audit records."""

from uuid import uuid4
from sqlalchemy import select
from app.qa.engine import check_draft
from app.storage.errors import RecordNotFoundError
from app.storage.models import ApprovalRequest, AuditEvent, Campaign, Draft, DraftVersion, now
from app.schemas import CampaignBrief
from app.storage.hashing import content_hash


class ApprovalConflict(ValueError):
    pass


class ApprovalService:
    def __init__(self, repository):
        self.repository = repository

    def _draft(self, session, tenant_id, draft_id):
        row = session.scalar(select(Draft).join(Campaign).where(
            Draft.id == draft_id, Campaign.tenant_id == tenant_id))
        if row is None:
            raise RecordNotFoundError("Draft not found.")
        campaign = session.get(Campaign, row.campaign_id)
        version = session.scalar(select(DraftVersion).where(
            DraftVersion.draft_id == row.id, DraftVersion.version == row.current_version))
        return row, campaign, version

    @staticmethod
    def _audit(session, tenant_id, actor, action, entity_id, payload):
        session.add(AuditEvent(tenant_id=tenant_id, actor_type="human", actor_id=actor,
            action=action, entity="draft", entity_id=entity_id, payload_json=payload))

    def edit(self, tenant_id, draft_id, text, media_suggestion, actor):
        with self.repository._write_lock, self.repository.sessions.begin() as session:
            draft, campaign, current = self._draft(session, tenant_id, draft_id)
            issues = [item.model_dump() for item in check_draft(
                draft.platform, text, media_suggestion, CampaignBrief.model_validate(campaign.brief_json))]
            next_version = draft.current_version + 1
            digest = content_hash(draft.platform, text)
            version = DraftVersion(draft_id=draft.id, version=next_version, text=text,
                media_suggestion=media_suggestion, content_hash=digest, qa_issues=issues,
                created_by="human", created_at=now())
            session.add(version)
            previous = session.scalars(select(ApprovalRequest).where(
                ApprovalRequest.draft_id == draft.id,
                ApprovalRequest.status.in_(["pending_review", "approved", "changes_requested"]))).all()
            for request in previous:
                if request.status == "approved":
                    self._audit(session, tenant_id, actor, "approval_voided_by_edit", draft.id,
                        {"approval_request_id": request.id, "version": request.version})
                request.status = "voided"
            draft.current_version = next_version
            draft.state = "pending_review" if not any(i["severity"] == "blocking" for i in issues) else "draft"
            if draft.state == "pending_review":
                session.add(ApprovalRequest(id=str(uuid4()), draft_id=draft.id, version=next_version,
                    content_hash=digest, status="pending_review"))
            self._audit(session, tenant_id, actor, "draft_edited", draft.id,
                {"version": next_version, "content_hash": digest})
        return self.repository.get_draft(tenant_id, draft_id)

    def request_changes(self, tenant_id, draft_id, comment, actor):
        with self.repository._write_lock, self.repository.sessions.begin() as session:
            draft, _, current = self._draft(session, tenant_id, draft_id)
            if draft.state != "pending_review":
                raise ApprovalConflict("Only a draft pending review can receive a change request.")
            active = session.scalar(select(ApprovalRequest).where(
                ApprovalRequest.draft_id == draft.id, ApprovalRequest.version == draft.current_version,
                ApprovalRequest.status == "pending_review"))
            if active is None:
                raise ApprovalConflict("No current review request exists.")
            active.status, active.decided_by, active.decided_at, active.comment = "changes_requested", actor, now(), comment
            draft.state = "changes_requested"
            self._audit(session, tenant_id, actor, "changes_requested", draft.id,
                {"version": draft.current_version, "comment": comment})
        return self.repository.get_draft(tenant_id, draft_id)

    def decide(self, tenant_id, draft_id, version_number, digest, actor, approved, comment=""):
        with self.repository._write_lock, self.repository.sessions.begin() as session:
            draft, _, current = self._draft(session, tenant_id, draft_id)
            if draft.current_version != version_number or current.content_hash != digest:
                raise ApprovalConflict("The requested version or content hash is stale.")
            if draft.state != "pending_review":
                raise ApprovalConflict("Only a draft pending review can be approved or rejected.")
            request = session.scalar(select(ApprovalRequest).where(
                ApprovalRequest.draft_id == draft.id, ApprovalRequest.version == version_number,
                ApprovalRequest.content_hash == digest, ApprovalRequest.status == "pending_review"))
            if request is None:
                raise ApprovalConflict("No matching approval request exists for this version.")
            request.status = "approved" if approved else "rejected"
            request.decided_by, request.decided_at, request.comment = actor, now(), comment or None
            draft.state = request.status
            self._audit(session, tenant_id, actor, request.status, draft.id,
                {"version": version_number, "content_hash": digest, "comment": comment})
        return self.repository.get_draft(tenant_id, draft_id)

    def audit(self, tenant_id, entity_id=None):
        with self.repository.sessions() as session:
            query = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
            if entity_id:
                query = query.where(AuditEvent.entity_id == entity_id)
            rows = session.scalars(query.order_by(AuditEvent.id)).all()
            return [{"id": row.id, "tenant_id": row.tenant_id, "actor_type": row.actor_type,
                "actor_id": row.actor_id, "action": row.action, "entity": row.entity,
                "entity_id": row.entity_id, "payload": row.payload_json, "at": row.at} for row in rows]
