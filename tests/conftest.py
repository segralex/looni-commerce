from io import BytesIO

from PIL import Image


def make_jpeg_bytes(
    width: int = 100,
    height: int = 100,
) -> bytes:
    buffer = BytesIO()

    image = Image.new(
        "RGB",
        (width, height),
        "white",
    )
    image.save(buffer, format="JPEG")

    return buffer.getvalue()
