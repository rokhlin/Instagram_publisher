"""
Communication HTTP API Server:
Exposes REST endpoints for external communication connectors (WhatsApp, Discord, Web UI)
to access shared Business Logic (prompts, orchestrator, image processing) and AI Engine (Gemini, Local LLM).
Also serves secure static media files for Instagram Graph API.
"""

import os
import base64
import logging
from aiohttp import web

from src.config import settings
from src.ai_engine import ai_engine, get_ai_engine
from src.business_logic import (
    orchestrator,
    tag_service,
    mention_service,
    image_processor,
    get_system_prompt,
    build_caption_prompt,
    build_refine_prompt,
    build_story_overlay_prompt,
    get_fallback_caption,
)
from src.business_logic.storage.media_server import secure_media_handler
from src.publishers import publisher

logger = logging.getLogger(__name__)


async def api_health_handler(request: web.Request) -> web.Response:
    """Returns status of AI Engine, Storage, and Publishers."""
    return web.json_response({
        "success": True,
        "service": "MemoryNMore Core Backend",
        "ai_provider": settings.AI_PROVIDER,
        "storage_type": settings.STORAGE_TYPE,
        "instagram_account_id": settings.IG_USER_ID or None,
    })


async def api_generate_caption_handler(request: web.Request) -> web.Response:
    """
    Endpoint for communication channels to generate AI captions using shared Business Logic & AI Engine.
    Payload: {
        "instructions": "...",
        "imageBase64": "...",
        "mimeType": "image/jpeg",
        "postFormat": "FEED_PORTRAIT",
        "language": "ru"
    }
    """
    try:
        data = await request.json()
    except Exception:
        data = {}

    instructions = data.get("instructions", "")
    image_b64 = data.get("imageBase64")
    mime_type = data.get("mimeType", "image/jpeg")
    post_format = data.get("postFormat", "FEED_PORTRAIT")
    language = data.get("language", "ru")

    image_bytes = None
    if image_b64:
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception as e:
            logger.warning("Failed to decode base64 image in API: %s", e)

    try:
        caption = await ai_engine.generate_caption(
            image_bytes=image_bytes,
            instructions=instructions,
            post_format=post_format,
            language=language
        )
        return web.json_response({
            "success": True,
            "caption": caption,
            "provider": settings.AI_PROVIDER
        })
    except Exception as e:
        logger.error("AI Caption generation error in API: %s", e)
        fallback = get_fallback_caption(instructions, post_format, language)
        return web.json_response({
            "success": False,
            "caption": fallback,
            "error": str(e)
        })


async def api_refine_caption_handler(request: web.Request) -> web.Response:
    """
    Endpoint to refine an existing caption based on user corrections.
    Payload: {
        "currentCaption": "...",
        "correctionInstructions": "...",
        "postFormat": "FEED_PORTRAIT",
        "language": "ru"
    }
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

    current_caption = data.get("currentCaption", "")
    corrections = data.get("correctionInstructions", "")
    post_format = data.get("postFormat", "FEED_PORTRAIT")
    language = data.get("language", "ru")

    try:
        refined = await ai_engine.refine_caption(
            current_caption=current_caption,
            correction_instructions=corrections,
            post_format=post_format,
            language=language
        )
        return web.json_response({
            "success": True,
            "caption": refined
        })
    except Exception as e:
        logger.error("Caption refinement error in API: %s", e)
        return web.json_response({
            "success": False,
            "caption": f"{current_caption}\n\n[Edit: {corrections}]",
            "error": str(e)
        })


async def api_story_overlay_handler(request: web.Request) -> web.Response:
    """
    Endpoint to generate a short 1-2 line aesthetic text for Story overlay.
    Payload: {
        "imageBase64": "...",
        "instructions": "...",
        "language": "ru"
    }
    """
    try:
        data = await request.json()
    except Exception:
        data = {}

    instructions = data.get("instructions", "")
    image_b64 = data.get("imageBase64")
    language = data.get("language", "ru")

    image_bytes = None
    if image_b64:
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception:
            pass

    try:
        text = await ai_engine.generate_story_overlay_text(
            image_bytes=image_bytes,
            instructions=instructions,
            language=language
        )
        return web.json_response({
            "success": True,
            "overlayText": text
        })
    except Exception as e:
        logger.error("Story overlay text generation error in API: %s", e)
        return web.json_response({
            "success": False,
            "overlayText": "Создаем воспоминания ✨" if language.startswith("ru") else "Making memories ✨",
            "error": str(e)
        })


async def start_communication_api_server() -> web.AppRunner:
    """
    Initializes and starts the HTTP API and static media server.
    Serves both static media files and REST API endpoints for communication channels.
    """
    os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)
    app = web.Application(client_max_size=50 * 1024 * 1024)  # 50MB payload limit

    # REST API Routes for Communication channels
    app.router.add_get("/api/health", api_health_handler)
    app.router.add_get("/api/status", api_health_handler)
    app.router.add_post("/api/ai/generate-caption", api_generate_caption_handler)
    app.router.add_post("/api/ai/refine-caption", api_refine_caption_handler)
    app.router.add_post("/api/ai/story-overlay", api_story_overlay_handler)

    # Static Media File Serving (Catch-all for /{filename})
    app.router.add_route("*", "/{filename:.*}", secure_media_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.LOCAL_SERVER_HOST, settings.LOCAL_SERVER_PORT)
    await site.start()
    logger.info(
        f"Communication API & Media Server running at http://{settings.LOCAL_SERVER_HOST}:{settings.LOCAL_SERVER_PORT}/ "
        f"(API: /api/*, Static Media: {settings.LOCAL_STORAGE_DIR})"
    )
    return runner
