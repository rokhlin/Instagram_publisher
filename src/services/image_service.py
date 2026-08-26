import os
from io import BytesIO
from typing import Tuple, Literal
from PIL import Image, ImageEnhance, ImageOps

PostType = Literal["STORY", "FEED_PORTRAIT", "FEED_SQUARE"]

TARGET_SIZES = {
    "STORY": (1080, 1920),         # 9:16
    "FEED_PORTRAIT": (1080, 1350), # 4:5
    "FEED_SQUARE": (1080, 1080),   # 1:1
}


class ImageService:
    @staticmethod
    def process_image(
        input_bytes: bytes,
        post_type: PostType = "STORY",
        contrast_factor: float = 1.08,
        color_factor: float = 1.05,
        output_format: str = "JPEG",
        quality: int = 95
    ) -> bytes:
        """
        Resize, crop and enhance image for Instagram publishing.
        """
        with Image.open(BytesIO(input_bytes)) as img:
            img = img.convert("RGB")
            
            # Apply EXIF rotation if needed
            img = ImageOps.exif_transpose(img)

            target_size = TARGET_SIZES.get(post_type, (1080, 1920))
            
            # Fit and center crop
            img_cropped = ImageOps.fit(img, target_size, centering=(0.5, 0.5))

            # Image enhancement
            if contrast_factor != 1.0:
                img_cropped = ImageEnhance.Contrast(img_cropped).enhance(contrast_factor)
            if color_factor != 1.0:
                img_cropped = ImageEnhance.Color(img_cropped).enhance(color_factor)

            output_io = BytesIO()
            img_cropped.save(output_io, format=output_format, quality=quality, optimize=True)
            return output_io.getvalue()

    @staticmethod
    def save_to_file(image_bytes: bytes, filepath: str) -> str:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return filepath
