"""Step 3a: build the published metadata tables from a snapshot and the store index.

Only fields listed in schema.py are copied. Emails (contributorsEmail, observer, reviewer, upload
contributor and archive paths) are intentionally never read.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import PurePosixPath

import pyarrow as pa

from . import schema
from .keys import thumbnail_key
from .media import MEDIA_TYPES
from .snapshot import is_public
from .store import StoreIndex


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    ts = datetime.fromisoformat(value)
    return ts.astimezone(UTC) if ts.tzinfo else ts.replace(tzinfo=UTC)


def clean_label(value: str | None) -> str | None:
    """Strip surrounding whitespace; a blank label becomes null so it is not counted as a concept."""
    if value is None:
        return None
    return value.strip() or None


def image_row(img: dict, s3_key: str, sha256: str) -> dict:
    """`sha256` is of the stored object (from the manifest), not FathomNet's stored value."""
    ext = PurePosixPath(s3_key).suffix.lstrip(".")
    return {
        "image_uuid": img["uuid"],
        "s3_key": s3_key,
        "thumbnail_s3_key": thumbnail_key(img["uuid"]),
        "source_url": img.get("url"),
        "sha256": sha256,
        "media_type": MEDIA_TYPES.get(ext),
        "width": img.get("width"),
        "height": img.get("height"),
        "image_license": img.get("imageLicense"),
        "imaging_type": img.get("imagingType"),
        "recorded_timestamp": parse_timestamp(img.get("timestamp")),
        "latitude": img.get("latitude"),
        "longitude": img.get("longitude"),
        "depth_meters": img.get("depthMeters"),
        "altitude_meters": img.get("altitude"),
        "temperature_celsius": img.get("temperatureCelsius"),
        "salinity": img.get("salinity"),
        "oxygen_ml_l": img.get("oxygenMlL"),
        "pressure_dbar": img.get("pressureDbar"),
        "modified_timestamp": parse_timestamp(img.get("lastUpdatedTimestamp")),
    }


def box_row(box: dict, image_uuid: str) -> dict:
    return {
        "box_uuid": box["uuid"],
        "image_uuid": image_uuid,
        "concept": clean_label(box.get("concept")),
        "alt_concept": clean_label(box.get("altConcept")),
        "x": box.get("x"),
        "y": box.get("y"),
        "width": box.get("width"),
        "height": box.get("height"),
        "group_of": box.get("groupOf"),
        "occluded": box.get("occluded"),
        "truncated": box.get("truncated"),
        "review_state": box.get("reviewState"),
        "last_reviewed_timestamp": parse_timestamp(box.get("lastReviewedTimestamp")),
        "user_defined_key": box.get("userDefinedKey"),
        "annotation_license": box.get("annotationLicense"),
        "modified_timestamp": parse_timestamp(box.get("lastUpdatedTimestamp")),
    }


def tag_row(tag: dict, image_uuid: str) -> dict:
    return {
        "tag_uuid": tag["uuid"],
        "image_uuid": image_uuid,
        "key": tag.get("key"),
        "value": tag.get("value"),
        "media_type": tag.get("mediaType"),
    }


def collection_row(upload: dict) -> dict:
    dwc = upload.get("darwinCore") or {}
    return {
        "collection_uuid": upload["uuid"],
        "dataset_id": dwc.get("datasetID"),
        "dataset_name": dwc.get("datasetName"),
        "owner_institution_code": dwc.get("ownerInstitutionCode"),
        "institution_code": dwc.get("institutionCode"),
        "collection_code": dwc.get("collectionCode"),
        "rights_holder": dwc.get("rightsHolder"),
        "bibliographic_citation": dwc.get("bibliographicCitation"),
        "access_rights": dwc.get("accessRights"),
        "record_type": dwc.get("recordType"),
        "basis_of_record": dwc.get("basisOfRecord"),
        "license_statement": dwc.get("license"),
        "created_timestamp": parse_timestamp(upload.get("createdTimestamp")),
    }


@dataclass
class BuildResult:
    tables: dict[str, pa.Table]
    excluded: dict[str, int] = field(default_factory=dict)


def _table(name: str, rows: list[dict], sort_by: list[str]) -> pa.Table:
    rows.sort(key=lambda r: tuple(r[c] or "" for c in sort_by))
    return pa.Table.from_pylist(rows, schema=schema.TABLES[name])


def build_tables(
    images: Iterable[dict],
    uploads: Iterable[dict],
    links: Iterable[dict],
    index: StoreIndex,
) -> BuildResult:
    """An image is published only if it is public and complete in the store."""
    excluded = {"not_valid": 0, "missing_objects": 0, "rejected_collection": 0}
    image_rows, box_rows, tag_rows = [], [], []

    for img in images:
        if not is_public(img):
            excluded["not_valid"] += 1
            continue
        if not index.complete(img["uuid"]):
            excluded["missing_objects"] += 1
            continue
        image_uuid = img["uuid"]
        image_rows.append(image_row(img, index.images[image_uuid], index.checksums[image_uuid]))
        box_rows.extend(box_row(b, image_uuid) for b in img.get("boundingBoxes") or [])
        tag_rows.extend(tag_row(t, image_uuid) for t in img.get("tags") or [])

    published = {r["image_uuid"] for r in image_rows}
    uploads_by_uuid = {}
    for upload in uploads:
        if upload.get("status") == "REJECTED":
            excluded["rejected_collection"] += 1
            continue
        uploads_by_uuid[upload["uuid"]] = upload

    link_rows = []
    seen_links = set()
    for link in links:
        pair = (link["image_uuid"], link["collection_uuid"])
        if pair[0] in published and pair[1] in uploads_by_uuid and pair not in seen_links:
            seen_links.add(pair)
            link_rows.append({"image_uuid": pair[0], "collection_uuid": pair[1]})

    used = {c for _, c in seen_links}
    collection_rows = [collection_row(u) for k, u in uploads_by_uuid.items() if k in used]

    tables = {
        "images": _table("images", image_rows, ["image_uuid"]),
        "boxes": _table("boxes", box_rows, ["image_uuid", "box_uuid"]),
        "tags": _table("tags", tag_rows, ["image_uuid", "key", "tag_uuid"]),
        "collections": _table("collections", collection_rows, ["collection_uuid"]),
        "image_collections": _table(
            "image_collections", link_rows, ["image_uuid", "collection_uuid"]
        ),
    }
    return BuildResult(tables=tables, excluded=excluded)
