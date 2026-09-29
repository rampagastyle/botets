# VideoProcessing v15

Нарезка видео 9:16 + баннеры + Gemini-метаданные (title / description / хештеги YT Shorts и TikTok).

## Убрано
- Субтитры
- Водяные знаки
- Автозагрузка YouTube

## Railway Variables
- `BOT_TOKEN` — обязательно
- `ADMIN_IDS` — Telegram ID админа
- `WHITELIST` — опционально
- `GEMINI_API_KEY` — для AI-описаний (бесплатный tier Google AI Studio)
- `GEMINI_MODEL` — по умолчанию `gemini-2.0-flash`
- `MAX_CONCURRENT_JOBS` — по умолчанию 3 (под ~8GB RAM)
- `MAX_FILE_SIZE` — по умолчанию 2GiB

## Админ-баннеры
`/createbanner` → название → ссылка на правила → AI-резюме → файл MP4.
Баннеры общие для всех пользователей (`data/banners/`).

## Volume
Подключите volume на `/app/data`, чтобы баннеры и whitelist сохранялись.
