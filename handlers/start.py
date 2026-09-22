from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import is_allowed

router = Router()

@router.message(Command("start"))
async def start(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer("Доступ запрещён.")
    await message.answer(
        "Видео-бот готов.\n\n"
        "Отправьте ссылку на видео.\n"
        "/settings — настройки\n"
        "/watermark — загрузить PNG/GIF\n"
        "/position — позиция водяного знака\n"
        "/mirror — зеркалирование\n"
        "/autopost — автопубликация\n"
        "/status — статус"
    )
