"""Additive schema migrations. Never reset a running database."""

from uuid import uuid4
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session
from app.storage.models import ApprovalRequest, AuditEvent, Base, Campaign, Draft, DraftVersion, SchemaVersion


def initialize_schema(engine):
    Base.metadata.create_all(engine)
    if "revision_rounds" not in {column["name"] for column in inspect(engine).get_columns("drafts")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE drafts ADD COLUMN revision_rounds INTEGER NOT NULL DEFAULT 0"))
    with Session(engine) as session, session.begin():
        current = session.get(SchemaVersion, 1)
        if current is None:
            session.add(SchemaVersion(id=1, version=2))
        elif current.version == 1:
            # create_all above adds the Phase 2 tables without touching Phase 1 data.
            campaigns = session.scalars(select(Campaign).where(Campaign.status == "completed")).all()
            for campaign in campaigns:
                drafts = session.scalars(select(Draft).where(Draft.campaign_id == campaign.id)).all()
                for draft in drafts:
                    version = session.scalar(select(DraftVersion).where(
                        DraftVersion.draft_id == draft.id, DraftVersion.version == draft.current_version))
                    if version and not any(issue.get("severity") == "blocking" for issue in version.qa_issues):
                        draft.state = "pending_review"
                        session.add(ApprovalRequest(id=str(uuid4()), draft_id=draft.id,
                            version=version.version, content_hash=version.content_hash, status="pending_review"))
                        session.add(AuditEvent(tenant_id=campaign.tenant_id, actor_type="system", actor_id="migration-v2",
                            action="draft_submitted_for_review", entity="draft", entity_id=draft.id,
                            payload_json={"version": version.version, "migration": 2}))
            current.version = 2
        elif current.version != 2:
            raise RuntimeError("Unsupported draft database schema version.")
