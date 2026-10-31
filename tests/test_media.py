import io

import pytest
from PIL import Image

from fathomnet_open_data.media import UnsupportedImage, detect_format, make_thumbnail


def encode(im: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format=fmt)
    return buf.getvalue()


def decode(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    im.load()
    return im


@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        ("PNG", ("png", "image/png")),
        ("JPEG", ("jpg", "image/jpeg")),
        ("TIFF", ("tif", "image/tiff")),
    ],
)
def test_detect_format(fmt, expected):
    assert detect_format(encode(Image.new("RGB", (8, 8)), fmt)) == expected


def test_detect_format_rejects_unsupported_and_garbage():
    with pytest.raises(UnsupportedImage, match="GIF"):
        detect_format(encode(Image.new("P", (8, 8)), "GIF"))
    with pytest.raises(UnsupportedImage):
        detect_format(b"<html>not found</html>")


def test_thumbnail_scales_longest_side():
    thumb = decode(make_thumbnail(encode(Image.new("RGB", (2048, 1024)), "PNG")))
    assert thumb.format == "JPEG" and thumb.size == (512, 256)


def test_thumbnail_never_upscales():
    assert decode(make_thumbnail(encode(Image.new("RGB", (100, 50)), "PNG"))).size == (100, 50)


@pytest.mark.parametrize("mode", ["RGBA", "LA", "P", "L", "CMYK"])
def test_thumbnail_converts_modes_to_rgb(mode):
    fmt = "JPEG" if mode == "CMYK" else "PNG"
    thumb = decode(make_thumbnail(encode(Image.new(mode, (600, 300)), fmt)))
    assert thumb.mode == "RGB"


def test_thumbnail_scales_16_bit():
    im = Image.new("I;16", (600, 300), 65535)
    thumb = decode(make_thumbnail(encode(im, "TIFF")))
    assert thumb.mode == "RGB"
    assert thumb.getpixel((10, 10))[0] >= 250  # full scale, not clipped to garbage
