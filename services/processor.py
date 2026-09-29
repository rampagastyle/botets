from pathlib import Path
import shutil
import subprocess

QUALITY_DIMS = {480: (480, 854), 720: (720, 1280), 1080: (1080, 1920)}
DEFAULT_QUALITY = 720
# Hobby 8GB: 2 threads is a good balance for concurrent users
FFMPEG_THREADS = "2"
FILTER_THREADS = "2"
VIDEO_PRESET = "veryfast"
VIDEO_CRF = "22"


def quality_dims(quality):
    try:
        quality = int(quality)
    except (TypeError, ValueError):
        quality = DEFAULT_QUALITY
    quality = min((480, 720, 1080), key=lambda x: abs(x - quality))
    return QUALITY_DIMS[quality]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "")[-2000:]
        raise RuntimeError(f"ffmpeg exit {r.returncode}: {err}")


def duration(path):
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out)


def _blur_bg(width: int, height: int) -> str:
    bw = max(160, width // 8)
    if bw % 2:
        bw += 1
    bh = max(284, height // 8)
    if bh % 2:
        bh += 1
    return (
        f"scale={bw}:{bh}:force_original_aspect_ratio=increase:flags=fast_bilinear,"
        f"crop={bw}:{bh},boxblur=6:1,"
        f"scale={width}:{height}:flags=fast_bilinear,setsar=1,format=yuv420p"
    )


def _fg(width: int, height: int, mirror: bool = False) -> str:
    m = ",hflip" if mirror else ""
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=fast_bilinear,"
        f"setsar=1,format=yuv420p{m}"
    )


def _encode_args(dst):
    return [
        "-c:v", "libx264", "-preset", VIDEO_PRESET, "-crf", VIDEO_CRF,
        "-threads", FFMPEG_THREADS, "-filter_threads", FILTER_THREADS,
        "-max_muxing_queue_size", "1024",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart", str(dst),
    ]


def to_vertical(src, dst, mirror=False, width=720, height=1280):
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    bg, fg = _blur_bg(width, height), _fg(width, height, mirror)
    fc = (
        f"[0:v]fps=30,split=2[b0][f0];"
        f"[b0]{bg}[bg];[f0]{fg}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[vout]"
    )
    run([
        "ffmpeg", "-y", "-threads", FFMPEG_THREADS, "-filter_threads", FILTER_THREADS,
        "-i", str(src), "-filter_complex", fc,
        "-map", "[vout]", "-map", "0:a?",
        *_encode_args(dst),
    ])
    return dst


def insert_banner_at(src, banner, dst, at_second=30.0, width=720, height=1280, mirror=False):
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

    bg, fg = _blur_bg(width, height), _fg(width, height, mirror)
    ban = (
        f"fps=30,scale={width}:{height}:force_original_aspect_ratio=increase:flags=fast_bilinear,"
        f"crop={width}:{height},setsar=1,format=yuv420p,setpts=PTS-STARTPTS+{t1}/TB"
    )
    fc = (
        f"[0:v]fps=30,split=2[b0][f0];"
        f"[b0]{bg}[bg];[f0]{fg}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
        f"[1:v]{ban}[ban];"
        f"[base][ban]overlay=0:0:enable='between(t,{t1},{t2})'[vout]"
    )
    has_main, has_ban = _has_audio(src), _has_audio(banner)
    if has_main and has_ban:
        fc += (
            f";[0:a]atrim=0:{t1},asetpts=PTS-STARTPTS[a0];"
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"atrim=0:{db},asetpts=PTS-STARTPTS[aban];"
            f"[0:a]atrim={t2},asetpts=PTS-STARTPTS[a2];"
            f"[a0][aban][a2]concat=n=3:v=0:a=1[aout]"
        )
        maps = ["-map", "[vout]", "-map", "[aout]"]
    elif has_main:
        fc += ";[0:a]asetpts=PTS-STARTPTS[aout]"
        maps = ["-map", "[vout]", "-map", "[aout]"]
    else:
        maps = ["-map", "[vout]"]

    run([
        "ffmpeg", "-y", "-threads", FFMPEG_THREADS, "-filter_threads", FILTER_THREADS,
        "-i", str(src), "-i", str(banner),
        "-filter_complex", fc, *maps, *_encode_args(dst),
    ])
    return dst


def render_part(src, dst, width=720, height=1280, mirror=False, banner=None, banner_at=30.0):
    if banner and Path(banner).exists():
        return insert_banner_at(src, banner, dst, at_second=banner_at, width=width, height=height, mirror=mirror)
    return to_vertical(src, dst, mirror=mirror, width=width, height=height)


def _has_audio(path):
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
            text=True,
        ).strip()
        return bool(out)
    except Exception:
        return False


def split_video(src, out_dir, chunk_seconds=30):
    out_dir = Path(out_dir)
    if out_dir.exists():
        for p in out_dir.glob("part_*.mp4"):
            cleanup_paths(p)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "part_%03d.mp4"
    run([
        "ffmpeg", "-y", "-threads", FFMPEG_THREADS, "-i", str(src),
        "-c", "copy", "-map", "0", "-f", "segment",
        "-segment_time", str(int(chunk_seconds)),
        "-reset_timestamps", "1", str(pattern),
    ])
    return sorted(out_dir.glob("part_*.mp4"))


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


def cleanup_user_work(user_dir: Path, keep_final=True):
    user_dir = Path(user_dir)
    for name in ("raw", "raw_parts"):
        cleanup_paths(user_dir / name)
    processed = user_dir / "processed"
    if processed.exists():
        if not keep_final:
            cleanup_paths(processed)
        else:
            for p in processed.glob("raw_parts/part_*.mp4"):
                cleanup_paths(p)
