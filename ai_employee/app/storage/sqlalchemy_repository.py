from pathlib import Path
from threading import RLock
from uuid import uuid4

from sqlalchemy import create_engine, delete, event, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.qa.engine import hashtag_count, normalize_text
from app.schemas import CampaignBrief
from app.storage.errors import CampaignConflictError, RecordNotFoundError
from app.storage.hashing import content_hash
from app.storage.migrations import initialize_schema
from app.storage.models import ApprovalRequest, AuditEvent, Campaign, Draft, DraftVersion, Tenant, now
from uuid import uuid4


class SQLAlchemyDraftRepository:
    def __init__(self, database_url: str):
        options = {}
        if database_url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if ":memory:" in database_url:
                options["poolclass"] = StaticPool
        self.engine = create_engine(database_url, **options)
        if self.engine.dialect.name == "sqlite":
            database = self.engine.url.database
            if database and database != ":memory:":
                Path(database).resolve().parent.mkdir(parents=True, exist_ok=True)
            @event.listens_for(self.engine, "connect")
            def foreign_keys(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
        initialize_schema(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self._write_lock = RLock()

    def close(self):
        self.engine.dispose()

    def _campaign(self, session, tenant_id, campaign_id):
        campaign = session.scalar(select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id))
        if campaign is None:
            raise RecordNotFoundError("Campaign not found.")
        return campaign

    def claim_campaign(self, brief: CampaignBrief) -> tuple[str, dict | None]:
        snapshot = brief.model_dump()
        # A unique tenant/run constraint also protects separate server processes.
        for attempt in range(2):
            try:
                with self._write_lock, self.sessions.begin() as session:
                    campaign = session.scalar(select(Campaign).where(Campaign.tenant_id == brief.tenant_id, Campaign.run_id == brief.run_id))
                    if campaign:
                        if campaign.brief_json != snapshot:
                            raise CampaignConflictError("This run_id already belongs to a different brief. Use a new run_id.")
                        if campaign.status == "completed":
                            return campaign.id, campaign.result_json
                        if campaign.status == "running":
                            raise CampaignConflictError("This run_id is already running.")
                        changed = session.execute(update(Campaign).where(Campaign.id == campaign.id, Campaign.status == "failed").values(status="running", error_code=None, result_json=None))
                        if changed.rowcount != 1:
                            raise CampaignConflictError("This run_id is already running.")
                        session.execute(delete(Draft).where(Draft.campaign_id == campaign.id))
                        return campaign.id, None
                    if session.get(Tenant, brief.tenant_id) is None:
                        session.add(Tenant(id=brief.tenant_id, name=brief.tenant_id))
                        session.flush()
                    campaign_id = str(uuid4())
                    session.add(Campaign(id=campaign_id, tenant_id=brief.tenant_id, run_id=brief.run_id, brief_json=snapshot, status="running"))
                    return campaign_id, None
            except IntegrityError:
                if attempt:
                    raise
        raise CampaignConflictError("Unable to claim campaign run.")

    @staticmethod
    def _version(version):
        return {"draft_id": version.draft_id, "version": version.version, "text": version.text,
                "media_suggestion": version.media_suggestion, "content_hash": version.content_hash,
                "qa_issues": version.qa_issues, "created_by": version.created_by, "created_at": version.created_at}

    def _preview(self, draft, version):
        return {**self._version(version), "platform": draft.platform, "character_count": len(version.text),
                "hashtag_count": hashtag_count(version.text), "state": draft.state, "status": draft.state,
                "warnings": [issue["message"] for issue in version.qa_issues if issue["severity"] == "warning"],
                "published": False, "connector_status": "not_connected"}

    def save_draft(self, tenant_id, campaign_id, platform, text, media_suggestion, qa_issues) -> dict:
        text = normalize_text(text)
        with self._write_lock, self.sessions.begin() as session:
            campaign = self._campaign(session, tenant_id, campaign_id)
            if campaign.status != "running":
                raise CampaignConflictError("Only a running campaign can receive agent drafts.")
            if platform not in campaign.brief_json["platforms"]:
                raise CampaignConflictError("Platform is not allowed by the campaign brief.")
            draft = session.scalar(select(Draft).where(Draft.campaign_id == campaign_id, Draft.platform == platform))
            if draft is None:
                draft = Draft(id=str(uuid4()), campaign_id=campaign_id, platform=platform, current_version=0)
                session.add(draft)
                session.flush()
            current = session.scalar(select(DraftVersion).where(DraftVersion.draft_id == draft.id, DraftVersion.version == draft.current_version))
            if current and current.text == text and current.media_suggestion == media_suggestion and current.qa_issues == qa_issues:
                return self._preview(draft, current)
            draft.current_version += 1
            version = DraftVersion(draft_id=draft.id, version=draft.current_version, text=text,
                media_suggestion=media_suggestion, content_hash=content_hash(platform, text),
                qa_issues=qa_issues, created_by="content_writer")
            session.add(version)
            session.flush()
            return self._preview(draft, version)

    def save_agent_revision(self, tenant_id, draft_id, text, media_suggestion, qa_issues) -> dict:
        text = normalize_text(text)
        with self._write_lock, self.sessions.begin() as session:
            draft = session.scalar(select(Draft).join(Campaign).where(
                Draft.id == draft_id, Campaign.tenant_id == tenant_id))
            if draft is None:
                raise RecordNotFoundError("Draft not found.")
            if draft.revision_rounds >= 2:
                raise CampaignConflictError("The two agent revision rounds are already used.")
            if draft.state not in ("changes_requested", "draft", "pending_review"):
                raise CampaignConflictError("This draft is not available for agent revision.")
            draft.revision_rounds += 1
            digest = content_hash(draft.platform, text)
            version_number = draft.current_version + 1
            version = DraftVersion(draft_id=draft.id, version=version_number, text=text,
                media_suggestion=media_suggestion, content_hash=digest, qa_issues=qa_issues,
                created_by="content_writer")
            session.add(version)
            active = session.scalars(select(ApprovalRequest).where(
                ApprovalRequest.draft_id == draft.id,
                ApprovalRequest.status.in_(["pending_review", "changes_requested"]))).all()
            for request in active:
                request.status = "voided"
            draft.current_version = version_number
            draft.state = "pending_review" if not any(i["severity"] == "blocking" for i in qa_issues) else "draft"
            if draft.state == "pending_review":
                session.add(ApprovalRequest(id=str(uuid4()), draft_id=draft.id, version=version_number,
                    content_hash=digest, status="pending_review"))
            campaign = session.get(Campaign, draft.campaign_id)
            session.add(AuditEvent(tenant_id=tenant_id, actor_type="agent", actor_id="content_writer",
                action="agent_revision_saved", entity="draft", entity_id=draft.id,
                payload_json={"version": version_number, "revision_round": draft.revision_rounds}))
            return self._preview(draft, version)

    def discard_attempt(self, tenant_id, campaign_id):
        with self._write_lock, self.sessions.begin() as session:
            campaign = self._campaign(session, tenant_id, campaign_id)
            if campaign.status != "running":
                raise CampaignConflictError("Cannot discard drafts of a completed campaign.")
            session.execute(delete(Draft).where(Draft.campaign_id == campaign_id))

    def complete_campaign(self, tenant_id, campaign_id, result):
        with self._write_lock, self.sessions.begin() as session:
            campaign = self._campaign(session, tenant_id, campaign_id)
            if campaign.status != "running":
                raise CampaignConflictError("Campaign is not running.")
            campaign.result_json = result
            campaign.status = "completed"
            drafts = session.scalars(select(Draft).where(Draft.campaign_id == campaign_id)).all()
            for draft in drafts:
                version = session.scalar(select(DraftVersion).where(
                    DraftVersion.draft_id == draft.id, DraftVersion.version == draft.current_version))
                if version and not any(issue["severity"] == "blocking" for issue in version.qa_issues):
                    draft.state = "pending_review"
                    session.add(ApprovalRequest(id=str(uuid4()), draft_id=draft.id,
                        version=version.version, content_hash=version.content_hash, status="pending_review"))
                else:
                    draft.state = "draft"
                session.add(AuditEvent(tenant_id=tenant_id, actor_type="system", actor_id="system",
                    action="draft_submitted_for_review" if draft.state == "pending_review" else "draft_blocked_by_qa",
                    entity="draft", entity_id=draft.id, payload_json={"version": draft.current_version}))

    def fail_campaign(self, tenant_id, campaign_id, error_code):
        with self._write_lock, self.sessions.begin() as session:
            campaign = self._campaign(session, tenant_id, campaign_id)
            session.execute(delete(Draft).where(Draft.campaign_id == campaign_id))
            campaign.status = "failed"
            campaign.result_json = None
            campaign.error_code = error_code

    def update_completed_result(self, tenant_id, campaign_id, result):
        with self._write_lock, self.sessions.begin() as session:
            campaign = self._campaign(session, tenant_id, campaign_id)
            if campaign.status != "completed":
                raise CampaignConflictError("Campaign is not completed.")
            campaign.result_json = result

    def _draft_view(self, session, draft):
        versions = session.scalars(select(DraftVersion).where(DraftVersion.draft_id == draft.id).order_by(DraftVersion.version)).all()
        return {"draft_id": draft.id, "campaign_id": draft.campaign_id, "platform": draft.platform,
                "current_version": draft.current_version, "state": draft.state,
                "revision_rounds": draft.revision_rounds,
                "created_by_agent": draft.created_by_agent, "created_at": draft.created_at,
                "versions": [self._version(version) for version in versions],
                "approval_requests": [{"id": item.id, "version": item.version, "content_hash": item.content_hash,
                    "status": item.status, "decided_by": item.decided_by, "decided_at": item.decided_at,
                    "comment": item.comment, "created_at": item.created_at}
                    for item in session.scalars(select(ApprovalRequest).where(ApprovalRequest.draft_id == draft.id).order_by(ApprovalRequest.created_at)).all()],
                "current": self._preview(draft, versions[-1])}

    def get_campaign(self, tenant_id, campaign_id) -> dict:
        with self.sessions() as session:
            campaign = self._campaign(session, tenant_id, campaign_id)
            drafts = session.scalars(select(Draft).where(Draft.campaign_id == campaign_id).order_by(Draft.platform)).all()
            return {"campaign_id": campaign.id, "tenant_id": campaign.tenant_id, "run_id": campaign.run_id,
                    "status": campaign.status, "brief": campaign.brief_json, "created_at": campaign.created_at,
                    "error_code": campaign.error_code, "drafts": [self._draft_view(session, draft) for draft in drafts]}

    def get_draft(self, tenant_id, draft_id) -> dict:
        with self.sessions() as session:
            draft = session.scalar(select(Draft).join(Campaign).where(Draft.id == draft_id, Campaign.tenant_id == tenant_id))
            if draft is None:
                raise RecordNotFoundError("Draft not found.")
            return self._draft_view(session, draft)
