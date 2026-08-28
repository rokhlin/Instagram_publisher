"""
Compatibility shim for ai_service.
Now located in `src.ai_engine`.
"""

from src.ai_engine import ai_engine, get_ai_engine, GeminiProvider, LocalLLMProvider
from src.ai_engine.providers.gemini_provider import GeminiProvider as AIService

ai_service = ai_engine

__all__ = ["AIService", "ai_service", "ai_engine", "get_ai_engine", "GeminiProvider", "LocalLLMProvider"]
