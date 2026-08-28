"""
Abstract Base Class for AI Engine Providers.
Defines standard interface for caption generation, refinement, story text overlays, and audio transcription.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class BaseAIProvider(ABC):
    """
    Abstract AI Provider Interface.
    Any provider (Gemini, Local LLM, OpenAI, Anthropic, etc.) must implement this contract.
    """

    @abstractmethod
    async def generate_caption(
        self,
        image_bytes: Optional[bytes] = None,
        media_items: Optional[List[Dict[str, Any]]] = None,
        instructions: str = "",
        post_format: str = "FEED_PORTRAIT",
        language: str = "ru"
    ) -> str:
        """
        Generates an engaging social media post caption based on visual media and guidance.
        """
        pass

    @abstractmethod
    async def refine_caption(
        self,
        current_caption: str,
        correction_instructions: str,
        image_bytes: Optional[bytes] = None,
        media_items: Optional[List[Dict[str, Any]]] = None,
        post_format: str = "FEED_PORTRAIT",
        language: str = "ru"
    ) -> str:
        """
        Refines an existing caption according to user feedback / instructions.
        """
        pass

    @abstractmethod
    async def generate_story_overlay_text(
        self,
        image_bytes: Optional[bytes] = None,
        instructions: str = "",
        language: str = "ru"
    ) -> str:
        """
        Generates a concise aesthetic 1-2 line quote for overlaying on a Story photo.
        """
        pass

    @abstractmethod
    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg"
    ) -> str:
        """
        Transcribes voice message or audio recording into plain text.
        """
        pass
