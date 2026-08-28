import io
import asyncio
import logging
from typing import List, Set, Dict, Any, Optional, Tuple
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from src.config import settings
from src.communication.telegram.states import PostCreationStates
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
from src.business_logic.media import ImageProcessor, ImageService, FONT_REGISTRY, FILTER_REGISTRY
from src.ai_engine import ai_engine, get_ai_engine
ai_service = ai_engine
from src.business_logic.tags import tag_service, TagService
from src.business_logic.mentions import mention_service, MentionService
from src.business_logic.storage import storage_service
from src.publishers import instagram_publisher, InstagramPublisher, InstagramService
instagram_service = instagram_publisher
from src.business_logic.i18n import (
    t,
    get_user_language,
    set_user_language,
    normalize_language,
)

logger = logging.getLogger(__name__)
router = Router(name="main_router")

# Media Group (Album) Buffering
_media_group_buffers: Dict[str, List[types.Message]] = {}
_media_group_tasks: Dict[str, asyncio.Task] = {}


def is_user_allowed(user_id: int) -> bool:
    if not settings.allowed_users:
        return True
    return user_id in settings.allowed_users


def assemble_full_caption(caption_body: str, active_mentions: List[str], active_tags: List[str]) -> str:
    parts = [caption_body.strip()]
    if active_mentions:
        parts.append("👥 " + " ".join(active_mentions))
    if active_tags:
        parts.append(" ".join(active_tags))
    return "\n\n".join([p for p in parts if p]).strip()


def get_localized_format_name(post_type: str, media_count: int = 1, lang: str = "ru") -> str:
    base = t(f"formats.{post_type}", lang=lang)
    if "CAROUSEL" in post_type and media_count > 1:
        suffix = f" ({media_count} {'файлов' if lang.lower().startswith('ru') else 'items'})"
        return f"{base}{suffix}"
    return base


def render_media_items(
    media_items: List[Dict[str, Any]],
    post_type: str,
    has_photo_text: bool,
    photo_overlay_text: str,
    active_filter: str = "ORIGINAL",
    active_font: str = "MODERN"
) -> Tuple[List[Dict[str, Any]], Optional[bytes]]:
    """
    Renders/crops images, applies visual filter and decorative on-photo text overlay.
    Returns (updated_media_items, cover_image_bytes).
    """
    is_story = (post_type in ("STORY", "CAROUSEL_STORY"))
    processed_items: List[Dict[str, Any]] = []
    cover_bytes: Optional[bytes] = None

    for item in media_items:
        if not item["is_video"]:
            # 1. Base crop, enhance & apply selected filter
            base_proc = ImageService.process_image(
                input_bytes=item["bytes"],
                post_type="STORY" if is_story else ("FEED_SQUARE" if "SQUARE" in post_type else "FEED_PORTRAIT"),
                filter_name=active_filter
            )
            # 2. Text overlay with chosen font if enabled
            if has_photo_text and photo_overlay_text:
                final_bytes = ImageService.overlay_text_on_image(
                    image_bytes=base_proc,
                    text=photo_overlay_text,
                    post_type=post_type,
                    font_key=active_font
                )
            else:
                final_bytes = base_proc

            processed_items.append({**item, "processed_bytes": final_bytes})
            if not cover_bytes:
                cover_bytes = final_bytes
        else:
            processed_items.append({**item, "processed_bytes": item["bytes"]})

    return processed_items, cover_bytes


# ==============================================================================
# Base Commands: /start, /help, /status, /cancel, /tags, /mentions, /language
# ==============================================================================

@router.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_lang = get_user_language(user_id=user_id, fallback_code=message.from_user.language_code)
    logger.info("Received /start from user_id=%s (%s), lang=%s", user_id, message.from_user.username, user_lang)
    if not is_user_allowed(user_id):
        await message.answer(t("telegram.access_denied", lang=user_lang), parse_mode="Markdown")
        return

    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    await message.answer(t("telegram.help_text", lang=user_lang), parse_mode="Markdown")


@router.message(Command("help"))
async def handle_help(message: types.Message):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return
    user_lang = get_user_language(user_id=user_id, fallback_code=message.from_user.language_code)
    await message.answer(t("telegram.help_text", lang=user_lang), parse_mode="Markdown")


@router.message(Command("status"))
async def handle_status_cmd(message: types.Message):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return

    user_lang = get_user_language(user_id=user_id, fallback_code=message.from_user.language_code)
    storage_mode = settings.STORAGE_TYPE.upper()
    ai_status = "Gemini AI Active (Multimodal & Voice)" if settings.GEMINI_API_KEY else "Template Fallback (No API Key)"
    preset_tags_count = len(tag_service.get_preset_tags())
    preset_mentions_count = len(mention_service.get_preset_mentions())

    status_text = t(
        "telegram.status_text",
        lang=user_lang,
        account_id=settings.IG_USER_ID or ("Не задан" if user_lang == "ru" else "Not set"),
        storage_mode=storage_mode,
        ai_status=ai_status,
        preset_tags_count=preset_tags_count,
        preset_mentions_count=preset_mentions_count
    )
    await message.answer(status_text, parse_mode="Markdown")


@router.message(Command("cancel"))
async def handle_cancel_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return
    user_lang = get_user_language(user_id=user_id, fallback_code=message.from_user.language_code)
    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    await message.answer(t("telegram.action_cancelled", lang=user_lang), parse_mode="Markdown")


@router.message(Command("tags"))
async def handle_tags_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return
    user_lang = get_user_language(user_id=user_id, fallback_code=message.from_user.language_code)
    presets = tag_service.get_preset_tags()
    await state.set_state(PostCreationStates.managing_preset_tags)
    msg = t("telegram.tags_management", lang=user_lang)
    await message.answer(msg, reply_markup=get_presets_manager_keyboard(presets, item_type="tag", language=user_lang), parse_mode="Markdown")


@router.message(Command("mentions"))
async def handle_mentions_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return
    user_lang = get_user_language(user_id=user_id, fallback_code=message.from_user.language_code)
    presets = mention_service.get_preset_mentions()
    await state.set_state(PostCreationStates.managing_preset_mentions)
    msg = t("telegram.mentions_management", lang=user_lang)
    await message.answer(msg, reply_markup=get_presets_manager_keyboard(presets, item_type="mention", language=user_lang), parse_mode="Markdown")


@router.message(Command("language"))
@router.message(Command("lang"))
async def handle_language_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return
    user_lang = get_user_language(user_id=user_id, fallback_code=message.from_user.language_code)
    await state.set_state(PostCreationStates.waiting_for_language)
    await message.answer(
        t("telegram.choose_language", lang=user_lang),
        reply_markup=get_language_keyboard(),
        parse_mode="Markdown"
    )


# ==============================================================================
# Media Receivers (Photos, Videos, Documents & Albums/Media Groups)
# ==============================================================================

async def _process_collected_media_group(media_group_id: str, bot: Bot, state: FSMContext):
    await asyncio.sleep(0.8)
    messages = _media_group_buffers.pop(media_group_id, [])
    _media_group_tasks.pop(media_group_id, None)

    if not messages:
        return

    first_msg = messages[0]
    user_id = first_msg.from_user.id
    user_lang = get_user_language(user_id=user_id, fallback_code=first_msg.from_user.language_code)
    logger.info("Processing media group %s with %d items for user_id=%s (lang=%s)", media_group_id, len(messages), user_id, user_lang)

    status_note = await first_msg.answer(t("telegram.loading_album", lang=user_lang, count=len(messages)), parse_mode="Markdown")

    media_items: List[Dict[str, Any]] = []
    user_instructions = ""
    cover_image_bytes: Optional[bytes] = None

    for idx, msg in enumerate(messages):
        if msg.caption and not user_instructions:
            user_instructions = msg.caption

        if msg.photo:
            photo = msg.photo[-1]
            p_file = await bot.get_file(photo.file_id)
            p_io = io.BytesIO()
            await bot.download_file(p_file.file_path, p_io)
            data_bytes = p_io.getvalue()
            if not cover_image_bytes:
                cover_image_bytes = data_bytes
            media_items.append({
                "type": "photo",
                "is_video": False,
                "bytes": data_bytes,
                "mime_type": "image/jpeg",
                "filename": f"carousel_item_{idx+1}.jpg"
            })

        elif msg.video:
            video = msg.video
            v_file = await bot.get_file(video.file_id)
            v_io = io.BytesIO()
            await bot.download_file(v_file.file_path, v_io)
            data_bytes = v_io.getvalue()
            media_items.append({
                "type": "video",
                "is_video": True,
                "bytes": data_bytes,
                "mime_type": "video/mp4",
                "filename": f"carousel_item_{idx+1}.mp4"
            })

        elif msg.document:
            doc = msg.document
            mime = (doc.mime_type or "").lower()
            is_vid = mime.startswith("video/") or (doc.file_name or "").lower().endswith((".mp4", ".mov"))
            d_file = await bot.get_file(doc.file_id)
            d_io = io.BytesIO()
            await bot.download_file(d_file.file_path, d_io)
            data_bytes = d_io.getvalue()
            if not is_vid and not cover_image_bytes:
                cover_image_bytes = data_bytes
            media_items.append({
                "type": "video" if is_vid else "photo",
                "is_video": is_vid,
                "bytes": data_bytes,
                "mime_type": "video/mp4" if is_vid else "image/jpeg",
                "filename": f"carousel_item_{idx+1}.mp4" if is_vid else f"carousel_item_{idx+1}.jpg"
            })

    try:
        await status_note.delete()
    except Exception:
        pass

    if not media_items:
        await first_msg.answer(t("common.error_occurred", lang=user_lang))
        return

    photos_count = sum(1 for m in media_items if not m["is_video"])
    videos_count = sum(1 for m in media_items if m["is_video"])

    await state.clear()
    await state.update_data(
        media_items=media_items,
        is_album=True,
        has_video=videos_count > 0,
        cover_image_bytes=cover_image_bytes,
        instructions=user_instructions,
        language=user_lang,
        active_filter="ORIGINAL",
        active_font="MODERN"
    )
    await state.set_state(PostCreationStates.waiting_for_language)

    summary_text = t("telegram.album_received", lang=user_lang, total=len(media_items), photos=photos_count, videos=videos_count)
    await first_msg.answer(summary_text, reply_markup=get_language_keyboard(), parse_mode="Markdown")


@router.message(F.media_group_id)
async def handle_media_group_item(message: types.Message, state: FSMContext, bot: Bot):
    if not is_user_allowed(message.from_user.id):
        return

    gid = message.media_group_id
    if gid not in _media_group_buffers:
        _media_group_buffers[gid] = []
    _media_group_buffers[gid].append(message)

    if gid in _media_group_tasks and not _media_group_tasks[gid].done():
        _media_group_tasks[gid].cancel()

    _media_group_tasks[gid] = asyncio.create_task(_process_collected_media_group(gid, bot, state))


@router.message(F.photo)
async def handle_single_photo(message: types.Message, state: FSMContext, bot: Bot):
    if message.media_group_id:
        return
    user_id = message.from_user.id
    user_lang = get_user_language(user_id=user_id, fallback_code=message.from_user.language_code)
    logger.info("Received single photo from user_id=%s (lang=%s)", user_id, user_lang)
    if not is_user_allowed(user_id):
        await message.answer(t("telegram.access_denied", lang=user_lang), parse_mode="Markdown")
        return

    photo = message.photo[-1]
    photo_file = await bot.get_file(photo.file_id)
    photo_io = io.BytesIO()
    await bot.download_file(photo_file.file_path, photo_io)
    raw_image_bytes = photo_io.getvalue()

    media_items = [{
        "type": "photo",
        "is_video": False,
        "bytes": raw_image_bytes,
        "mime_type": "image/jpeg",
        "filename": "post_photo.jpg"
    }]

    await state.clear()
    await state.update_data(
        raw_image_bytes=raw_image_bytes,
        media_items=media_items,
        is_album=False,
        has_video=False,
        cover_image_bytes=raw_image_bytes,
        instructions=message.caption or "",
        language=user_lang,
        active_filter="ORIGINAL",
        active_font="MODERN"
    )
    await state.set_state(PostCreationStates.waiting_for_language)

    await message.answer(
        t("telegram.choose_language", lang=user_lang),
        reply_markup=get_language_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.video)
async def handle_single_video(message: types.Message, state: FSMContext, bot: Bot):
    if message.media_group_id:
        return
    user_id = message.from_user.id
    user_lang = get_user_language(user_id=user_id, fallback_code=message.from_user.language_code)
    logger.info("Received single video from user_id=%s (lang=%s)", user_id, user_lang)
    if not is_user_allowed(user_id):
        await message.answer(t("telegram.access_denied", lang=user_lang), parse_mode="Markdown")
        return

    video = message.video
    status_msg = await message.answer(t("telegram.loading_video", lang=user_lang), parse_mode="Markdown")

    video_file = await bot.get_file(video.file_id)
    video_io = io.BytesIO()
    await bot.download_file(video_file.file_path, video_io)
    video_bytes = video_io.getvalue()

    media_items = [{
        "type": "video",
        "is_video": True,
        "bytes": video_bytes,
        "mime_type": "video/mp4",
        "filename": "post_video.mp4"
    }]

    await status_msg.delete()

    await state.clear()
    await state.update_data(
        media_items=media_items,
        is_album=False,
        has_video=True,
        instructions=message.caption or "",
        language=user_lang,
        active_filter="ORIGINAL",
        active_font="MODERN"
    )
    await state.set_state(PostCreationStates.waiting_for_language)

    await message.answer(
        t("telegram.video_received", lang=user_lang),
        reply_markup=get_language_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.document)
async def handle_single_document(message: types.Message, state: FSMContext, bot: Bot):
    if message.media_group_id:
        return
    user_id = message.from_user.id
    user_lang = get_user_language(user_id=user_id, fallback_code=message.from_user.language_code)
    logger.info("Received document from user_id=%s (lang=%s)", user_id, user_lang)
    if not is_user_allowed(user_id):
        await message.answer(t("telegram.access_denied", lang=user_lang), parse_mode="Markdown")
        return

    doc = message.document
    mime = (doc.mime_type or "").lower()
    filename = (doc.file_name or "").lower()

    is_image = mime.startswith("image/") or filename.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp"))
    is_video = mime.startswith("video/") or filename.endswith((".mp4", ".mov"))

    if not is_image and not is_video:
        await message.answer(
            t("telegram.unsupported_file_format", lang=user_lang, filename=doc.file_name or "Документ", mime=doc.mime_type or "неизвестный тип"),
            parse_mode="Markdown"
        )
        return

    file_info = await bot.get_file(doc.file_id)
    d_io = io.BytesIO()
    await bot.download_file(file_info.file_path, d_io)
    data_bytes = d_io.getvalue()

    media_items = [{
        "type": "video" if is_video else "photo",
        "is_video": is_video,
        "bytes": data_bytes,
        "mime_type": "video/mp4" if is_video else "image/jpeg",
        "filename": "post_video.mp4" if is_video else "post_photo.jpg"
    }]

    await state.clear()
    await state.update_data(
        raw_image_bytes=None if is_video else data_bytes,
        media_items=media_items,
        is_album=False,
        has_video=is_video,
        cover_image_bytes=None if is_video else data_bytes,
        instructions=message.caption or "",
        language=user_lang,
        active_filter="ORIGINAL",
        active_font="MODERN"
    )
    await state.set_state(PostCreationStates.waiting_for_language)

    await message.answer(
        t("telegram.choose_language", lang=user_lang),
        reply_markup=get_language_keyboard(),
        parse_mode="Markdown"
    )


# ==============================================================================
# Step 2: Language Selected -> Persist Preference & Ask for Instructions
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_language, F.data.startswith("lang_"))
async def handle_language_selected(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    raw_lang = callback.data.replace("lang_", "")  # "ru" or "en"
    lang = set_user_language(callback.from_user.id, raw_lang)
    await state.update_data(language=lang)

    data = await state.get_data()
    existing_instructions = data.get("instructions", "")
    is_album = data.get("is_album", False)
    has_video = data.get("has_video", False)

    if existing_instructions:
        await state.set_state(PostCreationStates.waiting_for_format)
        prompt_text = t("telegram.theme_selected_choose_format", lang=lang, instructions=existing_instructions)
        await callback.message.edit_text(
            prompt_text,
            reply_markup=get_format_keyboard(lang, is_album=is_album, has_video=has_video),
            parse_mode="Markdown"
        )
        return

    await state.set_state(PostCreationStates.waiting_for_instructions)
    prompt_text = t("telegram.instructions_prompt", lang=lang)

    await callback.message.edit_text(
        prompt_text,
        reply_markup=get_instructions_keyboard(lang),
        parse_mode="Markdown"
    )


# ==============================================================================
# Step 3: Instructions (Voice, Text, or Skip) -> Ask for Format
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_instructions, F.data == "act_skip_instructions")
async def handle_skip_instructions(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    is_album = data.get("is_album", False)
    has_video = data.get("has_video", False)

    await state.update_data(instructions="", language=lang)
    await state.set_state(PostCreationStates.waiting_for_format)

    prompt_text = t("telegram.choose_format", lang=lang)
    await callback.message.edit_text(
        prompt_text,
        reply_markup=get_format_keyboard(lang, is_album=is_album, has_video=has_video),
        parse_mode="Markdown"
    )


@router.message(PostCreationStates.waiting_for_instructions, F.voice | F.audio)
async def handle_voice_instructions(message: types.Message, state: FSMContext, bot: Bot):
    if not is_user_allowed(message.from_user.id):
        return

    data = await state.get_data()
    lang = get_user_language(user_id=message.from_user.id, state_lang=data.get("language"))
    is_album = data.get("is_album", False)
    has_video = data.get("has_video", False)

    progress_msg = await message.answer(
        t("telegram.transcribing_voice_instructions", lang=lang),
        parse_mode="Markdown"
    )

    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file_info = await bot.get_file(file_id)
        audio_io = io.BytesIO()
        await bot.download_file(file_info.file_path, audio_io)
        audio_bytes = audio_io.getvalue()

        transcription = await ai_service.transcribe_audio(audio_bytes, mime_type="audio/ogg")
        await state.update_data(instructions=transcription, language=lang)
        await state.set_state(PostCreationStates.waiting_for_format)

        await progress_msg.delete()

        prompt_text = t("telegram.transcribed_voice", lang=lang, transcription=transcription or ("голос принят" if lang == "ru" else "voice received"))
        await message.answer(
            prompt_text,
            reply_markup=get_format_keyboard(lang, is_album=is_album, has_video=has_video),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.exception("Error processing voice instructions: %s", e)
        await progress_msg.edit_text(
            f"⚠️ Ошибка обработки голоса: `{str(e)}`",
            reply_markup=get_instructions_keyboard(lang),
            parse_mode="Markdown"
        )


@router.message(PostCreationStates.waiting_for_instructions, F.text)
async def handle_text_instructions(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        return

    instructions = message.text.strip()
    data = await state.get_data()
    lang = get_user_language(user_id=message.from_user.id, state_lang=data.get("language"))
    is_album = data.get("is_album", False)
    has_video = data.get("has_video", False)

    await state.update_data(instructions=instructions, language=lang)
    await state.set_state(PostCreationStates.waiting_for_format)

    prompt_text = t("telegram.text_instructions_received", lang=lang, instructions=instructions)
    await message.answer(
        prompt_text,
        reply_markup=get_format_keyboard(lang, is_album=is_album, has_video=has_video),
        parse_mode="Markdown"
    )


# ==============================================================================
# Step 4: Format Selected -> Multimodal AI Generation & Preview
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_format, F.data.startswith("fmt_"))
async def handle_format_selected(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    post_type = callback.data.replace("fmt_", "")

    data = await state.get_data()
    media_items = data.get("media_items", [])
    raw_image_bytes = data.get("raw_image_bytes")
    instructions = data.get("instructions", "")
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")
    is_story = (post_type in ("STORY", "CAROUSEL_STORY"))

    status_text = t("telegram.analyzing_media", lang=lang)
    status_msg = await callback.message.edit_text(status_text)

    # If Story, generate overlay text by default
    photo_overlay_text = ""
    has_photo_text = False

    first_photo_bytes = next((m["bytes"] for m in media_items if not m["is_video"]), raw_image_bytes)
    if is_story and first_photo_bytes:
        photo_overlay_text = await ai_service.generate_story_overlay_text(
            image_bytes=first_photo_bytes,
            instructions=instructions,
            language=lang
        )
        has_photo_text = bool(photo_overlay_text)

    # Render media items with filter and font
    processed_items, cover_image_bytes = render_media_items(
        media_items=media_items,
        post_type=post_type,
        has_photo_text=has_photo_text,
        photo_overlay_text=photo_overlay_text,
        active_filter=active_filter,
        active_font=active_font
    )

    # AI generation for post caption
    raw_caption = await ai_service.generate_caption(
        media_items=processed_items,
        image_bytes=raw_image_bytes,
        instructions=instructions,
        post_format=post_type,
        language=lang
    )

    body_text, ai_tags = TagService.extract_tags_and_body(raw_caption)
    preset_tags = tag_service.get_preset_tags()
    preset_mentions = mention_service.get_preset_mentions()

    available_tags = list(dict.fromkeys(ai_tags + preset_tags))
    active_tags = list(ai_tags) if ai_tags else list(preset_tags[:4])

    available_mentions = list(preset_mentions)
    active_mentions = list(preset_mentions)

    final_caption = assemble_full_caption(body_text, active_mentions, active_tags)
    has_photos = any(not m["is_video"] for m in media_items)

    await state.update_data(
        media_items=processed_items,
        post_type=post_type,
        caption_body=body_text,
        available_tags=available_tags,
        active_tags=active_tags,
        available_mentions=available_mentions,
        active_mentions=active_mentions,
        caption=final_caption,
        is_story=is_story,
        photo_overlay_text=photo_overlay_text,
        has_photo_text=has_photo_text,
        active_filter=active_filter,
        active_font=active_font,
        language=lang,
        cover_image_bytes=cover_image_bytes
    )
    await state.set_state(PostCreationStates.waiting_for_approval)

    try:
        await status_msg.delete()
    except Exception:
        pass

    format_name = get_localized_format_name(post_type, len(media_items), lang)

    await send_post_preview(
        target=callback.message,
        cover_image_bytes=cover_image_bytes,
        format_name=format_name,
        caption=final_caption,
        active_tags_count=len(active_tags),
        active_mentions_count=len(active_mentions),
        media_count=len(media_items),
        show_photo_text_button=has_photos,
        has_photo_text=has_photo_text,
        active_filter=active_filter,
        active_font=active_font,
        language=lang
    )


async def send_post_preview(
    target: types.Message,
    cover_image_bytes: Optional[bytes],
    format_name: str,
    caption: str,
    active_tags_count: int = 0,
    active_mentions_count: int = 0,
    media_count: int = 1,
    show_photo_text_button: bool = True,
    has_photo_text: bool = False,
    active_filter: str = "ORIGINAL",
    active_font: str = "MODERN",
    language: str = "ru"
):
    media_info = f" ({media_count} {'медиафайлов' if language.lower().startswith('ru') else 'media items'})" if media_count > 1 else ""
    preview_header = t("telegram.preview_header", lang=language, format_name=format_name, media_info=media_info)
    full_caption = f"{preview_header}\n\n{caption}".strip()

    keyboard = get_approval_keyboard(
        active_tags_count=active_tags_count,
        active_mentions_count=active_mentions_count,
        language=language,
        show_photo_text_button=show_photo_text_button,
        has_photo_text=has_photo_text,
        active_filter=active_filter,
        active_font=active_font
    )

    if cover_image_bytes:
        preview_file = BufferedInputFile(cover_image_bytes, filename="preview.jpg")
        if len(full_caption) <= 1000:
            try:
                await target.answer_photo(
                    photo=preview_file,
                    caption=full_caption,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                return
            except Exception as e:
                logger.warning("Markdown parse error in photo preview: %s, falling back to plain text", e)
                try:
                    await target.answer_photo(
                        photo=preview_file,
                        caption=full_caption,
                        reply_markup=keyboard,
                        parse_mode=None
                    )
                    return
                except Exception:
                    pass

        await target.answer_photo(
            photo=preview_file,
            caption=preview_header,
            parse_mode="Markdown"
        )

    try:
        await target.answer(text=full_caption if not cover_image_bytes else caption, reply_markup=keyboard, parse_mode="Markdown")
    except Exception:
        await target.answer(text=full_caption if not cover_image_bytes else caption, reply_markup=keyboard, parse_mode=None)


# ==============================================================================
# Step 5: Visual Filters & Effects Menu Handlers
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_open_filter_menu")
async def handle_open_filter_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    active_filter = data.get("active_filter", "ORIGINAL")
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    msg = t("telegram.filter_menu_intro", lang=lang)

    await callback.message.answer(
        msg,
        reply_markup=get_filter_selection_keyboard(active_filter=active_filter, language=lang),
        parse_mode="Markdown"
    )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data.startswith("apply_filter_"))
async def handle_apply_filter(callback: types.CallbackQuery, state: FSMContext):
    new_filter = callback.data.replace("apply_filter_", "")
    data = await state.get_data()
    media_items = data.get("media_items", [])
    post_type = data.get("post_type", "FEED_PORTRAIT")
    has_photo_text = data.get("has_photo_text", False)
    photo_overlay_text = data.get("photo_overlay_text", "")
    active_font = data.get("active_font", "MODERN")
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    # Re-render media items with new filter
    processed_items, cover_image_bytes = render_media_items(
        media_items=media_items,
        post_type=post_type,
        has_photo_text=has_photo_text,
        photo_overlay_text=photo_overlay_text,
        active_filter=new_filter,
        active_font=active_font
    )

    await state.update_data(
        media_items=processed_items,
        active_filter=new_filter,
        cover_image_bytes=cover_image_bytes
    )

    filter_info = FILTER_REGISTRY.get(new_filter, {})
    filter_name = filter_info.get("name_ru" if lang == "ru" else "name_en", new_filter)
    await callback.answer(t("telegram.filter_applied", lang=lang, filter_name=filter_name))

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    format_name = get_localized_format_name(post_type, len(media_items), lang)
    active_tags = data.get("active_tags", [])
    active_mentions = data.get("active_mentions", [])
    caption = data.get("caption", "")
    has_photos = any(not m["is_video"] for m in media_items)

    await send_post_preview(
        target=callback.message,
        cover_image_bytes=cover_image_bytes,
        format_name=format_name,
        caption=caption,
        active_tags_count=len(active_tags),
        active_mentions_count=len(active_mentions),
        media_count=len(media_items),
        show_photo_text_button=has_photos,
        has_photo_text=has_photo_text,
        active_filter=new_filter,
        active_font=active_font,
        language=lang
    )


# ==============================================================================
# Step 6: Decorative Font Selection Handlers
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_open_font_menu")
async def handle_open_font_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    active_font = data.get("active_font", "MODERN")
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    msg = t("telegram.font_menu_intro", lang=lang)

    await callback.message.answer(
        msg,
        reply_markup=get_font_selection_keyboard(active_font=active_font, language=lang),
        parse_mode="Markdown"
    )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data.startswith("apply_font_"))
async def handle_apply_font(callback: types.CallbackQuery, state: FSMContext):
    new_font = callback.data.replace("apply_font_", "")
    data = await state.get_data()
    media_items = data.get("media_items", [])
    post_type = data.get("post_type", "FEED_PORTRAIT")
    has_photo_text = data.get("has_photo_text", False)
    photo_overlay_text = data.get("photo_overlay_text", "")
    active_filter = data.get("active_filter", "ORIGINAL")
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    # If photo text wasn't enabled, automatically enable it when a font style is chosen
    if not has_photo_text and not photo_overlay_text:
        first_photo_bytes = next((m["bytes"] for m in media_items if not m["is_video"]), None)
        photo_overlay_text = await ai_service.generate_story_overlay_text(
            image_bytes=first_photo_bytes,
            instructions=data.get("instructions", ""),
            language=lang
        )
        has_photo_text = True
    elif not has_photo_text and photo_overlay_text:
        has_photo_text = True

    processed_items, cover_image_bytes = render_media_items(
        media_items=media_items,
        post_type=post_type,
        has_photo_text=has_photo_text,
        photo_overlay_text=photo_overlay_text,
        active_filter=active_filter,
        active_font=new_font
    )

    await state.update_data(
        media_items=processed_items,
        active_font=new_font,
        has_photo_text=has_photo_text,
        photo_overlay_text=photo_overlay_text,
        cover_image_bytes=cover_image_bytes
    )

    font_info = FONT_REGISTRY.get(new_font, {})
    font_name = font_info.get("name_ru" if lang == "ru" else "name_en", new_font)
    await callback.answer(t("telegram.font_applied", lang=lang, font_name=font_name))

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    format_name = get_localized_format_name(post_type, len(media_items), lang)
    active_tags = data.get("active_tags", [])
    active_mentions = data.get("active_mentions", [])
    caption = data.get("caption", "")
    has_photos = any(not m["is_video"] for m in media_items)

    await send_post_preview(
        target=callback.message,
        cover_image_bytes=cover_image_bytes,
        format_name=format_name,
        caption=caption,
        active_tags_count=len(active_tags),
        active_mentions_count=len(active_mentions),
        media_count=len(media_items),
        show_photo_text_button=has_photos,
        has_photo_text=has_photo_text,
        active_filter=active_filter,
        active_font=new_font,
        language=lang
    )


# ==============================================================================
# Step 7: On-Photo Text Overlay Handlers (Toggle & Edit)
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_toggle_photo_text")
async def handle_toggle_photo_text(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    has_photo_text = data.get("has_photo_text", False)
    photo_overlay_text = data.get("photo_overlay_text", "")
    media_items = data.get("media_items", [])
    post_type = data.get("post_type", "FEED_PORTRAIT")
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    instructions = data.get("instructions", "")

    new_has_photo_text = not has_photo_text

    if new_has_photo_text and not photo_overlay_text:
        first_photo_bytes = next((m["bytes"] for m in media_items if not m["is_video"]), None)
        photo_overlay_text = await ai_service.generate_story_overlay_text(
            image_bytes=first_photo_bytes,
            instructions=instructions,
            language=lang
        )

    processed_items, cover_image_bytes = render_media_items(
        media_items=media_items,
        post_type=post_type,
        has_photo_text=new_has_photo_text,
        photo_overlay_text=photo_overlay_text,
        active_filter=active_filter,
        active_font=active_font
    )

    await state.update_data(
        media_items=processed_items,
        has_photo_text=new_has_photo_text,
        photo_overlay_text=photo_overlay_text,
        cover_image_bytes=cover_image_bytes
    )

    status_txt = t("telegram.photo_text_on" if new_has_photo_text else "telegram.photo_text_off", lang=lang)
    await callback.answer(status_txt)

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    format_name = get_localized_format_name(post_type, len(media_items), lang)
    active_tags = data.get("active_tags", [])
    active_mentions = data.get("active_mentions", [])
    caption = data.get("caption", "")

    await send_post_preview(
        target=callback.message,
        cover_image_bytes=cover_image_bytes,
        format_name=format_name,
        caption=caption,
        active_tags_count=len(active_tags),
        active_mentions_count=len(active_mentions),
        media_count=len(media_items),
        show_photo_text_button=True,
        has_photo_text=new_has_photo_text,
        active_filter=active_filter,
        active_font=active_font,
        language=lang
    )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_edit_photo_text")
async def handle_start_edit_photo_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    current_overlay = data.get("photo_overlay_text", "")

    await state.set_state(PostCreationStates.waiting_for_photo_text_edit)
    msg = t("telegram.edit_photo_text_intro", lang=lang, current_overlay=current_overlay)
    await callback.message.answer(msg, reply_markup=get_cancel_keyboard(lang), parse_mode="Markdown")


@router.message(PostCreationStates.waiting_for_photo_text_edit, F.voice | F.audio)
async def handle_voice_photo_text_edit(message: types.Message, state: FSMContext, bot: Bot):
    if not is_user_allowed(message.from_user.id):
        return

    data = await state.get_data()
    lang = get_user_language(user_id=message.from_user.id, state_lang=data.get("language"))
    media_items = data.get("media_items", [])
    post_type = data.get("post_type", "FEED_PORTRAIT")
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")

    progress_msg = await message.answer(t("telegram.transcribing_voice", lang=lang))

    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file_info = await bot.get_file(file_id)
        audio_io = io.BytesIO()
        await bot.download_file(file_info.file_path, audio_io)
        audio_bytes = audio_io.getvalue()

        new_text = await ai_service.transcribe_audio(audio_bytes, mime_type="audio/ogg")
        await progress_msg.delete()

        processed_items, cover_image_bytes = render_media_items(
            media_items=media_items,
            post_type=post_type,
            has_photo_text=True,
            photo_overlay_text=new_text,
            active_filter=active_filter,
            active_font=active_font
        )

        await state.update_data(
            media_items=processed_items,
            has_photo_text=True,
            photo_overlay_text=new_text,
            cover_image_bytes=cover_image_bytes
        )
        await state.set_state(PostCreationStates.waiting_for_approval)

        await message.answer(t("telegram.photo_text_updated", lang=lang, text=new_text), parse_mode="Markdown")

        format_name = get_localized_format_name(post_type, len(media_items), lang)
        active_tags = data.get("active_tags", [])
        active_mentions = data.get("active_mentions", [])
        caption = data.get("caption", "")

        await send_post_preview(
            target=message,
            cover_image_bytes=cover_image_bytes,
            format_name=format_name,
            caption=caption,
            active_tags_count=len(active_tags),
            active_mentions_count=len(active_mentions),
            media_count=len(media_items),
            show_photo_text_button=True,
            has_photo_text=True,
            active_filter=active_filter,
            active_font=active_font,
            language=lang
        )

    except Exception as e:
        logger.exception("Error in voice photo text edit: %s", e)
        await progress_msg.edit_text(f"⚠️ Ошибка: `{str(e)}`", reply_markup=get_cancel_keyboard(lang))


@router.message(PostCreationStates.waiting_for_photo_text_edit, F.text)
async def handle_text_photo_text_edit(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        return

    new_text = message.text.strip()
    data = await state.get_data()
    lang = get_user_language(user_id=message.from_user.id, state_lang=data.get("language"))
    media_items = data.get("media_items", [])
    post_type = data.get("post_type", "FEED_PORTRAIT")
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")

    processed_items, cover_image_bytes = render_media_items(
        media_items=media_items,
        post_type=post_type,
        has_photo_text=True,
        photo_overlay_text=new_text,
        active_filter=active_filter,
        active_font=active_font
    )

    await state.update_data(
        media_items=processed_items,
        has_photo_text=True,
        photo_overlay_text=new_text,
        cover_image_bytes=cover_image_bytes
    )
    await state.set_state(PostCreationStates.waiting_for_approval)

    await message.answer(t("telegram.photo_text_updated", lang=lang, text=new_text), parse_mode="Markdown")

    format_name = get_localized_format_name(post_type, len(media_items), lang)
    active_tags = data.get("active_tags", [])
    active_mentions = data.get("active_mentions", [])
    caption = data.get("caption", "")

    await send_post_preview(
        target=message,
        cover_image_bytes=cover_image_bytes,
        format_name=format_name,
        caption=caption,
        active_tags_count=len(active_tags),
        active_mentions_count=len(active_mentions),
        media_count=len(media_items),
        show_photo_text_button=True,
        has_photo_text=True,
        active_filter=active_filter,
        active_font=active_font,
        language=lang
    )


# ==============================================================================
# Step 8: Interactive Tag Editor (#)
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_open_tag_editor")
async def handle_open_tag_editor(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    available_tags = data.get("available_tags", [])
    active_tags = set(data.get("active_tags", []))
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    prompt_text = t("telegram.tag_editor_intro", lang=lang)

    await callback.message.answer(
        prompt_text,
        reply_markup=get_tag_editor_keyboard(available_tags, active_tags, lang),
        parse_mode="Markdown"
    )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data.startswith("tag_toggle_"))
async def handle_tag_toggle(callback: types.CallbackQuery, state: FSMContext):
    tag_idx = int(callback.data.replace("tag_toggle_", ""))
    data = await state.get_data()
    available_tags = data.get("available_tags", [])
    active_tags = set(data.get("active_tags", []))
    caption_body = data.get("caption_body", "")
    active_mentions = data.get("active_mentions", [])
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    if 0 <= tag_idx < len(available_tags):
        tag = available_tags[tag_idx]
        if tag in active_tags:
            active_tags.remove(tag)
            await callback.answer(t("telegram.tag_removed", lang=lang, tag=tag))
        else:
            active_tags.add(tag)
            await callback.answer(t("telegram.tag_added", lang=lang, tag=tag))

        new_active_tags = [t_item for t_item in available_tags if t_item in active_tags]
        new_caption = assemble_full_caption(caption_body, active_mentions, new_active_tags)

        await state.update_data(
            active_tags=new_active_tags,
            caption=new_caption
        )

        await callback.message.edit_reply_markup(
            reply_markup=get_tag_editor_keyboard(available_tags, active_tags, lang)
        )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_add_custom_tag")
async def handle_ask_custom_tag(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    await state.set_state(PostCreationStates.waiting_for_custom_tag)

    msg = t("telegram.tag_add_custom_prompt", lang=lang)
    await callback.message.answer(msg, reply_markup=get_cancel_keyboard(lang), parse_mode="Markdown")


@router.message(PostCreationStates.waiting_for_custom_tag, F.text)
async def handle_custom_tag_input(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        return

    text = message.text.strip()
    data = await state.get_data()
    available_tags = data.get("available_tags", [])
    active_tags = set(data.get("active_tags", []))
    caption_body = data.get("caption_body", "")
    active_mentions = data.get("active_mentions", [])
    lang = get_user_language(user_id=message.from_user.id, state_lang=data.get("language"))

    raw_words = text.split()
    added_count = 0
    for w in raw_words:
        clean = TagService.normalize_tag(w)
        if clean:
            if clean not in available_tags:
                available_tags.append(clean)
            active_tags.add(clean)
            added_count += 1

    new_active_tags = [t_item for t_item in available_tags if t_item in active_tags]
    new_caption = assemble_full_caption(caption_body, active_mentions, new_active_tags)

    await state.update_data(
        available_tags=available_tags,
        active_tags=new_active_tags,
        caption=new_caption
    )
    await state.set_state(PostCreationStates.waiting_for_approval)

    confirm_msg = t("telegram.tag_custom_added", lang=lang, count=added_count)
    await message.answer(confirm_msg)
    await message.answer(
        t("telegram.tag_editor_title", lang=lang),
        reply_markup=get_tag_editor_keyboard(available_tags, active_tags, lang),
        parse_mode="Markdown"
    )


# ==============================================================================
# Step 9: Interactive Mentions Editor (@)
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_open_mention_editor")
async def handle_open_mention_editor(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    available_mentions = data.get("available_mentions", [])
    active_mentions = set(data.get("active_mentions", []))
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    prompt_text = t("telegram.mention_editor_intro", lang=lang)

    await callback.message.answer(
        prompt_text,
        reply_markup=get_mention_editor_keyboard(available_mentions, active_mentions, lang),
        parse_mode="Markdown"
    )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data.startswith("men_toggle_"))
async def handle_mention_toggle(callback: types.CallbackQuery, state: FSMContext):
    men_idx = int(callback.data.replace("men_toggle_", ""))
    data = await state.get_data()
    available_mentions = data.get("available_mentions", [])
    active_mentions = set(data.get("active_mentions", []))
    caption_body = data.get("caption_body", "")
    active_tags = data.get("active_tags", [])
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    if 0 <= men_idx < len(available_mentions):
        mention = available_mentions[men_idx]
        if mention in active_mentions:
            active_mentions.remove(mention)
            await callback.answer(t("telegram.mention_removed", lang=lang, mention=mention))
        else:
            active_mentions.add(mention)
            await callback.answer(t("telegram.mention_added", lang=lang, mention=mention))

        new_active_mentions = [m for m in available_mentions if m in active_mentions]
        new_caption = assemble_full_caption(caption_body, new_active_mentions, active_tags)

        await state.update_data(
            active_mentions=new_active_mentions,
            caption=new_caption
        )

        await callback.message.edit_reply_markup(
            reply_markup=get_mention_editor_keyboard(available_mentions, active_mentions, lang)
        )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_add_custom_mention")
async def handle_ask_custom_mention(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    await state.set_state(PostCreationStates.waiting_for_custom_mention)

    msg = t("telegram.mention_add_custom_prompt", lang=lang)
    await callback.message.answer(msg, reply_markup=get_cancel_keyboard(lang), parse_mode="Markdown")


@router.message(PostCreationStates.waiting_for_custom_mention, F.text)
async def handle_custom_mention_input(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        return

    text = message.text.strip()
    data = await state.get_data()
    available_mentions = data.get("available_mentions", [])
    active_mentions = set(data.get("active_mentions", []))
    caption_body = data.get("caption_body", "")
    active_tags = data.get("active_tags", [])
    lang = get_user_language(user_id=message.from_user.id, state_lang=data.get("language"))

    raw_words = text.split()
    added_count = 0
    for w in raw_words:
        clean = MentionService.normalize_mention(w)
        if clean:
            if clean not in available_mentions:
                available_mentions.append(clean)
            active_mentions.add(clean)
            added_count += 1

    new_active_mentions = [m for m in available_mentions if m in active_mentions]
    new_caption = assemble_full_caption(caption_body, new_active_mentions, active_tags)

    await state.update_data(
        available_mentions=available_mentions,
        active_mentions=new_active_mentions,
        caption=new_caption
    )
    await state.set_state(PostCreationStates.waiting_for_approval)

    confirm_msg = t("telegram.mention_custom_added", lang=lang, count=added_count)
    await message.answer(confirm_msg)
    await message.answer(
        t("telegram.mention_editor_title", lang=lang),
        reply_markup=get_mention_editor_keyboard(available_mentions, active_mentions, lang),
        parse_mode="Markdown"
    )


# ==============================================================================
# Presets Management Submenu (Tags & Mentions)
# ==============================================================================

@router.callback_query(F.data.in_(["act_manage_preset_tags", "back_from_preset_tag"]))
async def handle_manage_preset_tags_view(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    presets = tag_service.get_preset_tags()

    msg = t("telegram.preset_tags_manage_intro", lang=lang)
    await callback.message.answer(msg, reply_markup=get_presets_manager_keyboard(presets, item_type="tag", language=lang), parse_mode="Markdown")


@router.callback_query(F.data.startswith("del_preset_tag_"))
async def handle_delete_preset_tag(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("del_preset_tag_", ""))
    presets = tag_service.get_preset_tags()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    if 0 <= idx < len(presets):
        removed = presets[idx]
        tag_service.remove_preset_tag(removed)
        await callback.answer(t("telegram.preset_tag_deleted", lang=lang, tag=removed))
        new_presets = tag_service.get_preset_tags()
        await callback.message.edit_reply_markup(
            reply_markup=get_presets_manager_keyboard(new_presets, item_type="tag", language=lang)
        )


@router.callback_query(F.data == "add_preset_tag")
async def handle_prompt_add_preset_tag(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    await state.set_state(PostCreationStates.adding_preset_tag)
    msg = t("telegram.preset_tag_prompt", lang=lang)
    await callback.message.answer(msg, reply_markup=get_cancel_keyboard(lang), parse_mode="Markdown")


@router.message(PostCreationStates.adding_preset_tag, F.text)
async def handle_save_new_preset_tag(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        return
    for w in message.text.strip().split():
        clean = TagService.normalize_tag(w)
        if clean:
            tag_service.add_preset_tag(clean)

    data = await state.get_data()
    lang = get_user_language(user_id=message.from_user.id, state_lang=data.get("language"))
    presets = tag_service.get_preset_tags()

    has_post = bool(data.get("media_items"))
    if has_post:
        avail = data.get("available_tags", [])
        for p in presets:
            if p not in avail:
                avail.append(p)
        await state.update_data(available_tags=avail)
        await state.set_state(PostCreationStates.waiting_for_approval)
    else:
        await state.set_state(PostCreationStates.waiting_for_media)

    await message.answer(t("telegram.preset_tag_saved", lang=lang))
    await message.answer(
        t("telegram.preset_tags_title", lang=lang),
        reply_markup=get_presets_manager_keyboard(presets, item_type="tag", language=lang),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.in_(["act_manage_preset_mentions", "back_from_preset_mention"]))
async def handle_manage_preset_mentions_view(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    presets = mention_service.get_preset_mentions()

    msg = t("telegram.preset_mentions_manage_intro", lang=lang)
    await callback.message.answer(msg, reply_markup=get_presets_manager_keyboard(presets, item_type="mention", language=lang), parse_mode="Markdown")


@router.callback_query(F.data.startswith("del_preset_mention_"))
async def handle_delete_preset_mention(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("del_preset_mention_", ""))
    presets = mention_service.get_preset_mentions()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    if 0 <= idx < len(presets):
        removed = presets[idx]
        mention_service.remove_preset_mention(removed)
        await callback.answer(t("telegram.preset_mention_deleted", lang=lang, mention=removed))
        new_presets = mention_service.get_preset_mentions()
        await callback.message.edit_reply_markup(
            reply_markup=get_presets_manager_keyboard(new_presets, item_type="mention", language=lang)
        )


@router.callback_query(F.data == "add_preset_mention")
async def handle_prompt_add_preset_mention(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    await state.set_state(PostCreationStates.adding_preset_mention)
    msg = t("telegram.preset_mention_prompt", lang=lang)
    await callback.message.answer(msg, reply_markup=get_cancel_keyboard(lang), parse_mode="Markdown")


@router.message(PostCreationStates.adding_preset_mention, F.text)
async def handle_save_new_preset_mention(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        return
    for w in message.text.strip().split():
        clean = MentionService.normalize_mention(w)
        if clean:
            mention_service.add_preset_mention(clean)

    data = await state.get_data()
    lang = get_user_language(user_id=message.from_user.id, state_lang=data.get("language"))
    presets = mention_service.get_preset_mentions()

    has_post = bool(data.get("media_items"))
    if has_post:
        avail = data.get("available_mentions", [])
        for p in presets:
            if p not in avail:
                avail.append(p)
        await state.update_data(available_mentions=avail)
        await state.set_state(PostCreationStates.waiting_for_approval)
    else:
        await state.set_state(PostCreationStates.waiting_for_media)

    await message.answer(t("telegram.preset_mention_saved", lang=lang))
    await message.answer(
        t("telegram.preset_mentions_title", lang=lang),
        reply_markup=get_presets_manager_keyboard(presets, item_type="mention", language=lang),
        parse_mode="Markdown"
    )


# ==============================================================================
# Step 10: AI-Powered Voice & Text Caption Refinement
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_edit")
async def handle_start_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    await state.set_state(PostCreationStates.waiting_for_edit)
    prompt_text = t("telegram.edit_caption_intro", lang=lang)

    await callback.message.answer(
        prompt_text,
        reply_markup=get_cancel_keyboard(lang),
        parse_mode="Markdown"
    )


@router.message(StateFilter(PostCreationStates.waiting_for_approval, PostCreationStates.waiting_for_edit), F.voice | F.audio)
async def handle_voice_correction(message: types.Message, state: FSMContext, bot: Bot):
    if not is_user_allowed(message.from_user.id):
        return

    data = await state.get_data()
    lang = get_user_language(user_id=message.from_user.id, state_lang=data.get("language"))
    current_caption = data.get("caption", "")
    media_items = data.get("media_items", [])
    raw_image_bytes = data.get("raw_image_bytes")
    cover_image_bytes = data.get("cover_image_bytes")
    post_type = data.get("post_type", "FEED_PORTRAIT")
    active_tags = data.get("active_tags", [])
    active_mentions = data.get("active_mentions", [])
    has_photo_text = data.get("has_photo_text", False)
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")

    progress_msg = await message.answer(
        t("telegram.listening_voice_correction", lang=lang),
        parse_mode="Markdown"
    )

    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file_info = await bot.get_file(file_id)
        audio_io = io.BytesIO()
        await bot.download_file(file_info.file_path, audio_io)
        audio_bytes = audio_io.getvalue()

        # Transcribe & Refine
        correction_transcript = await ai_service.transcribe_audio(audio_bytes, mime_type="audio/ogg")
        raw_refined_caption = await ai_service.refine_caption(
            current_caption=current_caption,
            correction_instructions=correction_transcript,
            image_bytes=raw_image_bytes,
            media_items=media_items,
            post_format=post_type,
            language=lang
        )

        body_text, new_ai_tags = TagService.extract_tags_and_body(raw_refined_caption)
        if new_ai_tags:
            available_tags = data.get("available_tags", [])
            for t_item in new_ai_tags:
                if t_item not in available_tags:
                    available_tags.append(t_item)
                if t_item not in active_tags:
                    active_tags.append(t_item)
            await state.update_data(available_tags=available_tags, active_tags=active_tags)

        final_caption = assemble_full_caption(body_text, active_mentions, active_tags)

        await state.update_data(
            caption_body=body_text,
            caption=final_caption,
            language=lang
        )
        await state.set_state(PostCreationStates.waiting_for_approval)

        await progress_msg.delete()

        format_name = get_localized_format_name(post_type, len(media_items), lang)
        feedback_note = t("telegram.voice_feedback_noted", lang=lang, text=correction_transcript) if correction_transcript else ""
        await message.answer(feedback_note, parse_mode="Markdown")

        has_photos = any(not m["is_video"] for m in media_items)

        await send_post_preview(
            target=message,
            cover_image_bytes=cover_image_bytes,
            format_name=format_name,
            caption=final_caption,
            active_tags_count=len(active_tags),
            active_mentions_count=len(active_mentions),
            media_count=len(media_items),
            show_photo_text_button=has_photos,
            has_photo_text=has_photo_text,
            active_filter=active_filter,
            active_font=active_font,
            language=lang
        )

    except Exception as e:
        logger.exception("Error during voice correction: %s", e)
        await progress_msg.edit_text(
            f"⚠️ Ошибка коррекции: `{str(e)}`",
            reply_markup=get_cancel_keyboard(lang),
            parse_mode="Markdown"
        )


@router.message(StateFilter(PostCreationStates.waiting_for_approval, PostCreationStates.waiting_for_edit), F.text)
async def handle_text_correction(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        return

    data = await state.get_data()
    lang = get_user_language(user_id=message.from_user.id, state_lang=data.get("language"))
    current_caption = data.get("caption", "")
    media_items = data.get("media_items", [])
    raw_image_bytes = data.get("raw_image_bytes")
    cover_image_bytes = data.get("cover_image_bytes")
    post_type = data.get("post_type", "FEED_PORTRAIT")
    active_tags = data.get("active_tags", [])
    active_mentions = data.get("active_mentions", [])
    has_photo_text = data.get("has_photo_text", False)
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")
    correction_text = message.text.strip()

    progress_msg = await message.answer(
        t("telegram.updating_caption_feedback", lang=lang),
        parse_mode="Markdown"
    )

    try:
        raw_refined_caption = await ai_service.refine_caption(
            current_caption=current_caption,
            correction_instructions=correction_text,
            image_bytes=raw_image_bytes,
            media_items=media_items,
            post_format=post_type,
            language=lang
        )

        body_text, new_ai_tags = TagService.extract_tags_and_body(raw_refined_caption)
        if new_ai_tags:
            available_tags = data.get("available_tags", [])
            for t_item in new_ai_tags:
                if t_item not in available_tags:
                    available_tags.append(t_item)
                if t_item not in active_tags:
                    active_tags.append(t_item)
            await state.update_data(available_tags=available_tags, active_tags=active_tags)

        final_caption = assemble_full_caption(body_text, active_mentions, active_tags)

        await state.update_data(
            caption_body=body_text,
            caption=final_caption,
            language=lang
        )
        await state.set_state(PostCreationStates.waiting_for_approval)

        await progress_msg.delete()

        format_name = get_localized_format_name(post_type, len(media_items), lang)
        has_photos = any(not m["is_video"] for m in media_items)

        await send_post_preview(
            target=message,
            cover_image_bytes=cover_image_bytes,
            format_name=format_name,
            caption=final_caption,
            active_tags_count=len(active_tags),
            active_mentions_count=len(active_mentions),
            media_count=len(media_items),
            show_photo_text_button=has_photos,
            has_photo_text=has_photo_text,
            active_filter=active_filter,
            active_font=active_font,
            language=lang
        )

    except Exception as e:
        logger.exception("Error during text correction: %s", e)
        await progress_msg.edit_text(
            f"⚠️ Ошибка коррекции: `{str(e)}`",
            reply_markup=get_cancel_keyboard(lang),
            parse_mode="Markdown"
        )


# ==============================================================================
# Step 11: Publishing (Single or Carousel / Mixed Media)
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_publish")
async def handle_publish(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    media_items = data.get("media_items", [])
    caption = data.get("caption", "")
    is_story = data.get("is_story", False)
    is_album = data.get("is_album", False)
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    await callback.message.edit_reply_markup(reply_markup=None)

    progress_msg = await callback.message.answer(
        t("telegram.publishing_step_1", lang=lang, count=len(media_items)),
        parse_mode="Markdown"
    )

    try:
        # Step 1: Upload all media items to public R2/S3
        uploaded_media_urls: List[Dict[str, Any]] = []
        for idx, item in enumerate(media_items):
            content_bytes = item.get("processed_bytes") or item["bytes"]
            url = await storage_service.upload_media(
                media_bytes=content_bytes,
                filename=item.get("filename"),
                content_type=item.get("mime_type"),
                is_video=item.get("is_video", False)
            )
            uploaded_media_urls.append({
                "url": url,
                "is_video": item.get("is_video", False)
            })

        # Step 2: Handle publishing depending on album vs single
        if is_album:
            await progress_msg.edit_text(
                t("telegram.publishing_step_2_carousel", lang=lang, count=len(uploaded_media_urls)),
                parse_mode="Markdown"
            )

            item_container_ids: List[str] = []
            for item in uploaded_media_urls:
                cid = await instagram_service.create_carousel_item_container(
                    media_url=item["url"],
                    is_video=item["is_video"]
                )
                item_container_ids.append(cid)

            for cid in item_container_ids:
                await instagram_service.wait_for_container_ready(cid, max_retries=15, delay_seconds=2)

            parent_id = await instagram_service.create_carousel_parent_container(
                children_ids=item_container_ids,
                caption=caption
            )

            await progress_msg.edit_text(
                t("telegram.publishing_step_3_carousel", lang=lang),
                parse_mode="Markdown"
            )
            post_id = await instagram_service.publish_container(parent_id, max_retries=15)
            target_type_str = f"Карусель / Альбом ({len(media_items)} файлов)" if lang == "ru" else f"Carousel ({len(media_items)} items)"

        else:
            await progress_msg.edit_text(
                t("telegram.publishing_step_2_single", lang=lang),
                parse_mode="Markdown"
            )
            first_item = uploaded_media_urls[0]
            creation_id = await instagram_service.create_media_container(
                image_url=first_item["url"] if not first_item["is_video"] else None,
                video_url=first_item["url"] if first_item["is_video"] else None,
                is_video=first_item["is_video"],
                caption=caption,
                is_story=is_story
            )
            post_id = await instagram_service.publish_container(creation_id, max_retries=15)
            if lang == "ru":
                target_type_str = "История (Story)" if is_story else ("Reels Video" if first_item["is_video"] else "Пост в ленту (Feed Post)")
            else:
                target_type_str = "Story" if is_story else ("Reels Video" if first_item["is_video"] else "Feed Post")

        success_msg = t("telegram.publishing_success", lang=lang, format=target_type_str, post_id=post_id)
        await progress_msg.edit_text(success_msg, parse_mode="Markdown")
        await state.clear()
        await state.set_state(PostCreationStates.waiting_for_media)

    except Exception as e:
        logger.exception("Error during Instagram publishing: %s", e)
        await progress_msg.edit_text(
            t("telegram.publishing_error", lang=lang, error=str(e)),
            reply_markup=get_cancel_keyboard(lang),
            parse_mode="Markdown"
        )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_regenerate")
async def handle_regenerate(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    instructions = data.get("instructions", "")
    post_type = data.get("post_type", "FEED_PORTRAIT")
    media_items = data.get("media_items", [])
    raw_image_bytes = data.get("raw_image_bytes")
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    active_mentions = data.get("active_mentions", [])
    is_story = (post_type in ("STORY", "CAROUSEL_STORY"))

    await callback.answer(t("telegram.regenerating_caption", lang=lang))

    first_photo_bytes = next((m["bytes"] for m in media_items if not m["is_video"]), raw_image_bytes)
    photo_overlay_text = ""
    has_photo_text = False
    if is_story and first_photo_bytes:
        photo_overlay_text = await ai_service.generate_story_overlay_text(
            image_bytes=first_photo_bytes,
            instructions=instructions,
            language=lang
        )
        has_photo_text = bool(photo_overlay_text)

    processed_items, cover_image_bytes = render_media_items(
        media_items=media_items,
        post_type=post_type,
        has_photo_text=has_photo_text,
        photo_overlay_text=photo_overlay_text,
        active_filter=active_filter,
        active_font=active_font
    )

    raw_caption = await ai_service.generate_caption(
        media_items=processed_items,
        image_bytes=raw_image_bytes,
        instructions=instructions,
        post_format=post_type,
        language=lang
    )

    body_text, ai_tags = TagService.extract_tags_and_body(raw_caption)
    preset_tags = tag_service.get_preset_tags()
    available_tags = list(dict.fromkeys(ai_tags + preset_tags))
    active_tags = list(ai_tags) if ai_tags else list(preset_tags[:4])

    final_caption = assemble_full_caption(body_text, active_mentions, active_tags)

    await state.update_data(
        caption_body=body_text,
        available_tags=available_tags,
        active_tags=active_tags,
        caption=final_caption,
        media_items=processed_items,
        photo_overlay_text=photo_overlay_text,
        has_photo_text=has_photo_text,
        language=lang,
        cover_image_bytes=cover_image_bytes
    )

    format_name = get_localized_format_name(post_type, len(media_items), lang)

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    has_photos = any(not m["is_video"] for m in media_items)

    await send_post_preview(
        target=callback.message,
        cover_image_bytes=cover_image_bytes,
        format_name=format_name,
        caption=final_caption,
        active_tags_count=len(active_tags),
        active_mentions_count=len(active_mentions),
        media_count=len(media_items),
        show_photo_text_button=has_photos,
        has_photo_text=has_photo_text,
        active_filter=active_filter,
        active_font=active_font,
        language=lang
    )


# ==============================================================================
# Navigation & Cancellation Callbacks
# ==============================================================================

@router.callback_query(F.data == "act_back_to_preview")
async def handle_back_to_preview(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    media_items = data.get("media_items", [])
    cover_image_bytes = data.get("cover_image_bytes")
    caption = data.get("caption", "")
    post_type = data.get("post_type", "FEED_PORTRAIT")
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))
    active_tags = data.get("active_tags", [])
    active_mentions = data.get("active_mentions", [])
    has_photo_text = data.get("has_photo_text", False)
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")

    format_name = get_localized_format_name(post_type, len(media_items), lang)

    await state.set_state(PostCreationStates.waiting_for_approval)

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    has_photos = any(not m["is_video"] for m in media_items)

    await send_post_preview(
        target=callback.message,
        cover_image_bytes=cover_image_bytes,
        format_name=format_name,
        caption=caption,
        active_tags_count=len(active_tags),
        active_mentions_count=len(active_mentions),
        media_count=len(media_items),
        show_photo_text_button=has_photos,
        has_photo_text=has_photo_text,
        active_filter=active_filter,
        active_font=active_font,
        language=lang
    )


@router.callback_query(F.data == "act_cancel")
async def handle_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = get_user_language(user_id=callback.from_user.id, state_lang=data.get("language"))

    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    cancel_msg = t("telegram.publication_cancelled", lang=lang)
    await callback.message.answer(cancel_msg, parse_mode="Markdown")
