"""Thumbnail generation and storage coordination."""
from __future__ import annotations

import tempfile
from pathlib import Path

from domain.media.image_processor import ImageProcessor
from domain.storage import StorageProvider


class ThumbnailService:
    """Creates and stores small, medium, and large thumbnails."""

    THUMBNAIL_WIDTHS = {
        "small": 240,
        "medium": 640,
        "large": 1280,
    }

    def __init__(self, processor: ImageProcessor, storage: StorageProvider):
        self.processor = processor
        self.storage = storage

    def _thumbnail_key(self, image_id: str, size: str, content_type: str) -> str:
        extension = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }[content_type]
        return f"thumbnails/{image_id}/{size}{extension}"

    def generate_and_store(self, source_path: str, image_id: str, content_type: str) -> dict[str, str]:
        created: dict[str, str] = {}
        temp_paths: list[str] = []

        try:
            for size, width in self.THUMBNAIL_WIDTHS.items():
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(source_path).suffix) as tmp:
                    tmp_path = tmp.name
                temp_paths.append(tmp_path)
                self.processor.generate_thumbnail(source_path, tmp_path, width)
                stored = self.storage.save_as(tmp_path, self._thumbnail_key(image_id, size, content_type), content_type)
                created[size] = stored.storage_key
        except Exception:
            for storage_key in created.values():
                self.storage.delete(storage_key)
            raise
        finally:
            for temp_path in temp_paths:
                Path(temp_path).unlink(missing_ok=True)

        return created
