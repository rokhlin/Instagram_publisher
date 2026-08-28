"""
Legacy Services Compatibility Layer.
Provides backward-compatible import aliases for modules moved to the 4-layer architecture:
- src.communication
- src.ai_engine
- src.publishers
- src.business_logic
"""

# AI Engine
from src.ai_engine import ai_engine, get_ai_engine, GeminiProvider, LocalLLMProvider
from src.ai_engine.providers.gemini_provider import GeminiProvider as AIService
ai_service = ai_engine

# Publishers
from src.publishers import (
    instagram_publisher,
    InstagramPublisher,
    InstagramService,
    get_publisher,
    publisher,
)

# Business Logic - Media & Image Processing
from src.business_logic.media import (
    ImageProcessor,
    ImageService,
    image_processor,
    FONT_REGISTRY,
    FILTER_REGISTRY,
    TARGET_SIZES,
    PostType,
)

# Business Logic - Tags & Mentions
from src.business_logic.tags import TagService, tag_service, DEFAULT_PRESET_TAGS
from src.business_logic.mentions import MentionService, mention_service, DEFAULT_PRESET_MENTIONS

# Business Logic - Storage
from src.business_logic.storage import (
    StorageService,
    storage_service,
    start_secure_media_server,
    secure_media_handler,
    run_cleanup_worker,
    cleanup_expired_files,
)

# Communication - WhatsApp
from src.communication.whatsapp import WhatsAppService, whatsapp_service

__all__ = [
    "ai_service",
    "AIService",
    "ai_engine",
    "get_ai_engine",
    "GeminiProvider",
    "LocalLLMProvider",
    "instagram_publisher",
    "InstagramPublisher",
    "InstagramService",
    "get_publisher",
    "publisher",
    "ImageProcessor",
    "ImageService",
    "image_processor",
    "FONT_REGISTRY",
    "FILTER_REGISTRY",
    "TARGET_SIZES",
    "PostType",
    "TagService",
    "tag_service",
    "DEFAULT_PRESET_TAGS",
    "MentionService",
    "mention_service",
    "DEFAULT_PRESET_MENTIONS",
    "StorageService",
    "storage_service",
    "start_secure_media_server",
    "secure_media_handler",
    "run_cleanup_worker",
    "cleanup_expired_files",
    "WhatsAppService",
    "whatsapp_service",
]
