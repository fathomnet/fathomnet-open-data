"""Image format detection, hashing, and thumbnails."""

import hashlib
import io

from PIL import Image

THUMBNAIL_SIZE = 512
THUMBNAIL_QUALITY = 85

# Some contributed images are large mosaics; allow them but keep a sanity bound.
Image.MAX_IMAGE_PIXELS = 1_000_000_000

# Pillow format -> (key extension, media type)
FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "TIFF": ("tif", "image/tiff"),
}
MEDIA_TYPES = {ext: media_type for ext, media_type in FORMATS.values()}


class UnsupportedImage(ValueError):
    pass


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_format(data: bytes) -> tuple[str, str]:
    """Return (extension, media type) from the image bytes, not the URL."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            fmt = im.format
    except Exception as e:
        raise UnsupportedImage(f"not a readable image: {e}") from e
    if fmt not in FORMATS:
        raise UnsupportedImage(f"unsupported image format {fmt}")
    return FORMATS[fmt]


def _to_rgb(im: Image.Image) -> Image.Image:
    if im.mode in ("I;16", "I;16B", "I;16L", "I"):
        # Scale 16-bit to 8-bit rather than clipping.
        im = im.convert("I").point(lambda v: v / 256).convert("L")
    return im if im.mode == "RGB" else im.convert("RGB")


def make_thumbnail(data: bytes, size: int = THUMBNAIL_SIZE) -> bytes:
    """JPEG with the longest side scaled down to `size` px. Never upscales."""
    with Image.open(io.BytesIO(data)) as im:
        im = _to_rgb(im)
        im.thumbnail((size, size), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
    return out.getvalue()
