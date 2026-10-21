# Licensing, data use, and citation

This page summarizes FathomNet's policies for convenience. It is not legal advice. The governing texts are
the [FathomNet Data Use Policy](https://www.fathomnet.org/datause),
[Terms of Use](https://www.fathomnet.org/terms), and the
[accepted licenses](https://database.fathomnet.org/fathomnet/#/license) page.

## Per-asset licenses

Images and annotations are licensed **independently**, and each one carries its own license:

- `images.image_license`: the license of the image file.
- `boxes.annotation_license`: the license of the annotation (label, box, and related metadata).

Licenses are identified by [SPDX ids](https://spdx.org/licenses/), such as `CC0-1.0`, `CC-BY-4.0`,
`CC-BY-NC-4.0`, and `CC-BY-NC-ND-4.0`. Contributors choose one image license and one annotation license
per collection. It is your responsibility to comply with the license of each asset you use, including
attributing the rights holder (`collections.rights_holder`). NonCommercial (NC) and NoDerivatives (ND)
licenses add restrictions.

To select only assets under licenses you can use:

```sql
SELECT i.image_uuid, i.s3_key, b.concept, b.x, b.y, b.width, b.height
FROM images i JOIN boxes b USING (image_uuid)
WHERE i.image_license IN ('CC0-1.0', 'CC-BY-4.0')
  AND b.annotation_license IN ('CC0-1.0', 'CC-BY-4.0');
```

## Images and thumbnails in this bucket

Images in `images/` are byte-for-byte copies of the contributed files. Thumbnails in `thumbnails/` are
format and size conversions, which Creative Commons 4.0 licenses permit as technical modifications
(Section 2(a)(4)). They are distributed under the same license as their source image.

## Data use

- FathomNet is intended for training and developing machine learning for the ocean. All submitted content
  may be used to train and develop ML models, regardless of license.
- FathomNet is **not intended to be used as an occurrence dataset**. Positions, depths, and labels
  reflect what contributors annotated, not systematic surveys.
- Acknowledge FathomNet in publications and projects, give back where you can (models, annotations,
  expert validation), and use the data consistently with the UN Sustainable Development Goals.

## Citation

Please cite:

> Katija, K., Orenstein, E., Schlining, B., Lundsten, L., Barnard, K., Sainz, G., Boulais, O., Cromwell,
> M., Butler, E., Woodward, B., and Bell, K. L. C. (2022). FathomNet: A global image database for enabling
> artificial intelligence in the ocean. *Scientific Reports*, 12, 15914.
> https://doi.org/10.1038/s41598-022-19939-2

Also cite any collection you use that provides a `collections.bibliographic_citation`. In a data
availability statement, you can reference the dataset as "available at
registry.opendata.aws/fathomnet".
