from pathlib import Path
import subprocess


def run(cmd):
    # capture stderr to help debug filter errors
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
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"fps=30,"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )
    if mirror:
        vf += ",hflip"
    run(
        [
            "ffmpeg",
            "-y",
            "-threads",
            "2",
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


def insert_banner_center(src, banner, dst):
    """
    Баннер по центру ролика.
    Простая схема: до | баннер (на весь кадр) | после.
    Числа для trim считаются в Python (ffmpeg не считает 12.8+0.04).
    """
    src, banner, dst = Path(src), Path(banner), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    d_main = duration(src)
    d_ban = max(0.5, duration(banner))
    start = max(0.0, d_main / 2.0 - d_ban / 2.0)
    if d_main <= d_ban + 0.05:
        start = 0.0
    end_ban = start + d_ban
    if end_ban > d_main:
        end_ban = d_main
        d_ban = max(0.1, end_ban - start)

    # precompute all times as plain floats for filter string
    t0 = 0.0
    t1 = round(start, 3)
    t2 = round(end_ban, 3)
    t3 = round(d_main, 3)
    db = round(d_ban, 3)

    w, h = 720, 1280

    # Video: part before + scaled banner full frame + part after
    # Use overlay of banner on frozen frame OR just replace segment with banner
    # Simpler reliable approach: concat [trim before][banner scaled][trim after]
    fc = (
        f"[0:v]fps=30,scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,setsar=1[base];"
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
        fc += f";[0:a]asetpts=PTS-STARTPTS[aout]"
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
