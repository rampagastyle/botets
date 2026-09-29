from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

from config import WORK_DIR
from services.whitelist import is_allowed
from services.storage import get_settings
from services.processor import cleanup_user_work

router = Router()
MAX_SEND_BYTES = 48 * 1024 * 1024


@router.message(Command("last"))
@router.message(F.text == "🔁 Последние")
async def last_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    s = get_settings(message.from_user.id)
    paths = [Path(p) for p in (s.get("last_parts") or []) if Path(p).exists()]
    if not paths:
        return await message.answer("Нет сохранённых частей.")
    meta = s.get("last_metadata") or []
    await message.answer(f"Пересылаю {len(paths)} частей…")
    for i, part in enumerate(paths):
        if part.stat().st_size > MAX_SEND_BYTES:
            continue
        m = meta[i] if i < len(meta) else {}
        title = m.get("title") or f"Часть {i + 1}"
        await message.answer_video(
            FSInputFile(part),
            caption=f"<b>{title}</b>\nЧасть {i + 1}/{len(paths)}",
            parse_mode="HTML",
        )


@router.message(Command("status"))
async def status_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer("Бот онлайн. Отправьте ссылку или /help")
