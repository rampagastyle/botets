# Telegram Video Bot — локальная версия без базы данных

Бот хранит настройки и данные локально в обычных JSONL-текстовых файлах:
`data/users.txt`, `data/settings.txt`, `data/accounts.txt`.
SQLite/PostgreSQL/Redis/Celery не используются.

## 1. Что установить

Windows:
1. Python 3.11+.
2. FFmpeg и FFprobe, добавленные в PATH.
3. В папке проекта:
   `python -m venv .venv`
   `.venv\Scripts\activate`
   `pip install -r requirements.txt`

Linux:
`sudo apt install ffmpeg`
`python3 -m venv .venv`
`source .venv/bin/activate`
`pip install -r requirements.txt`

## 2. Telegram

Создайте бота через BotFather, получите токен и скопируйте `.env.example` в `.env`.
Укажите:
BOT_TOKEN=...

Для ограничения доступа:
WHITELIST=123456789,987654321

Пустой WHITELIST означает, что whitelist выключен.

## 3. YouTube Shorts

1. Откройте Google Cloud Console.
2. Создайте проект.
3. Включите YouTube Data API v3.
4. Настройте OAuth consent screen.
5. Создайте OAuth Client ID типа Desktop App.
6. Скачайте JSON и сохраните как:
   `credentials/client_secret.json`
7. Запустите бота и используйте обработку/загрузку через модуль YouTube.
При первом обращении откроется окно OAuth. После авторизации токен сохраняется
локально как `credentials/youtube_token.json`.

Для реального Shorts важно соблюдать актуальные требования YouTube API и
ограничения аккаунта. Видео в коде по умолчанию создаётся приватным — смените
privacyStatus только после проверки своего сценария.

## 4. TikTok

Неофициальная автоматизация через Selenium/TikTokApi может ломаться из-за
изменений сайта и антибот-защиты. В проекте оставлен безопасный адаптер
`services/tiktok.py`.

Для публикации используйте официальный TikTok for Developers и Content Posting
API, получите необходимые разрешения для своего приложения и OAuth-токены.
Конкретные разрешения и доступность функций зависят от текущих правил TikTok.

## 5. Водяной знак

Сейчас процессор принимает путь к PNG/GIF. Для полноценной команды `/watermark`
нужно прислать боту файл и сохранить его в `data/<user_id>/watermark.*`.
Команду можно расширить без изменения формата хранения.

## 6. Важное про лимит Telegram

Переменная MAX_FILE_SIZE ограничивает локальную обработку до 2 GB, но фактические
лимиты Telegram Bot API и хостинга могут быть ниже/выше в зависимости от способа
получения файла. Бот скачивает исходник напрямую через yt-dlp, поэтому для ссылок
лимит Telegram на отправку исходника не применяется.

## 7. Запуск

`python main.py`

Логи:
`logs/bot.log`

Данные:
`data/`

## 8. Архитектура

- main.py — запуск
- handlers/ — Telegram-команды
- services/downloader.py — yt-dlp
- services/processor.py — FFmpeg
- services/youtube.py — OAuth + YouTube Data API
- services/tiktok.py — официальный API-адаптер
- services/storage.py — локальные JSONL-файлы

## Ограничения текущего шаблона

- Автопубликация YouTube/TikTok требует отдельных OAuth-настроек.
- TikTok намеренно не использует обходы антибот-защиты.
- `/watermark` пока является подготовленной архитектурой; обработчик загрузки
  можно добавить отдельно.
- Прогресс yt-dlp/FFmpeg можно подключить через callback и редактирование
  Telegram-сообщения.
- Для production рекомендуется отдельный worker/очередь, но здесь это намеренно
  не используется, чтобы проект оставался простым и полностью локальным.
"# botets" 
