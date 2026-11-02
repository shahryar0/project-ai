"""FastAPI service for the CEO-led social post preview workflow."""

import httpx
import re
from typing import Literal
from fastapi import FastAPI, HTTPException
from google.genai.errors import APIError
from langchain_core.exceptions import (
    ModelAPIError,
    ModelAuthenticationError,
    ModelInvalidRequestError,
    ModelNotFoundError,
    ModelPermissionDeniedError,
    ModelRateLimitError,
)
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from app import config
from app.agents.results import format_previews
from app.context import WorkflowContext
from app.runner import EmptyModelResponseError, ModelFallbackError, run_workflow
from app.schemas import BrandProfile, Platform, PostPreview, ProviderAttempt, ToolCallRecord
from app.api.campaigns import router as campaign_router
from app.api.approval import router as approval_router
from app.storage.errors import CampaignConflictError, StorageUnavailableError

app = FastAPI(
    title="AI Employee - Social Post Previews",
    description="CEO -> social media manager -> content writer -> local platform preview tools. No posts are published.",
)
app.include_router(campaign_router)
app.include_router(approval_router)


class ChatRequest(BaseModel):
    model_config = ConfigDict()

    query: str = Field(min_length=1, examples=["Draft launch posts for our planning app for freelancers on Facebook, Instagram, X and LinkedIn. Do not invent prices or dates."])
    brand: BrandProfile | None = None
    platforms: list[Platform] | None = Field(default=None, min_length=1, max_length=4)
    run_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    tenant_id: str = Field(default="local", pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    topic: str | None = None
    facts: list[str] = Field(default_factory=list, max_length=100)
    call_to_action: str | None = None

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value):
        if not value.strip():
            raise ValueError("Query must not be blank.")
        return value


class ChatResponse(BaseModel):
    answer: str
    model_id: str
    previews: list[PostPreview] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    mode: Literal["preview"] = "preview"
    provider: Literal["bedrock", "gemini"]
    fallback_used: bool = False
    provider_attempts: list[ProviderAttempt] = Field(default_factory=list)
    campaign_id: str
    run_id: str
    tenant_id: str
    replayed: bool = False
    guardian_verdicts: list[dict] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str


def sanitize_unverified_status(answer: str) -> str:
    """Do not relay a model's unsupported claim that an external action occurred."""
    for claim in re.finditer(r"\b(?:posted|published|scheduled|approved)\b", answer, re.IGNORECASE):
        context = answer[max(0, claim.start() - 32):claim.start()].lower()
        if not re.search(r"\b(?:not|never|no|isn't|aren't|cannot|can't|won't|without)\b", context):
            return "I can prepare drafts for human review. No post has been published or scheduled, and no approval was recorded."
    return answer


@app.get("/health")
def health() -> dict[str, str]:
    """Checks the API only; provider credentials and model access are not tested."""
    return {
        "status": "ok", "model_id": config.model_id(config.MODEL_PROVIDER),
        "primary_provider": config.MODEL_PROVIDER,
        "fallback_provider": "gemini" if config.MODEL_PROVIDER == "bedrock" else "",
    }


@app.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        409: {"model": ErrorResponse, "description": "Run ID is already active or belongs to a different brief."},
        429: {"model": ErrorResponse, "description": "Model quota or rate limit reached after fallback."},
        502: {"model": ErrorResponse, "description": "The model or workflow could not produce a response."},
        503: {"model": ErrorResponse, "description": "Model credentials, connection, or service unavailable."},
    },
)
def chat(body: ChatRequest) -> ChatResponse:
    """Run AWS first, with a fresh Gemini workflow if the AWS provider fails."""
    try:
        context = WorkflowContext(brand=body.brand, platforms=tuple(body.platforms) if body.platforms else None)
        run = run_workflow(body.query, context, run_id=body.run_id, tenant_id=body.tenant_id,
            topic=body.topic, facts=body.facts, call_to_action=body.call_to_action)
    except CampaignConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (StorageUnavailableError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="Draft storage is unavailable. Check DATABASE_URL and database permissions.") from exc
    except ModelFallbackError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except EmptyModelResponseError as exc:
        raise HTTPException(status_code=502, detail="The model returned no text or previews. Check generation limits or safety settings.") from exc
    except config.ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ModelRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail="Gemini quota or rate limit reached. Check your Google AI Studio project limits.",
        ) from exc
    except (ModelAuthenticationError, ModelPermissionDeniedError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Gemini rejected access. Check GOOGLE_API_KEY and its Google AI Studio project permissions.",
        ) from exc
    except ModelNotFoundError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini model not found. Check GEMINI_MODEL and the models available to your API key.",
        ) from exc
    except ModelAPIError as exc:
        raise HTTPException(status_code=503, detail="Gemini service is unavailable. Try again later.") from exc
    except (ModelInvalidRequestError, ChatGoogleGenerativeAIError, APIError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini rejected the request. Check GOOGLE_API_KEY, GEMINI_MODEL and the request settings.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Could not connect to Gemini. Check your internet connection.") from exc
    except GraphRecursionError as exc:
        raise HTTPException(status_code=502, detail="The agents reached their step limit. Try a smaller or clearer campaign brief.") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not initialize Gemini. Check GOOGLE_API_KEY and GEMINI_MODEL in ai_employee/.env.",
        ) from exc

    payload = run.payload
    previews = [PostPreview.model_validate(preview) for preview in payload["previews"]]
    answer = format_previews(previews) if previews else payload["summary"]
    if not previews:
        answer = sanitize_unverified_status(answer)
    if payload["tool_calls"] and not previews:
        answer += "\n\nNo platform previews were produced. Nothing was published."
    if not answer:
        raise HTTPException(status_code=502, detail="Gemini returned no text. Check whether generation was blocked or reached its output limit.")
    return ChatResponse(
        answer=answer, model_id=run.model_id, provider=run.provider,
        fallback_used=run.fallback_used, provider_attempts=run.attempts, previews=previews,
        tool_calls=[ToolCallRecord.model_validate(call) for call in payload["tool_calls"]],
        campaign_id=run.campaign_id, run_id=run.brief.run_id, tenant_id=run.brief.tenant_id, replayed=run.replayed,
        guardian_verdicts=payload.get("guardian_verdicts", []),
    )
