from __future__ import annotations

import asyncio
import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.whitelist import is_allowed
from services.storage import get_settings, save_settings
from services.youtube import create_auth_url, is_connected, redirect_uri

router = Router()


def youtube_kb(user_id: int):
    s = get_settings(user_id)
    auto = bool(s.get('youtube_auto'))
    privacy = s.get('youtube_privacy', 'private')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='▶️ Auto upload: ON' if auto else '▶️ Auto upload: OFF', callback_data='yt:auto')],
        [InlineKeyboardButton(text=f'🔒 Private {"●" if privacy == "private" else ""}', callback_data='yt:privacy:private'),
         InlineKeyboardButton(text=f'🔗 Unlisted {"●" if privacy == "unlisted" else ""}', callback_data='yt:privacy:unlisted'),
         InlineKeyboardButton(text=f'🌍 Public {"●" if privacy == "public" else ""}', callback_data='yt:privacy:public')],
        [InlineKeyboardButton(text='🔑 Connect YouTube', callback_data='yt:connect')],
    ])


async def _youtube_text(user_id: int) -> str:
    s = get_settings(user_id)
    connected = is_connected(user_id)
    return (
        '▶️ <b>YouTube Shorts</b>\n\n'
        f'Подключение: <b>{"✅ подключён" if connected else "❌ не подключён"}</b>\n'
        f'Автозагрузка: <b>{"вкл" if s.get("youtube_auto") else "выкл"}</b>\n'
        f'Приватность: <b>{s.get("youtube_privacy", "private")}</b>\n\n'
        'Gemini отдельно анализирует каждый готовый клип и создаёт заголовок, описание, хэштеги и теги.\n'
        'По умолчанию YouTube использует <b>private</b>, чтобы перед публикацией у тебя оставался контроль.'
        f'\n\n🔗 OAuth callback:\n<code>{html.escape(redirect_uri())}</code>'
    )


@router.message(Command('youtube'))
@router.message(F.text.in_({'▶️ YouTube', '▶️ YouTube Shorts'}))
async def youtube_cmd(message: Message):
    if not is_allowed(message.from_user.id):
        return
    await message.answer(await _youtube_text(message.from_user.id), parse_mode='HTML', reply_markup=youtube_kb(message.from_user.id))


@router.callback_query(F.data == 'yt:menu')
async def youtube_menu_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id):
        return await call.answer('No access', show_alert=True)
    await call.answer()
    try:
        await call.message.edit_text(await _youtube_text(call.from_user.id), parse_mode='HTML', reply_markup=youtube_kb(call.from_user.id))
    except Exception:
        await call.message.answer(await _youtube_text(call.from_user.id), parse_mode='HTML', reply_markup=youtube_kb(call.from_user.id))


@router.callback_query(F.data == 'yt:auto')
async def youtube_auto_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id):
        return await call.answer('No access', show_alert=True)
    connected = is_connected(call.from_user.id)
    if not connected:
        return await call.answer('Сначала подключи YouTube', show_alert=True)
    current = bool(get_settings(call.from_user.id).get('youtube_auto'))
    save_settings(call.from_user.id, youtube_auto=not current)
    await call.answer('ON' if not current else 'OFF')
    await call.message.edit_text(await _youtube_text(call.from_user.id), parse_mode='HTML', reply_markup=youtube_kb(call.from_user.id))


@router.callback_query(F.data.startswith('yt:privacy:'))
async def youtube_privacy_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id):
        return await call.answer('No access', show_alert=True)
    privacy = call.data.split(':')[-1]
    if privacy not in {'private', 'unlisted', 'public'}:
        return await call.answer('Invalid privacy', show_alert=True)
    save_settings(call.from_user.id, youtube_privacy=privacy)
    await call.answer(privacy)
    await call.message.edit_text(await _youtube_text(call.from_user.id), parse_mode='HTML', reply_markup=youtube_kb(call.from_user.id))


@router.callback_query(F.data == 'yt:connect')
async def youtube_connect_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id):
        return await call.answer('No access', show_alert=True)
    try:
        url = await asyncio.to_thread(create_auth_url, call.from_user.id)
    except Exception as e:
        return await call.answer(str(e)[:180], show_alert=True)
    await call.answer('Открой ссылку')
    await call.message.answer(
        '🔐 <b>Подключение YouTube</b>\n\n'
        '1. Открой ссылку.\n2. Выбери свой Google-аккаунт.\n3. Разреши загрузку видео.\n4. После возврата на страницу авторизация сохранится.\n\n'
        f'<a href="{html.escape(url, quote=True)}">Открыть Google OAuth</a>', parse_mode='HTML', disable_web_page_preview=True
    )
