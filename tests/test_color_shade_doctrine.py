"""Two-layer colour doctrine: base family strict, shade modifier guarded.

* base families differ                 -> REJECT
* same base, both shades, different    -> REJECT  (Diamond Red vs Ruby Red)
* same base, listing omits the shade   -> BASE usable + cross-check notice
* fully equal colours                  -> EXACT

The shade is read structurally (word in front of the matched base colour, or
the prefix of a multi-word alias like MILKY WHITE) -- no per-product lists --
and it can never leak into the series slot ("Smoke" must not become a
required series token that hard-rejects plain "Purple" listings).
"""

from pricing_engine.matcher import (
    TIER_BASE,
    TIER_EXACT,
    TIER_REJECT,
    extract_product_slots,
    referee_match,
)


def test_shade_omission_is_usable_base_not_reject() -> None:
    decision = referee_match(
        "Orient Crystal 3 Smoke Purple",
        "ORIENT Crystal 3 Taps Purple Glass Door Water Dispensers_021",
        "Orient",
    )
    assert decision.tier == TIER_BASE
    assert decision.usable
    assert "Color shade omitted" in decision.reason


def test_shade_never_leaks_into_series() -> None:
    slots = extract_product_slots("Orient Crystal 3 Smoke Purple", "Orient")
    assert slots.guarded_facets.color_shade == "SMOKE"
    assert "SMOKE" not in (slots.series or "").upper()


def test_different_declared_shades_reject() -> None:
    decision = referee_match(
        "Dawlance Refrigerator Diamond Red 18AITH",
        "Dawlance Refrigerator Ruby Red 18AITH",
        "Dawlance",
    )
    assert decision.tier == TIER_REJECT
    assert "Color shade collision" in decision.reason
    assert not decision.usable


def test_multi_word_aliases_decompose_into_shade() -> None:
    omit = referee_match(
        "Dawlance HRF-216 Milky White Refrigerator",
        "Dawlance HRF-216 White Refrigerator",
        "Dawlance",
    )
    assert omit.tier == TIER_BASE and omit.usable

    clash = referee_match(
        "Dawlance HRF-216 Pearl White Refrigerator",
        "Dawlance HRF-216 Milky White Refrigerator",
        "Dawlance",
    )
    assert clash.tier == TIER_REJECT
    assert "Color shade collision" in clash.reason

    same = referee_match(
        "Dawlance HRF-216 Milky White Refrigerator",
        "Dawlance HRF-216 Milky White Fridge",
        "Dawlance",
    )
    assert same.tier == TIER_EXACT


def test_base_family_mismatch_still_rejects() -> None:
    decision = referee_match(
        "Gree GS-12AITH Piano Black AC",
        "Gree GS-12AITH Grey AC",
        "Gree",
    )
    assert decision.tier == TIER_REJECT
    assert "Color collision" in decision.reason


def test_category_nouns_are_not_shades() -> None:
    # "Water Dispenser Purple" must not invent a DISPENSER shade.
    slots = extract_product_slots(
        "ORIENT Crystal 3 Taps Purple Glass Door Water Dispensers_021", "Orient"
    )
    assert slots.guarded_facets.color_shade is None
