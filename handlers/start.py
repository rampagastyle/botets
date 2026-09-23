from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import is_allowed

router = Router()


@router.message(Command("start", "help"))
async def start(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer("Доступ запрещён.")
    await message.answer(
        "🎬 Видео-бот: нарезка + баннер CSDOG\n\n"
        "Отправьте ссылку на видео (RuTube, VK, Twitch…).\n"
        "YouTube — если сеть/cookies позволяют.\n\n"
        "Команды:\n"
        "/settings — текущие настройки\n"
        "/clip — длина куска: 15 / 30 / 45 / 60 сек\n"
        "/banner — инструкция по баннеру\n"
        "/mirror — зеркало вкл/выкл\n\n"
        "Баннер (MP4 с озвучкой) пришлите файлом с подписью: баннер\n"
        "Скачать креатив: https://t.me/csdogTikTok/62\n"
        "Правила: https://telegra.ph/Usloviya-bannerov-csdog-09-08\n\n"
        "TikTok drafts — после подключения официального API."
    )
