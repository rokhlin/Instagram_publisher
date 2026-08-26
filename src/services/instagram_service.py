import asyncio
import logging
from typing import Dict, Any, Optional
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
        image_url: str,
        caption: str = "",
        is_story: bool = False
    ) -> str:
        """
        Creates an Instagram media container.
        Returns the creation_id.
        """
        endpoint = f"{self.base_url}/{self.account_id}/media"
        
        params: Dict[str, Any] = {
            "image_url": image_url,
            "access_token": self.access_token,
        }

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

    async def publish_container(self, creation_id: str, max_retries: int = 6) -> str:
        """
        Publishes the media container to Instagram.
        Returns the published post ID.
        """
        # Wait until container status is FINISHED / ready
        for attempt in range(max_retries):
            status = await self.check_container_status(creation_id)
            if status in ("FINISHED", None):
                break
            elif status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Container failed with status: {status}")
            logger.info(f"Container status is {status}, waiting... (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(2)

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
