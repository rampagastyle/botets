from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import WORK_DIR

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
_AUTH_STATES: dict[str, tuple[str, float]] = {}


def _redirect_uri() -> str:
    explicit = os.getenv("YOUTUBE_REDIRECT_URI", "").strip()
    if explicit:
        return explicit.rstrip("/")
    base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise RuntimeError("Set PUBLIC_BASE_URL or YOUTUBE_REDIRECT_URI in Railway")
    return base + "/oauth/youtube/callback"


def _client_config() -> dict:
    raw = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
    path = Path("credentials/client_secret.json")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return json.loads(Path(raw).read_text(encoding="utf-8"))
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    raise RuntimeError("YOUTUBE_CLIENT_SECRET is not configured")


def token_path(user_id: int | str) -> Path:
    path = WORK_DIR / str(user_id) / "youtube_token.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _flow(state: str | None = None) -> Flow:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = _redirect_uri()
    return flow


def create_auth_url(user_id: int | str) -> str:
    state = secrets.token_urlsafe(24)
    _AUTH_STATES[state] = (str(user_id), time.time() + 600)
    # Keep the in-memory map tiny on a free host.
    for key, (_, expires) in list(_AUTH_STATES.items()):
        if expires < time.time():
            _AUTH_STATES.pop(key, None)
    flow = _flow(state)
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url


def handle_callback(code: str, state: str) -> str:
    item = _AUTH_STATES.pop(state, None)
    if not item or item[1] < time.time():
        raise RuntimeError("OAuth state expired")
    user_id = item[0]
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
        raise RuntimeError("YouTube is not connected. Use /youtube")
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
    if not creds.valid:
        raise RuntimeError("YouTube authorization expired. Use /youtube again")
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
            "tags": tags or [],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]
