import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GOOGLE_API_KEY = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
ModelProvider = Literal["bedrock", "gemini"]
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "bedrock").strip().lower()
AWS_REGION = os.getenv("AWS_REGION", "us-east-1").strip()
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0").strip()
AWS_BEARER_TOKEN_BEDROCK = os.getenv("AWS_BEARER_TOKEN_BEDROCK", "").strip()
AWS_PROFILE = os.getenv("AWS_PROFILE", "").strip()


class ConfigurationError(ValueError):
    """A required local model setting is missing."""


def validate(provider: ModelProvider) -> None:
    """Only validate the provider being used; AWS does not require a Gemini key."""
    if provider == "bedrock":
        if not AWS_REGION or not BEDROCK_MODEL_ID:
            raise ConfigurationError("Set AWS_REGION and BEDROCK_MODEL_ID in ai_employee/.env.")
    elif provider == "gemini":
        if not GOOGLE_API_KEY:
            raise ConfigurationError("Set GOOGLE_API_KEY in ai_employee/.env using a Google AI Studio API key.")
        if not GEMINI_MODEL:
            raise ConfigurationError("Set GEMINI_MODEL in ai_employee/.env.")
    else:
        raise ConfigurationError("MODEL_PROVIDER must be bedrock or gemini.")


def model_id(provider: ModelProvider) -> str:
    return BEDROCK_MODEL_ID if provider == "bedrock" else GEMINI_MODEL
