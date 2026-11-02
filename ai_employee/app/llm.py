from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_aws import ChatBedrockConverse
from langchain_core.language_models.chat_models import BaseChatModel
from botocore.config import Config
from botocore.exceptions import BotoCoreError
from app import config


class BedrockInitializationError(RuntimeError):
    """AWS client setup failed before a model request could be sent."""


def get_llm(max_tokens: int = 1024, provider: config.ModelProvider | None = None) -> BaseChatModel:
    """Build one provider explicitly; the workflow runner controls fallback."""
    provider = provider or config.MODEL_PROVIDER
    config.validate(provider)
    if provider == "bedrock":
        try:
            return ChatBedrockConverse(
                model=config.BEDROCK_MODEL_ID,
                region_name=config.AWS_REGION,
                bedrock_api_key=config.AWS_BEARER_TOKEN_BEDROCK or None,
                credentials_profile_name=None if config.AWS_BEARER_TOKEN_BEDROCK else config.AWS_PROFILE or None,
                max_tokens=max_tokens,
                temperature=0.3,
                config=Config(
                    retries={"mode": "adaptive", "total_max_attempts": 2},
                    connect_timeout=10, read_timeout=30,
                ),
            )
        except (BotoCoreError, ValueError) as exc:
            raise BedrockInitializationError("AWS credentials or model configuration are unavailable.") from exc
    return ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        api_key=config.GOOGLE_API_KEY,
        vertexai=False,
        max_tokens=max_tokens,
        timeout=30,
        max_retries=1,
    )
