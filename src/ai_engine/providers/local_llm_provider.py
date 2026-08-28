"""
Local LLM AI Engine Provider.
Connects to local LLM instances (LM Studio, Ollama, vLLM, LocalAI) via standard OpenAI-compatible REST API.
"""

import base64
import logging
from typing import Optional, List, Dict, Any
import aiohttp

from src.config import settings
from src.ai_engine.base import BaseAIProvider
from src.business_logic.prompts import (
    get_system_prompt,
    build_caption_prompt,
    build_refine_prompt,
    build_story_overlay_prompt,
    get_fallback_caption,
)

logger = logging.getLogger(__name__)


class LocalLLMProvider(BaseAIProvider):
    """
    OpenAI-compatible HTTP client for local LLM engines (LM Studio, Ollama, vLLM, etc.).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.base_url = (base_url or settings.LOCAL_LLM_URL).rstrip("/")
        self.model_name = model_name or settings.LOCAL_LLM_MODEL
        self.api_key = api_key or settings.LOCAL_LLM_API_KEY or "not-needed"

    async def _post_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 800
    ) -> str:
        """
        Sends request to OpenAI-compatible /chat/completions endpoint.
        """
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=45)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0].get("message", {}).get("content", "").strip()
                        return ""
                    else:
                        error_text = await resp.text()
                        logger.error("Local LLM API error (%s): %s", resp.status, error_text)
                        return ""
        except Exception as e:
            logger.error("Failed to communicate with Local LLM endpoint %s: %s", endpoint, e)
            return ""

    async def generate_caption(
        self,
        image_bytes: Optional[bytes] = None,
        media_items: Optional[List[Dict[str, Any]]] = None,
        instructions: str = "",
        post_format: str = "FEED_PORTRAIT",
        language: str = "ru"
    ) -> str:
        lang_key = "ru" if language.lower().startswith("ru") else "en"
        system_prompt = get_system_prompt(lang_key)
        prompt_text = build_caption_prompt(
            instructions=instructions,
            post_format=post_format,
            language=lang_key
        )

        user_content: Any = []
        
        # Attach image base64 if vision model is available
        if image_bytes:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
            })
        elif media_items:
            for item in media_items[:3]:  # Limit attached images for local context window
                data = item.get("bytes")
                if data:
                    b64_img = base64.b64encode(data).decode("utf-8")
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                    })

        if user_content:
            user_content.append({"type": "text", "text": prompt_text})
        else:
            user_content = prompt_text

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        result = await self._post_chat_completion(messages, temperature=0.7)
        if result:
            return result
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
        lang_key = "ru" if language.lower().startswith("ru") else "en"
        system_prompt = get_system_prompt(lang_key)
        prompt_text = build_refine_prompt(
            current_caption=current_caption,
            correction_instructions=correction_instructions,
            post_format=post_format,
            language=lang_key
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ]

        result = await self._post_chat_completion(messages, temperature=0.7)
        if result:
            return result
        return f"{current_caption}\n\n[Updated with: {correction_instructions}]"

    async def generate_story_overlay_text(
        self,
        image_bytes: Optional[bytes] = None,
        instructions: str = "",
        language: str = "ru"
    ) -> str:
        lang_key = "ru" if language.lower().startswith("ru") else "en"
        prompt = build_story_overlay_prompt(instructions=instructions, language=language)

        messages = [
            {"role": "system", "content": "You are a concise aesthetic micro-copywriter. Output only the short quote."},
            {"role": "user", "content": prompt}
        ]

        result = await self._post_chat_completion(messages, temperature=0.7, max_tokens=100)
        if result:
            return result.strip().strip('"\'')
        return "Создаем воспоминания ✨" if lang_key == "ru" else "Making memories ✨"

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg"
    ) -> str:
        """
        Local LLM text endpoints do not natively support direct audio transcription without Whisper.
        Returns empty to fallback gracefully.
        """
        logger.warning("Local LLM audio transcription is not supported on text completions endpoint.")
        return ""
