"""
User language preference storage:
Persists user language preferences to data/user_preferences.json and provides
centralized lookup and update functions for Telegram, WhatsApp, and API channels.
"""

import os
import json
import logging
from typing import Optional, Dict, Union

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data")
USER_PREFS_FILE = os.path.join(DATA_DIR, "user_preferences.json")
_PREFS_CACHE: Dict[str, Dict[str, str]] = {}
_INITIALIZED = False


def _load_preferences() -> Dict[str, Dict[str, str]]:
    global _PREFS_CACHE, _INITIALIZED
    if _INITIALIZED:
        return _PREFS_CACHE

    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(USER_PREFS_FILE):
            with open(USER_PREFS_FILE, "r", encoding="utf-8") as f:
                _PREFS_CACHE = json.load(f)
        else:
            _PREFS_CACHE = {}
    except Exception as e:
        logger.error("Failed to load user preferences: %s", e)
        _PREFS_CACHE = {}
    _INITIALIZED = True
    return _PREFS_CACHE


def _save_preferences() -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(USER_PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(_PREFS_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to save user preferences: %s", e)


def normalize_language(lang: Optional[str]) -> str:
    """Normalizes any language string/code to either 'ru' or 'en'."""
    if not lang:
        return "ru"
    clean = str(lang).lower().strip()
    if clean.startswith("ru") or clean in ("rus", "russian", "русский"):
        return "ru"
    return "en"


def get_user_language(
    user_id: Optional[Union[int, str]] = None,
    state_lang: Optional[str] = None,
    fallback_code: Optional[str] = None
) -> str:
    """
    Returns the user's preferred language.
    Priority:
    1. Explicit state_lang (if provided in current FSM context)
    2. Persisted user preference (from last selection)
    3. Client language code (fallback_code)
    4. Default locale ('ru')
    """
    if state_lang:
        return normalize_language(state_lang)

    if user_id is not None:
        prefs = _load_preferences()
        uid_str = str(user_id)
        if uid_str in prefs and "language" in prefs[uid_str]:
            return normalize_language(prefs[uid_str]["language"])

    if fallback_code:
        return normalize_language(fallback_code)

    return "ru"


def set_user_language(user_id: Union[int, str], lang: str) -> str:
    """
    Persists the user's selected language as their last-used default.
    """
    normalized = normalize_language(lang)
    prefs = _load_preferences()
    uid_str = str(user_id)
    if uid_str not in prefs:
        prefs[uid_str] = {}
    prefs[uid_str]["language"] = normalized
    _save_preferences()
    logger.info("Saved preferred language '%s' for user %s", normalized, uid_str)
    return normalized
