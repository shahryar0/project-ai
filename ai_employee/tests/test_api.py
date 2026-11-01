"""Check API handlers -> LangGraph -> Bedrock without sockets or AWS calls."""

import boto3
import pytest
from botocore.exceptions import NoCredentialsError
from botocore.stub import ANY, Stubber
from fastapi import HTTPException
from langchain_aws import ChatBedrockConverse
from pydantic import ValidationError

from app import config, llm
from app.api.main import ChatRequest, app, chat, health
from app.graph import get_graph


@pytest.fixture
def bedrock(monkeypatch):
    monkeypatch.setattr(config, "AWS_REGION", "us-east-1")
    monkeypatch.setattr(config, "BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0")
    client = boto3.client(
        "bedrock-runtime",
        region_name=config.AWS_REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    control_client = boto3.client(
        "bedrock",
        region_name=config.AWS_REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    monkeypatch.setattr(
        llm,
        "ChatBedrockConverse",
        lambda **kwargs: ChatBedrockConverse(
            client=client, bedrock_client=control_client, **kwargs
        ),
    )
    get_graph.cache_clear()
    try:
        with Stubber(client) as stubber, Stubber(control_client):
            yield stubber
            stubber.assert_no_pending_responses()
    finally:
        get_graph.cache_clear()


def test_chat_passes_question_to_bedrock(bedrock):
    bedrock.add_response(
        "converse",
        {
            "output": {"message": {"role": "assistant", "content": [{"text": "Paris."}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 2, "totalTokens": 12},
            "metrics": {"latencyMs": 1},
        },
        {
            "modelId": config.BEDROCK_MODEL_ID,
            "messages": [{"role": "user", "content": [{"text": "What is the capital of France?"}]}],
            "system": ANY,
            "inferenceConfig": {"maxTokens": 128, "temperature": 0.3},
        },
    )
    response = chat(ChatRequest(query="What is the capital of France?"))
    assert response.model_dump() == {"answer": "Paris.", "model_id": config.BEDROCK_MODEL_ID}


@pytest.mark.parametrize("payload", [{}, {"query": ""}, {"query": " \t "}])
def test_invalid_question_does_not_call_bedrock(bedrock, payload):
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(payload)
    assert get_graph.cache_info().currsize == 0


def test_health_does_not_initialize_the_model(bedrock):
    assert health()["status"] == "ok"
    assert get_graph.cache_info().currsize == 0


def test_bedrock_access_error_is_actionable(bedrock):
    bedrock.add_client_error(
        "converse",
        service_error_code="AccessDeniedException",
        service_message="Model access denied.",
        http_status_code=403,
    )
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Hello"))
    assert error.value.status_code == 502
    assert "AccessDeniedException" in error.value.detail


@pytest.mark.parametrize("message", [
    "Too many tokens per day, please wait before trying again.",
    "Too many requests, please wait before trying again.",
])
def test_bedrock_throttling_returns_429(bedrock, message):
    bedrock.add_client_error(
        "converse",
        service_error_code="ThrottlingException",
        service_message=message,
        http_status_code=429,
    )
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="What is the capital of France?"))
    assert error.value.status_code == 429
    assert message in error.value.detail


def test_missing_credentials_returns_setup_message(bedrock, monkeypatch):
    def no_credentials(**kwargs):
        raise NoCredentialsError()

    monkeypatch.setattr(llm, "ChatBedrockConverse", no_credentials)
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Hello"))
    assert error.value.status_code == 503
    assert "AWS credentials are missing" in error.value.detail


def test_api_exposes_chat_and_health():
    paths = app.openapi()["paths"]
    assert "post" in paths["/chat"]
    assert "get" in paths["/health"]


def test_api_documents_bedrock_errors():
    schema = app.openapi()
    responses = schema["paths"]["/chat"]["post"]["responses"]
    for status_code in ("429", "502", "503"):
        assert responses[status_code]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }
