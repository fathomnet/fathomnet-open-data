"""Minimal read-only client for the public FathomNet REST API."""

from collections.abc import Iterator
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://database.fathomnet.org/api"
USER_AGENT = "fathomnet-open-data-release"


def make_session(pool_size: int = 32) -> requests.Session:
    """Session with retries on transient errors."""
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=pool_size, pool_maxsize=pool_size)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = USER_AGENT
    return session


class FathomNetClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        session: requests.Session | None = None,
        timeout: float = 300.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = session or make_session()
        self.timeout = timeout

    def _get(self, path: str, **params: Any) -> Any:
        resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _iter_pages(self, path: str, page_size: int) -> Iterator[dict]:
        # Sort by internal id so new rows land on later pages while we read.
        page = 0
        while True:
            body = self._get(path, page=page, size=page_size, sort="id")
            yield from body["content"]
            page += 1
            if page >= body["totalPages"]:
                return

    def count_images(self) -> int:
        return self._get("/images/count")["count"]

    def iter_images(self, page_size: int = 2000) -> Iterator[dict]:
        """Every image, with nested boundingBoxes and tags."""
        return self._iter_pages("/images", page_size)

    def iter_uploads(self, page_size: int = 500) -> Iterator[dict]:
        """Every image set upload (collection), with nested darwinCore."""
        return self._iter_pages("/imagesetuploads/list/all", page_size)

    def iter_upload_image_uuids(self, upload_uuid: str, page_size: int = 10000) -> Iterator[str]:
        offset = 0
        while True:
            rows = self._get(
                f"/geoimages/query/imagesetupload/{upload_uuid}", limit=page_size, offset=offset
            )
            for row in rows:
                yield row["uuid"]
            if len(rows) < page_size:
                return
            offset += page_size
