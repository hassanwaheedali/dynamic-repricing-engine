"""Regression tests for the base+variant -> base-model fallback contract.

Each test is pinned to a root cause documented in
``docs/validation-report-matcher-refactor.md`` (RC-1 ... RC-5).  The canonical
failing product is ``Dawlance 10 KG DWT-1016 INV PRIMA``, whose real marketplace
listing appears verbatim in ``tests/fixtures/selected_100_stress_products.csv``.
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pandas as pd
from rich.console import Console

import pricing_engine.range_pipeline as rp
from pricing_engine.matcher import (
    TIER_BASE,
    TIER_EXACT,
    TIER_REJECT,
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    referee_match,
)
from pricing_engine.models import ScrapedOffer, ScrapeResult

TARGET = "Dawlance 10 KG DWT-1016 INV PRIMA Top Load Fully Automatic Washing Machine"
# Verbatim from tests/fixtures/selected_100_stress_products.csv line 21.
REAL_LISTING = (
    "Dawlance DWT 1016 INV PRIMA 10 Kg Dark Grey Prima Series DDM Inverter Washing Machine"
)


# --------------------------------------------------------------------------- RC-1


def test_rc1_category_phrase_never_enters_series_slot() -> None:
    """'Fully Automatic' is a category phrase, not a series name."""
    slots = extract_product_slots(TARGET, brand="Dawlance")
    upper = slots.series.upper()
    assert "PRIMA" in upper
    assert "FULLY" not in upper and "AUTOMATIC" not in upper


def test_rc1_semi_automatic_and_top_load_also_stripped() -> None:
    for phrase in (
        "Semi Automatic Washing Machine",
        "Top Load Fully Automatic Washing Machine",
        "Automatic Washing Machine",
    ):
        slots = extract_product_slots(f"Dawlance DW-6550 C 8 KG Twin Tub {phrase}")
        upper = slots.series.upper()
        assert "AUTOMATIC" not in upper, phrase
        assert "TOP" not in upper, phrase


def test_rc1_model_extraction_not_polluted_by_category_phrase() -> None:
    _, model = extract_search_query_and_model(
        "Dawlance Top Load Fully Automatic Washing Machine (DWT-1166-X-ADS+)"
    )
    assert model.startswith("DWT-1166")
    assert "FULLY" not in model.upper()


def test_rc1_real_listing_is_an_exact_match() -> None:
    """The headline failure: the vendor's own listing must match the catalog target."""
    decision = referee_match(TARGET, REAL_LISTING, brand="Dawlance")
    assert decision.tier is TIER_EXACT
    assert decision.is_match is True
    assert decision.is_base_match is False


def test_rc1_fuller_vendor_sku_also_matches() -> None:
    """The stock sheet names the same machine 1016DDM; that SKU must match too."""
    decision = referee_match(
        TARGET, "Dawlance DWT-1016DDM INV PRIMA 10 KG Washing Machine", brand="Dawlance"
    )
    assert decision.tier is TIER_EXACT


# --------------------------------------------------------------------------- RC-2


def test_rc2_minibar_prefix_stem_is_not_glued_together() -> None:
    """``DMB 4467 SD`` must stay three tokens -- gluing it produced ``DMB-4467SD``."""
    _, model = extract_search_query_and_model("DAWLANCE DMB 4467 SD MINI BAR", brand="Dawlance")
    assert model.split() == ["4467", "SD"]
    patterns = generate_search_patterns("DAWLANCE DMB 4467 SD MINI BAR", brand="Dawlance")
    assert any("Dawlance 4467" in p for p in patterns["tier_1"])


def test_rc2_empty_model_never_returned() -> None:
    """A title that is entirely category words must not yield an empty query."""
    query, model = extract_search_query_and_model(
        "DAWLANCE 9KG AUTOMATIC TOP LOAD WASHING MACHINE", brand="Dawlance"
    )
    assert query.strip() and model.strip()


# --------------------------------------------------------------------------- RC-3


def test_rc3_distant_pure_alpha_code_is_not_a_capability() -> None:
    """``... Prima Series DDM ...`` -- DDM sits behind the series name, so it is
    part of the vendor's model designation, not an extra hardware capability."""
    slots = extract_product_slots(REAL_LISTING, brand="Dawlance")
    assert "DDM" not in slots.guarded_facets.capabilities


def test_rc3_contiguous_variant_code_is_still_guarded() -> None:
    """Codes in the post-model run stay Category-2 capabilities (variant protection)."""
    assert "ES" in extract_product_slots(
        "Dawlance DWT-11467 ES Automatic Washing Machine", brand="Dawlance"
    ).guarded_facets.capabilities
    assert "IG" in extract_product_slots("HDF 175 INV / IG").guarded_facets.capabilities


def test_rc3_digit_bearing_codes_guarded_anywhere() -> None:
    """T3 / ES8 / S6 are unambiguous identifiers and are honoured wherever they appear."""
    slots = extract_product_slots("Dawlance Magna Inverter AC 1.5 Ton T3", brand="Dawlance")
    assert "T3" in slots.guarded_facets.capabilities


# --------------------------------------------------------------------------- RC-4


def test_rc4_omitted_series_falls_back_to_base_model() -> None:
    decision = referee_match(
        "Haier HRF-216 EBD 8 Cu Ft Metallic Grey E-Star Non-Inverter Refrigerator",
        "Haier HRF-216 8 Cu Ft Refrigerator",
        brand="Haier",
    )
    assert decision.tier is TIER_BASE
    assert decision.is_match is False
    assert decision.is_base_match is True
    assert decision.missing_modifier
    assert "Missing required series" in decision.reason


def test_rc4_capability_omission_also_falls_back() -> None:
    """The same BASE verdict reached through the capability slot instead of series."""
    decision = referee_match(
        "Haier HRF-216 EBS 8 Cu Ft Silver E-Star Refrigerator",
        "Haier HRF-216 8 Cu Ft Refrigerator",
        brand="Haier",
    )
    assert decision.tier is TIER_BASE
    assert decision.missing_modifier == "EBS"
    assert "Hardware capability omitted" in decision.reason


def test_rc4_conflicting_series_is_still_a_hard_reject() -> None:
    decision = referee_match(
        "9173 WB Chrome FH",
        "Dawlance 9173 12 Cu Ft Graze+ Gem Black Glass Refrigerator",
        brand="Dawlance",
    )
    assert decision.tier is TIER_REJECT
    assert decision.is_base_match is False


def test_rc4_soft_styling_optionality_still_exact() -> None:
    """Unique 4-digit stems tolerate a seller dropping soft trim (Chrome FH)."""
    decision = referee_match(
        "9173 WB Chrome FH", "Dawlance 9173WB 12 Cu Ft Coral Red Refrigerator", brand="Dawlance"
    )
    assert decision.tier is TIER_EXACT


def test_rc4_inverter_omission_reports_uppercase_modifier() -> None:
    decision = referee_match(
        TARGET, "Dawlance DWT 1016 10 Kg Top Load Washing Machine", brand="Dawlance"
    )
    assert decision.tier is TIER_BASE
    assert decision.missing_modifier == "INVERTER"


def test_verdict_tier_vocabulary_is_consistent() -> None:
    exact = referee_match(TARGET, REAL_LISTING, brand="Dawlance")
    base = referee_match(
        TARGET, "Dawlance DWT 1016 10 Kg Top Load Washing Machine", brand="Dawlance"
    )
    reject = referee_match(
        "9173 WB Chrome FH", "Dawlance 9173 12 Cu Ft Graze+ Refrigerator", brand="Dawlance"
    )
    assert (exact.tier, base.tier, reject.tier) == (TIER_EXACT, TIER_BASE, TIER_REJECT)
    assert exact.usable and base.usable and not reject.usable


# --------------------------------------------------------------------------- RC-5


def _offer(vendor: str, price: float) -> ScrapedOffer:
    return ScrapedOffer(vendor_name=vendor, price=price, is_sold_out=False, raw_title="t")


def _base_result(modifier: str, price: float) -> ScrapeResult:
    offer = _offer("Base Vendor", price)
    return ScrapeResult(
        offers=[offer],
        base_offers=[offer],
        active_modifier_fallback=modifier,
        executed_queries=["Dawlance DWT-1016 INV"],
        matched_tier="tier_1",
        tier_summary={"tier_1": 1},
    )


def _run_range(tmp_path: Path, alfa: ScrapeResult, digi: ScrapeResult) -> tuple[pd.DataFrame, str]:
    catalog = tmp_path / "dwt1016.csv"
    catalog.write_text(f'Brand,Name\nDawlance,"{TARGET}"\n', encoding="utf-8")
    buf = io.StringIO()
    original = rp.console
    rp.console = Console(file=buf, force_terminal=True, width=200, legacy_windows=False)
    try:
        with (
            patch.object(rp, "scrape_alfamall", AsyncMock(return_value=alfa)),
            patch.object(rp, "scrape_digimall", AsyncMock(return_value=digi)),
            patch.object(rp, "RANGE_STAGGER_SECONDS", 0),
        ):
            df = asyncio.run(
                rp.run_range_pipeline(
                    catalog, concurrency=1, verbose=True, export_dir=tmp_path / "out"
                )
            )
    finally:
        rp.console = original
    return df, buf.getvalue()


def test_rc5_range_pipeline_prints_base_model_notice(tmp_path: Path) -> None:
    df, out = _run_range(
        tmp_path,
        _base_result("INVERTER", 108_000),
        ScrapeResult(offers=[_offer("V1", 111_999), _offer("V2", 122_699)]),
    )
    assert "CROSS-CHECK" in out
    assert "RANGED AGAINST BASE MODELS" in out
    assert "INVERTER" in out
    assert "base model offer" in out
    # The ranges themselves are unchanged.
    assert df.loc[0, "Minimum Price Alfa"] == 108_000
    assert (df.loc[0, "Minimum Price Digi"], df.loc[0, "Maximum Price Digi"]) == (111_999, 122_699)


def test_rc5_no_notice_when_every_match_is_exact(tmp_path: Path) -> None:
    exact = ScrapeResult(offers=[_offer("V1", 100)])
    _df, out = _run_range(tmp_path, exact, exact)
    assert "CROSS-CHECK" not in out
    assert "RANGED AGAINST BASE MODELS" not in out


def test_rc5_output_column_contract_unchanged(tmp_path: Path) -> None:
    """The notice is terminal-only: the CSV contract must not grow a column."""
    df, _ = _run_range(tmp_path, _base_result("INVERTER", 108_000), _base_result("INV", 120_000))
    assert list(df.columns)[0] == "S.NO"
    assert list(df.columns)[-2:] == ["Alfa Risk Alert", "Digi Risk Alert"]
    assert not any("fallback" in c.lower() for c in df.columns)


def test_rc5_detect_fallbacks_reads_scraper_metadata() -> None:
    found = rp._detect_fallbacks(_base_result("INVERTER", 1), ScrapeResult(offers=[_offer("a", 2)]))
    assert len(found) == 1
    assert (found[0].platform, found[0].modifier, found[0].offer_count) == ("AlfaMall", "INVERTER", 1)
    assert rp._detect_fallbacks([_offer("a", 1)], [_offer("b", 2)]) == ()
