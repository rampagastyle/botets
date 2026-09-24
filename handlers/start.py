from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from config import is_admin
from services.whitelist import is_allowed
from services.i18n import t, lang

router = Router()
BOT_NAME = 'VideoProcessing'
BOT_VERSION = 'v15'
SUPPORT = '@classismfact'


def main_kb(user_id=None):
    uid = user_id or 0
    rows = [
        [KeyboardButton(text=t(uid, 'menu_settings')), KeyboardButton(text=t(uid, 'menu_length'))],
        [KeyboardButton(text=t(uid, 'menu_quality')), KeyboardButton(text=t(uid, 'menu_banner'))],
        [KeyboardButton(text=t(uid, 'menu_watermark')), KeyboardButton(text=t(uid, 'menu_subtitles'))],
        [KeyboardButton(text=t(uid, 'menu_mirror')), KeyboardButton(text=t(uid, 'menu_caption'))],
        [KeyboardButton(text=t(uid, 'menu_all')), KeyboardButton(text=t(uid, 'menu_last'))],
        [KeyboardButton(text=t(uid, 'menu_language')), KeyboardButton(text=t(uid, 'menu_youtube'))],
        [KeyboardButton(text=t(uid, 'menu_about'))],
    ]
    if user_id and is_admin(user_id):
        rows.append([KeyboardButton(text='👥 Whitelist')])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def denied_text(user_id):
    return (f'━━━━━━━━━━━━━━━━━━━━\n🔒  <b>{BOT_NAME}</b> · {BOT_VERSION}\n'
            f'━━━━━━━━━━━━━━━━━━━━\n\nДоступ только по whitelist.\n\n'
            f'Ваш ID: <code>{user_id}</code>\n\nТехподдержка: {SUPPORT}\n━━━━━━━━━━━━━━━━━━━━')


def about_text(user_id):
    en = lang(user_id) == 'en'
    if en:
        return (
            f'━━━━━━━━━━━━━━━━━━━━\n🎬 <b>{BOT_NAME}</b> · {BOT_VERSION}\n━━━━━━━━━━━━━━━━━━━━\n\n'
            '<b>What it does</b>\nCuts long videos into vertical 9:16 clips, adds a soft blurred background, optional banner, watermark and subtitles.\n\n'
            '<b>Low-load design</b>\n• one processing job at a time\n• FFmpeg uses one thread\n• source captions are preferred over local speech recognition\n• watermark and subtitles are burned during the same encode\n• temporary files are deleted as soon as possible\n• download quality is capped at 1080p\n\n'
            '<b>Commands</b>\n/youtube — connect and auto-upload Shorts\n/gemini on|off — AI video analysis\n/quality 480|720|1080\n/clip 15|30|45|60\n/watermark text — set watermark\n/watermark off — remove watermark\n/subtitles off — disable\n/subtitles source — use source captions\n/subtitles ai — optional AI transcription via API\n/language ru|en — interface language\n/banner — banner instructions\n/mirror — mirror\n/caption text — Telegram caption\n/sendall — send all parts\n/last — resend last parts\n/cleanup — clean temporary files\n\nSupport: ' + SUPPORT + '\n━━━━━━━━━━━━━━━━━━━━'
        )
    return (
        f'━━━━━━━━━━━━━━━━━━━━\n🎬 <b>{BOT_NAME}</b> · {BOT_VERSION}\n━━━━━━━━━━━━━━━━━━━━\n\n'
        '<b>Что делает</b>\nНарезает длинные ролики в вертикальные 9:16 клипы, добавляет мягкий blur-фон, баннер, водяной знак и субтитры.\n\n'
        '<b>Система с низкой нагрузкой</b>\n• только одна обработка одновременно\n• FFmpeg использует один поток\n• сначала используются субтитры источника вместо локального распознавания\n• водяной знак и субтитры встраиваются в тот же encode\n• временные файлы удаляются сразу после этапа\n• скачивание ограничено 1080p\n\n'
        '<b>Команды</b>\n/youtube — подключить YouTube и автозагрузку Shorts\n/gemini on|off — AI-анализ видео\n/quality 480|720|1080\n/clip 15|30|45|60\n/watermark текст — установить водяной знак\n/watermark off — убрать водяной знак\n/subtitles off — выключить\n/subtitles source — субтитры из источника\n/subtitles ai — опциональная AI-транскрипция через API\n/language ru|en — язык интерфейса\n/banner — инструкция по баннеру\n/mirror — зеркало\n/caption текст — подпись Telegram\n/sendall — отправлять все части\n/last — последние части\n/cleanup — очистка\n\nПоддержка: ' + SUPPORT + '\n━━━━━━━━━━━━━━━━━━━━'
    )


@router.message(Command('start', 'help'))
async def start(message: Message):
    uid = message.from_user.id
    if not is_allowed(uid):
        return await message.answer(denied_text(uid), parse_mode='HTML')
    await message.answer(
        f'━━━━━━━━━━━━━━━━━━━━\n🎬 <b>{BOT_NAME}</b> · {BOT_VERSION}\n━━━━━━━━━━━━━━━━━━━━\n\n'
        + ('Vertical clips · 9:16 · blur · up to 1080p' if lang(uid) == 'en' else 'Нарезка видео · 9:16 · blur-фон · до 1080p')
        + '\n\n' + ('Send a video link or use the buttons below.' if lang(uid) == 'en' else 'Отправьте ссылку на видео или используйте кнопки ниже.')
        + '\n━━━━━━━━━━━━━━━━━━━━',
        parse_mode='HTML', reply_markup=main_kb(uid)
    )


@router.message(Command('about', 'info', 'project'))
@router.message(F.text.in_({'ℹ️ О проекте', 'ℹ️ About'}))
async def about_cmd(message: Message):
    uid = message.from_user.id
    if not is_allowed(uid):
        return await message.answer(denied_text(uid), parse_mode='HTML')
    await message.answer(about_text(uid), parse_mode='HTML', disable_web_page_preview=True)
