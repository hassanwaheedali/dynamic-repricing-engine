"""Corpus smoke guard over every real title in every input and fixture file.

Reads *every* string column of all 12 CSVs via ``scripts/corpus_harness.py`` --
not just column 0.  ``data/inputs/Haier_Products_List.csv`` starts with
``S.No,Brand,Name`` and ``tests/fixtures/Stock Holding Report ...csv`` with
``Item Name,Brand,Warehouse,Category``, so a first-column-only sweep feeds brand
names and category words to the matcher and silently skips the real titles.

Coverage: 2,997 unique product titles, 51 brands, 5 entry points each.

The two characterisation baselines that used to be pinned here (42 self-match
rejects, 1 dangling-query title) are now **fixed** and asserted at zero.  Each of
the fixes has a named regression test below.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from corpus_harness import csv_files, iter_all_cells, iter_product_titles  # noqa: E402

from pricing_engine.matcher import (  # noqa: E402
    expand_cartesian_branches,
    expand_multivariant_titles,
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    is_strict_model_match,
    referee_match,
)

TITLES: list[tuple[str, str, str]] = []
_seen: set[str] = set()
for _path, _line, _brand, _title in iter_product_titles():
    if _title.upper() not in _seen:
        _seen.add(_title.upper())
        TITLES.append((_brand, _title, f"{_path}:{_line}"))


def test_corpus_covers_every_input_file() -> None:
    """Guard against the corpus silently collapsing (glob/path/header drift)."""
    assert len(csv_files()) == 12, csv_files()
    assert len(TITLES) > 2500, f"corpus only yielded {len(TITLES)} unique titles"


def test_harness_reads_all_columns_not_just_the_first() -> None:
    """Regression guard for the harness itself: column 0 is often not the title."""
    columns = {col for _, _, col, _ in iter_all_cells()}
    assert {"Name", "Item Name", "Brand", "Category"} <= columns
    brands = {b for b, _, _ in TITLES if b}
    assert len(brands) >= 40, f"only {len(brands)} brands harvested"


def test_every_file_with_a_unique_title_contributes() -> None:
    """4 of the 12 CSVs are byte-identical duplicates of another file.

    Asserting 12 contributing files would fail on the de-duplication, not on a
    harness bug -- so assert on the files that actually hold unique titles.
    """
    contributing = {origin.rsplit(":", 1)[0] for _, _, origin in TITLES}
    duplicates = {
        "data/inputs/template.csv",  # 2-row header template
        "data/inputs/sample_test_products.csv",  # == tests/fixtures/sample_test_products.csv
        "data/inputs/Haier_Washers.csv",  # == tests/fixtures/Haier_Washing_Machines...
        "data/inputs/Gree_AC.csv",  # == tests/fixtures/Gree_Uploading_on_DigiMall...
    }
    assert len(contributing) == len(csv_files()) - len(duplicates), (
        f"missing: {set(csv_files()) - duplicates - contributing}"
    )


# --------------------------------------------------------------- hard guards


@pytest.mark.parametrize("brand,title,origin", TITLES, ids=[o for _, _, o in TITLES])
def test_no_entry_point_raises(brand: str, title: str, origin: str) -> None:
    extract_search_query_and_model(title, brand=brand)
    generate_search_patterns(title, brand=brand)
    extract_product_slots(title, brand=brand)
    expand_multivariant_titles(title)
    expand_cartesian_branches(title)
    is_strict_model_match(title, title, brand=brand)
    referee_match(title, title, brand=brand)


@pytest.mark.parametrize("brand,title,origin", TITLES, ids=[o for _, _, o in TITLES])
def test_search_query_and_model_are_never_empty(brand: str, title: str, origin: str) -> None:
    """An empty query silently produces an empty scrape -- it must never happen."""
    query, model = extract_search_query_and_model(title, brand=brand)
    assert query.strip(), f"empty search query for {title!r} ({origin})"
    assert model.strip(), f"empty model code for {title!r} ({origin})"


@pytest.mark.parametrize("brand,title,origin", TITLES, ids=[o for _, _, o in TITLES])
def test_every_title_matches_itself(brand: str, title: str, origin: str) -> None:
    """A product must always match its own listing.

    Was 173 failures over this corpus (42 in an earlier 700-title sample).  All
    are fixed; see the named regression tests below.
    """
    decision = referee_match(extract_product_slots(title, brand=brand), title, brand=brand)
    assert decision.usable, (
        f"{origin}: {title!r} rejected itself -> {decision.reason}"
    )


@pytest.mark.parametrize("brand,title,origin", TITLES, ids=[o for _, _, o in TITLES])
def test_no_dangling_search_queries(brand: str, title: str, origin: str) -> None:
    """Queries must not be blank or end in a bare separator ('DF-', 'SG -')."""
    for tier, queries in generate_search_patterns(title, brand=brand).items():
        for q in queries:
            assert q.strip(), f"{tier} empty query for {title!r} ({origin})"
            assert not q.strip().endswith(("-", "|", "/")), (
                f"{tier} dangling query {q!r} for {title!r} ({origin})"
            )


def test_no_category_phrase_leaks_into_series() -> None:
    """RC-1 guard across the whole corpus, not just the DWT-1016 example."""
    banned = {"FULLY", "AUTOMATIC", "WASHING", "MACHINE", "REFRIGERATOR", "CONDITIONER"}
    leaks = []
    for brand, title, origin in TITLES:
        series = extract_product_slots(title, brand=brand).series.upper().split()
        if banned & set(series):
            leaks.append((origin, title, series))
    assert not leaks, f"category phrase leaked into series: {leaks[:5]}"


# --------------------------------------------------- named regression tests


def test_adjacent_slash_list_is_one_variant_axis() -> None:
    """A digit list must not be paired off into two variant axes.

    ``GS-24PITH15/16/17/18G-T3`` used to expand to ``GS-24PITH15/17`` and
    ``16/18G-T3`` -- model codes that do not exist on any marketplace.
    """
    branches = expand_cartesian_branches("GS-24PITH15/16/17/18G-T3 Inverter")
    assert branches == [
        "GS-24PITH15G-T3 Inverter",
        "GS-24PITH16G-T3 Inverter",
        "GS-24PITH17G-T3 Inverter",
        "GS-24PITH18G-T3 Inverter",
    ]
    for b in branches:
        assert referee_match("GS-24PITH15/16/17/18G-T3", b).usable, b


def test_multi_branch_anchor_matches_its_own_branches() -> None:
    """One branch of a multi-variant anchor *is* the product.

    ``HSU-13HFS/013WDC(G)`` is one machine with two orderable branches, so a
    listing written with either single branch must match EXACT -- not reject,
    not even fall back to base.  The ``013WDC`` case previously rejected because
    the series slot had absorbed prose ("Super Pro") that the branch's matched
    series alternative did not contain.
    """
    target = (
        "Haier AC 1 Ton Inverter T3 Compressor Golden Color Heat and Cool Super "
        "T3 Pro Inverter HSU-13HFS/013WDC(G)-T3 Pro | Official 5year parts 10 "
        "Year Compressor warranty | Free Installation by Haier (0% Ma"
    )
    slots = extract_product_slots(target, brand="Haier")
    assert referee_match(slots, target, brand="Haier").is_match
    for branch in ("HSU-13HFS(G)", "HSU-013WDC(G)"):
        listing = target.replace("HSU-13HFS/013WDC(G)-T3 Pro", f"{branch}-T3 Pro")
        decision = referee_match(slots, listing, brand="Haier")
        assert decision.is_match, f"{branch}: {decision.reason}"


def test_homoglyph_capacity_unit_is_not_a_series() -> None:
    """Greek capitals reach the sheets via keyboard slips: '1.5 ΤΟΝ' == '1.5 TON'."""
    greek = "ECOSTAR SPLIT 1.5 \u03a4\u039f\u039d 18DU01GC"
    latin = "ECOSTAR SPLIT 1.5 TON 18DU01GC"
    assert extract_product_slots(greek, brand="ECOSTAR").series == ""
    assert extract_product_slots(greek, brand="ECOSTAR").guarded_facets.capacity == "1.5T"
    assert referee_match(greek, latin, brand="ECOSTAR").is_match


def test_series_inside_a_longer_hyphenated_code_is_covered() -> None:
    """``MSEZ2D-24HRFN1`` must be found inside ``MSEZ2D-24HRFN1-QCOW-B``."""
    target = "MIDEA SPLIT AC MSEZ2D-24HRFN1-QCOW-B EXTREME PLUS GREY"
    assert referee_match(target, target, brand="MIDEA").is_match


def test_series_truncated_by_noise_stripping_is_still_covered() -> None:
    """A long dash truncates the cleaned title; the raw title must be re-tested.

    ``clean_marketplace_noise`` cuts "EAF-05 Air Fryer - 4.5L Low-Fat ..." down to
    "EAF-05 Air Fryer", so the candidate loses its own series.  Without the
    raw-title re-test this exact title rejected itself.
    """
    target = "ELite EAF-05 Air Fryer \u2013 4.5L Low-Fat Digital Air Fryer"
    assert referee_match(target, target, brand="ELite").is_match


def test_three_way_variant_list_degrades_to_base_not_reject() -> None:
    """``GB/GR/GS`` is a real variant list; worst case is a cross-check, not a reject."""
    target = "HDR-TC2C1 GB/GR/GS"
    decision = referee_match(target, target)
    assert decision.usable, decision.reason


def test_model_code_glued_to_a_word_is_still_found() -> None:
    """``...Washing MachineDwt-1166`` must surface ``DWT-1166`` as the anchor."""
    listing = "Dawlance 11Kg Fully Automatic Top Load Washing MachineDwt-1166 - HUB"
    target = "Dawlance 11 KG DWT-1166 X ADS+ Top Load Fully Automatic Washing Machine"
    assert extract_product_slots(listing, brand="Dawlance").anchor.upper().endswith("DWT-1166")
    assert referee_match(extract_product_slots(target, brand="Dawlance"), listing,
                         brand="Dawlance").is_match


def test_paren_wrapped_model_is_matched_and_clean_capabilities() -> None:
    """``... 1.5 Ton (GS-18PITC12W-T3)`` must yield anchor ``GS-18PITC12W`` and no ``T3)``."""
    listing = "Gree Pular T3 Split Air Conditioner Cool Only 1.5 Ton (GS-18PITC12W-T3) - ISPK"
    slots = extract_product_slots(listing, brand="Gree")
    assert slots.anchor == "GS-18PITC12W"
    assert "T3)" not in slots.guarded_facets.capabilities
