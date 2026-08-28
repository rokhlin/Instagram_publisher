"""
Google Gemini AI Engine Provider.
Uses the official `google-genai` SDK for multimodal vision, voice transcription, and caption copywriting.
"""

import logging
from typing import Optional, List, Dict, Any

from src.config import settings
from src.ai_engine.base import BaseAIProvider
from src.business_logic.prompts import (
    get_system_prompt,
    build_caption_prompt,
    build_refine_prompt,
    build_story_overlay_prompt,
    build_transcription_prompt,
    get_fallback_caption,
)

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini AI implementation using google-genai SDK.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.6-flash"):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name
        self.client = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini AI Client initialized successfully (model: %s).", self.model_name)
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}")
        else:
            logger.info("Gemini API key not provided; GeminiProvider will use fallback responses.")

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
            prompt = build_transcription_prompt()
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

        prompt = build_story_overlay_prompt(instructions=instructions, language=language)

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
        system_prompt = get_system_prompt(lang_key)

        if not self.client:
            return get_fallback_caption(instructions, post_format, lang_key)

        prompt_text = build_caption_prompt(
            instructions=instructions,
            post_format=post_format,
            language=lang_key
        )

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
            return get_fallback_caption(instructions, post_format, lang_key)

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
        system_prompt = get_system_prompt(lang_key)

        if not self.client:
            return f"{current_caption}\n\n[Edit note: {correction_instructions}]"

        prompt_text = build_refine_prompt(
            current_caption=current_caption,
            correction_instructions=correction_instructions,
            post_format=post_format,
            language=lang_key
        )

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
