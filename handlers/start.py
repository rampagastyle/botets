from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from config import is_admin
from services.whitelist import is_allowed

router = Router()


def main_kb(user_id: int | None = None):
    rows = [
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="⏱ Длина")],
        [KeyboardButton(text="🎬 Баннер"), KeyboardButton(text="🪞 Mirror")],
        [KeyboardButton(text="📝 Caption"), KeyboardButton(text="📦 Все части")],
        [KeyboardButton(text="🔁 Последние"), KeyboardButton(text="❓ Помощь")],
    ]
    if user_id and is_admin(user_id):
        rows.append([KeyboardButton(text="👥 Whitelist")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


@router.message(Command("start", "help"))
async def start(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer(
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⛔️  <b>Нет доступа</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Ваш ID: <code>{message.from_user.id}</code>\n"
            "Попросите админа добавить вас:\n"
            f"<code>/allow {message.from_user.id}</code>",
            parse_mode="HTML",
        )
    admin_hint = ""
    if is_admin(message.from_user.id):
        admin_hint = (
            "\n👑 <b>Админ:</b> /whitelist · /allow · /deny\n"
        )
    await message.answer(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎬  <b>Video Bot</b>\n"
        "    нарезка · баннер · CSDOG\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 Отправьте <b>ссылку</b> на видео\n"
        "   RuTube · VK · другие\n\n"
        "Бот скачает → нарежет → 9:16\n"
        "при необходимости вставит баннер\n"
        "и отдаст части с кнопкой «далее»\n"
        f"{admin_hint}"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ настройки  ·  ⏱ 15–60 сек\n"
        "🎬 баннер: файл + подпись <code>баннер</code>\n"
        "📝 /caption  ·  🔁 /last\n"
        "━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=main_kb(message.from_user.id),
    )
