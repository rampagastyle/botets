from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import WORK_DIR, is_admin
from services.whitelist import is_allowed
from services.storage import get_settings, save_settings, DEFAULT_CAPTION
from services.tiktok import set_tiktok_token, get_tiktok_token

router = Router()
CLIP_OPTIONS = (15, 30, 45, 60)


def settings_kb(user_id: int):
    s = get_settings(user_id)
    has = bool(s.get("banner") and Path(str(s.get("banner"))).exists())
    en = bool(s.get("banner_enabled")) and has
    ban_btn = "🎬 Баннер: вкл" if en else "🎬 Баннер: выкл"
    if not has:
        ban_btn = "🎬 Баннер: нет файла"
    clip = int(s.get("clip_seconds") or 15)
    rows = [
        [InlineKeyboardButton(text=ban_btn, callback_data="banner:toggle")],
        [
            InlineKeyboardButton(text=f"{'●' if clip==n else '·'} {n}с", callback_data=f"clip:{n}")
            for n in CLIP_OPTIONS
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def clip_kb(current: int = 15):

    row = []
    for n in CLIP_OPTIONS:
        mark = "·" if n != current else "●"
        row.append(
            InlineKeyboardButton(
                text=f"{mark} {n}с",
                callback_data=f"clip:{n}",
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[row])


def _settings_text(user_id: int) -> str:
    s = get_settings(user_id)
    tt = get_tiktok_token(user_id)
    has_ban = bool(s.get("banner") and Path(s.get("banner")).exists())
    en = bool(s.get("banner_enabled")) and has_ban
    ban = ("вкл" if en else "выкл") if has_ban else "не загружен"
    mir = "вкл" if s.get("mirror") else "выкл"
    allp = "вкл" if s.get("send_all") else "выкл"
    tok = "да" if tt and tt.get("access_token") else "нет"
    cap = (s.get("caption") or DEFAULT_CAPTION).replace("<", "").replace(">", "")
    if len(cap) > 100:
        cap = cap[:100] + "…"
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️  <b>Настройки</b>  ·  VideoProcessing v12\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱  Длина куска   <b>{s.get('clip_seconds', 15)} сек</b>\n"
        f"🪞  Mirror        <b>{mir}</b>\n"
        f"🎬  Баннер        <b>{ban}</b>\n"
        f"📦  Слать все     <b>{allp}</b>\n"
        f"🎵  TikTok token  <b>{tok}</b>\n\n"
        f"📝  Caption\n<code>{cap}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Настройки")
async def settings_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    s = get_settings(message.from_user.id)
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
        return await message.answer(
            f"✅ Длина куска: <b>{arg} сек</b>", parse_mode="HTML"
        )
    s = get_settings(message.from_user.id)
    await message.answer(
        "⏱ Длина одного куска:",
        reply_markup=clip_kb(int(s.get("clip_seconds") or 15)),
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
            f"✅ Длина куска: <b>{sec} сек</b>",
            parse_mode="HTML",
            reply_markup=clip_kb(sec),
        )
    except Exception:
        await call.message.answer(
            f"✅ Длина куска: <b>{sec} сек</b>",
            parse_mode="HTML",
        )


@router.message(Command("banner"))
@router.message(F.text == "🎬 Баннер")
async def banner_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎬  <b>Баннер</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправьте <b>видео</b> с подписью:\n"
        "<code>баннер</code>\n\n"
        "~4 сек, с озвучкой (CSDOG)\n"
        "https://t.me/csdogTikTok/62",
        parse_mode="HTML",
        disable_web_page_preview=True,
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
        return await message.answer("⚠️ Нужен видеофайл (MP4/MOV).")
    dest_dir = WORK_DIR / str(message.from_user.id) / "banner"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "banner.mp4"
    await message.bot.download(file, destination=dest)
    save_settings(message.from_user.id, banner=str(dest), banner_enabled=True)
    await message.answer(
        "✅ Баннер сохранён на сервере и <b>включён</b>.\n"
        "Вставка с <b>30 сек</b> (если кусок короче — по центру).\n"
        "Выключить: ⚙️ Настройки → кнопка баннера",
        parse_mode="HTML",
    )


@router.message(Command("mirror"))
@router.message(F.text == "🪞 Mirror")
async def mirror_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    s = get_settings(message.from_user.id)
    new = not s.get("mirror", False)
    save_settings(message.from_user.id, mirror=new)
    await message.answer(
        f"🪞 Mirror: <b>{'вкл' if new else 'выкл'}</b>", parse_mode="HTML"
    )


@router.message(Command("sendall"))
@router.message(F.text == "📦 Все части")
async def sendall_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    s = get_settings(message.from_user.id)
    new = not s.get("send_all", False)
    save_settings(message.from_user.id, send_all=new)
    await message.answer(
        f"📦 Слать все части сразу: <b>{'вкл' if new else 'выкл'}</b>",
        parse_mode="HTML",
    )


@router.message(Command("caption"))
@router.message(F.text == "📝 Caption")
async def caption_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    if message.text and message.text.startswith("📝"):
        arg = ""
    else:
        arg = message.text.partition(" ")[2].strip() if message.text else ""
    if not arg:
        s = get_settings(message.from_user.id)
        return await message.answer(
            "📝 Caption сейчас:\n\n"
            f"<code>{s.get('caption') or DEFAULT_CAPTION}</code>\n\n"
            "Сменить: <code>/caption текст #cs2</code>\n"
            "Сброс: <code>/caption reset</code>",
            parse_mode="HTML",
        )
    if arg == "reset":
        save_settings(message.from_user.id, caption=DEFAULT_CAPTION)
        return await message.answer("✅ Caption сброшен.")
    save_settings(message.from_user.id, caption=arg)
    await message.answer(f"✅ Caption:\n<code>{arg}</code>", parse_mode="HTML")


@router.message(F.text == "❓ Помощь")
async def help_btn(message: Message):
    from handlers.start import about_cmd, start
    if not is_allowed(message.from_user.id):
        from handlers.start import denied_text
        return await message.answer(denied_text(message.from_user.id), parse_mode="HTML")
    await about_cmd(message)


@router.message(F.text == "👥 Whitelist")
async def wl_btn(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Только для админа.")
    from handlers.admin import whitelist_cmd
    await whitelist_cmd(message)


@router.message(Command("tiktok"))
async def tiktok_help(message: Message):
    if not is_allowed(message.from_user.id):
        return
    tt = get_tiktok_token(message.from_user.id)
    status = "подключён" if tt and tt.get("access_token") else "нет"
    await message.answer(
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎵  <b>TikTok</b> · {status}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Без Developer App — загрузка вручную.\n"
        "Токен: <code>/settoken act.xxx</code>\n"
        "В inbox: <code>/todraft</code>",
        parse_mode="HTML",
    )


@router.message(Command("settoken"))
async def settoken_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        return await message.answer(
            "Пример: <code>/settoken act.xxxxx</code>", parse_mode="HTML"
        )
    set_tiktok_token(
        message.from_user.id,
        parts[1].strip(),
        parts[2].strip() if len(parts) > 2 else "",
    )
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ TikTok token сохранён.")
