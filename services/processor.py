from pathlib import Path
import subprocess
import shutil

# Низкое разрешение специально под маленький RAM (Railway free ~512MB)
W, H = 480, 854


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "")[-1200:]
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


def to_vertical(src, dst, mirror=False, width=W, height=H):
    """Лёгкая 9:16: 480x854, 30fps, 1 поток, чёрные поля."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"fps=30,"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p"
    )
    if mirror:
        vf = (
            f"fps=30,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,hflip,setsar=1,format=yuv420p"
        )
    run([
        "ffmpeg", "-y",
        "-threads", "1",
        "-filter_threads", "1",
        "-i", str(src),
        "-vf", vf,
        "-map", "0:v", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart",
        str(dst),
    ])
    return dst


def insert_banner_center(src, banner, dst):
    """
    Баннер поверх середины одним проходом (overlay), без тройного concat —
    меньше пиковая память.
    """
    src, banner, dst = Path(src), Path(banner), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    d_main = duration(src)
    d_ban = max(0.5, min(duration(banner), d_main))
    start = max(0.0, d_main / 2.0 - d_ban / 2.0)
    end = min(d_main, start + d_ban)
    t1, t2, db = round(start, 3), round(end, 3), round(d_ban, 3)

    # video: scale both, overlay banner in time window
    # audio: main with banner audio mixed in window is complex — replace mid with banner audio via asplit
    fc = (
        f"[0:v]fps=30,scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[base];"
        f"[1:v]fps=30,scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,setpts=PTS-STARTPTS+{t1}/TB[ban];"
        f"[base][ban]overlay=0:0:enable='between(t,{t1},{t2})'[vout]"
    )

    has_main = _has_audio(src)
    has_ban = _has_audio(banner)

    if has_main and has_ban:
        # before + banner audio + after
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
        "ffmpeg", "-y",
        "-threads", "1",
        "-filter_threads", "1",
        "-i", str(src),
        "-i", str(banner),
        "-filter_complex", fc,
        *maps,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart",
        str(dst),
    ])
    return dst


def _has_audio(path) -> bool:
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


def split_video(src, out_dir, chunk_seconds=15):
    out_dir = Path(out_dir)
    if out_dir.exists():
        for p in out_dir.glob("part_*.mp4"):
            try:
                p.unlink()
            except OSError:
                pass
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "part_%03d.mp4"
    run([
        "ffmpeg", "-y", "-threads", "1",
        "-i", str(src),
        "-c", "copy", "-map", "0",
        "-f", "segment",
        "-segment_time", str(int(chunk_seconds)),
        "-reset_timestamps", "1",
        str(pattern),
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


def cleanup_user_work(user_dir: Path, keep_final: bool = True, keep_banner: bool = True):
    user_dir = Path(user_dir)
    for name in ("raw", "raw_parts"):
        cleanup_paths(user_dir / name)
    processed = user_dir / "processed"
    if processed.exists():
        for p in processed.glob("v_*.mp4"):
            cleanup_paths(p)
        if not keep_final:
            cleanup_paths(processed / "final")
            for p in processed.glob("**/*"):
                if p.is_file():
                    cleanup_paths(p)
    if not keep_banner:
        cleanup_paths(user_dir / "banner")
