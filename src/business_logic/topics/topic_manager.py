"""
Topic Series Session Manager.
Handles session-based content series (AC-6, AC-7, AC-8),
grouping incoming media under unified topic and style presets.
"""

import time
import logging
from typing import Dict, Optional, List, Any, Tuple

logger = logging.getLogger(__name__)


class TopicSession:
    """
    Represents an active content series session for a user.
    """
    def __init__(self, user_id: int, description: str):
        self.user_id: int = user_id
        self.description: str = description.strip()
        self.created_at: float = time.time()
        self.media_items: List[Dict[str, Any]] = []
        self.locked_style: Optional[str] = None
        self.is_active: bool = True

    def add_media(self, media_item: Dict[str, Any]) -> None:
        """Appends a media item to the topic series."""
        self.media_items.append(media_item)

    def set_style(self, style_key: str) -> None:
        """Sets a unified style for the entire series."""
        self.locked_style = style_key

    def close(self) -> None:
        """Closes the session."""
        self.is_active = False


class TopicManager:
    """
    Manages active topic sessions per user.
    """
    def __init__(self):
        self._active_sessions: Dict[int, TopicSession] = {}

    def is_topic_keyword(self, text: str) -> bool:
        """Checks if text starts with topic starter keyword."""
        if not text:
            return False
        clean = text.strip().lower()
        return clean.startswith("тема ") or clean.startswith("тема:") or clean == "тема"

    def is_close_keyword(self, text: str) -> bool:
        """Checks if text matches topic closing command."""
        if not text:
            return False
        clean = text.strip().lower()
        return clean in ["тема закрыта", "тема закрыта.", "закрыть тему", "/close_topic"]

    def extract_topic_description(self, text: str) -> str:
        """Extracts the description part from 'тема [описание]'."""
        clean = text.strip()
        if clean.lower().startswith("тема:"):
            return clean[5:].strip()
        elif clean.lower().startswith("тема "):
            return clean[5:].strip()
        return clean

    def handle_topic_command(self, user_id: int, text: str) -> Tuple[bool, str, TopicSession]:
        """
        Handles topic commands according to AC-6 and AC-7:
        - If already active, ignores new topic definition and retains active topic (AC-7).
        - If not active, opens new topic session (AC-6).
        Returns: (is_newly_opened, message_info, session)
        """
        existing = self.get_active_session(user_id)
        if existing:
            # AC-7: ignore new keyword and keep active topic
            logger.info("User %s already has active topic '%s'. Ignoring new topic command.", user_id, existing.description)
            return False, f"Тема уже активна: «{existing.description}». Медиа продолжают добавляться в текущую серию.", existing

        desc = self.extract_topic_description(text)
        session = TopicSession(user_id=user_id, description=desc)
        self._active_sessions[user_id] = session
        logger.info("Opened new topic session for user %s: '%s'", user_id, desc)
        return True, f"Открыта новая тема: «{desc}». Все последующие фото и видео будут объединены в эту серию.", session

    def get_active_session(self, user_id: int) -> Optional[TopicSession]:
        """Returns the user's active topic session if any."""
        session = self._active_sessions.get(user_id)
        if session and session.is_active:
            return session
        return None

    def add_media_to_active_topic(self, user_id: int, media_item: Dict[str, Any]) -> Optional[TopicSession]:
        """Adds media to the active topic if one exists."""
        session = self.get_active_session(user_id)
        if session:
            session.add_media(media_item)
            return session
        return None

    def set_topic_style(self, user_id: int, style_key: str) -> bool:
        """Locks style for all media in the active topic series."""
        session = self.get_active_session(user_id)
        if session:
            session.set_style(style_key)
            return True
        return False

    def close_topic(self, user_id: int) -> Optional[TopicSession]:
        """
        Closes active topic session (AC-8).
        Returns closed session or None.
        """
        session = self._active_sessions.pop(user_id, None)
        if session:
            session.close()
            logger.info("Closed topic session for user %s: '%s'", user_id, session.description)
            return session
        return None


# Global singleton instance
from typing import Tuple
topic_manager = TopicManager()
