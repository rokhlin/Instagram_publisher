"""
Media processing module for Instagram publishing.
Handles image scaling, aspect-ratio cropping, aesthetic visual filters, and typography overlays.
"""

import os
import textwrap
import logging
from io import BytesIO
from typing import Tuple, Literal, Optional, List, Dict
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

PostType = Literal["STORY", "FEED_PORTRAIT", "FEED_SQUARE", "CAROUSEL_PORTRAIT", "CAROUSEL_SQUARE", "REELS"]

TARGET_SIZES = {
    "STORY": (1080, 1920),             # 9:16
    "FEED_PORTRAIT": (1080, 1350),     # 4:5
    "FEED_SQUARE": (1080, 1080),       # 1:1
    "CAROUSEL_PORTRAIT": (1080, 1350), # 4:5
    "CAROUSEL_SQUARE": (1080, 1080),   # 1:1
    "REELS": (1080, 1920),             # 9:16
}

FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "fonts")

FONT_REGISTRY = {
    "MODERN": {
        "name_ru": "🔤 Modern Sans",
        "name_en": "🔤 Modern Sans",
        "file": os.path.join(FONTS_DIR, "Montserrat.ttf"),
        "scale": 1.0,
    },
    "HANDWRITING": {
        "name_ru": "🖋 Рукописный",
        "name_en": "🖋 Handwriting",
        "file": os.path.join(FONTS_DIR, "Caveat.ttf"),
        "scale": 1.35,  # Caveat is cursive and looks best slightly larger
    },
    "SERIF": {
        "name_ru": "📜 Элегантный Serif",
        "name_en": "📜 Elegant Serif",
        "file": os.path.join(FONTS_DIR, "PlayfairDisplay.ttf"),
        "scale": 1.05,
    },
    "ROUNDED": {
        "name_ru": "🪶 Ретро Rounded",
        "name_en": "🪶 Retro Rounded",
        "file": os.path.join(FONTS_DIR, "Comfortaa.ttf"),
        "scale": 0.95,
    },
    "IMPACT": {
        "name_ru": "⚡️ Акцентный Bold",
        "name_en": "⚡️ Impact Bold",
        "file": os.path.join(FONTS_DIR, "Oswald.ttf"),
        "scale": 1.1,
    }
}

FILTER_REGISTRY = {
    "ORIGINAL": {
        "name_ru": "🔘 Оригинал",
        "name_en": "🔘 Original",
        "desc": "Natural balanced colors"
    },
    "GOLDEN_HOUR": {
        "name_ru": "☀️ Золотой час",
        "name_en": "☀️ Golden Hour",
        "desc": "Warm sunlight glow & golden tones"
    },
    "VINTAGE_FILM": {
        "name_ru": "🎞 Винтаж / Плёнка",
        "name_en": "🎞 Vintage Film",
        "desc": "Analog film tones & soft shadows"
    },
    "CINEMATIC": {
        "name_ru": "🌊 Кинематограф",
        "name_en": "🌊 Cinematic Cool",
        "desc": "Teal & amber moody depth"
    },
    "BW_NOIR": {
        "name_ru": "🖤 Ч/Б Нуар",
        "name_en": "🖤 B&W Noir",
        "desc": "High contrast deep monochrome"
    },
    "VIBRANT": {
        "name_ru": "🍓 Сочный / Яркий",
        "name_en": "🍓 Vibrant Pop",
        "desc": "Punchy vivid colors and clarity"
    },
    "DREAMY": {
        "name_ru": "✨ Мягкий свет",
        "name_en": "✨ Dreamy Glow",
        "desc": "Soft pastel bloom and dreamy blur"
    }
}


class ImageProcessor:
    @staticmethod
    def get_font(font_key: str = "MODERN", base_size: int = 44) -> ImageFont.ImageFont:
        font_info = FONT_REGISTRY.get(font_key, FONT_REGISTRY["MODERN"])
        font_path = font_info["file"]
        actual_size = int(base_size * font_info.get("scale", 1.0))

        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size=actual_size)
            except Exception as e:
                logger.warning("Failed loading font %s: %s", font_path, e)

        # Fallbacks
        system_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "arial.ttf"
        ]
        for sys_path in system_candidates:
            if os.path.exists(sys_path):
                try:
                    return ImageFont.truetype(sys_path, size=actual_size)
                except Exception:
                    pass

        return ImageFont.load_default()

    @staticmethod
    def apply_filter(img: Image.Image, filter_name: str = "ORIGINAL") -> Image.Image:
        """
        Applies aesthetic color and lighting filter to PIL Image.
        """
        img = img.convert("RGB")
        filter_name = filter_name.upper()

        if filter_name == "GOLDEN_HOUR":
            # Warm golden tint: boost red and green slightly, lower blue
            r, g, b = img.split()
            r = r.point(lambda i: min(255, int(i * 1.08 + 10)))
            g = g.point(lambda i: min(255, int(i * 1.03 + 4)))
            b = b.point(lambda i: max(0, int(i * 0.92 - 6)))
            merged = Image.merge("RGB", (r, g, b))
            merged = ImageEnhance.Contrast(merged).enhance(1.08)
            merged = ImageEnhance.Color(merged).enhance(1.15)
            return merged

        elif filter_name == "VINTAGE_FILM":
            # Analog film look: slightly muted colors, warm faded shadows
            r, g, b = img.split()
            # Lift deep shadows, soft compress highlights
            r = r.point(lambda i: int(i * 0.95 + 16))
            g = g.point(lambda i: int(i * 0.93 + 12))
            b = b.point(lambda i: int(i * 0.88 + 18))
            merged = Image.merge("RGB", (r, g, b))
            merged = ImageEnhance.Contrast(merged).enhance(0.96)
            merged = ImageEnhance.Color(merged).enhance(0.90)
            return merged

        elif filter_name == "CINEMATIC":
            # Teal & Orange / Cinematic grade
            r, g, b = img.split()
            r = r.point(lambda i: min(255, int(i * 1.05 + 6)) if i > 110 else int(i * 0.94))
            g = g.point(lambda i: int(i * 1.02))
            b = b.point(lambda i: min(255, int(i * 1.10 + 12)) if i < 140 else int(i * 0.92))
            merged = Image.merge("RGB", (r, g, b))
            merged = ImageEnhance.Contrast(merged).enhance(1.14)
            merged = ImageEnhance.Color(merged).enhance(1.08)
            return merged

        elif filter_name == "BW_NOIR":
            # High-contrast dramatic black and white
            gray = ImageOps.grayscale(img)
            gray = ImageEnhance.Contrast(gray).enhance(1.30)
            gray = ImageEnhance.Brightness(gray).enhance(0.98)
            return gray.convert("RGB")

        elif filter_name == "VIBRANT":
            # Punchy vibrant saturation and crispness
            enhanced = ImageEnhance.Color(img).enhance(1.35)
            enhanced = ImageEnhance.Contrast(enhanced).enhance(1.12)
            enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.15)
            return enhanced

        elif filter_name == "DREAMY":
            # Soft glow / bloom diffusion
            glow = img.filter(ImageFilter.GaussianBlur(radius=10))
            blended = Image.blend(img, glow, alpha=0.32)
            blended = ImageEnhance.Brightness(blended).enhance(1.05)
            blended = ImageEnhance.Contrast(blended).enhance(1.02)
            blended = ImageEnhance.Color(blended).enhance(1.10)
            return blended

        else:
            # ORIGINAL (Baseline enhancement)
            enhanced = ImageEnhance.Contrast(img).enhance(1.06)
            enhanced = ImageEnhance.Color(enhanced).enhance(1.05)
            return enhanced

    @staticmethod
    def process_image(
        input_bytes: bytes,
        post_type: PostType = "STORY",
        filter_name: str = "ORIGINAL",
        output_format: str = "JPEG",
        quality: int = 95
    ) -> bytes:
        """
        Resize, crop and apply filter/enhancement for Instagram publishing.
        """
        with Image.open(BytesIO(input_bytes)) as img:
            img = img.convert("RGB")
            img = ImageOps.exif_transpose(img)

            target_size = TARGET_SIZES.get(post_type, (1080, 1920))
            img_cropped = ImageOps.fit(img, target_size, centering=(0.5, 0.5))

            # Apply selected visual filter
            img_filtered = ImageProcessor.apply_filter(img_cropped, filter_name=filter_name)

            output_io = BytesIO()
            img_filtered.save(output_io, format=output_format, quality=quality, optimize=True)
            return output_io.getvalue()

    @staticmethod
    def overlay_text_on_image(
        image_bytes: bytes,
        text: str,
        post_type: str = "STORY",
        font_key: str = "MODERN",
        font_size: Optional[int] = None,
        padding_x: int = 44,
        padding_y: int = 24,
        output_format: str = "JPEG",
        quality: int = 95
    ) -> bytes:
        """
        Renders aesthetic text overlay with selected decorative font and translucent rounded backdrop.
        """
        if not text or not text.strip():
            return image_bytes

        clean_text = text.strip()

        with Image.open(BytesIO(image_bytes)) as base_img:
            base_img = base_img.convert("RGBA")
            width, height = base_img.size

            if not font_size:
                font_size = max(38, int(height * 0.026))

            font = ImageProcessor.get_font(font_key=font_key, base_size=font_size)

            # Max width constraint
            max_text_width = width - 240
            words = clean_text.split()
            lines = []
            current_line = []

            draw_temp = ImageDraw.Draw(base_img)

            for word in words:
                test_line = " ".join(current_line + [word])
                bbox = draw_temp.textbbox((0, 0), test_line, font=font)
                w = bbox[2] - bbox[0]
                if w <= max_text_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
                        current_line = []
            if current_line:
                lines.append(" ".join(current_line))

            if not lines:
                lines = [clean_text]

            # Measure lines
            line_heights = []
            line_widths = []
            for line in lines:
                bbox = draw_temp.textbbox((0, 0), line, font=font)
                lw = bbox[2] - bbox[0]
                lh = bbox[3] - bbox[1]
                line_widths.append(lw)
                line_heights.append(lh)

            total_text_width = max(line_widths) if line_widths else 200
            line_spacing = int(font_size * 0.35)
            total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)

            pill_width = total_text_width + (padding_x * 2)
            pill_height = total_text_height + (padding_y * 2)
            pill_x = (width - pill_width) // 2

            if post_type in ("STORY", "REELS"):
                pill_y = int(height * 0.72)
            else:
                pill_y = int(height * 0.75)

            pill_y = min(pill_y, height - pill_height - 120)

            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            # Translucent rounded pill background
            pill_box = [pill_x, pill_y, pill_x + pill_width, pill_y + pill_height]
            pill_radius = min(28, pill_height // 2)
            draw.rounded_rectangle(pill_box, radius=pill_radius, fill=(12, 14, 18, 185))

            # Draw text
            current_y = pill_y + padding_y
            for idx, line in enumerate(lines):
                lw = line_widths[idx]
                text_x = pill_x + (pill_width - lw) // 2
                draw.text((text_x, current_y), line, font=font, fill=(255, 255, 255, 255))
                current_y += line_heights[idx] + line_spacing

            final_img = Image.alpha_composite(base_img, overlay).convert("RGB")

            output_io = BytesIO()
            final_img.save(output_io, format=output_format, quality=quality, optimize=True)
            return output_io.getvalue()

    @staticmethod
    def save_to_file(image_bytes: bytes, filepath: str) -> str:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return filepath


# Backward compatibility alias
ImageService = ImageProcessor
image_processor = ImageProcessor()
