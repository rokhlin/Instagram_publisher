from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 Stories (9:16)", callback_data="fmt_STORY"),
                InlineKeyboardButton(text="🖼 Пост (4:5 Портрет)", callback_data="fmt_FEED_PORTRAIT"),
            ],
            [
                InlineKeyboardButton(text="⏹ Пост (1:1 Квадрат)", callback_data="fmt_FEED_SQUARE"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="act_cancel")
            ]
        ]
    )


def get_approval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Опубликовать в Instagram", callback_data="act_publish")
            ],
            [
                InlineKeyboardButton(text="✏️ Изменить текст", callback_data="act_edit"),
                InlineKeyboardButton(text="🔄 Сгенерировать заново", callback_data="act_regenerate"),
            ],
            [
                InlineKeyboardButton(text="❌ Отменить", callback_data="act_cancel")
            ]
        ]
    )


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔙 Назад к превью", callback_data="act_back_to_preview"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="act_cancel")
            ]
        ]
    )
