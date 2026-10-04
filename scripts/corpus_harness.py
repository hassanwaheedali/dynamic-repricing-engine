"""Corpus harness: every product-title cell of every input/fixture CSV.

Used by ``tests/test_matcher_corpus_smoke.py``.  Deliberately reads *every*
string column, not just the first one: ``data/inputs/Haier_Products_List.csv``
starts with ``S.No,Brand,Name`` (column 0 is a number, column 1 is a brand) and
``tests/fixtures/Stock Holding Report ...csv`` starts with ``Item Name,Brand,
Warehouse,Category`` (column 3 is a category word).  A first-column-only sweep
feeds brand names and category words to the matcher and silently skips the real
titles.
"""

from __future__ import annotations

import csv
import glob
import re
from collections.abc import Iterator

INPUT_GLOBS = ("data/inputs/*.csv", "tests/fixtures/*.csv")

# Columns that hold a product title.  Note the trailing-space variant: the real
# upload sheets ship a header of ``Name `` and an exact match would miss them.
NAME_COLUMNS = {"name", "name ", "item name", "item name "}
BRAND_COLUMNS = {"brand", "brand ", "brands", "brands "}

_TRIVIAL = re.compile(r"^[-\s.|,]+$")


def csv_files() -> list[str]:
    return sorted(p for g in INPUT_GLOBS for p in glob.glob(g))


def _cells(path: str) -> Iterator[tuple[int, str, str]]:
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for lineno, row in enumerate(csv.DictReader(fh), start=2):
            for col, val in row.items():
                if not col or val is None:
                    continue
                text = str(val).strip()
                if len(text) >= 3 and not _TRIVIAL.match(text):
                    yield lineno, str(col).strip(), text


def iter_all_cells() -> Iterator[tuple[str, int, str, str]]:
    """Every non-trivial cell: ``(file, line, column, value)``."""
    for path in csv_files():
        for lineno, col, val in _cells(path):
            yield path, lineno, col, val


def iter_product_titles() -> Iterator[tuple[str, int, str, str]]:
    """Genuine product titles with the file's own Brand column.

    Yields ``(file, line, brand, title)``.  ``brand`` is ``""`` when the sheet
    has no Brand column, which is the case for the two stress-test lists.
    """
    for path in csv_files():
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            for lineno, row in enumerate(csv.DictReader(fh), start=2):
                if not row:
                    continue
                by_key = {str(k).strip().lower(): k for k in row if k}
                name_col = next((by_key[k] for k in NAME_COLUMNS if k in by_key), None)
                if not name_col:
                    continue
                title = str(row[name_col] or "").strip()
                if len(title) < 5:
                    continue
                brand_col = next((by_key[k] for k in BRAND_COLUMNS if k in by_key), None)
                brand = str(row[brand_col] or "").strip() if brand_col else ""
                yield path, lineno, brand, title
