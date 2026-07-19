"""Thumbnail generation and storage coordination."""
from __future__ import annotations

import tempfile
from pathlib import Path

from domain.media.image_processor import ImageProcessor
from domain.storage import StorageProvider, StoredFile


class ThumbnailService:
    """Creates and stores small/medium/large thumbnails."""

    THUMBNAIL_WIDTHS = {
        "small": 240,
        "medium": 640,
        "large": 1280,
    }

    def __init__(self, processor: ImageProcessor, storage: StorageProvider):
        self.processor = processor
        self.storage = storage

    def generate_and_store(self, source_path: str, content_type: str) -> dict[str, StoredFile]:
        created: dict[str, StoredFile] = {}

        try:
            for size, width in self.THUMBNAIL_WIDTHS.items():
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(source_path).suffix) as tmp:
                    tmp_path = tmp.name

                try:
                    self.processor.generate_thumbnail(source_path, tmp_path, width)
                    created[size] = self.storage.save(tmp_path, content_type)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            for stored in created.values():
                self.storage.delete(stored.storage_key)
            raise

        return created
