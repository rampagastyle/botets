import asyncio
import gc
import time
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import WORK_DIR, MAX_FILE_SIZE
from services.whitelist import is_allowed
from services.storage import get_settings, save_settings
from services.downloader import download
from services.processor import render_part, split_video, cleanup_paths, cleanup_user_work, duration, quality_dims
from services.subtitles import write_ass_for_clip, write_vtt_from_cues
from services.gemini import analyze_video
from services.youtube import upload_short

router = Router()
MAX_SEND_BYTES = 45 * 1024 * 1024
PROCESS_SEMAPHORE = asyncio.Semaphore(1)


def _bar(percent: int, width: int = 10) -> str:
    filled = max(0, min(width, round(percent * width / 100)))
    return '█' * filled + '░' * (width - filled)


def _yt_description(meta: dict, language: str) -> str:
    hashtags = ' '.join(meta.get('hashtags') or [])
    body = (meta.get('description') or '').strip()
    if hashtags:
        body += '\n\n' + hashtags
    return body[:4900]


@router.message(lambda m: m.text and m.text.startswith(('http://', 'https://')))
async def video_link(message: Message):
    uid = message.from_user.id
    if not is_allowed(uid):
        return await message.answer('⛔️ Доступ запрещён.')

    user_dir = WORK_DIR / str(uid)
    raw = user_dir / 'raw'
    processed = user_dir / 'processed'
    raw.mkdir(parents=True, exist_ok=True)
    status = await message.answer('🔗 Ссылка принята\nПодготавливаю обработку…')
    loop = asyncio.get_running_loop()
    last_edit = {'t': 0.0}

    def progress_callback(percent, text):
        now = time.time()
        if now - last_edit['t'] < 2 and percent not in (0, 100):
            return
        last_edit['t'] = now
        async def _edit():
            try:
                body = text if percent is None else f'{text}\n[{_bar(percent)}] {percent}%'
                await status.edit_text(body)
            except Exception:
                pass
        asyncio.run_coroutine_threadsafe(_edit(), loop)

    try:
        s = get_settings(uid)
        quality = int(s.get('quality') or 480)
        width, height = quality_dims(quality)
        clip_sec = int(s.get('clip_seconds') or 15)
        if clip_sec not in (15, 30, 45, 60):
            clip_sec = 15
        mirror = bool(s.get('mirror'))
        banner_path = s.get('banner') or ''
        banner_on = bool(s.get('banner_enabled')) and bool(banner_path) and Path(banner_path).exists()
        send_all = bool(s.get('send_all'))
        watermark = (s.get('watermark') or '').strip()[:80]
        subtitle_mode = s.get('subtitles', 'source')
        subtitle_lang = s.get('language', 'ru')
        gemini_on = bool(s.get('gemini_analysis', True))
        youtube_on = bool(s.get('youtube_auto'))
        youtube_privacy = s.get('youtube_privacy', 'private')

        async with PROCESS_SEMAPHORE:
            await status.edit_text('⬇️ Скачивание…')
            src = await asyncio.to_thread(download, message.text.strip(), raw, quality, progress_callback, subtitle_lang)
            src = Path(src)
            if not src.exists():
                raise RuntimeError('Скачанный файл не найден.')
            if src.stat().st_size > MAX_FILE_SIZE:
                cleanup_paths(src)
                return await status.edit_text('⚠️ Файл слишком большой.')

            source_sub = raw / 'source_subtitles.vtt'
            if subtitle_mode != 'source':
                cleanup_paths(source_sub)

            await status.edit_text(f'✂️ Нарезаю по {clip_sec} сек…')
            raw_parts_dir = processed / 'raw_parts'
            raw_parts = await asyncio.to_thread(split_video, src, raw_parts_dir, clip_sec)
            cleanup_paths(src)
            if not raw_parts:
                return await status.edit_text('⚠️ Не удалось нарезать.')

            final_parts = []
            metadata = []
            out_dir = processed / 'final'
            subs_dir = processed / 'subs'
            out_dir.mkdir(parents=True, exist_ok=True)
            subs_dir.mkdir(parents=True, exist_ok=True)

            total = len(raw_parts)
            for i, part in enumerate(raw_parts):
                part = Path(part)
                part_duration = await asyncio.to_thread(duration, part)
                clip_start = i * clip_sec
                clip_end = clip_start + part_duration
                ass_path = subs_dir / f'part_{i:03d}.ass'
                subtitle_path = None

                # One Gemini request per clip. If AI subtitles are enabled, the same request
                # returns transcript cues + metadata, avoiding a second model call.
                meta = {'title': f'Short {i + 1}', 'description': '', 'hashtags': [], 'tags': [], 'subtitles': []}
                if gemini_on or subtitle_mode == 'ai' or youtube_on:
                    await status.edit_text(f'🤖 Gemini · {i + 1}/{total}…')
                    meta = await asyncio.to_thread(
                        analyze_video,
                        part,
                        subtitle_lang,
                        subtitle_mode == 'ai',
                        i,
                        total,
                    )

                if subtitle_mode == 'source' and source_sub.exists():
                    ok = await asyncio.to_thread(write_ass_for_clip, source_sub, clip_start, clip_end, ass_path)
                    subtitle_path = str(ass_path) if ok else None
                elif subtitle_mode == 'ai' and meta.get('subtitles'):
                    ai_vtt = subs_dir / f'ai_{i:03d}.vtt'
                    ok = await asyncio.to_thread(write_vtt_from_cues, meta.get('subtitles'), ai_vtt)
                    if ok:
                        ok2 = await asyncio.to_thread(write_ass_for_clip, ai_vtt, 0, part_duration, ass_path)
                        subtitle_path = str(ass_path) if ok2 else None
                    cleanup_paths(ai_vtt)

                try:
                    await status.edit_text(f'🎨 {i + 1}/{total} · {quality}p')
                except Exception:
                    pass

                final = out_dir / f'part_{i:03d}.mp4'
                await asyncio.to_thread(
                    render_part,
                    part,
                    final,
                    width,
                    height,
                    mirror,
                    banner_path if banner_on else None,
                    watermark,
                    subtitle_path,
                    30.0,
                )
                cleanup_paths(part, ass_path)
                final_parts.append(final)
                metadata.append(meta)
                gc.collect()

                # Upload one clip at a time. The file is never duplicated in RAM.
                if youtube_on:
                    try:
                        await status.edit_text(f'▶️ YouTube · {i + 1}/{total}…')
                        title = meta.get('title') or f'Short {i + 1}'
                        description = _yt_description(meta, subtitle_lang)
                        video_id = await asyncio.to_thread(
                            upload_short,
                            uid,
                            final,
                            title,
                            description,
                            meta.get('tags') or [],
                            youtube_privacy,
                        )
                        meta['youtube_id'] = video_id
                    except Exception as exc:
                        meta['youtube_error'] = f'{type(exc).__name__}: {exc}'

            cleanup_paths(source_sub)
            save_settings(
                uid,
                last_parts=[str(p) for p in final_parts],
                last_sent_index=0,
                last_metadata=metadata,
            )
            await status.edit_text(f'✅ Готово · {len(final_parts)} частей · {quality}p')

            if send_all:
                for i, part in enumerate(final_parts, start=1):
                    if not part.exists() or part.stat().st_size > MAX_SEND_BYTES:
                        continue
                    meta = metadata[i - 1] if i - 1 < len(metadata) else {}
                    caption = f'Часть {i}/{len(final_parts)}'
                    if meta.get('title'):
                        caption += f'\n{meta["title"]}'
                    await message.answer_video(FSInputFile(part), caption=caption[:1024])
                save_settings(uid, last_sent_index=len(final_parts))
            else:
                await _send_part(message, final_parts, 0, metadata)

            cleanup_user_work(user_dir, keep_final=True, keep_banner=True)
            gc.collect()

    except Exception as e:
        try:
            await status.edit_text(f'❌ {type(e).__name__}: {e}')
        except Exception:
            await message.answer(f'❌ {type(e).__name__}: {e}')
        cleanup_user_work(user_dir, keep_final=False, keep_banner=True)
        gc.collect()


def _next_kb(index: int, total: int):
    if index + 1 >= total:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'▶️ Следующая часть ({index + 2}/{total})', callback_data=f'nextpart:{index + 1}')]])


async def _send_part(message: Message, parts: list, index: int, metadata=None):
    total = len(parts)
    if index < 0 or index >= total:
        return await message.answer('Больше частей нет.')
    part = Path(parts[index])
    if not part.exists():
        return await message.answer('Файл части не найден. Нарежьте снова.')
    if part.stat().st_size > MAX_SEND_BYTES:
        await message.answer(f'Часть {index + 1} слишком большая, пропуск.')
        return
    caption = f'Часть {index + 1}/{total}'
    if metadata and index < len(metadata) and metadata[index].get('title'):
        caption += f'\n{metadata[index]["title"]}'
    await message.answer_video(FSInputFile(part), caption=caption[:1024], reply_markup=_next_kb(index, total))
    save_settings(message.from_user.id, last_sent_index=index + 1)


@router.callback_query(F.data.startswith('nextpart:'))
async def next_part_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id):
        return await call.answer('Нет доступа', show_alert=True)
    try:
        index = int(call.data.split(':')[1])
    except (IndexError, ValueError):
        return await call.answer('Ошибка', show_alert=True)
    s = get_settings(call.from_user.id)
    paths = [Path(p) for p in (s.get('last_parts') or [])]
    if not paths:
        return await call.message.answer('Сначала отправьте ссылку на видео.')
    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    class _Msg:
        def __init__(self, origin):
            self.from_user = call.from_user
            self.chat = origin.chat
            self.answer = origin.answer
            self.answer_video = origin.answer_video

    await _send_part(_Msg(call.message), paths, index, s.get('last_metadata') or [])
