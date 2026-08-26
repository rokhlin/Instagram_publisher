import io
import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from src.config import settings
from src.bot.states import PostCreationStates
from src.bot.keyboards import (
    get_format_keyboard,
    get_approval_keyboard,
    get_cancel_keyboard,
)
from src.services.image_service import ImageService
from src.services.ai_service import ai_service
from src.services.storage_service import storage_service
from src.services.instagram_service import instagram_service

logger = logging.getLogger(__name__)
router = Router(name="main_router")


def is_user_allowed(user_id: int) -> bool:
    if not settings.allowed_users:
        return True
    return user_id in settings.allowed_users


@router.message(CommandStart())
async def handle_start(message: types.Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔ Access denied. You are not authorized to use this bot.")
        return

    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    welcome_text = (
        "👋 **Welcome to Instagram AutoPosting Bot!**\n\n"
        "📸 **How to publish a post or story:**\n"
        "1. Attach and send a photo.\n"
        "2. Add your topic, thoughts, or notes to the photo caption (or leave blank for auto-generation).\n"
        "3. Choose the publishing format (Stories 9:16, Feed 4:5, or Square 1:1).\n"
        "4. Review the preview and confirm publication!"
    )
    await message.answer(welcome_text, parse_mode="Markdown")


@router.message(Command("cancel"))
async def handle_cancel_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    await message.answer("🔄 Current action cancelled. Send a new photo to create a publication.")


@router.message(PostCreationStates.waiting_for_media, F.photo)
async def handle_media_received(message: types.Message, state: FSMContext, bot: Bot):
    if not is_user_allowed(message.from_user.id):
        return

    # Get the highest resolution photo
    photo = message.photo[-1]
    photo_file = await bot.get_file(photo.file_id)
    
    photo_io = io.BytesIO()
    await bot.download_file(photo_file.file_path, photo_io)
    raw_image_bytes = photo_io.getvalue()

    user_topic = message.caption or ""

    await state.update_data(
        raw_image_bytes=raw_image_bytes,
        user_topic=user_topic
    )
    await state.set_state(PostCreationStates.waiting_for_format)

    await message.answer(
        "📐 **Choose Instagram publication format:**",
        reply_markup=get_format_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(PostCreationStates.waiting_for_format, F.data.startswith("fmt_"))
async def handle_format_selected(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    post_type = callback.data.replace("fmt_", "")
    
    data = await state.get_data()
    raw_image_bytes = data["raw_image_bytes"]
    user_topic = data.get("user_topic", "")

    status_msg = await callback.message.edit_text("⏳ Processing image and generating AI caption...")

    # 1. Process image
    is_story = (post_type == "STORY")
    processed_image_bytes = ImageService.process_image(
        input_bytes=raw_image_bytes,
        post_type=post_type
    )

    # 2. Generate AI Caption
    caption = await ai_service.generate_caption(
        user_topic=user_topic,
        post_format=post_type
    )

    await state.update_data(
        processed_image_bytes=processed_image_bytes,
        post_type=post_type,
        caption=caption,
        is_story=is_story
    )
    await state.set_state(PostCreationStates.waiting_for_approval)

    await status_msg.delete()

    format_labels = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)"
    }
    format_name = format_labels.get(post_type, post_type)

    preview_file = BufferedInputFile(processed_image_bytes, filename="preview.jpg")
    preview_text = (
        f"📋 **Preview ({format_name})**\n\n"
        f"{caption}"
    )

    await callback.message.answer_photo(
        photo=preview_file,
        caption=preview_text,
        reply_markup=get_approval_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_publish")
async def handle_publish(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    processed_image_bytes = data["processed_image_bytes"]
    caption = data.get("caption", "")
    is_story = data.get("is_story", False)

    await callback.message.edit_reply_markup(reply_markup=None)
    progress_msg = await callback.message.answer("🚀 **Publishing...**\n1/2 Uploading image to cloud storage...")

    try:
        # Step 1: Upload to public S3 / Cloudflare R2
        public_url = await storage_service.upload_image(processed_image_bytes)
        
        await progress_msg.edit_text("🚀 **Publishing...**\n2/2 Sending to Meta Graph API...")

        # Step 2: Create media container
        creation_id = await instagram_service.create_media_container(
            image_url=public_url,
            caption=caption,
            is_story=is_story
        )

        # Step 3: Publish container
        post_id = await instagram_service.publish_container(creation_id)

        target_type_str = "Story" if is_story else "Feed Post"
        success_msg = (
            f"🎉 **Published successfully!**\n\n"
            f"• **Type:** {target_type_str}\n"
            f"• **Publication ID:** `{post_id}`\n\n"
            f"Send another photo to create a new publication."
        )
        await progress_msg.edit_text(success_msg, parse_mode="Markdown")
        await state.clear()
        await state.set_state(PostCreationStates.waiting_for_media)

    except Exception as e:
        logger.exception("Error during Instagram publishing")
        await progress_msg.edit_text(
            f"❌ **Publishing Error:**\n`{str(e)}`\n\nTry again or edit parameters.",
            reply_markup=get_approval_keyboard(),
            parse_mode="Markdown"
        )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_regenerate")
async def handle_regenerate(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("🔄 Regenerating caption...")
    data = await state.get_data()
    user_topic = data.get("user_topic", "")
    post_type = data.get("post_type", "STORY")
    processed_image_bytes = data["processed_image_bytes"]

    new_caption = await ai_service.generate_caption(
        user_topic=user_topic,
        post_format=post_type
    )
    await state.update_data(caption=new_caption)

    format_labels = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)"
    }
    format_name = format_labels.get(post_type, post_type)

    preview_file = BufferedInputFile(processed_image_bytes, filename="preview.jpg")
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=preview_file,
        caption=f"📋 **Preview ({format_name})**\n\n{new_caption}",
        reply_markup=get_approval_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_edit")
async def handle_start_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PostCreationStates.waiting_for_edit)
    await callback.message.answer(
        "✏️ **Send a message with your updated caption text:**",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )


@router.message(PostCreationStates.waiting_for_edit, F.text)
async def handle_custom_text(message: types.Message, state: FSMContext):
    new_caption = message.text.strip()
    await state.update_data(caption=new_caption)
    await state.set_state(PostCreationStates.waiting_for_approval)

    data = await state.get_data()
    processed_image_bytes = data["processed_image_bytes"]
    post_type = data.get("post_type", "STORY")
    format_labels = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)"
    }
    format_name = format_labels.get(post_type, post_type)

    preview_file = BufferedInputFile(processed_image_bytes, filename="preview.jpg")

    await message.answer_photo(
        photo=preview_file,
        caption=f"📋 **Preview ({format_name})**\n\n{new_caption}",
        reply_markup=get_approval_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "act_back_to_preview")
async def handle_back_to_preview(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    processed_image_bytes = data.get("processed_image_bytes")
    if not processed_image_bytes:
        await handle_cancel(callback, state)
        return

    caption = data.get("caption", "")
    post_type = data.get("post_type", "STORY")
    format_labels = {
        "STORY": "📱 Stories (9:16)",
        "FEED_PORTRAIT": "🖼 Feed Post (4:5)",
        "FEED_SQUARE": "⏹ Feed Post (1:1)"
    }
    format_name = format_labels.get(post_type, post_type)

    await state.set_state(PostCreationStates.waiting_for_approval)
    preview_file = BufferedInputFile(processed_image_bytes, filename="preview.jpg")

    if callback.message:
        await callback.message.delete()

    await callback.message.answer_photo(
        photo=preview_file,
        caption=f"📋 **Preview ({format_name})**\n\n{caption}",
        reply_markup=get_approval_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "act_cancel")
async def handle_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    if callback.message:
        await callback.message.delete()
    await callback.message.answer("🚫 Publication creation cancelled. Send a photo whenever you are ready.")
