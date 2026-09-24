from pathlib import Path
import shutil
import subprocess

QUALITY_DIMS = {480: (480, 854), 720: (720, 1280), 1080: (1080, 1920)}
DEFAULT_QUALITY = 480
MAX_QUALITY = 1080
FFMPEG_THREADS = '1'
FILTER_THREADS = '1'
VIDEO_PRESET = 'ultrafast'
VIDEO_CRF = '30'
FONT_FILE = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def quality_dims(quality):
    try:
        quality = int(quality)
    except (TypeError, ValueError):
        quality = DEFAULT_QUALITY
    quality = min(MAX_QUALITY, max(480, quality))
    return QUALITY_DIMS[quality]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or '')[-2200:]
        raise RuntimeError(f'ffmpeg exit {r.returncode}: {err}')


def duration(path):
    out = subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)], text=True).strip()
    return float(out)


def _filter_path(path):
    return str(Path(path)).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")


def _text_escape(text):
    return (str(text).replace('\\', r'\\').replace(':', r'\\:')
            .replace("'", r"\\'").replace('%', r'\\%').replace('\n', ' '))


def _vertical_blur_filter(width, height, mirror=False):
    bg_w, bg_h = max(2, width // 4), max(2, height // 4)
    mirror_filter = ',hflip' if mirror else ''
    return (
        f'split=2[bg0][fg0];'
        f'[bg0]scale={bg_w}:{bg_h}:force_original_aspect_ratio=increase,'
        f'crop={bg_w}:{bg_h},boxblur=2:1,scale={width}:{height}:flags=fast_bilinear[bg];'
        f'[fg0]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];'
        f'[bg][fg]overlay=(W-w)/2:(H-h)/2{mirror_filter},setsar=1,format=yuv420p'
    )


def _decorate_filter_chain(label, watermark='', subtitle_path=None):
    filters = []
    if watermark:
        # Keep the watermark inside the sharp foreground video, not on the blur area.
        # Alpha is intentionally low so it does not dominate the clip.
        filters.append(
            f"drawtext=fontfile='{FONT_FILE}':text='{_text_escape(watermark)}':"
            f'fontcolor=white@0.55:fontsize=38:bordercolor=black@0.35:borderw=2:'
            f'x=(w-text_w)/2:'
            f'y=(h-min(h,w*ih/iw))/2+min(h,w*ih/iw)-text_h-70:alpha=0.55'
        )
    if subtitle_path and Path(subtitle_path).exists():
        filters.append(f"subtitles='{_filter_path(subtitle_path)}':fontsdir='/usr/share/fonts/truetype/dejavu'")
    if not filters:
        filters.append('null')
    return f"[{label}]" + ','.join(filters) + '[vout]'


def _encode_args(dst):
    return ['-c:v', 'libx264', '-preset', VIDEO_PRESET, '-crf', VIDEO_CRF,
            '-threads', FFMPEG_THREADS, '-filter_threads', FILTER_THREADS,
            '-c:a', 'aac', '-ar', '44100', '-ac', '2', '-movflags', '+faststart', str(dst)]


def to_vertical(src, dst, mirror=False, width=480, height=854, watermark='', subtitle_path=None):
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    base = _vertical_blur_filter(width, height, mirror)
    decorated = _decorate_filter_chain('base', watermark, subtitle_path)
    vf = f'[0:v]fps=30,{base}[base];{decorated}'
    run(['ffmpeg', '-y', '-threads', FFMPEG_THREADS, '-filter_threads', FILTER_THREADS,
         '-i', str(src), '-filter_complex', vf, '-map', '[vout]', '-map', '0:a?',
         *_encode_args(dst)])
    return dst


def insert_banner_at(src, banner, dst, at_second=30.0, width=480, height=854,
                     mirror=False, watermark='', subtitle_path=None):
    src, banner, dst = Path(src), Path(banner), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    d_main = duration(src)
    d_ban = max(0.5, min(duration(banner), d_main * 0.9))
    if d_main >= at_second + d_ban:
        start = float(at_second)
    elif d_main >= d_ban + 0.5:
        start = max(0.0, d_main / 2.0 - d_ban / 2.0)
    else:
        start = 0.0
    end = min(d_main, start + d_ban)
    d_ban = max(0.1, end - start)
    t1, t2, db = round(start, 3), round(end, 3), round(d_ban, 3)

    base_vf = _vertical_blur_filter(width, height, mirror)
    banner_vf = _vertical_blur_filter(width, height, False)
    fc = (
        f'[0:v]fps=30,{base_vf}[base];'
        f'[1:v]fps=30,{banner_vf},setpts=PTS-STARTPTS+{t1}/TB[ban];'
        f'[base][ban]overlay=0:0:enable=between(t\\,{t1}\\,{t2})[merged];'
        + _decorate_filter_chain('merged', watermark, subtitle_path)
    )

    has_main, has_ban = _has_audio(src), _has_audio(banner)
    if has_main and has_ban:
        fc += (f';[0:a]atrim=0:{t1},asetpts=PTS-STARTPTS[a0];'
               f'[1:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:{db},asetpts=PTS-STARTPTS[aban];'
               f'[0:a]atrim={t2},asetpts=PTS-STARTPTS[a2];'
               f'[a0][aban][a2]concat=n=3:v=0:a=1[aout]')
        maps = ['-map', '[vout]', '-map', '[aout]']
    elif has_main:
        fc += ';[0:a]asetpts=PTS-STARTPTS[aout]'
        maps = ['-map', '[vout]', '-map', '[aout]']
    else:
        maps = ['-map', '[vout]']

    run(['ffmpeg', '-y', '-threads', FFMPEG_THREADS, '-filter_threads', FILTER_THREADS,
         '-i', str(src), '-i', str(banner), '-filter_complex', fc, *maps, *_encode_args(dst)])
    return dst


def insert_banner_center(src, banner, dst):
    return insert_banner_at(src, banner, dst, at_second=30.0)


def render_part(src, dst, width=480, height=854, mirror=False, banner=None,
                watermark='', subtitle_path=None, banner_at=30.0):
    if banner and Path(banner).exists():
        return insert_banner_at(src, banner, dst, at_second=banner_at, width=width,
                                height=height, mirror=mirror, watermark=watermark,
                                subtitle_path=subtitle_path)
    return to_vertical(src, dst, mirror=mirror, width=width, height=height,
                       watermark=watermark, subtitle_path=subtitle_path)


def _has_audio(path):
    try:
        out = subprocess.check_output(
            ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries',
             'stream=codec_type', '-of', 'csv=p=0', str(path)], text=True).strip()
        return bool(out)
    except Exception:
        return False


def split_video(src, out_dir, chunk_seconds=15):
    out_dir = Path(out_dir)
    if out_dir.exists():
        for p in out_dir.glob('part_*.mp4'):
            cleanup_paths(p)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / 'part_%03d.mp4'
    run(['ffmpeg', '-y', '-threads', FFMPEG_THREADS, '-i', str(src), '-c', 'copy', '-map', '0',
         '-f', 'segment', '-segment_time', str(int(chunk_seconds)), '-reset_timestamps', '1', str(pattern)])
    return sorted(out_dir.glob('part_*.mp4'))


def cleanup_paths(*paths):
    for p in paths:
        p = Path(p)
        try:
            if p.is_file():
                p.unlink(missing_ok=True)
            elif p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass


def cleanup_user_work(user_dir: Path, keep_final=True, keep_banner=True):
    user_dir = Path(user_dir)
    for name in ('raw', 'raw_parts'):
        cleanup_paths(user_dir / name)
    processed = user_dir / 'processed'
    if processed.exists():
        if not keep_final:
            cleanup_paths(processed)
        else:
            for p in processed.glob('v_*.mp4'):
                cleanup_paths(p)
            for p in processed.glob('raw_parts/part_*.mp4'):
                cleanup_paths(p)
            for p in processed.glob('subs/*.ass'):
                cleanup_paths(p)
    if not keep_banner:
        cleanup_paths(user_dir / 'banner')
