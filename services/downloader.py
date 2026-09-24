from pathlib import Path
import yt_dlp

MAX_DOWNLOAD_HEIGHT = 1080


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
                progress_callback(pct, f'Скачиваю {quality}p… {pct}% ({speed_mb:.1f} МБ/с)')
            else:
                progress_callback(None, f'Скачиваю {quality}p…')
        elif d.get('status') == 'finished':
            progress_callback(100, 'Скачивание завершено…')

    opts = {
        'outtmpl': str(Path(out_dir) / '%(id)s.%(ext)s'),
        'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best[height<=1080]',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [hook],
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': [subtitle_lang, f'{subtitle_lang}-*'],
        'subtitlesformat': 'vtt/best',
        'skip_download': False,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }
    if cookies.exists() and cookies.stat().st_size > 0:
        opts['cookiefile'] = str(cookies)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
        mp4 = path.with_suffix('.mp4')
        if mp4.exists():
            video = mp4
        else:
            video = path
            for p in Path(out_dir).glob(path.stem + '.*'):
                if p.suffix.lower() in {'.mp4', '.mkv', '.webm', '.mov'}:
                    video = p
                    break

        # Оставляем только небольшой текстовый файл субтитров.
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
