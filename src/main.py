import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from src.config import settings
from src.bot.handlers import router as main_router
from src.services.media_server import start_secure_media_server
from src.services.cleanup_service import run_cleanup_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting Instagram AutoPosting Bot...")
    
    server_runner = None
    cleanup_task = None

    # 1. Start optional secure local static media web server
    if settings.STORAGE_TYPE.lower() == "local" and settings.LOCAL_SERVER_ENABLED:
        server_runner = await start_secure_media_server()

    # 2. Start periodic background media cleanup worker (if enabled)
    if settings.MEDIA_CLEANUP_ENABLED:
        cleanup_task = asyncio.create_task(run_cleanup_worker())

    # 3. Initialize Telegram Bot and Dispatcher
    cleaned_token = (settings.BOT_TOKEN or "").strip().strip("'\"")
    if not cleaned_token:
        logger.critical("BOT_TOKEN is missing or empty in .env! Please set BOT_TOKEN.")
        sys.exit(1)

    bot = Bot(
        token=cleaned_token,
        default=DefaultBotProperties(parse_mode="Markdown")
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(main_router)

    try:
        # Delete existing webhooks if any and start polling
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot is ready and listening for incoming messages...")
        await dp.start_polling(bot)
    finally:
        # Graceful shutdown of background tasks
        if cleanup_task and not cleanup_task.done():
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        
        if server_runner:
            await server_runner.cleanup()
            logger.info("Local media server stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
