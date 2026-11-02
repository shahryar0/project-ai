import hashlib
import json
from app.qa.engine import normalize_text


def content_hash(platform: str, text: str, media_asset_hash: str = "") -> str:
    payload = json.dumps([platform, normalize_text(text), media_asset_hash], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
