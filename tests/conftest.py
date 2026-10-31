"""Shared fixtures: a tiny fake FathomNet API and image bytes."""

import io

import pytest
from PIL import Image

from fathomnet_open_data.media import sha256_hex
from fathomnet_open_data.store import LocalStore
from fathomnet_open_data.workdir import WorkDir

RELEASE = "2026-11-01"


def png_bytes(size=(64, 48), color=(10, 40, 80)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def jpeg_bytes(size=(64, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 100, 0)).save(buf, format="JPEG")
    return buf.getvalue()


def make_image(uuid, url, data, valid=True, boxes=(), tags=(), sha=None):
    return {
        "uuid": uuid,
        "url": url,
        "contributorsEmail": "contributor@example.org",
        "width": 64,
        "height": 48,
        "imagingType": "ROV",
        "depthMeters": 1200.5,
        "latitude": 36.8,
        "longitude": -122.0,
        "altitude": None,
        "salinity": 34.4,
        "temperatureCelsius": 4.1,
        "oxygenMlL": 1.0,
        "pressureDbar": 1210.0,
        "timestamp": "2019-08-08T22:23:25Z",
        "lastUpdatedTimestamp": "2025-09-29T23:41:44.434+00:00",
        "sha256": sha if sha is not None else sha256_hex(data),
        "mediaType": None,
        "valid": valid,
        "imageLicense": "CC-BY-4.0",
        "boundingBoxes": list(boxes),
        "tags": list(tags),
    }


def make_box(uuid, concept="Nanomia", x=1, y=2, w=10, h=8, state="VERIFIED"):
    return {
        "uuid": uuid,
        "concept": concept,
        "altConcept": None,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "groupOf": None,
        "occluded": False,
        "truncated": None,
        "observer": "annotator@example.org",
        "reviewer": "reviewer@example.org",
        "reviewState": state,
        "lastReviewedTimestamp": "2025-01-02T03:04:05Z",
        "lastUpdatedTimestamp": "2025-01-02T03:04:05.123Z",
        "userDefinedKey": "k1",
        "annotationLicense": "CC0-1.0",
    }


class FakeClient:
    base_url = "https://fake.test/api"

    def __init__(self, images, uploads, links):
        self.images, self.uploads, self.links = images, uploads, links

    def count_images(self):
        return len(self.images)

    def iter_images(self):
        return iter(self.images)

    def iter_uploads(self):
        return iter(self.uploads)

    def iter_upload_image_uuids(self, upload_uuid):
        return (i for c, i in self.links if c == upload_uuid)


@pytest.fixture
def blobs():
    return {
        "https://img.test/a.png": png_bytes(),
        "https://img.test/b.jpg": jpeg_bytes(),
        "https://img.test/c.png": png_bytes(color=(1, 2, 3)),
        "https://img.test/bad.png": png_bytes(color=(9, 9, 9)),
    }


@pytest.fixture
def fake_api(blobs):
    a = make_image(
        "aaaaaaaa-0000-0000-0000-000000000001",
        "https://img.test/a.png",
        blobs["https://img.test/a.png"],
        boxes=[make_box("box-1"), make_box("box-2", concept="Sebastes", state="UNVERIFIED")],
        tags=[{"uuid": "tag-1", "key": "camera", "value": "4K", "mediaType": "text/plain"}],
    )
    b = make_image(
        "bbbbbbbb-0000-0000-0000-000000000002",
        "https://img.test/b.jpg",
        blobs["https://img.test/b.jpg"],
        boxes=[make_box("box-3", x=60, w=10)],  # extends past the right edge
    )
    invalid = make_image(
        "cccccccc-0000-0000-0000-000000000003",
        "https://img.test/c.png",
        blobs["https://img.test/c.png"],
        valid=False,
        boxes=[make_box("box-4")],
    )
    mismatch = make_image(
        "dddddddd-0000-0000-0000-000000000004",
        "https://img.test/bad.png",
        blobs["https://img.test/bad.png"],
        sha="0" * 64,
    )
    upload = {
        "uuid": "upload-1",
        "contributorsEmail": "contributor@example.org",
        "remoteUri": "https://example.org/archive/contributor_at_example.org.zip",
        "status": None,
        "createdTimestamp": "2025-08-31T04:32:24.712Z",
        "darwinCore": {
            "datasetID": "dataset-1",
            "ownerInstitutionCode": "MBARI",
            "institutionCode": "MBARI",
            "collectionCode": "Dive 1",
            "rightsHolder": "MBARI",
            "accessRights": "https://www.fathomnet.org/terms",
            "recordType": "StillImage",
            "basisOfRecord": "MachineObservation",
            "license": "CC BY 4.0",
        },
    }
    rejected = dict(upload, uuid="upload-2", status="REJECTED")
    links = [
        ("upload-1", a["uuid"]),
        ("upload-1", b["uuid"]),
        ("upload-1", invalid["uuid"]),
        ("upload-2", a["uuid"]),
    ]
    return FakeClient([a, b, invalid, mismatch], [upload, rejected], links)


@pytest.fixture
def fetch(blobs):
    return lambda url: blobs[url]


@pytest.fixture
def work(tmp_path):
    return WorkDir(tmp_path / "work", RELEASE)


@pytest.fixture
def store(tmp_path):
    return LocalStore(tmp_path / "bucket")
