"""Check API handlers -> LangGraph -> Gemini with the SDK request mocked."""

from unittest.mock import Mock
import json

import httpx
import pytest
from fastapi import HTTPException
from google.genai import errors, models, types
from pydantic import ValidationError

from app import config
from app.api.main import ChatRequest, app, chat, health
from app.graph import get_graph
from app.llm import get_llm
from app.storage.factory import get_repository


class CampaignSDKMock(Mock):
    """Script model output while copying canonical briefs for ordinary handoffs."""
    def __call__(self, *args, **kwargs):
        response = super().__call__(*args, **kwargs).model_copy(deep=True)
        text = kwargs["contents"][0].parts[0].text
        canonical = json.JSONDecoder().raw_decode(text.split("Campaign brief (authoritative JSON):\n", 1)[1])[0]
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                call = part.function_call
                if call and call.name in ("social_media_manager", "content_writer") and isinstance(call.args.get("brief"), str):
                    call.args["brief"] = canonical
        return response


@pytest.fixture
def gemini(monkeypatch, tmp_path):
    get_repository.cache_clear()
    monkeypatch.setattr(config, "DATABASE_URL", "sqlite:///" + (tmp_path / "drafts.db").as_posix())
    monkeypatch.setattr(config, "MODEL_PROVIDER", "gemini")
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
    generate = CampaignSDKMock(return_value=response)
    monkeypatch.setattr(models.Models, "generate_content", generate)
    get_graph.cache_clear()
    try:
        yield generate
    finally:
        get_graph.cache_clear()
        if get_repository.cache_info().currsize:
            get_repository().close()
        get_repository.cache_clear()


def test_question_reaches_gemini_adapter(gemini):
    response = chat(ChatRequest(query="What is the capital of France?"))
    assert response.answer == "Paris."
    assert response.model_id == config.GEMINI_MODEL
    assert response.previews == []
    assert response.tool_calls == []
    gemini.assert_called_once()
    request = gemini.call_args.kwargs
    assert request["model"] == config.GEMINI_MODEL
    assert request["contents"][0].role == "user"
    assert "What is the capital of France?" in request["contents"][0].parts[0].text
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
    assert health() == {
        "status": "ok", "model_id": config.GEMINI_MODEL,
        "primary_provider": "gemini", "fallback_provider": "",
    }
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


def sdk_reply(text=None, calls=None):
    parts = [types.Part(text=text)] if text is not None else [
        types.Part(function_call=types.FunctionCall(name=name, args=args))
        for name, args in calls
    ]
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=parts), finish_reason=types.FinishReason.STOP,
    )])


def social_script(platforms):
    return [
        sdk_reply(calls=[("social_media_manager", {"brief": "Prepare a product launch campaign."})]),
        sdk_reply(calls=[("content_writer", {"brief": "Write the requested platform posts."})]),
        sdk_reply(calls=[(f"preview_{platform}_post", {
            "text": f"Draft for {platform}: meet our new planning app. #Planning",
            "media_suggestion": "A product screenshot supplied by the owner.",
        }) for platform in platforms]),
        sdk_reply("Draft previews are ready."),
        sdk_reply("Campaign drafts reviewed."),
        sdk_reply("Ready for your review."),
    ]


def test_real_agent_hierarchy_calls_all_platform_tools(gemini):
    from app.schemas import PLATFORMS
    gemini.side_effect = social_script(PLATFORMS)
    response = chat(ChatRequest(
        query="Write social posts for our planning app launch.",
        brand={"name": "Focus Studio", "audience": "Freelancers", "tone": "Friendly", "language": "English"},
    ))
    assert gemini.call_count == 6
    assert [post.platform for post in response.previews] == list(PLATFORMS)
    for post in response.previews:
        assert post.text.startswith(f"Draft for {post.platform}")
        assert post.character_count == len(post.text)
        assert post.published is False
        assert post.connector_status == "not_connected"
    assert [(call.agent, call.tool, call.status) for call in response.tool_calls] == [
        ("ceo", "social_media_manager", "completed"),
        ("social_media_manager", "content_writer", "completed"),
        *[("content_writer", f"preview_{platform}_post", "completed") for platform in PLATFORMS],
    ]
    for request in gemini.call_args_list[:3]:
        text = request.kwargs["contents"][0].parts[0].text
        assert "Focus Studio" in text
        assert "Freelancers" in text
    assert "Nothing was published" in response.answer


def test_explicit_platforms_are_enforced_even_if_model_calls_extra_tool(gemini):
    gemini.side_effect = social_script(["facebook", "x"])
    response = chat(ChatRequest(query="Only draft for X.", platforms=["x"]))
    assert [post.platform for post in response.previews] == ["x"]
    rejected = next(call for call in response.tool_calls if call.tool == "preview_facebook_post")
    assert rejected.status == "error"


def test_no_previews_is_reported_honestly(gemini):
    gemini.side_effect = social_script(["facebook"])
    response = chat(ChatRequest(query="Only draft for X.", platforms=["x"]))
    assert response.previews == []
    assert "No platform previews were produced" in response.answer
    assert "Nothing was published" in response.answer


def test_nested_manager_quota_error_returns_429(gemini):
    gemini.side_effect = [
        sdk_reply(calls=[("social_media_manager", {"brief": "Draft a launch campaign."})]),
        errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Quota reached"}}),
    ]
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Write launch posts."))
    assert error.value.status_code == 429
    assert gemini.call_count == 2


def test_brand_and_previews_do_not_leak_to_next_request(gemini):
    gemini.side_effect = social_script(["x"]) + [sdk_reply("Paris.")]
    first = chat(ChatRequest(query="Draft for X.", brand={"name": "Private Test Brand"}, platforms=["x"]))
    assert len(first.previews) == 1
    second = chat(ChatRequest(query="What is the capital of France?"))
    assert second.previews == []
    assert second.tool_calls == []
    assert second.answer == "Paris."
    assert "Private Test Brand" not in gemini.call_args.kwargs["contents"][0].parts[0].text


def test_preview_flags_and_editorial_warning(gemini):
    from app.schemas import PostPreview
    script = social_script(["x"])
    script[2].candidates[0].content.parts[0].function_call.args["text"] = "a" * 261
    gemini.side_effect = script
    preview = chat(ChatRequest(query="Draft for X.", platforms=["x"])).previews[0]
    assert preview.character_count == 261
    assert preview.warnings
    assert preview.published is False
    with pytest.raises(ValidationError):
        PostPreview.model_validate({**preview.model_dump(), "published": True})


@pytest.mark.parametrize("platforms", [[], ["tiktok"], ["facebook"] * 5])
def test_invalid_platform_preferences(platforms):
    with pytest.raises(ValidationError):
        ChatRequest(query="Draft a post", platforms=platforms)


@pytest.fixture
def bedrock(gemini, monkeypatch):
    import boto3
    from botocore.stub import Stubber
    from langchain_aws import ChatBedrockConverse
    from app import llm

    monkeypatch.setattr(config, "MODEL_PROVIDER", "bedrock")
    monkeypatch.setattr(config, "AWS_REGION", "us-east-1")
    monkeypatch.setattr(config, "BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0")
    monkeypatch.setattr(config, "AWS_BEARER_TOKEN_BEDROCK", "")
    monkeypatch.setattr(config, "AWS_PROFILE", "")
    client_args = {"region_name": "us-east-1", "aws_access_key_id": "test", "aws_secret_access_key": "test"}
    runtime = boto3.client("bedrock-runtime", **client_args)
    control = boto3.client("bedrock", **client_args)
    factory = Mock(side_effect=lambda **kwargs: ChatBedrockConverse(client=runtime, bedrock_client=control, **kwargs))
    monkeypatch.setattr(llm, "ChatBedrockConverse", factory)
    with Stubber(runtime) as stubber, Stubber(control):
        yield stubber, factory
        stubber.assert_no_pending_responses()


def aws_reply(text="Paris.", tool_use=None):
    content = [{"toolUse": tool_use}] if tool_use else [{"text": text}]
    return {
        "output": {"message": {"role": "assistant", "content": content}},
        "stopReason": "tool_use" if tool_use else "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 2, "totalTokens": 12},
        "metrics": {"latencyMs": 1},
    }


def test_bedrock_success_does_not_require_or_call_gemini(bedrock, gemini, monkeypatch):
    from botocore.stub import ANY
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")
    stubber, factory = bedrock
    stubber.add_response("converse", aws_reply(), {
        "modelId": config.BEDROCK_MODEL_ID,
        "messages": ANY,
        "system": ANY, "toolConfig": ANY,
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.3},
    })
    response = chat(ChatRequest(query="What is the capital of France?"))
    assert response.answer == "Paris."
    assert response.provider == "bedrock"
    assert response.model_id == config.BEDROCK_MODEL_ID
    assert response.fallback_used is False
    assert [(attempt.provider, attempt.status) for attempt in response.provider_attempts] == [("bedrock", "success")]
    gemini.assert_not_called()
    sdk_config = factory.call_args.kwargs["config"]
    assert sdk_config.retries == {"mode": "adaptive", "total_max_attempts": 2}
    assert sdk_config.connect_timeout == 10


@pytest.mark.parametrize("code,status,message", [
    ("ThrottlingException", 429, "Too many tokens per day, please wait before trying again."),
    ("ThrottlingException", 429, "Too many requests"),
    ("AccessDeniedException", 403, "Access denied unit-test-key"),
    ("ExpiredTokenException", 403, "Bearer token expired"),
    ("InternalServerException", 500, "Service temporarily unavailable"),
])
def test_aws_provider_failure_falls_back_to_gemini(bedrock, gemini, code, status, message):
    stubber, _ = bedrock
    stubber.add_client_error("converse", service_error_code=code, service_message=message, http_status_code=status)
    response = chat(ChatRequest(query="What is the capital of France?"))
    assert response.answer == "Paris."
    assert response.provider == "gemini"
    assert response.model_id == config.GEMINI_MODEL
    assert response.fallback_used is True
    assert [(attempt.provider, attempt.status) for attempt in response.provider_attempts] == [("bedrock", "failed"), ("gemini", "success")]
    assert code in response.provider_attempts[0].reason
    assert "unit-test-key" not in response.model_dump_json()
    gemini.assert_called_once()


def test_bearer_token_is_used_instead_of_explicit_profile(bedrock, monkeypatch):
    from app.llm import get_llm
    _, factory = bedrock
    monkeypatch.setattr(config, "AWS_BEARER_TOKEN_BEDROCK", "test-bearer-token")
    monkeypatch.setattr(config, "AWS_PROFILE", "unused-profile")
    get_llm(provider="bedrock")
    assert factory.call_args.kwargs["bedrock_api_key"] == "test-bearer-token"
    assert factory.call_args.kwargs["credentials_profile_name"] is None


def test_aws_initialization_failure_falls_back(bedrock, gemini):
    _, factory = bedrock
    factory.side_effect = ValueError("Private credentials: unit-test-key")
    response = chat(ChatRequest(query="Hello"))
    assert response.fallback_used is True
    assert response.provider == "gemini"
    assert "initialization failed" in response.provider_attempts[0].reason
    assert "unit-test-key" not in response.model_dump_json()
    gemini.assert_called_once()


def test_no_gemini_key_after_aws_failure_returns_setup_error(bedrock, gemini, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")
    stubber, _ = bedrock
    stubber.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Hello"))
    assert error.value.status_code == 503
    assert "Bedrock failed" in error.value.detail
    assert "Set GOOGLE_API_KEY" in error.value.detail
    gemini.assert_not_called()


def test_both_providers_exhausted_report_both_failures(bedrock, gemini):
    stubber, _ = bedrock
    stubber.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)
    gemini.side_effect = errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "unit-test-key"}})
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Hello"))
    assert error.value.status_code == 429
    assert "Bedrock failed" in error.value.detail
    assert "Gemini fallback failed" in error.value.detail
    assert "unit-test-key" not in error.value.detail


def test_nested_aws_failure_restarts_the_whole_hierarchy_on_gemini(bedrock, gemini):
    from app.briefs import build_brief
    from app.context import WorkflowContext
    body = ChatRequest(query="Original campaign brief.", brand={"name": "Focus Studio"}, run_id="nested-fallback")
    brief = build_brief(body.query, WorkflowContext(brand=body.brand), run_id=body.run_id)
    stubber, _ = bedrock
    stubber.add_response("converse", aws_reply(tool_use={
        "toolUseId": "delegate-manager", "name": "social_media_manager", "input": {"brief": brief.model_dump()},
    }))
    stubber.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)
    gemini.side_effect = social_script(["facebook", "instagram", "x", "linkedin"])
    response = chat(body)
    assert response.fallback_used is True
    assert response.provider == "gemini"
    assert len(response.previews) == 4
    assert len(response.tool_calls) == 6
    assert all(not preview.published for preview in response.previews)
    first_gemini_input = gemini.call_args_list[0].kwargs["contents"]
    assert len(first_gemini_input) == 1
    assert "Original campaign brief" in first_gemini_input[0].parts[0].text
    assert "Focus Studio" in first_gemini_input[0].parts[0].text
