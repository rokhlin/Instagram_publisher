from typing import List, Set
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.services.image_service import FONT_REGISTRY, FILTER_REGISTRY


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
    is_ru = language.lower().startswith("ru")
    skip_text = "⏩ Пропустить (автоанализ)" if is_ru else "⏩ Skip (Auto analysis)"
    cancel_text = "❌ Отмена" if is_ru else "❌ Cancel"

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
    is_ru = language.lower().startswith("ru")
    cancel_text = "❌ Отмена" if is_ru else "❌ Cancel"

    if is_album:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🎠 Карусель (4:5 Портрет)" if is_ru else "🎠 Carousel (4:5 Portrait)", callback_data="fmt_CAROUSEL_PORTRAIT"),
                    InlineKeyboardButton(text="⏹ Карусель (1:1 Квадрат)" if is_ru else "⏹ Carousel (1:1 Square)", callback_data="fmt_CAROUSEL_SQUARE"),
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
                    InlineKeyboardButton(text="🎬 Reels (9:16)" if is_ru else "🎬 Reels Video (9:16)", callback_data="fmt_REELS"),
                    InlineKeyboardButton(text="📱 Stories (9:16)" if is_ru else "📱 Stories (9:16)", callback_data="fmt_STORY"),
                ],
                [
                    InlineKeyboardButton(text="🖼 Feed Video (4:5)" if is_ru else "🖼 Feed Video (4:5)", callback_data="fmt_FEED_PORTRAIT"),
                ],
                [
                    InlineKeyboardButton(text=cancel_text, callback_data="act_cancel")
                ]
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 Stories (9:16)", callback_data="fmt_STORY"),
                InlineKeyboardButton(text="🖼 Feed Post (4:5)", callback_data="fmt_FEED_PORTRAIT"),
            ],
            [
                InlineKeyboardButton(text="⏹ Feed Post (1:1)", callback_data="fmt_FEED_SQUARE"),
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
    is_ru = language.lower().startswith("ru")
    publish_text = "🚀 Опубликовать в Instagram" if is_ru else "🚀 Publish to Instagram"
    tags_text = f"🏷 Теги ({active_tags_count})" if is_ru else f"🏷 Tags ({active_tags_count})"
    mentions_text = f"👥 Упоминания ({active_mentions_count})" if is_ru else f"👥 Mentions ({active_mentions_count})"
    edit_text = "🎙✏️ Текст описания" if is_ru else "🎙✏️ Refine Caption"
    regen_text = "🔄 Заново" if is_ru else "🔄 Regenerate"
    cancel_text = "❌ Отмена" if is_ru else "❌ Cancel"

    filter_label = FILTER_REGISTRY.get(active_filter, {}).get("name_ru" if is_ru else "name_en", "🎨 Фильтры")
    font_label = FONT_REGISTRY.get(active_font, {}).get("name_ru" if is_ru else "name_en", "🔤 Шрифт")

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
            photo_text_btn = "✍️ Текст на фото: ✅ Вкл" if is_ru else "✍️ Text on Photo: ✅ ON"
            edit_photo_text_btn = "✏️ Изменить текст на фото" if is_ru else "✏️ Edit Photo Text"
            buttons.append([
                InlineKeyboardButton(text=photo_text_btn, callback_data="act_toggle_photo_text"),
                InlineKeyboardButton(text=edit_photo_text_btn, callback_data="act_edit_photo_text"),
            ])
        else:
            photo_text_btn = "✍️ Добавить текст на фото" if is_ru else "✍️ Add Text on Photo"
            buttons.append([
                InlineKeyboardButton(text=photo_text_btn, callback_data="act_toggle_photo_text")
            ])
    else:
        # If purely video, still allow filter selection if applicable
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
    is_ru = language.lower().startswith("ru")
    buttons = []
    row = []

    for f_key, f_info in FILTER_REGISTRY.items():
        is_sel = (f_key == active_filter)
        icon = "✅ " if is_sel else ""
        label = f"{icon}{f_info['name_ru'] if is_ru else f_info['name_en']}"
        row.append(InlineKeyboardButton(text=label, callback_data=f"apply_filter_{f_key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    back_text = "🔙 Назад к предпросмотру" if is_ru else "🔙 Back to Preview"
    buttons.append([
        InlineKeyboardButton(text=back_text, callback_data="act_back_to_preview")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_font_selection_keyboard(active_font: str = "MODERN", language: str = "ru") -> InlineKeyboardMarkup:
    is_ru = language.lower().startswith("ru")
    buttons = []
    row = []

    for font_key, font_info in FONT_REGISTRY.items():
        is_sel = (font_key == active_font)
        icon = "✅ " if is_sel else ""
        label = f"{icon}{font_info['name_ru'] if is_ru else font_info['name_en']}"
        row.append(InlineKeyboardButton(text=label, callback_data=f"apply_font_{font_key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    back_text = "🔙 Назад к предпросмотру" if is_ru else "🔙 Back to Preview"
    buttons.append([
        InlineKeyboardButton(text=back_text, callback_data="act_back_to_preview")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tag_editor_keyboard(available_tags: List[str], active_tags: Set[str], language: str = "ru") -> InlineKeyboardMarkup:
    is_ru = language.lower().startswith("ru")
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

    add_custom_text = "➕ Добавить свой тег" if is_ru else "➕ Add Custom Tag"
    manage_presets_text = "⚙️ Пресеты тегов" if is_ru else "⚙️ Preset Tags"
    save_text = "💾 Сохранить и вернуться" if is_ru else "💾 Save & Return"

    buttons.append([
        InlineKeyboardButton(text=add_custom_text, callback_data="act_add_custom_tag"),
        InlineKeyboardButton(text=manage_presets_text, callback_data="act_manage_preset_tags"),
    ])
    buttons.append([
        InlineKeyboardButton(text=save_text, callback_data="act_back_to_preview")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_mention_editor_keyboard(available_mentions: List[str], active_mentions: Set[str], language: str = "ru") -> InlineKeyboardMarkup:
    is_ru = language.lower().startswith("ru")
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

    add_custom_text = "➕ Добавить аккаунт" if is_ru else "➕ Add Account"
    manage_presets_text = "⚙️ Пресеты упоминаний" if is_ru else "⚙️ Preset Mentions"
    save_text = "💾 Сохранить и вернуться" if is_ru else "💾 Save & Return"

    buttons.append([
        InlineKeyboardButton(text=add_custom_text, callback_data="act_add_custom_mention"),
        InlineKeyboardButton(text=manage_presets_text, callback_data="act_manage_preset_mentions"),
    ])
    buttons.append([
        InlineKeyboardButton(text=save_text, callback_data="act_back_to_preview")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_presets_manager_keyboard(items: List[str], item_type: str, language: str = "ru") -> InlineKeyboardMarkup:
    is_ru = language.lower().startswith("ru")
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

    add_text = f"➕ Добавить {'тег' if item_type == 'tag' else 'упоминание'}" if is_ru else f"➕ Add {'Tag' if item_type == 'tag' else 'Mention'}"
    back_text = "🔙 Назад" if is_ru else "🔙 Back"

    buttons.append([
        InlineKeyboardButton(text=add_text, callback_data=f"add_preset_{item_type}")
    ])
    buttons.append([
        InlineKeyboardButton(text=back_text, callback_data=f"back_from_preset_{item_type}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    is_ru = language.lower().startswith("ru")
    back_text = "🔙 Назад к превью" if is_ru else "🔙 Back to Preview"
    cancel_text = "❌ Отмена" if is_ru else "❌ Cancel"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=back_text, callback_data="act_back_to_preview"),
                InlineKeyboardButton(text=cancel_text, callback_data="act_cancel")
            ]
        ]
    )
