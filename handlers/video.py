import asyncio
import time
from pathlib import Path

from aiogram import Router
from aiogram.types import Message, FSInputFile

from config import WORK_DIR, MAX_FILE_SIZE, is_allowed
from services.storage import get_settings, save_settings
from services.downloader import download
from services.processor import to_vertical, insert_banner_center, split_video

router = Router()
MAX_SEND_BYTES = 45 * 1024 * 1024


def _bar(percent: int, width: int = 10) -> str:
    filled = max(0, min(width, round(percent * width / 100)))
    return "█" * filled + "░" * (width - filled)


@router.message(lambda m: m.text and m.text.startswith(("http://", "https://")))
async def video_link(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer("Доступ запрещён.")

    user_dir = WORK_DIR / str(message.from_user.id)
    raw = user_dir / "raw"
    processed = user_dir / "processed"

    status = await message.answer("🔗 <b>Ссылка принята</b>\nПодключаюсь…", parse_mode="HTML")

    loop = asyncio.get_running_loop()
    last_edit = {"t": 0.0}

    def progress_callback(percent, text):
        now = time.time()
        if now - last_edit["t"] < 2 and percent not in (0, 100):
            return
        last_edit["t"] = now

        async def _edit():
            try:
                body = text
                if percent is not None:
                    body = f"{text}\n[{_bar(percent)}] {percent}%"
                await status.edit_text(body)
            except Exception:
                pass

        asyncio.run_coroutine_threadsafe(_edit(), loop)

    try:
        await status.edit_text("⬇️ <b>Скачивание…</b>", parse_mode="HTML")
        src = await asyncio.to_thread(
            download, message.text.strip(), raw, progress_callback
        )

        size_mb = src.stat().st_size / 1024 / 1024
        if src.stat().st_size > MAX_FILE_SIZE:
            return await status.edit_text("Файл превышает установленный лимит.")

        s = get_settings(message.from_user.id)
        clip_sec = int(s.get("clip_seconds") or 30)
        if clip_sec not in (15, 30, 45, 60):
            clip_sec = 30
        mirror = bool(s.get("mirror"))
        banner_path = s.get("banner") or ""
        send_all = bool(s.get("send_all"))
        caption = s.get("caption") or ""

        await status.edit_text(
            f"✅ Скачано: <b>{size_mb:.1f} МБ</b>\n✂️ Режу по <b>{clip_sec} сек</b>…",
            parse_mode="HTML",
        )
        raw_parts = await asyncio.to_thread(
            split_video, src, processed / "raw_parts", clip_sec
        )
        if not raw_parts:
            return await status.edit_text("Не удалось нарезать видео.")

        final_parts = []
        out_dir = processed / "final"
        out_dir.mkdir(parents=True, exist_ok=True)

        for i, part in enumerate(raw_parts):
            try:
                await status.edit_text(
                    f"🎨 9:16 + blur  <b>{i + 1}/{len(raw_parts)}</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass

            vert = out_dir / f"v_{i:03d}.mp4"
            await asyncio.to_thread(to_vertical, part, vert, mirror)

            if banner_path and Path(banner_path).exists():
                final = out_dir / f"part_{i:03d}.mp4"
                try:
                    await status.edit_text(
                        f"🎬 Баннер  <b>{i + 1}/{len(raw_parts)}</b>",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
                await asyncio.to_thread(
                    insert_banner_center, vert, banner_path, final
                )
                final_parts.append(final)
            else:
                final_parts.append(vert)

        note = ""
        if not (banner_path and Path(banner_path).exists()):
            note = "\nℹ️ Баннер не задан"

        # remember paths for /last and /todraft
        save_settings(
            message.from_user.id,
            last_parts=[str(p) for p in final_parts],
        )

        await status.edit_text(f"━━━━━━━━━━━━━━━━━━\n✅ <b>Готово</b> · частей: {len(final_parts)}{note}\n━━━━━━━━━━━━━━━━━━", parse_mode="HTML")

        if caption:
            await message.answer(f"📝 Caption:\n{caption}")

        to_send = final_parts if send_all else final_parts[:1]
        for i, part in enumerate(to_send, start=1):
            if part.stat().st_size > MAX_SEND_BYTES:
                await message.answer(
                    f"Часть {i} слишком большая "
                    f"({part.stat().st_size // 1024 // 1024} МБ), пропуск."
                )
                continue
            await message.answer_video(
                FSInputFile(part),
                caption=f"Часть {i}/{len(final_parts)}",
            )

        if not send_all and len(final_parts) > 1:
            await message.answer(
                f"Отправлена 1 из {len(final_parts)}. "
                "Все части: /sendall и снова ссылка, или /last"
            )

    except Exception as e:
        try:
            await status.edit_text(f"Ошибка: {type(e).__name__}: {e}")
        except Exception:
            await message.answer(f"Ошибка: {type(e).__name__}: {e}")
