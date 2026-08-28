"""
Tags management subpackage.
"""

from src.business_logic.tags.tag_service import TagService, tag_service, DEFAULT_PRESET_TAGS

__all__ = [
    "TagService",
    "tag_service",
    "DEFAULT_PRESET_TAGS",
]
