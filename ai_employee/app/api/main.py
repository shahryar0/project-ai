"""Minimal FastAPI service for testing the LangGraph -> Gemini connection."""

import httpx
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
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.graph import get_graph

app = FastAPI(
    title="AI Employee - Model Connection",
    description="A basic question goes through LangGraph to Google Gemini.",
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, examples=["What is the capital of France?"])


class ChatResponse(BaseModel):
    answer: str
    model_id: str


class ErrorResponse(BaseModel):
    detail: str


@app.get("/health")
def health() -> dict[str, str]:
    """Checks the API only; this does not verify the Gemini key or model."""
    return {"status": "ok", "model_id": config.GEMINI_MODEL}


@app.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        429: {"model": ErrorResponse, "description": "Gemini quota or rate limit reached."},
        502: {"model": ErrorResponse, "description": "Gemini rejected the request or returned no text."},
        503: {"model": ErrorResponse, "description": "Gemini key, connection, or service unavailable."},
    },
)
def chat(body: ChatRequest) -> ChatResponse:
    """Use a sync route because the Gemini SDK call is blocking."""
    try:
        result = get_graph().invoke({"messages": [("user", body.query)]})
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
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not initialize Gemini. Check GOOGLE_API_KEY and GEMINI_MODEL in ai_employee/.env.",
        ) from exc

    answer = result["messages"][-1].text.strip()
    if not answer:
        raise HTTPException(status_code=502, detail="Gemini returned no text. Check whether generation was blocked or reached its output limit.")
    return ChatResponse(answer=answer, model_id=config.GEMINI_MODEL)
