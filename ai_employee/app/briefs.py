"""Code, not a model, owns campaign identity, supplied facts and platform selection."""

import re
from uuid import uuid4
from app.schemas import BrandProfile, CampaignBrief, PLATFORMS

_PATTERNS = {
    "facebook": r"\bface\s*book\b", "instagram": r"\binstagram\b",
    "x": r"\b(?:x|twitter)\b", "linkedin": r"\blinked\s*in\b",
}


def resolve_platforms(query: str, explicit=None) -> list:
    if explicit is not None:
        return list(dict.fromkeys(explicit))
    found = [platform for platform in PLATFORMS if re.search(_PATTERNS[platform], query, re.IGNORECASE)]
    return found or list(PLATFORMS)


def build_brief(query: str, context, *, run_id=None, tenant_id="local", topic=None, facts=None, call_to_action=None) -> CampaignBrief:
    brand = context.brand or BrandProfile()
    return CampaignBrief(
        run_id=run_id or str(uuid4()), tenant_id=tenant_id, request_text=query,
        topic=topic, facts=list(facts) if facts else [query],
        platforms=resolve_platforms(query, context.platforms), brand=brand,
        audience=brand.audience or None, tone=brand.tone or None,
        language=brand.language or None, call_to_action=call_to_action,
    )


def handoff_error(brief: CampaignBrief, context) -> dict | None:
    if context is None or context.brief is None:
        return {"error": "No authoritative campaign brief is attached to this request.", "previews": []}
    if brief != context.brief:
        return {
            "error": "CampaignBrief fields cannot be changed during delegation. Copy the authoritative campaign_brief exactly; put creative suggestions in notes.",
            "campaign_brief": context.brief.model_dump(), "previews": [],
        }
    return None
