"""Step 1: snapshot FathomNet metadata from the REST API into the work directory.

The raw snapshot contains personal information (emails) and must never be published; only the
tables built from it are.
"""

import logging
from collections.abc import Iterator
from datetime import UTC, datetime

from .api import FathomNetClient
from .workdir import WorkDir, read_jsonl_gz, write_json, write_jsonl_gz

log = logging.getLogger(__name__)

IMAGES = "images"
UPLOADS = "uploads"
LINKS = "image_uploads"


def _dedupe_images(images: Iterator[dict], counter: dict) -> Iterator[dict]:
    seen: set[str] = set()
    for img in images:
        if img["uuid"] in seen:
            counter["duplicates"] += 1
            continue
        seen.add(img["uuid"])
        if len(seen) % 50000 == 0:
            log.info("fetched %d images", len(seen))
        yield img


def take_snapshot(client: FathomNetClient, work: WorkDir) -> dict:
    taken_at = datetime.now(UTC).isoformat()
    expected = client.count_images()
    counter = {"duplicates": 0}

    n_images = write_jsonl_gz(work.raw_file(IMAGES), _dedupe_images(client.iter_images(), counter))
    uploads = list(client.iter_uploads())
    write_jsonl_gz(work.raw_file(UPLOADS), uploads)

    def links() -> Iterator[dict]:
        for upload in uploads:
            for image_uuid in client.iter_upload_image_uuids(upload["uuid"]):
                yield {"collection_uuid": upload["uuid"], "image_uuid": image_uuid}

    n_links = write_jsonl_gz(work.raw_file(LINKS), links())

    summary = {
        "taken_at": taken_at,
        "api": client.base_url,
        "images": n_images,
        "images_expected": expected,
        "duplicate_image_rows": counter["duplicates"],
        "uploads": len(uploads),
        "image_upload_links": n_links,
    }
    if n_images != expected:
        # Paging while the database changes can skip or repeat rows.
        log.warning("snapshot has %d images but the API reported %d", n_images, expected)
    write_json(work.report_file("snapshot"), summary)
    return summary


def has_snapshot(work: WorkDir) -> bool:
    return work.report_file("snapshot").exists()


def read_images(work: WorkDir) -> Iterator[dict]:
    return read_jsonl_gz(work.raw_file(IMAGES))


def read_uploads(work: WorkDir) -> Iterator[dict]:
    return read_jsonl_gz(work.raw_file(UPLOADS))


def read_links(work: WorkDir) -> Iterator[dict]:
    return read_jsonl_gz(work.raw_file(LINKS))


def is_public(image: dict) -> bool:
    """Images eligible for the bucket: those the FathomNet validation job marked valid."""
    return image.get("valid") is True
