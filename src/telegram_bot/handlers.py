import io
import asyncio
import logging
from typing import List, Set, Dict, Any, Optional, Tuple
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from src.config import settings
from src.telegram_bot.states import PostCreationStates
from src.telegram_bot.keyboards import (
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
from src.services.image_service import ImageService, FONT_REGISTRY, FILTER_REGISTRY
from src.services.ai_service import ai_service
from src.services.tag_service import tag_service, TagService
from src.services.mention_service import mention_service, MentionService
from src.services.storage_service import storage_service
from src.services.instagram_service import instagram_service

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
        parts.append(f"👥 " + " ".join(active_mentions))
    if active_tags:
        parts.append(" ".join(active_tags))
    return "\n\n".join([p for p in parts if p]).strip()


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


HELP_TEXT = (
    "🌟 *Instagram Auto-Posting Bot Guide*\n\n"
    "Этот бот помогает подготавливать фото, видео и альбомы (карусели), создавать AI-описания на русском или английском языках, "
    "накладывать красивые дизайнерские шрифты, применять стильные фильтры (Golden Hour, Vintage, Cinematic и др.), "
    "настраивать теги (#) и упоминания (@), и публиковать всё в Instagram!\n\n"
    "📸 *Поддерживаемые возможности:*\n"
    "• **Фото, видео и альбомы** (Stories, Feed, Reels, Carousels).\n"
    "• 🎨 **7 эстетичных фильтров**: Золотой час, Винтаж, Кинематограф, Ч/Б Нуар, Сочный, Мягкий свет.\n"
    "• 🔤 **5 декоративных шрифтов**: Modern Sans, Рукописный, Элегантный Serif, Ретро Rounded, Акцентный Bold.\n"
    "• 🎙 **Голосовой ввод и коррекция**: надиктуйте пожелания или правки к тексту.\n\n"
    "🚀 *Как создать публикацию:*\n"
    "1️⃣ Отправьте фото, видео или альбом через скрепку 📎.\n"
    "2️⃣ Выберите язык описания (🇷🇺 Русский / 🇬🇧 English).\n"
    "3️⃣ Задайте пожелания голосом 🎙 или текстом (или нажмите «Пропустить»).\n"
    "4️⃣ Выберите формат размещения.\n"
    "5️⃣ Настройте фильтры, шрифты, теги, упоминания и опубликуйте в 1 клик!\n\n"
    "📋 *Команды:*\n"
    "• /start — перезапуск и справка\n"
    "• /tags — управление постоянными тегами (#)\n"
    "• /mentions — управление постоянными упоминаниями (@)\n"
    "• /status — статус подключений и серверов\n"
    "• /cancel — отменить текущую публикацию"
)


# ==============================================================================
# Base Commands: /start, /help, /status, /cancel, /tags, /mentions
# ==============================================================================

@router.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info("Received /start from user_id=%s (%s)", user_id, message.from_user.username)
    if not is_user_allowed(user_id):
        await message.answer("⛔ *Access denied.* You are not authorized to use this bot.", parse_mode="Markdown")
        return

    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    await message.answer(HELP_TEXT, parse_mode="Markdown")


@router.message(Command("help"))
async def handle_help(message: types.Message):
    if not is_user_allowed(message.from_user.id):
        return
    await message.answer(HELP_TEXT, parse_mode="Markdown")


@router.message(Command("status"))
async def handle_status_cmd(message: types.Message):
    if not is_user_allowed(message.from_user.id):
        return

    storage_mode = settings.STORAGE_TYPE.upper()
    ai_status = "Gemini AI Active (Multimodal & Voice)" if settings.GEMINI_API_KEY else "Template Fallback (No API Key)"
    preset_tags_count = len(tag_service.get_preset_tags())
    preset_mentions_count = len(mention_service.get_preset_mentions())
    
    status_text = (
        "📊 *Статус системы и подключений*\n\n"
        f"• *Instagram Account ID:* `{settings.IG_USER_ID or 'Не задан'}`\n"
        f"• *Хранилище:* `{storage_mode}`\n"
        f"• *AI Копирайтер & Голос:* `{ai_status}`\n"
        f"• *Предустановленные теги:* `{preset_tags_count}` шт. (/tags)\n"
        f"• *Постоянные упоминания:* `{preset_mentions_count}` шт. (/mentions)\n"
        "• *Статус бота:* `Онлайн и готов к работе` ✅\n\n"
        "Отправьте фото, видео или альбом для создания новой публикации."
    )
    await message.answer(status_text, parse_mode="Markdown")


@router.message(Command("cancel"))
async def handle_cancel_cmd(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        return
    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    await message.answer("🔄 *Действие отменено.* Отправьте фото или видео для создания публикации.", parse_mode="Markdown")


@router.message(Command("tags"))
async def handle_tags_command(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        return
    presets = tag_service.get_preset_tags()
    await state.set_state(PostCreationStates.managing_preset_tags)
    msg = (
        "🏷 *Управление предустановленными тегами*\n\n"
        "Эти теги автоматически предлагаются во всех публикациях.\n"
        "Нажмите на тег с 🗑 чтобы удалить его, либо добавьте новый:"
    )
    await message.answer(msg, reply_markup=get_presets_manager_keyboard(presets, item_type="tag", language="ru"), parse_mode="Markdown")


@router.message(Command("mentions"))
async def handle_mentions_command(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        return
    presets = mention_service.get_preset_mentions()
    await state.set_state(PostCreationStates.managing_preset_mentions)
    msg = (
        "👥 *Управление постоянными упоминаниями (@)*\n\n"
        "Аккаунты из этого списка доступны для быстрого включения в публикации.\n"
        "Нажмите на упоминание с 🗑 чтобы удалить его, либо добавьте новое:"
    )
    await message.answer(msg, reply_markup=get_presets_manager_keyboard(presets, item_type="mention", language="ru"), parse_mode="Markdown")


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
    logger.info("Processing media group %s with %d items for user_id=%s", media_group_id, len(messages), user_id)

    status_note = await first_msg.answer(f"📥 *Загрузка альбома ({len(messages)} файлов)...*", parse_mode="Markdown")

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
        await first_msg.answer("⚠️ Не удалось извлечь медиафайлы из альбома.")
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
        active_filter="ORIGINAL",
        active_font="MODERN"
    )
    await state.set_state(PostCreationStates.waiting_for_language)

    summary_text = (
        f"🎠 *Получен альбом из {len(media_items)} файлов* "
        f"({photos_count} фото, {videos_count} видео).\n\n"
        "🌍 *Выберите язык для описания публикации:*"
    )
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
    logger.info("Received single photo from user_id=%s", user_id)
    if not is_user_allowed(user_id):
        await message.answer("⛔ *Access denied.* You are not authorized to use this bot.", parse_mode="Markdown")
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
        active_filter="ORIGINAL",
        active_font="MODERN"
    )
    await state.set_state(PostCreationStates.waiting_for_language)

    await message.answer(
        "🌍 *Выберите язык для описания публикации:*\n*Choose caption language:*",
        reply_markup=get_language_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.video)
async def handle_single_video(message: types.Message, state: FSMContext, bot: Bot):
    if message.media_group_id:
        return
    user_id = message.from_user.id
    logger.info("Received single video from user_id=%s", user_id)
    if not is_user_allowed(user_id):
        await message.answer("⛔ *Access denied.* You are not authorized to use this bot.", parse_mode="Markdown")
        return

    video = message.video
    status_msg = await message.answer("📥 *Загрузка видео...*", parse_mode="Markdown")

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
        active_filter="ORIGINAL",
        active_font="MODERN"
    )
    await state.set_state(PostCreationStates.waiting_for_language)

    await message.answer(
        "🎬 *Видео получено!*\n\n🌍 *Выберите язык для описания публикации:*",
        reply_markup=get_language_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.document)
async def handle_single_document(message: types.Message, state: FSMContext, bot: Bot):
    if message.media_group_id:
        return
    user_id = message.from_user.id
    logger.info("Received document from user_id=%s", user_id)
    if not is_user_allowed(user_id):
        await message.answer("⛔ *Access denied.* You are not authorized to use this bot.", parse_mode="Markdown")
        return

    doc = message.document
    mime = (doc.mime_type or "").lower()
    filename = (doc.file_name or "").lower()

    is_image = mime.startswith("image/") or filename.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp"))
    is_video = mime.startswith("video/") or filename.endswith((".mp4", ".mov"))

    if not is_image and not is_video:
        await message.answer(
            "⚠️ *Неподдерживаемый формат файла*\n\n"
            f"Вы отправили: `{doc.file_name or 'Документ'}` ({doc.mime_type or 'неизвестный тип'})\n\n"
            "Пожалуйста, отправьте **фотографию** или **видео** (*JPEG*, *PNG*, *WEBP*, *MP4*, *MOV*).",
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
        active_filter="ORIGINAL",
        active_font="MODERN"
    )
    await state.set_state(PostCreationStates.waiting_for_language)

    await message.answer(
        "🌍 *Выберите язык для описания публикации:*\n*Choose caption language:*",
        reply_markup=get_language_keyboard(),
        parse_mode="Markdown"
    )


# ==============================================================================
# Step 2: Language Selected -> Ask for Voice / Text Instructions
# ==============================================================================

@router.callback_query(PostCreationStates.waiting_for_language, F.data.startswith("lang_"))
async def handle_language_selected(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    lang = callback.data.replace("lang_", "")  # "ru" or "en"
    await state.update_data(language=lang)

    data = await state.get_data()
    existing_instructions = data.get("instructions", "")
    is_album = data.get("is_album", False)
    has_video = data.get("has_video", False)

    if existing_instructions:
        await state.set_state(PostCreationStates.waiting_for_format)
        prompt_text = (
            f"📝 *Тема поста:* _{existing_instructions}_\n\n📐 *Выберите формат публикации в Instagram:*"
            if lang == "ru"
            else f"📝 *Post theme:* _{existing_instructions}_\n\n📐 *Choose Instagram publication format:*"
        )
        await callback.message.edit_text(
            prompt_text,
            reply_markup=get_format_keyboard(lang, is_album=is_album, has_video=has_video),
            parse_mode="Markdown"
        )
        return

    await state.set_state(PostCreationStates.waiting_for_instructions)

    if lang == "ru":
        prompt_text = (
            "🎙 *Хотите добавить тему или инструкции к описанию?*\n\n"
            "• Надиктуйте 🎙 *голосовое сообщение* с пожеланиями к посту.\n"
            "• Или отправьте *текстовое сообщение*.\n"
            "• Либо нажмите кнопку «⏩ Пропустить», и AI автоматически проанализирует сюжет и детали."
        )
    else:
        prompt_text = (
            "🎙 *Want to add instructions or a topic for the post?*\n\n"
            "• Send a 🎙 *voice message* with details or tone guidance.\n"
            "• Or send a *text message*.\n"
            "• Or tap «⏩ Skip» to let Gemini AI analyze the media automatically."
        )

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
    lang = data.get("language", "ru")
    is_album = data.get("is_album", False)
    has_video = data.get("has_video", False)

    await state.update_data(instructions="")
    await state.set_state(PostCreationStates.waiting_for_format)

    prompt_text = (
        "📐 *Выберите формат публикации в Instagram:*"
        if lang == "ru"
        else "📐 *Choose Instagram publication format:*"
    )
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
    lang = data.get("language", "ru")
    is_album = data.get("is_album", False)
    has_video = data.get("has_video", False)

    progress_msg = await message.answer(
        "🎧 *Слушаю и распознаю голосовые инструкции...*" if lang == "ru" else "🎧 *Listening & transcribing voice instructions...*",
        parse_mode="Markdown"
    )

    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file_info = await bot.get_file(file_id)
        audio_io = io.BytesIO()
        await bot.download_file(file_info.file_path, audio_io)
        audio_bytes = audio_io.getvalue()

        transcription = await ai_service.transcribe_audio(audio_bytes, mime_type="audio/ogg")
        await state.update_data(instructions=transcription)
        await state.set_state(PostCreationStates.waiting_for_format)

        await progress_msg.delete()

        prompt_text = (
            f"🎙 *Распознано:* _{transcription or 'голос принят'}_\n\n📐 *Выберите формат публикации в Instagram:*"
            if lang == "ru"
            else f"🎙 *Transcribed:* _{transcription or 'voice received'}_\n\n📐 *Choose Instagram publication format:*"
        )
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
    lang = data.get("language", "ru")
    is_album = data.get("is_album", False)
    has_video = data.get("has_video", False)

    await state.update_data(instructions=instructions)
    await state.set_state(PostCreationStates.waiting_for_format)

    prompt_text = (
        f"📝 *Принято:* _{instructions}_\n\n📐 *Выберите формат публикации в Instagram:*"
        if lang == "ru"
        else f"📝 *Saved:* _{instructions}_\n\n📐 *Choose Instagram publication format:*"
    )
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
    lang = data.get("language", "ru")
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")
    is_story = (post_type in ("STORY", "CAROUSEL_STORY"))

    status_text = (
        "⏳ Анализирую медиафайлы и создаю AI-описание..."
        if lang == "ru"
        else "⏳ Analyzing media & generating AI caption..."
    )
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
        cover_image_bytes=cover_image_bytes
    )
    await state.set_state(PostCreationStates.waiting_for_approval)

    try:
        await status_msg.delete()
    except Exception:
        pass

    format_labels_ru = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)",
        "CAROUSEL_PORTRAIT": f"🎠 Карусель ({len(media_items)} файлов, 4:5)",
        "CAROUSEL_SQUARE": f"⏹ Карусель ({len(media_items)} файлов, 1:1)",
        "REELS": "🎬 Reels Video"
    }
    format_name = format_labels_ru.get(post_type, post_type)

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
    media_info = f" ({media_count} медиафайлов)" if media_count > 1 else ""
    preview_header = f"📋 *Предпросмотр ({format_name}){media_info}*" if language == "ru" else f"📋 *Preview ({format_name}){media_info}*"
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
    lang = data.get("language", "ru")

    msg = (
        "🎨 *Выберите эффект / цветовой фильтр для фото:*\n\n"
        "• ☀️ *Золотой час* — тёплые закатные лучи\n"
        "• 🎞 *Винтаж / Плёнка* — мягкий аналоговый стиль\n"
        "• 🌊 *Кинематограф* — глубокие тени и кино-оттенки\n"
        "• 🖤 *Ч/Б Нуар* — стильный контрастный монохром\n"
        "• 🍓 *Сочный* — насыщенность и резкость\n"
        "• ✨ *Мягкий свет* — пастельное свечение"
        if lang == "ru"
        else (
            "🎨 *Choose visual filter / color grade:*\n\n"
            "• ☀️ *Golden Hour* — warm sunlight glow\n"
            "• 🎞 *Vintage Film* — analog retro tones\n"
            "• 🌊 *Cinematic* — moody teal & amber\n"
            "• 🖤 *B&W Noir* — deep rich monochrome\n"
            "• 🍓 *Vibrant* — punchy colors\n"
            "• ✨ *Dreamy Glow* — soft pastel diffusion"
        )
    )

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
    lang = data.get("language", "ru")

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
    await callback.answer(f"✅ Применен фильтр: {filter_name}")

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    format_labels_ru = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)",
        "CAROUSEL_PORTRAIT": f"🎠 Карусель ({len(media_items)} файлов, 4:5)",
        "CAROUSEL_SQUARE": f"⏹ Карусель ({len(media_items)} файлов, 1:1)",
        "REELS": "🎬 Reels Video"
    }
    format_name = format_labels_ru.get(post_type, post_type)

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
    lang = data.get("language", "ru")

    msg = (
        "🔤 *Выберите стиль декоративного шрифта:*\n\n"
        "• 🔤 *Modern Sans* — стильный минимализм (Montserrat)\n"
        "• 🖋 *Рукописный* — живой эстетичный почерк (Caveat)\n"
        "• 📜 *Элегантный Serif* — журнальная классика (Playfair)\n"
        "• 🪶 *Ретро Rounded* — мягкие округлые линии (Comfortaa)\n"
        "• ⚡️ *Акцентный Bold* — динамичный плотный шрифт (Oswald)"
        if lang == "ru"
        else (
            "🔤 *Choose decorative typography style:*\n\n"
            "• 🔤 *Modern Sans* — sleek minimalist (Montserrat)\n"
            "• 🖋 *Handwriting* — aesthetic cursive (Caveat)\n"
            "• 📜 *Elegant Serif* — editorial class (Playfair)\n"
            "• 🪶 *Retro Rounded* — soft curves (Comfortaa)\n"
            "• ⚡️ *Impact Bold* — punchy condensed (Oswald)"
        )
    )

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
    lang = data.get("language", "ru")

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
    await callback.answer(f"✅ Выбран шрифт: {font_name}")

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    format_labels_ru = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)",
        "CAROUSEL_PORTRAIT": f"🎠 Карусель ({len(media_items)} файлов, 4:5)",
        "CAROUSEL_SQUARE": f"⏹ Карусель ({len(media_items)} файлов, 1:1)",
        "REELS": "🎬 Reels Video"
    }
    format_name = format_labels_ru.get(post_type, post_type)

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
    lang = data.get("language", "ru")
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

    status_txt = "✅ Текст на фото включен" if new_has_photo_text else "❌ Текст на фото выключен"
    await callback.answer(status_txt)

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    format_labels_ru = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)",
        "CAROUSEL_PORTRAIT": f"🎠 Карусель ({len(media_items)} файлов, 4:5)",
        "CAROUSEL_SQUARE": f"⏹ Карусель ({len(media_items)} файлов, 1:1)",
        "REELS": "🎬 Reels Video"
    }
    format_name = format_labels_ru.get(post_type, post_type)

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
    lang = data.get("language", "ru")
    current_overlay = data.get("photo_overlay_text", "")

    await state.set_state(PostCreationStates.waiting_for_photo_text_edit)

    msg = (
        f"✍️ *Редактирование текста на фото*\n\n"
        f"Текущий текст: _{current_overlay}_\n\n"
        f"• Надиктуйте 🎙 *голосовое сообщение* с новым текстом.\n"
        f"• Или отправьте *текстовое сообщение* (короткая фраза 1-2 строки)."
        if lang == "ru"
        else (
            f"✍️ *Edit Photo Overlay Text*\n\n"
            f"Current: _{current_overlay}_\n\n"
            f"• Send a 🎙 *voice note* with the new text.\n"
            f"• Or send a *text message* (short 1-2 lines)."
        )
    )
    await callback.message.answer(msg, reply_markup=get_cancel_keyboard(lang), parse_mode="Markdown")


@router.message(PostCreationStates.waiting_for_photo_text_edit, F.voice | F.audio)
async def handle_voice_photo_text_edit(message: types.Message, state: FSMContext, bot: Bot):
    if not is_user_allowed(message.from_user.id):
        return

    data = await state.get_data()
    lang = data.get("language", "ru")
    media_items = data.get("media_items", [])
    post_type = data.get("post_type", "FEED_PORTRAIT")
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")

    progress_msg = await message.answer("🎧 Распознаю голос..." if lang == "ru" else "🎧 Transcribing voice...")

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

        await message.answer(f"✍️ *Текст на фото обновлен:* _{new_text}_", parse_mode="Markdown")

        format_labels_ru = {
            "STORY": "📱 Stories (9:16)",
            "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
            "FEED_SQUARE": "⏹ Feed Post (1:1)",
            "CAROUSEL_PORTRAIT": f"🎠 Карусель ({len(media_items)} файлов, 4:5)",
            "CAROUSEL_SQUARE": f"⏹ Карусель ({len(media_items)} файлов, 1:1)",
            "REELS": "🎬 Reels Video"
        }
        format_name = format_labels_ru.get(post_type, post_type)

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
    lang = data.get("language", "ru")
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

    await message.answer(f"✍️ *Текст на фото обновлен:* _{new_text}_", parse_mode="Markdown")

    format_labels_ru = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)",
        "CAROUSEL_PORTRAIT": f"🎠 Карусель ({len(media_items)} файлов, 4:5)",
        "CAROUSEL_SQUARE": f"⏹ Карусель ({len(media_items)} файлов, 1:1)",
        "REELS": "🎬 Reels Video"
    }
    format_name = format_labels_ru.get(post_type, post_type)

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
    lang = data.get("language", "ru")

    prompt_text = (
        "🏷 *Редактор тегов публикации:*\n\n"
        "Нажимайте на кнопки с тегами, чтобы включить (✅) или выключить (◻️) их в посте.\n\n"
        "Вы также можете добавить свой тег или настроить постоянные пресеты."
        if lang == "ru"
        else (
            "🏷 *Post Tag Editor:*\n\n"
            "Click tag buttons to toggle them ON (✅) or OFF (◻️).\n\n"
            "You can also add custom tags or manage persistent presets."
        )
    )

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
    lang = data.get("language", "ru")

    if 0 <= tag_idx < len(available_tags):
        tag = available_tags[tag_idx]
        if tag in active_tags:
            active_tags.remove(tag)
            await callback.answer(f"❌ Убран {tag}" if lang == "ru" else f"❌ Removed {tag}")
        else:
            active_tags.add(tag)
            await callback.answer(f"✅ Добавлен {tag}" if lang == "ru" else f"✅ Added {tag}")

        new_active_tags = [t for t in available_tags if t in active_tags]
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
    lang = data.get("language", "ru")
    await state.set_state(PostCreationStates.waiting_for_custom_tag)

    msg = (
        "➕ *Введите новый тег* (или несколько через пробел, например `#закат #путешествие`):"
        if lang == "ru"
        else "➕ *Enter custom tag* (or several separated by space, e.g. `#sunset #adventure`):"
    )
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
    lang = data.get("language", "ru")

    raw_words = text.split()
    added_count = 0
    for w in raw_words:
        clean = TagService.normalize_tag(w)
        if clean:
            if clean not in available_tags:
                available_tags.append(clean)
            active_tags.add(clean)
            added_count += 1

    new_active_tags = [t for t in available_tags if t in active_tags]
    new_caption = assemble_full_caption(caption_body, active_mentions, new_active_tags)

    await state.update_data(
        available_tags=available_tags,
        active_tags=new_active_tags,
        caption=new_caption
    )
    await state.set_state(PostCreationStates.waiting_for_approval)

    confirm_msg = (
        f"✅ Добавлено тегов: {added_count} шт." if lang == "ru" else f"✅ Added {added_count} tag(s)."
    )
    await message.answer(confirm_msg)
    await message.answer(
        "🏷 *Редактор тегов:*",
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
    lang = data.get("language", "ru")

    prompt_text = (
        "👥 *Редактор упоминаний (@) в публикации:*\n\n"
        "Нажимайте на кнопки с аккаунтами, чтобы включить (✅) или выключить (◻️) их в посте.\n\n"
        "Вы можете добавить новый аккаунт или настроить постоянный список."
        if lang == "ru"
        else (
            "👥 *Post Mentions Editor (@):*\n\n"
            "Click account buttons to toggle them ON (✅) or OFF (◻️).\n\n"
            "You can also add accounts or manage permanent presets."
        )
    )

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
    lang = data.get("language", "ru")

    if 0 <= men_idx < len(available_mentions):
        mention = available_mentions[men_idx]
        if mention in active_mentions:
            active_mentions.remove(mention)
            await callback.answer(f"❌ Убран {mention}" if lang == "ru" else f"❌ Removed {mention}")
        else:
            active_mentions.add(mention)
            await callback.answer(f"✅ Добавлен {mention}" if lang == "ru" else f"✅ Added {mention}")

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
    lang = data.get("language", "ru")
    await state.set_state(PostCreationStates.waiting_for_custom_mention)

    msg = (
        "➕ *Введите Instagram username для упоминания* (например `@john_doe` или `alex_family`):"
        if lang == "ru"
        else "➕ *Enter Instagram username to mention* (e.g. `@john_doe` or `alex_family`):"
    )
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
    lang = data.get("language", "ru")

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

    confirm_msg = (
        f"✅ Добавлено упоминаний: {added_count} шт." if lang == "ru" else f"✅ Added {added_count} mention(s)."
    )
    await message.answer(confirm_msg)
    await message.answer(
        "👥 *Редактор упоминаний:*",
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
    lang = data.get("language", "ru")
    presets = tag_service.get_preset_tags()

    msg = (
        "⚙️ *Настройка постоянных пресетов тегов:*\n\n"
        "Нажмите 🗑 на теге, чтобы удалить его из постоянного списка, или нажмите «➕ Добавить тег»."
        if lang == "ru"
        else "⚙️ *Preset Tags Management:*\n\nClick 🗑 to delete a preset, or click «➕ Add Tag»."
    )
    await callback.message.answer(msg, reply_markup=get_presets_manager_keyboard(presets, item_type="tag", language=lang), parse_mode="Markdown")


@router.callback_query(F.data.startswith("del_preset_tag_"))
async def handle_delete_preset_tag(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("del_preset_tag_", ""))
    presets = tag_service.get_preset_tags()
    data = await state.get_data()
    lang = data.get("language", "ru")

    if 0 <= idx < len(presets):
        removed = presets[idx]
        tag_service.remove_preset_tag(removed)
        await callback.answer(f"🗑 Удален {removed}")
        new_presets = tag_service.get_preset_tags()
        await callback.message.edit_reply_markup(
            reply_markup=get_presets_manager_keyboard(new_presets, item_type="tag", language=lang)
        )


@router.callback_query(F.data == "add_preset_tag")
async def handle_prompt_add_preset_tag(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "ru")
    await state.set_state(PostCreationStates.adding_preset_tag)
    msg = "➕ *Введите новый тег для сохранения в постоянные пресеты:*" if lang == "ru" else "➕ *Enter tag to save in presets:*"
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
    lang = data.get("language", "ru")
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

    await message.answer(f"✅ Сохранено в пресеты!")
    await message.answer(
        "⚙️ *Текущие пресеты тегов:*",
        reply_markup=get_presets_manager_keyboard(presets, item_type="tag", language=lang),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.in_(["act_manage_preset_mentions", "back_from_preset_mention"]))
async def handle_manage_preset_mentions_view(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "ru")
    presets = mention_service.get_preset_mentions()

    msg = (
        "⚙️ *Настройка постоянных упоминаний (@):*\n\n"
        "Нажмите 🗑 на аккаунте, чтобы удалить его из постоянного списка, или нажмите «➕ Добавить аккаунт»."
        if lang == "ru"
        else "⚙️ *Preset Mentions Management:*\n\nClick 🗑 to delete a mention, or click «➕ Add Account»."
    )
    await callback.message.answer(msg, reply_markup=get_presets_manager_keyboard(presets, item_type="mention", language=lang), parse_mode="Markdown")


@router.callback_query(F.data.startswith("del_preset_mention_"))
async def handle_delete_preset_mention(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("del_preset_mention_", ""))
    presets = mention_service.get_preset_mentions()
    data = await state.get_data()
    lang = data.get("language", "ru")

    if 0 <= idx < len(presets):
        removed = presets[idx]
        mention_service.remove_preset_mention(removed)
        await callback.answer(f"🗑 Удален {removed}")
        new_presets = mention_service.get_preset_mentions()
        await callback.message.edit_reply_markup(
            reply_markup=get_presets_manager_keyboard(new_presets, item_type="mention", language=lang)
        )


@router.callback_query(F.data == "add_preset_mention")
async def handle_prompt_add_preset_mention(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "ru")
    await state.set_state(PostCreationStates.adding_preset_mention)
    msg = "➕ *Введите Instagram username для сохранения в постоянные упоминания:*" if lang == "ru" else "➕ *Enter username to save in preset mentions:*"
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
    lang = data.get("language", "ru")
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

    await message.answer(f"✅ Сохранено в постоянные упоминания!")
    await message.answer(
        "⚙️ *Текущие постоянные упоминания:*",
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
    lang = data.get("language", "ru")

    await state.set_state(PostCreationStates.waiting_for_edit)

    if lang == "ru":
        prompt_text = (
            "🎙✏️ *Режим коррекции текста описания:*\n\n"
            "• Надиктуйте 🎙 *голосовое сообщение* с правками (например: _«Сделай текст короче и добавь упоминание про горячий чай»_).\n"
            "• Или отправьте *текстовое сообщение* с пожеланиями или новым текстом.\n\n"
            "AI переработает публикацию с учетом ваших замечаний."
        )
    else:
        prompt_text = (
            "🎙✏️ *Caption Correction Mode:*\n\n"
            "• Send a 🎙 *voice note* with your edits (e.g., _\"Make it punchier and add hashtags about travel\"_).\n"
            "• Or send a *text message* with edits.\n\n"
            "Gemini AI will re-analyze your feedback and update the post."
        )

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
    lang = data.get("language", "ru")
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
        "🎧 *Слушаю голосовую правку и обновляю текст с помощью AI...*"
        if lang == "ru"
        else "🎧 *Listening to voice feedback & updating caption with AI...*",
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
            for t in new_ai_tags:
                if t not in available_tags:
                    available_tags.append(t)
                if t not in active_tags:
                    active_tags.append(t)
            await state.update_data(available_tags=available_tags, active_tags=active_tags)

        final_caption = assemble_full_caption(body_text, active_mentions, active_tags)

        await state.update_data(
            caption_body=body_text,
            caption=final_caption
        )
        await state.set_state(PostCreationStates.waiting_for_approval)

        await progress_msg.delete()

        format_labels_ru = {
            "STORY": "📱 Stories (9:16)",
            "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
            "FEED_SQUARE": "⏹ Feed Post (1:1)",
            "CAROUSEL_PORTRAIT": f"🎠 Карусель ({len(media_items)} файлов, 4:5)",
            "CAROUSEL_SQUARE": f"⏹ Карусель ({len(media_items)} файлов, 1:1)",
            "REELS": "🎬 Reels Video"
        }
        format_name = format_labels_ru.get(post_type, post_type)

        feedback_note = f"🎙 *Учтена голосовая правка:* _{correction_transcript}_\n\n" if correction_transcript else ""
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
    lang = data.get("language", "ru")
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
        "⏳ Обновляю текст с учетом ваших пожеланий..." if lang == "ru" else "⏳ Updating caption based on your feedback...",
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
            for t in new_ai_tags:
                if t not in available_tags:
                    available_tags.append(t)
                if t not in active_tags:
                    active_tags.append(t)
            await state.update_data(available_tags=available_tags, active_tags=active_tags)

        final_caption = assemble_full_caption(body_text, active_mentions, active_tags)

        await state.update_data(
            caption_body=body_text,
            caption=final_caption
        )
        await state.set_state(PostCreationStates.waiting_for_approval)

        await progress_msg.delete()

        format_labels_ru = {
            "STORY": "📱 Stories (9:16)",
            "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
            "FEED_SQUARE": "⏹ Feed Post (1:1)",
            "CAROUSEL_PORTRAIT": f"🎠 Карусель ({len(media_items)} файлов, 4:5)",
            "CAROUSEL_SQUARE": f"⏹ Карусель ({len(media_items)} файлов, 1:1)",
            "REELS": "🎬 Reels Video"
        }
        format_name = format_labels_ru.get(post_type, post_type)

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
    lang = data.get("language", "ru")

    await callback.message.edit_reply_markup(reply_markup=None)

    progress_msg = await callback.message.answer(
        f"🚀 *Публикация...*\n1/3 Загрузка медиа ({len(media_items)} шт.) в облако R2/S3..."
        if lang == "ru"
        else f"🚀 *Publishing...*\n1/3 Uploading media ({len(media_items)} items) to cloud...",
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
                f"🚀 *Публикация...*\n2/3 Создание карусели ({len(uploaded_media_urls)} элементов)..."
                if lang == "ru"
                else f"🚀 *Publishing...*\n2/3 Creating carousel containers ({len(uploaded_media_urls)} items)...",
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
                "🚀 *Публикация...*\n3/3 Завершение публикации в Instagram..."
                if lang == "ru"
                else "🚀 *Publishing...*\n3/3 Finalizing Instagram publication...",
                parse_mode="Markdown"
            )
            post_id = await instagram_service.publish_container(parent_id, max_retries=15)
            target_type_str = f"Карусель / Альбом ({len(media_items)} файлов)"

        else:
            await progress_msg.edit_text(
                "🚀 *Публикация...*\n2/2 Отправка в Meta Graph API..."
                if lang == "ru"
                else "🚀 *Publishing...*\n2/2 Sending to Meta Graph API...",
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
            target_type_str = "История (Story)" if is_story else ("Reels Video" if first_item["is_video"] else "Пост в ленту (Feed Post)")

        if lang == "ru":
            success_msg = (
                f"🎉 *Успешно опубликовано в Instagram!* ✨\n\n"
                f"• *Формат:* {target_type_str}\n"
                f"• *ID публикации:* `{post_id}`\n\n"
                f"Отправьте новое фото или видео для следующей публикации."
            )
        else:
            success_msg = (
                f"🎉 *Successfully published to Instagram!* ✨\n\n"
                f"• *Format:* {target_type_str}\n"
                f"• *Publication ID:* `{post_id}`\n\n"
                f"Send another photo or video to create a new post."
            )

        await progress_msg.edit_text(success_msg, parse_mode="Markdown")
        await state.clear()
        await state.set_state(PostCreationStates.waiting_for_media)

    except Exception as e:
        logger.exception("Error during Instagram publishing: %s", e)
        err_header = "❌ *Ошибка публикации:*" if lang == "ru" else "❌ *Publishing Error:*"
        await progress_msg.edit_text(
            f"{err_header}\n`{str(e)}`\n\nПопробуйте снова или отредактируйте параметры.",
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
    lang = data.get("language", "ru")
    active_mentions = data.get("active_mentions", [])
    is_story = (post_type in ("STORY", "CAROUSEL_STORY"))

    await callback.answer("🔄 Генерация нового варианта..." if lang == "ru" else "🔄 Regenerating caption...")

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
        cover_image_bytes=cover_image_bytes
    )

    format_labels_ru = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)",
        "CAROUSEL_PORTRAIT": f"🎠 Карусель ({len(media_items)} файлов, 4:5)",
        "CAROUSEL_SQUARE": f"⏹ Карусель ({len(media_items)} файлов, 1:1)",
        "REELS": "🎬 Reels Video"
    }
    format_name = format_labels_ru.get(post_type, post_type)

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
    lang = data.get("language", "ru")
    active_tags = data.get("active_tags", [])
    active_mentions = data.get("active_mentions", [])
    has_photo_text = data.get("has_photo_text", False)
    active_filter = data.get("active_filter", "ORIGINAL")
    active_font = data.get("active_font", "MODERN")

    format_labels_ru = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)",
        "CAROUSEL_PORTRAIT": f"🎠 Карусель ({len(media_items)} файлов, 4:5)",
        "CAROUSEL_SQUARE": f"⏹ Карусель ({len(media_items)} файлов, 1:1)",
        "REELS": "🎬 Reels Video"
    }
    format_name = format_labels_ru.get(post_type, post_type)

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
    lang = data.get("language", "ru")

    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    cancel_msg = (
        "🚫 *Создание публикации отменено.* Отправьте фото или видео в любое время."
        if lang == "ru"
        else "🚫 *Publication cancelled.* Send photo or video whenever you're ready."
    )
    await callback.message.answer(cancel_msg, parse_mode="Markdown")
