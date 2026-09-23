import asyncio
import time
from pathlib import Path

from aiogram import Router
from aiogram.types import Message, FSInputFile

from config import WORK_DIR, MAX_FILE_SIZE, is_allowed
from services.storage import get_settings
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

    status = await message.answer("Ссылка принята.\nПодключаюсь к источнику…")

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
        await status.edit_text("Скачивание началось…")
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

        # 1) Сначала режем СЫРОЕ (copy) — мало RAM
        await status.edit_text(
            f"Скачано: {size_mb:.1f} МБ\nРежу на части по {clip_sec} сек…"
        )
        raw_parts = await asyncio.to_thread(
            split_video, src, processed / "raw_parts", clip_sec
        )
        if not raw_parts:
            return await status.edit_text("Не удалось нарезать видео.")

        # 2) Каждый кусок отдельно: вертикаль → баннер
        final_parts = []
        out_dir = processed / "final"
        out_dir.mkdir(parents=True, exist_ok=True)

        for i, part in enumerate(raw_parts):
            try:
                await status.edit_text(
                    f"Обработка {i + 1}/{len(raw_parts)} (9:16)…"
                )
            except Exception:
                pass

            vert = out_dir / f"v_{i:03d}.mp4"
            await asyncio.to_thread(to_vertical, part, vert, mirror)

            if banner_path and Path(banner_path).exists():
                final = out_dir / f"part_{i:03d}.mp4"
                try:
                    await status.edit_text(
                        f"Баннер {i + 1}/{len(raw_parts)}…"
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
            note = "\nБаннер не задан (файл с подписью «баннер»)."

        await status.edit_text(f"Готово.\nЧастей: {len(final_parts)}{note}")

        if final_parts:
            first = final_parts[0]
            if first.stat().st_size <= MAX_SEND_BYTES:
                await message.answer_video(
                    FSInputFile(first),
                    caption=f"Часть 1/{len(final_parts)} (превью)",
                )
            else:
                await message.answer(
                    f"Первая часть слишком большая для Telegram "
                    f"({first.stat().st_size // 1024 // 1024} МБ)."
                )

    except Exception as e:
        try:
            await status.edit_text(f"Ошибка: {type(e).__name__}: {e}")
        except Exception:
            await message.answer(f"Ошибка: {type(e).__name__}: {e}")
