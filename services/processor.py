from pathlib import Path
import subprocess


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "")[-2000:]
        raise RuntimeError(f"ffmpeg exit {r.returncode}: {err}")


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


def to_vertical(src, dst, mirror=False, width=720, height=1280):
    """
    9:16 с размытым фоном вместо чёрных полос:
    фон = кадр, растянутый и blur; поверх — исходник с сохранением пропорций.
    """
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # bg: cover + blur; fg: contain; overlay center
    fc = (
        f"[0:v]fps=30,split=2[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma=25,eq=brightness=-0.05[blur];"
        f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[main];"
        f"[blur][main]overlay=(W-w)/2:(H-h)/2"
    )
    if mirror:
        fc += ",hflip"
    fc += ",setsar=1,format=yuv420p[vout]"

    run(
        [
            "ffmpeg",
            "-y",
            "-threads",
            "2",
            "-i",
            str(src),
            "-filter_complex",
            fc,
            "-map",
            "[vout]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-shortest",
            "-movflags",
            "+faststart",
            str(dst),
        ]
    )
    return dst


def insert_banner_center(src, banner, dst):
    """Баннер по центру ролика (замена среднего сегмента)."""
    src, banner, dst = Path(src), Path(banner), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    d_main = duration(src)
    d_ban = max(0.5, duration(banner))
    start = max(0.0, d_main / 2.0 - d_ban / 2.0)
    if d_main <= d_ban + 0.05:
        start = 0.0
    end_ban = min(d_main, start + d_ban)
    d_ban = max(0.1, end_ban - start)

    t0 = 0.0
    t1 = round(start, 3)
    t2 = round(end_ban, 3)
    t3 = round(d_main, 3)
    db = round(d_ban, 3)

    w, h = 720, 1280

    fc = (
        f"[0:v]fps=30,scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[base];"
        f"[1:v]fps=30,scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[ban];"
        f"[base]split=2[b0][b2];"
        f"[b0]trim=start={t0}:end={t1},setpts=PTS-STARTPTS[v0];"
        f"[ban]trim=start=0:end={db},setpts=PTS-STARTPTS[vmid];"
        f"[b2]trim=start={t2}:end={t3},setpts=PTS-STARTPTS[v2];"
        f"[v0][vmid][v2]concat=n=3:v=1:a=0[vout]"
    )

    has_main = _has_audio(src)
    has_ban = _has_audio(banner)

    if has_main and has_ban:
        fc += (
            f";[0:a]atrim=start={t0}:end={t1},asetpts=PTS-STARTPTS[a0];"
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"atrim=start=0:end={db},asetpts=PTS-STARTPTS[aban];"
            f"[0:a]atrim=start={t2}:end={t3},asetpts=PTS-STARTPTS[a2];"
            f"[a0][aban][a2]concat=n=3:v=0:a=1[aout]"
        )
        map_args = ["-map", "[vout]", "-map", "[aout]"]
    elif has_ban:
        fc += (
            f";[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"atrim=start=0:end={db},asetpts=PTS-STARTPTS[aout]"
        )
        map_args = ["-map", "[vout]", "-map", "[aout]"]
    elif has_main:
        fc += ";[0:a]asetpts=PTS-STARTPTS[aout]"
        map_args = ["-map", "[vout]", "-map", "[aout]"]
    else:
        map_args = ["-map", "[vout]"]

    run(
        [
            "ffmpeg",
            "-y",
            "-threads",
            "2",
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
            "ultrafast",
            "-crf",
            "28",
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
            "-threads",
            "2",
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
