"""Release steps tying the modules together. The CLI is a thin wrapper over these."""

import dataclasses
import logging

import pyarrow as pa
import pyarrow.parquet as pq

from . import schema, snapshot
from .api import FathomNetClient
from .coco import build_coco, write_coco
from .keys import IMAGES_PREFIX, THUMBNAILS_PREFIX
from .publish import ReleaseExists, publish_release
from .store import Store, StoreIndex
from .sync import Fetch, sync_objects
from .tables import build_tables
from .validate import ValidationReport, validate_release
from .workdir import WorkDir, write_json

log = logging.getLogger(__name__)


class StepError(RuntimeError):
    pass


def _require_snapshot(work: WorkDir) -> None:
    if not snapshot.has_snapshot(work):
        raise StepError(f"no snapshot in {work.base}; run the snapshot step first")


def run_snapshot(client: FathomNetClient, work: WorkDir, refresh: bool = False) -> dict:
    if snapshot.has_snapshot(work) and not refresh:
        log.info("reusing snapshot in %s (pass --refresh to fetch again)", work.raw)
        return {"reused": True}
    return snapshot.take_snapshot(client, work)


def run_sync(
    work: WorkDir,
    store: Store,
    fetch: Fetch | None = None,
    workers: int = 16,
    limit: int | None = None,
) -> dict:
    _require_snapshot(work)
    result = sync_objects(snapshot.read_images(work), store, fetch, workers, limit)
    report = dataclasses.asdict(result)
    write_json(work.report_file("sync"), report)
    if result.failures:
        log.warning(
            "%d images failed to sync; see %s", len(result.failures), work.report_file("sync")
        )
    return report


def run_build(work: WorkDir, store: Store) -> dict:
    _require_snapshot(work)
    index = StoreIndex.load(store)
    result = build_tables(
        snapshot.read_images(work), snapshot.read_uploads(work), snapshot.read_links(work), index
    )
    work.metadata.mkdir(parents=True, exist_ok=True)
    for name, table in result.tables.items():
        pq.write_table(table, work.table_file(name), compression="zstd")
    coco = build_coco(
        result.tables["images"], result.tables["boxes"], work.release, store.public_base_url()
    )
    write_coco(coco, work.coco_file)

    report = {
        "rows": {name: t.num_rows for name, t in result.tables.items()},
        "excluded_images": result.excluded,
        "coco_categories": len(coco["categories"]),
    }
    write_json(work.report_file("build"), report)
    return report


def load_tables(work: WorkDir) -> dict[str, pa.Table]:
    missing = [n for n in schema.TABLES if not work.table_file(n).exists()]
    if missing:
        raise StepError(f"tables not built: {missing}; run the build step first")
    return {n: pq.read_table(work.table_file(n), schema=schema.TABLES[n]) for n in schema.TABLES}


def run_validate(work: WorkDir, store: Store) -> ValidationReport:
    tables = load_tables(work)
    keys = set(store.list_keys(IMAGES_PREFIX)) | set(store.list_keys(THUMBNAILS_PREFIX))
    report = validate_release(tables, keys)
    write_json(work.report_file("validate"), dataclasses.asdict(report))
    for w in report.warnings:
        log.warning(w)
    for e in report.errors:
        log.error(e)
    return report


def run_publish(work: WorkDir, store: Store, notes: str, force: bool = False) -> dict:
    report = run_validate(work, store)
    if not report.ok:
        raise StepError(f"validation failed with {len(report.errors)} errors; not publishing")
    try:
        row = publish_release(store, work, load_tables(work), notes, force)
    except ReleaseExists as e:
        raise StepError(f"{e}; pass --force to overwrite") from e
    write_json(work.report_file("publish"), row)
    return row
