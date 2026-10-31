import io

import pytest
from PIL import Image

from fathomnet_open_data.media import ImageInfo, UnsupportedImage, inspect_image, make_thumbnail


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
        ("PNG", ImageInfo("png", "image/png", 8, 6)),
        ("JPEG", ImageInfo("jpg", "image/jpeg", 8, 6)),
        ("TIFF", ImageInfo("tif", "image/tiff", 8, 6)),
    ],
)
def test_inspect_image(fmt, expected):
    assert inspect_image(encode(Image.new("RGB", (8, 6)), fmt)) == expected


def test_inspect_image_rejects_unsupported_and_garbage():
    with pytest.raises(UnsupportedImage, match="GIF"):
        inspect_image(encode(Image.new("P", (8, 8)), "GIF"))
    with pytest.raises(UnsupportedImage):
        inspect_image(b"<html>not found</html>")


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
