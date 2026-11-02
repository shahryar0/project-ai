"""Public request preferences and preview results."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["facebook", "instagram", "x", "linkedin"]
PLATFORMS: tuple[Platform, ...] = ("facebook", "instagram", "x", "linkedin")


class BrandProfile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=1000)
    audience: str = Field(default="", max_length=300)
    tone: str = Field(default="warm, clear and professional", max_length=200)
    language: str = Field(default="match the user's language", max_length=100)
    forbidden_claims: list[str] = Field(default_factory=list, max_length=50)


class CampaignBrief(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    run_id: str
    tenant_id: str
    request_text: str
    topic: str | None = None
    facts: list[str] = Field(default_factory=list)
    platforms: list[Platform]
    audience: str | None = None
    tone: str | None = None
    language: str | None = None
    call_to_action: str | None = None
    brand: BrandProfile


class QAIssue(BaseModel):
    severity: Literal["blocking", "warning"]
    code: str
    message: str


class PostPreview(BaseModel):
    draft_id: str
    version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    platform: Platform
    text: str = Field(min_length=1)
    media_suggestion: str = ""
    character_count: int
    warnings: list[str] = Field(default_factory=list)
    qa_issues: list[QAIssue] = Field(default_factory=list)
    hashtag_count: int = 0
    state: Literal["draft"] = "draft"
    status: Literal["draft"] = "draft"
    connector_status: Literal["not_connected"] = "not_connected"
    published: Literal[False] = False


class ToolCallRecord(BaseModel):
    agent: str
    tool: str
    status: Literal["completed", "error", "incomplete"]


class ProviderAttempt(BaseModel):
    provider: Literal["bedrock", "gemini"]
    status: Literal["success", "failed"]
    reason: str | None = None
