import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1").strip()
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0").strip()


def validate() -> None:
    """Validate settings before creating the Bedrock model."""
    if not AWS_REGION or not BEDROCK_MODEL_ID:
        raise ValueError("Set AWS_REGION and BEDROCK_MODEL_ID in ai_employee/.env.")
