"""
Publisher Factory: dynamically resolves and instantiates the active social media publisher.
"""

import logging
from typing import Dict, Type, Optional

from src.publishers.base import BasePublisher
from src.publishers.instagram.instagram_publisher import InstagramPublisher

logger = logging.getLogger(__name__)


class PublisherFactory:
    """
    Factory for resolving and instantiating publisher backends.
    """

    _registry: Dict[str, Type[BasePublisher]] = {
        "instagram": InstagramPublisher,
    }

    _instances: Dict[str, BasePublisher] = {}

    @classmethod
    def register_publisher(cls, name: str, publisher_cls: Type[BasePublisher]) -> None:
        """Allows registering additional publishers dynamically (e.g., Facebook, Pinterest)."""
        cls._registry[name.lower().strip()] = publisher_cls

    @classmethod
    def get_publisher(cls, name: str = "instagram") -> BasePublisher:
        """
        Returns a cached or new instance of the specified publisher.
        """
        target = name.lower().strip()
        if target not in cls._registry:
            logger.warning(
                f"Unknown publisher '{target}'. Available: {list(cls._registry.keys())}. "
                "Defaulting to 'instagram'."
            )
            target = "instagram"

        if target not in cls._instances:
            pub_cls = cls._registry[target]
            cls._instances[target] = pub_cls()
            logger.info(f"Instantiated Publisher: '{target}' ({pub_cls.__name__})")

        return cls._instances[target]


def get_publisher(name: str = "instagram") -> BasePublisher:
    """Convenience accessor to get a social media publisher."""
    return PublisherFactory.get_publisher(name)


# Global default instance
publisher = get_publisher("instagram")
