import logging
from typing import Optional
from src.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — профессиональный SMM-копирайтер и контент-креатор для душевного и эстетичного личного блога в Instagram.
Темы блога:
1. Семья (Family & Warmth): Искренние совместные моменты, эмоции детей, традиции.
2. Путешествия (Travel & Memories): Панорамные виды, впечатления от новых мест, путевые заметки.
3. Любовь к природе (Nature & Harmony): Пейзажи, закаты, море, прогулки на воздухе.
4. Развлечения и досуг (Entertainment & Fun): Яркие выходные, активный отдых.

Твоя задача — по описанию или теме от пользователя составить привлекательный пост для Instagram.
Формат ответа:
- Заголовок с эмодзи.
- Основной текст (2-4 абзаца, живой, теплый, без банальных клише).
- Интерактивный вопрос или призыв к общению в конце.
- Блок хэштегов (8-15 релевантных хэштегов на русском и английском языках).
"""

class AIService:
    def __init__(self):
        self.client = None
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}")

    async def generate_caption(self, user_topic: str = "", post_format: str = "STORY") -> str:
        """
        Generate an engaging Instagram caption with hashtags and interactive question.
        """
        if not self.client:
            return self._fallback_caption(user_topic, post_format)

        prompt = f"""
Создай пост для формата: {'Instagram Stories' if post_format == 'STORY' else 'Пост в ленту Instagram'}.
Пожелания/тема автора: {user_topic if user_topic else 'Семейный теплый момент / яркие воспоминания'}.

Сгенерируй готовый текст поста с подходящими эмодзи, интерактивом и хэштегами.
"""
        try:
            # Using google-genai SDK
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "temperature": 0.7,
                }
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            return self._fallback_caption(user_topic, post_format)

    def _fallback_caption(self, user_topic: str, post_format: str) -> str:
        topic_text = f"Тема: {user_topic}\n\n" if user_topic else ""
        return (
            f"Заново открываем мир вместе ✨🌍\n\n"
            f"{topic_text}"
            f"Каждый день дарит нам новые моменты, которые хочется сохранить в памяти надолго.\n\n"
            f"📍 Вопрос дня: А как проходят ваши выходные?\n\n"
            f"#family #travel #nature #moments #lifestyle #семья #путешествия #вдохновение"
        )


ai_service = AIService()
