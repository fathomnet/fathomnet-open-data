"""End-to-end: fake API -> local store, through every step."""

import csv
import io
import json

import pyarrow.parquet as pq
import pytest
from PIL import Image

from fathomnet_open_data import pipeline
from fathomnet_open_data.keys import (
    MANIFEST_PREFIX,
    RELEASES_KEY,
    coco_key,
    table_key,
    thumbnail_key,
)
from fathomnet_open_data.media import sha256_hex
from fathomnet_open_data.schema import TABLES
from fathomnet_open_data.store import StoreIndex

A = "aaaaaaaa-0000-0000-0000-000000000001"
B = "bbbbbbbb-0000-0000-0000-000000000002"
INVALID = "cccccccc-0000-0000-0000-000000000003"
MISMATCH = "dddddddd-0000-0000-0000-000000000004"
WRONG_SIZE = "eeeeeeee-0000-0000-0000-000000000005"


@pytest.fixture
def synced(fake_api, work, store, fetch):
    pipeline.run_snapshot(fake_api, work)
    report = pipeline.run_sync(work, store, fetch, workers=2)
    return report


def test_snapshot_reused_unless_refresh(fake_api, work):
    first = pipeline.run_snapshot(fake_api, work)
    assert first["images"] == 5 and first["image_upload_links"] == 4
    assert pipeline.run_snapshot(fake_api, work) == {"reused": True}
    assert pipeline.run_snapshot(fake_api, work, refresh=True)["images"] == 5


def test_steps_require_snapshot(work, store):
    with pytest.raises(pipeline.StepError):
        pipeline.run_sync(work, store)
    with pytest.raises(pipeline.StepError):
        pipeline.run_build(work, store)


def test_sync_uploads_originals_and_thumbnails(synced, store):
    assert synced["candidates"] == 4  # invalid image excluded
    assert synced["images_uploaded"] == 3
    assert [f["image_uuid"] for f in synced["failures"]] == [WRONG_SIZE]
    assert "sha256 and size differ" in synced["failures"][0]["error"]
    assert store.exists(f"images/{A}.png")
    assert store.exists(f"images/{B}.jpg")  # extension from bytes
    assert not any(store.list_keys(f"images/{INVALID}"))
    with Image.open(io.BytesIO(store.get_bytes(thumbnail_key(A)))) as im:
        assert im.format == "JPEG"


def test_sync_is_incremental(synced, work, store, fetch):
    again = pipeline.run_sync(work, store, fetch, workers=2)
    assert again["already_present"] == 3
    assert again["images_uploaded"] == 0 and again["manifest_entries"] == 0


def test_sync_accepts_bad_fathomnet_checksum_when_size_matches(synced, store, blobs):
    actual = sha256_hex(blobs["https://img.test/bad-sha.png"])
    assert synced["checksum_mismatches"] == [
        {"image_uuid": MISMATCH, "api_sha256": "0" * 64, "sha256": actual}
    ]
    assert StoreIndex.load(store).checksums[MISMATCH] == actual


def test_manifest_records_stored_bytes(synced, store):
    index = StoreIndex.load(store)
    assert set(index.checksums) == {A, B, MISMATCH}
    for uuid, key in index.images.items():
        assert index.checksums[uuid] == sha256_hex(store.get_bytes(key))


def test_sync_rebuilds_lost_manifest_without_downloading(synced, work, store, blobs):
    for key in list(store.list_keys(MANIFEST_PREFIX)):
        (store.root / key).unlink()

    def only_failed_image(url):
        # The rejected image is retried; stored images are hashed from the store.
        assert url.endswith("wrong-size.png"), f"should not download {url}"
        return blobs[url]

    again = pipeline.run_sync(work, store, only_failed_image, workers=2)
    assert again["manifest_entries"] == 3 and again["images_uploaded"] == 0
    assert set(StoreIndex.load(store).checksums) == {A, B, MISMATCH}


def test_interrupted_sync_resumes(fake_api, work, store, blobs):
    pipeline.run_snapshot(fake_api, work)

    def crash_on_b(url):
        if url.endswith("b.jpg"):
            raise RuntimeError("simulated crash")  # not a per-image error: stops the run
        return blobs[url]

    with pytest.raises(RuntimeError):
        pipeline.run_sync(work, store, crash_on_b, workers=1)

    fetched = []

    def recording(url):
        fetched.append(url)
        return blobs[url]

    pipeline.run_sync(work, store, recording, workers=1)
    index = StoreIndex.load(store)
    assert all(index.complete(u) for u in (A, B, MISMATCH))
    assert "https://img.test/a.png" not in fetched  # uploaded before the crash, not refetched


def test_sync_regenerates_missing_thumbnail_from_store(synced, work, store):
    (store.root / thumbnail_key(A)).unlink()

    def no_network(url):
        raise AssertionError("should not download")

    again = pipeline.run_sync(work, store, lambda url: no_network(url) if A in url else b"", 1)
    assert store.exists(thumbnail_key(A))
    assert again["images_uploaded"] == 0 and again["thumbnails_uploaded"] == 1


def test_build_validate_publish(synced, work, store, blobs):
    report = pipeline.run_build(work, store)
    assert report["rows"] == {
        "images": 3,
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

    images = pq.read_table(work.table_file("images")).to_pylist()
    sha = {r["image_uuid"]: r["sha256"] for r in images}
    assert sha[MISMATCH] == sha256_hex(blobs["https://img.test/bad-sha.png"])

    row = pipeline.run_publish(work, store, notes="first release")
    assert row["n_images"] == 3 and row["n_concepts"] == 2
    for name in TABLES:
        assert store.exists(table_key(name, work.release))
    assert store.exists("README.md") and store.exists("LICENSE.md")

    coco = json.loads(store.get_bytes(coco_key(work.release)))
    assert len(coco["images"]) == 3 and len(coco["annotations"]) == 3
    assert {c["name"] for c in coco["categories"]} == {"Nanomia", "Sebastes"}
    assert coco["images"][0]["coco_url"].startswith("file://")

    releases = list(csv.DictReader(io.StringIO(store.get_bytes(RELEASES_KEY).decode())))
    assert releases == [
        {
            "release": work.release,
            "n_images": "3",
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


def test_fatal_error_stops_sync_without_draining_queue(store):
    import threading

    import pytest

    from fathomnet_open_data.sync import sync_objects

    from .conftest import make_image, png_bytes

    data = png_bytes()
    images = [make_image(f"u{i:04d}", f"https://img.test/{i}.png", data) for i in range(200)]
    calls = []
    lock = threading.Lock()

    def fetch(url):
        with lock:
            calls.append(url)
        raise RuntimeError("store credentials expired")  # not a per-image error

    with pytest.raises(RuntimeError):
        sync_objects(images, store, fetch=fetch, workers=2)
    assert len(calls) < 20


def test_dropped_store_connection_is_a_per_image_failure(fake_api, fetch, store):
    from botocore.exceptions import ConnectionClosedError

    from fathomnet_open_data.sync import sync_objects

    real_put = store.put_bytes

    def flaky_put(key, data, content_type, metadata=None):
        if key.startswith("images/aaaaaaaa"):
            raise ConnectionClosedError(endpoint_url="https://bucket.test/" + key)
        return real_put(key, data, content_type, metadata)

    store.put_bytes = flaky_put
    result = sync_objects(fake_api.iter_images(), store, fetch=fetch, workers=1)
    failed = {f["image_uuid"] for f in result.failures}
    assert "aaaaaaaa-0000-0000-0000-000000000001" in failed
    assert result.images_uploaded >= 1  # the run kept going
