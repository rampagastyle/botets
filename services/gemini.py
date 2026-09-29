from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from config import GEMINI_API_KEY, GEMINI_MODEL


def _client():
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        return genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        return None


def _fallback(part_index: int, total: int) -> dict:
    n = part_index + 1
    return {
        "title": f"Часть {n}/{total}",
        "description": f"Короткий фрагмент ролика · часть {n} из {total}.",
        "hashtags_yt": ["#shorts", "#youtube", "#fyp"],
        "hashtags_tt": ["#fyp", "#foryou", "#viral"],
    }


def _normalize(data: dict, part_index: int, total: int) -> dict:
    fb = _fallback(part_index, total)

    def tags(key_a, key_b=None):
        raw = data.get(key_a) or (data.get(key_b) if key_b else None) or fb.get(key_a) or []
        if isinstance(raw, str):
            raw = raw.split()
        out = []
        for t in raw:
            t = str(t).strip()
            if not t:
                continue
            if not t.startswith("#"):
                t = "#" + t.lstrip("#")
            if t not in out:
                out.append(t)
        return out[:25]

    title = str(data.get("title") or fb["title"]).strip()[:90]
    desc = str(data.get("description") or fb["description"]).strip()[:500]
    return {
        "title": title,
        "description": desc,
        "hashtags_yt": tags("hashtags_yt", "hashtags"),
        "hashtags_tt": tags("hashtags_tt", "hashtags"),
    }


def analyze_clip(path: Path, part_index: int = 0, total_parts: int = 1) -> dict:
    """Анализ одного куска: title, description, hashtags YT / TikTok."""
    path = Path(path)
    if not path.exists() or path.stat().st_size <= 0:
        return _fallback(part_index, total_parts)

    client = _client()
    if not client:
        return _fallback(part_index, total_parts)

    prompt = f"""
Ты помощник для Shorts / TikTok. Это клип {part_index + 1} из {total_parts}.
Посмотри видео и верни ТОЛЬКО JSON без markdown:
{{
  "title": "короткий цепляющий заголовок до 90 символов на русском",
  "description": "1-3 предложения только о том, что реально в этом куске",
  "hashtags_yt": ["#shorts", "#...", "..."],
  "hashtags_tt": ["#fyp", "#...", "..."]
}}
hashtags_yt — 10-18 тегов для YouTube Shorts.
hashtags_tt — 10-18 тегов для TikTok.
Не выдумывай факты, не обещай вирусность, не копируй один и тот же тег дважды.
""".strip()

    try:
        uploaded = client.files.upload(file=str(path))
        deadline = time.time() + 90
        while getattr(uploaded, "state", None) and getattr(uploaded.state, "name", "") == "PROCESSING":
            if time.time() > deadline:
                raise TimeoutError("Gemini processing timeout")
            time.sleep(1.5)
            uploaded = client.files.get(name=uploaded.name)

        if getattr(getattr(uploaded, "state", None), "name", "") == "FAILED":
            raise RuntimeError("Gemini file failed")

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL or "gemini-2.0-flash",
                contents=[uploaded, prompt],
                config={"temperature": 0.35, "max_output_tokens": 900},
            )
            text = getattr(response, "text", "") or ""
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("no json")
            data = json.loads(text[start : end + 1])
            return _normalize(data, part_index, total_parts)
        finally:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass
    except Exception:
        return _fallback(part_index, total_parts)


def summarize_banner_rules(rules_text: str, rules_url: str = "") -> str:
    """Краткое резюме правил баннера для админа."""
    client = _client()
    if not client or not rules_text.strip():
        return (rules_text or rules_url or "Правила не распознаны.")[:800]

    prompt = f"""
Ниже текст правил размещения рекламного видео-баннера.
Сделай краткое резюме на русском (5-10 пунктов или абзац), что важно:
длительность, место в ролике, звук, запреты.
Только текст, без markdown-заголовков.

Источник: {rules_url}

ТЕКСТ:
{rules_text[:5000]}
""".strip()
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL or "gemini-2.0-flash",
            contents=prompt,
            config={"temperature": 0.2, "max_output_tokens": 700},
        )
        text = (getattr(response, "text", "") or "").strip()
        return text[:1500] if text else rules_text[:800]
    except Exception:
        return rules_text[:800]
