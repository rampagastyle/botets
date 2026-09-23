from pathlib import Path
import subprocess


def run(cmd):
    subprocess.run(cmd, check=True)


def duration(path):
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out)


def to_vertical(src, dst, mirror=False):
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )
    if mirror:
        vf += ",hflip"
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vf",
            vf,
            "-map",
            "0:v",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(dst),
        ]
    )
    return dst


def insert_banner_center(src, banner, dst):
    """
    Баннер по центру ролика (куски <= 60 с, правила CSDOG).
    На время баннера основной кадр заморожен, поверх — баннер с озвучкой.
    """
    src, banner, dst = Path(src), Path(banner), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    d_main = duration(src)
    d_ban = max(0.5, duration(banner))
    start = max(0.0, d_main / 2.0 - d_ban / 2.0)
    if d_main <= d_ban + 0.1:
        start = 0.0

    # Разбиваем на 3 сегмента: до баннера | баннер | после
    # Баннер масштабируем под 9:16 и кладём по центру.
    fc = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[base];"
        f"[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[ban];"
        f"[base]split=3[b0][b1][b2];"
        f"[b0]trim=0:{start:.3f},setpts=PTS-STARTPTS[v0];"
        f"[b1]trim={start:.3f}:{start:.3f}+0.04,setpts=PTS-STARTPTS,"
        f"loop=loop=-1:size=1:start=0,trim=duration={d_ban:.3f},setpts=PTS-STARTPTS[fr];"
        f"[fr][ban]overlay=(W-w)/2:(H-h)/2:shortest=1[vmid];"
        f"[b2]trim={start + d_ban:.3f},setpts=PTS-STARTPTS[v2];"
        f"[v0][vmid][v2]concat=n=3:v=1:a=0[vout]"
    )

    # Аудио: кусок до + аудио баннера + кусок после (если есть дорожки)
    has_main_audio = _has_audio(src)
    has_ban_audio = _has_audio(banner)

    if has_main_audio and has_ban_audio:
        fc += (
            f";[0:a]atrim=0:{start:.3f},asetpts=PTS-STARTPTS[a0];"
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"atrim=0:{d_ban:.3f},asetpts=PTS-STARTPTS[aban];"
            f"[0:a]atrim={start + d_ban:.3f},asetpts=PTS-STARTPTS[a2];"
            f"[a0][aban][a2]concat=n=3:v=0:a=1[aout]"
        )
        map_args = ["-map", "[vout]", "-map", "[aout]"]
    elif has_ban_audio:
        fc += (
            f";[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"atrim=0:{d_ban:.3f},asetpts=PTS-STARTPTS[aout]"
        )
        map_args = ["-map", "[vout]", "-map", "[aout]"]
    elif has_main_audio:
        fc += f";[0:a]asetpts=PTS-STARTPTS[aout]"
        map_args = ["-map", "[vout]", "-map", "[aout]"]
    else:
        map_args = ["-map", "[vout]"]

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-i",
        str(banner),
        "-filter_complex",
        fc,
        *map_args,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(dst),
    ]
    run(cmd)
    return dst


def _has_audio(path) -> bool:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
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
            try:
                p.unlink()
            except OSError:
                pass
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "part_%03d.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-c",
            "copy",
            "-map",
            "0",
            "-f",
            "segment",
            "-segment_time",
            str(int(chunk_seconds)),
            "-reset_timestamps",
            "1",
            str(pattern),
        ]
    )
    return sorted(out_dir.glob("part_*.mp4"))
