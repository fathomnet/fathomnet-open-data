# FathomNet Open Data on AWS

> **Draft.** The S3 bucket does not exist yet. Bucket names, prefixes, and table schemas below are
> proposals and may change before launch.

[FathomNet](https://www.fathomnet.org) is a global, open-source database of ocean imagery and AI-ready
annotations, operated by the [Monterey Bay Aquarium Research Institute (MBARI)](https://www.mbari.org/).
Through the [AWS Open Data Sponsorship Program](https://aws.amazon.com/opendata/), a public copy of the
FathomNet Database is available on Amazon S3, so you can query metadata and pull only the images you need
without downloading the whole corpus.

| | |
|---|---|
| Registry entry | https://registry.opendata.aws/fathomnet/ |
| Bucket | `s3://fathomnet-pds` (`us-west-2`, public, no AWS account required) |
| Tutorial | [`get-to-know-a-dataset.ipynb`](get-to-know-a-dataset.ipynb) |
| FathomNet Database | https://database.fathomnet.org |
| Contact | fathomnet@mbari.org, or [open an issue](https://github.com/fathomnet/fathomnet-open-data/issues) |

## What is in the bucket

- **Images**: every public FathomNet image, byte-for-byte as contributed (JPEG, PNG, TIFF), keyed by
  image UUID.
- **Thumbnails**: a small JPEG for every image, for browsing and quick-look visualization.
- **Metadata**: Parquet tables for images, bounding boxes, tags, and collections (Darwin Core),
  versioned by release.
- **Exports**: COCO object detection JSON for the full corpus.
- **Video** (planned): source video that FathomNet frames were extracted from.

See [docs/bucket-layout.md](docs/bucket-layout.md) for the prefix structure and
[docs/data-dictionary.md](docs/data-dictionary.md) for every table and column.

## Quick start

List the bucket with the AWS CLI. No credentials are needed:

```bash
aws s3 ls --no-sign-request s3://fathomnet-pds/
```

Metadata is published in dated releases. `metadata/releases.csv` lists them; pin one for reproducible
work. Query a release with [DuckDB](https://duckdb.org/) directly from S3:

```sql
INSTALL httpfs; LOAD httpfs;
SET s3_region = 'us-west-2';

SELECT concept, count(*) AS n_boxes
FROM 's3://fathomnet-pds/metadata/boxes/release=2026-11-01/*.parquet'
GROUP BY concept
ORDER BY n_boxes DESC
LIMIT 10;
```

Download a single image:

```bash
aws s3 cp --no-sign-request s3://fathomnet-pds/images/<image_uuid>.png .
```

For SQL at scale with Amazon Athena, see [docs/athena.md](docs/athena.md).

## Licensing and citation

FathomNet content is licensed **per asset**: each image and each annotation carries its own SPDX license,
chosen by the contributor. Check the `image_license` and `annotation_license` columns before
redistributing. See [docs/licensing.md](docs/licensing.md).

If you use FathomNet, please cite:

> Katija, K., Orenstein, E., Schlining, B., Lundsten, L., Barnard, K., Sainz, G., Boulais, O., Cromwell,
> M., Butler, E., Woodward, B., and Bell, K. L. C. (2022). FathomNet: A global image database for enabling
> artificial intelligence in the ocean. *Scientific Reports*, 12, 15914.
> https://doi.org/10.1038/s41598-022-19939-2

## Related tools

- [fathomnet-py](https://github.com/fathomnet/fathomnet-py): Python client for the live FathomNet REST
  API, including the `fathomnet-generate` dataset builder.
- [FathomNet on Hugging Face](https://huggingface.co/FathomNet): pretrained models.

## Running the notebook

The notebook's dependencies are listed in [pyproject.toml](pyproject.toml). With
[uv](https://docs.astral.sh/uv/):

```bash
uv run jupyter lab get-to-know-a-dataset.ipynb
```

Outputs are stripped before commit; please run `uv run nbstripout get-to-know-a-dataset.ipynb` before
opening a pull request.
