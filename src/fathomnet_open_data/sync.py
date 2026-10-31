"""Step 2: copy public images into the store and generate thumbnails.

The store itself is the state: an image is skipped if its original and thumbnail already exist.
Image objects are immutable, so a later release never rewrites them.
"""

import logging
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import requests
from PIL import Image

from .api import make_session
from .keys import image_key, thumbnail_key
from .media import detect_format, make_thumbnail, sha256_hex
from .snapshot import is_public
from .store import Store, StoreIndex

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
        resp = session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.content


@dataclass
class SyncResult:
    candidates: int = 0
    already_present: int = 0
    images_uploaded: int = 0
    thumbnails_uploaded: int = 0
    failures: list[dict] = field(default_factory=list)


class SyncError(RuntimeError):
    pass


# Problems with one image are recorded and skipped. Anything else (for example, S3 credentials)
# stops the run; rerunning resumes from what is already in the store.
PER_IMAGE_ERRORS = (
    requests.RequestException,
    SyncError,
    ValueError,
    OSError,
    Image.DecompressionBombError,
)


def _sync_one(image: dict, store: Store, fetch: Fetch, existing_key: str | None) -> bool:
    """Ensure original and thumbnail exist. Return True if the original was uploaded."""
    image_uuid = image["uuid"]
    if existing_key:
        # Original already copied; only the thumbnail is missing.
        data = store.get_bytes(existing_key)
        uploaded = False
    else:
        data = fetch(image["url"])
        digest = sha256_hex(data)
        expected = (image.get("sha256") or "").lower()
        if expected and expected != digest:
            raise SyncError(f"sha256 mismatch: API {expected}, downloaded {digest}")
        ext, media_type = detect_format(data)
        store.put_bytes(image_key(image_uuid, ext), data, media_type, metadata={"sha256": digest})
        uploaded = True
    store.put_bytes(thumbnail_key(image_uuid), make_thumbnail(data), "image/jpeg")
    return uploaded


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

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_sync_one, img, store, fetch, index.images.get(img["uuid"])): img
            for img in todo
        }
        for i, future in enumerate(as_completed(futures), 1):
            img = futures[future]
            try:
                if future.result():
                    result.images_uploaded += 1
                result.thumbnails_uploaded += 1
            except PER_IMAGE_ERRORS as e:
                result.failures.append(
                    {"image_uuid": img["uuid"], "url": img.get("url"), "error": str(e)}
                )
            if i % 1000 == 0:
                log.info("synced %d/%d (%d failures)", i, len(todo), len(result.failures))
    return result
