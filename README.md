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
PUBLIC_BASE_URL=https://botets-production.up.railway.app
# Не задавай YOUTUBE_REDIRECT_URI, если он содержит старый адрес.
OAUTH_STATE_SECRET=long-random-secret
YOUTUBE_CLIENT_SECRET_JSON={PASTE_THE_CONTENT_OF_client_secret.json_HERE}
```

In Google Cloud Console, create a **Web application** OAuth client and add:

```text
https://botets-production.up.railway.app/oauth/youtube/callback
```

to Authorized redirect URIs. Enable YouTube Data API v3. Then open `/youtube` in the bot and connect the channel.

The bot defaults to `private` uploads. You can switch to `unlisted` or `public` in the YouTube menu.

### YouTube download reliability
The Docker image includes Node.js because current YouTube delivery can require a JavaScript runtime for player challenges. yt-dlp downloads only the selected quality, uses one fragment at a time, and lets current yt-dlp choose its default YouTube client before trying two lightweight fallbacks. Optional `YTDLP_COOKIES` can provide a fresh Netscape-format cookies.txt when YouTube blocks the Railway IP. Use cookies only for videos your account is allowed to access.

Only download/re-upload videos you have permission to use.


### Если появляется «срок действия состояния OAuth истёк»

В этой версии OAuth state не хранится только в оперативной памяти процесса. Он подписывается сервером, поэтому перезапуск Railway между открытием Google и callback больше не ломает авторизацию. Срок действия state — 15 минут. Если страница Google была открыта дольше 15 минут, просто нажмите Connect YouTube ещё раз.

### Настройка именно для этого Railway проекта

Ваш Railway-домен: `botets-production.up.railway.app`

`PUBLIC_BASE_URL`:
```env
PUBLIC_BASE_URL=https://botets-production.up.railway.app
```

Authorized redirect URI в Google Cloud должен быть **ровно**:
```text
https://botets-production.up.railway.app/oauth/youtube/callback
```

В Railway нельзя оставлять `YOUTUBE_CLIENT_SECRET=JSON_OT_Google_OAuth` или другой текст-заглушку. Нужно вставить содержимое файла `client_secret.json`, который скачан из Google Cloud, в переменную `YOUTUBE_CLIENT_SECRET_JSON`. Нужен OAuth client типа **Web application**.


### Важно: redirect_uri_mismatch

Для этого проекта callback должен быть ровно:
`https://botets-production.up.railway.app/oauth/youtube/callback`

В Railway задай `PUBLIC_BASE_URL=https://botets-production.up.railway.app`. Если у тебя уже есть `YOUTUBE_REDIRECT_URI` со старым адресом, удали эту переменную. В Google Cloud в Authorized redirect URIs оставь ровно тот же callback. Бот показывает фактический callback в меню `/youtube`.
