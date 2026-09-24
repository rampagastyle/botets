# YouTube Data API (загрузка на свой канал) — OAuth.
# Положите client_secret.json и youtube_token.json в credentials/
# или задайте YOUTUBE_CLIENT_SECRET / YOUTUBE_TOKEN в env.

from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def authenticate(
    credentials_file="credentials/client_secret.json",
    token_file="credentials/youtube_token.json",
):
    token = Path(token_file)
    if token.exists():
        from google.oauth2.credentials import Credentials

        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        creds = flow.run_local_server(port=0)
        token.parent.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def upload_short(path, title, description=""):
    youtube = authenticate()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "categoryId": "22",
        },
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]
