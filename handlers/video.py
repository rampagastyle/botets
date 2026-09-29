import asyncio
import gc
import time
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import WORK_DIR, MAX_FILE_SIZE, MAX_CONCURRENT_JOBS
from services.whitelist import is_allowed
from services.storage import get_settings, save_settings
from services.downloader import download
from services.processor import render_part, split_video, cleanup_paths, cleanup_user_work, quality_dims
from services.banners import get_banner_path
from services.gemini import analyze_clip

router = Router()
MAX_SEND_BYTES = 48 * 1024 * 1024
PROCESS_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_JOBS)


def _bar(percent: int, width: int = 10) -> str:
    filled = max(0, min(width, round(percent * width / 100)))
    return "█" * filled + "░" * (width - filled)


def _meta_caption(meta: dict, index: int, total: int) -> str:
    title = meta.get("title") or f"Часть {index}/{total}"
    desc = meta.get("description") or ""
    yt = " ".join(meta.get("hashtags_yt") or [])
    tt = " ".join(meta.get("hashtags_tt") or [])
    lines = [
        f"<b>{title}</b>",
        f"Часть {index}/{total}",
        "",
        desc,
        "",
        f"<b>YouTube Shorts</b>\n{yt}" if yt else "",
        f"<b>TikTok</b>\n{tt}" if tt else "",
    ]
    text = "\n".join(x for x in lines if x is not None)
    return text[:1024]


def _next_kb(index: int, total: int):
    if index + 1 >= total:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"▶️ Следующая · {index + 2}/{total}",
                    callback_data=f"nextpart:{index + 1}",
                )
            ]
        ]
    )


@router.message(lambda m: m.text and m.text.startswith(("http://", "https://")))
async def video_link(message: Message):
    uid = message.from_user.id
    if not is_allowed(uid):
        return await message.answer("⛔️ Доступ запрещён.")

    user_dir = WORK_DIR / str(uid)
    raw = user_dir / "raw"
    processed = user_dir / "processed"
    raw.mkdir(parents=True, exist_ok=True)

    status = await message.answer(
        "🔗 <b>Ссылка принята</b>\nГотовлю обработку…",
        parse_mode="HTML",
    )
    loop = asyncio.get_running_loop()
    last_edit = {"t": 0.0}

    def progress_callback(percent, text):
        now = time.time()
        if now - last_edit["t"] < 2 and percent not in (0, 100):
            return
        last_edit["t"] = now

        async def _edit():
            try:
                body = text if percent is None else f"{text}\n[{_bar(percent)}] {percent}%"
                await status.edit_text(body)
            except Exception:
                pass

        asyncio.run_coroutine_threadsafe(_edit(), loop)

    try:
        s = get_settings(uid)
        try:
            quality = int(s.get("quality") or 720)
        except (TypeError, ValueError):
            quality = 720
        if quality not in (480, 720, 1080):
            quality = 720
        width, height = quality_dims(quality)
        try:
            clip_sec = int(s.get("clip_seconds") or 30)
        except (TypeError, ValueError):
            clip_sec = 30
        if clip_sec not in (15, 30, 45, 60):
            clip_sec = 30
        mirror = bool(s.get("mirror"))
        send_all = bool(s.get("send_all"))
        gemini_on = bool(s.get("gemini_on", True))
        banner_id = s.get("banner_id") or ""
        banner_on = bool(s.get("banner_enabled"))
        banner_path = get_banner_path(banner_id) if banner_on and banner_id else None

        async with PROCESS_SEMAPHORE:
            await status.edit_text("⬇️ <b>Скачивание…</b>", parse_mode="HTML")
            src = await asyncio.to_thread(
                download, message.text.strip(), raw, quality, progress_callback
            )
            src = Path(src)
            if not src.exists():
                raise RuntimeError("Скачанный файл не найден.")

            max_bytes = int(MAX_FILE_SIZE) if MAX_FILE_SIZE else 0
            file_size = int(src.stat().st_size)
            if max_bytes > 0 and file_size > max_bytes:
                mb = file_size / (1024 * 1024)
                lim = max_bytes / (1024 * 1024)
                cleanup_paths(src)
                return await status.edit_text(
                    f"⚠️ Файл слишком большой: {mb:.0f} МБ (лимит {lim:.0f} МБ)."
                )

            await status.edit_text(
                f"✅ Скачано · <b>{file_size / (1024 * 1024):.1f} МБ</b>\n"
                f"✂️ Нарезка по <b>{clip_sec} сек</b>…",
                parse_mode="HTML",
            )
            raw_parts_dir = processed / "raw_parts"
            raw_parts = await asyncio.to_thread(split_video, src, raw_parts_dir, clip_sec)
            cleanup_paths(src)
            gc.collect()

            if not raw_parts:
                return await status.edit_text("⚠️ Не удалось нарезать видео.")

            final_parts = []
            metadata = []
            out_dir = processed / "final"
            out_dir.mkdir(parents=True, exist_ok=True)
            total = len(raw_parts)

            for i, part in enumerate(raw_parts):
                part = Path(part)
                try:
                    await status.edit_text(
                        f"🎨 Обработка  <b>{i + 1}/{total}</b> · {quality}p",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

                final = out_dir / f"part_{i:03d}.mp4"
                await asyncio.to_thread(
                    render_part,
                    part,
                    final,
                    width,
                    height,
                    mirror,
                    str(banner_path) if banner_path else None,
                    30.0,
                )
                cleanup_paths(part)

                meta = {
                    "title": f"Часть {i + 1}/{total}",
                    "description": "",
                    "hashtags_yt": [],
                    "hashtags_tt": [],
                }
                if gemini_on:
                    try:
                        await status.edit_text(
                            f"🤖 Gemini  <b>{i + 1}/{total}</b>",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                    meta = await asyncio.to_thread(analyze_clip, final, i, total)

                final_parts.append(final)
                metadata.append(meta)
                gc.collect()

            save_settings(
                uid,
                last_parts=[str(p) for p in final_parts],
                last_sent_index=0,
                last_metadata=metadata,
            )
            await status.edit_text(
                f"✅ <b>Готово</b> · {len(final_parts)} частей · {quality}p",
                parse_mode="HTML",
            )

            to_send = final_parts if send_all else final_parts[:1]
            for i, part in enumerate(to_send):
                if not part.exists():
                    continue
                if part.stat().st_size > MAX_SEND_BYTES:
                    await message.answer(f"Часть {i + 1} слишком большая для Telegram.")
                    continue
                meta = metadata[i] if i < len(metadata) else {}
                cap = _meta_caption(meta, i + 1, len(final_parts))
                kb = None if send_all else _next_kb(i, len(final_parts))
                await message.answer_video(
                    FSInputFile(part),
                    caption=cap,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
            if not send_all:
                save_settings(uid, last_sent_index=1)

            cleanup_user_work(user_dir, keep_final=True)
            gc.collect()

    except Exception as e:
        try:
            await status.edit_text(f"❌ {type(e).__name__}: {e}")
        except Exception:
            await message.answer(f"❌ {type(e).__name__}: {e}")
        try:
            cleanup_user_work(user_dir, keep_final=False)
        except Exception:
            pass
        gc.collect()


async def _send_part(message: Message, paths: list, index: int, metadata: list):
    total = len(paths)
    if index < 0 or index >= total:
        return await message.answer("Больше частей нет.")
    part = Path(paths[index])
    if not part.exists():
        return await message.answer("Файл не найден. Нарежьте снова.")
    if part.stat().st_size > MAX_SEND_BYTES:
        return await message.answer("Файл слишком большой для Telegram.")
    meta = metadata[index] if index < len(metadata) else {}
    await message.answer_video(
        FSInputFile(part),
        caption=_meta_caption(meta, index + 1, total),
        parse_mode="HTML",
        reply_markup=_next_kb(index, total),
    )
    save_settings(message.from_user.id, last_sent_index=index + 1)


@router.callback_query(F.data.startswith("nextpart:"))
async def next_part_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    try:
        index = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        return await call.answer("Ошибка", show_alert=True)
    s = get_settings(call.from_user.id)
    paths = [Path(p) for p in (s.get("last_parts") or [])]
    if not paths:
        return await call.message.answer("Сначала отправьте ссылку.")
    await call.answer()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    class _Msg:
        def __init__(self, origin):
            self.from_user = call.from_user
            self.answer = origin.answer
            self.answer_video = origin.answer_video

    await _send_part(_Msg(call.message), paths, index, s.get("last_metadata") or [])
