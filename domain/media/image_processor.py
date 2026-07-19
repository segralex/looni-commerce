"""Image processor abstraction for thumbnail generation."""
from __future__ import annotations

from typing import Protocol


class ImageProcessor(Protocol):
    """Protocol for image resizing backends."""

    def generate_thumbnail(self, source_path: str, destination_path: str, max_width: int) -> None:
        """Generate a thumbnail from source_path at destination_path.

        Implementations must preserve aspect ratio and must not upscale images.
        """
        ...
