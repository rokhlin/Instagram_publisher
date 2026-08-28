"""
AI Engine Factory: dynamically resolves and instantiates the active AI provider.
"""

import logging
from typing import Dict, Type, Optional

from src.config import settings
from src.ai_engine.base import BaseAIProvider
from src.ai_engine.providers.gemini_provider import GeminiProvider
from src.ai_engine.providers.local_llm_provider import LocalLLMProvider

logger = logging.getLogger(__name__)


class AIEngineFactory:
    """
    Factory for creating and managing AI provider instances.
    """

    _registry: Dict[str, Type[BaseAIProvider]] = {
        "gemini": GeminiProvider,
        "local_llm": LocalLLMProvider,
    }

    _instances: Dict[str, BaseAIProvider] = {}

    @classmethod
    def register_provider(cls, name: str, provider_cls: Type[BaseAIProvider]) -> None:
        """Allows registering new AI providers dynamically."""
        cls._registry[name.lower().strip()] = provider_cls

    @classmethod
    def get_provider(cls, provider_name: Optional[str] = None) -> BaseAIProvider:
        """
        Returns a cached or new instance of the specified (or globally configured) AI provider.
        """
        target = (provider_name or settings.AI_PROVIDER or "gemini").lower().strip()

        if target not in cls._registry:
            logger.warning(
                f"Unknown AI_PROVIDER '{target}'. Available: {list(cls._registry.keys())}. "
                "Defaulting to 'gemini'."
            )
            target = "gemini"

        if target not in cls._instances:
            provider_cls = cls._registry[target]
            cls._instances[target] = provider_cls()
            logger.info(f"Instantiated AI Provider: '{target}' ({provider_cls.__name__})")

        return cls._instances[target]


def get_ai_engine(provider_name: Optional[str] = None) -> BaseAIProvider:
    """Convenience accessor to get the configured AI Engine."""
    return AIEngineFactory.get_provider(provider_name)


# Global default instance
ai_engine = get_ai_engine()
