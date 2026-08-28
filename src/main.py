import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from src.config import settings
from src.communication.telegram import (
    create_telegram_bot_and_dispatcher,
    setup_bot_commands,
)
from src.communication.api_server import start_communication_api_server
from src.business_logic.storage import run_cleanup_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting MemoryNMore Service...")
    
    server_runner = None
    cleanup_task = None

    # 1. Start Communication API & Media Server (exposes AI Engine & Business Logic for WhatsApp / Web)
    if settings.LOCAL_SERVER_ENABLED or settings.WHATSAPP_ENABLED or settings.STORAGE_TYPE.lower() == "local":
        server_runner = await start_communication_api_server()

    # 2. Start periodic background media cleanup worker (Business Logic / Storage)
    if settings.MEDIA_CLEANUP_ENABLED:
        cleanup_task = asyncio.create_task(run_cleanup_worker())

    # 3. Validate required configuration for the active mode
    missing_configs = settings.validate_required_config()
    if missing_configs:
        logger.critical(
            f"Missing required configuration for active STORAGE_TYPE='{settings.STORAGE_TYPE}': "
            f"{', '.join(missing_configs)}. "
            "Please provide them via Docker environment variables or in ./config/.env"
        )
        sys.exit(1)

    # 4. Start Communication Layer: Telegram Bot
    bot, dp = create_telegram_bot_and_dispatcher()
    if bot and dp:
        try:
            # Delete existing webhooks if any and start polling
            await bot.delete_webhook(drop_pending_updates=True)
            await setup_bot_commands(bot)
            logger.info("Telegram Bot is ready and listening for incoming messages...")
            await dp.start_polling(bot)
        finally:
            if cleanup_task and not cleanup_task.done():
                cleanup_task.cancel()
                try:
                    await cleanup_task
                except asyncio.CancelledError:
                    pass
            
            if server_runner:
                await server_runner.cleanup()
                logger.info("Local media server stopped.")
    else:
        logger.info("Telegram Bot is disabled or BOT_TOKEN is empty. Core services (Media server / Cleanup) running in background.")
        try:
            # Keep process alive for media server / cleanup worker
            while True:
                await asyncio.sleep(3600)
        finally:
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
        logger.info("Service stopped.")
