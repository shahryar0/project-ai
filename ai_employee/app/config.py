import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GOOGLE_API_KEY = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()


class ConfigurationError(ValueError):
    """A required local model setting is missing."""


def validate() -> None:
    """Validate settings before creating the Gemini model."""
    if not GOOGLE_API_KEY:
        raise ConfigurationError("Set GOOGLE_API_KEY in ai_employee/.env using a Google AI Studio API key.")
    if not GEMINI_MODEL:
        raise ConfigurationError("Set GEMINI_MODEL in ai_employee/.env.")
