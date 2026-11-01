from langchain_aws import ChatBedrockConverse
from app import config


def get_llm(temperature: float = 0.3, max_tokens: int = 128) -> ChatBedrockConverse:
    """Single place the Bedrock model is created. Every agent uses this."""
    config.validate()
    return ChatBedrockConverse(
        model=config.BEDROCK_MODEL_ID,
        region_name=config.AWS_REGION,
        temperature=temperature,
        max_tokens=max_tokens,
    )
