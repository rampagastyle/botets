from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Iterable


def _stamp(value: str) -> float:
    value = value.strip().replace(',', '.')
    parts = value.split(':')
    if len(parts) == 2:
        minutes, sec = parts
        return int(minutes) * 60 + float(sec)
    hours, minutes, sec = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(sec)


def _ass_time(seconds: float) -> str:
    seconds = max(0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = text.replace('{', '(').replace('}', ')')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def read_vtt(path: str | Path) -> list[tuple[float, float, str]]:
    path = Path(path)
    if not path.exists():
        return []
    lines = path.read_text(encoding='utf-8-sig', errors='ignore').splitlines()
    cues = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if '-->' not in line:
            i += 1
            continue
        left, right = [x.strip() for x in line.split('-->', 1)]
        right = right.split(' ', 1)[0]
        try:
            start, end = _stamp(left), _stamp(right)
        except Exception:
            i += 1
            continue
        i += 1
        text_lines = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].strip())
            i += 1
        text = _clean(' '.join(text_lines))
        if text and end > start:
            cues.append((start, end, text))
        i += 1
    return cues


def write_ass_for_clip(source_vtt: str | Path, clip_start: float, clip_end: float, out_ass: str | Path) -> bool:
    cues = read_vtt(source_vtt)
    selected = []
    for start, end, text in cues:
        if end <= clip_start or start >= clip_end:
            continue
        start2 = max(0.0, start - clip_start)
        end2 = min(clip_end - clip_start, end - clip_start)
        if end2 > start2:
            selected.append((start2, end2, text))

    out = Path(out_ass)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not selected:
        return False

    lines = [
        '[Script Info]',
        'ScriptType: v4.00+',
        'PlayResX: 1080',
        'PlayResY: 1920',
        'WrapStyle: 2',
        'ScaledBorderAndShadow: yes',
        '',
        '[V4+ Styles]',
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
        'Style: Default,DejaVu Sans,58,&H00FFFFFF,&H00FFFFFF,&H00101010,&H99000000,-1,0,0,0,100,100,0,0,1,5,2,2,90,90,150,1',
        '',
        '[Events]',
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
    ]
    for start, end, text in selected:
        text = text.replace('\n', ' ').strip()
        lines.append(f'Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}')
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return True
