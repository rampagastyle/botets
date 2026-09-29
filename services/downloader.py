from pathlib import Path
import os
import yt_dlp


def _normalize_proxy(raw: str):
    if not raw:
        return None
    line = ""
    for part in str(raw).replace("\r", "\n").split("\n"):
        part = part.strip()
        if part:
            line = part
            break
    if not line:
        return None
    if "://" not in line:
        if line[:1].isdigit() or line.startswith("["):
            line = "http://" + line
        else:
            return None
    if line.count("://") != 1:
        return None
    after = line.split("://", 1)[1]
    if any(ch in after for ch in ("\n", "\r", " ")):
        return None
    return line


def download(url, out_dir, quality=720, progress_callback=None):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    try:
        quality = int(quality)
    except (TypeError, ValueError):
        quality = 720
    if quality not in (480, 720, 1080):
        quality = min((480, 720, 1080), key=lambda x: abs(x - quality))
    cookies = Path(os.getenv("YTDLP_COOKIES_FILE", "credentials/cookies.txt"))
    proxy = _normalize_proxy(os.getenv("YTDLP_PROXY") or "")

    def hook(d):
        if not progress_callback:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes") or 0
            try:
                total_n = float(total) if total else 0.0
                downloaded_n = float(downloaded or 0)
            except (TypeError, ValueError):
                total_n = downloaded_n = 0.0
            if total_n > 0:
                pct = int(downloaded_n * 100 / total_n)
                speed = d.get("speed") or 0
                try:
                    speed_mb = float(speed) / 1024 / 1024 if speed else 0.0
                except (TypeError, ValueError):
                    speed_mb = 0.0
                progress_callback(pct, f"⬇️  {quality}p · {pct}% · {speed_mb:.1f} МБ/с")
            else:
                progress_callback(None, f"⬇️  Скачивание {quality}p…")
        elif d.get("status") == "finished":
            progress_callback(100, "✅ Файл получен")

    opts = {
        "outtmpl": str(Path(out_dir) / "%(id)s.%(ext)s"),
        "format": (
            f"bestvideo[height<={quality}]+bestaudio/"
            f"best[height<={quality}]/best[height<=1080]/best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "retries": 3,
        "socket_timeout": 30,
    }
    u = (url or "").lower()
    if "youtube.com" in u or "youtu.be" in u:
        opts["extractor_args"] = {"youtube": {"player_client": ["android", "web"]}}
    if cookies.exists() and cookies.stat().st_size > 0:
        opts["cookiefile"] = str(cookies)
    if proxy:
        opts["proxy"] = proxy

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
        mp4 = path.with_suffix(".mp4")
        if mp4.exists():
            return mp4
        for p in Path(out_dir).glob(path.stem + ".*"):
            if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}:
                return p
        return path
