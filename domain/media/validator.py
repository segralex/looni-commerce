"""Image validation abstraction."""
from __future__ import annotations

from typing import Protocol


class ImageValidator(Protocol):
    def validate(self, source_path: str) -> None:
        ...
