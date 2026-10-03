"""Haier benchmark test suite for multi-stage search, deduplication, and referee matching.

Validates the resolution of 25 benchmark models that previously experienced SOLO/false monopolies:
1. Technical Compound Slashes (/DC, /AC, /Z):
   - 24 HE/DC, 48 CE/DC, Cassette 18 HE/DC contain /DC (Direct Current rating).
   - Must NEVER split into alternative series HE or DC.
2. Alternative Variant Slashes (OR Branches):
   - HRF-418 TIFG1U1/TIFB1U1 (IOT), HGL-25MXP8 / 25MXP9.
   - Must expand into Cartesian branches and match candidates from either branch.
3. Dynamic Brand-Initial Prefix Synthesis:
   - Bare catalog stems like 11lf, 13hfn under brand Haier match portal listings HRF-11LF, HSU-13HFN.
4. Asymmetric Negative Guards:
   - HAF 50 MB vs HAF 50 DB (variant collision).
   - COOL ONLY vs Heat & Cool (operating mode collision).
   - T3 vs non-T3, IoT vs non-IoT.
"""

from pricing_engine.matcher import (
    expand_cartesian_branches,
    generate_search_patterns,
    normalize_technical_slashes,
    referee_match,
)


def test_technical_slash_dc_never_splits_into_alternative_series() -> None:
    """Ensure /DC (Direct Current) is preserved as a compound code and never split into HE or DC series."""
    # 1. 24 HE/DC
    norm_24 = normalize_technical_slashes("24 HE/DC")
    assert "HE-DC" in norm_24 or "HEDC" in norm_24
    branches_24 = expand_cartesian_branches("24 HE/DC")
    assert len(branches_24) == 1
    assert "DC 24" not in branches_24[0]
    assert "HE 24" not in branches_24[0]

    # Search patterns must contain 24 and HE-DC together, NOT bare HE or DC
    p24 = generate_search_patterns("24 HE/DC", brand="Haier")
    t1_24 = p24["tier_1"]
    assert any("HE-DC" in q or "HEDC" in q or "24 HE" in q for q in t1_24)
    # Ensure neither tier_1 nor tier_2 has standalone "DC" as a series search
    assert not any(q.strip().upper() == "DC" or q.strip().upper() == "HAIER DC" for q in p24["tier_2"])

    # 2. 48 CE/DC
    norm_48 = normalize_technical_slashes("48 CE/DC")
    assert "CE-DC" in norm_48 or "CEDC" in norm_48
    branches_48 = expand_cartesian_branches("48 CE/DC")
    assert len(branches_48) == 1

    # 3. Cassette 18 HE/DC
    norm_c18 = normalize_technical_slashes("Cassette 18 HE/DC")
    assert "18 HE-DC" in norm_c18 or "18HE-DC" in norm_c18
    branches_c18 = expand_cartesian_branches("Cassette 18 HE/DC")
    assert len(branches_c18) == 1


def test_compound_slash_z_normalizes_to_hdz() -> None:
    """Ensure 24 HD/Z W normalizes to 24 HDZ W and does not split into Z series."""
    norm = normalize_technical_slashes("24 HD/Z W")
    assert "HDZ" in norm
    branches = expand_cartesian_branches("24 HD/Z W")
    assert len(branches) == 1
    assert "HDZ" in branches[0]


def test_alternative_slashes_expand_cartesian_branches() -> None:
    """Ensure true alternative model variants expand into independent branches."""
    # 1. Dual model refrigerator
    target_rf = "HRF-418 TIFG1U1/TIFB1U1 (IOT)"
    branches_rf = expand_cartesian_branches(target_rf)
    assert len(branches_rf) >= 2
    assert any("TIFG1U1" in b for b in branches_rf)
    assert any("TIFB1U1" in b for b in branches_rf)

    # 2. Dual model microwave oven
    target_mwo = "HGL-25MXP8 / 25MXP9"
    branches_mwo = expand_cartesian_branches(target_mwo)
    assert len(branches_mwo) >= 2
    assert any("25MXP8" in b for b in branches_mwo)
    assert any("25MXP9" in b for b in branches_mwo)


def test_haier_multi_pattern_generation_tiers() -> None:
    """Ensure Haier models generate comprehensive queries across all 3 tiers."""
    # 1. Bare alphanumeric refrigerator stem: 11lf
    p_11lf = generate_search_patterns("11lf", brand="Haier")
    assert any("11lf" in q.lower() for q in p_11lf["tier_1"])
    assert any("haier" in q.lower() for q in p_11lf["tier_1"])

    # 2. Microwave with spaced prefix: HMO-62 MX80
    p_mx80 = generate_search_patterns("HMO-62 MX80", brand="Haier")
    assert any("62" in q and "MX80" in q.upper() for q in p_mx80["tier_1"])

    # 3. Air fryer with separated variant: HAF 50 MB
    p_50mb = generate_search_patterns("HAF 50 MB", brand="Haier")
    assert any("50" in q and "MB" in q.upper() for q in p_50mb["tier_1"])


def test_haier_referee_dynamic_brand_initial_synthesis() -> None:
    """Ensure bare catalog stems match portal listings with Haier brand initial prefixes (HRF, HSU)."""
    # 11lf -> HRF-11LF
    dec_11lf = referee_match("11lf", "Haier HRF-11LF Refrigerator Direct Cool", brand="Haier")
    assert dec_11lf.is_match is True

    # 13hfn -> HSU-13HFN
    dec_13hfn = referee_match("13hfn", "Haier Inverter Air Conditioner 1 Ton HSU-13HFN", brand="Haier")
    assert dec_13hfn.is_match is True


def test_haier_referee_dc_compound_ac_matching() -> None:
    """Ensure candidate listings with HE/DC, CE/DC, HDZ match cleanly without false monopoly."""
    # Cassette 18 HE/DC
    dec_c18 = referee_match(
        "Cassette 18 HE/DC",
        "Haier Cassette 1.5 Ton Inverter 18HE/DC AC",
        brand="Haier",
    )
    assert dec_c18.is_match is True

    # 48 CE/DC
    dec_48 = referee_match(
        "48 CE/DC",
        "Haier Floor Standing 4 Ton Inverter 48CE/DC",
        brand="Haier",
    )
    assert dec_48.is_match is True

    # 24 HD/Z W vs 24 HDZ White (Base Match)
    dec_24hdz = referee_match(
        "24 HD/Z W",
        "Haier 2 Ton Inverter AC 24 HDZ White",
        brand="Haier",
    )
    assert dec_24hdz.is_match is True

    # 24 HD/Z UV W vs 24 HDZ UV White (UV Category 2 Match)
    dec_24hdz_uv = referee_match(
        "24 HD/Z UV W",
        "Haier 2 Ton Inverter AC 24 HDZ UV White",
        brand="Haier",
    )
    assert dec_24hdz_uv.is_match is True


def test_haier_referee_alternative_branches_acceptance() -> None:
    """Ensure candidate matching either branch of a slash model is accepted."""
    target_rf = "HRF-418 TIFG1U1/TIFB1U1 (IOT)"
    # Match G1 branch
    cand_g1 = "Haier HRF-418 TIFG1U1 Glass Door Smart Refrigerator (IoT)"
    dec_g1 = referee_match(target_rf, cand_g1, brand="Haier")
    assert dec_g1.is_match is True

    # Match B1 branch
    cand_b1 = "Haier HRF-418 TIFB1U1 Glass Door Smart Refrigerator"
    dec_b1 = referee_match(target_rf, cand_b1, brand="Haier")
    assert dec_b1.is_match is True

    target_mwo = "HGL-25MXP8 / 25MXP9"
    # Match MXP8
    cand_p8 = "Haier Microwave Oven HGL-25MXP8 Grill 25 Litres"
    dec_p8 = referee_match(target_mwo, cand_p8, brand="Haier")
    assert dec_p8.is_match is True

    # Match MXP9
    cand_p9 = "Haier Microwave Oven HGL-25MXP9 Grill"
    dec_p9 = referee_match(target_mwo, cand_p9, brand="Haier")
    assert dec_p9.is_match is True


def test_haier_referee_variant_tag_collision_guard() -> None:
    """Ensure conflicting variant tags (50MB vs 50DB) trigger zero-tolerance rejection."""
    target_mb = "HAF 50 MB"
    cand_matching = "Haier Air Fryer HAF-50MB Black"
    assert referee_match(target_mb, cand_matching, brand="Haier").is_match is True

    cand_conflicting = "Haier Air Fryer HAF-50DB Dark Brown"
    dec_rej = referee_match(target_mb, cand_conflicting, brand="Haier")
    assert dec_rej.is_match is False
    assert "Variant tag collision" in dec_rej.reason


def test_haier_referee_operating_mode_collision_guard() -> None:
    """Ensure Cool Only target strictly rejects Heat & Cool candidates to avoid commercial mispricing."""
    target_cool_only = "Cassette 48 HE/DC COOL ONLY"
    cand_heat_cool = "Haier 4 Ton Cassette Inverter 48HE/DC Heat and Cool"
    dec_mode = referee_match(target_cool_only, cand_heat_cool, brand="Haier")
    assert dec_mode.is_match is False
    assert "Operating mode collision" in dec_mode.reason


def test_haier_descriptive_series_and_tv_screen_matching() -> None:
    """Ensure descriptive series (Solar hybrid) and TV screen codes (32 D2) match properly."""
    # Solar hybrid 1.5ton
    dec_solar = referee_match(
        "Solar hybrid 1.5ton",
        "Haier Inverter Air Conditioner 1.5 Ton Solar Hybrid HSU-18HNS",
        brand="Haier",
    )
    assert dec_solar.is_match is True

    # 32" D2 LED TV
    dec_tv = referee_match(
        "32\" D2",
        "Haier 32 Inch HD LED TV 32D2 Official Warranty",
        brand="Haier",
    )
    assert dec_tv.is_match is True
