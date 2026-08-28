"""
Compatibility shim for telegram_bot package.
Now located in `src.communication.telegram`.
"""

from src.communication.telegram import (
    create_telegram_bot_and_dispatcher,
    telegram_router,
    PostCreationStates,
)

__all__ = [
    "create_telegram_bot_and_dispatcher",
    "telegram_router",
    "PostCreationStates",
]
