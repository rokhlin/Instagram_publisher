"""
Mentions management subpackage.
"""

from src.business_logic.mentions.mention_service import MentionService, mention_service, DEFAULT_PRESET_MENTIONS

__all__ = [
    "MentionService",
    "mention_service",
    "DEFAULT_PRESET_MENTIONS",
]
