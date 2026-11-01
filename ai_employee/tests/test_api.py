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
    assert response.answer == "Paris."
    assert response.model_id == config.GEMINI_MODEL
    assert response.previews == []
    assert response.tool_calls == []
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


def test_preview_flags_and_editorial_warning():
    from app.tools.preview import render_preview
    from app.schemas import PostPreview
    _, artifact = render_preview("x", "a" * 261, "Visual idea", None)
    preview = PostPreview.model_validate(artifact["previews"][0])
    assert preview.character_count == 261
    assert preview.warnings
    assert preview.published is False
    with pytest.raises(ValidationError):
        PostPreview.model_validate({**preview.model_dump(), "published": True})


@pytest.mark.parametrize("platforms", [[], ["tiktok"], ["facebook"] * 5])
def test_invalid_platform_preferences(platforms):
    with pytest.raises(ValidationError):
        ChatRequest(query="Draft a post", platforms=platforms)
