from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import BOT_TOKEN, WORK_DIR

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
STATE_TTL = 15 * 60


def _redirect_uri() -> str:
    # Prefer the public Railway URL. This prevents a stale YOUTUBE_REDIRECT_URI
    # variable from silently causing Google's redirect_uri_mismatch.
    base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base:
        domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip().strip("/")
        if domain:
            base = domain if domain.startswith("http") else "https://" + domain
    if not base:
        explicit = os.getenv("YOUTUBE_REDIRECT_URI", "").strip()
        if explicit:
            return explicit.rstrip("/")
    if not base:
        # Current project fallback; PUBLIC_BASE_URL should still be set in Railway.
        base = "https://botets-production.up.railway.app"
    return base + "/oauth/youtube/callback"


def redirect_uri() -> str:
    return _redirect_uri()

def _client_config() -> dict:
    """Load Google Web OAuth client JSON.

    Supported forms:
      1) YOUTUBE_CLIENT_SECRET_JSON = full JSON object
      2) YOUTUBE_CLIENT_SECRET = full JSON object
      3) YOUTUBE_CLIENT_SECRET = path to a JSON file
      4) credentials/client_secret.json inside the container

    A common mistake is leaving a placeholder such as
    'JSON_OT_Google_OAuth' in Railway. We fail with a clear message instead
    of exposing a confusing JSONDecodeError.
    """
    raw_json = os.getenv("YOUTUBE_CLIENT_SECRET_JSON", "").strip()
    raw = raw_json or os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()

    candidates: list[Path] = []
    if raw and not raw.startswith("{"):
        candidates.append(Path(raw))
    candidates.append(Path(__file__).resolve().parent.parent / "credentials" / "client_secret.json")
    candidates.append(Path("credentials/client_secret.json"))

    if raw.startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("YOUTUBE_CLIENT_SECRET содержит повреждённый JSON OAuth") from exc
    else:
        data = None
        for path in candidates:
            if path.exists() and path.is_file():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    break
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Файл OAuth повреждён: {path}") from exc

    if not data:
        raise RuntimeError(
            "Не найден Google OAuth client JSON. В Railway добавь "
            "YOUTUBE_CLIENT_SECRET_JSON и вставь содержимое скачанного "
            "client_secret.json. Не используй текст вроде 'JSON_OT_Google_OAuth'."
        )

    if not isinstance(data, dict) or not (data.get("web") or data.get("installed")):
        raise RuntimeError(
            "Неверный OAuth JSON: нужен client_secret.json от Google Cloud "
            "для типа приложения Web application."
        )
    return data


def _state_secret() -> bytes:
    secret = os.getenv("OAUTH_STATE_SECRET", "").strip() or BOT_TOKEN
    if not secret:
        raise RuntimeError("Нужен OAUTH_STATE_SECRET (или BOT_TOKEN) для защиты OAuth state")
    return secret.encode("utf-8")


def _make_state(user_id: int | str) -> str:
    payload = {
        "uid": str(user_id),
        "iat": int(time.time()),
        "nonce": secrets.token_urlsafe(16),
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    sig = hmac.new(_state_secret(), encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return encoded + "." + sig


def _parse_state(state: str) -> str:
    try:
        encoded, sig = state.split(".", 1)
        expected = hmac.new(_state_secret(), encoded.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        issued = int(payload["iat"])
        user_id = str(payload["uid"])
    except Exception as exc:
        raise RuntimeError("OAuth state недействителен. Нажми Connect YouTube ещё раз.") from exc

    if not user_id or time.time() - issued > STATE_TTL or issued > time.time() + 60:
        raise RuntimeError("OAuth state истёк. Нажми Connect YouTube и пройди авторизацию заново.")
    return user_id


def token_path(user_id: int | str) -> Path:
    path = WORK_DIR / str(user_id) / "youtube_token.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _flow(state: str | None = None) -> Flow:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = _redirect_uri()
    return flow


def create_auth_url(user_id: int | str) -> str:
    state = _make_state(user_id)
    flow = _flow(state)
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url


def handle_callback(code: str, state: str) -> str:
    if not code:
        raise RuntimeError("Google не вернул authorization code")
    user_id = _parse_state(state)
    flow = _flow(state)
    flow.fetch_token(code=code)
    token_path(user_id).write_text(flow.credentials.to_json(), encoding="utf-8")
    return user_id


def is_connected(user_id: int | str) -> bool:
    path = token_path(user_id)
    if not path.exists():
        return False
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(str(path), SCOPES)
        return bool(creds.refresh_token or creds.valid)
    except Exception:
        return False


def authenticate(user_id: int | str):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    path = token_path(user_id)
    if not path.exists():
        raise RuntimeError("YouTube не подключён. Открой /youtube и нажми Connect YouTube.")
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
    if not creds.valid:
        raise RuntimeError("Авторизация YouTube истекла. Открой /youtube и подключи канал заново.")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_short(
    user_id: int | str,
    path: str | Path,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy: str = "private",
) -> str:
    privacy = privacy if privacy in {"private", "unlisted", "public"} else "private"
    youtube = authenticate(user_id)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": (tags or [])[:500],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(
        str(path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=8 * 1024 * 1024,
    )
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]
