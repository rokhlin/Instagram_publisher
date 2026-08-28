"""
Compatibility shim for media_server.
Now located in `src.business_logic.storage`.
"""

from src.business_logic.storage import (
    start_secure_media_server,
    secure_media_handler,
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
)

__all__ = [
    "start_secure_media_server",
    "secure_media_handler",
    "ALLOWED_EXTENSIONS",
    "ALLOWED_MIME_TYPES",
]
