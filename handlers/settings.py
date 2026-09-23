from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import is_allowed, WORK_DIR
from services.storage import get_settings, save_settings

router = Router()
CLIP_OPTIONS = (15, 30, 45, 60)


def clip_kb():
    row = [
        InlineKeyboardButton(text=f"{n}с", callback_data=f"clip:{n}")
        for n in CLIP_OPTIONS
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row])


@router.message(Command("settings"))
async def settings_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    s = get_settings(message.from_user.id)
    await message.answer(
        "⚙️ Настройки\n\n"
        f"⏱ Длина нарезки: {s.get('clip_seconds', 30)} сек\n"
        f"🪞 Mirror: {s.get('mirror', False)}\n"
        f"🎬 Баннер: {'загружен' if s.get('banner') else 'нет'}\n"
        f"📤 Autopost: {s.get('autopost', False)}\n\n"
        "/clip — 15 / 30 / 45 / 60\n"
        "/banner — как загрузить баннер\n"
        "/mirror — зеркало\n"
        "Файл с подписью «баннер» — сохранить MP4/MOV",
        reply_markup=clip_kb(),
    )


@router.message(Command("clip"))
async def clip_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    arg = message.text.partition(" ")[2].strip()
    if arg.isdigit() and int(arg) in CLIP_OPTIONS:
        save_settings(message.from_user.id, clip_seconds=int(arg))
        return await message.answer(f"Длина нарезки: {arg} сек")
    await message.answer("Выберите длину куска:", reply_markup=clip_kb())


@router.callback_query(F.data.startswith("clip:"))
async def clip_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    sec = int(call.data.split(":")[1])
    save_settings(call.from_user.id, clip_seconds=sec)
    await call.answer(f"{sec} сек")
    try:
        await call.message.edit_text(f"Длина нарезки: {sec} сек")
    except Exception:
        await call.message.answer(f"Длина нарезки: {sec} сек")


@router.message(Command("banner"))
async def banner_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer(
        "Пришлите файл баннера (MP4/MOV) с подписью:\n"
        "баннер\n\n"
        "По правилам CSDOG — с озвучкой, ~4 сек, по центру ролика.\n"
        "Скачать: https://t.me/csdogTikTok/62\n"
        "Правила: https://telegra.ph/Usloviya-bannerov-csdog-09-08"
    )


@router.message(F.video | F.document)
async def banner_file(message: Message):
    if not is_allowed(message.from_user.id):
        return

    caption = (message.caption or "").lower().strip()
    if "баннер" not in caption and "banner" not in caption:
        return

    file = message.video or message.document
    if message.document and not (message.document.mime_type or "").startswith("video"):
        return await message.answer("Нужен видеофайл (MP4/MOV).")

    dest_dir = WORK_DIR / str(message.from_user.id) / "banner"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "banner.mp4"

    await message.bot.download(file, destination=dest)
    save_settings(message.from_user.id, banner=str(dest))
    await message.answer(
        "Баннер сохранён.\nБудет вставляться в центр каждой нарезки."
    )


@router.message(Command("mirror"))
async def mirror_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    s = get_settings(message.from_user.id)
    new = not s.get("mirror", False)
    save_settings(message.from_user.id, mirror=new)
    await message.answer(f"Mirror: {new}")


@router.message(Command("autopost"))
async def autopost_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    s = get_settings(message.from_user.id)
    new = not s.get("autopost", False)
    save_settings(message.from_user.id, autopost=new)
    await message.answer(
        f"Autopost: {new}\n"
        "(Автозалив в TikTok — после подключения Content Posting API)"
    )
