"""Check API handlers -> LangGraph -> Gemini with the SDK request mocked."""

from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException
from google.genai import errors, models, types
from pydantic import ValidationError

from app import config
from app.api.main import ChatRequest, app, chat, health
from app.graph import get_graph
from app.llm import get_llm


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "unit-test-key")
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    response = types.GenerateContentResponse(
        candidates=[types.Candidate(
            content=types.Content(role="model", parts=[types.Part(text="Paris.")]),
            finish_reason=types.FinishReason.STOP,
        )],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=10, candidates_token_count=2, total_token_count=12,
        ),
    )
    generate = Mock(return_value=response)
    monkeypatch.setattr(models.Models, "generate_content", generate)
    get_graph.cache_clear()
    try:
        yield generate
    finally:
        get_graph.cache_clear()


def test_question_reaches_gemini_adapter(gemini):
    response = chat(ChatRequest(query="What is the capital of France?"))
    assert response.model_dump() == {"answer": "Paris.", "model_id": config.GEMINI_MODEL}
    gemini.assert_called_once()
    request = gemini.call_args.kwargs
    assert request["model"] == config.GEMINI_MODEL
    assert request["contents"][0].role == "user"
    assert request["contents"][0].parts[0].text == "What is the capital of France?"
    assert request["config"].max_output_tokens == 1024
    assert request["config"].system_instruction


def test_factory_uses_api_key_developer_backend(gemini):
    model = get_llm()
    assert model.vertexai is False
    assert model.google_api_key.get_secret_value() == "unit-test-key"
    gemini.assert_not_called()


@pytest.mark.parametrize("payload", [{}, {"query": ""}, {"query": " \t "}])
def test_invalid_question_does_not_create_model(gemini, payload):
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(payload)
    assert get_graph.cache_info().currsize == 0
    gemini.assert_not_called()


def test_health_does_not_initialize_model(gemini, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")
    assert health() == {"status": "ok", "model_id": config.GEMINI_MODEL}
    assert get_graph.cache_info().currsize == 0
    gemini.assert_not_called()


def test_missing_key_returns_setup_message(gemini, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Hello"))
    assert error.value.status_code == 503
    assert "Set GOOGLE_API_KEY" in error.value.detail
    gemini.assert_not_called()


@pytest.mark.parametrize("code,status,expected,detail", [
    (429, "RESOURCE_EXHAUSTED", 429, "quota"),
    (401, "UNAUTHENTICATED", 503, "GOOGLE_API_KEY"),
    (403, "PERMISSION_DENIED", 503, "GOOGLE_API_KEY"),
    (404, "NOT_FOUND", 502, "GEMINI_MODEL"),
    (400, "INVALID_ARGUMENT", 502, "rejected the request"),
    (503, "UNAVAILABLE", 503, "unavailable"),
])
def test_sdk_errors_are_translated_without_exposing_secrets(gemini, code, status, expected, detail):
    error_type = errors.ServerError if code >= 500 else errors.ClientError
    gemini.side_effect = error_type(code, {
        "error": {"code": code, "status": status, "message": "private provider message unit-test-key"},
    })
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Hello"))
    assert error.value.status_code == expected
    assert detail in error.value.detail
    assert "unit-test-key" not in error.value.detail
    gemini.assert_called_once()


def test_connection_failure_is_actionable(gemini):
    gemini.side_effect = httpx.ConnectError("connection unavailable")
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Hello"))
    assert error.value.status_code == 503
    assert "connection" in error.value.detail


def test_empty_generation_returns_502(gemini):
    gemini.return_value = types.GenerateContentResponse(
        candidates=[types.Candidate(
            content=types.Content(role="model", parts=[]),
            finish_reason=types.FinishReason.STOP,
        )],
    )
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Hello"))
    assert error.value.status_code == 502
    assert "no text" in error.value.detail


def test_api_documents_routes_and_errors():
    schema = app.openapi()
    assert "get" in schema["paths"]["/health"]
    responses = schema["paths"]["/chat"]["post"]["responses"]
    for status_code in ("429", "502", "503"):
        assert responses[status_code]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }
