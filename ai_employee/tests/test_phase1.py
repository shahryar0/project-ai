"""V2 Phase 1: persistence, authoritative briefs, lexical QA, and fallback cleanup."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.campaigns import get_campaign, get_draft
from app.api.main import ChatRequest, chat
from app.briefs import build_brief, resolve_platforms
from app.context import WorkflowContext
from app.qa.engine import check_draft, hashtag_count
from app.schemas import BrandProfile, CampaignBrief
from app.storage.errors import CampaignConflictError, RecordNotFoundError
from app.storage.factory import get_repository
from app.storage.hashing import content_hash
from app.storage.models import Campaign, Draft, DraftVersion
from app.storage.sqlalchemy_repository import SQLAlchemyDraftRepository
from app.tools.preview import render_preview
from test_api import gemini, bedrock, social_script, sdk_reply, aws_reply


@pytest.fixture
def repository(tmp_path):
    instance = SQLAlchemyDraftRepository("sqlite:///" + (tmp_path / "repository.db").as_posix())
    try:
        yield instance
    finally:
        instance.close()


def draft_context(repository, *, query="Draft a planning app campaign.", platforms=("x",), tenant_id="local", run_id="test-run"):
    original = WorkflowContext(platforms=platforms)
    brief = build_brief(query, original, tenant_id=tenant_id, run_id=run_id)
    campaign_id, _ = repository.claim_campaign(brief)
    return replace(original, brief=brief, campaign_id=campaign_id, repository=repository)


@pytest.mark.parametrize("query,explicit,expected", [
    ("Post to Instagram", None, ["instagram"]),
    ("Use TWITTER", None, ["x"]),
    ("Post on Linked In and Facebook", None, ["facebook", "linkedin"]),
    ("An example of a post", None, ["facebook", "instagram", "x", "linkedin"]),
    ("Draft for X", None, ["x"]),
    ("Use Instagram", ["linkedin"], ["linkedin"]),
    ("Anything", ["x", "x"], ["x"]),
])
def test_platform_resolution_is_code_owned(query, explicit, expected):
    assert resolve_platforms(query, explicit) == expected


def test_brief_preserves_exact_owner_text_and_brand():
    query = "  Plan a launch.\nDo not add dates.  "
    body = ChatRequest(query=query, brand={"name": "Focus", "tone": "Calm"})
    brief = build_brief(body.query, WorkflowContext(brand=body.brand), run_id="original")
    assert brief.request_text == query
    assert brief.facts == [query]
    assert brief.brand.name == "Focus"
    assert brief.tone == "Calm"
    with pytest.raises(ValueError):
        brief.request_text = "Changed"


@pytest.mark.parametrize("owner,text,expected", [
    ("Planning app", "Visit https://invented.example.com", "UNSUPPLIED_URL"),
    ("Use https://example.com", "Visit https://example.com", None),
    ("Planning app", "Visit invented.example.com", "UNSUPPLIED_URL"),
    ("Planning app", "Visit https://[", "UNSUPPLIED_URL"),
    ("Use https://example.com", "Visit example.com", None),
    ("Use https://example.com/About", "Visit https://example.com/about", "UNSUPPLIED_URL"),
    ("Planning app", "Only $29", "UNSUPPLIED_PRICE"),
    ("Costs $29", "Only $29", None),
    ("Planning app", "Costs PKR 500", "UNSUPPLIED_PRICE"),
    ("Costs PKR 500", "Costs PKR 500", None),
    ("Planning app", "Launch on 2026-11-02", "UNSUPPLIED_DATE"),
    ("Launch on 2026-11-02", "Launch on 2026-11-02", None),
    ("Planning app", "Launch on June 1, 2026", "UNSUPPLIED_DATE"),
    ("Launch June 1, 2026", "Launch June 1, 2026", None),
    ("Planning app", "Available tomorrow", "UNSUPPLIED_DATE"),
    ("Available tomorrow", "Available tomorrow", None),
    ("Planning app", "Call +92 300 1234567", "UNSUPPLIED_PHONE"),
    ("Call +92 300 1234567", "Call +92 300 1234567", None),
    ("Planning app", "Follow @invented_account", "UNSUPPLIED_HANDLE"),
    ("Our handle is @focus", "Follow @focus", None),
    ("Planning app", "We promise guaranteed results", "FORBIDDEN_CLAIM"),
    ("Planning app", "A risk-free investment", "FORBIDDEN_CLAIM"),
    ("Planning app", "Our tool cures diabetes", "FORBIDDEN_CLAIM"),
    ("Planning app", "Plan your day with clarity", None),
])
def test_qa_supplied_facts_and_banned_claims(owner, text, expected):
    brief = build_brief(owner, WorkflowContext(), run_id="qa")
    blocking = {issue.code for issue in check_draft("x", text, "", brief) if issue.severity == "blocking"}
    if expected:
        assert expected in blocking
    else:
        assert not blocking


def test_qa_extra_facts_and_custom_forbidden_claims():
    brief = build_brief("Launch app", WorkflowContext(brand=BrandProfile(forbidden_claims=["miracle solution"])), facts=["Costs $19"], run_id="qa")
    assert not any(issue.code == "UNSUPPLIED_PRICE" for issue in check_draft("x", "Costs $19", "", brief))
    assert any(issue.code == "FORBIDDEN_CLAIM" for issue in check_draft("x", "A miracle solution", "", brief))


def test_qa_editorial_rules_are_warnings():
    brief = build_brief("Launch app", WorkflowContext(platforms=("x",)), run_id="qa")
    issues = check_draft("x", "a" * 261 + " #Plan #Plan", "", brief)
    assert {issue.code for issue in issues} == {"OVER_BUDGET", "DUPLICATE_HASHTAG"}
    assert all(issue.severity == "warning" for issue in issues)
    assert hashtag_count("#Plan #Work #Plan") == 3
    assert any(issue.code == "EMPTY_TEXT" for issue in check_draft("x", "", "", brief))
    assert any(issue.code == "PLATFORM_NOT_ALLOWED" for issue in check_draft("facebook", "Post", "", brief))


def test_saved_versions_are_immutable_and_identical_saves_are_idempotent(repository):
    context = draft_context(repository)
    _, one = render_preview("x", "First draft", "Visual one", context)
    first = one["previews"][0]
    _, same = render_preview("x", "First draft", "Visual one", context)
    assert same["previews"][0] == first
    _, two = render_preview("x", "Revised draft", "Visual one", context)
    second = two["previews"][0]
    assert first["draft_id"] == second["draft_id"]
    assert second["version"] == 2
    assert first["content_hash"] != second["content_hash"]
    draft = repository.get_draft("local", first["draft_id"])
    assert [version["text"] for version in draft["versions"]] == ["First draft", "Revised draft"]
    assert draft["current_version"] == 2
    assert draft["current"]["published"] is False


def test_hash_is_stable_normalized_and_platform_specific():
    assert content_hash("x", "Cafe\u0301\r\nPlan") == content_hash("x", "Caf\u00e9\nPlan")
    assert content_hash("x", "Plan") != content_hash("facebook", "Plan")
    assert len(content_hash("x", "Plan")) == 64


def test_qa_issues_are_persisted_and_visible(repository):
    context = draft_context(repository)
    _, artifact = render_preview("x", "Buy for $999 at https://invented.example.com", "", context)
    preview = artifact["previews"][0]
    codes = {issue["code"] for issue in preview["qa_issues"]}
    assert {"UNSUPPLIED_PRICE", "UNSUPPLIED_URL"} <= codes
    stored = repository.get_draft("local", preview["draft_id"])
    assert stored["current"]["qa_issues"] == preview["qa_issues"]
    assert stored["state"] == "draft"


def test_empty_or_unrequested_preview_does_not_save(repository):
    context = draft_context(repository)
    for platform,text in [("x", " "), ("facebook", "A draft")]:
        _, artifact = render_preview(platform, text, "", context)
        assert artifact["error"]
    assert repository.get_campaign("local", context.campaign_id)["drafts"] == []


def test_disk_persistence_survives_repository_restart(repository):
    context = draft_context(repository)
    _, artifact = render_preview("x", "A durable draft", "", context)
    database_url = str(repository.engine.url)
    repository.close()
    restarted = SQLAlchemyDraftRepository(database_url)
    try:
        assert restarted.get_draft("local", artifact["previews"][0]["draft_id"])["current"]["text"] == "A durable draft"
        assert restarted.get_campaign("local", context.campaign_id)["brief"]["request_text"] == context.brief.request_text
    finally:
        restarted.close()


def test_repository_reads_are_tenant_scoped(repository):
    context = draft_context(repository, tenant_id="tenant-a")
    _, artifact = render_preview("x", "Private brand draft", "", context)
    with pytest.raises(RecordNotFoundError):
        repository.get_draft("tenant-b", artifact["previews"][0]["draft_id"])
    with pytest.raises(RecordNotFoundError):
        repository.get_campaign("tenant-b", context.campaign_id)


def test_concurrent_run_claim_has_one_owner(repository):
    brief = build_brief("Draft", WorkflowContext(), run_id="one-run")
    def claim():
        try:
            return repository.claim_campaign(brief)[0]
        except CampaignConflictError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim(), range(2)))
    assert sum(claim is not None for claim in claims) == 1


def test_four_platform_request_returns_saved_ids_and_history(gemini):
    from app.storage.views import CampaignView, DraftView
    gemini.side_effect = social_script(["facebook", "instagram", "x", "linkedin"])
    response = chat(ChatRequest(query="Launch our planning app", run_id="four-platform"))
    campaign = get_campaign(response.campaign_id, tenant_id="local")
    CampaignView.model_validate(campaign)
    assert campaign["run_id"] == "four-platform"
    assert campaign["status"] == "completed"
    assert len(campaign["drafts"]) == len(response.previews) == 4
    assert len({preview.draft_id for preview in response.previews}) == 4
    for preview in response.previews:
        draft = get_draft(preview.draft_id, tenant_id="local")
        DraftView.model_validate(draft)
        assert preview.version == draft["current_version"] == 1
        assert preview.content_hash == draft["current"]["content_hash"]
        assert draft["current"]["text"] == preview.text


def test_same_run_id_replays_saved_result_without_model_calls(gemini):
    gemini.side_effect = social_script(["x"])
    body = ChatRequest(query="Create an X draft", run_id="replay-this")
    first = chat(body)
    second = chat(body)
    assert gemini.call_count == 6
    assert second.replayed is True and first.replayed is False
    assert first.campaign_id == second.campaign_id
    assert first.previews == second.previews
    assert len(get_campaign(first.campaign_id, tenant_id="local")["drafts"]) == 1


def test_reused_run_id_with_changed_brief_is_409(gemini):
    first = chat(ChatRequest(query="Hello", run_id="same-id"))
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Different request", run_id="same-id"))
    assert error.value.status_code == 409
    assert gemini.call_count == 1
    assert get_campaign(first.campaign_id, tenant_id="local")["brief"]["request_text"] == "Hello"


def test_running_run_id_is_409_without_model_call(gemini):
    brief = build_brief("Hello", WorkflowContext(), run_id="in-progress")
    get_repository().claim_campaign(brief)
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Hello", run_id="in-progress"))
    assert error.value.status_code == 409
    gemini.assert_not_called()


def test_read_routes_report_404_without_leaking_other_tenants(gemini):
    response = chat(ChatRequest(query="Hello", tenant_id="tenant-a"))
    with pytest.raises(HTTPException) as error:
        get_campaign(response.campaign_id, tenant_id="tenant-b")
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        get_draft("does-not-exist", tenant_id="tenant-a")
    assert error.value.status_code == 404


def test_changed_delegation_brief_is_rejected(gemini):
    body = ChatRequest(query="Create an X post", platforms=["x"], run_id="immutable")
    canonical = build_brief(body.query, WorkflowContext(platforms=("x",)), run_id=body.run_id)
    changed = canonical.model_dump()
    changed["platforms"] = ["facebook"]
    gemini.side_effect = [sdk_reply(calls=[("social_media_manager", {"brief": changed})]), sdk_reply("Please use the unchanged brief.")]
    response = chat(body)
    assert response.previews == []
    assert response.tool_calls[0].status == "error"
    assert gemini.call_count == 2
    assert get_campaign(response.campaign_id, tenant_id="local")["brief"]["platforms"] == ["x"]


def aws_campaign_script(stubber, brief):
    stubber.add_response("converse", aws_reply(tool_use={"toolUseId": "manager", "name": "social_media_manager", "input": {"brief": brief.model_dump()}}))
    stubber.add_response("converse", aws_reply(tool_use={"toolUseId": "writer", "name": "content_writer", "input": {"brief": brief.model_dump()}}))
    reply = aws_reply()
    reply["output"]["message"]["content"] = [{"toolUse": {"toolUseId": "tool-"+platform, "name": "preview_"+platform+"_post", "input": {"text": "AWS partial draft for " + platform, "media_suggestion": "A screenshot"}}} for platform in brief.platforms]
    reply["stopReason"] = "tool_use"
    stubber.add_response("converse", reply)
    stubber.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)


def test_failed_aws_drafts_are_deleted_before_gemini_starts(bedrock, gemini):
    stubber,_ = bedrock
    body = ChatRequest(query="Launch a planning app", run_id="fallback-persistence")
    brief = build_brief(body.query, WorkflowContext(), run_id=body.run_id)
    aws_campaign_script(stubber, brief)
    script = iter(social_script(brief.platforms))
    inspected = []
    def gemini_response(**kwargs):
        if not inspected:
            repository = get_repository()
            with repository.sessions() as session:
                assert session.scalar(select(func.count()).select_from(Draft)) == 0
                assert session.scalar(select(func.count()).select_from(DraftVersion)) == 0
            inspected.append(True)
        return next(script)
    gemini.side_effect = gemini_response
    response = chat(body)
    assert response.fallback_used is True
    assert len(response.previews) == 4
    repository = get_repository()
    with repository.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Campaign)) == 1
        assert session.scalar(select(func.count()).select_from(Draft)) == 4
        assert session.scalar(select(func.count()).select_from(DraftVersion)) == 4
    assert all(preview.version == 1 and "AWS partial" not in preview.text for preview in response.previews)
    assert len(get_campaign(response.campaign_id, tenant_id="local")["drafts"]) == 4


def test_failed_run_is_cleaned_and_can_retry_same_id(gemini):
    from google.genai import errors
    partial = social_script(["x"])
    partial[3] = errors.ClientError(429, {"error": {"code": 429, "message": "Quota", "status": "RESOURCE_EXHAUSTED"}})
    gemini.side_effect = partial
    body = ChatRequest(query="Draft for X", run_id="retry-failed")
    with pytest.raises(HTTPException):
        chat(body)
    repository = get_repository()
    with repository.sessions() as session:
        failed = session.scalar(select(Campaign))
        campaign_id = failed.id
        assert failed.status == "failed"
        assert session.scalar(select(func.count()).select_from(Draft)) == 0
        assert session.scalar(select(func.count()).select_from(DraftVersion)) == 0
    gemini.side_effect = social_script(["x"])
    response = chat(body)
    assert response.campaign_id == campaign_id
    assert response.previews[0].version == 1


def test_phase_two_adds_manual_review_routes_without_publishing():
    from app.api.main import app
    paths = app.openapi()["paths"]
    assert "/campaigns/{campaign_id}" in paths
    assert "/drafts/{draft_id}" in paths
    assert "/drafts/{draft_id}/approve" in paths
    assert "/drafts/{draft_id}/reject" in paths
    assert "/drafts/{draft_id}/schedule" not in paths
    assert not any("publish" in path or "connectors" in path for path in paths)


def test_storage_configuration_failure_is_sanitized(gemini, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "DATABASE_URL", "unknown-driver://private-database-credential")
    with pytest.raises(HTTPException) as error:
        chat(ChatRequest(query="Hello"))
    assert error.value.status_code == 503
    assert "storage" in error.value.detail
    assert "private-database-credential" not in error.value.detail
    gemini.assert_not_called()
