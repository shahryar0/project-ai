"""Bounded writer and Guardian flow for a human-requested draft revision."""

from dataclasses import replace
from app import config
from app.agents.results import collect_result
from app.agents.social.brand_guardian import build_brand_guardian, GuardianVerdict
from app.agents.social.content_writer import build_content_writer
from app.context import WorkflowContext, brief_with_context
from app.schemas import CampaignBrief
from app.storage.errors import CampaignConflictError


def run_draft_revision(repository, tenant_id: str, draft_id: str, owner_comment: str) -> dict:
    draft = repository.get_draft(tenant_id, draft_id)
    if draft["state"] != "changes_requested":
        raise CampaignConflictError("Request changes before starting an agent revision.")
    remaining = 2 - draft["revision_rounds"]
    if remaining <= 0:
        raise CampaignConflictError("The two agent revision rounds are already used.")
    campaign = repository.get_campaign(tenant_id, draft["campaign_id"])
    brief = CampaignBrief.model_validate(campaign["brief"])
    context = WorkflowContext(brief=brief, campaign_id=campaign["campaign_id"],
        repository=repository, revision_draft_id=draft_id)
    provider = config.MODEL_PROVIDER
    writer = build_content_writer(provider)
    guardian = build_brand_guardian(provider)
    verdicts = []
    guidance = owner_comment
    for round_index in range(remaining):
        request = (f"Revise only saved draft {draft_id} on {draft['platform']}. Owner's requested changes: "
            f"{guidance}. Keep all unmentioned content stable. Use only the corresponding platform preview tool.")
        writer_result = writer.invoke({"messages": [("user", brief_with_context(request, context))]},
            context=context, config={"recursion_limit": 8})
        writer_payload = collect_result(writer_result, "content_writer")
        if not writer_payload["previews"]:
            raise RuntimeError("The writer did not save a revised draft version.")
        review_request = "Review the current saved revision against the original brief, facts and brand profile."
        review = guardian.invoke({"messages": [("user", brief_with_context(review_request, context))]},
            context=context, config={"recursion_limit": 8})
        verdict = GuardianVerdict.model_validate(review["structured_response"]).model_dump()
        verdicts.append(verdict)
        current = repository.get_draft(tenant_id, draft_id)["current"]
        qa_blocking = any(issue["severity"] == "blocking" for issue in current["qa_issues"])
        guardian_blocking = any(issue["severity"] == "blocking" and issue["draft_id"] == draft_id
            for issue in verdict["issues"])
        if not qa_blocking and not guardian_blocking:
            break
        guidance = "Resolve these blocking review issues: " + "; ".join(
            f"{issue.get('problem', '')} Suggestion: {issue.get('suggestion', '')}"
            for issue in verdict["issues"] if issue.get("draft_id") == draft_id and issue.get("severity") == "blocking")
        if not guidance.strip():
            guidance = "Resolve the blocking QA issues attached to the saved preview."
        # Re-read state so the bounded remaining count reflects versions already saved.
        draft = repository.get_draft(tenant_id, draft_id)
        if draft["revision_rounds"] >= 2:
            break
    return {"draft": repository.get_draft(tenant_id, draft_id), "guardian_verdicts": verdicts,
        "revision_rounds": repository.get_draft(tenant_id, draft_id)["revision_rounds"]}
