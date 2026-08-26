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
        await message.answer("⛔ Извините, у вас нет доступа к этому боту.")
        return

    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    welcome_text = (
        "👋 **Добро пожаловать в Instagram AutoPosting Bot!**\n\n"
        "📸 **Как опубликовать пост/историю:**\n"
        "1. Прикрепите фото к сообщению.\n"
        "2. В подписи к фото укажите тему, ключевые мысли или оставьте пустым для автогенерации.\n"
        "3. Выберите формат (Stories 9:16, Лента 4:5 или 1:1).\n"
        "4. Проверьте превью и подтвердите публикацию!"
    )
    await message.answer(welcome_text, parse_mode="Markdown")


@router.message(Command("cancel"))
async def handle_cancel_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(PostCreationStates.waiting_for_media)
    await message.answer("🔄 Текущее действие отменено. Отправьте новое фото для создания публикации.")


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
        "📐 **Выберите формат публикации в Instagram:**",
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

    status_msg = await callback.message.edit_text("⏳ Обрабатываю фото и генерирую текст через AI...")

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
        "FEED_PORTRAIT": "🖼 Пост в ленту (4:5)",
        "FEED_SQUARE": "⏹ Пост в ленту (1:1)"
    }
    format_name = format_labels.get(post_type, post_type)

    preview_file = BufferedInputFile(processed_image_bytes, filename="preview.jpg")
    preview_text = (
        f"📋 **Предварительный просмотр ({format_name})**\n\n"
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
    progress_msg = await callback.message.answer("🚀 **Публикация...**\n1/2 Загрузка изображения в облако...")

    try:
        # Step 1: Upload to public S3 / Cloudflare R2
        public_url = await storage_service.upload_image(processed_image_bytes)
        
        await progress_msg.edit_text("🚀 **Публикация...**\n2/2 Отправка в Instagram Graph API...")

        # Step 2: Create media container
        creation_id = await instagram_service.create_media_container(
            image_url=public_url,
            caption=caption,
            is_story=is_story
        )

        # Step 3: Publish container
        post_id = await instagram_service.publish_container(creation_id)

        target_type_str = "История (Story)" if is_story else "Пост в ленту"
        success_msg = (
            f"🎉 **Успешно опубликовано!**\n\n"
            f"• **Тип:** {target_type_str}\n"
            f"• **ID публикации:** `{post_id}`\n\n"
            f"Отправьте следующее фото, чтобы создать новую публикацию."
        )
        await progress_msg.edit_text(success_msg, parse_mode="Markdown")
        await state.clear()
        await state.set_state(PostCreationStates.waiting_for_media)

    except Exception as e:
        logger.exception("Error during Instagram publishing")
        await progress_msg.edit_text(
            f"❌ **Ошибка при публикации:**\n`{str(e)}`\n\nПопробуйте снова или отредактируйте параметры.",
            reply_markup=get_approval_keyboard(),
            parse_mode="Markdown"
        )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_regenerate")
async def handle_regenerate(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("🔄 Перегенерация текста...")
    data = await state.get_data()
    user_topic = data.get("user_topic", "")
    post_type = data.get("post_type", "STORY")
    processed_image_bytes = data["processed_image_bytes"]

    new_caption = await ai_service.generate_caption(
        user_topic=user_topic,
        post_format=post_type
    )
    await state.update_data(caption=new_caption)

    preview_file = BufferedInputFile(processed_image_bytes, filename="preview.jpg")
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=preview_file,
        caption=f"📋 **Обновлённый текст:**\n\n{new_caption}",
        reply_markup=get_approval_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(PostCreationStates.waiting_for_approval, F.data == "act_edit")
async def handle_start_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PostCreationStates.waiting_for_edit)
    await callback.message.answer(
        "✏️ **Отправьте в ответ сообщение с новым текстом публикации:**",
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
    preview_file = BufferedInputFile(processed_image_bytes, filename="preview.jpg")

    await message.answer_photo(
        photo=preview_file,
        caption=f"📋 **Обновлённое превью:**\n\n{new_caption}",
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
    await callback.message.answer("🚫 Создание публикации отменено. Отправьте фото, когда будете готовы.")
