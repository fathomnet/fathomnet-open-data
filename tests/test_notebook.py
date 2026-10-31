"""Run every tutorial notebook cell against a bucket produced by the pipeline itself.

Builds a synthetic FathomNet, publishes it to a local store, then executes the notebook with S3
calls redirected to that store. This keeps the notebook in step with the published schema.
"""

import io
import os
import random
import shutil
from pathlib import Path

import matplotlib
import nbformat
import pytest

from fathomnet_open_data import pipeline
from fathomnet_open_data.store import LocalStore
from fathomnet_open_data.workdir import WorkDir

from .conftest import FakeClient, make_box, make_image, png_bytes

NOTEBOOK = Path(__file__).parents[1] / "get-to-know-a-dataset.ipynb"
CONCEPTS = ["Nanomia", "Bathochordaeus stygius", "Sebastes", "Strongylocentrotus fragilis", "Rock"]
LICENSES = ["CC0-1.0", "CC-BY-4.0", "CC-BY-NC-ND-4.0"]


def synthetic_api(n_images=150, seed=0):
    rng = random.Random(seed)
    images, blobs = [], {}
    for i in range(n_images):
        uuid = f"{i:08x}-0000-4000-8000-000000000000"
        url = f"https://img.test/{uuid}.png"
        blobs[url] = png_bytes(size=(640, 480), color=(i % 255, 40, 80))
        boxes = [
            make_box(
                f"{uuid}-{j}",
                concept=rng.choice(CONCEPTS),
                x=rng.randint(0, 500),
                y=rng.randint(0, 380),
                w=rng.randint(10, 140),
                h=rng.randint(10, 100),
                state=rng.choice(["VERIFIED", "VERIFIED", "UNVERIFIED"]),
            )
            for j in range(rng.randint(1, 12))
        ]
        for b in boxes:
            b["occluded"] = rng.choice([None, False, True])
            b["annotationLicense"] = rng.choice(LICENSES[:2])
        img = make_image(uuid, url, blobs[url], boxes=boxes)
        img.update(
            width=640,
            height=480,
            imageLicense=rng.choice(LICENSES),
            depthMeters=rng.uniform(0, 5000) if rng.random() < 0.9 else None,
            latitude=rng.uniform(-60, 60),
            longitude=rng.uniform(-180, 180),
        )
        images.append(img)
    upload = {"uuid": "upload-1", "status": None, "darwinCore": {"datasetID": "d1"}}
    links = [("upload-1", img["uuid"]) for img in images]
    return FakeClient(images, [upload], links), blobs


class FakeS3:
    """The subset of the boto3 S3 client the notebook uses, backed by a directory."""

    def __init__(self, root: Path):
        self.root = root

    def list_objects_v2(self, Bucket, Prefix="", Delimiter=None, MaxKeys=1000):
        keys = sorted(LocalStore(self.root).list_keys(Prefix))
        contents, prefixes = [], []
        for key in keys:
            rest = key[len(Prefix) :]
            if Delimiter and Delimiter in rest:
                p = Prefix + rest.split(Delimiter)[0] + Delimiter
                if p not in prefixes:
                    prefixes.append(p)
            else:
                contents.append({"Key": key, "Size": (self.root / key).stat().st_size})
        resp = {}
        if contents:
            resp["Contents"] = contents[:MaxKeys]
        if prefixes:
            resp["CommonPrefixes"] = [{"Prefix": p} for p in prefixes]
        return resp

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO((self.root / Key).read_bytes())}

    def download_file(self, Bucket, Key, Filename):
        shutil.copyfile(self.root / Key, Filename)


@pytest.fixture
def published_bucket(tmp_path):
    client, blobs = synthetic_api()
    work = WorkDir(tmp_path / "work", "2026-11-01")
    store = LocalStore(tmp_path / "bucket")
    pipeline.run_snapshot(client, work)
    pipeline.run_sync(work, store, blobs.__getitem__, workers=4)
    pipeline.run_build(work, store)
    pipeline.run_publish(work, store, notes="synthetic")
    return store.root


def test_notebook_runs_against_published_bucket(published_bucket, tmp_path, monkeypatch):
    import boto3

    matplotlib.use("Agg")
    monkeypatch.setattr(boto3, "client", lambda *a, **k: FakeS3(published_bucket))
    monkeypatch.chdir(tmp_path)

    ns: dict = {}
    for i, cell in enumerate(nbformat.read(NOTEBOOK, as_version=4).cells):
        if cell.cell_type != "code":
            continue
        src = (
            cell.source.replace('con.execute("INSTALL httpfs; LOAD httpfs;")', "")
            .replace("s3://{BUCKET}", str(published_bucket))
            .replace("MIN_BOXES = 1000", "MIN_BOXES = 50")
        )
        exec(compile(src, f"{NOTEBOOK.name}[{i}]", "exec"), ns)  # noqa: S102 trusted notebook

    assert len(ns["gallery"]) == len(CONCEPTS)
    assert len(ns["subset"]) > 0
    assert os.path.exists(tmp_path / "fathomnet-subset" / "annotations.json")
