"""fathomnet-release: build and publish a FathomNet release to the Open Data bucket."""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import pipeline
from .api import BASE_URL, FathomNetClient
from .keys import DEFAULT_REGION, check_release
from .store import open_store
from .workdir import WorkDir


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fathomnet-release", description=__doc__)
    p.add_argument("--work", type=Path, default=Path("work"), help="local work directory")
    p.add_argument(
        "--release",
        type=check_release,
        default=datetime.now(UTC).date().isoformat(),
        help="release id, YYYY-MM-DD (default: today, UTC)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="step", required=True)

    def with_store(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sp.add_argument(
            "--store", required=True, help="s3://<bucket>, or a local directory for dry runs"
        )
        sp.add_argument("--region", default=DEFAULT_REGION)
        return sp

    def with_sync(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--workers", type=int, default=16)
        sp.add_argument("--limit", type=int, help="sync at most N images (for testing)")

    def with_publish(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--notes", default="", help="summary for releases.csv")
        sp.add_argument("--force", action="store_true", help="overwrite an existing release")

    snap = sub.add_parser("snapshot", help="fetch metadata from the FathomNet REST API")
    snap.add_argument("--api-url", default=BASE_URL)
    snap.add_argument("--refresh", action="store_true", help="fetch even if a snapshot exists")

    with_sync(with_store(sub.add_parser("sync", help="copy images and make thumbnails")))
    with_store(sub.add_parser("build", help="build Parquet tables and the COCO export"))
    with_store(sub.add_parser("validate", help="check a built release"))
    with_publish(with_store(sub.add_parser("publish", help="validate, then upload metadata")))

    run = with_store(sub.add_parser("run", help="snapshot, sync, build, validate, publish"))
    run.add_argument("--api-url", default=BASE_URL)
    run.add_argument("--refresh", action="store_true")
    with_sync(run)
    with_publish(run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    work = WorkDir(args.work, args.release)
    store = open_store(args.store, args.region) if hasattr(args, "store") else None

    def show(obj) -> None:
        print(json.dumps(obj, indent=2, default=str))

    try:
        if args.step in ("snapshot", "run"):
            show(pipeline.run_snapshot(FathomNetClient(args.api_url), work, args.refresh))
        if args.step in ("sync", "run"):
            show(pipeline.run_sync(work, store, workers=args.workers, limit=args.limit))
        if args.step in ("build", "run"):
            show(pipeline.run_build(work, store))
        if args.step == "validate":
            report = pipeline.run_validate(work, store)
            return 0 if report.ok else 1
        if args.step in ("publish", "run"):
            show(pipeline.run_publish(work, store, args.notes, args.force))
    except pipeline.StepError as e:
        logging.getLogger("fathomnet-release").error(str(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
