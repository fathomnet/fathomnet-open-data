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

> **Contributors choose the licenses.** Each FathomNet contributor selects the licenses for their own
> images and annotations, and that license is attached to every record: `image_license` on each image
> and `annotation_license` on each bounding box. There is no single license for the dataset, and an
> image and its annotations can be licensed differently. Check both before you reuse anything; see
> [docs/licensing.md](docs/licensing.md).

## What is in the bucket

- **Images**: every public FathomNet image, byte-for-byte as contributed (JPEG, PNG, TIFF), keyed by
  image UUID.
- **Thumbnails**: a small JPEG for every image, for browsing and quick-look visualization.
- **Metadata**: Parquet tables for images, bounding boxes, tags, and collections (Darwin Core),
  versioned by release. Every image and annotation record includes the license its contributor chose.
- **Exports**: COCO object detection JSON for the full corpus.
- **Video** (planned): source video that FathomNet frames were extracted from.

See [docs/bucket-layout.md](docs/bucket-layout.md) for the prefix structure and
[docs/data-dictionary.md](docs/data-dictionary.md) for every table and column. [docs/](docs/README.md) lists
all documentation pages.

## Quick start

List the bucket with the AWS CLI. No credentials are needed:

```bash
aws s3 ls --no-sign-request s3://fathomnet-pds/
```

Metadata is published in dated releases. `metadata/releases.csv` lists them; pin one for reproducible
work. Query a release with [DuckDB](https://duckdb.org/) directly from S3. Here, counting boxes per
label and per contributor-chosen annotation license:

```sql
INSTALL httpfs; LOAD httpfs;
SET s3_region = 'us-west-2';

SELECT concept, annotation_license, count(*) AS n_boxes
FROM 's3://fathomnet-pds/metadata/boxes/release=2026-11-01/*.parquet'
GROUP BY ALL
ORDER BY n_boxes DESC
LIMIT 10;
```

Download a single image:

```bash
aws s3 cp --no-sign-request s3://fathomnet-pds/images/<image_uuid>.png .
```

For SQL at scale with Amazon Athena, see [docs/athena.md](docs/athena.md).

## Licensing and citation

FathomNet content is licensed **per record, by its contributor**. When contributors upload to FathomNet,
they choose an SPDX license for their images and one for their annotations. That choice is attached to
every image record (`images.image_license`) and every annotation record (`boxes.annotation_license`),
and the two can differ. Check both columns before you use, train on, or redistribute anything. See
[docs/licensing.md](docs/licensing.md).

If you use FathomNet, please cite:

> Katija, K., Orenstein, E., Schlining, B., Lundsten, L., Barnard, K., Sainz, G., Boulais, O., Cromwell,
> M., Butler, E., Woodward, B., and Bell, K. L. C. (2022). FathomNet: A global image database for enabling
> artificial intelligence in the ocean. *Scientific Reports*, 12, 15914.
> https://doi.org/10.1038/s41598-022-19939-2

Machine-readable metadata is in [CITATION.cff](CITATION.cff); GitHub's "Cite this repository"
button exports it as APA or BibTeX.

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

## Maintainers

The bucket is built and published by the `fathomnet-release` CLI in [`src/`](src/fathomnet_open_data).
See [docs/releasing.md](docs/releasing.md).
