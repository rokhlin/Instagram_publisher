"""
Abstract Base Class for Communication Channels (Telegram, WhatsApp, Discord, Slack, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseCommunicationChannel(ABC):
    """
    Abstract Channel Interface.
    """

    @abstractmethod
    async def start(self) -> None:
        """Starts the communication channel listener / polling / webhook."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stops the communication channel."""
        pass

    @abstractmethod
    async def send_text_message(self, recipient_id: str, text: str) -> Dict[str, Any]:
        """Sends a text message to a user / chat."""
        pass
