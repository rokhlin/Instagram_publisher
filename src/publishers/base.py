"""
Abstract Base Class for Social Media Publishers.
Defines standard interface for single media, carousel containers, status polling, and publishing.
"""

from abc import ABC, abstractmethod
from typing import Optional, List


class BasePublisher(ABC):
    """
    Abstract Publisher Interface for publishing media to target platforms (Instagram, Facebook, etc.).
    """

    @abstractmethod
    async def create_media_container(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        is_video: bool = False,
        caption: str = "",
        is_story: bool = False
    ) -> str:
        """
        Creates a single media container on the destination platform.
        Returns the container ID.
        """
        pass

    @abstractmethod
    async def create_carousel_item_container(
        self,
        media_url: str,
        is_video: bool = False
    ) -> str:
        """
        Creates an individual child item container for a multi-media album/carousel.
        """
        pass

    @abstractmethod
    async def create_carousel_parent_container(
        self,
        children_ids: List[str],
        caption: str = ""
    ) -> str:
        """
        Creates the parent carousel container linking the provided child items.
        """
        pass

    @abstractmethod
    async def check_container_status(self, creation_id: str) -> str:
        """
        Queries status of media container processing.
        """
        pass

    @abstractmethod
    async def wait_for_container_ready(
        self,
        creation_id: str,
        max_retries: int = 15,
        delay_seconds: int = 3
    ) -> None:
        """
        Waits until container transcoding/upload is FINISHED and ready to publish.
        """
        pass

    @abstractmethod
    async def publish_container(self, creation_id: str, max_retries: int = 15) -> str:
        """
        Executes publication of container to live feed/story.
        Returns the published post/media ID.
        """
        pass
