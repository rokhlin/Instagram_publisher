"""
Compatibility shim for mention_service.
Now located in `src.business_logic.mentions`.
"""

from src.business_logic.mentions import MentionService, mention_service, DEFAULT_PRESET_MENTIONS

__all__ = ["MentionService", "mention_service", "DEFAULT_PRESET_MENTIONS"]
