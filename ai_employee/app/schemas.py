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


class PostPreview(BaseModel):
    platform: Platform
    text: str = Field(min_length=1)
    media_suggestion: str = ""
    character_count: int
    warnings: list[str] = Field(default_factory=list)
    status: Literal["draft"] = "draft"
    connector_status: Literal["not_connected"] = "not_connected"
    published: Literal[False] = False


class ToolCallRecord(BaseModel):
    agent: str
    tool: str
    status: Literal["completed", "error", "incomplete"]
