"""Separate definitive incompatibility from uncertain identity in Digi discovery."""

from pricing_engine.digi_discovery import is_definitive_digi_rejection
from pricing_engine.matcher import MatchDecision, referee_match


def test_different_model_and_automation_are_definitive() -> None:
    target = "Haier HWM 130-196WB 13KG Twin Tub Semi Automatic Washing Machine White"
    for candidate in ("Haier Top Load Automatic Washing Machine HWM-130-688S8",
                      "Haier 12 KG Semi-Automatic Washing Machine HWM 130-1217"):
        decision = referee_match(target, candidate, brand="Haier")
        assert not decision.is_match
        assert is_definitive_digi_rejection(decision)


def test_uncertain_or_missing_identity_still_requires_review() -> None:
    assert not is_definitive_digi_rejection(MatchDecision(False, "Insufficient model identity"))
    assert not is_definitive_digi_rejection(MatchDecision(False, "Anchor model mismatch: no extracted identity"))


def test_missing_candidate_model_is_rejected_without_blocking_monopoly() -> None:
    target = "Haier HWM 150-826S6 (GC) 15KG Fully Automatic Top Load Washing Machine"
    decision = referee_match(target, "HAIER 15 kg Top Load Washing Machine", brand="Haier")
    assert not decision.is_match
    assert is_definitive_digi_rejection(decision)


def test_unidentified_listing_does_not_create_review_flag_or_prevent_monopoly() -> None:
    from pricing_engine.calculator import calculate_floors
    from pricing_engine.evaluator import evaluate_digi_pricing
    from pricing_engine.models import ScrapeResult
    from pricing_engine.scraper import _parse_offers_with_tiers
    target = "Haier HWM 150-826S6 (GC) 15KG Fully Automatic Top Load Washing Machine"
    raw = [{"title": "HAIER 15 kg Top Load Washing Machine", "sold_out": False,
            "vendor": {"name": "External seller"}, "variant_detail": {"discounted_price": "95000"}}]
    parsed = _parse_offers_with_tiers(raw, "150-826S6 GC", brand="Haier", target_desc=target,
                                    definitive_rejection=is_definitive_digi_rejection)
    assert parsed[8] == 0
    assert not parsed[0] and not parsed[1] and not parsed[2]
    floors = calculate_floors(82000)
    result = evaluate_digi_pricing(floors, ScrapeResult(coverage_status="CAPPED", rejected_count=1))
    assert result.final_price == evaluate_digi_pricing(floors, []).final_price
    assert "Monopoly" in result.status
