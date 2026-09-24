from pathlib import Path
import os
import yt_dlp

MAX_DOWNLOAD_HEIGHT = 1080
MIN_DOWNLOAD_HEIGHT = 480


def _is_youtube(url: str) -> bool:
    value = (url or "").lower()
    return "youtube.com/" in value or "youtu.be/" in value or "youtube.com/shorts/" in value


def _quality(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 480
    if value not in (480, 720, 1080):
        value = min((480, 720, 1080), key=lambda x: abs(x - int(value)))
    return int(value)


def _youtube_profiles():
    """
    Порядок клиентов: сначала «мобильные»/TV — меньше 403 на googlevideo
    с IP датацентра. Переопределение: YTDLP_PLAYER_CLIENTS=android,ios,tv
    """
    raw = os.getenv("YTDLP_PLAYER_CLIENTS", "").strip()
    if raw:
        clients = [x.strip() for x in raw.split(",") if x.strip()]
        return [[c] for c in clients] if clients else [[None]]
    return [
        ["android"],
        ["ios"],
        ["tv_embedded"],
        ["mweb"],
        ["web_embedded"],
        ["web"],
        None,
    ]


def _base_format(quality: int) -> str:
    q = int(quality)
    return (
        f"bestvideo[height<={q}][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={q}]+bestaudio/"
        f"best[height<={q}][ext=mp4]/best[height<={q}]/"
        f"best[height<=1080]/best"
    )


def _youtube_format(quality: int) -> str:
    """Для YouTube отдельные progressive-форматы часто стабильнее на 403."""
    q = int(quality)
    return (
        f"best[height<={q}][ext=mp4]/"
        f"bestvideo[height<={q}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
        f"bestvideo[height<={q}]+bestaudio/"
        f"best[height<={q}]/best"
    )


def download(
    url,
    out_dir,
    quality=480,
    progress_callback=None,
    subtitle_lang="ru",
    download_subtitles=False,
):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    quality = _quality(quality)
    subtitle_lang = "en" if str(subtitle_lang).lower() == "en" else "ru"
    cookies = Path(os.getenv("YTDLP_COOKIES_FILE", "credentials/cookies.txt"))
    proxy = (os.getenv("YTDLP_PROXY") or os.getenv("HTTPS_PROXY") or "").strip() or None

    def hook(d):
        if not progress_callback:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes") or 0
            try:
                total_n = float(total) if total is not None else 0.0
                downloaded_n = float(downloaded or 0)
            except (TypeError, ValueError):
                total_n = downloaded_n = 0.0
            if total_n > 0:
                pct = max(0, min(100, int(downloaded_n * 100 / total_n)))
                speed = d.get("speed") or 0
                try:
                    speed_mb = float(speed) / 1024 / 1024 if speed else 0.0
                except (TypeError, ValueError):
                    speed_mb = 0.0
                progress_callback(
                    pct, f"Stream {quality}p… {pct}% ({speed_mb:.1f} MB/s)"
                )
            else:
                progress_callback(None, f"Downloading {quality}p…")
        elif d.get("status") == "finished":
            progress_callback(100, "Download complete…")

    is_yt = _is_youtube(url)
    base_opts = {
        "outtmpl": str(Path(out_dir) / "%(id)s.%(ext)s"),
        "format": _youtube_format(quality) if is_yt else _base_format(quality),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "writesubtitles": bool(download_subtitles),
        "writeautomaticsub": bool(download_subtitles),
        "subtitleslangs": [subtitle_lang, f"{subtitle_lang}-*"],
        "subtitlesformat": "vtt/best",
        "retries": 3,
        "fragment_retries": 3,
        "extractor_retries": 3,
        "concurrent_fragment_downloads": 1,
        "socket_timeout": 30,
        "http_chunk_size": 10 * 1024 * 1024,
        "overwrites": True,
        "nocheckcertificate": False,
        "geo_bypass": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        },
    }
    if proxy:
        base_opts["proxy"] = proxy

    if is_yt:
        # EJS / node optional — не падаем, если runtime нет
        try:
            base_opts["js_runtimes"] = {"node": {}}
            base_opts["remote_components"] = {"ejs:github": {}}
        except Exception:
            pass

    if cookies.exists() and cookies.stat().st_size > 0:
        base_opts["cookiefile"] = str(cookies)

    last_error = None
    profiles = _youtube_profiles() if is_yt else [None]

    for client_profile in profiles:
        opts = dict(base_opts)
        if client_profile:
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": client_profile,
                    # меньше проблем с SABR на части клиентов
                    "player_skip": ["webpage", "configs"],
                }
            }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = Path(ydl.prepare_filename(info))
                mp4 = path.with_suffix(".mp4")
                video = mp4 if mp4.exists() else path
                if not video.exists():
                    for candidate in Path(out_dir).glob(path.stem + ".*"):
                        if candidate.suffix.lower() in {
                            ".mp4",
                            ".mkv",
                            ".webm",
                            ".mov",
                        }:
                            video = candidate
                            break
                if not video.exists():
                    raise RuntimeError(
                        "yt-dlp completed but the output video was not found"
                    )
                candidates = sorted(Path(out_dir).glob(path.stem + ".*.vtt"))
                if not candidates:
                    candidates = sorted(Path(out_dir).glob("*.vtt"))
                if candidates:
                    target = Path(out_dir) / "source_subtitles.vtt"
                    if candidates[0] != target:
                        candidates[0].replace(target)
                    for extra in candidates[1:]:
                        try:
                            extra.unlink()
                        except OSError:
                            pass
                return video
        except Exception as exc:
            last_error = exc
            if not is_yt:
                raise

    if is_yt:
        has_cookies = cookies.exists() and cookies.stat().st_size > 0
        if not has_cookies:
            hint = (
                " YouTube блокирует IP Railway без cookies. "
                "Экспортируйте cookies.txt (Netscape) из браузера, "
                "вставьте в Variable YTDLP_COOKIES и Redeploy. "
                "Опционально: YTDLP_PROXY=http://user:pass@host:port"
            )
        else:
            hint = (
                " Сессия/cookies отклонены (403). Обновите YTDLP_COOKIES "
                "(свежий экспорт после входа на youtube.com), Redeploy. "
                "Если снова 403 — нужен residential proxy: YTDLP_PROXY=..."
            )
        raise RuntimeError(
            "YouTube download failed after all supported yt-dlp profiles."
            + hint
            + f" Last error: {last_error}"
        ) from last_error
    raise RuntimeError(str(last_error)) from last_error
