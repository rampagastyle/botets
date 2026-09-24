from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import is_admin
from services import whitelist as wl

router = Router()


def _wl_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить список", callback_data="wl:refresh"),
            ]
        ]
    )


def _format_list() -> str:
    ids = wl.list_ids()
    if not ids:
        body = "<i>Список пуст — бот открыт для всех</i>"
    else:
        lines = [f"  <code>{i}</code>" for i in ids]
        body = "\n".join(lines)
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👥  <b>Whitelist</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{body}\n\n"
        "Добавить:  <code>/allow 123456789</code>\n"
        "Удалить:   <code>/deny 123456789</code>\n"
        "Список:    <code>/whitelist</code>\n\n"
        "Свой ID: напишите боту @userinfobot\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


@router.message(Command("whitelist", "wl"))
async def whitelist_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Только для админа.")
    await message.answer(_format_list(), parse_mode="HTML", reply_markup=_wl_kb())


@router.callback_query(F.data == "wl:refresh")
async def wl_refresh(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    await call.answer("Обновлено")
    try:
        await call.message.edit_text(
            _format_list(), parse_mode="HTML", reply_markup=_wl_kb()
        )
    except Exception:
        await call.message.answer(_format_list(), parse_mode="HTML", reply_markup=_wl_kb())


@router.message(Command("allow", "adduser"))
async def allow_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Только для админа.")
    arg = message.text.partition(" ")[2].strip()
    if not arg.isdigit():
        return await message.answer(
            "Укажите Telegram ID:\n<code>/allow 123456789</code>",
            parse_mode="HTML",
        )
    added = wl.add(arg)
    if added:
        await message.answer(f"✅ Добавлен в whitelist:\n<code>{arg}</code>", parse_mode="HTML")
    else:
        await message.answer(f"ℹ️ Уже в списке:\n<code>{arg}</code>", parse_mode="HTML")


@router.message(Command("deny", "deluser", "removeuser"))
async def deny_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Только для админа.")
    arg = message.text.partition(" ")[2].strip()
    if not arg.isdigit():
        return await message.answer(
            "Укажите Telegram ID:\n<code>/deny 123456789</code>",
            parse_mode="HTML",
        )
    removed = wl.remove(arg)
    if removed:
        await message.answer(f"🗑 Удалён из whitelist:\n<code>{arg}</code>", parse_mode="HTML")
    else:
        await message.answer(
            "Не найден или это админ (админов удалить нельзя).",
        )


@router.message(Command("myid"))
async def myid_cmd(message: Message):
    await message.answer(
        f"Ваш Telegram ID:\n<code>{message.from_user.id}</code>",
        parse_mode="HTML",
    )
