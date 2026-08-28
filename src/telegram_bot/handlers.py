"""
Compatibility shim for handlers.
Now located in `src.communication.telegram.handlers`.
"""

from src.communication.telegram.handlers import (
    router,
    is_user_allowed,
    assemble_full_caption,
    show_approval_preview,
    generate_and_preview_post,
)

__all__ = [
    "router",
    "is_user_allowed",
    "assemble_full_caption",
    "show_approval_preview",
    "generate_and_preview_post",
]
