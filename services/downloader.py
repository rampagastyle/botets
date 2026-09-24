from pathlib import Path
import os
import yt_dlp

MAX_DOWNLOAD_HEIGHT = 1080
MIN_DOWNLOAD_HEIGHT = 480


def _is_youtube(url: str) -> bool:
    value = (url or '').lower()
    return 'youtube.com/' in value or 'youtu.be/' in value


def _quality(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 480
    if value not in (480, 720, 1080):
        value = min(MAX_DOWNLOAD_HEIGHT, max(MIN_DOWNLOAD_HEIGHT, value))
        value = min((480, 720, 1080), key=lambda x: abs(x - value))
    return value


def _youtube_profiles():
    raw = os.getenv('YTDLP_PLAYER_CLIENTS', '').strip()
    if raw:
        clients = [x.strip() for x in raw.split(',') if x.strip()]
        return [clients] if clients else [None]
    return [None, ['web_embedded'], ['android_vr']]


def download(url, out_dir, quality=480, progress_callback=None, subtitle_lang='ru', download_subtitles=False):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    quality = _quality(quality)
    subtitle_lang = 'en' if str(subtitle_lang).lower() == 'en' else 'ru'
    cookies = Path(os.getenv('YTDLP_COOKIES_FILE', 'credentials/cookies.txt'))

    def hook(d):
        if not progress_callback:
            return
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes') or 0
            try:
                total_n = float(total) if total is not None else 0
                downloaded_n = float(downloaded or 0)
            except (TypeError, ValueError):
                total_n = downloaded_n = 0
            if total_n > 0:
                pct = max(0, min(100, int(downloaded_n * 100 / total_n)))
                speed = d.get('speed') or 0
                try:
                    speed_mb = float(speed) / 1024 / 1024 if speed else 0
                except (TypeError, ValueError):
                    speed_mb = 0
                progress_callback(pct, f'Stream {quality}p… {pct}% ({speed_mb:.1f} MB/s)')
            else:
                progress_callback(None, f'Downloading {quality}p…')
        elif d.get('status') == 'finished':
            progress_callback(100, 'Download complete…')

    fmt = (
        f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/'
        f'bestvideo[height<={quality}]+bestaudio/'
        f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best[height<=1080]'
    )
    base_opts = {
        'outtmpl': str(Path(out_dir) / '%(id)s.%(ext)s'),
        'format': fmt,
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [hook],
        'writesubtitles': bool(download_subtitles),
        'writeautomaticsub': bool(download_subtitles),
        'subtitleslangs': [subtitle_lang, f'{subtitle_lang}-*'],
        'subtitlesformat': 'vtt/best',
        'retries': 2,
        'fragment_retries': 2,
        'extractor_retries': 2,
        'concurrent_fragment_downloads': 1,
        'socket_timeout': 30,
        'buffersize': '1M',
        'http_chunk_size': 10 * 1024 * 1024,
        'overwrites': True,
    }
    is_yt = _is_youtube(url)
    if is_yt:
        base_opts['js_runtimes'] = {'node': {}}
        base_opts['remote_components'] = {'ejs:github': {}}
    if cookies.exists() and cookies.stat().st_size > 0:
        base_opts['cookiefile'] = str(cookies)

    last_error = None
    profiles = _youtube_profiles() if is_yt else [None]
    for client_profile in profiles:
        opts = dict(base_opts)
        if client_profile:
            opts['extractor_args'] = {'youtube': {'player_client': client_profile}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = Path(ydl.prepare_filename(info))
                mp4 = path.with_suffix('.mp4')
                video = mp4 if mp4.exists() else path
                if not video.exists():
                    for candidate in Path(out_dir).glob(path.stem + '.*'):
                        if candidate.suffix.lower() in {'.mp4', '.mkv', '.webm', '.mov'}:
                            video = candidate
                            break
                if not video.exists():
                    raise RuntimeError('yt-dlp completed but the output video was not found')
                candidates = sorted(Path(out_dir).glob(path.stem + '.*.vtt'))
                if not candidates:
                    candidates = sorted(Path(out_dir).glob('*.vtt'))
                if candidates:
                    target = Path(out_dir) / 'source_subtitles.vtt'
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
        if not cookies.exists() or cookies.stat().st_size == 0:
            hint = (' YouTube is rejecting requests from this Railway IP. '
                    'For videos you are permitted to download, add a fresh Netscape-format '
                    'cookies.txt as the Railway variable YTDLP_COOKIES.')
        else:
            hint = ' YouTube rejected the current session; refresh YTDLP_COOKIES and redeploy.'
        raise RuntimeError(
            'YouTube download failed after all supported yt-dlp profiles.' + hint +
            f' Last error: {last_error}'
        ) from last_error
    raise RuntimeError(str(last_error)) from last_error

