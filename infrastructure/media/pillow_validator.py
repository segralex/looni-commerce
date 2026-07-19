"""Pillow-backed image validation."""
from __future__ import annotations

from PIL import Image, UnidentifiedImageError


class PillowImageValidator:
    def validate(self, source_path: str) -> None:
        try:
            with Image.open(source_path) as image:
                image.verify()
        except UnidentifiedImageError as exc:
            raise ValueError("Unable to decode image") from exc
