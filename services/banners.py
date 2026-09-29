from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

from config import BANNERS_DIR, BANNERS_INDEX


def _ensure():
    BANNERS_DIR.mkdir(parents=True, exist_ok=True)
    if not BANNERS_INDEX.exists():
        BANNERS_INDEX.write_text("[]", encoding="utf-8")


def list_banners() -> list[dict]:
    _ensure()
    try:
        data = json.loads(BANNERS_INDEX.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def get_banner(banner_id: str) -> dict | None:
    for b in list_banners():
        if b.get("id") == banner_id:
            return b
    return None


def get_banner_path(banner_id: str) -> Path | None:
    b = get_banner(banner_id)
    if not b:
        return None
    p = Path(b.get("path") or "")
    if p.exists():
        return p
    return None


def save_banner(name: str, rules_url: str, rules_summary: str, src_file: Path) -> dict:
    _ensure()
    bid = uuid.uuid4().hex[:12]
    dest_dir = BANNERS_DIR / bid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "banner.mp4"
    shutil.copy2(src_file, dest)
    entry = {
        "id": bid,
        "name": name.strip()[:80],
        "rules_url": (rules_url or "").strip()[:500],
        "rules_summary": (rules_summary or "").strip()[:2000],
        "path": str(dest),
    }
    rows = list_banners()
    rows.append(entry)
    BANNERS_INDEX.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def delete_banner(banner_id: str) -> bool:
    rows = list_banners()
    new_rows = [b for b in rows if b.get("id") != banner_id]
    if len(new_rows) == len(rows):
        return False
    BANNERS_INDEX.write_text(json.dumps(new_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    d = BANNERS_DIR / banner_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    return True


def fetch_rules_text(url: str, max_chars: int = 6000) -> str:
    """Скачать текст страницы правил (telegra.ph и др.)."""
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; VideoProcessingBot/15)"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="ignore")
    # strip tags roughly
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]
