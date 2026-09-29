"""Админский мастер создания баннера: /createbanner."""
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import is_admin, WORK_DIR
from services.banners import fetch_rules_text, save_banner
from services.gemini import summarize_banner_rules

router = Router()


class CreateBanner(StatesGroup):
    name = State()
    rules_url = State()
    file = State()


@router.message(Command("createbanner"))
async def createbanner_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Только для админа.")
    await state.clear()
    await state.set_state(CreateBanner.name)
    await message.answer(
        "<b>Создание баннера</b>\n"
        "────────────────────\n\n"
        "Шаг 1/3 · Введите <b>название</b> баннера\n"
        "(например: CSDOG, Promo A)\n\n"
        "Отмена: /cancel",
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext):
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer("Отменено.")


@router.message(CreateBanner.name)
async def createbanner_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    name = (message.text or "").strip()
    if not name or name.startswith("/"):
        return await message.answer("Введите название текстом.")
    await state.update_data(name=name[:80])
    await state.set_state(CreateBanner.rules_url)
    await message.answer(
        "Шаг 2/3 · Пришлите <b>ссылку на правила</b>\n"
        "(telegra.ph, сайт кампании)\n\n"
        "Бот прочитает страницу и сделает краткое резюме.",
        parse_mode="HTML",
    )


@router.message(CreateBanner.rules_url)
async def createbanner_rules(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    url = (message.text or "").strip()
    if not url.startswith("http"):
        return await message.answer("Нужна ссылка http/https.")

    status = await message.answer("🔎 Читаю правила…")
    summary = ""
    try:
        text = await __import__("asyncio").to_thread(fetch_rules_text, url)
        summary = await __import__("asyncio").to_thread(summarize_banner_rules, text, url)
    except Exception as e:
        summary = f"Не удалось разобрать страницу ({type(e).__name__}). Правила: {url}"

    await state.update_data(rules_url=url, rules_summary=summary)
    await state.set_state(CreateBanner.file)

    await status.edit_text(
        f"<b>Резюме правил</b>\n"
        f"────────────────────\n\n"
        f"{summary}\n\n"
        f"Шаг 3/3 · Пришлите <b>видеофайл баннера</b> (MP4/MOV).",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(CreateBanner.file, F.video | F.document)
async def createbanner_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    file = message.video or message.document
    if message.document and not (message.document.mime_type or "").startswith("video"):
        return await message.answer("Нужен видеофайл.")

    tmp_dir = WORK_DIR / "tmp_banners"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tmp_dir / f"upload_{message.from_user.id}.mp4"
    await message.bot.download(file, destination=tmp)

    entry = save_banner(
        data.get("name") or "Banner",
        data.get("rules_url") or "",
        data.get("rules_summary") or "",
        tmp,
    )
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass
    await state.clear()
    await message.answer(
        f"✅ Баннер сохранён на сервере\n\n"
        f"<b>{entry['name']}</b>\n"
        f"id: <code>{entry['id']}</code>\n\n"
        f"Пользователи выбирают его в 🎬 Баннер / настройках.",
        parse_mode="HTML",
    )


@router.message(CreateBanner.file)
async def createbanner_file_wrong(message: Message):
    await message.answer("Пришлите видеофайл баннера.")
