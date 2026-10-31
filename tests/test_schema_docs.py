"""docs/data-dictionary.md must document exactly the columns in schema.py."""

import re
from pathlib import Path

import pytest

from fathomnet_open_data import schema

DOC = Path(__file__).parents[1] / "docs" / "data-dictionary.md"


def documented_columns() -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in DOC.read_text().splitlines():
        heading = re.match(r"^## `(\w+)`", line)
        if heading:
            current = sections.setdefault(heading.group(1), [])
        elif line.startswith("## "):
            current = None
        elif current is not None and line.startswith("| `"):
            first_cell = line.split("|")[1]
            current.extend(re.findall(r"`(\w+)`", first_cell))
    return sections


@pytest.mark.parametrize("table", list(schema.TABLES))
def test_data_dictionary_matches_schema(table):
    assert documented_columns().get(table) == schema.TABLES[table].names
