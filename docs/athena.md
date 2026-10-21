# Querying with Amazon Athena

> **Draft.** Untested until the bucket exists.

[Amazon Athena](https://aws.amazon.com/athena/) runs SQL directly over the Parquet tables in
`s3://fathomnet-pds/metadata/`. You need an AWS account and an S3 location for query results; you pay
for the data each query scans. For small, interactive work, DuckDB or Polars on your own machine (see
the [README](../README.md)) needs no account.

## Create the tables

Run these once in the Athena query editor. They use
[partition projection](https://docs.aws.amazon.com/athena/latest/ug/partition-projection.html) on
`release`, so new releases are queryable without `MSCK REPAIR TABLE`.

```sql
CREATE DATABASE IF NOT EXISTS fathomnet;

CREATE EXTERNAL TABLE fathomnet.images (
  image_uuid string,
  s3_key string,
  thumbnail_s3_key string,
  source_url string,
  sha256 string,
  media_type string,
  width int,
  height int,
  image_license string,
  imaging_type string,
  recorded_timestamp timestamp,
  latitude double,
  longitude double,
  depth_meters double,
  altitude_meters double,
  temperature_celsius double,
  salinity double,
  oxygen_ml_l double,
  pressure_dbar double,
  modified_timestamp timestamp
)
PARTITIONED BY (release string)
STORED AS PARQUET
LOCATION 's3://fathomnet-pds/metadata/images/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.release.type' = 'date',
  'projection.release.format' = 'yyyy-MM-dd',
  'projection.release.range' = '2026-01-01,NOW',
  'storage.location.template' = 's3://fathomnet-pds/metadata/images/release=${release}/'
);

CREATE EXTERNAL TABLE fathomnet.boxes (
  box_uuid string,
  image_uuid string,
  concept string,
  alt_concept string,
  x int,
  y int,
  width int,
  height int,
  group_of boolean,
  occluded boolean,
  truncated boolean,
  review_state string,
  last_reviewed_timestamp timestamp,
  user_defined_key string,
  annotation_license string,
  modified_timestamp timestamp
)
PARTITIONED BY (release string)
STORED AS PARQUET
LOCATION 's3://fathomnet-pds/metadata/boxes/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.release.type' = 'date',
  'projection.release.format' = 'yyyy-MM-dd',
  'projection.release.range' = '2026-01-01,NOW',
  'storage.location.template' = 's3://fathomnet-pds/metadata/boxes/release=${release}/'
);

CREATE EXTERNAL TABLE fathomnet.concepts (
  concept string,
  is_taxon boolean,
  aphia_id bigint,
  accepted_aphia_id bigint,
  accepted_name string,
  rank string,
  kingdom string,
  phylum string,
  `class` string,
  `order` string,
  family string,
  genus string,
  species string
)
PARTITIONED BY (release string)
STORED AS PARQUET
LOCATION 's3://fathomnet-pds/metadata/concepts/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.release.type' = 'date',
  'projection.release.format' = 'yyyy-MM-dd',
  'projection.release.range' = '2026-01-01,NOW',
  'storage.location.template' = 's3://fathomnet-pds/metadata/concepts/release=${release}/'
);
```

The `tags`, `collections`, and `image_collections` tables follow the same pattern; see
[data-dictionary.md](data-dictionary.md) for their columns.

## Example: verified boxes per phylum below 1000 m

Always filter on `release` so Athena scans one snapshot.

```sql
SELECT c.phylum, count(*) AS n_boxes
FROM fathomnet.boxes b
JOIN fathomnet.images i ON i.image_uuid = b.image_uuid AND i.release = b.release
JOIN fathomnet.concepts c ON c.concept = b.concept AND c.release = b.release
WHERE b.release = '2026-11-01'
  AND b.review_state = 'VERIFIED'
  AND i.depth_meters > 1000
GROUP BY c.phylum
ORDER BY n_boxes DESC;
```

Select `DISTINCT i.s3_key` instead of the aggregate to get a manifest of matching images. A training
job on Amazon SageMaker or Amazon EC2 can then read only those objects from `s3://fathomnet-pds/images/`.
