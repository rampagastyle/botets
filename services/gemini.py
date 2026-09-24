from __future__ import annotations

import json
import os
import time
from pathlib import Path

MODEL_DEFAULT = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


def _prompt(language: str, include_subtitles: bool, part_index: int | None, total_parts: int | None) -> str:
    part_note = f"This is clip {part_index + 1} of {total_parts}." if part_index is not None and total_parts else ""
    if language == "en":
        base = f"""
Analyze this individual short video clip for YouTube Shorts. {part_note}
Return ONLY JSON, no markdown:
{{
  "title": "a natural short title under 90 characters",
  "description": "1-3 short sentences describing only what is actually in the clip",
  "hashtags": ["#...", "#..."],
  "tags": ["...", "..."]
}}
Create 15-25 relevant hashtags. Do not repeat the same idea, invent facts, promise virality,
or add unrelated trending tags. tags should contain 8-15 normal YouTube keywords, around 450
characters or less in total. Use English.
""".strip()
    else:
        base = f"""
Проанализируй именно этот отдельный короткий ролик для YouTube Shorts. {part_note}
Верни ТОЛЬКО JSON без markdown:
{{
  "title": "естественный короткий заголовок до 90 символов",
  "description": "1-3 коротких предложения только о том, что реально есть в ролике",
  "hashtags": ["#...", "#..."],
  "tags": ["...", "..."]
}}
Сделай 15-25 релевантных хэштегов. Не повторяй одну и ту же мысль, не выдумывай факты,
не обещай вирусность и не добавляй нерелевантные тренды. tags — 8-15 обычных ключевых слов,
суммарно примерно до 450 символов. Язык: русский.
""".strip()

    if include_subtitles:
        base += """
Также добавь поле "subtitles": массив объектов с точными по возможности временными метками:
[{"start": "00:00.000", "end": "00:02.500", "text": "..."}].
Включай только реально слышимую речь. Если речи нет, верни пустой массив.
"""
    return base


def _fallback(language: str) -> dict:
    if language == "en":
        return {
            "title": "YouTube Short",
            "description": "Short video.",
            "hashtags": ["#shorts", "#youtube", "#video"],
            "tags": ["shorts", "youtube", "video"],
            "subtitles": [],
        }
    return {
        "title": "Новый короткий ролик",
        "description": "Короткое видео.",
        "hashtags": ["#shorts", "#ютуб", "#видео"],
        "tags": ["shorts", "youtube", "видео"],
        "subtitles": [],
    }


def _normalize(data: dict, language: str) -> dict:
    fallback = _fallback(language)
    title = str(data.get("title") or fallback["title"]).replace("<", "").replace(">", "").strip()
    description = str(data.get("description") or fallback["description"]).replace("<", "").replace(">", "").strip()

    hashtags = []
    seen = set()
    for value in data.get("hashtags") or []:
        value = str(value).strip()
        if not value:
            continue
        if not value.startswith("#"):
            value = "#" + value
        value = "#" + "".join(ch for ch in value[1:] if ch.isalnum() or ch == "_")
        key = value.lower()
        if len(value) > 1 and key not in seen:
            seen.add(key)
            hashtags.append(value)
    if not hashtags:
        hashtags = fallback["hashtags"]

    tags = []
    seen_tags = set()
    for value in data.get("tags") or []:
        value = " ".join(str(value).split()).strip().replace(",", " ")
        key = value.lower()
        if value and key not in seen_tags and len(",".join(tags + [value])) <= 450:
            seen_tags.add(key)
            tags.append(value)
    if not tags:
        tags = fallback["tags"]

    subtitles = []
    for cue in data.get("subtitles") or []:
        if not isinstance(cue, dict):
            continue
        start = str(cue.get("start", "")).strip()
        end = str(cue.get("end", "")).strip()
        text = " ".join(str(cue.get("text", "")).split()).strip()
        if start and end and text:
            subtitles.append({"start": start, "end": end, "text": text[:300]})

    return {
        "title": title[:90],
        "description": description[:1200],
        "hashtags": hashtags[:25],
        "tags": tags[:15],
        "subtitles": subtitles[:80],
    }


def analyze_video(
    video_path: str | Path,
    language: str = "ru",
    include_subtitles: bool = False,
    part_index: int | None = None,
    total_parts: int | None = None,
) -> dict:
    """Analyze one clip with Gemini. Returns a safe fallback if API is unavailable."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return _fallback(language)

    path = Path(video_path)
    if not path.exists() or path.stat().st_size <= 0:
        return _fallback(language)

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        uploaded = client.files.upload(file=str(path))

        deadline = time.time() + 120
        while getattr(uploaded, "state", None) and getattr(uploaded.state, "name", "") == "PROCESSING":
            if time.time() > deadline:
                raise TimeoutError("Gemini file processing timeout")
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)

        if getattr(getattr(uploaded, "state", None), "name", "") == "FAILED":
            raise RuntimeError("Gemini file processing failed")

        try:
            response = client.models.generate_content(
                model=MODEL_DEFAULT,
                contents=[uploaded, _prompt(language, include_subtitles, part_index, total_parts)],
                config={"temperature": 0.3, "max_output_tokens": 1600 if include_subtitles else 700},
            )
            text = getattr(response, "text", "") or ""
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("Gemini did not return JSON")
            return _normalize(json.loads(text[start:end + 1]), language)
        finally:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass
    except Exception:
        return _fallback(language)
