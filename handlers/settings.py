from pathlib import Path

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import WORK_DIR, is_admin
from services.whitelist import is_allowed
from services.storage import get_settings, save_settings, DEFAULT_CAPTION, QUALITY_OPTIONS
from services.tiktok import set_tiktok_token, get_tiktok_token
from services.i18n import t, lang

router = Router()
CLIP_OPTIONS = (15, 30, 45, 60)


def settings_kb(user_id: int):
    s = get_settings(user_id)
    has = bool(s.get('banner') and Path(str(s.get('banner'))).exists())
    en = bool(s.get('banner_enabled')) and has
    ban_btn = '🎬 Баннер: вкл' if en else '🎬 Баннер: выкл'
    if not has:
        ban_btn = '🎬 Баннер: нет файла'
    clip = int(s.get('clip_seconds') or 15)
    quality = int(s.get('quality') or 480)
    rows = [
        [InlineKeyboardButton(text=ban_btn, callback_data='banner:toggle')],
        [InlineKeyboardButton(text=f"{'●' if clip == n else '·'} {n}с", callback_data=f'clip:{n}') for n in CLIP_OPTIONS],
        [InlineKeyboardButton(text=f"{'●' if quality == q else '·'} {q}p", callback_data=f'quality:{q}') for q in QUALITY_OPTIONS],
        [InlineKeyboardButton(text='🇷🇺 RU', callback_data='lang:ru'), InlineKeyboardButton(text='🇬🇧 EN', callback_data='lang:en')],
        [InlineKeyboardButton(text='💬 Subtitles', callback_data='subtitles:menu')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def clip_kb(current=15):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{'●' if n == current else '·'} {n}с", callback_data=f'clip:{n}') for n in CLIP_OPTIONS]])


def quality_kb(current=480):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{'●' if q == current else '·'} {q}p", callback_data=f'quality:{q}') for q in QUALITY_OPTIONS]])


def language_kb(current='ru'):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{'●' if current == 'ru' else '·'} Русский", callback_data='lang:ru'), InlineKeyboardButton(text=f"{'●' if current == 'en' else '·'} English", callback_data='lang:en')]])


def subtitles_kb(current='source'):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{'●' if current == 'off' else '·'} выкл", callback_data='subtitles:off'), InlineKeyboardButton(text=f"{'●' if current == 'source' else '·'} source", callback_data='subtitles:source'), InlineKeyboardButton(text=f"{'●' if current == 'ai' else '·'} AI", callback_data='subtitles:ai')]])


def _settings_text(user_id: int):
    s = get_settings(user_id)
    tt = get_tiktok_token(user_id)
    has_ban = bool(s.get('banner') and Path(s.get('banner')).exists())
    ban = 'вкл' if bool(s.get('banner_enabled')) and has_ban else ('выкл' if has_ban else 'не загружен')
    mir = 'вкл' if s.get('mirror') else 'выкл'
    allp = 'вкл' if s.get('send_all') else 'выкл'
    tok = 'да' if tt and tt.get('access_token') else 'нет'
    cap = (s.get('caption') or DEFAULT_CAPTION).replace('<', '').replace('>', '')[:100]
    quality = int(s.get('quality') or 480)
    if quality not in QUALITY_OPTIONS: quality = 480
    sub = s.get('subtitles', 'source')
    wm = s.get('watermark') or t(user_id, 'watermark_none')
    if len(wm) > 50: wm = wm[:50] + '…'
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n{t(user_id, 'settings')} · VideoProcessing v14\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱  Длина: <b>{s.get('clip_seconds', 15)} сек</b>\n"
        f"🎞  Качество: <b>{quality}p</b>\n"
        f"💧  Водяной знак: <b>{wm}</b>\n"
        f"💬  Субтитры: <b>{sub}</b>\n"
        f"🌐  {t(user_id, 'language')}: <b>{'Русский' if lang(user_id) == 'ru' else 'English'}</b>\n"
        f"🪞  Mirror: <b>{mir}</b>\n🎬  Баннер: <b>{ban}</b>\n📦  Слать все: <b>{allp}</b>\n🎵  TikTok token: <b>{tok}</b>\n\n"
        f"📝 Caption\n<code>{cap}</code>\n\n"
        "Максимум: <b>1080×1920</b>. Один FFmpeg-процесс за раз, 1 поток.\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


@router.message(Command('settings'))
@router.message(F.text.in_({'⚙️ Настройки', '⚙️ Settings'}))
async def settings_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    await message.answer(_settings_text(message.from_user.id), parse_mode='HTML', reply_markup=settings_kb(message.from_user.id))


@router.message(Command('language'))
@router.message(F.text.in_({'🌐 Язык', '🌐 Language'}))
async def language_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    arg = (message.text or '').partition(' ')[2].strip().lower()
    if arg in ('ru', 'en'):
        save_settings(message.from_user.id, language=arg)
        from handlers.start import main_kb
        await message.answer('✅ Язык: Русский' if arg == 'ru' else '✅ Language: English', reply_markup=main_kb(message.from_user.id))
        return
    await message.answer('🌐 Выберите язык / Choose language:', reply_markup=language_kb(lang(message.from_user.id)))


@router.callback_query(F.data.startswith('lang:'))
async def language_cb(call: CallbackQuery):
    value = call.data.split(':', 1)[1]
    if value not in ('ru', 'en'): return await call.answer('Error', show_alert=True)
    save_settings(call.from_user.id, language=value)
    await call.answer('Русский' if value == 'ru' else 'English')
    from handlers.start import main_kb
    try:
        await call.message.edit_text(_settings_text(call.from_user.id), parse_mode='HTML', reply_markup=settings_kb(call.from_user.id))
        await call.message.answer('Главное меню обновлено.' if value == 'ru' else 'Main menu updated.', reply_markup=main_kb(call.from_user.id))
    except Exception: pass


@router.message(Command('watermark'))
@router.message(F.text.in_({'💧 Водяной знак', '💧 Watermark'}))
async def watermark_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    arg = (message.text or '').partition(' ')[2].strip()
    if not arg:
        current = get_settings(message.from_user.id).get('watermark') or t(message.from_user.id, 'watermark_none')
        return await message.answer(f"💧 {t(message.from_user.id, 'watermark')}: <b>{current}</b>\n\n/watermark ваш_текст\n/watermark off", parse_mode='HTML')
    if arg.lower() in ('off', 'none', 'выкл', 'нет'):
        save_settings(message.from_user.id, watermark='')
        return await message.answer('✅ Водяной знак выключен.')
    arg = arg[:80]
    save_settings(message.from_user.id, watermark=arg)
    await message.answer(f'✅ Водяной знак: <b>{arg}</b>\nОн будет снизу по центру.', parse_mode='HTML')


@router.message(Command('subtitles'))
@router.message(F.text.in_({'💬 Субтитры', '💬 Subtitles'}))
async def subtitles_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    arg = (message.text or '').partition(' ')[2].strip().lower()
    if arg in ('off', 'source', 'ai'):
        if arg == 'ai' and not __import__('os').getenv('OPENAI_API_KEY'):
            return await message.answer('⚠️ Для AI-субтитров нужен OPENAI_API_KEY. Source-субтитры работают без него.')
        save_settings(message.from_user.id, subtitles=arg)
        return await message.answer(f'✅ Subtitles: <b>{arg}</b>', parse_mode='HTML')
    current = get_settings(message.from_user.id).get('subtitles', 'source')
    await message.answer('💬 Режим субтитров / Subtitle mode:', reply_markup=subtitles_kb(current))


@router.callback_query(F.data.startswith('subtitles:'))
async def subtitles_cb(call: CallbackQuery):
    mode = call.data.split(':', 1)[1]
    if mode == 'menu':
        return await call.message.answer('💬 Режим субтитров:', reply_markup=subtitles_kb(get_settings(call.from_user.id).get('subtitles', 'source')))
    if mode == 'ai' and not __import__('os').getenv('OPENAI_API_KEY'):
        return await call.answer('Нужен OPENAI_API_KEY', show_alert=True)
    if mode not in ('off', 'source', 'ai'): return await call.answer('Error', show_alert=True)
    save_settings(call.from_user.id, subtitles=mode)
    await call.answer(mode)
    try: await call.message.edit_text(_settings_text(call.from_user.id), parse_mode='HTML', reply_markup=settings_kb(call.from_user.id))
    except Exception: pass


@router.callback_query(F.data.startswith('quality:'))
async def quality_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id): return await call.answer('Нет доступа', show_alert=True)
    q = int(call.data.split(':')[1])
    if q not in QUALITY_OPTIONS: return await call.answer('Недоступное качество', show_alert=True)
    save_settings(call.from_user.id, quality=q)
    await call.answer(f'{q}p')
    try: await call.message.edit_text(_settings_text(call.from_user.id), parse_mode='HTML', reply_markup=settings_kb(call.from_user.id))
    except Exception: pass


@router.callback_query(F.data == 'banner:toggle')
async def banner_toggle_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id): return await call.answer('Нет доступа', show_alert=True)
    s = get_settings(call.from_user.id)
    has = bool(s.get('banner') and Path(str(s.get('banner'))).exists())
    if not has: return await call.answer('Сначала загрузите баннер', show_alert=True)
    new = not bool(s.get('banner_enabled'))
    save_settings(call.from_user.id, banner_enabled=new)
    await call.answer(f'Баннер: {"вкл" if new else "выкл"}')
    try: await call.message.edit_text(_settings_text(call.from_user.id), parse_mode='HTML', reply_markup=settings_kb(call.from_user.id))
    except Exception: pass


@router.message(Command('quality'))
@router.message(F.text.in_({'🎞 Качество', '🎞 Quality'}))
async def quality_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    arg = (message.text or '').partition(' ')[2].strip()
    if arg.isdigit() and int(arg) in QUALITY_OPTIONS:
        save_settings(message.from_user.id, quality=int(arg))
        return await message.answer(f'✅ Quality: <b>{arg}p</b>', parse_mode='HTML')
    current = int(get_settings(message.from_user.id).get('quality') or 480)
    await message.answer('🎞 Выберите качество:', reply_markup=quality_kb(current))


@router.message(Command('clip'))
@router.message(F.text.in_({'⏱ Длина', '⏱ Length'}))
async def clip_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    arg = (message.text or '').partition(' ')[2].strip()
    if arg.isdigit() and int(arg) in CLIP_OPTIONS:
        save_settings(message.from_user.id, clip_seconds=int(arg))
        return await message.answer(f'✅ Длина: <b>{arg} сек</b>', parse_mode='HTML')
    s = get_settings(message.from_user.id)
    await message.answer('⏱ Длина одного куска:', reply_markup=clip_kb(int(s.get('clip_seconds') or 15)))


@router.callback_query(F.data.startswith('clip:'))
async def clip_cb(call: CallbackQuery):
    if not is_allowed(call.from_user.id): return await call.answer('Нет доступа', show_alert=True)
    sec = int(call.data.split(':')[1])
    if sec not in CLIP_OPTIONS: return await call.answer('Недопустимая длина', show_alert=True)
    save_settings(call.from_user.id, clip_seconds=sec)
    await call.answer(f'{sec} сек')
    try: await call.message.edit_text(_settings_text(call.from_user.id), parse_mode='HTML', reply_markup=settings_kb(call.from_user.id))
    except Exception: pass


@router.message(Command('banner'))
@router.message(F.text.in_({'🎬 Баннер', '🎬 Banner'}))
async def banner_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    await message.answer('🎬 Отправьте видео с подписью <code>баннер</code> / <code>banner</code>.', parse_mode='HTML')


@router.message(F.video | F.document)
async def banner_file(message: Message):
    if not is_allowed(message.from_user.id): return
    caption = (message.caption or '').lower().strip()
    if 'баннер' not in caption and 'banner' not in caption: return
    file = message.video or message.document
    if message.document and not (message.document.mime_type or '').startswith('video'):
        return await message.answer('⚠️ Нужен видеофайл (MP4/MOV).')
    dest_dir = WORK_DIR / str(message.from_user.id) / 'banner'
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / 'banner.mp4'
    await message.bot.download(file, destination=dest)
    save_settings(message.from_user.id, banner=str(dest), banner_enabled=True)
    await message.answer('✅ Баннер сохранён и включён. Вставка около 30 сек.')


@router.message(Command('mirror'))
@router.message(F.text == '🪞 Mirror')
async def mirror_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    s = get_settings(message.from_user.id); new = not s.get('mirror', False)
    save_settings(message.from_user.id, mirror=new)
    await message.answer(f'Mirror: <b>{"вкл" if new else "выкл"}</b>', parse_mode='HTML')


@router.message(Command('sendall'))
@router.message(F.text.in_({'📦 Все части', '📦 All parts'}))
async def sendall_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    s = get_settings(message.from_user.id); new = not s.get('send_all', False)
    save_settings(message.from_user.id, send_all=new)
    await message.answer(f'📦 Send all: <b>{"on" if new else "off"}</b>' if lang(message.from_user.id) == 'en' else f'📦 Слать все: <b>{"вкл" if new else "выкл"}</b>', parse_mode='HTML')


@router.message(Command('caption'))
@router.message(F.text.in_({'📝 Caption'}))
async def caption_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    arg = '' if message.text and message.text.startswith('📝') else ((message.text or '').partition(' ')[2].strip())
    if not arg:
        s = get_settings(message.from_user.id)
        return await message.answer(f"📝 Caption:\n<code>{s.get('caption') or DEFAULT_CAPTION}</code>\n\n/caption текст\n/caption reset", parse_mode='HTML')
    if arg == 'reset': save_settings(message.from_user.id, caption=DEFAULT_CAPTION); return await message.answer('✅ Caption reset.')
    save_settings(message.from_user.id, caption=arg)
    await message.answer(f'✅ Caption:\n<code>{arg}</code>', parse_mode='HTML')


@router.message(F.text == '👥 Whitelist')
async def wl_btn(message: Message):
    if not is_admin(message.from_user.id): return await message.answer('⛔️ Только для админа.')
    from handlers.admin import whitelist_cmd
    await whitelist_cmd(message)


@router.message(Command('tiktok'))
async def tiktok_help(message: Message):
    if not is_allowed(message.from_user.id): return
    tt = get_tiktok_token(message.from_user.id)
    status = 'подключён' if tt and tt.get('access_token') else 'нет'
    await message.answer(f'🎵 TikTok · {status}\n/settoken act.xxx\n/todraft')


@router.message(Command('settoken'))
async def settoken_cmd(message: Message):
    if not is_allowed(message.from_user.id): return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2: return await message.answer('Пример: /settoken act.xxxxx')
    set_tiktok_token(message.from_user.id, parts[1].strip(), parts[2].strip() if len(parts) > 2 else '')
    try: await message.delete()
    except Exception: pass
    await message.answer('✅ TikTok token сохранён.')
