from langchain_google_genai import ChatGoogleGenerativeAI
from app import config


def get_llm(max_tokens: int = 1024) -> ChatGoogleGenerativeAI:
    """Create a Gemini Developer API model using the local API key."""
    config.validate()
    return ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        api_key=config.GOOGLE_API_KEY,
        vertexai=False,
        max_tokens=max_tokens,
        timeout=30,
        max_retries=1,
    )
