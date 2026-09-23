"""
TikTok Content Posting API (официально):
- черновики / inbox: scope video.upload
- POST /v2/post/publish/inbox/video/init/

Зарегистрируйте приложение на developers.tiktok.com, получите OAuth
пользователя и реализуйте upload. Неофициальные обходы не используются.
"""


def upload_video(path, caption=""):
    raise NotImplementedError(
        "Подключите официальный TikTok Content Posting API "
        "(inbox/drafts). См. README."
    )
