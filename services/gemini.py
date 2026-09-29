from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from config import GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger(__name__)

# Перебор моделей: 401/404 на одной — пробуем следующую
_MODEL_CANDIDATES = [
    (GEMINI_MODEL or "").strip() or "gemini-2.0-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-2.0-flash-001",
]


def _api_key() -> str:
    # Убрать кавычки/пробелы/переносы из Railway Variable
    key = (GEMINI_API_KEY or "").strip().strip('"').strip("'")
    key = "".join(key.split())  # убрать \n внутри
    return key


def _client():
    key = _api_key()
    if not key:
        log.warning("GEMINI_API_KEY is empty")
        return None
    try:
        from google import genai
        return genai.Client(api_key=key)
    except Exception as e:
        log.warning("Gemini client init failed: %s", e)
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


def _is_auth_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return "401" in s or "unauthorized" or "invalid api key" in s or "api key not valid" in s


def analyze_clip(path: Path, part_index: int = 0, total_parts: int = 1) -> dict:
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
Не выдумывай факты, не обещай вирусность.
""".strip()

    models = []
    for m in _MODEL_CANDIDATES:
        if m and m not in models:
            models.append(m)

    last_err = None
    for model in models:
        uploaded = None
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

            response = client.models.generate_content(
                model=model,
                contents=[uploaded, prompt],
                config={"temperature": 0.35, "max_output_tokens": 900},
            )
            text = getattr(response, "text", "") or ""
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("no json in response")
            data = json.loads(text[start : end + 1])
            return _normalize(data, part_index, total_parts)
        except Exception as e:
            last_err = e
            log.warning("Gemini model %s failed: %s", model, e)
            if "401" in str(e) or "Unauthorized" in str(e) or "API_KEY" in str(e).upper():
                # Ключ неверный — нет смысла крутить другие модели
                log.error(
                    "GEMINI 401 Unauthorized: проверьте GEMINI_API_KEY в Railway "
                    "(ключ с https://aistudio.google.com/apikey, без кавычек и пробелов)"
                )
                break
        finally:
            if uploaded is not None:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:
                    pass

    if last_err:
        log.warning("Gemini analyze_clip fallback due to: %s", last_err)
    return _fallback(part_index, total_parts)


def summarize_banner_rules(rules_text: str, rules_url: str = "") -> str:
    client = _client()
    if not client or not (rules_text or "").strip():
        return (rules_text or rules_url or "Правила не распознаны.")[:800]

    prompt = f"""
Ниже текст правил размещения рекламного видео-баннера.
Краткое резюме на русском (5-10 пунктов): длительность, место в ролике, звук, запреты.
Только текст.

Источник: {rules_url}

ТЕКСТ:
{(rules_text or '')[:5000]}
""".strip()

    models = []
    for m in _MODEL_CANDIDATES:
        if m and m not in models:
            models.append(m)

    for model in models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"temperature": 0.2, "max_output_tokens": 700},
            )
            text = (getattr(response, "text", "") or "").strip()
            if text:
                return text[:1500]
        except Exception as e:
            log.warning("summarize_banner_rules %s: %s", model, e)
            if "401" in str(e) or "Unauthorized" in str(e):
                break
    return (rules_text or "")[:800]
