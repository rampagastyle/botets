import asyncio
import time
from aiogram import Router
from aiogram.types import Message, FSInputFile
from config import WORK_DIR, MAX_FILE_SIZE, is_allowed
from services.storage import get_settings
from services.downloader import download
from services.processor import process, split_video
from pathlib import Path

router = Router()
MAX_SEND_BYTES = 45 * 1024 * 1024


@router.message(lambda m: m.text and m.text.startswith(("http://", "https://")))
async def video_link(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer("Доступ запрещён.")

    user_dir = WORK_DIR / str(message.from_user.id)
    raw = user_dir / "raw"
    processed = user_dir / "processed"

    status = await message.answer("Ссылка принята.\nПодключаюсь к источнику…")

    loop = asyncio.get_running_loop()
    last_edit = {"t": 0.0}

    def progress_callback(percent, text):
        # не чаще раза в 2 сек, чтобы Telegram не резал flood
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
        await status.edit_text("Скачивание началось…")
        src = await asyncio.to_thread(
            download, message.text.strip(), raw, progress_callback
        )

        size_mb = src.stat().st_size / 1024 / 1024
        if src.stat().st_size > MAX_FILE_SIZE:
            return await status.edit_text("Файл превышает установленный лимит.")

        await status.edit_text(
            f"Скачано: {size_mb:.1f} МБ\n"
            f"Начинаю обработку 9:16 (это может занять несколько минут)…"
        )

        s = get_settings(message.from_user.id)
        out = processed / f"{src.stem}_vertical.mp4"

        await asyncio.to_thread(
            process,
            src,
            out,
            s.get("watermark") or None,
            s.get("position", "bottom-right"),
            s.get("mirror", False),
        )

        out_mb = out.stat().st_size / 1024 / 1024
        await status.edit_text(
            f"Обработка 9:16 готова ({out_mb:.1f} МБ).\nРежу на части по 60 сек…"
        )

        if out.stat().st_size <= MAX_SEND_BYTES:
            await message.answer_video(FSInputFile(out), caption="Предпросмотр готов.")
        else:
            await status.edit_text(
                f"Файл {out_mb:.0f} МБ — целиком в Telegram не влезет.\n"
                f"Режу на части по 60 сек…"
            )

        parts = await asyncio.to_thread(split_video, out, processed / "parts", 60)
        await status.edit_text(f"Готово.\nЧастей: {len(parts)}")

        if parts and parts[0].stat().st_size <= MAX_SEND_BYTES:
            await message.answer_video(
                FSInputFile(parts[0]),
                caption="Часть 1 (превью)",
            )

    except Exception as e:
        try:
            await status.edit_text(f"Ошибка: {type(e).__name__}: {e}")
        except Exception:
            await message.answer(f"Ошибка: {type(e).__name__}: {e}")


def _bar(percent: int, width: int = 10) -> str:
    filled = max(0, min(width, round(percent * width / 100)))
    return "█" * filled + "░" * (width - filled)