"""End-to-end: fake API -> local store, through every step."""

import csv
import io
import json

import pytest
from PIL import Image

from fathomnet_open_data import pipeline
from fathomnet_open_data.keys import RELEASES_KEY, coco_key, table_key, thumbnail_key
from fathomnet_open_data.schema import TABLES

A = "aaaaaaaa-0000-0000-0000-000000000001"
B = "bbbbbbbb-0000-0000-0000-000000000002"
INVALID = "cccccccc-0000-0000-0000-000000000003"
MISMATCH = "dddddddd-0000-0000-0000-000000000004"


@pytest.fixture
def synced(fake_api, work, store, fetch):
    pipeline.run_snapshot(fake_api, work)
    report = pipeline.run_sync(work, store, fetch, workers=2)
    return report


def test_snapshot_reused_unless_refresh(fake_api, work):
    first = pipeline.run_snapshot(fake_api, work)
    assert first["images"] == 4 and first["image_upload_links"] == 4
    assert pipeline.run_snapshot(fake_api, work) == {"reused": True}
    assert pipeline.run_snapshot(fake_api, work, refresh=True)["images"] == 4


def test_steps_require_snapshot(work, store):
    with pytest.raises(pipeline.StepError):
        pipeline.run_sync(work, store)
    with pytest.raises(pipeline.StepError):
        pipeline.run_build(work, store)


def test_sync_uploads_originals_and_thumbnails(synced, store):
    assert synced["candidates"] == 3  # invalid image excluded
    assert synced["images_uploaded"] == 2
    assert [f["image_uuid"] for f in synced["failures"]] == [MISMATCH]
    assert "sha256 mismatch" in synced["failures"][0]["error"]
    assert store.exists(f"images/{A}.png")
    assert store.exists(f"images/{B}.jpg")  # extension from bytes
    assert not any(store.list_keys(f"images/{INVALID}"))
    with Image.open(io.BytesIO(store.get_bytes(thumbnail_key(A)))) as im:
        assert im.format == "JPEG"


def test_sync_is_incremental(synced, work, store, fetch):
    again = pipeline.run_sync(work, store, fetch, workers=2)
    assert again["already_present"] == 2
    assert again["images_uploaded"] == 0


def test_sync_regenerates_missing_thumbnail_from_store(synced, work, store):
    (store.root / thumbnail_key(A)).unlink()

    def no_network(url):
        raise AssertionError("should not download")

    again = pipeline.run_sync(work, store, lambda url: no_network(url) if A in url else b"", 1)
    assert store.exists(thumbnail_key(A))
    assert again["images_uploaded"] == 0 and again["thumbnails_uploaded"] == 1


def test_build_validate_publish(synced, work, store):
    report = pipeline.run_build(work, store)
    assert report["rows"] == {
        "images": 2,
        "boxes": 3,
        "tags": 1,
        "collections": 1,
        "image_collections": 2,
    }
    assert report["excluded_images"] == {
        "not_valid": 1,
        "missing_objects": 1,
        "rejected_collection": 1,
    }

    validation = pipeline.run_validate(work, store)
    assert validation.ok, validation.errors
    assert any("outside" in w for w in validation.warnings)

    row = pipeline.run_publish(work, store, notes="first release")
    assert row["n_images"] == 2 and row["n_concepts"] == 2
    for name in TABLES:
        assert store.exists(table_key(name, work.release))
    assert store.exists("README.md") and store.exists("LICENSE.md")

    coco = json.loads(store.get_bytes(coco_key(work.release)))
    assert len(coco["images"]) == 2 and len(coco["annotations"]) == 3
    assert {c["name"] for c in coco["categories"]} == {"Nanomia", "Sebastes"}
    assert coco["images"][0]["coco_url"].startswith("file://")

    releases = list(csv.DictReader(io.StringIO(store.get_bytes(RELEASES_KEY).decode())))
    assert releases == [
        {
            "release": work.release,
            "n_images": "2",
            "n_boxes": "3",
            "n_concepts": "2",
            "notes": "first release",
        }
    ]

    with pytest.raises(pipeline.StepError, match="--force"):
        pipeline.run_publish(work, store, notes="again")
    pipeline.run_publish(work, store, notes="again", force=True)


def test_published_files_contain_no_emails(synced, work, store):
    pipeline.run_build(work, store)
    pipeline.run_publish(work, store, notes="")
    for key in store.list_keys(""):
        if key.startswith(("images/", "thumbnails/")):
            continue
        assert b"@example.org" not in store.get_bytes(key), key


def test_publish_refuses_invalid_release(synced, work, store):
    pipeline.run_build(work, store)
    (store.root / thumbnail_key(A)).unlink()
    with pytest.raises(pipeline.StepError, match="validation failed"):
        pipeline.run_publish(work, store, notes="")
    assert not store.exists(RELEASES_KEY)
