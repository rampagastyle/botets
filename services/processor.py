from pathlib import Path
import shutil
import subprocess

QUALITY_DIMS = {480: (480, 854), 720: (720, 1280), 1080: (1080, 1920)}
DEFAULT_QUALITY = 720
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


def _banner_max_box(width: int, height: int) -> tuple[int, int]:
    """
    Баннер только в зоне «острого» кадра (середина 9:16), не на blur.
    Для типичного 16:9 контента полоса ≈ width × (9/16).
    """
    content_h = int(width * 9 / 16)
    content_h = max(200, min(content_h, int(height * 0.55)))
    max_w = int(width * 0.88)
    max_h = int(content_h * 0.92)
    if max_w % 2:
        max_w -= 1
    if max_h % 2:
        max_h -= 1
    return max(2, max_w), max(2, max_h)


def insert_banner_at(
    src,
    banner,
    dst,
    at_second=None,
    width=720,
    height=1280,
    mirror=False,
):
    """
    Баннер ровно по центру клипа (для кусков ≤ 60 сек).
    Основное видео на паузе на время баннера (freeze).
    Баннер масштабируется в центральную секцию, без перекрытия blur-полей на весь экран.
    """
    src, banner, dst = Path(src), Path(banner), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    d_main = duration(src)
    d_ban = max(0.5, min(duration(banner), 12.0, d_main * 0.5))

    # Центр ролика: баннер «сидит» посередине (пауза в середине)
    t1 = max(0.0, d_main / 2.0)
    if at_second is not None:
        # явный старт только если кусок длинный; иначе всё равно центр
        if d_main >= 60 and float(at_second) + d_ban <= d_main:
            t1 = float(at_second)
    t1 = round(min(t1, max(0.0, d_main - 0.05)), 3)
    db = round(d_ban, 3)

    bg = _blur_bg(width, height)
    fg = _fg(width, height, mirror)
    bw, bh = _banner_max_box(width, height)

    # 1) вертикальный base
    # 2) pre | freeze+banner | post  → concat (пауза = +db к длительности)
    fc = (
        f"[0:v]fps=30,split=2[b0][f0];"
        f"[b0]{bg}[bg];[f0]{fg}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p,setsar=1[base];"
        f"[base]split=3[s0][s1][s2];"
        f"[s0]trim=0:{t1},setpts=PTS-STARTPTS[pre];"
        f"[s1]trim={t1}:{t1}+0.04,setpts=PTS-STARTPTS,"
        f"tpad=stop_mode=clone:stop_duration={db},trim=0:{db},setpts=PTS-STARTPTS[frz];"
        f"[1:v]fps=30,scale={bw}:{bh}:force_original_aspect_ratio=decrease:flags=fast_bilinear,"
        f"setsar=1,format=yuv420p,setpts=PTS-STARTPTS[ban];"
        f"[frz][ban]overlay=(W-w)/2:(H-h)/2:shortest=1[mid];"
        f"[s2]trim={t1},setpts=PTS-STARTPTS[post];"
        f"[pre][mid][post]concat=n=3:v=1:a=0[vout]"
    )

    has_main = _has_audio(src)
    has_ban = _has_audio(banner)
    maps = ["-map", "[vout]"]

    if has_main:
        # аудио: до паузы → (баннер или тишина) → после паузы
        if has_ban:
            fc += (
                f";[0:a]atrim=0:{t1},asetpts=PTS-STARTPTS[a0];"
                f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                f"atrim=0:{db},asetpts=PTS-STARTPTS,apad=whole_dur={db}[aban];"
                f"[0:a]atrim={t1},asetpts=PTS-STARTPTS[a2];"
                f"[a0][aban][a2]concat=n=3:v=0:a=1[aout]"
            )
        else:
            fc += (
                f";[0:a]atrim=0:{t1},asetpts=PTS-STARTPTS[a0];"
                f"anullsrc=r=44100:cl=stereo,atrim=0:{db},asetpts=PTS-STARTPTS[asil];"
                f"[0:a]atrim={t1},asetpts=PTS-STARTPTS[a2];"
                f"[a0][asil][a2]concat=n=3:v=0:a=1[aout]"
            )
        maps = ["-map", "[vout]", "-map", "[aout]"]

    run([
        "ffmpeg", "-y",
        "-threads", FFMPEG_THREADS, "-filter_threads", FILTER_THREADS,
        "-i", str(src),
        "-i", str(banner),
        "-filter_complex", fc,
        *maps,
        *_encode_args(dst),
    ])
    return dst


def render_part(src, dst, width=720, height=1280, mirror=False, banner=None, banner_at=None):
    if banner and Path(banner).exists():
        return insert_banner_at(
            src, banner, dst,
            at_second=None,  # всегда центр куска ≤60с
            width=width, height=height, mirror=mirror,
        )
    return to_vertical(src, dst, mirror=mirror, width=width, height=height)


def _has_audio(path):
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                str(path),
            ],
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
