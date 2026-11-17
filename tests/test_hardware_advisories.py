"""Advisory evidence follows the selected offer without changing match priority."""

from collections.abc import Callable
from dataclasses import replace
from itertools import permutations
from typing import Any

import pytest

from pricing_engine.calculator import calculate_floors
from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.matcher import referee_match
from pricing_engine.models import (
    DISCOVERY_CANDIDATES_REJECTED,
    DISCOVERY_PAGINATION_INCOMPLETE,
    STATUS_CANDIDATES_REJECTED,
    STATUS_INCOMPLETE_DISCOVERY,
    STATUS_SERVER_DOWN,
    CostFloors,
    PlatformPricingResult,
    ScrapeResult,
    has_compatibility_or_fallback_notice,
)
from pricing_engine.offer_processing import finalize_offers, parse_offers_with_tiers

Evaluator = Callable[[CostFloors, ScrapeResult], PlatformPricingResult]
TARGET = "Dawlance DWT-1165 Washing Machine"
NOTICE = "⚠️ [CROSS-CHECK NOTICE: Market listing includes 'ECO' not specified in target catalog]"


def _raw(title: str, price: int, vendor: str = "External Seller") -> dict[str, Any]:
    return {
        "title": title,
        "vendor": {"name": vendor},
        "sold_out": False,
        "variant_detail": {"discounted_price": str(price)},
    }


def _finalize(
    raw_items: list[dict[str, Any]],
    target: str = TARGET,
    model: str = "DWT-1165",
    brand: str = "Dawlance",
    floor_price: float | None = None,
) -> ScrapeResult:
    exact, base, sibling, modifier, own, count, rejected, reasons, suspicious, extended = (
        parse_offers_with_tiers(raw_items, model, brand, target)
    )
    return finalize_offers(
        ScrapeResult(
            offers=exact,
            base_offers=base,
            sibling_offers=sibling,
            active_modifier_fallback=modifier,
            own_offers=own,
            raw_candidate_count=count,
            rejected_count=rejected,
            rejection_reasons=reasons,
            suspicious_rejected_count=suspicious,
            extended_model_designation=extended,
        ),
        model,
        floor_price=floor_price,
    )


@pytest.mark.parametrize("designation", ["ECO", "ET", "XYQ"])
def test_candidate_only_designation_is_exact_and_advisory_only(designation: str) -> None:
    decision = referee_match(TARGET, f"Dawlance DWT-1165 {designation} Washing Machine", "Dawlance")

    assert decision.is_match
    assert decision.match_tier == 1
    assert not decision.is_base_match
    assert decision.missing_modifier is None
    assert decision.detected_variant is None
    assert decision.compatibility_notice == NOTICE.replace("ECO", designation)


def test_catalog_declared_designation_omission_remains_a_base_fallback() -> None:
    decision = referee_match("Dawlance DWT-1165 ECO Washing Machine", TARGET, "Dawlance")

    assert decision.is_base_match
    assert decision.match_tier == 2
    assert "ECO" in (decision.missing_modifier or "")
    assert decision.compatibility_notice
    assert has_compatibility_or_fallback_notice(decision.compatibility_notice)


@pytest.mark.parametrize("prose", ["4-Way", "WiFi", "Non WiFi", "IOT", "Smart", "Non Smart"])
def test_count_and_disabled_connectivity_prose_do_not_generate_advisories(prose: str) -> None:
    decision = referee_match(TARGET, f"{TARGET} {prose}", "Dawlance")

    assert decision.is_match and decision.match_tier == 1
    assert not decision.is_base_match
    assert decision.missing_modifier is None
    assert decision.detected_variant is None
    assert decision.compatibility_notice is None


@pytest.mark.parametrize("evaluator", [evaluate_alfa_pricing, evaluate_digi_pricing])
@pytest.mark.parametrize("reverse_order", [False, True])
def test_cheaper_warned_exact_offer_is_selected_and_notice_propagates_once(
    evaluator: Evaluator, reverse_order: bool
) -> None:
    raw = [
        _raw("Dawlance DWT-1165 ECO Washing Machine", 85000, "Warned Seller"),
        _raw(TARGET, 88000, "Clean Seller"),
    ]
    if reverse_order:
        raw.reverse()
    scrape = _finalize(raw)
    floors = calculate_floors(72000)
    result = evaluator(floors, scrape)
    clean_control = evaluator(
        floors,
        _finalize(
            [
                _raw(TARGET, 85000, "Warned Seller"),
                _raw(TARGET, 88000, "Clean Seller"),
            ]
        ),
    )

    assert {(o.vendor_name, o.price, o.match_tier) for o in scrape.offers} == {
        ("Warned Seller", 85000, 1),
        ("Clean Seller", 88000, 1),
    }
    assert not scrape.base_offers and not scrape.sibling_offers
    assert scrape.active_modifier_fallback is None
    assert scrape.compatibility_notice == NOTICE
    assert result.min_price == 85000
    assert result.final_price is not None and result.final_price < 85000
    assert result.final_price == clean_control.final_price
    assert result.status == clean_control.status
    assert result.real_profit == clean_control.real_profit
    assert result.compatibility_notice == NOTICE
    assert result.reason.count(NOTICE) == 1
    assert result.reason.count("CROSS-CHECK NOTICE") == 1
    assert has_compatibility_or_fallback_notice(result.reason)


@pytest.mark.parametrize("evaluator", [evaluate_alfa_pricing, evaluate_digi_pricing])
@pytest.mark.parametrize("reverse_order", [False, True])
def test_unselected_costlier_advisory_does_not_contaminate_clean_winner(
    evaluator: Evaluator, reverse_order: bool
) -> None:
    raw = [
        _raw("Dawlance DWT-1165 ECO Washing Machine", 88000, "Warned Seller"),
        _raw(TARGET, 85000, "Clean Seller"),
    ]
    if reverse_order:
        raw.reverse()
    scrape = _finalize(raw)
    result = evaluator(calculate_floors(72000), scrape)

    assert len(scrape.offers) == 2
    assert any(o.compatibility_notice == NOTICE for o in scrape.offers)
    assert scrape.compatibility_notice is None
    assert scrape.active_modifier_fallback is None
    assert result.min_price == 85000
    assert result.compatibility_notice is None
    assert not has_compatibility_or_fallback_notice(result.reason)


@pytest.mark.parametrize("evaluator", [evaluate_alfa_pricing, evaluate_digi_pricing])
def test_duplicate_warned_payloads_keep_one_offer_and_one_notice(evaluator: Evaluator) -> None:
    raw = _raw("Dawlance DWT-1165 ECO Washing Machine", 85000)
    scrape = _finalize([raw, raw.copy()])
    result = evaluator(calculate_floors(72000), scrape)

    assert len(scrape.offers) == 1
    assert scrape.offers[0].duplicate_count == 2
    assert scrape.offers[0].match_tier == 1
    assert result.compatibility_notice == NOTICE
    assert result.reason.count("CROSS-CHECK NOTICE") == 1


@pytest.mark.parametrize("evaluator", [evaluate_alfa_pricing, evaluate_digi_pricing])
def test_duplicate_clean_and_advisory_spellings_choose_clean_evidence(evaluator: Evaluator) -> None:
    raw = [
        _raw("Dawlance DWT-1165 ECO Washing Machine", 85000),
        _raw(TARGET, 85000),
    ]
    for order in permutations(raw):
        scrape = _finalize(list(order))
        result = evaluator(calculate_floors(72000), scrape)

        assert len(scrape.offers) == 1
        assert scrape.offers[0].duplicate_count == 2
        assert scrape.offers[0].match_tier == 1
        assert scrape.offers[0].compatibility_notice is None
        assert scrape.compatibility_notice is None
        assert result.compatibility_notice is None
        assert not has_compatibility_or_fallback_notice(result.reason)


@pytest.mark.parametrize("evaluator", [evaluate_alfa_pricing, evaluate_digi_pricing])
def test_sold_out_advisory_cannot_contaminate_clean_winner(evaluator: Evaluator) -> None:
    sold_out = _raw("Dawlance DWT-1165 ECO Washing Machine", 84000, "Sold Out Seller")
    sold_out["sold_out"] = True
    scrape = _finalize([sold_out, _raw(TARGET, 85000, "Clean Seller")])
    result = evaluator(calculate_floors(72000), scrape)

    assert len(scrape.offers) == 2
    assert any(o.is_sold_out and o.compatibility_notice == NOTICE for o in scrape.offers)
    assert scrape.compatibility_notice is None
    assert result.min_price == 85000
    assert result.compatibility_notice is None
    assert not has_compatibility_or_fallback_notice(result.reason)


@pytest.mark.parametrize("evaluator", [evaluate_alfa_pricing, evaluate_digi_pricing])
def test_subfloor_warned_offer_does_not_override_viable_clean_reference(
    evaluator: Evaluator,
) -> None:
    floors = calculate_floors(72000)
    scrape = _finalize(
        [
            _raw("Dawlance DWT-1165 ECO Washing Machine", 1000, "Loss Seller"),
            _raw(TARGET, 85000, "Viable Seller"),
        ]
    )
    result = evaluator(floors, scrape)

    # Finalization without a floor can retain a different provisional notice;
    # evaluation must resolve metadata from its own viable reference offer.
    assert scrape.compatibility_notice == NOTICE
    assert result.final_price is not None and 1000 < result.final_price < 85000
    assert result.compatibility_notice is None
    assert not has_compatibility_or_fallback_notice(result.reason)


@pytest.mark.parametrize("evaluator", [evaluate_alfa_pricing, evaluate_digi_pricing])
def test_warned_exact_keeps_priority_over_real_base_and_sibling(evaluator: Evaluator) -> None:
    target = "Haier 18HFPCA 1.5 Ton Inverter AC"
    raw = [
        _raw("Haier 18HFPCA ECO 1.5 Ton Inverter AC", 148000, "Exact Seller"),
        _raw("Haier HSU-18HFP 1.5 Ton Inverter AC", 145000, "Base Seller"),
        _raw("Haier HSU-18HFPE 1.5 Ton Inverter AC", 146000, "Sibling Seller"),
    ]
    for order in permutations(raw):
        scrape = _finalize(list(order), target, "18HFPCA", "Haier")
        result = evaluator(calculate_floors(117500), scrape)
        assert [(o.vendor_name, o.match_tier) for o in scrape.offers] == [("Exact Seller", 1)]
        assert [(o.vendor_name, o.match_tier) for o in scrape.base_offers] == [("Base Seller", 2)]
        assert [(o.vendor_name, o.match_tier) for o in scrape.sibling_offers] == [
            ("Sibling Seller", 3)
        ]
        assert "Exact Seller" in result.reason
        assert result.min_price == 148000
        assert result.compatibility_notice == NOTICE
        assert result.reason.count("CROSS-CHECK NOTICE") == 1
        assert "FALLBACK MODEL" not in result.reason


@pytest.mark.parametrize("evaluator", [evaluate_alfa_pricing, evaluate_digi_pricing])
@pytest.mark.parametrize(
    ("listing", "tier", "marker"),
    [
        ("HSU-18HFP", 2, "[FALLBACK MODEL:"),
        ("HSU-18HFPE", 3, "[SIBLING SUB-MODEL FALLBACK:"),
        ("18HFPCA T3", 1, "[OPTIONAL SPECIFICATION:"),
    ],
)
def test_existing_base_sibling_and_optional_t3_notices_are_preserved(
    evaluator: Evaluator, listing: str, tier: int, marker: str
) -> None:
    scrape = _finalize(
        [_raw(f"Haier {listing} 1.5 Ton Inverter AC", 148000)],
        "Haier 18HFPCA 1.5 Ton Inverter AC",
        "18HFPCA",
        "Haier",
    )
    result = evaluator(calculate_floors(117500), scrape)

    assert len(scrape.offers) == 1 and scrape.offers[0].match_tier == tier
    assert result.compatibility_notice == scrape.offers[0].compatibility_notice
    assert marker in (result.compatibility_notice or "")
    assert result.reason.count(marker) == 1
    assert has_compatibility_or_fallback_notice(result.reason)


@pytest.mark.parametrize("evaluator", [evaluate_alfa_pricing, evaluate_digi_pricing])
@pytest.mark.parametrize(
    ("scrape", "status"),
    [
        (ScrapeResult(), "Monopoly Win"),
        (ScrapeResult(is_success=False, status_code=503), STATUS_SERVER_DOWN),
        (
            ScrapeResult(discovery_status=DISCOVERY_PAGINATION_INCOMPLETE),
            STATUS_INCOMPLETE_DISCOVERY,
        ),
        (ScrapeResult(discovery_status=DISCOVERY_CANDIDATES_REJECTED), STATUS_CANDIDATES_REJECTED),
    ],
)
def test_nonreference_statuses_suppress_stale_advisory(
    evaluator: Evaluator, scrape: ScrapeResult, status: str
) -> None:
    result = evaluator(calculate_floors(72000), replace(scrape, compatibility_notice=NOTICE))

    assert result.status == status
    assert result.compatibility_notice is None
    assert not has_compatibility_or_fallback_notice(result.reason)
