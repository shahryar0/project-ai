"""Minimal FastAPI service for testing the LangGraph -> Bedrock connection."""

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.graph import get_graph

app = FastAPI(
    title="AI Employee - Model Connection",
    description="A basic question goes through LangGraph to Amazon Bedrock.",
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, examples=["What is the capital of France?"])


class ChatResponse(BaseModel):
    answer: str
    model_id: str


@app.get("/health")
def health() -> dict[str, str]:
    """Checks the API only; this does not call or verify the AWS model."""
    return {"status": "ok", "model_id": config.BEDROCK_MODEL_ID}


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    """Use a sync route because the Bedrock SDK call is blocking."""
    try:
        result = get_graph().invoke({"messages": [("user", body.query)]})
    except (NoCredentialsError, PartialCredentialsError) as exc:
        raise HTTPException(
            status_code=503,
            detail="AWS credentials are missing. Sign in with the AWS CLI or configure your AWS profile.",
        ) from exc
    except ClientError as exc:
        error = exc.response.get("Error", {})
        raise HTTPException(
            status_code=502,
            detail=f"Bedrock request failed ({error.get('Code', 'Unknown')}): {error.get('Message', '')}",
        ) from exc
    except BotoCoreError as exc:
        raise HTTPException(status_code=503, detail=f"AWS connection failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not initialize Bedrock. Check your AWS login, AWS_REGION and BEDROCK_MODEL_ID.",
        ) from exc

    answer = result["messages"][-1].text.strip()
    if not answer:
        raise HTTPException(status_code=502, detail="Bedrock returned an empty text response.")
    return ChatResponse(answer=answer, model_id=config.BEDROCK_MODEL_ID)
