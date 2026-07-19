"""Processing state for listing images."""
from __future__ import annotations

from enum import StrEnum


class ImageProcessingStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


def infer_processing_status(thumbnails_present: bool) -> ImageProcessingStatus:
    """Infer legacy image processing state from stored thumbnail metadata."""
    return ImageProcessingStatus.READY if thumbnails_present else ImageProcessingStatus.PENDING


def sanitize_processing_error(error: Exception | str) -> str:
    """Map internal failures to a safe, user-facing summary."""
    message = str(error).lower()
    if "decode" in message or "identify" in message or "image" in message:
        return "Unable to decode image"
    if "storage" in message or "file" in message or "save" in message:
        return "Storage operation failed"
    return "Thumbnail generation failed"
