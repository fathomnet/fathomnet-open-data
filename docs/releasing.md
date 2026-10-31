# Publishing a release (maintainers)

Releases are built by the `fathomnet-release` CLI in this repo and run by hand on MBARI hardware. The
AWS account that hosts the bucket is sponsored for **Amazon S3 only**: do all compute (downloads,
thumbnails, Parquet, COCO) on our machines and use the account only for uploads.

## How it works

| Step | Command | What it does |
|---|---|---|
| 1 | `snapshot` | Pages the public FathomNet REST API (`/images`, `/imagesetuploads`, image-to-collection links) into `work/<release>/raw/`. |
| 2 | `sync` | For every valid image not yet in the bucket: downloads it from its source URL, checks the SHA-256 against FathomNet, detects the format from the bytes, uploads `images/<uuid>.<ext>` and a 512 px `thumbnails/<uuid>.jpg`. |
| 3 | `build` | Writes the five Parquet tables and the COCO export to `work/<release>/`. An image is included only if it is valid and both its objects are in the bucket. |
| 4 | `validate` | Checks schemas, keys, references, that every key exists, and that no value looks like an email address. Exits non-zero on errors. |
| 5 | `publish` | Re-runs validation, uploads `metadata/<table>/release=<date>/`, the COCO export, and the bucket `README.md`/`LICENSE.md`, then updates `metadata/releases.csv` last. |

`run` does all five in order. Each step writes `work/<release>/<step>-report.json`.

**The bucket is the state.** Image objects are immutable and never rewritten, so `sync` only copies
images that are new since the last release; a failed or interrupted sync can be rerun safely. The
raw snapshot in `work/` contains contributor emails: keep it local and do not share it.

**Releases are immutable.** `publish` refuses to overwrite an existing `release=<date>` partition
unless you pass `--force`. Use a new date for a corrected release.

## Prerequisites

- AWS credentials for the sponsored account with write access to the bucket, for example
  `export AWS_PROFILE=fathomnet-open-data`.
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
