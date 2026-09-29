from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import is_admin
from services import whitelist as wl
from services.banners import list_banners, delete_banner

router = Router()


def _wl_text() -> str:
    ids = wl.list_ids()
    body = "\n".join(f"  <code>{i}</code>" for i in ids) if ids else "<i>пусто — открыт для всех</i>"
    return (
        "<b>Whitelist</b>\n"
        "────────────────────\n\n"
        f"{body}\n\n"
        "/allow ID — добавить\n"
        "/deny ID — удалить"
    )


@router.message(Command("whitelist", "wl"))
@router.message(F.text == "👥 Whitelist")
async def whitelist_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Только для админа.")
    await message.answer(_wl_text(), parse_mode="HTML")


@router.message(Command("allow", "adduser"))
async def allow_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Только для админа.")
    arg = message.text.partition(" ")[2].strip()
    if not arg.isdigit():
        return await message.answer("Пример: <code>/allow 123456789</code>", parse_mode="HTML")
    if wl.add(arg):
        await message.answer(f"✅ Добавлен: <code>{arg}</code>", parse_mode="HTML")
    else:
        await message.answer("Уже в списке.")


@router.message(Command("deny", "deluser"))
async def deny_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Только для админа.")
    arg = message.text.partition(" ")[2].strip()
    if not arg.isdigit():
        return await message.answer("Пример: <code>/deny 123456789</code>", parse_mode="HTML")
    if wl.remove(arg):
        await message.answer(f"🗑 Удалён: <code>{arg}</code>", parse_mode="HTML")
    else:
        await message.answer("Не найден или это админ.")


@router.message(Command("banners"))
@router.message(F.text == "🛠 Баннеры")
async def banners_list(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Только для админа.")
    rows = list_banners()
    if not rows:
        return await message.answer(
            "Баннеров нет.\nСоздать: <code>/createbanner</code>",
            parse_mode="HTML",
        )
    lines = ["<b>Баннеры на сервере</b>\n────────────────────\n"]
    for b in rows:
        lines.append(
            f"• <b>{b.get('name')}</b>\n"
            f"  id: <code>{b.get('id')}</code>\n"
            f"  правила: {b.get('rules_url') or '—'}\n"
        )
    lines.append("\nУдалить: <code>/delbanner ID</code>")
    await message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("delbanner"))
async def delbanner_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔️ Только для админа.")
    bid = message.text.partition(" ")[2].strip()
    if not bid:
        return await message.answer("Пример: <code>/delbanner abc123</code>", parse_mode="HTML")
    if delete_banner(bid):
        await message.answer(f"🗑 Баннер <code>{bid}</code> удалён.", parse_mode="HTML")
    else:
        await message.answer("Не найден.")
