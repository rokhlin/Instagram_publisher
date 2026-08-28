"""
Tag management service: provides hashtag normalization, extraction from caption body,
and persistent JSON storage of user preset tags.
"""

import os
import json
import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

DEFAULT_PRESET_TAGS = [
    "#memoryandmore",
    "#family",
    "#travel",
    "#lifestyle",
    "#moments",
    "#inspiration"
]

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data")
PRESET_TAGS_FILE = os.path.join(DATA_DIR, "preset_tags.json")


class TagService:
    def __init__(self):
        self._ensure_data_file()

    def _ensure_data_file(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(PRESET_TAGS_FILE):
                with open(PRESET_TAGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_PRESET_TAGS, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to initialize preset tags file: %s", e)

    def get_preset_tags(self) -> List[str]:
        try:
            if os.path.exists(PRESET_TAGS_FILE):
                with open(PRESET_TAGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error("Error reading preset tags: %s", e)
        return DEFAULT_PRESET_TAGS.copy()

    def add_preset_tag(self, tag: str) -> bool:
        clean = self.normalize_tag(tag)
        if not clean:
            return False
        tags = self.get_preset_tags()
        if clean not in tags:
            tags.append(clean)
            self._save_preset_tags(tags)
            return True
        return False

    def remove_preset_tag(self, tag: str) -> bool:
        clean = self.normalize_tag(tag)
        tags = self.get_preset_tags()
        if clean in tags:
            tags.remove(clean)
            self._save_preset_tags(tags)
            return True
        return False

    def _save_preset_tags(self, tags: List[str]):
        try:
            with open(PRESET_TAGS_FILE, "w", encoding="utf-8") as f:
                json.dump(tags, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Error saving preset tags: %s", e)

    @staticmethod
    def normalize_tag(tag: str) -> str:
        tag = tag.strip()
        if not tag:
            return ""
        if not tag.startswith("#"):
            tag = f"#{tag}"
        # Remove unwanted punctuation
        tag = re.sub(r"[^\w#]", "", tag, flags=re.UNICODE)
        return tag

    @staticmethod
    def extract_tags_and_body(text: str) -> Tuple[str, List[str]]:
        """
        Separate hashtags from body text.
        """
        lines = text.strip().split("\n")
        tags = []
        body_lines = []

        for line in lines:
            stripped = line.strip()
            # If line is primarily hashtags
            words = stripped.split()
            if words and all(w.startswith("#") for w in words):
                for w in words:
                    clean = TagService.normalize_tag(w)
                    if clean and clean not in tags:
                        tags.append(clean)
            else:
                found_tags = re.findall(r"(#\w+)", stripped)
                if found_tags and len(found_tags) >= len(words) * 0.7:
                    for t in found_tags:
                        clean = TagService.normalize_tag(t)
                        if clean and clean not in tags:
                            tags.append(clean)
                else:
                    body_lines.append(line)

        body = "\n".join(body_lines).strip()
        return body, tags


tag_service = TagService()
