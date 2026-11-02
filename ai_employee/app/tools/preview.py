"""Save local draft versions and return their authoritative artifacts; never publish."""

import json
from app.context import WorkflowContext
from app.qa.engine import check_draft, normalize_text
from app.schemas import Platform, PostPreview


def render_preview(platform: Platform, text: str, media_suggestion: str, context: WorkflowContext | None) -> tuple[str, dict]:
    if context is None or context.brief is None or context.repository is None or context.campaign_id is None:
        error = "A current persisted campaign context is required. No draft was saved."
        return json.dumps({"error": error}), {"error": error, "previews": []}
    if platform not in context.brief.platforms:
        error = f"{platform} was not requested. Use only: {', '.join(context.brief.platforms)}."
        return json.dumps({"error": error}), {"error": error, "previews": []}
    if context.revision_draft_id:
        try:
            target = context.repository.get_draft(context.brief.tenant_id, context.revision_draft_id)
        except Exception:
            target = None
        if target is None or target["platform"] != platform:
            error = "A revision may only update its specified existing draft and platform."
            return json.dumps({"error": error}), {"error": error, "previews": []}
    text = normalize_text(text)
    issues = check_draft(platform, text, media_suggestion, context.brief)
    if not text:
        error = "Post text is empty. Write a complete draft and call the preview tool again."
        return json.dumps({"error": error}), {"error": error, "previews": [], "qa_issues": [issue.model_dump() for issue in issues]}
    if context.revision_draft_id:
        saved = context.repository.save_agent_revision(context.brief.tenant_id, context.revision_draft_id,
            text, media_suggestion.strip(), [issue.model_dump() for issue in issues])
    else:
        saved = context.repository.save_draft(context.brief.tenant_id, context.campaign_id, platform, text,
            media_suggestion.strip(), [issue.model_dump() for issue in issues])
    preview = PostPreview.model_validate(saved).model_dump()
    return json.dumps(preview, ensure_ascii=False), {"previews": [preview]}
