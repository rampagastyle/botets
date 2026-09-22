from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import is_allowed
from services.storage import get_settings, save_settings

router = Router()

@router.message(Command("settings"))
async def settings(message: Message):
    if not is_allowed(message.from_user.id): return
    s = get_settings(message.from_user.id)
    await message.answer(
        f"Настройки:\n"
        f"watermark: {s['watermark'] or 'нет'}\n"
        f"position: {s['position']}\n"
        f"mirror: {s['mirror']}\n"
        f"autopost: {s['autopost']}\n\n"
        "API-секреты не вводите в чат: храните их в .env/credentials."
    )

@router.message(Command("position"))
async def position(message: Message):
    if not is_allowed(message.from_user.id): return
    arg = message.text.partition(" ")[2].strip()
    allowed = {"top-left","top-right","bottom-left","bottom-right","center"}
    if arg not in allowed:
        return await message.answer("Пример: /position bottom-right")
    save_settings(message.from_user.id, position=arg)
    await message.answer(f"Позиция: {arg}")

@router.message(Command("mirror"))
async def mirror(message: Message):
    if not is_allowed(message.from_user.id): return
    s = get_settings(message.from_user.id)
    save_settings(message.from_user.id, mirror=not s["mirror"])
    await message.answer(f"Mirror: {not s['mirror']}")

@router.message(Command("autopost"))
async def autopost(message: Message):
    if not is_allowed(message.from_user.id): return
    s = get_settings(message.from_user.id)
    save_settings(message.from_user.id, autopost=not s["autopost"])
    await message.answer(f"Autopost: {not s['autopost']}")
