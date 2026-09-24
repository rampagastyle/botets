from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from config import is_admin
from services.whitelist import is_allowed

router = Router()

BOT_NAME = "VideoProcessing"
BOT_VERSION = "v13"
SUPPORT = "@classismfact"


def main_kb(user_id=None):
    rows = [
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="⏱ Длина")],
        [KeyboardButton(text="🎞 Качество"), KeyboardButton(text="🎬 Баннер")],
        [KeyboardButton(text="🪞 Mirror"), KeyboardButton(text="📝 Caption")],
        [KeyboardButton(text="📦 Все части"), KeyboardButton(text="🔁 Последние")],
        [KeyboardButton(text="ℹ️ О проекте")],
    ]
    if user_id and is_admin(user_id):
        rows.append([KeyboardButton(text="👥 Whitelist")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def denied_text(user_id):
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔒  <b>{BOT_NAME}</b>  ·  {BOT_VERSION}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Доступ только по whitelist.\n\n"
        f"Ваш ID: <code>{user_id}</code>\n\n"
        f"Техподдержка и покупка доступа:\n"
        f"👉 {SUPPORT}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


def about_text():
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬  <b>{BOT_NAME}</b>  ·  {BOT_VERSION}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Что это</b>\n"
        f"Бот для нарезки длинных роликов в короткие вертикальные "
        f"клипы (9:16) и вставки рекламного <b>баннера-видео</b>.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>С чего начать</b>\n"
        f"1. При необходимости загрузите баннер.\n"
        f"2. В «⚙️ Настройки» выберите длину куска.\n"
        f"3. Нажмите «🎞 Качество» и выберите 480p / 720p / 1080p.\n"
        f"4. Отправьте <b>ссылку</b> на ролик.\n"
        f"5. Дождитесь обработки и забирайте части.\n\n"
        f"<b>Качество</b>\n"
        f"• 480p — самый экономный режим для бесплатного хостинга.\n"
        f"• 720p — компромисс между качеством и нагрузкой.\n"
        f"• 1080p — максимальный выход, 1080×1920.\n"
        f"При выборе качества бот не скачивает исходник выше этого "
        f"разрешения и никогда не запрашивает источник выше 1080p.\n\n"
        f"<b>Фон</b>\n"
        f"Вместо чёрных полос используется мягкий blur из самого видео. "
        f"Размытая копия считается в уменьшенном размере, чтобы не "
        f"раздувать потребление памяти на Railway.\n\n"
        f"<b>Railway / RAM</b>\n"
        f"Обработка идёт последовательно: один ffmpeg-процесс за раз, "
        f"1 поток кодирования и очистка временных файлов после каждого "
        f"этапа. Это уменьшает пик RAM, но 1080p всё равно работает "
        f"медленнее на слабом тарифе.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Кнопки</b>\n\n"
        f"⚙️ <b>Настройки</b> — все параметры.\n"
        f"🎞 <b>Качество</b> — 480p / 720p / 1080p.\n"
        f"⏱ <b>Длина</b> — 15 / 30 / 45 / 60 сек.\n"
        f"🎬 <b>Баннер</b> — загрузка видео-баннера.\n"
        f"🪞 <b>Mirror</b> — зеркальное отражение.\n"
        f"📦 <b>Все части</b> — отправлять все части сразу.\n"
        f"🔁 <b>Последние</b> — повторно отправить последнюю обработку.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Команды</b>\n\n"
        f"/start · /help — главное меню\n"
        f"/settings — настройки\n"
        f"/quality — качество\n"
        f"/quality 1080 — сразу выбрать 1080p\n"
        f"/clip 30 — длина куска\n"
        f"/banner — как загрузить баннер\n"
        f"/mirror — зеркало вкл/выкл\n"
        f"/caption текст — свой текст под видео\n"
        f"/caption reset — сбросить caption\n"
        f"/sendall — режим «слать все части»\n"
        f"/last — последние части снова\n"
        f"/cleanup — удалить временные файлы\n"
        f"/myid — ваш Telegram ID\n"
        f"/whitelist · /allow · /deny — доступ (админ)\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Поддержка: {SUPPORT}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


@router.message(Command("start", "help"))
async def start(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer(
            denied_text(message.from_user.id),
            parse_mode="HTML",
        )

    admin_line = ""
    if is_admin(message.from_user.id):
        admin_line = "👑 Админ: /whitelist · /allow · /deny\n"

    await message.answer(
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬  <b>{BOT_NAME}</b>  ·  {BOT_VERSION}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Нарезка видео · 9:16 · blur-фон · до 1080p\n"
        f"Для любых кампаний и контента.\n\n"
        f"📎 Отправьте <b>ссылку</b> на ролик\n"
        f"   или откройте «ℹ️ О проекте»\n\n"
        f"{admin_line}"
        f"Поддержка: {SUPPORT}\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=main_kb(message.from_user.id),
    )


@router.message(Command("about", "info", "project"))
async def about_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return await message.answer(
            denied_text(message.from_user.id),
            parse_mode="HTML",
        )

    text = about_text()
    if len(text) <= 4000:
        await message.answer(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    else:
        mid = text.find("<b>Команды</b>")
        if mid == -1:
            mid = len(text) // 2
        await message.answer(
            text[:mid],
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        await message.answer(
            "━━━━━━━━━━━━━━━━━━━━\n" + text[mid:],
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
