"""Step 2: copy public images into the store, generate thumbnails, and record checksums.

The store itself is the state. An image is complete when its original, its thumbnail, and its
manifest entry (SHA-256 and size of the stored bytes) all exist; anything missing is filled in on
the next run. Image objects are immutable, so a later release never rewrites them.
"""

import io
import logging
import threading
import uuid
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime

import botocore.exceptions
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from PIL import Image

from . import schema
from .api import make_session
from .keys import image_key, manifest_key, thumbnail_key
from .media import inspect_image, make_thumbnail, sha256_hex
from .snapshot import is_public
from .store import Store, StoreIndex
from .tls import verify_for

log = logging.getLogger(__name__)

Fetch = Callable[[str], bytes]


class HttpFetcher:
    """Thread-safe GET of image bytes, one session per thread."""

    def __init__(self, timeout: float = 120.0):
        self.timeout = timeout
        self._local = threading.local()

    def __call__(self, url: str) -> bytes:
        session = getattr(self._local, "session", None)
        if session is None:
            session = self._local.session = make_session(pool_size=4)
        resp = session.get(url, timeout=self.timeout, verify=verify_for(url))
        resp.raise_for_status()
        return resp.content


class SyncError(RuntimeError):
    pass


# Problems with one image are recorded and skipped, including dropped connections to the store
# (retried on the next run). Anything else (for example, S3 credentials or permissions) stops the
# run; rerunning resumes from what is already in the store.
PER_IMAGE_ERRORS = (
    requests.RequestException,
    botocore.exceptions.ConnectionError,
    botocore.exceptions.HTTPClientError,
    SyncError,
    ValueError,
    OSError,
    Image.DecompressionBombError,
)


@dataclass
class SyncResult:
    candidates: int = 0
    already_present: int = 0
    images_uploaded: int = 0
    thumbnails_uploaded: int = 0
    manifest_entries: int = 0
    # FathomNet's stored sha256 disagreed with the bytes but the image size matched.
    checksum_mismatches: list[dict] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)


@dataclass
class Outcome:
    image_uploaded: bool = False
    thumbnail_uploaded: bool = False
    manifest_row: dict | None = None
    checksum_mismatch: dict | None = None


def verify_download(image: dict, data: bytes) -> tuple[str, str, str, dict | None]:
    """Check downloaded bytes against FathomNet. Return (sha256, ext, media type, mismatch).

    FathomNet's stored sha256 is wrong for some images, so a mismatch is accepted when the image
    decodes at the width and height FathomNet recorded; it is returned for reporting.
    """
    info = inspect_image(data)
    digest = sha256_hex(data)
    expected = (image.get("sha256") or "").lower()
    mismatch = None
    if expected != digest:
        api_size = (image.get("width"), image.get("height"))
        if (info.width, info.height) != api_size:
            raise SyncError(
                f"sha256 and size differ from FathomNet: API {expected or None} {api_size}, "
                f"downloaded {digest} {(info.width, info.height)}"
            )
        mismatch = {"image_uuid": image["uuid"], "api_sha256": expected or None, "sha256": digest}
    return digest, info.ext, info.media_type, mismatch


def _sync_one(image: dict, store: Store, fetch: Fetch, index: StoreIndex) -> Outcome:
    image_uuid = image["uuid"]
    outcome = Outcome()
    key = index.images.get(image_uuid)
    if key:
        data = store.get_bytes(key)
        digest = sha256_hex(data)
    else:
        data = fetch(image["url"])
        digest, ext, media_type, outcome.checksum_mismatch = verify_download(image, data)
        key = image_key(image_uuid, ext)
        store.put_bytes(key, data, media_type, metadata={"sha256": digest})
        outcome.image_uploaded = True
    if image_uuid not in index.thumbnails:
        store.put_bytes(thumbnail_key(image_uuid), make_thumbnail(data), "image/jpeg")
        outcome.thumbnail_uploaded = True
    if image_uuid not in index.checksums or outcome.image_uploaded:
        outcome.manifest_row = {
            "image_uuid": image_uuid,
            "s3_key": key,
            "sha256": digest,
            "size_bytes": len(data),
            "synced_timestamp": datetime.now(UTC),
        }
    return outcome


class ManifestWriter:
    """Buffers manifest rows and writes them to the store in parts."""

    def __init__(self, store: Store, part_size: int = 5000):
        self.store = store
        self.part_size = part_size
        self.run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        self.rows: list[dict] = []
        self.seq = 0

    def add(self, row: dict) -> None:
        self.rows.append(row)
        if len(self.rows) >= self.part_size:
            self.flush()

    def flush(self) -> None:
        if not self.rows:
            return
        buf = io.BytesIO()
        pq.write_table(pa.Table.from_pylist(self.rows, schema=schema.MANIFEST), buf)
        self.store.put_bytes(
            manifest_key(self.run_id, self.seq), buf.getvalue(), "application/vnd.apache.parquet"
        )
        self.seq += 1
        self.rows = []


def sync_objects(
    images: Iterable[dict],
    store: Store,
    fetch: Fetch | None = None,
    workers: int = 16,
    limit: int | None = None,
) -> SyncResult:
    fetch = fetch or HttpFetcher()
    index = StoreIndex.load(store)
    result = SyncResult()

    todo = []
    for image in images:
        if not is_public(image):
            continue
        result.candidates += 1
        if index.complete(image["uuid"]):
            result.already_present += 1
        else:
            todo.append(image)
    if limit is not None:
        todo = todo[:limit]
    log.info(
        "%d public images, %d already present, %d to sync",
        result.candidates,
        result.already_present,
        len(todo),
    )

    manifest = ManifestWriter(store)
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = {pool.submit(_sync_one, img, store, fetch, index): img for img in todo}
        for i, future in enumerate(as_completed(futures), 1):
            img = futures[future]
            try:
                outcome = future.result()
            except PER_IMAGE_ERRORS as e:
                result.failures.append(
                    {"image_uuid": img["uuid"], "url": img.get("url"), "error": str(e)}
                )
            else:
                result.images_uploaded += outcome.image_uploaded
                result.thumbnails_uploaded += outcome.thumbnail_uploaded
                if outcome.checksum_mismatch:
                    result.checksum_mismatches.append(outcome.checksum_mismatch)
                if outcome.manifest_row:
                    manifest.add(outcome.manifest_row)
                    result.manifest_entries += 1
            if i % 1000 == 0:
                log.info("synced %d/%d (%d failures)", i, len(todo), len(result.failures))
    except BaseException:
        # Stop promptly on Ctrl-C or a store error instead of draining the whole queue.
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        pool.shutdown()
    finally:
        # Record checksums for everything uploaded so far, even if the run is interrupted.
        manifest.flush()
    return result
