"""Pure local rendering; no platform API or publishing capability."""

import json
from app.context import WorkflowContext
from app.schemas import Platform, PostPreview

EDITORIAL_BUDGETS = {"facebook": 1200, "instagram": 1800, "x": 260, "linkedin": 2000}


def render_preview(platform: Platform, text: str, media_suggestion: str, context: WorkflowContext | None) -> tuple[str, dict]:
    if context and context.platforms and platform not in context.platforms:
        error = f"{platform} was not requested. Use only: {', '.join(context.platforms)}."
        return json.dumps({"error": error}), {"error": error, "previews": []}
    text = text.strip()
    if not text:
        error = "Post text is empty. Write a complete draft and call the preview tool again."
        return json.dumps({"error": error}), {"error": error, "previews": []}
    warnings = []
    budget = EDITORIAL_BUDGETS[platform]
    if len(text) > budget:
        warnings.append(f"Draft exceeds the internal {budget}-character editorial budget. Shorten it before use.")
    preview = PostPreview(
        platform=platform, text=text, media_suggestion=media_suggestion.strip(),
        character_count=len(text), warnings=warnings,
    ).model_dump()
    return json.dumps(preview, ensure_ascii=False), {"previews": [preview]}
