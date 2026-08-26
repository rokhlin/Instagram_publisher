import logging
from typing import Optional, List, Dict, Any
from src.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    "ru": """Вы — профессиональный SMM-копирайтер и контент-мейкер для теплого, эстетичного личного блога в Instagram.
Темы блога:
1. Семья и душевность: искренние моменты, детские эмоции, семейные традиции и уют.
2. Путешествия и воспоминания: красивые виды, впечатления от новых мест, путевые заметки.
3. Природа и гармония: пейзажи, закаты, море, прогулки, спокойствие.
4. Отдых и развлечения: яркие выходные, активности, досуг.

Ваша задача — создать вовлекающий, эстетичный пост для Instagram на основе прикрепленных медиафайлов (фото/видео/карусель) и пожеланий пользователя.
Формат поста:
- Яркий заголовок с эмодзи.
- Основной текст (1-2 коротких абзаца, живой, теплый, атмосферный стиль, объединяющий все кадры истории).
- Интерактивный вопрос или призыв к действию в конце.
- Блок хештегов (5-10 релевантных хештегов на русском и английском языках).
Общая длина текста: лаконично, в пределах 600 символов для максимального визуального восприятия.
Язык ответа: РУССКИЙ.
""",
    "en": """You are a professional social media copywriter and content creator for a warm, aesthetic personal Instagram blog.
Blog themes:
1. Family & Warmth: Genuine shared moments, kids' emotions, traditions, and togetherness.
2. Travel & Memories: Scenic views, impressions from new places, travel diary notes.
3. Nature & Harmony: Landscapes, sunsets, sea, outdoor walks, tranquility.
4. Entertainment & Fun: Vibrant weekends, activities, leisure time.

Your task is to craft an engaging, aesthetic Instagram post based on the attached media (photos/videos/carousel) and user's guidance.
Output format:
- Catchy headline with emojis.
- Body text (1-2 short paragraphs, concise, warm, conversational, authentic, tying the story together).
- Interactive question or call-to-action at the end.
- Hashtag block (5-10 relevant and trending hashtags in English).
Keep the total caption length concise and under 600 characters for maximum visual appeal.
Language of response: ENGLISH.
"""
}


class AIService:
    def __init__(self):
        self.client = None
        self.model_name = "gemini-3.6-flash"
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}")

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        """
        Transcribe voice or audio message into text using Gemini multimodal audio capabilities.
        """
        if not self.client:
            logger.warning("Gemini client not initialized, cannot transcribe audio.")
            return ""

        try:
            from google.genai import types
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            prompt = (
                "Transcribe this voice message accurately into plain text in the language spoken. "
                "Output ONLY the exact transcribed text with proper punctuation, without any introductions, explanations, quotes, or metadata."
            )
            config = types.GenerateContentConfig(
                temperature=0.3,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[audio_part, prompt],
                config=config
            )
            transcription = (response.text or "").strip()
            logger.info("Voice transcription result: %s", transcription)
            return transcription
        except Exception as e:
            logger.error(f"Error during voice transcription: {e}")
            return ""

    async def generate_story_overlay_text(
        self,
        image_bytes: Optional[bytes] = None,
        instructions: str = "",
        language: str = "ru"
    ) -> str:
        """
        Generate a short, punchy 1-2 line aesthetic caption (under 60-80 chars) for overlaying directly on a Story photo.
        """
        lang_key = "ru" if language.lower().startswith("ru") else "en"
        if not self.client:
            return "Создаем воспоминания ✨" if lang_key == "ru" else "Making memories ✨"

        prompt = (
            f"Generate a VERY SHORT, beautiful, aesthetic 1-2 line quote or phrase (under 60 characters total, with 1-2 emojis) "
            f"to place directly on top of this Instagram Story photo.\n"
            f"Target Language: {'Russian' if lang_key == 'ru' else 'English'}.\n"
            f"User instructions: {instructions if instructions else 'Warm aesthetic lifestyle / travel'}.\n"
            f"Output ONLY the short phrase, without quotes or explanations."
        )

        try:
            from google.genai import types
            contents = []
            if image_bytes:
                contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
            contents.append(prompt)

            config = types.GenerateContentConfig(
                temperature=0.7,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )
            return (response.text or "").strip().strip('"\'')
        except Exception as e:
            logger.error("Error generating story overlay text: %s", e)
            return "Создаем воспоминания ✨" if lang_key == "ru" else "Making memories ✨"

    async def generate_caption(
        self,
        image_bytes: Optional[bytes] = None,
        media_items: Optional[List[Dict[str, Any]]] = None,
        instructions: str = "",
        post_format: str = "FEED_PORTRAIT",
        language: str = "ru"
    ) -> str:
        """
        Generate an engaging Instagram caption analyzing single or multiple media items (photos & videos).
        """
        lang_key = "ru" if language.lower().startswith("ru") else "en"
        system_prompt = SYSTEM_PROMPTS.get(lang_key, SYSTEM_PROMPTS["ru"])

        if not self.client:
            return self._fallback_caption(instructions, post_format, lang_key)

        format_names = {
            "STORY": "Instagram Stories",
            "FEED_PORTRAIT": "Instagram Feed Post (Portrait 4:5)",
            "FEED_SQUARE": "Instagram Feed Post (Square 1:1)",
            "CAROUSEL_PORTRAIT": "Instagram Carousel / Album (Multi-Photo & Video Post)",
            "CAROUSEL_SQUARE": "Instagram Carousel / Album (Multi-Photo & Video Post)",
            "REELS": "Instagram Reels Video"
        }
        format_desc = format_names.get(post_format, "Instagram Post")
        
        prompt_text = (
            f"Post Format: {format_desc}\n"
            f"Target Language: {'Russian' if lang_key == 'ru' else 'English'}\n"
        )
        if instructions:
            prompt_text += f"User instructions / theme: {instructions}\n\n"
        else:
            prompt_text += "No specific user instructions provided. Please analyze all visual content and the mood of the media files to create a warm, engaging caption.\n\n"

        prompt_text += "Please generate the complete, ready-to-publish Instagram caption."

        try:
            from google.genai import types
            contents = []
            
            if media_items:
                for item in media_items:
                    data = item.get("bytes")
                    mime = item.get("mime_type", "image/jpeg")
                    if data:
                        try:
                            contents.append(types.Part.from_bytes(data=data, mime_type=mime))
                        except Exception as me:
                            logger.warning("Could not add media item to Gemini prompt: %s", me)
            elif image_bytes:
                contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

            contents.append(prompt_text)

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error calling Gemini API in generate_caption: {e}")
            return self._fallback_caption(instructions, post_format, lang_key)

    async def refine_caption(
        self,
        current_caption: str,
        correction_instructions: str,
        image_bytes: Optional[bytes] = None,
        media_items: Optional[List[Dict[str, Any]]] = None,
        post_format: str = "FEED_PORTRAIT",
        language: str = "ru"
    ) -> str:
        """
        Re-analyze user's correction instructions against the existing caption and media to produce an updated version.
        """
        lang_key = "ru" if language.lower().startswith("ru") else "en"
        system_prompt = SYSTEM_PROMPTS.get(lang_key, SYSTEM_PROMPTS["ru"])

        if not self.client:
            return f"{current_caption}\n\n[Edit note: {correction_instructions}]"

        format_desc = "Instagram Stories" if post_format == "STORY" else "Instagram Feed Post"
        prompt_text = f"""You need to update and refine an existing Instagram post caption based on the user's feedback/correction instructions.

Current Caption:
\"\"\"
{current_caption}
\"\"\"

User's Correction / Edit Instructions:
\"\"\"
{correction_instructions}
\"\"\"

Format: {format_desc}
Language: {'Russian' if lang_key == 'ru' else 'English'}

Task:
Re-write the Instagram post caption incorporating all user corrections and instructions while keeping the warm, aesthetic, and engaging tone.
Output ONLY the final updated caption (headline, text, question, hashtags) ready for publication.
"""
        try:
            from google.genai import types
            contents = []
            
            if media_items:
                for item in media_items:
                    data = item.get("bytes")
                    mime = item.get("mime_type", "image/jpeg")
                    if data:
                        try:
                            contents.append(types.Part.from_bytes(data=data, mime_type=mime))
                        except Exception:
                            pass
            elif image_bytes:
                contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

            contents.append(prompt_text)

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error calling Gemini API in refine_caption: {e}")
            return f"{current_caption}\n\n[Updated with: {correction_instructions}]"

    def _fallback_caption(self, instructions: str, post_format: str, language: str) -> str:
        if language == "ru":
            topic_text = f"Тема: {instructions}\n\n" if instructions else ""
            return (
                f"Создаем моменты, которые остаются в сердце навсегда ✨🌿\n\n"
                f"{topic_text}"
                f"Каждый день дарит нам особенные поводы для улыбки и вдохновения.\n\n"
                f"📍 Вопрос дня: Как проходит ваша неделя?\n\n"
                f"#семья #путешествия #уют #моменты #вдохновение #жизнь #воспоминания"
            )
        else:
            topic_text = f"Topic: {instructions}\n\n" if instructions else ""
            return (
                f"Rediscovering the world together ✨🌍\n\n"
                f"{topic_text}"
                f"Every single day brings new moments that are truly worth keeping in our hearts forever.\n\n"
                f"📍 Question of the day: How are you spending your week?\n\n"
                f"#family #travel #nature #moments #lifestyle #wanderlust #memories #inspiration"
            )


ai_service = AIService()
