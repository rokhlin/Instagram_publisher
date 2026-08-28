"""
Compatibility shim for tag_service.
Now located in `src.business_logic.tags`.
"""

from src.business_logic.tags import TagService, tag_service, DEFAULT_PRESET_TAGS

__all__ = ["TagService", "tag_service", "DEFAULT_PRESET_TAGS"]
