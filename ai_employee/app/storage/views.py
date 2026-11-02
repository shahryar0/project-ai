from typing import Literal
from pydantic import BaseModel
from app.schemas import CampaignBrief, Platform, PostPreview, QAIssue


class DraftVersionView(BaseModel):
    draft_id: str
    version: int
    text: str
    media_suggestion: str
    content_hash: str
    qa_issues: list[QAIssue]
    created_by: str
    created_at: str


class DraftView(BaseModel):
    draft_id: str
    campaign_id: str
    platform: Platform
    current_version: int
    revision_rounds: int = 0
    state: Literal["draft", "pending_review", "changes_requested", "approved", "rejected"]
    created_by_agent: str
    created_at: str
    versions: list[DraftVersionView]
    approval_requests: list[dict] = []
    current: PostPreview


class CampaignView(BaseModel):
    campaign_id: str
    tenant_id: str
    run_id: str
    status: Literal["running", "completed", "failed"]
    brief: CampaignBrief
    created_at: str
    error_code: str | None
    drafts: list[DraftView]
