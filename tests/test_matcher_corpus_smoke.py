"""Corpus smoke guard over every real title in the workspace.

Two distinct jobs:

1. **Hard guard** -- no entry point may raise on any real title, and no query may
   come back empty.  This exists because a refactor once renamed a local variable
   and left a dangling reference that only fired on ``<prefix> <capacity> <series>``
   shaped titles; the unit tests never hit that shape, and a differential harness
   that swallowed exceptions recorded the crash as a "delta" instead of a failure.

2. **Characterisation** -- two known gaps are *pinned*, not fixed, so they cannot
   silently grow.  Both pre-date the matcher refactor (measured old=57 / new=42 for
   the first, byte-identical for the second); see
   ``docs/validation-report-matcher-refactor.md`` §"Known gaps carried forward".
"""

from __future__ import annotations

import csv
import glob
import os

import pytest

from pricing_engine.matcher import (
    expand_multivariant_titles,
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    is_strict_model_match,
    referee_match,
)

BRAND_PREFIXES = ("Dawlance", "Haier", "Gree", "TCL", "Kenwood", "PEL", "WestPoint", "Super Asia")

# Pinned baselines measured over this corpus (see module docstring).
MAX_SELF_MATCH_REJECTS = 42
KNOWN_DANGLING_PATTERN_TITLES = {"SG WATER PURIFIER -"}


def _brand_of(title: str) -> str:
    up = title.upper()
    return next((b for b in BRAND_PREFIXES if up.startswith(b.upper())), "")


def _corpus(limit: int = 700) -> list[str]:
    """Deterministic sample of Name columns from every catalog and fixture CSV."""
    titles: list[str] = []
    for path in sorted(glob.glob("data/inputs/*.csv") + glob.glob("tests/fixtures/*.csv")):
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                if not row:
                    continue
                first = next(iter(row.values()))
                if first and len(str(first).strip()) > 8:
                    titles.append(str(first).strip())
    step = max(1, len(titles) // limit)
    return titles[::step][:limit]


CORPUS = _corpus()


def test_corpus_paths_resolve() -> None:
    """Make the corpus path assumption explicit instead of silently empty."""
    assert os.path.isdir("tests/fixtures") and os.path.isdir("data/inputs")
    assert len(CORPUS) >= 300, f"corpus only yielded {len(CORPUS)} titles"


# --------------------------------------------------------------- hard guards


@pytest.mark.parametrize("title", CORPUS)
def test_no_entry_point_raises(title: str) -> None:
    brand = _brand_of(title)
    extract_search_query_and_model(title, brand=brand)
    generate_search_patterns(title, brand=brand)
    extract_product_slots(title, brand=brand)
    expand_multivariant_titles(title)
    is_strict_model_match(title, title, brand=brand)
    referee_match(title, title, brand=brand)


def test_search_query_is_never_empty() -> None:
    """An empty query silently produces an empty scrape -- it must never happen."""
    empties = [
        t for t in CORPUS if not extract_search_query_and_model(t, brand=_brand_of(t))[0].strip()
    ]
    assert not empties, f"empty search query for: {empties[:5]}"


def test_model_code_is_never_empty() -> None:
    empties = [
        t for t in CORPUS if not extract_search_query_and_model(t, brand=_brand_of(t))[1].strip()
    ]
    assert not empties, f"empty model code for: {empties[:5]}"


def test_no_category_phrase_leaks_into_series() -> None:
    """RC-1 guard across the whole corpus, not just the DWT-1016 example."""
    banned = {"FULLY", "AUTOMATIC", "WASHING", "MACHINE", "REFRIGERATOR"}
    leaks = [
        (t, extract_product_slots(t, brand=_brand_of(t)).series)
        for t in CORPUS
        if banned & set(extract_product_slots(t, brand=_brand_of(t)).series.upper().split())
    ]
    assert not leaks, f"category phrase leaked into series: {leaks[:5]}"


# ------------------------------------------------------- characterised gaps


def test_self_match_rejects_do_not_grow() -> None:
    """A product should always match its own title.

    42 corpus rows still fail this -- all non-appliance SKUs (geysers, garment
    steamers, fans, blenders) whose marketing prose ("Electric Geyser", "Touch
    Panel") is read as a series name.  Pre-existing: the pre-refactor matcher
    rejected 57.  Pinned so the number can only go down.
    """
    rejects = []
    for t in CORPUS:
        brand = _brand_of(t)
        decision = referee_match(extract_product_slots(t, brand=brand), t, brand=brand)
        if not decision.usable:
            rejects.append(t)
    assert len(rejects) <= MAX_SELF_MATCH_REJECTS, (
        f"{len(rejects)} self-match rejects (baseline {MAX_SELF_MATCH_REJECTS}); "
        f"new offenders: {rejects[:5]}"
    )


def test_dangling_search_patterns_do_not_grow() -> None:
    """Queries must not be blank or end in a bare hyphen ('DF-', 'SG -').

    One pre-existing title still emits them; identical output before and after the
    refactor.  Pinned by title so any *new* offender fails immediately.
    """
    offenders = set()
    for t in CORPUS:
        patterns = generate_search_patterns(t, brand=_brand_of(t))
        if any(
            not q.strip() or q.strip().endswith("-")
            for queries in patterns.values()
            for q in queries
        ):
            offenders.add(t)
    assert offenders <= KNOWN_DANGLING_PATTERN_TITLES, (
        f"new dangling-pattern titles: {offenders - KNOWN_DANGLING_PATTERN_TITLES}"
    )
