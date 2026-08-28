"""
Compatibility shim for keyboards.
Now located in `src.communication.telegram.keyboards`.
"""

from src.communication.telegram.keyboards import (
    get_language_keyboard,
    get_instructions_keyboard,
    get_format_keyboard,
    get_approval_keyboard,
    get_filter_selection_keyboard,
    get_font_selection_keyboard,
    get_tag_editor_keyboard,
    get_mention_editor_keyboard,
    get_presets_manager_keyboard,
    get_cancel_keyboard,
)

__all__ = [
    "get_language_keyboard",
    "get_instructions_keyboard",
    "get_format_keyboard",
    "get_approval_keyboard",
    "get_filter_selection_keyboard",
    "get_font_selection_keyboard",
    "get_tag_editor_keyboard",
    "get_mention_editor_keyboard",
    "get_presets_manager_keyboard",
    "get_cancel_keyboard",
]
