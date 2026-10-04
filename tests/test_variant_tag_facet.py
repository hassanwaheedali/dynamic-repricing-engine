"""Regression tests: parenthesised / glued finish-variant tags ("(G)", "(OW)").

A short alphabetic tag wrapped in parentheses is a guarded variant facet,
read identically from every spelling the marketplaces use:

* ``HSU-20HJUV(G)-T3``   -- tag wrapped inside the catalog model code
* ``... (G) (HSU-20HJUV T3)`` -- tag in parentheses beside the model
* ``... | (G) | ...``    -- tag in a pipe-separated segment
* ``HSU-20HJUVGT3``      -- tag glued onto the anchor

Equal tag  -> EXACT.  Omitted tag -> BASE (usable, cross-check notice).
Different tag -> REJECT.  Marketing parens ("(NEW)") are never tags.
No brand / colour / series vocabulary is consulted anywhere here.
"""

from pricing_engine.matcher import (
    TIER_BASE,
    TIER_EXACT,
    TIER_REJECT,
    extract_product_slots,
    generate_search_patterns,
    referee_match,
)

TARGET = "HSU-20HJUV(G)-T3"


def test_search_patterns_never_carry_literal_parens() -> None:
    patterns = generate_search_patterns(TARGET)
    assert patterns["tier_1"], "waterfall must still emit queries"
    for tier in patterns.values():
        for query in tier:
            assert "(" not in query and ")" not in query, query
    # The bare anchor must be queryable: that is what a human would type.
    assert "HSU-20HJUV" in patterns["tier_1"]


def test_paren_tag_read_from_every_spelling() -> None:
    for title in (
        "HAIER Split Air Conditioner DC INVERTER AC 1.5TON (G) (HSU-20HJUV T3)",
        "Haier | 1.5 Ton | HSU-20HJUV T3 | DC Inverter | (G) | Split | Air Conditioner",
        "HAIER 1.5 TON Air Conditioner T3 UV INVERTER AC Model HSU-20HJUVGT3",
        "Haier HSU-20HJUV (G) T3 1.5 Ton DC Inverter AC",
    ):
        decision = referee_match(TARGET, title, "Haier")
        assert decision.tier == TIER_EXACT, f"{title!r}: {decision.reason}"
        assert decision.usable


def test_different_variant_tag_rejects() -> None:
    decision = referee_match(
        TARGET,
        "HAIER 1.5 TON Air Conditioner T3 UV INVERTER AC Model HSU-20HJUVE T3",
        "Haier",
    )
    assert decision.tier == TIER_REJECT
    assert "Variant tag collision" in decision.reason
    assert not decision.usable


def test_omitted_variant_tag_falls_back_to_base() -> None:
    decision = referee_match(
        TARGET,
        "HAIER 1.5 TON Air Conditioner T3 UV INVERTER AC Model HSU-20HJUV",
        "Haier",
    )
    assert decision.tier == TIER_BASE
    assert decision.usable


def test_marketing_parens_are_not_variant_tags() -> None:
    slots = extract_product_slots(
        "Haier (NEW) HSU-20HJUV(G) T3 1.5 Ton DC Inverter AC", "Haier"
    )
    assert slots.guarded_facets.variant_tag == "G"
    noise = extract_product_slots("Haier (NEW) HSU-20HJUV T3 1.5 Ton DC Inverter AC", "Haier")
    assert noise.guarded_facets.variant_tag is None
    decision = referee_match(TARGET, "Haier (NEW) HSU-20HJUV (G) T3 1.5 Ton DC Inverter AC", "Haier")
    assert decision.tier == TIER_EXACT
    # A bare lone letter that IS a colour (G = Gold) stays owned by the colour
    # facet, so it must not enter the variant_tag slot.
    bare = extract_product_slots("Haier HSU-20HJUV G T3 1.5 Ton DC Inverter AC", "Haier")
    assert bare.guarded_facets.variant_tag is None


def test_two_letter_finish_codes_are_tags_too() -> None:
    # The corpus shows (OW)/(DG)/(GE) style finish codes, not only single letters.
    target = "Haier HSU-14HFTEX (OW) T3 Plus"
    same = referee_match(target, "Haier HSU-14HFTEX(OW)-T3 Plus 1 Ton AC", "Haier")
    assert same.tier == TIER_EXACT, same.reason
    other = referee_match(target, "Haier HSU-14HFTEX(DG)-T3 Plus 1 Ton AC", "Haier")
    assert other.tier == TIER_REJECT
    assert "Variant tag collision" in other.reason
