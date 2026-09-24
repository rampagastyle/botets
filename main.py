import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import web

from config import BOT_TOKEN
from handlers.start import router as start_router
from handlers.settings import router as settings_router
from handlers.video import router as video_router
from handlers.upload import router as upload_router
from handlers.admin import router as admin_router
from handlers.youtube import router as youtube_router
from services.youtube import handle_callback
from services.storage import ensure_storage


def ensure_runtime_files():
    Path("logs").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    cred = Path("credentials")
    cred.mkdir(exist_ok=True)

    mapping = {
        "YOUTUBE_CLIENT_SECRET": cred / "client_secret.json",
        "YOUTUBE_TOKEN": cred / "youtube_token.json",
        "YTDLP_COOKIES": cred / "cookies.txt",
    }
    for env_name, path in mapping.items():
        value = os.getenv(env_name)
        if value:
            path.write_text(value, encoding="utf-8")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


async def main():
    ensure_runtime_files()
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан (переменная окружения или .env)")
    ensure_storage()

    session = AiohttpSession(timeout=600)
    bot = Bot(BOT_TOKEN, session=session)
    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(settings_router)
    dp.include_router(video_router)
    dp.include_router(upload_router)
    dp.include_router(admin_router)
    dp.include_router(youtube_router)
    async def youtube_callback(request):
        code = request.query.get("code", "")
        state = request.query.get("state", "")
        error = request.query.get("error")
        if error:
            return web.Response(text=f"YouTube authorization cancelled: {error}", content_type="text/plain")
        try:
            user_id = await asyncio.to_thread(handle_callback, code, state)
            return web.Response(
                text=f"YouTube connected for Telegram user {user_id}. You can close this page and return to the bot.",
                content_type="text/plain",
            )
        except Exception as exc:
            return web.Response(text=f"Authorization error: {exc}", content_type="text/plain", status=400)

    web_app = web.Application()
    web_app.router.add_get("/oauth/youtube/callback", youtube_callback)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "8080")))
    await site.start()
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
