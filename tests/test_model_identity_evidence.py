"""Real listing regressions and adversarial controls for product identity evidence."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pricing_engine.matcher import (
    MatchDecision,
    extract_product_slots,
    extract_search_query_and_model,
    referee_match,
)

CASES: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "fixtures" / "model_identity_regressions.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", CASES, ids=["iron", "washer", "ac", "mincer"])
def test_real_exact_models_survive_descriptive_differences(case: dict[str, Any]) -> None:
    for offer in case["offers"]:
        decision = referee_match(case["target"], offer["title"], brand=case["brand"])
        assert decision.is_match, (offer["title"], decision.reason)


@pytest.mark.parametrize("suffix", ["", "W", " W", "-W"])
def test_prefix_context_preserves_model_before_unit_classification(suffix: str) -> None:
    slots = extract_product_slots(f"Acme - Kitchen appliance AXMM - 6001{suffix}", "Acme")
    assert "6001" in slots.anchor
    assert "600" not in slots.series


@pytest.mark.parametrize("word", ["CASH", "IRON", "MEAT"])
def test_description_words_are_not_capabilities(word: str) -> None:
    slots = extract_product_slots(f"Acme AX-5432 Refrigerator {word}", "Acme")
    assert word not in slots.guarded_facets.capabilities


@pytest.mark.parametrize(
    ("suffix", "source"), [("", "sku"), (" Grey", "explicit"), (" (G)", "code")]
)
def test_color_evidence_distinguishes_model_inference_from_stated_color(
    suffix: str, source: str
) -> None:
    facets = extract_product_slots("Gree GS-18PITH17G-T3" + suffix, "Gree").guarded_facets
    assert facets.color_source == source


@pytest.mark.parametrize(("code", "expected"), [("G", True), ("B", False)])
def test_encoded_color_agreement_does_not_override_a_different_explicit_code(
    code: str, expected: bool
) -> None:
    decision = referee_match(CASES[2]["target"], f"Gree GS-18PITH17G-T3 ({code}) Pular AC", "Gree")
    assert decision.is_match is expected


@pytest.mark.parametrize(
    ("target", "candidate", "brand"),
    [
        (
            "Dawlance DWSI 2322 CX Steam Iron",
            "Dawlance DWSI 2322 CX Steam Iron Super Savings",
            "Dawlance",
        ),
        (
            "Gree GS-12AITH21W Inverter AC",
            "Gree GS-12AITH21W Inverter AC Black Friday Sale",
            "Gree",
        ),
        (
            "Haier HRF-538 Refrigerator",
            "Haier HRF-538 Refrigerator | Microwave specialists",
            "Haier",
        ),
        ("Haier HSU-19HFS Split AC", "Haier HSU-19HFS Split AC | Window AC specialists", "Haier"),
        ("Dawlance DWSI 2322 CX", "Efficient Steam Iron DWSI 2322 CX", "Dawlance"),
        (
            "Dawlance DWMM 6001 W 600 W Electric Meat Mincer",
            "Dawlance Meat Mincer DWMM - 6001W Efficient Kitchen Performance",
            "Dawlance",
        ),
        (
            "Acme AX42Y123W Steam appliance",
            "Acme AX42Y123W Steam appliance Premium PRO performance",
            "Acme",
        ),
    ],
)
def test_removed_prose_cannot_reenter_identity_guards(
    target: str, candidate: str, brand: str
) -> None:
    decision = referee_match(
        target,
        candidate,
        brand=brand,
        candidate_brand=brand if not candidate.startswith(brand) else "",
    )
    assert decision.is_match, decision.reason


@pytest.mark.parametrize(
    ("case_idx", "candidate"),
    [
        (0, "Dawlance DWSI 2323 CX Steam Iron"),
        (0, "Otherbrand DWSI 2322 CX Steam Iron"),
        (1, "Samsung WA80CK4240BW Washing Machine 8KG"),
        (1, "Samsung WA80CK4240BWRT Washing Machine 10KG"),
        (1, "Samsung WA80CK4240BWRT Non-Inverter Washing Machine 8KG"),
        (2, "Gree GS-18PITH17W-T3 Pular Inverter AC"),
        (2, "Gree GS-18PITH17G-T3 Pular Non-Inverter AC Grey"),
        (2, "Gree GS-18PITH17G-T3 Pular Inverter AC White"),
        (3, "Sogo JPN-6001 Meat Mincer"),
        (3, "Dawlance DWMM-6001-B Meat Mincer"),
    ],
)
def test_matching_fixes_keep_explicit_conflicts_blocked(case_idx: int, candidate: str) -> None:
    case = CASES[case_idx]
    decision = referee_match(case["target"], candidate, brand=case["brand"])
    assert not decision.is_match and not decision.is_base_match and decision.match_tier is None


def test_authoritative_marketplace_brand_cannot_be_overridden_by_shared_sku() -> None:
    from pricing_engine.scraper import _parse_offers_with_tiers

    case = CASES[0]
    offer = deepcopy(case["offers"][0])
    # Metadata is authoritative when the title does not explicitly identify a brand.
    offer["title"] = "Efficient Steam Iron DWSI 2322 CX"
    offer["brand"] = [{"title": "Otherbrand"}]
    parsed = _parse_offers_with_tiers(
        [offer], "DWSI-2322-CX", brand="Dawlance", target_desc=case["target"]
    )
    assert not parsed[0] and not parsed[1] and parsed[6] == 1


def test_brand_evidence_survives_scraping_for_learning() -> None:
    from pricing_engine.scraper import _parse_offers_with_tiers

    case = CASES[0]
    raw = deepcopy(case["offers"][0])
    raw.update(title="Efficient Steam Iron DWSI 2322 CX", brand=[{"title": "Dawlance"}])
    offers = _parse_offers_with_tiers(
        [raw], "DWSI-2322-CX", brand="Dawlance", target_desc=case["target"]
    )[0]
    assert len(offers) == 1
    offer = offers[0]
    decision = referee_match(
        extract_product_slots(case["target"], case["brand"]),
        offer.raw_title,
        brand=case["brand"],
        candidate_brand=offer.brand_name,
    )
    assert decision.is_match


def test_foreign_brand_before_product_prose_is_still_rejected() -> None:
    target = "Acme AX-5432 CX Steam Iron"
    decision = referee_match(target, "Otherbrand Efficient Steam Iron AX-5432 CX", "Acme")
    assert not decision.is_match and not decision.is_base_match


def test_legacy_interface_reuses_separator_and_marketing_normalization() -> None:
    from pricing_engine.matcher import is_strict_model_match

    for case in CASES:
        _, model = extract_search_query_and_model(case["target"], case["brand"])
        assert all(
            is_strict_model_match(offer["title"], model, case["brand"]) for offer in case["offers"]
        )


def test_diagnostic_classification_does_not_depend_on_reason_wording() -> None:
    from pricing_engine.digi_discovery import is_definitive_digi_rejection

    decision = referee_match("Haier HWM-120-826S6", "Haier HWM-100-826S6", "Haier")
    assert decision.reason_code == "MODEL_CONFLICT"
    decision.reason = "Human-readable explanation changed"
    assert is_definitive_digi_rejection(decision)
    assert not is_definitive_digi_rejection(MatchDecision(False, "New marketing mismatch"))


def test_market_variant_metadata_survives_readable_reason_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pricing_engine.scraper as scraper

    decision = referee_match("Dawlance DWT-260", "Dawlance DWT-260 S", "Dawlance")
    assert decision.is_base_match
    decision.reason = "Localized compatibility explanation"
    monkeypatch.setattr(scraper, "referee_match", lambda *args, **kwargs: decision)
    raw = {"title": "Dawlance DWT-260 S", "variant_detail": {"discounted_price": "80000"}}
    parsed = scraper._parse_offers_with_tiers([raw], "DWT-260", brand="Dawlance")
    assert parsed[1][0].detected_variant == "S"


def test_zero_offer_summary_shows_structured_rejection_evidence() -> None:
    from pricing_engine.digi_discovery import format_digimall_summary
    from pricing_engine.models import RejectedCandidate, ScrapeResult

    result = ScrapeResult(
        coverage_status="COMPLETE",
        rejected_count=1,
        rejected_examples=[
            RejectedCandidate(
                "Acme AX-5433", "AX-5433", "MODEL_CONFLICT", "Anchor model mismatch", "AX-5432"
            )
        ],
    )
    summary = format_digimall_summary(result)
    assert "MODEL_CONFLICT" in summary and "AX-5433" in summary


@pytest.mark.parametrize("platform", ["alfa", "digi", "all"])
def test_matching_policy_invalidates_all_platform_checkpoints(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    import pricing_engine.checkpoint as checkpoint

    row = {"Brand": "Acme", "Name": "Acme AX-5432", "Net Price": 5000}
    old = checkpoint.compute_row_fingerprint(row, platform=platform)
    monkeypatch.setattr(checkpoint, "MATCHER_POLICY_VERSION", "next-evidence-policy")
    assert checkpoint.compute_row_fingerprint(row, platform=platform) != old


@pytest.mark.parametrize("case", CASES, ids=["iron", "washer", "ac", "mincer"])
@pytest.mark.parametrize("platform", ["alfa", "digi"])
def test_real_payloads_reach_market_range_and_pricing(case: dict[str, Any], platform: str) -> None:
    async def run() -> None:
        from pricing_engine.calculator import calculate_floors
        from pricing_engine.evaluator import (
            evaluate_alfa_pricing,
            evaluate_digi_pricing,
            evaluate_market_range,
        )
        from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall, scrape_digimall

        clear_scraper_cache()
        items = deepcopy(case["offers"])
        sold = deepcopy(items[0])
        sold.update(id="sold-only", sold_out=True, vendor={"name": "Sold-only seller"})
        sold["variant_detail"] = {"discounted_price": "1"}
        wrong = deepcopy(items[0])
        wrong.update(
            id="wrong-brand", title="Unrelated ZZ-9999 appliance", vendor={"name": "Wrong seller"}
        )
        wrong["variant_detail"] = {"discounted_price": "2"}
        items.extend([sold, wrong, deepcopy(items[0])])
        session = AsyncMock()
        response = MagicMock(status_code=200)
        response.json.return_value = {"results": items, "count": len(items)}
        session.get.return_value = response
        _, model = extract_search_query_and_model(case["target"], case["brand"])
        scraper = scrape_alfamall if platform == "alfa" else scrape_digimall
        result = await scraper(
            session, model, model, target_desc=case["target"], brand=case["brand"]
        )
        assert result.offers
        market = evaluate_market_range(result.offers)
        assert market.min_price is not None and market.min_price > 2
        assert all(offer.vendor_name != "Wrong seller" for offer in result.offers)
        assert any(example.title == wrong["title"] for example in result.rejected_examples)
        assert all(
            example.reason_code != "UNKNOWN" and example.query
            for example in result.rejected_examples
        )
        assert any(offer.duplicate_count >= 2 for offer in result.offers)
        if case["brand"] == "Gree":
            assert len(result.own_offers) == 1
            assert all("Kia" not in offer.vendor_name for offer in result.offers)
        costs = {"Dawlance": 8200, "Samsung": 83500, "Gree": 161500}
        floors = calculate_floors(costs[case["brand"]])
        evaluator = evaluate_alfa_pricing if platform == "alfa" else evaluate_digi_pricing
        pricing = evaluator(floors, result)
        assert pricing.final_price is not None
        assert "Monopoly" not in pricing.status
        assert pricing.final_price >= (
            floors.floor_alfa if platform == "alfa" else floors.floor_digi_8
        )

    asyncio.run(run())
