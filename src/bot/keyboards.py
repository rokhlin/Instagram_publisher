from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 Stories (9:16)", callback_data="fmt_STORY"),
                InlineKeyboardButton(text="🖼 Feed Post (4:5 Portrait)", callback_data="fmt_FEED_PORTRAIT"),
            ],
            [
                InlineKeyboardButton(text="⏹ Feed Post (1:1 Square)", callback_data="fmt_FEED_SQUARE"),
            ],
            [
                InlineKeyboardButton(text="❌ Cancel", callback_data="act_cancel")
            ]
        ]
    )


def get_approval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Publish to Instagram", callback_data="act_publish")
            ],
            [
                InlineKeyboardButton(text="✏️ Edit Text", callback_data="act_edit"),
                InlineKeyboardButton(text="🔄 Regenerate", callback_data="act_regenerate"),
            ],
            [
                InlineKeyboardButton(text="❌ Cancel", callback_data="act_cancel")
            ]
        ]
    )


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔙 Back to Preview", callback_data="act_back_to_preview"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="act_cancel")
            ]
        ]
    )
