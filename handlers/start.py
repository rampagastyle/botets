from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from config import is_admin
from services.whitelist import is_allowed

router = Router()

BOT_NAME = "VideoProcessing"
BOT_VERSION = "v12"
SUPPORT = "@classismfact"


def main_kb(user_id: int | None = None):
    rows = [
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="⏱ Длина")],
        [KeyboardButton(text="🎬 Баннер"), KeyboardButton(text="🪞 Mirror")],
        [KeyboardButton(text="📝 Caption"), KeyboardButton(text="📦 Все части")],
        [KeyboardButton(text="🔁 Последние"), KeyboardButton(text="ℹ️ О проекте")],
    ]
    if user_id and is_admin(user_id):
        rows.append([KeyboardButton(text="👥 Whitelist")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def denied_text(user_id: int) -> str:
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


def about_text() -> str:
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬  <b>{BOT_NAME}</b>  ·  {BOT_VERSION}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Что это</b>\n"
        f"Бот для нарезки длинных роликов в короткие "
        f"вертикальные клипы (9:16) и вставки рекламного "
        f"<b>баннера-видео</b> в нужную секунду.\n\n"
        f"Подходит не только для CSDOG: любые нарезки, "
        f"стримы, геймплей, обзоры — везде, где нужен "
        f"короткий формат и свой баннер по правилам кампании.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>С чего начать</b>\n"
        f"1. Загрузите баннер (если нужен): кнопка «🎬 Баннер» "
        f"или видео с подписью <code>баннер</code>.\n"
        f"2. В «⚙️ Настройки» включите баннер кнопкой "
        f"«🎬 Баннер: вкл/выкл».\n"
        f"3. Выберите длину куска: 15 / 30 / 45 / 60 сек.\n"
        f"4. Отправьте <b>ссылку</b> на видео (RuTube, VK и др.).\n"
        f"5. Дождитесь обработки и забирайте части "
        f"(кнопка «Следующая часть»).\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Кнопки</b>\n\n"
        f"⚙️ <b>Настройки</b> — сводка: длина куска, mirror, "
        f"баннер, caption, режим «все части». "
        f"Отсюда же переключается баннер и длина.\n\n"
        f"⏱ <b>Длина</b> — длина одного куска после нарезки: "
        f"15, 30, 45 или 60 секунд. "
        f"Для баннера с 30-й секунды лучше 45–60 сек.\n\n"
        f"🎬 <b>Баннер</b> — инструкция по загрузке. "
        f"Файл хранится на сервере. "
        f"Вставка с <b>30-й секунды</b> куска; "
        f"если кусок короче — ближе к центру. "
        f"Вкл/выкл — одной кнопкой в настройках "
        f"(файл при этом не удаляется).\n\n"
        f"🪞 <b>Mirror</b> — зеркальное отражение картинки "
        f"(иногда помогает от блокировок шаблонов).\n\n"
        f"📝 <b>Caption</b> — шаблон текста под ролик "
        f"(хештеги, ссылка). Показывается после нарезки, "
        f"удобно копировать в TikTok / Shorts / Reels.\n\n"
        f"📦 <b>Все части</b> — если вкл, после обработки "
        f"бот пришлёт все куски сразу. "
        f"Если выкл — только первую и кнопку "
        f"«Следующая часть».\n\n"
        f"🔁 <b>Последние</b> — ещё раз отправить файлы "
        f"последней успешной нарезки (пока они на сервере).\n\n"
        f"ℹ️ <b>О проекте</b> — этот текст.\n\n"
        f"👥 <b>Whitelist</b> (только админ) — кто может "
        f"пользоваться ботом.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Команды</b>\n\n"
        f"/start · /help — главное меню\n"
        f"/settings — настройки\n"
        f"/clip 30 — длина куска\n"
        f"/banner — как загрузить баннер\n"
        f"/mirror — зеркало вкл/выкл\n"
        f"/caption текст — свой текст под видео\n"
        f"/caption reset — сбросить caption\n"
        f"/sendall — режим «слать все части»\n"
        f"/last — последние части снова\n"
        f"/cleanup — удалить временные файлы\n"
        f"/myid — ваш Telegram ID\n"
        f"/whitelist · /allow · /deny — управление доступом (админ)\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Баннер — кратко</b>\n"
        f"• Загрузка: видео + подпись <code>баннер</code>\n"
        f"• Хранение: на сервере, пока не зальёте новый\n"
        f"• Старт вставки: с 30-й секунды куска\n"
        f"• Вкл/выкл: Настройки → кнопка баннера\n"
        f"• Подходит под разные рекламные офферы, "
        f"не только CSDOG\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Ограничения</b>\n"
        f"• Тяжёлые длинные ролики на слабом хостинге "
        f"могут обрабатываться долго или упираться в память — "
        f"берите куски 15–30 сек.\n"
        f"• YouTube с облака часто режет загрузку; "
        f"RuTube / VK обычно стабильнее.\n"
        f"• TikTok API (автозалив в черновики) — "
        f"только при своём Developer-приложении.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Техподдержка · доступ · вопросы:\n"
        f"👉 {SUPPORT}\n"
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
        f"Нарезка видео · вертикаль 9:16 · баннер\n"
        f"Для любых кампаний и контента, не только CSDOG.\n\n"
        f"📎 Отправьте <b>ссылку</b> на ролик\n"
        f"   или откройте «ℹ️ О проекте»\n\n"
        f"{admin_line}"
        f"Поддержка: {SUPPORT}\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=main_kb(message.from_user.id),
    )


@router.message(Command("about", "info", "project"))
@router.message(F.text == "ℹ️ О проекте")
async def about_cmd(message: Message):
    # о проекте видно и без whitelist — но полный гайд только своим
    if not is_allowed(message.from_user.id):
        return await message.answer(
            denied_text(message.from_user.id),
            parse_mode="HTML",
        )
    # Telegram limit ~4096; about_text may be long — split if needed
    text = about_text()
    if len(text) <= 4000:
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    else:
        mid = text.find("<b>Команды</b>")
        if mid == -1:
            mid = len(text) // 2
        await message.answer(text[:mid], parse_mode="HTML", disable_web_page_preview=True)
        await message.answer(
            "━━━━━━━━━━━━━━━━━━━━\n" + text[mid:],
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
