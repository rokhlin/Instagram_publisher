"""
Communication / UI layer: abstracts Telegram bot, WhatsApp connector, and future chat interfaces.
"""

from src.communication.base import BaseCommunicationChannel
from src.communication.telegram import (
    create_telegram_bot_and_dispatcher,
    telegram_router,
    PostCreationStates,
)
from src.communication.whatsapp import WhatsAppService, whatsapp_service

__all__ = [
    "BaseCommunicationChannel",
    "create_telegram_bot_and_dispatcher",
    "telegram_router",
    "PostCreationStates",
    "WhatsAppService",
    "whatsapp_service",
]
