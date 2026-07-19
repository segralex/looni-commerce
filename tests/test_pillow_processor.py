from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from infrastructure.media.pillow_processor import PillowImageProcessor


def _write_image(path: Path, size: tuple[int, int], image_format: str = "JPEG") -> None:
    image = Image.new("RGB", size, (120, 40, 80))
    image.save(path, format=image_format)


def test_pillow_processor_downscales_and_preserves_aspect_ratio(tmp_path):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "thumb.jpg"
    _write_image(source, (1200, 600), "JPEG")

    processor = PillowImageProcessor()
    processor.generate_thumbnail(str(source), str(destination), max_width=300)

    with Image.open(destination) as generated:
        assert generated.size == (300, 150)


def test_pillow_processor_does_not_upscale(tmp_path):
    source = tmp_path / "source.png"
    destination = tmp_path / "thumb.png"
    _write_image(source, (120, 80), "PNG")

    processor = PillowImageProcessor()
    processor.generate_thumbnail(str(source), str(destination), max_width=600)

    with Image.open(destination) as generated:
        assert generated.size == (120, 80)


def test_pillow_processor_rejects_invalid_image(tmp_path):
    source = tmp_path / "bad.jpg"
    destination = tmp_path / "thumb.jpg"
    source.write_bytes(b"not-image-data")

    processor = PillowImageProcessor()
    with pytest.raises(ValueError, match="invalid image data"):
        processor.generate_thumbnail(str(source), str(destination), max_width=200)
