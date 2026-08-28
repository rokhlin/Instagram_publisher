"""
Telegram Bot Launcher: initializes aiogram Bot and Dispatcher, attaches routers and middleware.
"""

import logging
from typing import Optional, Tuple
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from src.config import settings
from src.communication.telegram.handlers import router as main_router

logger = logging.getLogger(__name__)


def create_telegram_bot_and_dispatcher(
    token: Optional[str] = None
) -> Tuple[Optional[Bot], Optional[Dispatcher]]:
    """
    Creates and configures the aiogram Bot and Dispatcher instances.
    """
    cleaned_token = (token or settings.BOT_TOKEN or "").strip().strip("'\"")
    if not cleaned_token or not settings.TELEGRAM_ENABLED:
        logger.info("Telegram Bot is disabled or BOT_TOKEN is empty.")
        return None, None

    bot = Bot(
        token=cleaned_token,
        default=DefaultBotProperties(parse_mode="Markdown")
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(main_router)

    return bot, dp
