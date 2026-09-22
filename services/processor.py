from pathlib import Path
import subprocess
import json

def run(cmd):
    subprocess.run(cmd, check=True)

def duration(path):
    out = subprocess.check_output([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(path)
    ], text=True).strip()
    return float(out)

def process(src, dst, watermark=None, position="bottom-right", mirror=False):
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Масштабируем с сохранением пропорций и вписываем в вертикальный 1080x1920.
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    if mirror:
        vf += ",hflip"

    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if watermark:
        cmd += ["-i", str(watermark)]
        positions = {
            "top-left": "20:20", "top-right": "W-w-20:20",
            "bottom-left": "20:H-h-20", "bottom-right": "W-w-20:H-h-20",
            "center": "(W-w)/2:(H-h)/2"
        }
        cmd += ["-filter_complex", f"[0:v]{vf}[v0];[1:v]format=rgba[wm];[v0][wm]overlay={positions.get(position, positions['bottom-right'])}[v]"]
        cmd += ["-map","[v]","-map","0:a?"]
    else:
        cmd += ["-vf", vf, "-map", "0:v", "-map", "0:a?"]

    cmd += ["-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-movflags","+faststart",str(dst)]
    run(cmd)
    return dst

def split_video(src, out_dir, chunk_seconds=60):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "part_%03d.mp4"
    run(["ffmpeg","-y","-i",str(src),"-c","copy","-map","0","-f","segment",
         "-segment_time",str(chunk_seconds),"-reset_timestamps","1",str(pattern)])
    return sorted(out_dir.glob("part_*.mp4"))
