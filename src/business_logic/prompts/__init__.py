"""
Prompts module for SMM copywriting, templates, and multilingual content.
"""

from src.business_logic.prompts.system_prompts import SYSTEM_PROMPTS, get_system_prompt
from src.business_logic.prompts.templates import (
    FORMAT_NAMES,
    build_caption_prompt,
    build_refine_prompt,
    build_story_overlay_prompt,
    build_transcription_prompt,
    get_fallback_caption,
)

__all__ = [
    "SYSTEM_PROMPTS",
    "get_system_prompt",
    "FORMAT_NAMES",
    "build_caption_prompt",
    "build_refine_prompt",
    "build_story_overlay_prompt",
    "build_transcription_prompt",
    "get_fallback_caption",
]
