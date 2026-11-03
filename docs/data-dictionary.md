# Data dictionary

> **Pre-launch.** Schemas may still change before the first release is published.

All metadata tables are Parquet, one directory per table per release (see
[bucket-layout.md](bucket-layout.md)). Column names are `snake_case`. Timestamps are UTC
(`TIMESTAMP` with microsecond precision). Nullable columns are common: position, depth, time, and
environmental fields are only present when the contributor supplied them, and the `group_of`, `occluded`,
and `truncated` box flags are null when the contributor did not set them (use
`coalesce(occluded, false)` in SQL).

> **Contributors choose the licenses.** Each FathomNet contributor selects the licenses for their own
> images and annotations, and that license is attached to every record: `image_license` on each image
> and `annotation_license` on each bounding box. There is no single license for the dataset, and an
> image and its annotations can be licensed differently. Check both before you reuse anything; see
> [licensing.md](licensing.md).

Join keys:

```
images.image_uuid  1 --- *  boxes.image_uuid
images.image_uuid  1 --- *  tags.image_uuid
images.image_uuid  * --- *  collections.collection_uuid   (via image_collections)
```

## `images`

One row per image.

| Column | Type | Description |
|---|---|---|
| `image_uuid` | string | FathomNet image UUID. Same id as the FathomNet Database and REST API. |
| `s3_key` | string | Key of the original image in this bucket, e.g. `images/<uuid>.png`. |
| `thumbnail_s3_key` | string | Key of the 512 px JPEG thumbnail. |
| `source_url` | string | URL the image was contributed from. May point outside AWS. |
| `sha256` | string | Lowercase hex SHA-256 of the object in this bucket. Use it to verify downloads. |
| `media_type` | string | MIME type detected from the image bytes: `image/jpeg`, `image/png`, or `image/tiff`. |
| `width`, `height` | int32 | Image size in pixels. |
| `image_license` | string | **License chosen by the contributor** for this image, as an [SPDX id](https://spdx.org/licenses/), e.g. `CC-BY-4.0`. Applies to the image object and its thumbnail. |
| `imaging_type` | string | Free text platform/method, e.g. `ROV`, `Drop Camera`. Often null. |
| `recorded_timestamp` | timestamp | When the image was captured. |
| `latitude`, `longitude` | double | WGS84 decimal degrees. |
| `depth_meters` | double | Depth, positive down. |
| `altitude_meters` | double | Height above the seafloor. |
| `temperature_celsius` | double | Water temperature. |
| `salinity` | double | Salinity (practical salinity units). |
| `oxygen_ml_l` | double | Dissolved oxygen, ml/L. |
| `pressure_dbar` | double | Pressure, decibars. |
| `modified_timestamp` | timestamp | Last time the image record changed in FathomNet. |

## `boxes`

One row per bounding box annotation.

| Column | Type | Description |
|---|---|---|
| `box_uuid` | string | FathomNet bounding box UUID. |
| `image_uuid` | string | Image the box belongs to. |
| `concept` | string | Primary label. Usually a [WoRMS](https://www.marinespecies.org/) scientific name at any rank (e.g. `Bathochordaeus stygius`, `Sebastes`); sometimes a non-taxon such as `Rock` or `trash`. Labels are free text; see [Taxonomy](#taxonomy). |
| `alt_concept` | string | Optional secondary label, e.g. a part (`head`) or alternate identification. |
| `x`, `y` | int32 | **Top-left** corner in pixels, origin at the image's top-left. |
| `width`, `height` | int32 | Box size in pixels. |
| `group_of` | boolean | Box covers a group of organisms rather than one individual. |
| `occluded` | boolean | Object is partly hidden by something in front of it. |
| `truncated` | boolean | Object is cut off by the image edge. |
| `review_state` | string | `UNVERIFIED` (default), `VERIFIED` (confirmed by a reviewer), `REJECTED`, or `UNKNOWN`. |
| `last_reviewed_timestamp` | timestamp | When `review_state` last changed. |
| `user_defined_key` | string | Contributor's own id for the annotation. Not unique. |
| `annotation_license` | string | **License chosen by the contributor** for this annotation (label, box, and flags), as an SPDX id. May differ from the image license. |
| `modified_timestamp` | timestamp | Last time the box changed in FathomNet. |

Not every organism in an image is necessarily boxed. Many collections were annotated for a subset of
taxa, so treat missing boxes as "not labeled", not "absent".

## `tags`

Free-form key/value tags attached to images by contributors.

| Column | Type | Description |
|---|---|---|
| `tag_uuid` | string | FathomNet tag UUID. |
| `image_uuid` | string | Tagged image. |
| `key` | string | Tag name. |
| `value` | string | Tag value. |
| `media_type` | string | MIME type of `value`, usually `text/plain`. |

## `collections`

One row per contributed collection (an image set upload), with
[Darwin Core](https://dwc.tdwg.org/terms/) dataset-level metadata.

| Column | Type | Description |
|---|---|---|
| `collection_uuid` | string | FathomNet collection (image set upload) UUID. |
| `dataset_id` | string | Darwin Core `datasetID`. |
| `dataset_name` | string | Darwin Core `datasetName`. |
| `owner_institution_code` | string | Darwin Core `ownerInstitutionCode`, e.g. `MBARI`. |
| `institution_code` | string | Darwin Core `institutionCode`. |
| `collection_code` | string | Darwin Core `collectionCode`. |
| `rights_holder` | string | Darwin Core `rightsHolder`. |
| `bibliographic_citation` | string | How to cite this collection, in addition to FathomNet. |
| `access_rights` | string | Darwin Core `accessRights`. |
| `record_type` | string | Darwin Core `type`, usually `StillImage`. |
| `basis_of_record` | string | Darwin Core `basisOfRecord`. |
| `license_statement` | string | Contributor's free-text license statement for the collection. The per-asset `image_license` and `annotation_license` columns are authoritative. |
| `created_timestamp` | timestamp | When the collection was uploaded. |

## `image_collections`

Many-to-many link between images and collections. An image can appear in more than one collection.

| Column | Type | Description |
|---|---|---|
| `image_uuid` | string | Image. |
| `collection_uuid` | string | Collection. |

## Taxonomy

`boxes.concept` is a free-text label. Most labels are [WoRMS](https://www.marinespecies.org/) scientific
names, at whatever rank the annotator could identify, but nothing in the bucket enforces that. To resolve
labels to accepted names, synonyms, or lineage (for example, to roll species up to family), use
FathomNet's WoRMS name server at https://database.fathomnet.org/worms
([API docs](https://database.fathomnet.org/worms/docs)), for example:

```bash
curl -s https://database.fathomnet.org/worms/ancestors/Atolla
```

## `manifests/objects`

A checksum manifest for every image object, written as images are copied into the bucket
(`manifests/objects/part-<run>-<n>.parquet`). It is not versioned by release; the `images` table
already carries the same `sha256` for each release.

| Column | Type | Description |
|---|---|---|
| `image_uuid` | string | Image. |
| `s3_key` | string | Key of the original image. |
| `sha256` | string | Lowercase hex SHA-256 of the object. |
| `size_bytes` | int64 | Object size in bytes. |
| `synced_timestamp` | timestamp | When the entry was recorded. |

## `releases.csv`

| Column | Description |
|---|---|
| `release` | Release date, `YYYY-MM-DD`; matches the `release=` partition. |
| `n_images`, `n_boxes`, `n_concepts` | Row counts for the release. |
| `notes` | Summary of what changed. |

## Not included

Contributor, observer, and reviewer email addresses recorded in the FathomNet Database are personal
information and are not published in this bucket. The release pipeline refuses to publish any table
value that looks like an email address. Images the FathomNet validation job has not confirmed as
valid (for example, broken source links) are also left out.

## COCO export

`exports/coco/release=<YYYY-MM-DD>/fathomnet-boxes.json` follows the
[COCO object detection format](https://cocodataset.org/#format-data). Each image's `file_name` is its
`s3_key`, `coco_url` is the public HTTPS URL of the object, and `bbox` is `[x, y, width, height]` with a
top-left origin (the same as the `boxes` table). Category names are `boxes.concept`. FathomNet-specific
fields (`image_license`, `annotation_license`, `review_state`, `image_uuid`, `box_uuid`) are added to the
`images` and `annotations` entries, so the contributor-chosen license stays attached to every image and
box in COCO form too.
