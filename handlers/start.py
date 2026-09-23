from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from config import is_allowed

router = Router()


def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="⏱ Длина")],
            [KeyboardButton(text="🎬 Баннер"), KeyboardButton(text="🪞 Mirror")],
            [KeyboardButton(text="📝 Caption"), KeyboardButton(text="📦 Все части")],
            [KeyboardButton(text="🔁 Последние"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )


@router.message(Command("start", "help"))
async def start(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer("⛔️ Доступ запрещён.")
    await message.answer(
        "━━━━━━━━━━━━━━━━━━\n"
        "🎬  <b>Video Bot</b> · CSDOG\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте <b>ссылку</b> на видео\n"
        "(RuTube, VK и др.)\n\n"
        "Я скачаю → нарежу → сделаю 9:16\n"
        "→ вставлю баннер\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️ /settings — всё меню\n"
        "⏱ /clip — 15 · 30 · 45 · 60 сек\n"
        "🎬 баннер: файл с подписью <code>баннер</code>\n"
        "📝 /caption — текст для TikTok\n"
        "📦 /sendall · 🔁 /last\n"
        "━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=main_kb(),
    )
