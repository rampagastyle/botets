from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _srt_to_vtt(srt: str) -> str:
    lines = ['WEBVTT', '']
    for line in srt.splitlines():
        if '-->' in line:
            lines.append(line.replace(',', '.'))
        elif line.strip().isdigit():
            continue
        else:
            lines.append(line)
    return '\n'.join(lines) + '\n'


def transcribe_file_to_vtt(video_path: str | Path, out_vtt: str | Path, language='ru') -> bool:
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    if not api_key:
        return False

    audio = Path(out_vtt).with_suffix('.m4a')
    audio.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([
            'ffmpeg', '-y', '-threads', '1', '-i', str(video_path), '-vn',
            '-ac', '1', '-ar', '16000', '-c:a', 'aac', '-b:a', '32k', str(audio)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        model = os.getenv('OPENAI_TRANSCRIBE_MODEL', 'gpt-4o-mini-transcribe')
        with audio.open('rb') as f:
            result = client.audio.transcriptions.create(
                model=model,
                file=f,
                language='ru' if language == 'ru' else 'en',
                response_format='srt',
            )
        text = result if isinstance(result, str) else getattr(result, 'text', '')
        if not text:
            return False
        Path(out_vtt).write_text(_srt_to_vtt(text), encoding='utf-8')
        return True
    except Exception:
        return False
    finally:
        try: audio.unlink(missing_ok=True)
        except OSError: pass
