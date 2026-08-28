"""
Internationalization (i18n) translation engine for MemoryNMore.
Loads JSON locale dictionaries and provides localized string resolution.
"""

import os
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")
_LOCALES_CACHE: Dict[str, Dict[str, Any]] = {}
DEFAULT_LOCALE = "ru"
FALLBACK_LOCALE = "en"


def _load_locale(lang: str) -> Dict[str, Any]:
    """Loads and caches a JSON locale file."""
    normalized_lang = "ru" if lang.lower().startswith("ru") else "en"
    if normalized_lang in _LOCALES_CACHE:
        return _LOCALES_CACHE[normalized_lang]

    file_path = os.path.join(LOCALES_DIR, f"{normalized_lang}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _LOCALES_CACHE[normalized_lang] = data
                return data
        except Exception as e:
            logger.error("Failed to load locale %s from %s: %s", normalized_lang, file_path, e)

    # Fallback to default
    default_path = os.path.join(LOCALES_DIR, f"{DEFAULT_LOCALE}.json")
    if os.path.exists(default_path):
        with open(default_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _LOCALES_CACHE[normalized_lang] = data
            return data

    return {}


def t(key: str, lang: str = "ru", **kwargs: Any) -> str:
    """
    Translates a dot-notation key (e.g. 'common.cancel', 'whatsapp.help_text') into localized string.
    Supports variable interpolation, e.g. t('whatsapp.status_account', account_id='12345').
    """
    normalized_lang = "ru" if lang.lower().startswith("ru") else "en"
    locale_data = _load_locale(normalized_lang)

    # Navigate dot-separated key
    keys = key.split(".")
    val: Any = locale_data
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            val = None
            break

    # Fallback to English / Russian if missing
    if val is None and normalized_lang != FALLBACK_LOCALE:
        fallback_data = _load_locale(FALLBACK_LOCALE)
        val = fallback_data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                val = None
                break

    if val is None:
        return key  # Return raw key if not found in any locale

    if isinstance(val, str):
        if kwargs:
            try:
                return val.format(**kwargs)
            except Exception:
                return val
        return val

    return str(val)


get_text = t
