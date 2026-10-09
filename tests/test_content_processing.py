"""
Unit tests for [MNM-01] Content Processing & Theme Series:
- 10 AI styles catalog integrity (AC-1)
- 3 variant auto-selection & prompts (AC-2)
- Unified editing style across items (AC-3)
- Instagram music suggestions for video (AC-4)
- Fancy fonts & typography (AC-5)
- Topic series session lifecycle (AC-6, AC-7, AC-8)
"""

import unittest
from io import BytesIO
from PIL import Image

from src.business_logic.prompts.styles import (
    AI_STYLES_CATALOG,
    get_style,
    select_style_variants,
    recommend_music_for_content,
    format_music_recommendation_text,
)
from src.business_logic.topics.topic_manager import TopicManager, TopicSession
from src.business_logic.media.image_processor import (
    ImageProcessor,
    FILTER_REGISTRY,
    FONT_REGISTRY,
)


class TestContentProcessing(unittest.TestCase):

    def test_ac1_ten_styles_catalog_integrity(self):
        """AC-1: Ensure 10 distinct AI styles exist with full prompt and music specifications."""
        expected_styles = [
            "CLEAN_COMMERCIAL",
            "WARM_CAFE",
            "STREET_35MM",
            "GOLDEN_HOUR",
            "ATHLETIC_DRIVE",
            "GOURMET_FOODIE",
            "LUXURY_STUDIO",
            "TECH_CREATOR",
            "BOTANICAL_SPA",
            "VINTAGE_FILM"
        ]
        self.assertEqual(len(AI_STYLES_CATALOG), 10)
        for style_key in expected_styles:
            self.assertIn(style_key, AI_STYLES_CATALOG)
            style = AI_STYLES_CATALOG[style_key]
            self.assertEqual(style["id"], style_key)
            self.assertTrue(style["name_en"])
            self.assertTrue(style["name_ru"])
            self.assertTrue(style["prompt_directive"])
            self.assertTrue(style["negative_constraints"])
            self.assertIn("music", style)
            music = style["music"]
            self.assertTrue(len(music["genres"]) > 0)
            self.assertTrue(music["tempo"])
            self.assertTrue(len(music["keywords"]) > 0)

    def test_ac2_variant_auto_selection(self):
        """AC-2: System automatically analyzes context and selects 3 distinct variants."""
        # Test default fallback yields exactly 3 distinct styles
        variants = select_style_variants(instructions="", count=3)
        self.assertEqual(len(variants), 3)
        variant_ids = [v["id"] for v in variants]
        self.assertEqual(len(set(variant_ids)), 3)

        # Test context matching
        cafe_variants = select_style_variants(instructions="Утренний кофе в кафе с книгой", count=3)
        self.assertIn("WARM_CAFE", [v["id"] for v in cafe_variants])

        fitness_variants = select_style_variants(instructions="Тяжелая тренировка в тренажерном зале", count=3)
        self.assertIn("ATHLETIC_DRIVE", [v["id"] for v in fitness_variants])

    def test_ac4_video_music_recommendation(self):
        """AC-4: Recommend music (genre, tempo, keywords) for Instagram Music Library."""
        music = recommend_music_for_content("ATHLETIC_DRIVE")
        self.assertIn("Phonk", music["genres"])
        self.assertIn("Fast", music["tempo"])
        self.assertIn("gym motivation", music["keywords"])

        # Test text formatting
        formatted_ru = format_music_recommendation_text("GOLDEN_HOUR", lang="ru")
        self.assertIn("Музыка для Instagram", formatted_ru)
        self.assertIn("Поиск в музыке Instagram", formatted_ru)

        formatted_en = format_music_recommendation_text("GOLDEN_HOUR", lang="en")
        self.assertIn("Instagram Reels / Video Music", formatted_en)
        self.assertIn("Search in Instagram Music", formatted_en)

    def test_ac5_fancy_fonts_registry(self):
        """AC-5: Custom typography registry is available for overlaying text."""
        self.assertGreaterEqual(len(FONT_REGISTRY), 5)
        for font_key, font_meta in FONT_REGISTRY.items():
            self.assertTrue(font_meta["name_ru"])
            font = ImageProcessor.get_font(font_key=font_key, base_size=40)
            self.assertIsNotNone(font)

    def test_ac6_ac7_ac8_topic_series_lifecycle(self):
        """
        AC-6: Start topic session with 'тема [описание]'.
        AC-7: Ignore subsequent 'тема' while active and keep adding to current topic.
        AC-8: Close topic with 'тема закрыта'.
        """
        tm = TopicManager()
        user_id = 12345

        # Initial state: no active topic
        self.assertIsNone(tm.get_active_session(user_id))
        self.assertFalse(tm.is_topic_keyword("Привет"))
        self.assertTrue(tm.is_topic_keyword("тема Поездка в Рим"))
        self.assertTrue(tm.is_topic_keyword("тема: Осенний уют"))
        self.assertTrue(tm.is_close_keyword("тема закрыта"))

        # AC-6: Start new topic
        is_new, msg, session = tm.handle_topic_command(user_id, "тема Отпуск 2026")
        self.assertTrue(is_new)
        self.assertEqual(session.description, "Отпуск 2026")
        self.assertTrue(session.is_active)
        self.assertIsNotNone(tm.get_active_session(user_id))

        # Add media to active topic
        item_1 = {"type": "photo", "filename": "photo1.jpg"}
        session.add_media(item_1)
        self.assertEqual(len(session.media_items), 1)

        # AC-7: Send another 'тема' keyword while active -> ignored, keeps active topic
        is_new_2, msg_2, session_2 = tm.handle_topic_command(user_id, "тема Другая тема")
        self.assertFalse(is_new_2)
        self.assertEqual(session_2.description, "Отпуск 2026")
        self.assertIn("Тема уже активна", msg_2)

        # AC-3: Set unified style for topic series
        tm.set_topic_style(user_id, "WARM_CAFE")
        self.assertEqual(session.locked_style, "WARM_CAFE")

        # AC-8: Close topic
        closed_session = tm.close_topic(user_id)
        self.assertIsNotNone(closed_session)
        self.assertEqual(closed_session.description, "Отпуск 2026")
        self.assertFalse(closed_session.is_active)
        self.assertIsNone(tm.get_active_session(user_id))

        # Re-closing when no topic
        self.assertIsNone(tm.close_topic(user_id))

    def test_image_processor_all_10_filters(self):
        """Verify that all 10 styles process images cleanly without runtime errors."""
        img = Image.new("RGB", (200, 200), color=(180, 140, 100))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        sample_bytes = buf.getvalue()

        for style_key in AI_STYLES_CATALOG.keys():
            self.assertIn(style_key, FILTER_REGISTRY)
            processed_bytes = ImageProcessor.process_image(
                input_bytes=sample_bytes,
                post_type="FEED_PORTRAIT",
                filter_name=style_key
            )
            self.assertTrue(len(processed_bytes) > 0)


if __name__ == "__main__":
    unittest.main()
