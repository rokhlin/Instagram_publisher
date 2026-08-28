"""
Business Logic Orchestrator:
Coordinates the high-level domain workflows across Communication, AI Engine, Media Processing, Storage, and Publisher layers.
"""

import logging
from typing import List, Dict, Any, Optional

from src.business_logic.prompts import (
    get_system_prompt,
    build_caption_prompt,
    build_refine_prompt,
    build_story_overlay_prompt,
    get_fallback_caption,
)
from src.business_logic.media.image_processor import ImageProcessor, image_processor
from src.business_logic.tags.tag_service import tag_service, TagService
from src.business_logic.mentions.mention_service import mention_service, MentionService
from src.business_logic.storage.storage_service import storage_service

logger = logging.getLogger(__name__)


class ContentOrchestrator:
    """
    Central business logic coordinator for post processing, AI caption creation,
    asset transformation, and caption formatting.
    """

    def __init__(self):
        self.image_processor = image_processor
        self.tag_service = tag_service
        self.mention_service = mention_service
        self.storage_service = storage_service

    def assemble_full_caption(
        self,
        caption_body: str,
        active_mentions: Optional[List[str]] = None,
        active_tags: Optional[List[str]] = None
    ) -> str:
        """
        Combines body text, active mentions (@), and active hashtags (#)
        into a finalized Instagram-ready caption string.
        """
        clean_body = caption_body.strip() if caption_body else ""
        mentions_str = " ".join(active_mentions) if active_mentions else ""
        tags_str = " ".join(active_tags) if active_tags else ""

        parts = []
        if clean_body:
            parts.append(clean_body)
        if mentions_str:
            parts.append(mentions_str)
        if tags_str:
            parts.append(tags_str)

        return "\n\n".join(parts)

    def parse_user_caption_input(
        self,
        text: str
    ) -> Dict[str, Any]:
        """
        Extracts hashtags and body from user-provided caption or edit instruction.
        """
        body, tags = self.tag_service.extract_tags_and_body(text)
        return {
            "body": body,
            "extracted_tags": tags
        }

    async def prepare_media_for_publishing(
        self,
        media_bytes: bytes,
        post_format: str = "FEED_PORTRAIT",
        filter_name: str = "ORIGINAL",
        overlay_text: Optional[str] = None,
        font_key: str = "MODERN",
        is_video: bool = False
    ) -> str:
        """
        Processes media item (applies crop/aspect ratio, filter, and optional text overlay)
        and uploads to public storage, returning the public URL.
        """
        if is_video:
            # Video files are uploaded directly to storage
            return await self.storage_service.upload_media(
                media_bytes=media_bytes,
                is_video=True
            )

        # 1. Process image geometry & visual filter
        processed_bytes = self.image_processor.process_image(
            input_bytes=media_bytes,
            post_type=post_format,
            filter_name=filter_name
        )

        # 2. Apply typography overlay if provided
        if overlay_text and overlay_text.strip():
            processed_bytes = self.image_processor.overlay_text_on_image(
                image_bytes=processed_bytes,
                text=overlay_text.strip(),
                post_type=post_format,
                font_key=font_key
            )

        # 3. Upload to storage (R2 / S3 / Local)
        public_url = await self.storage_service.upload_media(
            media_bytes=processed_bytes,
            is_video=False
        )
        return public_url


orchestrator = ContentOrchestrator()
