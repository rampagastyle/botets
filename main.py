import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN
from handlers.start import router as start_router
from handlers.settings import router as settings_router
from handlers.video import router as video_router
from handlers.upload import router as upload_router
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
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
