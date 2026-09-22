from pathlib import Path
import yt_dlp


def download(url, out_dir, progress_callback=None):
    """
    progress_callback(percent: int | None, text: str) — вызывается из потока yt-dlp.
    percent: 0..100 или None, если неизвестно.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    cookies = Path("credentials/cookies.txt")

    def hook(d):
        if not progress_callback:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes") or 0
            if total:
                pct = int(downloaded * 100 / total)
                speed = d.get("speed") or 0
                speed_mb = speed / 1024 / 1024 if speed else 0
                progress_callback(pct, f"Скачиваю… {pct}% ({speed_mb:.1f} МБ/с)")
            else:
                progress_callback(None, "Скачиваю…")
        elif d.get("status") == "finished":
            progress_callback(100, "Скачивание завершено, сохраняю файл…")

    opts = {
        "outtmpl": str(Path(out_dir) / "%(id)s.%(ext)s"),
        "format": "bestvideo[height<=1080]+bestaudio/best/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    if cookies.exists():
        opts["cookiefile"] = str(cookies)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
        mp4 = path.with_suffix(".mp4")
        return mp4 if mp4.exists() else path