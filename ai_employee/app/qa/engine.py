"""Conservative lexical QA, not semantic fact verification or connector validation."""

import re
import unicodedata
from urllib.parse import urlsplit
from app.schemas import CampaignBrief, Platform, QAIssue

EDITORIAL_BUDGETS = {"facebook": 1200, "instagram": 1800, "x": 260, "linkedin": 2000}
_MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
_PATTERNS = {
    "URL": r"(?:https?://|www\.)[^\s<>]+|(?<![\w@])(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,63}(?:/[^\s<>]*)?",
    "PRICE": r"(?:[$€£₹]\s*|\b(?:USD|PKR|Rs\.?)\s*)\d[\d,.]*(?:\.\d+)?|\b\d[\d,.]*\s*(?:USD|PKR|dollars|rupees)\b",
    "DATE": rf"\b(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?|\d{{1,2}}\s+{_MONTH}(?:\s+\d{{4}})?|tomorrow|tonight|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
    "HANDLE": r"(?<![\w@])@[A-Za-z0-9_][A-Za-z0-9_.]*",
    "PHONE": r"(?<!\w)\+?\d[\d ()+.-]{5,}\d(?!\w)",
}
_DEFAULT_BANS = ("guaranteed results", "guaranteed returns", "risk-free investment", "double your money", "100% guaranteed", "cures diabetes", "cures cancer")


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _canonical(kind: str, text: str) -> str:
    if kind == "PHONE":
        return re.sub(r"\D", "", text)
    if kind == "URL":
        text = normalize_text(text).rstrip(".,!?;:)")
        try:
            parsed = urlsplit(text if "://" in text else "https://" + text)
        except ValueError:
            return "invalid-url:" + text
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}{'?' + parsed.query if parsed.query else ''}{'#' + parsed.fragment if parsed.fragment else ''}"
    return re.sub(r"\s+", "", normalize_text(text).casefold()).rstrip(".,!?;:)")


def _tokens(kind: str, text: str) -> set[str]:
    matches = list(re.finditer(_PATTERNS[kind], text, re.IGNORECASE))
    if kind == "PHONE":
        dates = list(re.finditer(_PATTERNS["DATE"], text, re.IGNORECASE))
        matches = [match for match in matches if 7 <= len(_canonical(kind, match.group())) <= 15
                   and not any(match.start() < date.end() and date.start() < match.end() for date in dates)]
    return {_canonical(kind, match.group()) for match in matches}


def hashtag_count(text: str) -> int:
    return len(re.findall(r"(?<!\w)#\w+", text))


def check_draft(platform: Platform, text: str, media_suggestion: str, brief: CampaignBrief) -> list[QAIssue]:
    issues = []
    def add(severity, code, message):
        issues.append(QAIssue(severity=severity, code=code, message=message))
    if not text.strip():
        add("blocking", "EMPTY_TEXT", "Draft text is empty.")
    if platform not in brief.platforms:
        add("blocking", "PLATFORM_NOT_ALLOWED", "Platform is outside the campaign brief.")
    if len(text) > EDITORIAL_BUDGETS[platform]:
        add("warning", "OVER_BUDGET", f"Draft exceeds the internal {EDITORIAL_BUDGETS[platform]}-character editorial budget.")
    evidence = "\n".join([brief.request_text, *brief.facts, brief.call_to_action or "", brief.brand.model_dump_json()])
    for kind in _PATTERNS:
        if _tokens(kind, text) - _tokens(kind, evidence):
            add("blocking", f"UNSUPPLIED_{kind}", f"Draft contains a {kind.lower()} not supplied in the brief or brand profile.")
    banned = [*_DEFAULT_BANS, *brief.brand.forbidden_claims]
    if any(claim.strip() and claim.casefold() in text.casefold() for claim in banned):
        add("blocking", "FORBIDDEN_CLAIM", "Draft contains a forbidden or exaggerated claim.")
    hashtags = re.findall(r"(?<!\w)#\w+", text.casefold())
    if len(hashtags) != len(set(hashtags)):
        add("warning", "DUPLICATE_HASHTAG", "Draft repeats a hashtag.")
    if platform == "instagram" and not media_suggestion.strip():
        add("warning", "MISSING_VISUAL_IDEA", "Add a concrete Instagram visual suggestion.")
    return issues
