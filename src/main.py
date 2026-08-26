import asyncio
import logging
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from src.config import settings
from src.bot.handlers import router as main_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def start_local_static_server():
    """Lightweight web server to serve local media files over HTTP."""
    os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)
    app = web.Application()
    app.router.add_static("/", settings.LOCAL_STORAGE_DIR, show_index=False)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.LOCAL_SERVER_HOST, settings.LOCAL_SERVER_PORT)
    await site.start()
    logger.info(
        f"Local static media server started at http://{settings.LOCAL_SERVER_HOST}:{settings.LOCAL_SERVER_PORT}/ "
        f"serving directory: {settings.LOCAL_STORAGE_DIR}"
    )


async def main():
    logger.info("Starting Instagram AutoPosting Bot...")
    
    # Start optional local static web server
    if settings.STORAGE_TYPE.lower() == "local" and settings.LOCAL_SERVER_ENABLED:
        await start_local_static_server()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="Markdown")
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(main_router)

    # Delete existing webhooks if any and start polling
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot is ready and listening for incoming messages...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
