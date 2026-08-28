"""
Inline Keyboards for Telegram Bot.
"""

from typing import List, Set
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.business_logic.media import FONT_REGISTRY, FILTER_REGISTRY
from src.business_logic.i18n import t


def get_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена / Cancel", callback_data="act_cancel")
            ]
        ]
    )


def get_instructions_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    skip_text = t("common.skip_auto", lang=language)
    cancel_text = t("common.cancel", lang=language)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=skip_text, callback_data="act_skip_instructions")
            ],
            [
                InlineKeyboardButton(text=cancel_text, callback_data="act_cancel")
            ]
        ]
    )


def get_format_keyboard(language: str = "ru", is_album: bool = False, has_video: bool = False) -> InlineKeyboardMarkup:
    cancel_text = t("common.cancel", lang=language)

    if is_album:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=t("formats.CAROUSEL_PORTRAIT", lang=language), callback_data="fmt_CAROUSEL_PORTRAIT"),
                    InlineKeyboardButton(text=t("formats.CAROUSEL_SQUARE", lang=language), callback_data="fmt_CAROUSEL_SQUARE"),
                ],
                [
                    InlineKeyboardButton(text=cancel_text, callback_data="act_cancel")
                ]
            ]
        )

    if has_video:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=t("formats.REELS", lang=language), callback_data="fmt_REELS"),
                    InlineKeyboardButton(text=t("formats.STORY", lang=language), callback_data="fmt_STORY"),
                ],
                [
                    InlineKeyboardButton(text=t("formats.FEED_PORTRAIT", lang=language), callback_data="fmt_FEED_PORTRAIT"),
                ],
                [
                    InlineKeyboardButton(text=cancel_text, callback_data="act_cancel")
                ]
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("formats.STORY", lang=language), callback_data="fmt_STORY"),
                InlineKeyboardButton(text=t("formats.FEED_PORTRAIT", lang=language), callback_data="fmt_FEED_PORTRAIT"),
            ],
            [
                InlineKeyboardButton(text=t("formats.FEED_SQUARE", lang=language), callback_data="fmt_FEED_SQUARE"),
            ],
            [
                InlineKeyboardButton(text=cancel_text, callback_data="act_cancel")
            ]
        ]
    )


def get_approval_keyboard(
    active_tags_count: int = 0,
    active_mentions_count: int = 0,
    language: str = "ru",
    show_photo_text_button: bool = True,
    has_photo_text: bool = False,
    active_filter: str = "ORIGINAL",
    active_font: str = "MODERN"
) -> InlineKeyboardMarkup:
    lang_attr = "name_ru" if language.lower().startswith("ru") else "name_en"
    publish_text = t("common.publish", lang=language)
    tags_text = t("keyboards.tags", lang=language, count=active_tags_count)
    mentions_text = t("keyboards.mentions", lang=language, count=active_mentions_count)
    edit_text = t("keyboards.edit_caption", lang=language)
    regen_text = t("keyboards.regenerate", lang=language)
    cancel_text = t("common.cancel", lang=language)

    filter_label = FILTER_REGISTRY.get(active_filter, {}).get(lang_attr, t("keyboards.filters", lang=language))
    font_label = FONT_REGISTRY.get(active_font, {}).get(lang_attr, t("keyboards.fonts", lang=language))

    buttons = [
        [
            InlineKeyboardButton(text=publish_text, callback_data="act_publish")
        ]
    ]

    # Visual customization row: Filters & Fonts
    if show_photo_text_button:
        buttons.append([
            InlineKeyboardButton(text=f"🎨 {filter_label}", callback_data="act_open_filter_menu"),
            InlineKeyboardButton(text=f"🔤 {font_label}", callback_data="act_open_font_menu"),
        ])

        if has_photo_text:
            photo_text_btn = t("keyboards.photo_text_on", lang=language)
            edit_photo_text_btn = t("keyboards.edit_photo_text", lang=language)
            buttons.append([
                InlineKeyboardButton(text=photo_text_btn, callback_data="act_toggle_photo_text"),
                InlineKeyboardButton(text=edit_photo_text_btn, callback_data="act_edit_photo_text"),
            ])
        else:
            photo_text_btn = t("keyboards.add_photo_text", lang=language)
            buttons.append([
                InlineKeyboardButton(text=photo_text_btn, callback_data="act_toggle_photo_text")
            ])
    else:
        buttons.append([
            InlineKeyboardButton(text=f"🎨 {filter_label}", callback_data="act_open_filter_menu"),
        ])

    buttons.append([
        InlineKeyboardButton(text=tags_text, callback_data="act_open_tag_editor"),
        InlineKeyboardButton(text=mentions_text, callback_data="act_open_mention_editor"),
    ])
    buttons.append([
        InlineKeyboardButton(text=edit_text, callback_data="act_edit"),
        InlineKeyboardButton(text=regen_text, callback_data="act_regenerate"),
    ])
    buttons.append([
        InlineKeyboardButton(text=cancel_text, callback_data="act_cancel")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_filter_selection_keyboard(active_filter: str = "ORIGINAL", language: str = "ru") -> InlineKeyboardMarkup:
    lang_attr = "name_ru" if language.lower().startswith("ru") else "name_en"
    buttons = []
    row = []

    for f_key, f_info in FILTER_REGISTRY.items():
        is_sel = (f_key == active_filter)
        icon = "✅ " if is_sel else ""
        label = f"{icon}{f_info.get(lang_attr, f_info.get('name_en', f_key))}"
        row.append(InlineKeyboardButton(text=label, callback_data=f"apply_filter_{f_key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    back_text = t("keyboards.back_to_preview", lang=language)
    buttons.append([
        InlineKeyboardButton(text=back_text, callback_data="act_back_to_preview")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_font_selection_keyboard(active_font: str = "MODERN", language: str = "ru") -> InlineKeyboardMarkup:
    lang_attr = "name_ru" if language.lower().startswith("ru") else "name_en"
    buttons = []
    row = []

    for font_key, font_info in FONT_REGISTRY.items():
        is_sel = (font_key == active_font)
        icon = "✅ " if is_sel else ""
        label = f"{icon}{font_info.get(lang_attr, font_info.get('name_en', font_key))}"
        row.append(InlineKeyboardButton(text=label, callback_data=f"apply_font_{font_key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    back_text = t("keyboards.back_to_preview", lang=language)
    buttons.append([
        InlineKeyboardButton(text=back_text, callback_data="act_back_to_preview")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tag_editor_keyboard(available_tags: List[str], active_tags: Set[str], language: str = "ru") -> InlineKeyboardMarkup:
    buttons = []

    row = []
    for idx, tag in enumerate(available_tags):
        is_active = tag in active_tags
        icon = "✅" if is_active else "◻️"
        btn_text = f"{icon} {tag}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"tag_toggle_{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    add_custom_text = t("keyboards.add_custom_tag", lang=language)
    manage_presets_text = t("keyboards.manage_preset_tags", lang=language)
    save_text = t("keyboards.save_and_return", lang=language)

    buttons.append([
        InlineKeyboardButton(text=add_custom_text, callback_data="act_add_custom_tag"),
        InlineKeyboardButton(text=manage_presets_text, callback_data="act_manage_preset_tags"),
    ])
    buttons.append([
        InlineKeyboardButton(text=save_text, callback_data="act_back_to_preview")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_mention_editor_keyboard(available_mentions: List[str], active_mentions: Set[str], language: str = "ru") -> InlineKeyboardMarkup:
    buttons = []

    row = []
    for idx, mention in enumerate(available_mentions):
        is_active = mention in active_mentions
        icon = "✅" if is_active else "◻️"
        btn_text = f"{icon} {mention}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"men_toggle_{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    add_custom_text = t("keyboards.add_custom_mention", lang=language)
    manage_presets_text = t("keyboards.manage_preset_mentions", lang=language)
    save_text = t("keyboards.save_and_return", lang=language)

    buttons.append([
        InlineKeyboardButton(text=add_custom_text, callback_data="act_add_custom_mention"),
        InlineKeyboardButton(text=manage_presets_text, callback_data="act_manage_preset_mentions"),
    ])
    buttons.append([
        InlineKeyboardButton(text=save_text, callback_data="act_back_to_preview")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_presets_manager_keyboard(items: List[str], item_type: str, language: str = "ru") -> InlineKeyboardMarkup:
    buttons = []

    row = []
    for idx, item in enumerate(items):
        btn_text = f"🗑 {item}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"del_preset_{item_type}_{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    add_text = t("keyboards.add_preset_tag" if item_type == "tag" else "keyboards.add_preset_mention", lang=language)
    back_text = t("keyboards.back", lang=language)

    buttons.append([
        InlineKeyboardButton(text=add_text, callback_data=f"add_preset_{item_type}")
    ])
    buttons.append([
        InlineKeyboardButton(text=back_text, callback_data=f"back_from_preset_{item_type}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    back_text = t("keyboards.back_to_preview", lang=language)
    cancel_text = t("common.cancel", lang=language)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=back_text, callback_data="act_back_to_preview"),
                InlineKeyboardButton(text=cancel_text, callback_data="act_cancel")
            ]
        ]
    )
