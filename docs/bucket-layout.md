# Bucket layout

> **Draft.** Proposed layout; subject to change before launch.

The dataset lives in a single public bucket, `s3://fathomnet-pds`, in `us-west-2`. Requests do not need
to be signed (`--no-sign-request` with the AWS CLI, `signature_version=UNSIGNED` with boto3).

```
s3://fathomnet-pds/
  README.md                      Pointer to this documentation
  LICENSE.md                     Per-asset licensing summary (see licensing.md)
  images/
    <image_uuid>.<ext>           Original image bytes (jpg, png, tif)
  thumbnails/
    <image_uuid>.jpg             JPEG, longest side 512 px
  metadata/
    releases.csv                 One row per release: date, counts, notes
    images/release=<YYYY-MM-DD>/part-<n>.parquet
    boxes/release=<YYYY-MM-DD>/part-<n>.parquet
    tags/release=<YYYY-MM-DD>/part-<n>.parquet
    collections/release=<YYYY-MM-DD>/part-<n>.parquet
    image_collections/release=<YYYY-MM-DD>/part-<n>.parquet
    concepts/release=<YYYY-MM-DD>/part-<n>.parquet
    masks/release=<YYYY-MM-DD>/part-<n>.parquet        (planned)
  exports/
    coco/release=<YYYY-MM-DD>/fathomnet-boxes.json
  video/                         (planned) Source video
```

## Design notes

**Images are immutable and keyed by UUID.** An image object is written once and never changed, so image
keys are stable across releases. The image UUID is the same one used by the
[FathomNet Database](https://database.fathomnet.org) and its REST API, so you can move between the two.
The file extension matches the original format; use the `s3_key` column in the `images` table rather
than constructing keys yourself.

**Images are stored as contributed.** No re-encoding, resizing, or color correction. The SHA-256 of each
object is recorded in the `images` table (`sha256`) so you can verify downloads.

**Thumbnails are for browsing.** Every image has a JPEG thumbnail with its longest side scaled to 512 px.
They are convenient for quick looks, dashboards, and embedding sanity checks. Train on the originals.

**Metadata is versioned by release.** FathomNet is updated ad hoc as new contributions are reviewed. Each
release writes a complete snapshot of every metadata table under a new `release=<YYYY-MM-DD>` prefix.
Earlier releases are kept, so a query pinned to a release returns the same answer later. The prefixes use
[Hive partition naming](https://docs.aws.amazon.com/athena/latest/ug/partitions.html), which DuckDB,
Polars, PyArrow, Spark, and Amazon Athena understand natively.

**Removed images.** An image removed from FathomNet (for example, at a contributor's request) is left
out of later metadata releases. Its object may also be deleted from `images/`, in which case older
releases will reference a missing key.

**Exports are derived from metadata.** COCO JSON under `exports/` is generated from the same release's
Parquet tables, for use with tools that expect COCO. The Parquet tables are the source of truth.

**No archives.** Objects are not zipped or tarred, so you can fetch exactly the subset you need.

## Notifications

New objects are announced on a public SNS topic,
`arn:aws:sns:us-west-2:<account_id>:fathomnet-pds-object_created`. Subscribe an SQS queue or Lambda
function to react to new releases.
