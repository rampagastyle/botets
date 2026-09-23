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
from services.storage import get_settings, save_settings, DEFAULT_CAPTION
from services.tiktok import set_tiktok_token, get_tiktok_token

router = Router()
CLIP_OPTIONS = (15, 30, 45, 60)


def clip_kb():
    row = [
        InlineKeyboardButton(text=f"  {n} сек  ", callback_data=f"clip:{n}")
        for n in CLIP_OPTIONS
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def _settings_text(user_id: int) -> str:
    s = get_settings(user_id)
    tt = get_tiktok_token(user_id)
    ban = "✅" if s.get("banner") else "—"
    mir = "вкл" if s.get("mirror") else "выкл"
    allp = "вкл" if s.get("send_all") else "выкл"
    tok = "✅" if tt and tt.get("access_token") else "—"
    cap = (s.get("caption") or DEFAULT_CAPTION).replace("<", "").replace(">", "")
    if len(cap) > 90:
        cap = cap[:90] + "…"
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️  <b>Настройки</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱  Нарезка: <b>{s.get('clip_seconds', 30)} сек</b>\n"
        f"🪞  Mirror: <b>{mir}</b>\n"
        f"🎬  Баннер: <b>{ban}</b>\n"
        f"📦  Все части: <b>{allp}</b>\n"
        f"🎵  TikTok: <b>{tok}</b>\n\n"
        f"📝  Caption:\n<code>{cap}</code>\n"
        "━━━━━━━━━━━━━━━━━━"
    )


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Настройки")
async def settings_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer(
        _settings_text(message.from_user.id),
        parse_mode="HTML",
        reply_markup=clip_kb(),
    )


@router.message(Command("clip"))
@router.message(F.text == "⏱ Длина")
async def clip_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    arg = (message.text or "").partition(" ")[2].strip()
    if arg.isdigit() and int(arg) in CLIP_OPTIONS:
        save_settings(message.from_user.id, clip_seconds=int(arg))
        return await message.answer(f"✅ Длина нарезки: <b>{arg} сек</b>", parse_mode="HTML")
    await message.answer(
        "⏱ Выберите длину одного куска:",
        reply_markup=clip_kb(),
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
            f"✅ Длина нарезки: <b>{sec} сек</b>",
            parse_mode="HTML",
        )
    except Exception:
        await call.message.answer(
            f"✅ Длина нарезки: <b>{sec} сек</b>",
            parse_mode="HTML",
        )


@router.message(Command("banner"))
@router.message(F.text == "🎬 Баннер")
async def banner_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer(
        "━━━━━━━━━━━━━━━━━━\n"
        "🎬  <b>Баннер CSDOG</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Пришлите <b>видеофайл</b> с подписью:\n"
        "<code>баннер</code>\n\n"
        "Требования: ~4 сек, с озвучкой\n"
        "Скачать: https://t.me/csdogTikTok/62\n"
        "Правила: telegra.ph/Usloviya-bannerov-csdog-09-08",
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
    save_settings(message.from_user.id, banner=str(dest))
    await message.answer("✅ Баннер сохранён. Будет в центре каждой нарезки.")


@router.message(Command("mirror"))
@router.message(F.text == "🪞 Mirror")
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
        f"📦 Отправка всех частей: <b>{'вкл' if new else 'выкл'}</b>\n"
        "<i>Много файлов подряд — лимиты Telegram</i>",
        parse_mode="HTML",
    )


@router.message(Command("caption"))
@router.message(F.text == "📝 Caption")
async def caption_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    # if only button pressed, show current
    if message.text and message.text.startswith("📝"):
        arg = ""
    else:
        arg = message.text.partition(" ")[2].strip() if message.text else ""
    if not arg:
        s = get_settings(message.from_user.id)
        return await message.answer(
            "📝 Текущий caption:\n\n"
            f"<code>{s.get('caption') or DEFAULT_CAPTION}</code>\n\n"
            "Сменить: <code>/caption ваш текст #cs2</code>\n"
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
    if not is_allowed(message.from_user.id):
        return
    from handlers.start import start
    await start(message)


@router.message(Command("tiktok"))
async def tiktok_help(message: Message):
    if not is_allowed(message.from_user.id):
        return
    tt = get_tiktok_token(message.from_user.id)
    status = "✅" if tt and tt.get("access_token") else "—"
    await message.answer(
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎵  <b>TikTok API</b>  {status}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Без верификации Developer — только ручная загрузка.\n\n"
        "Если токен есть:\n"
        "<code>/settoken act.xxxxx</code>\n"
        "затем <code>/todraft</code>\n\n"
        "docs: developers.tiktok.com",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("settoken"))
async def settoken_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        return await message.answer("Пример:\n<code>/settoken act.xxxxx</code>", parse_mode="HTML")
    access = parts[1].strip()
    open_id = parts[2].strip() if len(parts) > 2 else ""
    set_tiktok_token(message.from_user.id, access, open_id)
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer("✅ TikTok token сохранён.")
