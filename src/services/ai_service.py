import logging
from typing import Optional
from src.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a professional social media copywriter and content creator for a warm, aesthetic personal Instagram blog.
Blog themes:
1. Family & Warmth: Genuine shared moments, kids' emotions, traditions, and togetherness.
2. Travel & Memories: Scenic views, impressions from new places, travel diary notes.
3. Nature & Harmony: Landscapes, sunsets, sea, outdoor walks, tranquility.
4. Entertainment & Fun: Vibrant weekends, activities, leisure time.

Your task is to craft an engaging, aesthetic Instagram post based on the user's topic or image description.
Output format:
- Catchy headline with emojis.
- Body text (2-4 paragraphs, lively, warm, conversational, authentic).
- Interactive question or call-to-action at the end.
- Hashtag block (8-15 relevant and trending hashtags in English).
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
Create a post for format: {'Instagram Stories' if post_format == 'STORY' else 'Instagram Feed Post'}.
User prompt/topic: {user_topic if user_topic else 'Warm family moment / scenic travel memory'}.

Generate a complete post caption with suitable emojis, an engaging question, and hashtags.
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
        topic_text = f"Topic: {user_topic}\n\n" if user_topic else ""
        return (
            f"Rediscovering the world together ✨🌍\n\n"
            f"{topic_text}"
            f"Every single day brings new moments that are truly worth keeping in our hearts forever.\n\n"
            f"📍 Question of the day: How are you spending your week?\n\n"
            f"#family #travel #nature #moments #lifestyle #wanderlust #memories #inspiration"
        )


ai_service = AIService()
