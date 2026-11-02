# FathomNet

Public copy of the [FathomNet](https://www.fathomnet.org) Database, a global database of ocean imagery
and AI-ready annotations from the Monterey Bay Aquarium Research Institute (MBARI).

- Documentation, data dictionary, and tutorial: https://github.com/fathomnet/fathomnet-open-data
- Registry of Open Data entry: https://registry.opendata.aws/fathomnet/
- Release history: `metadata/releases.csv`
- Contact: fathomnet@mbari.org

**Licenses are chosen by each contributor and attached to every record.** There is no single license
for this bucket. Each image's license is in the `image_license` column of the `images` table and each
annotation's license is in the `annotation_license` column of the `boxes` table; they can differ.
Check both before reuse; see `LICENSE.md`.
