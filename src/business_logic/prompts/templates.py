"""
Prompt templates, fallback captions, and helper formatters.
"""

from typing import Optional


FORMAT_NAMES = {
    "STORY": "Instagram Stories",
    "FEED_PORTRAIT": "Instagram Feed Post (Portrait 4:5)",
    "FEED_SQUARE": "Instagram Feed Post (Square 1:1)",
    "CAROUSEL_PORTRAIT": "Instagram Carousel / Album (Multi-Photo & Video Post)",
    "CAROUSEL_SQUARE": "Instagram Carousel / Album (Multi-Photo & Video Post)",
    "REELS": "Instagram Reels Video"
}


def build_caption_prompt(
    instructions: str = "",
    post_format: str = "FEED_PORTRAIT",
    language: str = "ru"
) -> str:
    """Builds prompt text for caption generation."""
    lang_key = "ru" if language.lower().startswith("ru") else "en"
    format_desc = FORMAT_NAMES.get(post_format, "Instagram Post")

    prompt_text = (
        f"Post Format: {format_desc}\n"
        f"Target Language: {'Russian' if lang_key == 'ru' else 'English'}\n"
    )
    if instructions:
        prompt_text += f"User instructions / theme: {instructions}\n\n"
    else:
        prompt_text += "No specific user instructions provided. Please analyze all visual content and the mood of the media files to create a warm, engaging caption.\n\n"

    prompt_text += "Please generate the complete, ready-to-publish Instagram caption."
    return prompt_text


def build_refine_prompt(
    current_caption: str,
    correction_instructions: str,
    post_format: str = "FEED_PORTRAIT",
    language: str = "ru"
) -> str:
    """Builds prompt text for caption refinement."""
    lang_key = "ru" if language.lower().startswith("ru") else "en"
    format_desc = "Instagram Stories" if post_format == "STORY" else "Instagram Feed Post"

    return f"""You need to update and refine an existing Instagram post caption based on the user's feedback/correction instructions.

Current Caption:
\"\"\"
{current_caption}
\"\"\"

User's Correction / Edit Instructions:
\"\"\"
{correction_instructions}
\"\"\"

Format: {format_desc}
Language: {'Russian' if lang_key == 'ru' else 'English'}

Task:
Re-write the Instagram post caption incorporating all user corrections and instructions while keeping the warm, aesthetic, and engaging tone.
Output ONLY the final updated caption (headline, text, question, hashtags) ready for publication.
"""


def build_story_overlay_prompt(
    instructions: str = "",
    language: str = "ru"
) -> str:
    """Builds prompt for story text overlay."""
    lang_key = "ru" if language.lower().startswith("ru") else "en"
    return (
        f"Generate a VERY SHORT, beautiful, aesthetic 1-2 line quote or phrase (under 60 characters total, with 1-2 emojis) "
        f"to place directly on top of this Instagram Story photo.\n"
        f"Target Language: {'Russian' if lang_key == 'ru' else 'English'}.\n"
        f"User instructions: {instructions if instructions else 'Warm aesthetic lifestyle / travel'}.\n"
        f"Output ONLY the short phrase, without quotes or explanations."
    )


def build_transcription_prompt() -> str:
    """Prompt for voice / audio transcription."""
    return (
        "Transcribe this voice message accurately into plain text in the language spoken. "
        "Output ONLY the exact transcribed text with proper punctuation, without any introductions, explanations, quotes, or metadata."
    )


from src.business_logic.i18n import t


def get_fallback_caption(
    instructions: str = "",
    post_format: str = "FEED_PORTRAIT",
    language: str = "ru"
) -> str:
    """Provides fallback caption when AI generation is unavailable."""
    is_ru = language.lower().startswith("ru")
    if instructions:
        topic_text = f"Тема: {instructions}\n\n" if is_ru else f"Topic: {instructions}\n\n"
    else:
        topic_text = ""
    return t("prompts.fallback_caption", lang=language, topic_text=topic_text)

