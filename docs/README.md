# Documentation

Start with the [project README](../README.md) for an overview and quick start, and the
[tutorial notebook](../get-to-know-a-dataset.ipynb) for a guided walkthrough.

## Using the data

| Page | Read it to learn |
|---|---|
| [bucket-layout.md](bucket-layout.md) | Where everything lives in `s3://fathomnet-pds`: images, thumbnails, metadata tables, exports, and manifests, and how releases are versioned. |
| [data-dictionary.md](data-dictionary.md) | Every table and column, how tables join, how to resolve taxonomic labels with WoRMS, what is deliberately left out, and the COCO export format. |
| [licensing.md](licensing.md) | Per-image and per-annotation licenses, how to filter by license, FathomNet's data use policy, and how to cite FathomNet and its collections. |
| [athena.md](athena.md) | Creating Amazon Athena tables over the Parquet metadata and running SQL at scale. |

Citation metadata is also in [CITATION.cff](../CITATION.cff).

## Maintaining the dataset

| Page | Read it to learn |
|---|---|
| [releasing.md](releasing.md) | How the `fathomnet-release` CLI builds and publishes a release, its prerequisites, and how to handle removed images. |
