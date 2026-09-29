from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from config import is_admin
from services.whitelist import is_allowed

router = Router()

BOT_NAME = "VideoProcessing"
BOT_VERSION = "v15"
SUPPORT = "@classismfact"


def main_kb(user_id: int | None = None):
    rows = [
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="⏱ Длина")],
        [KeyboardButton(text="🎬 Баннер"), KeyboardButton(text="🎞 Качество")],
        [KeyboardButton(text="📦 Все части"), KeyboardButton(text="🔁 Последние")],
        [KeyboardButton(text="ℹ️ О проекте"), KeyboardButton(text="❓ Help")],
    ]
    if user_id and is_admin(user_id):
        rows.append([KeyboardButton(text="👥 Whitelist"), KeyboardButton(text="🛠 Баннеры")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def denied_text(user_id: int) -> str:
    return (
        f"<b>{BOT_NAME}</b>  ·  {BOT_VERSION}\n\n"
        f"Доступ ограничен whitelist.\n\n"
        f"Ваш ID: <code>{user_id}</code>\n\n"
        f"Поддержка и доступ: {SUPPORT}"
    )


def about_text() -> str:
    return (
        f"<b>{BOT_NAME}</b>  ·  {BOT_VERSION}\n"
        f"────────────────────\n\n"
        f"Профессиональная нарезка длинных роликов "
        f"в вертикальные клипы <b>9:16</b> с баннером и "
        f"AI-описанием для Shorts / TikTok.\n\n"
        f"<b>Как пользоваться</b>\n"
        f"1. Выберите длину куска и качество\n"
        f"2. Включите нужный баннер (если есть)\n"
        f"3. Отправьте ссылку на видео\n"
        f"4. Получите части + заголовок, описание, хештеги\n\n"
        f"<b>Возможности</b>\n"
        f"• RuTube, VK и другие источники\n"
        f"• Размытый фон 9:16\n"
        f"• Баннеры кампаний (общие для всех)\n"
        f"• Gemini: title / description / хештеги YT и TikTok\n"
        f"• Несколько пользователей одновременно\n\n"
        f"Список команд — кнопка <b>❓ Help</b>\n\n"
        f"Поддержка: {SUPPORT}"
    )


def help_text() -> str:
    return (
        f"<b>Команды · {BOT_NAME}</b>\n"
        f"────────────────────\n\n"
        f"/start — главное меню\n"
        f"/help — эта справка\n"
        f"/settings — настройки\n"
        f"/clip 15|30|45|60 — длина куска\n"
        f"/quality 480|720|1080 — качество\n"
        f"/mirror — зеркало вкл/выкл\n"
        f"/banner — выбрать баннер\n"
        f"/sendall — слать все части сразу\n"
        f"/last — последние части снова\n"
        f"/cleanup — очистить временные файлы\n"
        f"/myid — ваш Telegram ID\n\n"
        f"<b>Админ</b>\n"
        f"/createbanner — создать баннер\n"
        f"/banners — список баннеров\n"
        f"/delbanner ID — удалить баннер\n"
        f"/whitelist · /allow · /deny\n\n"
        f"Поддержка: {SUPPORT}"
    )


@router.message(Command("start"))
async def start(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer(denied_text(message.from_user.id), parse_mode="HTML")
    await message.answer(
        f"<b>{BOT_NAME}</b>  ·  {BOT_VERSION}\n"
        f"────────────────────\n\n"
        f"Отправьте <b>ссылку</b> на видео.\n"
        f"Бот нарежет, оформит 9:16 и подготовит "
        f"тексты для Shorts и TikTok.\n\n"
        f"Поддержка: {SUPPORT}",
        parse_mode="HTML",
        reply_markup=main_kb(message.from_user.id),
    )


@router.message(Command("help"))
@router.message(F.text == "❓ Help")
async def help_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer(denied_text(message.from_user.id), parse_mode="HTML")
    await message.answer(help_text(), parse_mode="HTML")


@router.message(Command("about", "info"))
@router.message(F.text == "ℹ️ О проекте")
async def about_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer(denied_text(message.from_user.id), parse_mode="HTML")
    await message.answer(about_text(), parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("myid"))
async def myid_cmd(message: Message):
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>", parse_mode="HTML")
