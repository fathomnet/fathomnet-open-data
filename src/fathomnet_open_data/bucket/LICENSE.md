# Licensing

FathomNet content is licensed per asset by its contributor. There is no single license for this bucket.

- Each image's license is the SPDX id in `metadata/images/.../*.parquet`, column `image_license`.
- Each bounding box's license is the SPDX id in `metadata/boxes/.../*.parquet`, column
  `annotation_license`. It may differ from the image's license.
- Thumbnails under `thumbnails/` carry the license of their source image.

Accepted licenses are listed at https://database.fathomnet.org/fathomnet/#/license. For details and
the FathomNet data use policy, see
https://github.com/fathomnet/fathomnet-open-data/blob/main/docs/licensing.md.

If you use FathomNet, please cite:

Katija, K., et al. (2022). FathomNet: A global image database for enabling artificial intelligence in
the ocean. Scientific Reports, 12, 15914. https://doi.org/10.1038/s41598-022-19939-2
