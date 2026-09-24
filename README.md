# VideoProcessing v15

Telegram-бот для нарезки видео в вертикальные 9:16 Shorts.

## Возможности

- 480p / 720p / 1080p, максимум 1080×1920.
- Мягкий blur вместо чёрных полей.
- Полупрозрачный водяной знак внутри основного видео, а не на blur-зоне.
- Source-субтитры без локального AI.
- AI-субтитры через Gemini без локальной модели.
- Русский / English интерфейс.
- Gemini анализирует каждый отдельный клип и создаёт отдельные title, description, 15–25 релевантных hashtags и YouTube tags.
- Один Gemini-запрос на клип: при AI-субтитрах транскрипт и metadata возвращаются вместе.
- Автоматическая загрузка готовых Shorts в подключённый YouTube-канал.
- Приватность YouTube: private / unlisted / public.
- Один тяжёлый job одновременно.
- FFmpeg — один поток.
- Один клип кодируется один раз: blur + banner + watermark + subtitles.
- Временные файлы удаляются сразу после этапа.
- yt-dlp ограничивает загрузку выбранным качеством и использует один fragment за раз.

## Команды

- `/start`, `/help`
- `/settings`
- `/gemini on|off`
- `/youtube`
- `/quality 480|720|1080`
- `/clip 15|30|45|60`
- `/watermark текст`
- `/watermark off`
- `/subtitles off|source|ai`
- `/language ru|en`
- `/banner`
- `/mirror`
- `/caption текст`
- `/sendall`
- `/last`
- `/cleanup`

## v15: Gemini + YouTube Shorts

### Gemini
Set in Railway:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Gemini analyzes each generated clip separately and creates a title, description, 15-25 relevant hashtags and YouTube keyword tags. If AI subtitles are enabled, the same request also returns timestamped speech cues, so the bot does not make a second AI request.

`gemini-3.5-flash-lite` supports text, image, video and audio input and has a free tier for input/output tokens according to Google's current pricing documentation. Free-tier rate limits still apply.

### YouTube automatic upload
The bot uses YouTube Data API OAuth and uploads each processed clip sequentially. It does not keep several upload buffers in RAM at once.

Railway variables:

```env
PUBLIC_BASE_URL=https://YOUR-RAILWAY-DOMAIN
YOUTUBE_CLIENT_SECRET={PASTE_YOUR_WEB_OAUTH_CLIENT_JSON_HERE}
```

In Google Cloud Console, create a **Web application** OAuth client and add:

```text
https://YOUR-RAILWAY-DOMAIN/oauth/youtube/callback
```

to Authorized redirect URIs. Enable YouTube Data API v3. Then open `/youtube` in the bot and connect the channel.

The bot defaults to `private` uploads. You can switch to `unlisted` or `public` in the YouTube menu.

### YouTube download reliability
The Docker image includes Node.js because current YouTube delivery can require a JavaScript runtime for player challenges. yt-dlp is configured to download only the selected quality, use one fragment at a time, and optionally use `credentials/cookies.txt` when provided. If YouTube changes its delivery, update `yt-dlp` before changing the rest of the bot.

Only download/re-upload videos you have permission to use.
