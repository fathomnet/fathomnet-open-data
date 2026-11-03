# Publishing a release (maintainers)

Releases are built by the `fathomnet-release` CLI in this repo and run by hand on MBARI hardware. The
AWS account that hosts the bucket is sponsored for **Amazon S3 only**: do all compute (downloads,
thumbnails, Parquet, COCO) on our machines and use the account only for uploads.

## How it works

| Step | Command | What it does |
|---|---|---|
| 1 | `snapshot` | Pages the public FathomNet REST API (`/images`, `/imagesetuploads`, image-to-collection links) into `work/<release>/raw/`. |
| 2 | `sync` | For every valid image not yet in the bucket: downloads it from its source URL, verifies it against FathomNet (see below), detects the format from the bytes, uploads `images/<uuid>.<ext>` and a 512 px `thumbnails/<uuid>.jpg`, and records the SHA-256 and size in `manifests/objects/`. |
| 3 | `build` | Writes the five Parquet tables and the COCO export to `work/<release>/`. An image is included only if it is valid and complete in the bucket (original, thumbnail, and manifest entry). |
| 4 | `validate` | Checks schemas, keys, references, that every key exists, and that no value looks like an email address. Exits non-zero on errors. |
| 5 | `publish` | Re-runs validation, uploads `metadata/<table>/release=<date>/`, the COCO export, and the bucket `README.md`/`LICENSE.md`, then updates `metadata/releases.csv` last. |

`run` does all five in order. Each step writes `work/<release>/<step>-report.json`.

**The bucket is the state.** Image objects are immutable and never rewritten, so `sync` only copies
images that are new since the last release. An image is complete when its original, thumbnail, and
manifest entry all exist; a failed or interrupted sync fills in whatever is missing when rerun, without
downloading images already in the bucket.

**Checksums.** FathomNet's stored SHA-256 is wrong for some images (about 5% in a 2026-10 sample, all
FathomVerse images on CloudFront, and 5,526 images store the hash of an empty file). `sync` therefore
accepts an image whose checksum disagrees with FathomNet if it decodes at the width and height FathomNet
recorded, and lists it under `checksum_mismatches` in the sync report. If both checksum and size
disagree, the image is skipped and listed under `failures`. The published `sha256` is always computed
from the stored bytes.

**The raw snapshot is private.** `work/<release>/raw/` contains contributor emails: keep it local and
do not share it. Only the tables built from it are published.

**Releases are immutable.** `publish` refuses to overwrite an existing `release=<date>` partition
unless you pass `--force`. Use a new date for a corrected release.

## Infrastructure

- **Account:** `fathomnet-open-data` (639589055367), linked to the AWS Open Data billing organization.
  The sponsorship covers S3 only; do not create other resources in it.
- **Bucket:** `s3://fathomnet-pds` in `us-west-2`, created with the Open Data program's CloudFormation
  template ([pds-bucket-cf.yml](https://s3-us-west-2.amazonaws.com/opendata.aws/pds-bucket-cf.yml)).
  The template sets a public read and list bucket policy (HTTPS only), CORS for `GET`/`HEAD`, a
  lifecycle rule that moves objects to Intelligent-Tiering and aborts incomplete multipart uploads
  after 7 days, CloudWatch request metrics, and the SNS topic
  `arn:aws:sns:us-west-2:639589055367:fathomnet-pds-object_created`. Versioning is off, so deletes are
  permanent. Anything written to the bucket is public immediately.
- **Uploader:** IAM user `fathomnet-release`, with only the customer-managed policy in
  [infra/release-writer-policy.json](../infra/release-writer-policy.json) (list the bucket; get, put,
  and delete objects). It cannot change bucket settings.

## Prerequisites

- An access key for `fathomnet-release` in a local AWS CLI profile, then
  `export AWS_PROFILE=fathomnet-open-data`. Check it with `aws sts get-caller-identity`.
- Disk for the snapshot (about 1 GB) and the built tables. Images stream straight to S3 and are not
  kept locally.

## Dry run

Point `--store` at a local directory to exercise everything without AWS:

```bash
uv run fathomnet-release --release 2026-11-01 snapshot
uv run fathomnet-release --release 2026-11-01 sync --store /tmp/fathomnet-bucket --limit 100
uv run fathomnet-release --release 2026-11-01 build --store /tmp/fathomnet-bucket
uv run fathomnet-release --release 2026-11-01 validate --store /tmp/fathomnet-bucket
```

## Release

```bash
export AWS_PROFILE=fathomnet-open-data
R=$(date -u +%F)
uv run fathomnet-release --release $R snapshot
uv run fathomnet-release --release $R sync --store s3://fathomnet-pds --workers 32
# Review work/$R/sync-report.json; rerun sync to retry transient failures.
uv run fathomnet-release --release $R build --store s3://fathomnet-pds
uv run fathomnet-release --release $R validate --store s3://fathomnet-pds
# Review work/$R/build-report.json and validate-report.json.
uv run fathomnet-release --release $R publish --store s3://fathomnet-pds --notes "What changed"
```

## Removed images

An image that is no longer valid in FathomNet is left out of the next release's tables. Its objects
stay in `images/` and `thumbnails/` until removed by hand, so earlier releases keep working. To honor
a takedown request, delete both objects with the AWS CLI and publish a new release.

## Development

```bash
uv run pytest
uv run ruff check src tests && uv run ruff format --check src tests
```

`src/fathomnet_open_data/schema.py` defines every published column. If you change it, update
[data-dictionary.md](data-dictionary.md); a test fails if they disagree.
