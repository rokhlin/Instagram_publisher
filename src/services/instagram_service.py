import asyncio
import logging
from typing import Dict, Any, List, Optional
import aiohttp
from src.config import settings

logger = logging.getLogger(__name__)


class InstagramService:
    def __init__(self):
        self.base_url = f"https://graph.facebook.com/{settings.IG_GRAPH_API_VERSION}"
        self.account_id = settings.IG_USER_ID
        self.access_token = settings.IG_ACCESS_TOKEN

    async def create_media_container(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        is_video: bool = False,
        caption: str = "",
        is_story: bool = False
    ) -> str:
        """
        Creates a single Instagram media container (Image, Video/Reel, or Story).
        Returns the creation_id.
        """
        endpoint = f"{self.base_url}/{self.account_id}/media"
        
        params: Dict[str, Any] = {
            "access_token": self.access_token,
        }

        if is_video or video_url:
            params["video_url"] = video_url or image_url
            if is_story:
                params["media_type"] = "STORIES"
            else:
                params["media_type"] = "REELS"
                if caption:
                    params["caption"] = caption
        else:
            params["image_url"] = image_url
            if is_story:
                params["media_type"] = "STORIES"
            elif caption:
                params["caption"] = caption

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, data=params) as response:
                result = await response.json()
                if response.status != 200 or "id" not in result:
                    error_msg = result.get("error", {}).get("message", str(result))
                    logger.error(f"Meta Graph API error creating container: {error_msg}")
                    raise RuntimeError(f"Instagram container creation error: {error_msg}")
                
                creation_id = result["id"]
                logger.info(f"Media container created successfully: {creation_id}")
                return creation_id

    async def create_carousel_item_container(
        self,
        media_url: str,
        is_video: bool = False
    ) -> str:
        """
        Creates an individual child item container for an Instagram Carousel.
        """
        endpoint = f"{self.base_url}/{self.account_id}/media"
        params: Dict[str, Any] = {
            "access_token": self.access_token,
            "is_carousel_item": "true",
        }

        if is_video:
            params["media_type"] = "VIDEO"
            params["video_url"] = media_url
        else:
            params["image_url"] = media_url

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, data=params) as response:
                result = await response.json()
                if response.status != 200 or "id" not in result:
                    error_msg = result.get("error", {}).get("message", str(result))
                    logger.error(f"Meta Graph API error creating carousel item container: {error_msg}")
                    raise RuntimeError(f"Instagram carousel item creation error: {error_msg}")

                creation_id = result["id"]
                logger.info(f"Carousel item container created: {creation_id} (is_video={is_video})")
                return creation_id

    async def create_carousel_parent_container(
        self,
        children_ids: List[str],
        caption: str = ""
    ) -> str:
        """
        Creates the parent CAROUSEL container containing multiple children containers.
        """
        endpoint = f"{self.base_url}/{self.account_id}/media"
        params: Dict[str, Any] = {
            "access_token": self.access_token,
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
        }
        if caption:
            params["caption"] = caption

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, data=params) as response:
                result = await response.json()
                if response.status != 200 or "id" not in result:
                    error_msg = result.get("error", {}).get("message", str(result))
                    logger.error(f"Meta Graph API error creating parent carousel container: {error_msg}")
                    raise RuntimeError(f"Instagram parent carousel creation error: {error_msg}")

                creation_id = result["id"]
                logger.info(f"Parent Carousel container created successfully: {creation_id}")
                return creation_id

    async def check_container_status(self, creation_id: str) -> str:
        """
        Checks the status of media container (FINISHED, IN_PROGRESS, ERROR, EXPIRED).
        """
        endpoint = f"{self.base_url}/{creation_id}"
        params = {
            "fields": "status_code",
            "access_token": self.access_token,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, params=params) as response:
                result = await response.json()
                if response.status != 200:
                    error_msg = result.get("error", {}).get("message", str(result))
                    raise RuntimeError(f"Failed to check container status: {error_msg}")
                
                return result.get("status_code", "FINISHED")

    async def wait_for_container_ready(self, creation_id: str, max_retries: int = 15, delay_seconds: int = 3) -> None:
        """
        Waits for a container (especially video/carousel item) to finish transcoding.
        """
        for attempt in range(max_retries):
            status = await self.check_container_status(creation_id)
            if status in ("FINISHED", None):
                logger.info(f"Container {creation_id} is ready (FINISHED).")
                return
            elif status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Container {creation_id} failed with status: {status}")
            
            logger.info(f"Container {creation_id} status is {status}, waiting... (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(delay_seconds)

    async def publish_container(self, creation_id: str, max_retries: int = 15) -> str:
        """
        Publishes the media or carousel container to Instagram.
        Returns the published post ID.
        """
        await self.wait_for_container_ready(creation_id, max_retries=max_retries)

        endpoint = f"{self.base_url}/{self.account_id}/media_publish"
        params = {
            "creation_id": creation_id,
            "access_token": self.access_token,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, data=params) as response:
                result = await response.json()
                if response.status != 200 or "id" not in result:
                    error_msg = result.get("error", {}).get("message", str(result))
                    logger.error(f"Meta Graph API error publishing container: {error_msg}")
                    raise RuntimeError(f"Instagram publishing error: {error_msg}")

                post_id = result["id"]
                logger.info(f"Post published successfully to Instagram: {post_id}")
                return post_id


instagram_service = InstagramService()
