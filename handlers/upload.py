from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import is_allowed

router = Router()

@router.message(Command("status"))
async def status(message: Message):
    if not is_allowed(message.from_user.id): return
    await message.answer("Статус: бот работает. Обработка выполняется локально.")
