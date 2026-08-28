"""
Secure local static media server for Instagram Graph API webhooks and image fetches.
Enforces strict anti-path-traversal, extension/MIME whitelisting, and security headers.
"""

import os
import mimetypes
import logging
from aiohttp import web
from src.config import settings

logger = logging.getLogger(__name__)

# Allowed media extensions for Instagram
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
    "video/quicktime",
}


async def secure_media_handler(request: web.Request) -> web.StreamResponse:
    """
    Secure file serving handler:
    1. Only GET and HEAD methods allowed.
    2. Strict Path Traversal prevention (canonical path checking).
    3. Blocks root directory index and directory listing.
    4. Blocks hidden files (.gitkeep, .env, etc.).
    5. Enforces extension and MIME whitelist.
    6. Adds security headers (nosniff, frame deny, CSP).
    """
    # 1. Method restriction
    if request.method not in ("GET", "HEAD"):
        raise web.HTTPMethodNotAllowed(request.method, ["GET", "HEAD"])

    filename = request.match_info.get("filename", "").strip()
    if not filename or filename == "/":
        raise web.HTTPNotFound(text="Not Found")

    # 2. Block hidden files and special paths
    if filename.startswith(".") or "/." in filename or "\\." in filename:
        logger.warning(f"Blocked attempt to access hidden file: '{filename}' from {request.remote}")
        raise web.HTTPNotFound(text="Not Found")

    # 3. Path Traversal Protection
    base_dir = os.path.abspath(settings.LOCAL_STORAGE_DIR)
    target_path = os.path.abspath(os.path.join(base_dir, filename))

    try:
        common_path = os.path.commonpath([base_dir, target_path])
        if common_path != base_dir:
            logger.warning(f"Directory traversal attempt blocked: '{filename}' from {request.remote}")
            raise web.HTTPForbidden(text="Access Denied")
    except ValueError:
        raise web.HTTPForbidden(text="Access Denied")

    # 4. Check file existence and verify it is a regular file
    if not os.path.isfile(target_path):
        raise web.HTTPNotFound(text="Media file not found")

    # 5. Validate extension whitelist
    _, ext = os.path.splitext(target_path)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        logger.warning(f"Blocked access to non-whitelisted extension '{ext}': {filename}")
        raise web.HTTPForbidden(text="File type not permitted")

    # Determine Content-Type
    content_type, _ = mimetypes.guess_type(target_path)
    if not content_type or content_type not in ALLOWED_MIME_TYPES:
        content_type = "application/octet-stream"

    # 6. Build response with security headers
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": "default-src 'none'; media-src 'self'; img-src 'self';",
        "Cache-Control": "public, max-age=3600",
        "Content-Disposition": "inline",
    }

    return web.FileResponse(target_path, headers=headers)


async def start_secure_media_server() -> web.AppRunner:
    """Initializes and starts the secure media static server."""
    os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)
    app = web.Application()

    # Route all requests to secure handler
    app.router.add_route("*", "/{filename:.*}", secure_media_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.LOCAL_SERVER_HOST, settings.LOCAL_SERVER_PORT)
    await site.start()
    logger.info(
        f"Secure local media server running at http://{settings.LOCAL_SERVER_HOST}:{settings.LOCAL_SERVER_PORT}/ "
        f"(Serving: {settings.LOCAL_STORAGE_DIR}, Protection: Whitelist, Anti-Traversal, Security Headers)"
    )
    return runner
