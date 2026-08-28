"""
Mention management service: provides Instagram user mention normalization,
validation, and persistent JSON storage of user preset mentions.
"""

import os
import json
import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data")
PRESET_MENTIONS_FILE = os.path.join(DATA_DIR, "preset_mentions.json")

DEFAULT_PRESET_MENTIONS = []


class MentionService:
    def __init__(self):
        self._ensure_data_file()

    def _ensure_data_file(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(PRESET_MENTIONS_FILE):
                with open(PRESET_MENTIONS_FILE, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_PRESET_MENTIONS, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to initialize preset mentions file: %s", e)

    def get_preset_mentions(self) -> List[str]:
        try:
            if os.path.exists(PRESET_MENTIONS_FILE):
                with open(PRESET_MENTIONS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error("Error reading preset mentions: %s", e)
        return DEFAULT_PRESET_MENTIONS.copy()

    def add_preset_mention(self, mention: str) -> bool:
        clean = self.normalize_mention(mention)
        if not clean:
            return False
        mentions = self.get_preset_mentions()
        if clean not in mentions:
            mentions.append(clean)
            self._save_preset_mentions(mentions)
            return True
        return False

    def remove_preset_mention(self, mention: str) -> bool:
        clean = self.normalize_mention(mention)
        mentions = self.get_preset_mentions()
        if clean in mentions:
            mentions.remove(clean)
            self._save_preset_mentions(mentions)
            return True
        return False

    def _save_preset_mentions(self, mentions: List[str]):
        try:
            with open(PRESET_MENTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(mentions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Error saving preset mentions: %s", e)

    @staticmethod
    def normalize_mention(mention: str) -> str:
        mention = mention.strip()
        if not mention:
            return ""
        if not mention.startswith("@"):
            mention = f"@{mention}"
        # Only allow valid Instagram username characters (letters, numbers, underscores, periods)
        mention = re.sub(r"[^\w@.]", "", mention)
        return mention


mention_service = MentionService()
