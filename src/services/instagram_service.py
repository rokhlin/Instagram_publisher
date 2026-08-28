"""
Compatibility shim for instagram_service.
Now located in `src.publishers.instagram`.
"""

from src.publishers.instagram import InstagramPublisher, InstagramService, instagram_publisher

__all__ = ["InstagramPublisher", "InstagramService", "instagram_publisher"]
