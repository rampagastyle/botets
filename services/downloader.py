from pathlib import Path
import os
import yt_dlp

MAX_DOWNLOAD_HEIGHT = 1080


def _is_youtube(url: str) -> bool:
    value = (url or '').lower()
    return 'youtube.com/' in value or 'youtu.be/' in value


def download(url, out_dir, quality=480, progress_callback=None, subtitle_lang='ru'):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    try:
        quality = int(quality)
    except (TypeError, ValueError):
        quality = 480
    quality = min(MAX_DOWNLOAD_HEIGHT, max(480, quality))
    subtitle_lang = 'en' if str(subtitle_lang).lower() == 'en' else 'ru'
    cookies = Path('credentials/cookies.txt')

    def hook(d):
        if not progress_callback:
            return
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes') or 0
            if total:
                pct = int(downloaded * 100 / total)
                speed = d.get('speed') or 0
                speed_mb = speed / 1024 / 1024 if speed else 0
                progress_callback(pct, f'Stream {quality}p… {pct}% ({speed_mb:.1f} MB/s)')
            else:
                progress_callback(None, f'Downloading {quality}p…')
        elif d.get('status') == 'finished':
            progress_callback(100, 'Download complete…')

    # One stream + one audio stream. Avoids downloading 4K/8K just to resize it later.
    fmt = (
        f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/'
        f'bestvideo[height<={quality}]+bestaudio/'
        f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best[height<=1080]'
    )
    opts = {
        'outtmpl': str(Path(out_dir) / '%(id)s.%(ext)s'),
        'format': fmt,
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [hook],
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': [subtitle_lang, f'{subtitle_lang}-*'],
        'subtitlesformat': 'vtt/best',
        'retries': 3,
        'fragment_retries': 3,
        'concurrent_fragment_downloads': 1,
        'socket_timeout': 30,
        'buffersize': '1M',
        'http_chunk_size': 10 * 1024 * 1024,
        'overwrites': True,
    }

    # YouTube may require a JS runtime for current player challenges. Node is only
    # spawned by yt-dlp when needed, so it does not permanently consume RAM.
    if _is_youtube(url):
        opts['extractor_args'] = {'youtube': {'player_client': ['web_safari', 'android']}}
        opts['js_runtimes'] = {'node': {}}
        opts['remote_components'] = {'ejs:github': {}}

    if cookies.exists() and cookies.stat().st_size > 0:
        opts['cookiefile'] = str(cookies)

    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
        except Exception as first_error:
            if _is_youtube(url):
                # A second, less restrictive client profile helps when a specific
                # player client is temporarily unavailable.
                opts.pop('extractor_args', None)
                with yt_dlp.YoutubeDL(opts) as retry_ydl:
                    try:
                        info = retry_ydl.extract_info(url, download=True)
                    except Exception as second_error:
                        raise RuntimeError(
                            'YouTube download failed. Update yt-dlp or add a fresh browser cookies.txt. '
                            f'First: {first_error}; Retry: {second_error}'
                        ) from second_error
            else:
                raise

        path = Path(ydl.prepare_filename(info))
        mp4 = path.with_suffix('.mp4')
        video = mp4 if mp4.exists() else path
        if not video.exists():
            for p in Path(out_dir).glob(path.stem + '.*'):
                if p.suffix.lower() in {'.mp4', '.mkv', '.webm', '.mov'}:
                    video = p
                    break

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
