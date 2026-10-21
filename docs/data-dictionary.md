# Data dictionary

> **Draft.** Proposed schemas; subject to change before launch.

All metadata tables are Parquet, one directory per table per release (see
[bucket-layout.md](bucket-layout.md)). Column names are `snake_case`. Timestamps are UTC
(`TIMESTAMP` with microsecond precision). Nullable columns are common: position, depth, time, and
environmental fields are only present when the contributor supplied them.

Join keys:

```
images.image_uuid  1 --- *  boxes.image_uuid
images.image_uuid  1 --- *  tags.image_uuid
images.image_uuid  * --- *  collections.collection_uuid   (via image_collections)
boxes.concept      * --- 1  concepts.concept
boxes.box_uuid     1 --- *  masks.box_uuid                 (planned)
```

## `images`

One row per image.

| Column | Type | Description |
|---|---|---|
| `image_uuid` | string | FathomNet image UUID. Same id as the FathomNet Database and REST API. |
| `s3_key` | string | Key of the original image in this bucket, e.g. `images/<uuid>.png`. |
| `thumbnail_s3_key` | string | Key of the 512 px JPEG thumbnail. |
| `source_url` | string | URL the image was contributed from. May point outside AWS. |
| `sha256` | string | Hex SHA-256 of the image bytes. |
| `media_type` | string | MIME type, e.g. `image/png`. |
| `width`, `height` | int32 | Image size in pixels. |
| `image_license` | string | [SPDX id](https://spdx.org/licenses/) of the image license, e.g. `CC-BY-4.0`. |
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
| `concept` | string | Primary label. Usually a [WoRMS](https://www.marinespecies.org/) scientific name at any rank (e.g. `Bathochordaeus stygius`, `Sebastes`); sometimes a non-taxon such as `Rock` or `trash`. See `concepts`. |
| `alt_concept` | string | Optional secondary label, e.g. a part (`head`) or alternate identification. |
| `x`, `y` | int32 | **Top-left** corner in pixels, origin at the image's top-left. |
| `width`, `height` | int32 | Box size in pixels. |
| `group_of` | boolean | Box covers a group of organisms rather than one individual. |
| `occluded` | boolean | Object is partly hidden by something in front of it. |
| `truncated` | boolean | Object is cut off by the image edge. |
| `review_state` | string | `UNVERIFIED` (default), `VERIFIED` (confirmed by a reviewer), `REJECTED`, or `UNKNOWN`. |
| `last_reviewed_timestamp` | timestamp | When `review_state` last changed. |
| `user_defined_key` | string | Contributor's own id for the annotation. Not unique. |
| `annotation_license` | string | SPDX id of the annotation license. May differ from the image license. |
| `modified_timestamp` | timestamp | Last time the box changed in FathomNet. |

Not every organism in an image is necessarily boxed. Many collections were annotated for a subset of
taxa, so treat missing boxes as "not labeled", not "absent".

## `tags`

Free-form key/value tags attached to images by contributors.

| Column | Type | Description |
|---|---|---|
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
| `image_license` | string | SPDX id applied to this collection's images. |
| `annotation_license` | string | SPDX id applied to this collection's annotations. |
| `created_timestamp` | timestamp | When the collection was uploaded. |

## `image_collections`

Many-to-many link between images and collections. An image can appear in more than one collection.

| Column | Type | Description |
|---|---|---|
| `image_uuid` | string | Image. |
| `collection_uuid` | string | Collection. |

## `concepts`

One row per distinct `boxes.concept`, resolved against FathomNet's
[WoRMS](https://www.marinespecies.org/) mirror at release time. Rank columns use Darwin Core term names,
so `class` and `order` need quoting in SQL (`"class"` in DuckDB, `` `order` `` in Athena).

| Column | Type | Description |
|---|---|---|
| `concept` | string | Label as used in `boxes.concept`. |
| `is_taxon` | boolean | `false` for non-taxa such as `Rock` or equipment. |
| `aphia_id` | int64 | WoRMS AphiaID of the matched name. |
| `accepted_aphia_id` | int64 | AphiaID of the currently accepted name (differs for synonyms). |
| `accepted_name` | string | Currently accepted scientific name. |
| `rank` | string | Taxonomic rank of the concept, e.g. `Species`, `Genus`, `Family`. |
| `kingdom`, `phylum`, `class`, `order`, `family`, `genus`, `species` | string | Lineage of the accepted name. Ranks below the concept's own rank are null. |

## `masks` (planned)

Instance segmentation masks, including those contributed by Meta from the Segment Anything Model 3
(SAM 3) collaboration. Schema to be finalized.

| Column | Type | Description |
|---|---|---|
| `mask_uuid` | string | Mask id. |
| `box_uuid` | string | Bounding box the mask refines. |
| `image_uuid` | string | Image. |
| `encoding` | string | Mask encoding, e.g. `coco_rle`. |
| `counts` | string | Encoded mask. |
| `annotation_license` | string | SPDX id of the mask's license. |

## `releases.csv`

| Column | Description |
|---|---|
| `release` | Release date, `YYYY-MM-DD`; matches the `release=` partition. |
| `n_images`, `n_boxes`, `n_concepts` | Row counts for the release. |
| `notes` | Summary of what changed. |

## Not included

Contributor, observer, and reviewer email addresses recorded in the FathomNet Database are personal
information and are not published in this bucket.

## COCO export

`exports/coco/release=<YYYY-MM-DD>/fathomnet-boxes.json` follows the
[COCO object detection format](https://cocodataset.org/#format-data). Each image's `file_name` is its
`s3_key`, `coco_url` is the public HTTPS URL of the object, and `bbox` is `[x, y, width, height]` with a
top-left origin (the same as the `boxes` table). Category names are `boxes.concept`. FathomNet-specific
fields (`image_license`, `annotation_license`, `review_state`, `image_uuid`, `box_uuid`) are added to the
`images` and `annotations` entries.
