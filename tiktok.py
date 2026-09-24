"""
Официальный TikTok Content Posting API.

Черновики (inbox):
  POST https://open.tiktokapis.com/v2/post/publish/inbox/video/init/
  Scope: video.upload

Токен = user access_token после OAuth (не Client Secret приложения).
"""
from __future__ import annotations

import json
from pathlib import Path
import urllib.request

from services.storage import get_account, save_account


def get_tiktok_token(user_id) -> dict | None:
    return get_account(user_id, "tiktok")


def set_tiktok_token(user_id, access_token: str, open_id: str = "", refresh_token: str = ""):
    save_account(
        user_id,
        "tiktok",
        {
            "access_token": access_token.strip(),
            "open_id": open_id.strip(),
            "refresh_token": refresh_token.strip(),
        },
    )


def upload_to_inbox(path: Path, access_token: str) -> dict:
    path = Path(path)
    size = path.stat().st_size
    init_body = {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": size,
            "total_chunk_count": 1,
        }
    }
    req = urllib.request.Request(
        "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
        data=json.dumps(init_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    err = (data.get("error") or {}).get("code", "")
    if err and err != "ok":
        raise RuntimeError(f"TikTok init error: {data}")

    upload_url = data["data"]["upload_url"]
    publish_id = data["data"]["publish_id"]

    video_bytes = path.read_bytes()
    put = urllib.request.Request(
        upload_url,
        data=video_bytes,
        headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{size - 1}/{size}",
        },
        method="PUT",
    )
    with urllib.request.urlopen(put, timeout=300) as resp:
        resp.read()

    return {"publish_id": publish_id, "status": "uploaded_to_inbox"}


def upload_video(path, caption="", access_token=None, user_id=None):
    token = access_token
    if not token and user_id is not None:
        acc = get_tiktok_token(user_id)
        token = (acc or {}).get("access_token")
    if not token:
        raise RuntimeError("TikTok access_token не задан. /tiktok")
    return upload_to_inbox(Path(path), token)
