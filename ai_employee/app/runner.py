"""Try the complete workflow on AWS, then start a clean Gemini run on provider failure."""

from dataclasses import dataclass
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
from app.schemas import ProviderAttempt


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


def _invoke(provider: config.ModelProvider, query: str, context: WorkflowContext) -> dict:
    result = get_graph(provider).invoke(
        {"messages": [("user", brief_with_context(query, context))]},
        context=context, config={"recursion_limit": 12},
    )
    payload = collect_result(result, "ceo")
    if not payload["summary"] and not payload["previews"]:
        raise EmptyModelResponseError("Model returned no text or previews.")
    return result


def run_workflow(query: str, context: WorkflowContext) -> WorkflowRun:
    provider = config.MODEL_PROVIDER
    if provider not in ("bedrock", "gemini"):
        raise config.ConfigurationError("MODEL_PROVIDER must be bedrock or gemini.")
    if provider == "gemini":
        result = _invoke("gemini", query, context)
        return WorkflowRun(result, "gemini", config.GEMINI_MODEL, False, [
            ProviderAttempt(provider="gemini", status="success"),
        ])
    try:
        result = _invoke("bedrock", query, context)
    except PROVIDER_ERRORS as primary_error:
        try:
            result = _invoke("gemini", query, context)
        except (*PROVIDER_ERRORS, ValueError) as fallback_error:
            raise ModelFallbackError(primary_error, fallback_error) from fallback_error
        return WorkflowRun(result, "gemini", config.GEMINI_MODEL, True, [
            ProviderAttempt(provider="bedrock", status="failed", reason=failure_reason(primary_error)),
            ProviderAttempt(provider="gemini", status="success"),
        ])
    return WorkflowRun(result, "bedrock", config.BEDROCK_MODEL_ID, False, [
        ProviderAttempt(provider="bedrock", status="success"),
    ])
