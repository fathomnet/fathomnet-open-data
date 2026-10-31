"""Object store abstraction: the public S3 bucket, or a local directory for dry runs and tests."""

import shutil
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .keys import (
    DEFAULT_REGION,
    IMAGES_PREFIX,
    THUMBNAILS_PREFIX,
    s3_public_base_url,
    uuid_from_key,
)


class Store(Protocol):
    def list_keys(self, prefix: str) -> Iterator[str]: ...

    def exists(self, key: str) -> bool: ...

    def get_bytes(self, key: str) -> bytes: ...

    def put_bytes(
        self, key: str, data: bytes, content_type: str, metadata: dict[str, str] | None = None
    ) -> None: ...

    def put_file(self, key: str, path: Path, content_type: str) -> None: ...

    def public_base_url(self) -> str: ...


class LocalStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def list_keys(self, prefix: str) -> Iterator[str]:
        base = self._path(prefix)
        # A prefix can name a directory or a partial file name.
        search = base if base.is_dir() else base.parent
        if not search.exists():
            return
        for p in search.rglob("*"):
            if p.is_file() and not p.name.endswith(".tmp"):
                key = p.relative_to(self.root).as_posix()
                if key.startswith(prefix):
                    yield key

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def put_bytes(self, key, data, content_type, metadata=None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def put_file(self, key, path, content_type) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)

    def public_base_url(self) -> str:
        return self.root.resolve().as_uri()


class S3Store:
    """Writes need credentials for the sponsored account (AWS_PROFILE or the usual env vars)."""

    def __init__(self, bucket: str, region: str = DEFAULT_REGION, client=None):
        self.bucket = bucket
        self.region = region
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                region_name=region,
                config=Config(max_pool_connections=64, retries={"mode": "adaptive"}),
            )
        self.client = client

    def list_keys(self, prefix: str) -> Iterator[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                yield obj["Key"]

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def get_bytes(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def put_bytes(self, key, data, content_type, metadata=None) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata=metadata or {},
            ChecksumAlgorithm="SHA256",
        )

    def put_file(self, key, path, content_type) -> None:
        self.client.upload_file(
            str(path), self.bucket, key, ExtraArgs={"ContentType": content_type}
        )

    def public_base_url(self) -> str:
        return s3_public_base_url(self.bucket, self.region)


@dataclass
class StoreIndex:
    """Existing objects in the store, keyed by image UUID."""

    images: dict[str, str] = field(default_factory=dict)
    thumbnails: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, store: Store) -> "StoreIndex":
        index = cls()
        for key in store.list_keys(IMAGES_PREFIX):
            index.images[uuid_from_key(key)] = key
        index.thumbnails = {uuid_from_key(k) for k in store.list_keys(THUMBNAILS_PREFIX)}
        return index

    def complete(self, image_uuid: str) -> bool:
        return image_uuid in self.images and image_uuid in self.thumbnails


def open_store(uri: str, region: str = DEFAULT_REGION) -> Store:
    """`s3://bucket` for S3; anything else is a local directory."""
    if uri.startswith("s3://"):
        bucket = uri.removeprefix("s3://").strip("/")
        if not bucket or "/" in bucket:
            raise ValueError(f"expected s3://<bucket> with no prefix, got {uri!r}")
        return S3Store(bucket, region)
    return LocalStore(uri)
