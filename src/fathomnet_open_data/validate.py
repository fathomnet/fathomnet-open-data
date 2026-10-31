"""Step 4: checks that must pass before a release is published."""

from dataclasses import dataclass, field

import pyarrow as pa
import pyarrow.compute as pc

from . import schema

# Fail closed on anything that looks like an email address in any published string column.
EMAIL_PATTERN = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _missing(values: pa.ChunkedArray, allowed: set[str]) -> int:
    return sum(1 for v in values.to_pylist() if v is not None and v not in allowed)


def _check_schemas(tables: dict[str, pa.Table], report: ValidationReport) -> None:
    for name, expected in schema.TABLES.items():
        if name not in tables:
            report.errors.append(f"{name}: table missing")
        elif not tables[name].schema.equals(expected):
            report.errors.append(f"{name}: schema differs from schema.py")


def _check_primary_keys(tables: dict[str, pa.Table], report: ValidationReport) -> None:
    for name, cols in schema.PRIMARY_KEYS.items():
        t = tables[name]
        if t.num_rows == 0:
            continue
        for col in cols:
            if t[col].null_count:
                report.errors.append(f"{name}.{col}: {t[col].null_count} nulls in key")
        distinct = t.group_by(list(cols)).aggregate([]).num_rows
        if distinct != t.num_rows:
            report.errors.append(f"{name}: {t.num_rows - distinct} duplicate keys on {cols}")


def _check_references(tables: dict[str, pa.Table], report: ValidationReport) -> None:
    image_uuids = set(tables["images"]["image_uuid"].to_pylist())
    collection_uuids = set(tables["collections"]["collection_uuid"].to_pylist())
    for name in ("boxes", "tags", "image_collections"):
        n = _missing(tables[name]["image_uuid"], image_uuids)
        if n:
            report.errors.append(f"{name}.image_uuid: {n} rows reference unpublished images")
    n = _missing(tables["image_collections"]["collection_uuid"], collection_uuids)
    if n:
        report.errors.append(f"image_collections.collection_uuid: {n} unknown collections")


def _check_objects(tables: dict[str, pa.Table], object_keys: set[str], report) -> None:
    for col in ("s3_key", "thumbnail_s3_key"):
        n = _missing(tables["images"][col], object_keys)
        if n:
            report.errors.append(f"images.{col}: {n} keys not found in the store")


def _check_emails(tables: dict[str, pa.Table], report: ValidationReport) -> None:
    for name, t in tables.items():
        for col in t.column_names:
            if not pa.types.is_string(t[col].type):
                continue
            hits = pc.sum(pc.match_substring_regex(t[col], EMAIL_PATTERN)).as_py() or 0
            if hits:
                report.errors.append(f"{name}.{col}: {hits} values contain an email address")


def _check_content(tables: dict[str, pa.Table], report: ValidationReport) -> None:
    images, boxes = tables["images"], tables["boxes"]
    if images.num_rows == 0:
        report.errors.append("images: no rows")
    for col in ("image_license",):
        if images[col].null_count:
            report.warnings.append(f"images.{col}: {images[col].null_count} nulls")
    for col in ("annotation_license", "concept"):
        if boxes[col].null_count:
            report.warnings.append(f"boxes.{col}: {boxes[col].null_count} nulls")

    # Boxes outside the image are a data quality issue, not a release blocker.
    sizes = dict(
        zip(
            images["image_uuid"].to_pylist(),
            zip(images["width"].to_pylist(), images["height"].to_pylist()),
            strict=True,
        )
    )
    outside = 0
    for b in boxes.select(["image_uuid", "x", "y", "width", "height"]).to_pylist():
        w, h = sizes.get(b["image_uuid"], (None, None))
        if None in (w, h, b["x"], b["y"], b["width"], b["height"]):
            continue
        if b["x"] < 0 or b["y"] < 0 or b["x"] + b["width"] > w or b["y"] + b["height"] > h:
            outside += 1
    if outside:
        report.warnings.append(f"boxes: {outside} extend outside their image")


def validate_release(tables: dict[str, pa.Table], object_keys: set[str]) -> ValidationReport:
    report = ValidationReport()
    _check_schemas(tables, report)
    if report.errors:
        return report
    _check_primary_keys(tables, report)
    _check_references(tables, report)
    _check_objects(tables, object_keys, report)
    _check_emails(tables, report)
    _check_content(tables, report)
    return report
