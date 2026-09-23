from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram import F
from aiogram.types import Message, FSInputFile

from config import is_allowed
from services.storage import get_settings
from services.tiktok import get_tiktok_token, upload_to_inbox
from services.processor import cleanup_user_work
from config import WORK_DIR

router = Router()
MAX_SEND_BYTES = 45 * 1024 * 1024


@router.message(Command("status"))
async def status_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer("Бот онлайн. Ссылка на видео или /help")


@router.message(Command("last"))
@router.message(F.text == "🔁 Последние")
async def last_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    s = get_settings(message.from_user.id)
    paths = [Path(p) for p in (s.get("last_parts") or []) if Path(p).exists()]
    if not paths:
        return await message.answer("Нет сохранённых частей. Сначала отправьте ссылку.")
    await message.answer(f"Пересылаю {len(paths)} частей…")
    for i, part in enumerate(paths, start=1):
        if part.stat().st_size > MAX_SEND_BYTES:
            await message.answer(f"Часть {i} слишком большая, пропуск.")
            continue
        await message.answer_video(
            FSInputFile(part),
            caption=f"Часть {i}/{len(paths)}",
        )


@router.message(Command("todraft"))
async def todraft_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    tt = get_tiktok_token(message.from_user.id)
    token = (tt or {}).get("access_token")
    if not token:
        return await message.answer(
            "Нет TikTok access_token.\n"
            "Инструкция: /tiktok\n"
            "Сохранить: /settoken ВАШ_TOKEN"
        )
    s = get_settings(message.from_user.id)
    paths = [Path(p) for p in (s.get("last_parts") or []) if Path(p).exists()]
    if not paths:
        return await message.answer("Сначала нарежьте видео (отправьте ссылку).")

    part = paths[0]
    await message.answer(f"Загружаю в TikTok inbox: {part.name}…")
    try:
        import asyncio
        result = await asyncio.to_thread(upload_to_inbox, part, token)
        await message.answer(
            "✅ Отправлено в inbox TikTok.\n"
            f"publish_id: {result.get('publish_id')}\n\n"
            "Откройте TikTok → уведомления/inbox → "
            "доделайте публикацию вручную."
        )
    except Exception as e:
        await message.answer(
            f"Ошибка TikTok API: {type(e).__name__}: {e}\n\n"
            "Проверьте scope video.upload и срок access_token."
        )


@router.message(Command("cleanup"))
async def cleanup_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    user_dir = WORK_DIR / str(message.from_user.id)
    cleanup_user_work(user_dir, keep_final=False, keep_banner=True)
    await message.answer("🧹 Временные файлы удалены (баннер оставлен).")
