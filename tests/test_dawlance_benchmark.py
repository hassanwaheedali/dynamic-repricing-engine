"""Regression and benchmark test suite for Dawlance multi-tier search and strict referee matching.

Validates:
1. Dynamic Decomposer & Pattern Generator for leading capacity (e.g. 15 Infinity Pro -> Dawlance Infinity 15).
2. Dynamic Slash-Separated Series OR-Matching (e.g. 30 Sprinter / Powercon T3).
3. Marketplace Noise Purification (stripping sellers, installments, operational terms).
4. Strict Guarded Facets (Capacity 30 vs 15 block, T3 isolation, Tub WB vs GB isolation).
5. Color Optionality Rule (Conflicting color rejected, omitted color accepted).
"""


from pricing_engine.matcher import (
    clean_marketplace_noise,
    extract_search_query_and_model,
    generate_search_patterns,
    referee_match,
)


def test_leading_capacity_query_extraction_no_digit_repetition() -> None:
    """Ensure leading capacity codes do not repeat digits (e.g. no 'Dawlance 15 15')."""
    query, model = extract_search_query_and_model("15 Infinity Pro Fix Speed", brand="Dawlance")
    assert query == "Dawlance Infinity 15"
    assert "Infinity" in model
    assert "15" in model

    query30, model30 = extract_search_query_and_model("30 Infinity Pro Fix Speed", brand="Dawlance")
    assert query30 == "Dawlance Infinity 30"
    assert "Infinity" in model30
    assert "30" in model30


def test_slash_series_pattern_generation() -> None:
    """Ensure slash-separated series generates multi-tier queries for both alternatives."""
    patterns = generate_search_patterns("30 Sprinter / Powercon T3", brand="Dawlance")
    t1 = patterns["tier_1"]
    t2 = patterns["tier_2"]
    t3 = patterns["tier_3"]

    # Tier 1 should cover both Sprinter and Powercon with capacity 30
    assert any("Sprinter" in q and "30" in q for q in t1)
    assert any("Powercon" in q and "30" in q for q in t1)

    # Tier 2 should cover bare series names
    assert any("Sprinter" in q for q in t2)
    assert any("Powercon" in q for q in t2)

    # Tier 3 should cover 1.5 TON conversion
    assert any("1.5 TON" in q for q in t3)


def test_slash_series_referee_or_matching() -> None:
    """Ensure candidate matching either alternative in slash series is accepted."""
    target = "30 Sprinter / Powercon T3"

    # Match Sprinter alternative
    cand_sprinter = "Dawlance Sprinter 30 T3 Inverter 1.5 Ton AC - ElectroEase"
    dec_s = referee_match(target, cand_sprinter, brand="Dawlance")
    assert dec_s.is_match is True

    # Match Powercon alternative
    cand_powercon = "Dawlance Powercon 30 T3 Inverter 1.5 Ton AC"
    dec_p = referee_match(target, cand_powercon, brand="Dawlance")
    assert dec_p.is_match is True

    # Reject non-T3
    cand_non_t3 = "Dawlance Sprinter 30 Inverter 1.5 Ton AC - ElectroEase"
    dec_non_t3 = referee_match(target, cand_non_t3, brand="Dawlance")
    assert dec_non_t3.is_match is False
    assert "T3 mismatch" in dec_non_t3.reason


def test_color_optionality_and_parentheses_cleaning() -> None:
    """Ensure catalog parenthetical colors are extracted, noise is stripped, and unmentioned color is accepted."""
    target = "30 Magna T3 INV (Milky White Textured)"

    # Candidate omits color entirely -> MUST ACCEPT
    cand_no_color = "Dawlance Magna 30 T3 Inverter AC - HomeCart"
    dec_accept = referee_match(target, cand_no_color, brand="Dawlance")
    assert dec_accept.is_match is True

    # Candidate has conflicting color (Silver) -> MUST REJECT
    cand_silver = "Dawlance Magna 30 T3 Inverter AC Silver"
    dec_reject_color = referee_match(target, cand_silver, brand="Dawlance")
    assert dec_reject_color.is_match is False
    assert "Color collision" in dec_reject_color.reason


def test_capacity_mismatch_strictly_rejected() -> None:
    """Ensure capacity code 30 strictly rejects 15 (1.5 Ton vs 1.0 Ton)."""
    target = "30 Magna T3 INV (Milky White Textured)"
    cand_15 = "Dawlance Magna 15 T3 Inverter AC"
    dec = referee_match(target, cand_15, brand="Dawlance")
    assert dec.is_match is False
    assert "Capacity / screen size mismatch" in dec.reason


def test_sub_series_collision_guard() -> None:
    """Ensure genuine sub-series tokens (Pro, Plus, Max) trigger collisions while noise does not."""
    target = "15 Infinity Pro Fix Speed"

    # Exact sub-series match with operational noise -> MUST ACCEPT
    cand_pro = "Dawlance 15 Infinity Pro Fixed Speed AC - On Installment 0% Markup"
    dec_pro = referee_match(target, cand_pro, brand="Dawlance")
    assert dec_pro.is_match is True

    # Missing sub-series 'Pro' -> MUST REJECT
    cand_base = "Dawlance 15 Infinity Fixed Speed AC"
    dec_base = referee_match(target, cand_base, brand="Dawlance")
    assert dec_base.is_match is False
    assert "Missing required series tokens" in dec_base.reason


def test_glued_sku_anchor_matching() -> None:
    """Ensure glued model numbers like DWT11467ES match hyphenated and spaced marketplace listings."""
    target = "AWM DWT11467ES"

    # Hyphenated listing with vendor noise
    cand_hyphen = "Dawlance DWT-11467 ES Automatic Washing Machine - ElectroEase"
    dec_hyphen = referee_match(target, cand_hyphen, brand="Dawlance")
    assert dec_hyphen.is_match is True

    # Spaced listing with brand
    cand_spaced = "Dawlance 11467 ES Washing Machine"
    dec_spaced = referee_match(target, cand_spaced, brand="Dawlance")
    assert dec_spaced.is_match is True

    # Wrong numeric model code (11465 vs 11467) -> MUST REJECT
    cand_wrong = "Dawlance DWT-11465 ES Washing Machine"
    dec_wrong = referee_match(target, cand_wrong, brand="Dawlance")
    assert dec_wrong.is_match is False
    assert "Anchor model mismatch" in dec_wrong.reason


def test_hardware_tub_wb_vs_gb_isolation() -> None:
    """Ensure Glass Lid (GB) strictly rejects Plastic Window (WB)."""
    target = "DW 10095 GB Twin Tub Black Lid"

    # Matching GB
    cand_gb = "Dawlance DW-10095 GB Twin Tub Washing Machine"
    assert referee_match(target, cand_gb, brand="Dawlance").is_match is True

    # Mismatching WB
    cand_wb = "Dawlance DW-10095 WB Twin Tub Washing Machine"
    dec_wb = referee_match(target, cand_wb, brand="Dawlance")
    assert dec_wb.is_match is False
    assert "Hardware tub mismatch" in dec_wb.reason


def test_marketplace_noise_cleaner() -> None:
    """Verify clean_marketplace_noise strips seller tags, delivery, payment terms, and HVAC tags."""
    raw = "Dawlance AC 1.5 Ton On Installment 0% Markup Free Delivery ElectroEase ISPK-991 Heat & Cool"
    cleaned = clean_marketplace_noise(raw)
    assert "Installment" not in cleaned
    assert "0% Markup" not in cleaned
    assert "Free Delivery" not in cleaned
    assert "ElectroEase" not in cleaned
    assert "ISPK-991" not in cleaned
    assert "Heat & Cool" not in cleaned
