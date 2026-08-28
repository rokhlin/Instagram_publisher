"""
Telegram Bot Launcher: initializes aiogram Bot and Dispatcher, attaches routers and middleware.
"""

import logging
from typing import Optional, Tuple, List
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault

from src.config import settings
from src.communication.telegram.handlers import router as main_router
from src.business_logic.i18n import t

logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """
    Registers bot command menus for Telegram clients in multiple languages (RU/EN).
    """
    try:
        commands_list = ["start", "help", "tags", "mentions", "status", "language", "cancel"]

        # Russian commands
        ru_commands = [
            BotCommand(command=cmd, description=t(f"commands.{cmd}", lang="ru"))
            for cmd in commands_list
        ]
        await bot.set_my_commands(ru_commands, scope=BotCommandScopeDefault(), language_code="ru")

        # English / default commands
        en_commands = [
            BotCommand(command=cmd, description=t(f"commands.{cmd}", lang="en"))
            for cmd in commands_list
        ]
        await bot.set_my_commands(en_commands, scope=BotCommandScopeDefault(), language_code="en")
        await bot.set_my_commands(ru_commands, scope=BotCommandScopeDefault())  # Default fallback

        logger.info("Telegram Bot commands menu registered successfully.")
    except Exception as e:
        logger.warning(f"Failed to set Telegram bot commands: {e}")


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
