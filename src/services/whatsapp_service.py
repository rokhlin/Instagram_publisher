import logging
from typing import Dict, Any, Optional
import aiohttp

from src.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Client for interacting with the Node.js WhatsApp Connector API.
    Enables sending messages, media, and checking connection readiness.
    """

    def __init__(self, base_url: Optional[str] = None):
        self._base_url = (base_url or settings.WHATSAPP_CONNECTOR_URL).rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(settings.WHATSAPP_ENABLED and self._base_url)

    async def get_status(self) -> Dict[str, Any]:
        """
        Queries the WhatsApp connector status and readiness.
        """
        if not self._base_url:
            return {"success": False, "error": "WhatsApp connector URL not configured"}

        url = f"{self._base_url}/api/status"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {"success": False, "status_code": resp.status, "error": await resp.text()}
        except Exception as e:
            logger.warning(f"Failed to connect to WhatsApp connector at {url}: {e}")
            return {"success": False, "error": str(e)}

    async def send_message(self, to: str, message: str) -> Dict[str, Any]:
        """
        Sends a WhatsApp text message to the specified recipient phone number.
        """
        if not self._base_url:
            return {"success": False, "error": "WhatsApp connector URL not configured"}

        url = f"{self._base_url}/api/send-message"
        payload = {
            "to": to,
            "message": message
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json()
                    if resp.status == 200 and data.get("success"):
                        logger.info(f"WhatsApp message successfully sent to {to}")
                        return data
                    logger.error(f"WhatsApp API error sending message to {to}: {data}")
                    return data
        except Exception as e:
            logger.error(f"WhatsApp send_message exception for {to}: {e}")
            return {"success": False, "error": str(e)}

    async def send_media(
        self,
        to: str,
        media_url: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends an image/video via URL to the specified recipient phone number.
        """
        if not self._base_url:
            return {"success": False, "error": "WhatsApp connector URL not configured"}

        url = f"{self._base_url}/api/send-media"
        payload = {
            "to": to,
            "mediaUrl": media_url,
            "caption": caption or ""
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    data = await resp.json()
                    if resp.status == 200 and data.get("success"):
                        logger.info(f"WhatsApp media successfully sent to {to}")
                        return data
                    logger.error(f"WhatsApp API error sending media to {to}: {data}")
                    return data
        except Exception as e:
            logger.error(f"WhatsApp send_media exception for {to}: {e}")
            return {"success": False, "error": str(e)}


whatsapp_service = WhatsAppService()
