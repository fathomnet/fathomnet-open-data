"""Step 5: upload a built release's metadata and exports to the store.

Release partitions are immutable: publishing refuses to overwrite one unless forced.
releases.csv is written last so a release is only listed once all its files are in place.
"""

import csv
import io
import logging
from importlib import resources

import pyarrow as pa

from . import schema
from .keys import RELEASES_KEY, coco_key, table_key, table_prefix
from .store import Store
from .workdir import WorkDir

log = logging.getLogger(__name__)

RELEASES_FIELDS = ["release", "n_images", "n_boxes", "n_concepts", "notes"]
BUCKET_FILES = {"README.md": "text/markdown", "LICENSE.md": "text/markdown"}
PARQUET_TYPE = "application/vnd.apache.parquet"


class ReleaseExists(RuntimeError):
    pass


def release_summary(release: str, tables: dict[str, pa.Table], notes: str) -> dict:
    boxes = tables["boxes"]
    return {
        "release": release,
        "n_images": tables["images"].num_rows,
        "n_boxes": boxes.num_rows,
        "n_concepts": len(set(boxes["concept"].drop_null().to_pylist())),
        "notes": notes,
    }


def merge_releases_csv(existing: str | None, row: dict) -> str:
    """Add or replace `row` in releases.csv, sorted by release."""
    rows = {}
    if existing:
        for r in csv.DictReader(io.StringIO(existing)):
            rows[r["release"]] = r
    rows[row["release"]] = row
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=RELEASES_FIELDS, lineterminator="\n")
    writer.writeheader()
    for release in sorted(rows):
        writer.writerow({k: rows[release].get(k, "") for k in RELEASES_FIELDS})
    return out.getvalue()


def published_tables(store: Store, release: str) -> list[str]:
    """Tables that already have files for this release."""
    return [t for t in schema.TABLES if next(store.list_keys(table_prefix(t, release)), None)]


def publish_release(
    store: Store, work: WorkDir, tables: dict[str, pa.Table], notes: str, force: bool = False
) -> dict:
    release = work.release
    existing = published_tables(store, release)
    if existing and not force:
        raise ReleaseExists(f"release {release} already has tables in the store: {existing}")

    for name in schema.TABLES:
        log.info("uploading %s", table_key(name, release))
        store.put_file(table_key(name, release), work.table_file(name), PARQUET_TYPE)
    store.put_file(coco_key(release), work.coco_file, "application/json")

    package = resources.files("fathomnet_open_data") / "bucket"
    for name, content_type in BUCKET_FILES.items():
        store.put_bytes(name, (package / name).read_bytes(), content_type)

    row = release_summary(release, tables, notes)
    current = store.get_bytes(RELEASES_KEY).decode() if store.exists(RELEASES_KEY) else None
    store.put_bytes(
        RELEASES_KEY, merge_releases_csv(current, row).encode(), "text/csv; charset=utf-8"
    )
    return row
