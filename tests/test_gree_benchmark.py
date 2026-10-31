from pricing_engine.matcher import generate_search_patterns, referee_match


def test_gree_airy_t3_in_title_and_attached_t3() -> None:
    """Verify that Gree Airy T3 models match whether T3 is attached as -T3 or specified in title."""
    target_12_w = "Gree GS-12AITH21W-T3 1 Ton Airy Plus Split Air Conditioner"

    # Candidate 1: Attached -T3
    cand_attached = (
        "GREE Airy Plus T3 1 TON Inverter Split AC GS-12AITH21W-T3 | On Easy Monthly Installments"
    )
    dec1 = referee_match(target_12_w, cand_attached, brand="Gree")
    assert dec1.is_match is True, f"Failed attached -T3 match: {dec1.reason}"

    # Candidate 2: Model without -T3, but T3 in title
    cand_title_t3 = (
        "Gree Airy T3 Series GS-12AITH21W 1.0 Ton Inverter (Heat & Cool) Split Air Conditioner"
    )
    dec2 = referee_match(target_12_w, cand_title_t3, brand="Gree")
    assert dec2.is_match is True, f"Failed title T3 match: {dec2.reason}"


def test_gree_airy_pro_24s_matching() -> None:
    """Verify that GS-12AITH24S-T3 matches listings with -T3 and with T3 in title."""
    target_24_s = "Gree GS-12AITH24S-T3 1 Ton Airy Pro Split Air Conditioner"

    cand_t3_attached = (
        "Gree 1.0 Ton Airy T3 Series Inverter Heat & Cool Air Conditioner Model Gs-12AITH24S-T3"
    )
    dec1 = referee_match(target_24_s, cand_t3_attached, brand="Gree")
    assert dec1.is_match is True, f"Failed 24S attached -T3 match: {dec1.reason}"

    cand_t3_series = (
        "Gree Airy T3 Series GS-12AITH24S 1.0 Ton Inverter (Heat & Cool) Split Air Conditioner"
    )
    dec2 = referee_match(target_24_s, cand_t3_series, brand="Gree")
    assert dec2.is_match is True, f"Failed 24S title T3 match: {dec2.reason}"


def test_gree_airy_unprefixed_gs_matching_and_patterns() -> None:
    """Verify that GS-18AITH21B-T3 matches listings without GS- prefix and emits pure stem search patterns."""
    target_18_b = "Gree GS-18AITH21B-T3 1.5 Ton Airy Plus Split Air Conditioner"

    # Candidate 1: Missing GS- prefix (18AITH21B-T3)
    cand_no_gs = "GREE AC 1.5 TON Inverter Split Air Conditioner Airy Plus 18AITH21B-T3 BLACK Free installation"
    dec1 = referee_match(target_18_b, cand_no_gs, brand="Gree")
    assert dec1.is_match is True, f"Failed match for candidate without GS- prefix: {dec1.reason}"

    # Candidate 2: Standard GS-18AITH21B-T3
    cand_std = (
        "Gree 1.5 Ton Airy T3 Series Inverter Heat & Cool Air Conditioner Model Gs-18AITH21B-T3"
    )
    dec2 = referee_match(target_18_b, cand_std, brand="Gree")
    assert dec2.is_match is True, f"Failed standard GS match: {dec2.reason}"

    # Candidate 3: GS-18AITH21B with T3 in title
    cand_title_t3 = (
        "Gree Airy T3 Series GS-18AITH21B 1.5 Ton Inverter (Heat & Cool) Split Air Conditioner"
    )
    dec3 = referee_match(target_18_b, cand_title_t3, brand="Gree")
    assert dec3.is_match is True, f"Failed GS title T3 match: {dec3.reason}"

    # Search patterns must emit unprefixed pure stem in Tier 1 and Tier 2
    patterns = generate_search_patterns(target_18_b, brand="Gree")
    all_tier_queries = [q.upper() for q in patterns["tier_1"] + patterns["tier_2"]]
    assert any("18AITH21B" in q for q in all_tier_queries), "Missing 18AITH21B in search queries"
