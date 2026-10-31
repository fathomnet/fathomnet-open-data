import pyarrow as pa

from fathomnet_open_data import schema
from fathomnet_open_data.validate import validate_release


def tables(images=(), boxes=(), tags=(), collections=(), links=()):
    rows = {
        "images": list(images),
        "boxes": list(boxes),
        "tags": list(tags),
        "collections": list(collections),
        "image_collections": list(links),
    }
    return {name: pa.Table.from_pylist(r, schema=schema.TABLES[name]) for name, r in rows.items()}


IMAGE = {
    "image_uuid": "u1",
    "s3_key": "images/u1.png",
    "thumbnail_s3_key": "thumbnails/u1.jpg",
    "width": 100,
    "height": 50,
    "image_license": "CC0-1.0",
}
KEYS = {"images/u1.png", "thumbnails/u1.jpg"}
BOX = {
    "box_uuid": "b1",
    "image_uuid": "u1",
    "concept": "Nanomia",
    "x": 0,
    "y": 0,
    "width": 10,
    "height": 10,
    "annotation_license": "CC0-1.0",
}


def test_valid_release():
    report = validate_release(tables([IMAGE], [BOX]), KEYS)
    assert report.ok and not report.warnings


def test_detects_emails_anywhere():
    tag = {"tag_uuid": "t1", "image_uuid": "u1", "key": "contact", "value": "Jane <j.d@mbari.org>"}
    report = validate_release(tables([IMAGE], [BOX], [tag]), KEYS)
    assert report.errors == ["tags.value: 1 values contain an email address"]


def test_detects_dangling_references_and_duplicates():
    orphan = dict(BOX, box_uuid="b2", image_uuid="nope")
    report = validate_release(tables([IMAGE], [BOX, BOX, orphan]), KEYS)
    assert "boxes: 1 duplicate keys on ('box_uuid',)" in report.errors
    assert "boxes.image_uuid: 1 rows reference unpublished images" in report.errors


def test_detects_missing_objects():
    report = validate_release(tables([IMAGE]), {"images/u1.png"})
    assert report.errors == ["images.thumbnail_s3_key: 1 keys not found in the store"]


def test_schema_mismatch_short_circuits():
    t = tables([IMAGE])
    t["boxes"] = t["boxes"].drop_columns(["concept"])
    report = validate_release(t, KEYS)
    assert report.errors == ["boxes: schema differs from schema.py"]
