"""Series matching must reuse guards without pretending its SKU was verified."""

from dataclasses import asdict
from itertools import permutations

import pytest

from pricing_engine.matcher import extract_product_slots
from pricing_engine.series_fallback import build_series_search, referee_series_match


@pytest.mark.parametrize("unit", ["1T", "1.0T", "1 Ton"])
def test_supported_tonnage_aliases_never_become_series_words(unit: str) -> None:
    search = build_series_search(f"Acme AX-900 Aurora Series {unit} Split AC", "Acme")
    assert search is not None
    decision = referee_series_match(search, f"Acme Aurora {unit} Split AC", "Acme")
    assert decision.is_base_match, decision.reason


def test_model_basis_survives_same_seller_price_series_duplicate() -> None:
    from pricing_engine.models import ScrapedOffer
    from pricing_engine.scraper import deduplicate_offers

    model = ScrapedOffer("Seller", 100, False, "Model", match_tier=2, missing_modifier="suffix")
    series = ScrapedOffer("Seller", 100, False, "Series", match_tier=2, match_basis="series")
    for ordering in permutations([model, series]):
        retained = deduplicate_offers(list(ordering))
        assert retained[0].match_basis == "model"


@pytest.mark.parametrize("left,right", [("Clear Lid", "Glass Lid"), ("Glass Lid", "Clear Lid")])
def test_series_reuses_explicit_lid_conflict_guard(left: str, right: str) -> None:
    target = f"Acme AX-1200 Aurora Series 8 KG Washing Machine {left}"
    decision = referee_series_match(target, f"Acme Aurora 8 KG Washing Machine {right}", "Acme")
    assert not decision.is_base_match, decision.reason


def test_series_reports_omitted_lid() -> None:
    decision = referee_series_match(
        "Acme AX-1200 Aurora Series 8 KG Washing Machine Clear Lid",
        "Acme Aurora 8 KG Washing Machine",
        "Acme",
    )
    assert decision.is_base_match
    assert "Clear Lid" in (decision.compatibility_notice or "")


def test_sold_out_model_does_not_erase_available_series_duplicate() -> None:
    from pricing_engine.models import ScrapedOffer
    from pricing_engine.scraper import deduplicate_offers

    model = ScrapedOffer("Seller", 100, True, "Model", match_tier=2)
    series = ScrapedOffer("Seller", 100, False, "Series", match_tier=2, match_basis="series")
    for ordering in permutations([model, series]):
        retained = deduplicate_offers(list(ordering))
        assert not retained[0].is_sold_out
        assert retained[0].match_basis == "series"


TARGET = (
    "Midea MSEZ1B-12HRFN1-QC2 1 Ton Titan Series Inverter Wall Mounted Split Air Conditioner White"
)


@pytest.mark.parametrize("variant", ["", "Pro", "Plus", "Ultra", "Next"])
def test_explicit_different_sku_cannot_enter_series_fallback(variant: str) -> None:
    title = f"Midea Titan {variant} 1 Ton Inverter Split AC MSEZ1D-12HRFN1-QC2 White"
    decision = referee_series_match(TARGET, title, "Midea")
    assert not decision.is_base_match and decision.match_tier is None


@pytest.mark.parametrize("extra", ["Pro", "Plus", "Next", "Ultra"])
def test_series_identity_is_complete_not_a_subset(extra: str) -> None:
    decision = referee_series_match(
        TARGET, f"Midea Titan {extra} 1 Ton Inverter Split AC White", "Midea"
    )
    assert not decision.is_base_match
    assert decision.reason_code == "SERIES_CONFLICT"


def test_series_preserves_original_target_and_warns_missing_color() -> None:
    search = build_series_search(TARGET, "Midea")
    assert search is not None
    before = asdict(search.target)
    decision = referee_series_match(search, "Midea Titan 1 Ton Split AC", "Midea")
    assert decision.is_base_match and decision.match_tier == 2
    assert decision.target_slots is search.target
    assert asdict(search.target) == before
    assert decision.match_basis == "series"
    assert "color" in (decision.compatibility_notice or "").lower()


def test_series_requires_positive_product_family_evidence() -> None:
    decision = referee_series_match(TARGET, "Midea Titan 1 Ton White", "Midea")
    assert not decision.is_base_match
    assert decision.reason_code == "MISSING_IDENTITY"


@pytest.mark.parametrize("brand,prefix", [("Acme", "AX"), ("Novus", "NV")])
def test_model_dependent_finish_omission_never_becomes_inherent_in_series(
    brand: str, prefix: str
) -> None:
    target = f"{brand} {prefix}-91999 8 CFT Aurora Series Glass Door Refrigerator"
    decision = referee_series_match(target, f"{brand} Aurora 8 CFT Refrigerator", brand)
    assert decision.is_base_match
    assert "GD" in (decision.compatibility_notice or "")
    assert decision.target_slots == extract_product_slots(target, brand)
