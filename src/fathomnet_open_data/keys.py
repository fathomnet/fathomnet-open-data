"""Bucket key layout. See docs/bucket-layout.md."""

import re
from datetime import date
from pathlib import PurePosixPath

IMAGES_PREFIX = "images/"
THUMBNAILS_PREFIX = "thumbnails/"
MANIFEST_PREFIX = "manifests/objects/"
RELEASES_KEY = "metadata/releases.csv"
DEFAULT_REGION = "us-west-2"

_RELEASE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_release(release: str) -> str:
    """Return the release id if it is a valid YYYY-MM-DD date, else raise ValueError."""
    if not _RELEASE_RE.match(release):
        raise ValueError(f"release must be YYYY-MM-DD, got {release!r}")
    date.fromisoformat(release)
    return release


def image_key(image_uuid: str, ext: str) -> str:
    return f"{IMAGES_PREFIX}{image_uuid}.{ext}"


def thumbnail_key(image_uuid: str) -> str:
    return f"{THUMBNAILS_PREFIX}{image_uuid}.jpg"


def uuid_from_key(key: str) -> str:
    return PurePosixPath(key).stem


def manifest_key(run_id: str, seq: int) -> str:
    return f"{MANIFEST_PREFIX}part-{run_id}-{seq:05d}.parquet"


def table_prefix(table: str, release: str) -> str:
    return f"metadata/{table}/release={release}/"


def table_key(table: str, release: str) -> str:
    return f"{table_prefix(table, release)}part-0000.parquet"


def coco_key(release: str) -> str:
    return f"exports/coco/release={release}/fathomnet-boxes.json"


def s3_public_base_url(bucket: str, region: str = DEFAULT_REGION) -> str:
    return f"https://{bucket}.s3.{region}.amazonaws.com"
