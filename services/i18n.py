from services.storage import get_settings

TEXTS = {
    "ru": {
        "menu_settings": "⚙️ Настройки",
        "menu_length": "⏱ Длина",
        "menu_quality": "🎞 Качество",
        "menu_banner": "🎬 Баннер",
        "menu_watermark": "💧 Водяной знак",
        "menu_mirror": "🪞 Mirror",
        "menu_caption": "📝 Caption",
        "menu_subtitles": "💬 Субтитры",
        "menu_all": "📦 Все части",
        "menu_last": "🔁 Последние",
        "menu_language": "🌐 Язык",
        "menu_youtube": "▶️ YouTube",
        "menu_about": "ℹ️ О проекте",
        "settings": "⚙️ Настройки",
        "language": "Язык",
        "russian": "Русский",
        "english": "English",
        "watermark": "Водяной знак",
        "watermark_none": "не задан",
        "subtitles": "Субтитры",
        "subtitles_off": "выкл",
        "subtitles_source": "авто из источника",
        "subtitles_api": "AI API",
        "saved": "сохранено",
    },
    "en": {
        "menu_settings": "⚙️ Settings",
        "menu_length": "⏱ Length",
        "menu_quality": "🎞 Quality",
        "menu_banner": "🎬 Banner",
        "menu_watermark": "💧 Watermark",
        "menu_mirror": "🪞 Mirror",
        "menu_caption": "📝 Caption",
        "menu_subtitles": "💬 Subtitles",
        "menu_all": "📦 All parts",
        "menu_last": "🔁 Last",
        "menu_language": "🌐 Language",
        "menu_youtube": "▶️ YouTube",
        "menu_about": "ℹ️ About",
        "settings": "⚙️ Settings",
        "language": "Language",
        "russian": "Русский",
        "english": "English",
        "watermark": "Watermark",
        "watermark_none": "not set",
        "subtitles": "Subtitles",
        "subtitles_off": "off",
        "subtitles_source": "source auto-captions",
        "subtitles_api": "AI API",
        "saved": "saved",
    },
}


def lang(user_id: int) -> str:
    try:
        value = get_settings(user_id).get("language", "ru")
    except Exception:
        value = "ru"
    return value if value in TEXTS else "ru"


def t(user_id: int, key: str, **kwargs) -> str:
    language = lang(user_id)
    text = TEXTS[language].get(key, TEXTS["ru"].get(key, key))
    return text.format(**kwargs) if kwargs else text
