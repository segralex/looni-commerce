"""Pillow-based image processor implementation."""
from __future__ import annotations

from PIL import Image, ImageOps, UnidentifiedImageError


class PillowImageProcessor:
    """Generates resized thumbnails with Pillow."""

    def generate_thumbnail(self, source_path: str, destination_path: str, max_width: int) -> None:
        if max_width <= 0:
            raise ValueError("max_width must be greater than zero")

        try:
            with Image.open(source_path) as img:
                image = ImageOps.exif_transpose(img)
                width, height = image.size

                if width > max_width:
                    scale = max_width / float(width)
                    new_size = (max_width, max(1, int(height * scale)))
                    image = image.resize(new_size, Image.Resampling.LANCZOS)

                image_format = image.format or img.format or "JPEG"
                save_kwargs: dict[str, object] = {}
                if image_format.upper() in {"JPEG", "JPG"} and image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                if image_format.upper() in {"JPEG", "JPG", "WEBP"}:
                    save_kwargs["quality"] = 90

                image.save(destination_path, format=image_format, **save_kwargs)
        except UnidentifiedImageError as exc:
            raise ValueError("invalid image data") from exc
