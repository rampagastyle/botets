# Video bot — нарезка + баннер CSDOG

Telegram-бот: скачивание (yt-dlp), вертикаль 9:16, нарезка 15/30/45/60 сек, вставка баннера по центру.

## Локальный запуск

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# нужен ffmpeg в PATH
echo BOT_TOKEN=... > .env
python main.py
```

## Команды

- Ссылка http(s) — скачать и обработать
- `/settings` — настройки
- `/clip` — длина куска
- `/banner` — как загрузить баннер
- Файл с подписью `баннер` — сохранить MP4 баннера
- `/mirror` — зеркало

Баннер CSDOG: https://t.me/csdogTikTok/62  
Правила: https://telegra.ph/Usloviya-bannerov-csdog-09-08

## Railway

1. Dockerfile уже есть (python + ffmpeg)
2. Variables: `BOT_TOKEN`, при необходимости `YTDLP_COOKIES`
3. Локальный бот выключить (один polling)

YouTube с IP облака часто требует cookies и всё равно может резать. RuTube/VK обычно стабильнее.

## TikTok drafts

Только через официальный Content Posting API (`video.upload` → inbox). Заглушка в `services/tiktok.py`.

## TikTok drafts

1. Create app: https://developers.tiktok.com
2. Product: Content Posting API, scope `video.upload`
3. OAuth → user `access_token`
4. In bot: `/settoken act.xxx`
5. After processing a video: `/todraft`

See `/tiktok` in the bot for steps.
