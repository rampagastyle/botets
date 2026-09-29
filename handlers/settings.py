from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import is_admin, WORK_DIR
from services.whitelist import is_allowed
from services.storage import get_settings, save_settings
from services.banners import list_banners, get_banner
from services.processor import cleanup_user_work

router = Router()
CLIP_OPTIONS = (15, 30, 45, 60)
QUALITY_OPTIONS = (480, 720, 1080)


def settings_kb(user_id: int):
    s = get_settings(user_id)
    clip = int(s.get("clip_seconds") or 30)
    q = int(s.get("quality") or 720)
    ban = get_banner(s.get("banner_id") or "")
    ban_on = bool(s.get("banner_enabled")) and ban
    ban_label = f"🎬 {ban['name']}: {'ON' if ban_on else 'OFF'}" if ban else "🎬 Баннер: не выбран"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=ban_label, callback_data="banner:toggle")],
            [
                InlineKeyboardButton(
                    text=f"{'●' if clip == n else '·'} {n}с",
                    callback_data=f"clip:{n}",
                )
                for n in CLIP_OPTIONS
            ],
            [
                InlineKeyboardButton(
                    text=f"{'●' if q == n else '·'} {n}p",
                    callback_data=f"quality:{n}",
                )
                for n in QUALITY_OPTIONS
            ],
        ]
    )


def _settings_text(user_id: int) -> str:
    s = get_settings(user_id)
    ban = get_banner(s.get("banner_id") or "")
    ban_on = bool(s.get("banner_enabled")) and ban
    if ban:
        ban_s = f"{ban['name']} · {'вкл' if ban_on else 'выкл'}"
    else:
        ban_s = "не выбран"
    return (
        "<b>Настройки</b>\n"
        "────────────────────\n\n"
        f"⏱  Длина куска   <b>{s.get('clip_seconds', 30)} сек</b>\n"
        f"🎞  Качество      <b>{s.get('quality', 720)}p</b>\n"
        f"🪞  Mirror        <b>{'вкл' if s.get('mirror') else 'выкл'}</b>\n"
        f"🎬  Баннер        <b>{ban_s}</b>\n"
        f"📦  Все части     <b>{'вкл' if s.get('send_all') else 'выкл'}</b>\n"
        f"🤖  Gemini        <b>{'вкл' if s.get('gemini_on', True) else 'выкл'}</b>\n"
    )


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Настройки")
async def settings_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer(
        _settings_text(message.from_user.id),
        parse_mode="HTML",
        reply_markup=settings_kb(message.from_user.id),
    )


@router.message(Command("clip"))
@router.message(F.text == "⏱ Длина")
async def clip_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    arg = (message.text or "").partition(" ")[2].strip()
    if arg.isdigit() and int(arg) in CLIP_OPTIONS:
        save_settings(message.from_user.id, clip_seconds=int(arg))
        return await message.answer(f"✅ Длина куска: <b>{arg} сек</b>", parse_mode="HTML")
    s = get_settings(message.from_user.id)
    await message.answer(
        "Выберите длину одного куска:",
        reply_markup=settings_kb(message.from_user.id),
    )


@router.callback_query(F.data.startswith("clip:"))
async def clip_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    sec = int(call.data.split(":")[1])
    save_settings(call.from_user.id, clip_seconds=sec)
    await call.answer(f"{sec} сек")
    try:
        await call.message.edit_text(
            _settings_text(call.from_user.id),
            parse_mode="HTML",
            reply_markup=settings_kb(call.from_user.id),
        )
    except Exception:
        pass


@router.message(Command("quality"))
@router.message(F.text == "🎞 Качество")
async def quality_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    arg = (message.text or "").partition(" ")[2].strip()
    if arg.isdigit() and int(arg) in QUALITY_OPTIONS:
        save_settings(message.from_user.id, quality=int(arg))
        return await message.answer(f"✅ Качество: <b>{arg}p</b>", parse_mode="HTML")
    await message.answer(
        "Выберите качество:",
        reply_markup=settings_kb(message.from_user.id),
    )


@router.callback_query(F.data.startswith("quality:"))
async def quality_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    q = int(call.data.split(":")[1])
    save_settings(call.from_user.id, quality=q)
    await call.answer(f"{q}p")
    try:
        await call.message.edit_text(
            _settings_text(call.from_user.id),
            parse_mode="HTML",
            reply_markup=settings_kb(call.from_user.id),
        )
    except Exception:
        pass


@router.message(Command("mirror"))
async def mirror_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    s = get_settings(message.from_user.id)
    new = not s.get("mirror", False)
    save_settings(message.from_user.id, mirror=new)
    await message.answer(f"🪞 Mirror: <b>{'вкл' if new else 'выкл'}</b>", parse_mode="HTML")


@router.message(Command("sendall"))
@router.message(F.text == "📦 Все части")
async def sendall_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    s = get_settings(message.from_user.id)
    new = not s.get("send_all", False)
    save_settings(message.from_user.id, send_all=new)
    await message.answer(
        f"📦 Отправка всех частей: <b>{'вкл' if new else 'выкл'}</b>",
        parse_mode="HTML",
    )


@router.message(Command("banner"))
@router.message(F.text == "🎬 Баннер")
async def banner_pick(message: Message):
    if not is_allowed(message.from_user.id):
        return
    banners = list_banners()
    if not banners:
        return await message.answer(
            "Баннеров пока нет.\nАдмин создаёт их командой /createbanner"
        )
    rows = []
    for b in banners:
        rows.append(
            [
                InlineKeyboardButton(
                    text=b.get("name", b["id"]),
                    callback_data=f"banner:use:{b['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Выключить баннер", callback_data="banner:off")])
    await message.answer(
        "<b>Выберите баннер</b>\nОн общий для всех пользователей.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("banner:"))
async def banner_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "toggle":
        s = get_settings(call.from_user.id)
        if not s.get("banner_id") or not get_banner(s.get("banner_id") or ""):
            await call.answer("Сначала выберите баннер", show_alert=True)
            return await banner_pick(call.message)
        new = not bool(s.get("banner_enabled"))
        save_settings(call.from_user.id, banner_enabled=new)
        await call.answer("ON" if new else "OFF")
    elif action == "use" and len(parts) > 2:
        bid = parts[2]
        if not get_banner(bid):
            return await call.answer("Не найден", show_alert=True)
        save_settings(call.from_user.id, banner_id=bid, banner_enabled=True)
        await call.answer("Выбран")
    elif action == "off":
        save_settings(call.from_user.id, banner_enabled=False)
        await call.answer("Выкл")
    else:
        return await call.answer()

    try:
        await call.message.edit_text(
            _settings_text(call.from_user.id),
            parse_mode="HTML",
            reply_markup=settings_kb(call.from_user.id),
        )
    except Exception:
        await call.message.answer(
            _settings_text(call.from_user.id),
            parse_mode="HTML",
            reply_markup=settings_kb(call.from_user.id),
        )


@router.message(Command("cleanup"))
async def cleanup_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    cleanup_user_work(WORK_DIR / str(message.from_user.id), keep_final=False)
    await message.answer("🧹 Временные файлы удалены.")
