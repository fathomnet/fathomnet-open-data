"""Step 3b: COCO object detection export derived from the release tables."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa

REGISTRY_URL = "https://registry.opendata.aws/fathomnet/"


def build_coco(images: pa.Table, boxes: pa.Table, release: str, base_url: str) -> dict:
    image_rows = images.select(
        ["image_uuid", "s3_key", "width", "height", "image_license", "recorded_timestamp"]
    ).to_pylist()
    box_rows = boxes.to_pylist()

    license_ids = {
        spdx: i
        for i, spdx in enumerate(
            sorted({r["image_license"] for r in image_rows if r["image_license"]}), 1
        )
    }
    category_ids = {
        name: i
        for i, name in enumerate(sorted({b["concept"] for b in box_rows if b["concept"]}), 1)
    }
    image_ids = {}
    coco_images = []
    for i, r in enumerate(image_rows, 1):
        image_ids[r["image_uuid"]] = i
        ts = r["recorded_timestamp"]
        coco_images.append(
            {
                "id": i,
                "file_name": r["s3_key"],
                "coco_url": f"{base_url}/{r['s3_key']}",
                "width": r["width"],
                "height": r["height"],
                "license": license_ids.get(r["image_license"]),
                "date_captured": ts.isoformat() if ts else None,
                "image_uuid": r["image_uuid"],
                "image_license": r["image_license"],
            }
        )

    annotations = []
    for i, b in enumerate((b for b in box_rows if b["concept"]), 1):
        w, h = b["width"] or 0, b["height"] or 0
        annotations.append(
            {
                "id": i,
                "image_id": image_ids[b["image_uuid"]],
                "category_id": category_ids[b["concept"]],
                "bbox": [b["x"], b["y"], w, h],
                "area": w * h,
                "iscrowd": 0,
                "box_uuid": b["box_uuid"],
                "image_uuid": b["image_uuid"],
                "alt_concept": b["alt_concept"],
                "group_of": b["group_of"],
                "occluded": b["occluded"],
                "truncated": b["truncated"],
                "review_state": b["review_state"],
                "annotation_license": b["annotation_license"],
            }
        )

    return {
        "info": {
            "description": "FathomNet bounding boxes",
            "version": release,
            "url": REGISTRY_URL,
            "year": int(release[:4]),
            "contributor": "FathomNet contributors; see image_license and annotation_license",
            "date_created": datetime.now(UTC).isoformat(),
        },
        "licenses": [
            {"id": i, "name": spdx, "url": f"https://spdx.org/licenses/{spdx}.html"}
            for spdx, i in license_ids.items()
        ],
        "images": coco_images,
        "annotations": annotations,
        "categories": [{"id": i, "name": name} for name, i in category_ids.items()],
    }


def write_coco(coco: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(coco, f, separators=(",", ":"))
