"""Local working directory layout for one release."""

import gzip
import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkDir:
    root: Path
    release: str

    @property
    def base(self) -> Path:
        return self.root / self.release

    @property
    def raw(self) -> Path:
        return self.base / "raw"

    @property
    def metadata(self) -> Path:
        return self.base / "metadata"

    def raw_file(self, name: str) -> Path:
        return self.raw / f"{name}.jsonl.gz"

    def table_file(self, table: str) -> Path:
        return self.metadata / f"{table}.parquet"

    @property
    def coco_file(self) -> Path:
        return self.base / "exports" / "coco" / "fathomnet-boxes.json"

    def report_file(self, step: str) -> Path:
        return self.base / f"{step}-report.json"


def write_jsonl_gz(path: Path, rows: Iterable[dict]) -> int:
    """Write rows atomically; return the number written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    n = 0
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")))
            f.write("\n")
            n += 1
    os.replace(tmp, path)
    return n


def read_jsonl_gz(path: Path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
