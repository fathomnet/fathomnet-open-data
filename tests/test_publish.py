import pytest

from fathomnet_open_data.keys import check_release
from fathomnet_open_data.publish import merge_releases_csv

HEADER = "release,n_images,n_boxes,n_concepts,notes\n"


def row(release, notes=""):
    return {"release": release, "n_images": 1, "n_boxes": 2, "n_concepts": 1, "notes": notes}


def test_merge_releases_csv_creates_and_sorts():
    first = merge_releases_csv(None, row("2026-12-01"))
    both = merge_releases_csv(first, row("2026-11-01", "with, comma"))
    assert both == HEADER + '2026-11-01,1,2,1,"with, comma"\n2026-12-01,1,2,1,\n'


def test_merge_releases_csv_replaces_same_release():
    first = merge_releases_csv(None, row("2026-11-01", "old"))
    assert merge_releases_csv(first, row("2026-11-01", "new")) == HEADER + "2026-11-01,1,2,1,new\n"


@pytest.mark.parametrize("bad", ["2026-13-01", "20261101", "2026-11-1", "latest"])
def test_check_release_rejects_bad_ids(bad):
    with pytest.raises(ValueError):
        check_release(bad)
