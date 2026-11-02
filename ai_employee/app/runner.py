"""Try the complete workflow on AWS, then start a clean Gemini run on provider failure."""

from dataclasses import dataclass, replace
import re

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from google.genai.errors import APIError
from langchain_core.exceptions import (
    ModelError, ModelRateLimitError, ModelInvalidRequestError, ModelNotFoundError,
    ModelAuthenticationError, ModelPermissionDeniedError,
)
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

from app import config
from app.agents.results import collect_result
from app.context import WorkflowContext, brief_with_context
from app.graph import get_graph
from app.llm import BedrockInitializationError
from app.schemas import CampaignBrief, ProviderAttempt
from app.briefs import build_brief
from app.storage.factory import get_repository


class EmptyModelResponseError(RuntimeError):
    pass


PROVIDER_ERRORS = (
    BotoCoreError, ClientError, ModelError, APIError, httpx.HTTPError,
    ChatGoogleGenerativeAIError, BedrockInitializationError,
    config.ConfigurationError, EmptyModelResponseError,
)


def failure_reason(error: Exception) -> str:
    """Return an actionable code without echoing provider messages or credentials."""
    if isinstance(error, ClientError):
        details = error.response.get("Error", {})
        code = details.get("Code", "AWSRequestFailed")
        code = code if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", code) else "AWSRequestFailed"
        if code == "ThrottlingException" and "per day" in details.get("Message", "").lower():
            return "ThrottlingException (daily token quota)"
        return code
    if isinstance(error, config.ConfigurationError):
        return str(error)
    if isinstance(error, BedrockInitializationError):
        return "AWS client initialization failed; check credentials, bearer-token expiry and configuration."
    if isinstance(error, EmptyModelResponseError):
        return "Model returned no text or previews."
    return type(error).__name__


def failure_status(error: Exception) -> int:
    if isinstance(error, ModelRateLimitError) or isinstance(error, APIError) and error.code == 429:
        return 429
    if isinstance(error, (ModelAuthenticationError, ModelPermissionDeniedError)):
        return 503
    if isinstance(error, (ModelInvalidRequestError, ModelNotFoundError, EmptyModelResponseError)):
        return 502
    if isinstance(error, ChatGoogleGenerativeAIError):
        return 502
    if isinstance(error, APIError) and error.code < 500:
        return 502
    return 503


class ModelFallbackError(RuntimeError):
    def __init__(self, primary: Exception, fallback: Exception):
        self.status_code = failure_status(fallback)
        self.attempts = [
            ProviderAttempt(provider="bedrock", status="failed", reason=failure_reason(primary)),
            ProviderAttempt(provider="gemini", status="failed", reason=failure_reason(fallback)),
        ]
        super().__init__(
            f"Bedrock failed: {self.attempts[0].reason} "
            f"Gemini fallback failed: {self.attempts[1].reason}"
        )


@dataclass
class WorkflowRun:
    result: dict
    provider: config.ModelProvider
    model_id: str
    fallback_used: bool
    attempts: list[ProviderAttempt]
    campaign_id: str
    brief: CampaignBrief
    payload: dict
    replayed: bool = False


def _invoke(provider: config.ModelProvider, query: str, context: WorkflowContext) -> dict:
    result = get_graph(provider).invoke(
        {"messages": [("user", brief_with_context(query, context))]},
        context=context, config={"recursion_limit": 12},
    )
    payload = collect_result(result, "ceo")
    if not payload["summary"] and not payload["previews"]:
        raise EmptyModelResponseError("Model returned no text or previews.")
    return result


def _run_providers(query: str, context: WorkflowContext):
    if config.MODEL_PROVIDER == "gemini":
        result = _invoke("gemini", query, context)
        return result, "gemini", False, [ProviderAttempt(provider="gemini", status="success")]
    try:
        result = _invoke("bedrock", query, context)
    except PROVIDER_ERRORS as primary_error:
        # Delete every version written by the failed attempt before starting Gemini.
        context.repository.discard_attempt(context.brief.tenant_id, context.campaign_id)
        try:
            result = _invoke("gemini", query, context)
        except (*PROVIDER_ERRORS, ValueError) as fallback_error:
            raise ModelFallbackError(primary_error, fallback_error) from fallback_error
        return result, "gemini", True, [
            ProviderAttempt(provider="bedrock", status="failed", reason=failure_reason(primary_error)),
            ProviderAttempt(provider="gemini", status="success"),
        ]
    return result, "bedrock", False, [ProviderAttempt(provider="bedrock", status="success")]


def run_workflow(query: str, context: WorkflowContext, *, run_id=None, tenant_id="local", topic=None, facts=None, call_to_action=None) -> WorkflowRun:
    if config.MODEL_PROVIDER not in ("bedrock", "gemini"):
        raise config.ConfigurationError("MODEL_PROVIDER must be bedrock or gemini.")
    brief = build_brief(query, context, run_id=run_id, tenant_id=tenant_id, topic=topic, facts=facts, call_to_action=call_to_action)
    repository = get_repository()
    campaign_id, cached = repository.claim_campaign(brief)
    if cached is not None:
        return WorkflowRun({}, cached["provider"], cached["model_id"], cached["fallback_used"],
            [ProviderAttempt.model_validate(attempt) for attempt in cached["attempts"]],
            campaign_id, brief, cached["payload"], True)
    context = replace(context, brand=brief.brand, platforms=tuple(brief.platforms),
        brief=brief, campaign_id=campaign_id, repository=repository)
    try:
        result, provider, fallback_used, attempts = _run_providers(query, context)
        payload = collect_result(result, "ceo")
        actual_model = config.model_id(provider)
        repository.complete_campaign(tenant_id, campaign_id, {
            "payload": payload, "provider": provider, "model_id": actual_model,
            "fallback_used": fallback_used, "attempts": [attempt.model_dump() for attempt in attempts],
        })
    except Exception as error:
        # No partial drafts survive a failed request, including a failed fallback.
        repository.fail_campaign(tenant_id, campaign_id, type(error).__name__)
        raise
    return WorkflowRun(result, provider, actual_model, fallback_used, attempts, campaign_id, brief, payload)
