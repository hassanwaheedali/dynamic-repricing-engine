"""Base-model search tiers + collision-beats-omission doctrine.

Strict search engines only answer short human-like queries, so the waterfall
must always include the base model (series blob with aux tags stripped, and
the prefix cut at the first capacity-like token).  Category-2 then decides on
what is retrieved: tag found -> EXACT, tag omitted -> BASE + notice.

And a declared conflict on any facet must REJECT even when another facet is
merely omitted ("collisions beat omissions").
"""

from pricing_engine.matcher import (
    TIER_BASE,
    TIER_EXACT,
    TIER_REJECT,
    generate_search_patterns,
    referee_match,
)


def test_series_capacity_models_emit_tag_stripped_base() -> None:
    p = generate_search_patterns("15 Sprinter T3", "Dawlance")
    assert "15 Sprinter" in p["tier_2"]
    assert "Dawlance 15 Sprinter" in p["tier_1"]


def test_capacity_cut_prefix_base_for_letter_stem_models() -> None:
    p = generate_search_patterns("PINV 12K Turbo Ultimate T3 12", "PEL")
    assert "PINV 12K" in p["tier_2"]
    assert "PEL PINV 12K" in p["tier_1"]


def test_category2_on_retrieved_base_listing() -> None:
    omitted = referee_match(
        "Dawlance 15 Sprinter T3", "Dawlance 15 Sprinter AC", "Dawlance"
    )
    assert omitted.tier == TIER_BASE and omitted.usable

    exact = referee_match(
        "Dawlance 15 Sprinter T3", "Dawlance 15 Sprinter T3 AC", "Dawlance"
    )
    assert exact.tier == TIER_EXACT


def test_collision_beats_omission() -> None:
    # Target: H&C + inverter.  Listing: COOL ONLY and no inverter word.
    # The declared operating-mode conflict must REJECT; the inverter omission
    # (soft BASE) must not mask it.
    decision = referee_match(
        "PEL 1 Ton PINV 12K Turbo Ultimate T3 (H&C) Inverter Air Conditioner",
        "PEL PINV 12K COOL BREEZE COOL ONLY WITH FREE INSTALLATION UE002",
        "PEL",
    )
    assert decision.tier == TIER_REJECT
    assert "Operating mode collision" in decision.reason
    assert not decision.usable
