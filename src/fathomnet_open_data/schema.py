"""Arrow schemas for the published metadata tables.

This module is the source of truth for column names and types. docs/data-dictionary.md must list
the same columns; tests/test_schema_docs.py enforces that.
"""

import pyarrow as pa

TIMESTAMP = pa.timestamp("us", tz="UTC")

IMAGES = pa.schema(
    [
        ("image_uuid", pa.string()),
        ("s3_key", pa.string()),
        ("thumbnail_s3_key", pa.string()),
        ("source_url", pa.string()),
        ("sha256", pa.string()),
        ("media_type", pa.string()),
        ("width", pa.int32()),
        ("height", pa.int32()),
        ("image_license", pa.string()),
        ("imaging_type", pa.string()),
        ("recorded_timestamp", TIMESTAMP),
        ("latitude", pa.float64()),
        ("longitude", pa.float64()),
        ("depth_meters", pa.float64()),
        ("altitude_meters", pa.float64()),
        ("temperature_celsius", pa.float64()),
        ("salinity", pa.float64()),
        ("oxygen_ml_l", pa.float64()),
        ("pressure_dbar", pa.float64()),
        ("modified_timestamp", TIMESTAMP),
    ]
)

BOXES = pa.schema(
    [
        ("box_uuid", pa.string()),
        ("image_uuid", pa.string()),
        ("concept", pa.string()),
        ("alt_concept", pa.string()),
        ("x", pa.int32()),
        ("y", pa.int32()),
        ("width", pa.int32()),
        ("height", pa.int32()),
        ("group_of", pa.bool_()),
        ("occluded", pa.bool_()),
        ("truncated", pa.bool_()),
        ("review_state", pa.string()),
        ("last_reviewed_timestamp", TIMESTAMP),
        ("user_defined_key", pa.string()),
        ("annotation_license", pa.string()),
        ("modified_timestamp", TIMESTAMP),
    ]
)

TAGS = pa.schema(
    [
        ("tag_uuid", pa.string()),
        ("image_uuid", pa.string()),
        ("key", pa.string()),
        ("value", pa.string()),
        ("media_type", pa.string()),
    ]
)

COLLECTIONS = pa.schema(
    [
        ("collection_uuid", pa.string()),
        ("dataset_id", pa.string()),
        ("dataset_name", pa.string()),
        ("owner_institution_code", pa.string()),
        ("institution_code", pa.string()),
        ("collection_code", pa.string()),
        ("rights_holder", pa.string()),
        ("bibliographic_citation", pa.string()),
        ("access_rights", pa.string()),
        ("record_type", pa.string()),
        ("basis_of_record", pa.string()),
        ("license_statement", pa.string()),
        ("created_timestamp", TIMESTAMP),
    ]
)

IMAGE_COLLECTIONS = pa.schema(
    [
        ("image_uuid", pa.string()),
        ("collection_uuid", pa.string()),
    ]
)

TABLES: dict[str, pa.Schema] = {
    "images": IMAGES,
    "boxes": BOXES,
    "tags": TAGS,
    "collections": COLLECTIONS,
    "image_collections": IMAGE_COLLECTIONS,
}

# Primary key columns, used for uniqueness checks.
PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "images": ("image_uuid",),
    "boxes": ("box_uuid",),
    "tags": ("tag_uuid",),
    "collections": ("collection_uuid",),
    "image_collections": ("image_uuid", "collection_uuid"),
}
