from datetime import UTC, datetime

import pyarrow as pa

from fathomnet_open_data import schema
from fathomnet_open_data.tables import (
    box_row,
    collection_row,
    image_row,
    parse_timestamp,
    tag_row,
)

from .conftest import make_box, make_image, png_bytes


def test_parse_timestamp_formats():
    expected = datetime(2025, 8, 1, 11, 11, 47, 842000, tzinfo=UTC)
    assert parse_timestamp("2025-08-01T11:11:47.842Z") == expected
    assert parse_timestamp("2025-08-01T11:11:47.842+00:00") == expected
    assert parse_timestamp("2025-08-01T04:11:47.842-07:00") == expected
    assert parse_timestamp(None) is None and parse_timestamp("") is None


def test_rows_match_schema_columns():
    img = make_image("u1", "https://x/a.png", png_bytes(), boxes=[make_box("b1")])
    tag = {"uuid": "t1", "key": "k", "value": "v", "mediaType": "text/plain"}
    rows = {
        "images": image_row(img, "images/u1.png"),
        "boxes": box_row(img["boundingBoxes"][0], "u1"),
        "tags": tag_row(tag, "u1"),
        "collections": collection_row({"uuid": "c1", "darwinCore": {}}),
    }
    for name, row in rows.items():
        assert list(row) == schema.TABLES[name].names
        pa.Table.from_pylist([row], schema=schema.TABLES[name])  # types are compatible


def test_image_row_derives_media_type_from_key():
    img = make_image("u1", "https://x/a.PNG", png_bytes(), sha="ABC")
    row = image_row(img, "images/u1.jpg")
    assert row["media_type"] == "image/jpeg"
    assert row["sha256"] == "abc"
    assert row["thumbnail_s3_key"] == "thumbnails/u1.jpg"
