import pytest

from pricing_engine.matcher import (
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    is_strict_model_match,
    referee_match,
)


@pytest.mark.parametrize(
    ("full_title", "expected_query", "expected_code"),
    [
        (
            "Gree Inverter 1.5 Ton GS-18PITH11W",
            "18PITH11W",
            "18PITH11W",
        ),
        (
            "Gree 1 Ton Fairy Inverter GW-12AITH21W-T3",
            "12AITH21W",
            "12AITH21W-T3",
        ),
        (
            "Gree Floor Standing GF-24FITH1",
            "24FITH1",
            "24FITH1",
        ),
    ],
)
def test_extract_search_query_and_model(
    full_title: str, expected_query: str, expected_code: str
) -> None:
    query, model = extract_search_query_and_model(full_title)
    assert query == expected_query
    assert model.replace("GS-", "").replace("GW-", "").replace("GF-", "") == expected_code


def test_strict_model_match_success() -> None:
    target = "12AITH21W"
    # Exact match in title
    assert is_strict_model_match("Gree Inverter AC 1 Ton 12AITH21W White", target)
    # T3 / AAA variant suffix in title
    assert is_strict_model_match("Gree 12AITH21W-T3 Inverter 1.0 Ton", target)
    # Generic base without color suffix
    assert is_strict_model_match("Gree Inverter 12AITH21 Series", target)


def test_strict_model_match_color_collision_rejection() -> None:
    target = "12AITH21W"  # White target
    # Must reject Black (B)
    assert not is_strict_model_match("Gree 12AITH21B Inverter AC Black", target)
    # Must reject Silver (S)
    assert not is_strict_model_match("Gree 12AITH21S Inverter AC Silver", target)
    # Must reject Grey (G)
    assert not is_strict_model_match("Gree 12AITH21G Inverter AC Grey", target)


def test_strict_model_match_capacity_mismatch_rejection() -> None:
    # 1.5 Ton target must reject 1.0 Ton title
    target = "18PITH11W"
    assert not is_strict_model_match("Gree 12PITH11W Inverter AC 1 Ton", target)
    # 3.0 Ton Floor Standing target must reject 2.0 Ton title
    assert not is_strict_model_match("Gree Floor Standing GF-24TFIH 2 Ton", "36TFIH")
    # 12AITH21W must reject 12AITH24 Pro
    assert not is_strict_model_match("Gree 12AITH24 Pro Inverter AC", "12AITH21W")


def test_strict_model_match_floor_standing_36tfih() -> None:
    target = "36TFIH"
    # Matches Gree Floor Standing GF-36TFIH
    assert is_strict_model_match(
        "Gree - Air Conditioner 3.0 Ton Floor Standing T3 Inverter Heat & Cool - GF-36TFIH",
        target,
    )
    assert is_strict_model_match(
        "Gree | 3.0 Ton | GF-36TFIH | Cabinet | Inverter | Floor Standing",
        target,
    )


def test_strict_model_match_cool_only_vs_heat_cool() -> None:
    # Cool only (PITC) must reject Heat & Cool (PITH)
    target_cool_only = "18PITC12W"
    assert is_strict_model_match("Gree 1.5 Ton Inverter AC GS-18PITC12W-T3 Cool Only", target_cool_only)
    assert not is_strict_model_match("Gree 1.5 Ton Inverter AC GS-18PITH12W Heat & Cool", target_cool_only)


def test_strict_model_match_black_target_rejects_white() -> None:
    # Target is Black (18AITH21B) -> must reject White (18AITH21W)
    target_black = "18AITH21B"
    assert is_strict_model_match("Gree 1.5 Ton Airy 18AITH21B Black", target_black)
    assert not is_strict_model_match("Gree 1.5 Ton Airy 18AITH21W White", target_black)
    assert not is_strict_model_match("Gree 1.5 Ton Airy 18AITH21 Series", target_black)


def test_strict_model_match_silver_target_rejects_white() -> None:
    # Target is Silver (24PITH11S) -> must reject White (24PITH11W)
    target_silver = "24PITH11S"
    assert is_strict_model_match("Gree 2.0 Ton Pular 24PITH11S Silver", target_silver)
    assert not is_strict_model_match("Gree 2.0 Ton Pular 24PITH11W White", target_silver)


def test_strict_model_match_color_slash_expansion() -> None:
    silver_target = "12AITH24S-T3"
    white_target = "12AITH24W-T3"
    black_target = "12AITH24B-T3"

    # 1. Standard slash: GS-12AITH24W/S matches both Silver and White
    title_standard = "GREE Airy Pro 1 TON Split AC Inverter G-Boost AI T3 GS-12AITH24W/S"
    assert is_strict_model_match(title_standard, silver_target)
    assert is_strict_model_match(title_standard, white_target)
    # But strictly rejects Black
    assert not is_strict_model_match(title_standard, black_target)

    # 2. Hyphenated slash: GS-12AITH24-W/S
    title_hyphen = "Gree Airy Pro 1 Ton GS-12AITH24-W/S Heat & Cool"
    assert is_strict_model_match(title_hyphen, silver_target)
    assert is_strict_model_match(title_hyphen, white_target)

    # 3. Spaced slash: GS-12AITH24 - W/S
    title_spaced = "Gree Airy Pro 1 Ton GS-12AITH24 - W/S Heat & Cool"
    assert is_strict_model_match(title_spaced, silver_target)

    # 4. Trailing -T3 suffix: GS-12AITH24W/S-T3
    title_suffix = "Gree Airy Pro 1 Ton GS-12AITH24W/S-T3 Heat & Cool"
    assert is_strict_model_match(title_suffix, silver_target)
    assert is_strict_model_match(title_suffix, white_target)

    # 5. Trailing space T3 suffix: GS-12AITH24W/S T3
    title_space_suffix = "Gree Airy Pro 1 Ton GS-12AITH24W/S T3 Inverter"
    assert is_strict_model_match(title_space_suffix, silver_target)

    # 5b. Trailing attached T3 (without dash or space): GS-12AITH24W/ST3
    title_attached_suffix = "Gree Airy Pro 1 Ton GS-12AITH24W/ST3 Inverter"
    assert is_strict_model_match(title_attached_suffix, silver_target)
    assert is_strict_model_match(title_attached_suffix, white_target)

    # 6. Single-color isolation: pure White without slash strictly rejects Silver
    pure_white = "GREE Airy Pro 1 TON Split AC Inverter GS-12AITH24W"
    assert not is_strict_model_match(pure_white, silver_target)

    # 7. Extended colors: W/B (White / Black) and W/C (White / Champagne)
    wb_title = "Gree 1.5 Ton Airy GS-18AITH21W/B-T3"
    assert is_strict_model_match(wb_title, "18AITH21W-T3")
    assert is_strict_model_match(wb_title, "18AITH21B-T3")
    assert not is_strict_model_match(wb_title, "18AITH21S-T3")

    wc_title = "Gree 1 Ton Airy GS-12AITH24W/C"
    assert is_strict_model_match(wc_title, "12AITH24W")
    assert is_strict_model_match(wc_title, "12AITH24C")


def test_strict_model_match_series_slash_and_generation_isolation() -> None:
    # 1. Pular batch slash: 14S / 11S
    pular_14s = "12PITH14S"
    pular_11s = "12PITH11S"
    pular_title = "GREE Split AC 1 TON Pular Series Inverter GS-12PITH14S /11S"
    assert is_strict_model_match(pular_title, pular_14s)
    assert is_strict_model_match(pular_title, pular_11s)

    # 2. Pular batch without space: 14S/11S
    assert is_strict_model_match("Gree Pular 1 Ton GS-12PITH14S/11S", pular_14s)
    assert is_strict_model_match("Gree Pular 1 Ton GS-12PITH14S/11S", pular_11s)

    # 3. Generation isolation: ZITH1 and ZITH2 must NEVER match each other
    zeno_1 = "12ZITH1W-T3"
    zeno_2 = "12ZITH2W-T3"
    assert is_strict_model_match("Gree Zeno 1 Ton GS-12ZITH1W Inverter", zeno_1)
    assert not is_strict_model_match("Gree Zeno 1 Ton GS-12ZITH1W Inverter", zeno_2)
    assert is_strict_model_match("Gree Zeno 1 Ton GS-12ZITH2W Inverter", zeno_2)
    assert not is_strict_model_match("Gree Zeno 1 Ton GS-12ZITH2W Inverter", zeno_1)


def test_strict_model_match_pular_shared_color_batch_slashes() -> None:
    target_15g = "GS-24PITH15G-T3"
    target_17g = "GS-24PITH17G-T3"
    target_18g = "GS-24PITH18G-T3"
    target_15w = "GS-24PITH15W-T3"

    # 1. Two-batch with shared color: GS-24PITH15/17G - T3
    title_2batch = "GREE Pular T3 2 TON Split AC GS-24PITH15/17G - T3"
    assert is_strict_model_match(title_2batch, target_15g)
    assert is_strict_model_match(title_2batch, target_17g)
    # Must strictly reject White
    assert not is_strict_model_match(title_2batch, target_15w)

    # 2. Four-batch with shared color: GS-24PITH15/16/17/18G
    title_4batch = "Gree Pular Series 2 Ton Split AC GS-24PITH15/16/17/18G"
    assert is_strict_model_match(title_4batch, target_15g)
    assert is_strict_model_match(title_4batch, target_18g)
    assert not is_strict_model_match(title_4batch, target_15w)

    # 3. Two-batch White with space: GS-24PITH15/ 17W - T3
    title_white_batch = "GREE Pular T3 2 TON Split AC GS-24PITH15/ 17W - T3"
    assert is_strict_model_match(title_white_batch, target_15w)
    # Must strictly reject Grey
    assert not is_strict_model_match(title_white_batch, target_15g)

    # 4. Attached T3 (without dash or space): GS-24PITH15/17GT3
    title_attached = "GREE Pular T3 2 TON Split AC GS-24PITH15/17GT3 Inverter"
    assert is_strict_model_match(title_attached, target_15g)
    assert is_strict_model_match(title_attached, target_17g)
    assert not is_strict_model_match(title_attached, target_15w)


def test_strict_model_match_universal_multivariant_expansion() -> None:
    # 1. Multi-generation slash with trailing tag: GS-18ZITH1W/2W/3W Ultra -T3
    zeno_title = "Gree Split AC GS-18ZITH1W/2W/3W Ultra -T3"
    assert is_strict_model_match(zeno_title, "GS-18ZITH1W-T3")
    assert is_strict_model_match(zeno_title, "GS-18ZITH2W-T3")
    assert is_strict_model_match(zeno_title, "GS-18ZITH3W-T3")
    assert not is_strict_model_match(zeno_title, "GS-18ZITH4W-T3")
    assert not is_strict_model_match(zeno_title, "GS-12ZITH2W-T3")

    # 2. Pure standalone isolation: GS-18ZITH1W-T3 must NOT match target GS-18ZITH2W-T3
    standalone_gen1 = "Gree Split AC GS-18ZITH1W-T3"
    assert not is_strict_model_match(standalone_gen1, "GS-18ZITH2W-T3")

    # 3. Floor standing multi-variant: GF-24FITH1/2
    floor_title = "Gree Floor Standing Cabinet GF-24FITH1/2 Inverter"
    assert is_strict_model_match(floor_title, "24FITH1")
    assert is_strict_model_match(floor_title, "24FITH2")
    assert not is_strict_model_match(floor_title, "24FITH3")

    # 4. Hyphenated and parenthesized variants
    assert is_strict_model_match("Gree Zeno Inverter GS-18ZITH-1W/2W/3W", "GS-18ZITH2W-T3")
    assert is_strict_model_match("Gree Zeno Inverter GS-18ZITH (1W/2W/3W)", "GS-18ZITH2W-T3")
    assert is_strict_model_match("Gree Zeno Inverter GS-18ZITH [1W/2W/3W]", "GS-18ZITH2W-T3")
    assert is_strict_model_match("Gree 2.0 Ton Pular GS-24PITH (15/17G)", "GS-24PITH17G-T3")
    assert is_strict_model_match("Gree 1.0 Ton Airy GS-12AITH24 (W/S)", "GS-12AITH24W-T3")

    # 5. Commercial Floor Standing capacity isolation (24 vs 36 Ton)
    assert not is_strict_model_match("Gree Floor Standing GF-24TFIH 2 Ton", "36TFIH")
    assert not is_strict_model_match("Gree Floor Standing GF-36TFIH 3 Ton", "24TFIH")


def test_electronics_world_headline_case() -> None:
    """Verify headline case: Electronics World listing with hyphenated tag on both sides."""
    title_ew = "Gree GS-24AITH21W-T3/21B-T3 2.0 Ton Inverter Split AC"
    assert is_strict_model_match(title_ew, "24AITH21B-T3")
    assert is_strict_model_match(title_ew, "24AITH21W-T3")
    assert is_strict_model_match(title_ew, "24AITH21B")
    assert is_strict_model_match(title_ew, "24AITH21W")
    assert not is_strict_model_match(title_ew, "24AITH21S-T3")

    # Cross-color isolation: pure black vs pure white must NEVER match
    black_only = "Gree GS-24AITH21B-T3 2.0 Ton Inverter Split AC"
    assert is_strict_model_match(black_only, "24AITH21B")
    assert not is_strict_model_match(black_only, "24AITH21W")
    white_only = "Gree GS-24AITH21W-T3 2.0 Ton Inverter Split AC"
    assert is_strict_model_match(white_only, "24AITH21W")
    assert not is_strict_model_match(white_only, "24AITH21B")


def test_multibrand_extractor_and_compound_colors() -> None:
    """Verify brand-agnostic extraction across 768 products, stripping compound colors without hardcoded lists."""
    test_cases = [
        ("DAW AUTO W/M DWT-1165 PL", "Dawlance", "DWT-1165", "DWT-1165 PL"),
        ("DAW AUTO W/M DWT-11671 FLT", "Dawlance", "DWT-11671", "DWT-11671 FLT"),
        ("DAW AUTO W/M DWT-1006 MYSTIC GREY", "Dawlance", "DWT-1006", "DWT-1006"),
        ("DAW AUTO W/M DWT-14470 ES", "Dawlance", "DWT-14470", "DWT-14470 ES"),
        ("HAIER AUTO W/M 100-1269 S6", "Haier", "100-1269", "100-1269 S6"),
        ("HAIER AUTO W/M 100-316S6 GC", "Haier", "100-316S6", "100-316S6 GC"),
        ("HAIER AUTO W/M 110-688S8 BLACK -", "Haier", "110-688S8", "110-688S8"),
        ("HOMAGE M/O HDG-201S", "Homage", "HDG-201S", "HDG-201S"),
        ("HOMAGE M/OVEN HDG-2312B", "Homage", "HDG-2312B", "HDG-2312B"),
        ("KENWOOD CASSETTE 1.5TON NORMAL KCT-1801H", "Kenwood", "KCT-1801H", "KCT-1801H"),
        ("MIDEA CASSETTE 2TON INVERTER MCD1-24HRDN1", "Midea", "MCD1-24HRDN1", "MCD1-24HRDN1"),
        ("UCOOL AIR CURTAIN 3FEET UCA-315Y", "UCOOL", "UCA-315Y", "UCA-315Y"),
        ("MOULINEX BLENDER 3IN1 LM242025", "Moulinex", "LM242025", "LM242025"),
        ("ECOSTAR SPLIT AC 1 ΤΟN 12NV01WT3", "EcoStar", "12NV01WT3", "12NV01WT3"),
        ("MIDEA DISHWAHSER WQP12-5201F INVERTER BLACK 13SETS", "Midea", "WQP12", "WQP12-5201F"),
        ("HOMAGE SDA SANDWICH MAKER 3IN1 HSM-70300-", "Homage", "HSM-70300", "HSM-70300"),
    ]
    for full_name, brand, exp_query, exp_model in test_cases:
        q, m = extract_search_query_and_model(full_name, brand)
        assert q == exp_query, f"Failed query for {full_name}: got {q}, expected {exp_query}"
        assert m == exp_model, f"Failed model for {full_name}: got {m}, expected {exp_model}"


def test_multibrand_slash_multivariant_expansion() -> None:
    """Verify that multi-brand slash models (Dawlance, Homage) expand correctly."""
    # Dawlance washing machines
    daw_title = "Dawlance Auto W/M DWT-1165/1167 PL Glass Door"
    assert is_strict_model_match(daw_title, "DWT-1165 PL")
    assert is_strict_model_match(daw_title, "DWT-1167 PL")
    assert not is_strict_model_match(daw_title, "DWT-1168 PL")

    # Homage microwave ovens
    homage_title = "Homage Microwave Oven HDG-2312/2313B Digital"
    assert is_strict_model_match(homage_title, "HDG-2312B")
    assert is_strict_model_match(homage_title, "HDG-2313B")
    assert not is_strict_model_match(homage_title, "HDG-2314B")


def test_non_model_safeguards_unmodified() -> None:
    """Verify category acronyms and fractions are 100% untouched."""
    from pricing_engine.matcher import expand_multivariant_titles

    assert expand_multivariant_titles("DAW AUTO W/M DWT-1165 PL") == "DAW AUTO W/M DWT-1165 PL"
    assert expand_multivariant_titles("DAW D/F 9199 H&C Inverter") == "DAW D/F 9199 H&C Inverter"
    assert expand_multivariant_titles("Gree Inverter Heat / Cool Split AC") == "Gree Inverter Heat / Cool Split AC"
    assert expand_multivariant_titles("Midea Front Load 12W/8D KG") == "Midea Front Load 12W/8D KG"


def test_technical_slash_safeguards() -> None:
    """Verify technical slashes (/DC, /AC, /KB-xx, /YY year codes, W/O) are NOT expanded."""
    from pricing_engine.matcher import expand_multivariant_titles

    # Haier Cassette /DC (Direct Current) — NOT a variant separator
    assert expand_multivariant_titles("HAIER CASSETTE 1.5TON INVERTER 18HE/DC") == \
        "HAIER CASSETTE 1.5TON INVERTER 18HE/DC"
    assert expand_multivariant_titles("HAIER CASSETTE 4TON INVERTER HBU-48E/DC") == \
        "HAIER CASSETTE 4TON INVERTER HBU-48E/DC"
    assert expand_multivariant_titles("HAIER FLOOR STANDING 48CE/DC INVERTER") == \
        "HAIER FLOOR STANDING 48CE/DC INVERTER"

    # Haier complex technical model
    assert expand_multivariant_titles("HAIER FLOOR 4TON INVERTER HBU-48HE/T3DC-012GE") == \
        "HAIER FLOOR 4TON INVERTER HBU-48HE/T3DC-012GE"

    # Haier subordinate model code /KB-01
    assert expand_multivariant_titles("HAIER CASSETTE 2TON NORMAL 24CE03/KB-01") == \
        "HAIER CASSETTE 2TON NORMAL 24CE03/KB-01"

    # Gaba National year codes /21, /20, /23
    assert expand_multivariant_titles("GABA NATIONAL HOT PLATE GN-261/21") == \
        "GABA NATIONAL HOT PLATE GN-261/21"
    assert expand_multivariant_titles("GABA NATIONAL SANDWITCH MAKER GNE-396/20") == \
        "GABA NATIONAL SANDWITCH MAKER GNE-396/20"
    assert expand_multivariant_titles("GABA NATIONAL SPINNER GND-1606/23") == \
        "GABA NATIONAL SPINNER GND-1606/23"

    # W/O = "Without" — NOT a variant separator
    assert expand_multivariant_titles("DAW W/D 1060 W/O REF WHITE") == \
        "DAW W/D 1060 W/O REF WHITE"


def test_technical_suffix_model_match() -> None:
    """Verify is_strict_model_match handles technical slash suffixes (/DC, /AC, /KB-xx, /YY)."""
    # 18HE/DC: exact match
    assert is_strict_model_match("Haier Cassette 18HE/DC Inverter 1.5 Ton", "18HE/DC")
    # 18HE/DC: partial match — seller omitted /DC
    assert is_strict_model_match("Haier Cassette 18HE Inverter 1.5 Ton", "18HE/DC")
    # Reverse: our catalog says 18HE, listing says 18HE/DC — should still match
    assert is_strict_model_match("Haier Cassette 18HE/DC Inverter", "18HE")
    # Capacity mismatch: 24HE/DC vs 18HE/DC — must reject
    assert not is_strict_model_match("Haier Cassette 24HE/DC Inverter 2 Ton", "18HE/DC")

    # HBU-48E/DC: exact + partial
    assert is_strict_model_match("Haier Cassette HBU-48E/DC Inverter 4 Ton", "HBU-48E/DC")
    assert is_strict_model_match("Haier Cassette HBU-48E Inverter 4 Ton", "HBU-48E/DC")

    # 48CE/DC
    assert is_strict_model_match("Haier Floor Standing 48CE/DC Inverter", "48CE/DC")
    assert is_strict_model_match("Haier Floor Standing 48CE Inverter", "48CE/DC")

    # GN-261/21: exact match
    assert is_strict_model_match("Gaba National GN-261/21 Hot Plate", "GN-261/21")
    # GN-261/21: seller omitted year
    assert is_strict_model_match("Gaba National GN-261 Hot Plate", "GN-261/21")
    # GN-261/21 must NOT match GN-262
    assert not is_strict_model_match("Gaba National GN-262/21 Hot Plate", "GN-261/21")

    # 24CE03/KB-01: exact match
    assert is_strict_model_match("Haier Cassette 24CE03/KB-01 Normal 2 Ton", "24CE03/KB-01")
    # 24CE03/KB-01: seller omitted subordinate code
    assert is_strict_model_match("Haier Cassette 24CE03 Normal 2 Ton", "24CE03/KB-01")


def test_name_only_extraction_dawlance_acs() -> None:
    """Verify name-only Dawlance ACs extract meaningful search queries and keyword models."""
    # AVANTE 30 CLASSIC — query should contain Avante+30, model should include CLASSIC
    q, m = extract_search_query_and_model("DAW SPLIT AC AVANTE INVERTER 30 (CLASSIC", "Dawlance")
    assert "Avante" in q or "AVANTE" in q.upper()
    assert "30" in q
    assert "AVANTE" in m.upper()
    assert "30" in m
    assert "CLASSIC" in m.upper()

    # AVANTE 30 ELEGANT — differentiated from CLASSIC
    q2, m2 = extract_search_query_and_model("DAW SPLIT AC AVANTE INVERTER 30 (ELEGANT", "Dawlance")
    assert "AVANTE" in q2.upper()
    assert "ELEGANT" in m2.upper()
    assert "CLASSIC" not in m2.upper()

    # FROST 20 COOL ONLY vs FROST 30 COOL ONLY — capacity differentiation
    q3, m3 = extract_search_query_and_model("DAW SPLIT AC FROST INVERTER 20 (COOL ONLY)", "Dawlance")
    assert "FROST" in q3.upper()
    assert "20" in m3
    q4, m4 = extract_search_query_and_model("DAW SPLIT AC FROST INVERTER 30 (COOL ONLY)", "Dawlance")
    assert "30" in m4
    assert m3 != m4  # Different capacities must produce different models

    # CHROME 30 WHITE
    q5, m5 = extract_search_query_and_model("DAW SPLIT AC CHROME INVERTER 30 WHITE", "Dawlance")
    assert "CHROME" in q5.upper()
    assert "WHITE" in m5.upper()

    # ENERCON X 15 — X is part of series name
    q6, m6 = extract_search_query_and_model("DAW SPLIT AC ENERCON X INVERTER 15", "Dawlance")
    assert "ENERCON" in q6.upper()
    assert "ENERCON" in m6.upper()
    assert "X" in m6.upper().split()
    assert "15" in m6

    # DUAL PRO T3 15 — T3 is part of model name
    q7, m7 = extract_search_query_and_model("DAW SPLIT AC DUAL PRO T3 INVERTER 15", "Dawlance")
    assert "DUAL" in m7.upper()
    assert "PRO" in m7.upper()
    assert "T3" in m7.upper()
    assert "15" in m7

    # MEGA T3 PRO 30
    q8, m8 = extract_search_query_and_model("DAW SPLIT AC MEGA T3 PRO INVERTER 30", "Dawlance")
    assert "MEGA" in m8.upper()
    assert "T3" in m8.upper()
    assert "30" in m8

    # Existing model-code products must NOT be affected
    q_gree, m_gree = extract_search_query_and_model("Gree Inverter 1.5 Ton GS-18PITH11W", "Gree")
    assert q_gree == "18PITH11W"


def test_keyword_match_mode() -> None:
    """Verify keyword match mode: ALL keywords must appear in seller title."""
    # AVANTE 30 CLASSIC — all keywords match
    assert is_strict_model_match(
        "Dawlance Avante Inverter 1.5 Ton Classic Gold", "AVANTE 30 CLASSIC"
    )
    # AVANTE 30 CLASSIC must reject ELEGANT
    assert not is_strict_model_match(
        "Dawlance Avante Inverter 1.5 Ton Elegant Silver", "AVANTE 30 CLASSIC"
    )
    # AVANTE 30 ELEGANT — correct match
    assert is_strict_model_match(
        "Dawlance Avante Inverter 1.5 Ton Elegant Silver", "AVANTE 30 ELEGANT"
    )

    # CHROME 30 WHITE vs CHROME 45 COPPER — capacity isolation
    assert is_strict_model_match(
        "Dawlance Chrome Inverter 1.5 Ton White", "CHROME 30 WHITE"
    )
    assert not is_strict_model_match(
        "Dawlance Chrome+ Inverter 2 Ton Copper", "CHROME 30 WHITE"
    )

    # ENERCON X 15 — X is required
    assert is_strict_model_match(
        "Dawlance Enercon X Inverter 1 Ton", "ENERCON X 15"
    )


def test_keyword_match_t3_isolation() -> None:
    """Verify T3 isolation: non-T3 target rejects T3 listings and vice versa."""
    # SPRINTER 30 (non-T3) must reject T3 listing
    assert not is_strict_model_match(
        "Dawlance Sprinter T3 X Inverter 1.5 Ton", "SPRINTER 30"
    )
    # SPRINTER 30 (non-T3) matches non-T3 listing
    assert is_strict_model_match(
        "Dawlance Sprinter Inverter 1.5 Ton", "SPRINTER 30"
    )

    # SPRINTER T3 X 30 (T3 product) must reject non-T3 listing
    assert not is_strict_model_match(
        "Dawlance Sprinter Inverter 1.5 Ton", "SPRINTER T3 X 30"
    )
    # SPRINTER T3 X 30 matches T3 listing
    assert is_strict_model_match(
        "Dawlance Sprinter T3 X Inverter 1.5 Ton", "SPRINTER T3 X 30"
    )

    # MAGNA T3 30 MILKY — T3 is in target, must require T3 in seller
    assert is_strict_model_match(
        "Dawlance Magna T3 Inverter 1.5 Ton Milky White", "MAGNA T3 30 MILKY"
    )
    assert not is_strict_model_match(
        "Dawlance Magna Inverter 1.5 Ton Silver", "MAGNA T3 30 MILKY"
    )

    # Model-code T3 (Gree) should NOT be affected — T3 is auxiliary tag, soft match
    assert is_strict_model_match("Gree 12AITH21W-T3 Inverter AC", "12AITH21W")
    assert is_strict_model_match("Gree 12AITH21W Inverter AC", "12AITH21W-T3")


def test_hyphenated_numeric_skus_and_plus_models() -> None:
    """Verify Haier numeric hyphenated SKUs, pure numbers, and Dawlance '+' series."""
    # Haier washing machines: 100-1269 S6
    assert is_strict_model_match("HAIER AUTO W/M 100-1269 S6", "100-1269 S6")
    assert is_strict_model_match("Haier Automatic Washing Machine 100-1269 S6", "100-1269")
    # Capacity / model isolation: 100-1269 must not match 100-826
    assert not is_strict_model_match("HAIER AUTO W/M 100-826 S6", "100-1269 S6")

    # Haier spinners: 60-50, 80-60
    assert is_strict_model_match("HAIER SPINNER 60-50", "60-50")
    assert is_strict_model_match("HAIER SPINNER 80-60", "80-60")
    assert not is_strict_model_match("HAIER SPINNER 60-50", "80-60")

    # Pure numeric model codes: 1060, 183 S.S
    assert is_strict_model_match("DAW W/D 1060 W/O REF WHITE", "1060")
    assert is_strict_model_match("GABA NATIONAL R/F 183 S.S", "183 S.S")
    assert is_strict_model_match("Gaba National Refrigerator 183 SS", "183 S.S")

    # Dawlance ACs with '+' in series name
    assert is_strict_model_match(
        "DAW FLOOR STANDING GLAMOUR+ INVERTER 45", "GLAMOUR+ 45"
    )
    assert is_strict_model_match(
        "Dawlance Glamour Inverter 2 Ton", "GLAMOUR+ 45"
    )
    assert is_strict_model_match(
        "DAW SPLIT AC ECONO+ X INVERTER 15", "ECONO+ X 15"
    )
    assert is_strict_model_match(
        "DAW SPLIT AC MEGA T+ 10", "MEGA T+ 10"
    )


def test_multibrand_universal_capacity_mappings() -> None:
    """Verify Universal AC capacity structure (Gree, Haier, Orient, PEL, Kenwood) alongside Dawlance.

    Universal standard (BTU / 1,000):
    09/9 = 0.75 Ton, 12 = 1.0 Ton, 18 = 1.5 Ton, 24 = 2.0 Ton, 28/30 = 2.5 Ton

    Dawlance custom standard:
    10 = 0.75 Ton, 15 = 1.0 Ton, 20 = 1.25 Ton, 30 = 1.5 Ton, 45 = 2.0 Ton
    """
    # 1. Haier: 18 = 1.5 Ton, 12 = 1.0 Ton, 24 = 2.0 Ton
    assert is_strict_model_match("Haier Inverter 1.5 Ton Pearl White", "PEARL 18 WHITE", brand="Haier")
    assert is_strict_model_match("Haier Inverter 1.5Ton Pearl White", "PEARL 18 WHITE", brand="Haier")
    assert not is_strict_model_match("Haier Inverter 1.0 Ton Pearl White", "PEARL 18 WHITE", brand="Haier")
    assert not is_strict_model_match("Haier Inverter 2.0 Ton Pearl White", "PEARL 18 WHITE", brand="Haier")
    assert is_strict_model_match("Haier Inverter 1 Ton HSU-12HFP", "12HFP", brand="Haier")

    # 2. Gree: 09 = 0.75 Ton, 12 = 1.0 Ton, 24 = 2.0 Ton, 28/30 = 2.5 Ton
    assert is_strict_model_match("Gree Inverter AC 0.75 Ton Pular", "PULAR 09", brand="Gree")
    assert is_strict_model_match("Gree Inverter AC 1 Ton Fairy", "FAIRY 12", brand="Gree")
    assert is_strict_model_match("Gree Inverter AC 1.0 Ton Fairy", "FAIRY 12", brand="Gree")
    assert not is_strict_model_match("Gree Inverter AC 1.5 Ton Fairy", "FAIRY 12", brand="Gree")
    assert is_strict_model_match("Gree Inverter AC 2 Ton Airy", "AIRY 24", brand="Gree")
    assert is_strict_model_match("Gree Inverter AC 2.5 Ton Pular", "PULAR 28", brand="Gree")
    assert is_strict_model_match("Gree Inverter AC 2.5 Ton Pular", "PULAR 30", brand="Gree")
    # In Gree, 30 is 2.5 Ton — must reject 1.5 Ton!
    assert not is_strict_model_match("Gree Inverter AC 1.5 Ton Pular", "PULAR 30", brand="Gree")

    # 3. Orient: 18 = 1.5 Ton, 24 = 2.0 Ton
    assert is_strict_model_match("Orient Inverter 1.5 Ton Ultron", "ULTRON 18", brand="Orient")
    assert is_strict_model_match("Orient Inverter 2 Ton Ultron", "ULTRON 24", brand="Orient")
    assert is_strict_model_match("Orient Inverter 2.0 Ton Ultron", "ULTRON 24", brand="Orient")
    assert not is_strict_model_match("Orient Inverter 1.5 Ton Ultron", "ULTRON 24", brand="Orient")

    # 4. PEL: 18 = 1.5 Ton, 12 = 1.0 Ton
    assert is_strict_model_match("PEL Split AC 1.5 Ton Inverter Ace", "ACE 18", brand="PEL")
    assert not is_strict_model_match("PEL Split AC 1.0 Ton Inverter Ace", "ACE 18", brand="PEL")
    # Catalog extraction test for PEL explicit 1.5TON phrase
    q_pel, m_pel = extract_search_query_and_model("PEL SPLIT AC 1.5TON INVERTER ACE", "PEL")
    assert "18" in q_pel
    assert "18" in m_pel
    assert is_strict_model_match("PEL Split AC 1.5 Ton Inverter Ace", m_pel, brand="PEL")

    # 5. Kenwood: 18 = 1.5 Ton, 09 = 0.75 Ton
    assert is_strict_model_match("Kenwood Inverter 1.5 Ton eSmart", "ESMART 18", brand="Kenwood")
    assert is_strict_model_match("Kenwood Inverter 0.75 Ton eSmart", "ESMART 09", brand="Kenwood")
    assert not is_strict_model_match("Kenwood Inverter 1.0 Ton eSmart", "ESMART 09", brand="Kenwood")

    # 6. Disambiguation of '30' (Dawlance 1.5 Ton vs Gree/Universal 2.5 Ton)
    assert is_strict_model_match("Dawlance Avante Inverter 1.5 Ton Classic Gold", "AVANTE 30 CLASSIC", brand="Dawlance")
    assert not is_strict_model_match("Dawlance Avante Inverter 2.5 Ton Classic Gold", "AVANTE 30 CLASSIC", brand="Dawlance")
    assert is_strict_model_match("Gree Inverter AC 2.5 Ton Pular", "PULAR 30", brand="Gree")
    assert not is_strict_model_match("Gree Inverter AC 1.5 Ton Pular", "PULAR 30", brand="Gree")

    # 7. Brand auto-detection from title when brand arg is not explicitly provided
    assert is_strict_model_match("Haier Inverter 1.5 Ton Pearl White", "PEARL 18 WHITE")
    assert is_strict_model_match("Dawlance Avante Inverter 1.5 Ton Classic Gold", "AVANTE 30 CLASSIC")
    assert is_strict_model_match("Gree Inverter AC 1.0 Ton Fairy", "FAIRY 12")
    assert is_strict_model_match("Orient Inverter 2.0 Ton Ultron", "ULTRON 24")
    assert is_strict_model_match("Kenwood Inverter 1.5 Ton eSmart", "ESMART 18")


def test_generate_search_patterns_haier_washing_machine() -> None:
    patterns = generate_search_patterns("HAIER TOP LOAD HWM 120-826S6 GC WASHING MACHINE", brand="Haier")
    assert "tier_1" in patterns
    assert "tier_2" in patterns
    assert "tier_3" in patterns
    assert any("120-826S6 GC" in p for p in patterns["tier_1"])
    assert any("120-826S6" in p for p in patterns["tier_2"])
    # Tier 3 spaced/glued/prefixed
    assert any("120 826S6" in p for p in patterns["tier_3"])
    assert any("HWM" in p for p in patterns["tier_3"])


def test_generate_search_patterns_variant_preservation() -> None:
    # WB / GB hardware variant code must NOT be stripped from bare stem
    patterns = generate_search_patterns("HAIER WASHING MACHINE HWM 80-1217WB", brand="Haier")
    assert any("80-1217WB" in p for p in patterns["tier_1"])
    assert any("80-1217WB" in p for p in patterns["tier_2"])
    # WB must not be dropped into just '80-1217'
    assert "80-1217" not in patterns["tier_2"]


def test_generate_search_patterns_tv() -> None:
    patterns = generate_search_patterns("HAIER LED 50S80EUX 4K SMART", brand="Haier")
    assert any("50S80EUX" in p for p in patterns["tier_1"])
    assert any("S80EUX" in p for p in patterns["tier_2"])
    assert any("50 S80EUX" in p for p in patterns["tier_3"])


def test_generate_search_patterns_gree_ac() -> None:
    patterns = generate_search_patterns("GREE SPLIT AC GS-12AITH21W-T3", brand="Gree")
    assert any("12AITH21W-T3" in p for p in patterns["tier_1"])
    assert any("12AITH21W" in p for p in patterns["tier_2"])
    assert any("GS-12AITH21W" in p or "GS-12AITH21W-T3" in p or "12AITH21" in p for p in patterns["tier_3"])


def test_generate_search_patterns_dawlance_series_ac() -> None:
    patterns = generate_search_patterns("DAWLANCE SPLIT AC MAGNA 30 INVERTER", brand="Dawlance")
    assert any("MAGNA 30" in p for p in patterns["tier_1"])
    assert any("MAGNA" in p for p in patterns["tier_2"])
    assert any("MAGNA 1.5 TON" in p for p in patterns["tier_3"])


def test_generate_search_patterns_refrigerator() -> None:
    patterns = generate_search_patterns("DAWLANCE REFRIGERATOR 276EBS SILVER", brand="Dawlance")
    assert any("276EBS" in p for p in patterns["tier_1"])
    assert any("276EBS" in p for p in patterns["tier_2"])
    assert any("276 EBS" in p or "276-EBS" in p for p in patterns["tier_3"])


# ==============================================================================
# PHASE 3: 4-SLOT STRUCTURAL EXTRACTION & NEGATIVE-COLLISION REFEREE TESTS
# ==============================================================================


def test_extract_product_slots_haier_washing_machine() -> None:
    title = "HAIER TOP LOAD HWM 120-826S6 GC WASHING MACHINE"
    slots = extract_product_slots(title, brand="Haier")
    assert slots.anchor == "120-826S6"
    assert "GC" in slots.residuals
    assert slots.guarded_facets.capacity in ("12KG", "12")


def test_referee_match_haier_washing_machine_synonyms() -> None:
    target_slots = extract_product_slots("HAIER TOP LOAD HWM 120-826S6 GC WASHING MACHINE", brand="Haier")
    decision1 = referee_match(target_slots, "Haier 120-826S6 Glass Door Washing Machine", brand="Haier")
    assert decision1.is_match is True
    assert "Accepted" in decision1.reason

    decision2 = referee_match(target_slots, "Haier HWM 120-826S6 GC Auto", brand="Haier")
    assert decision2.is_match is True


def test_referee_match_hardware_tub_rejection() -> None:
    # 80-1217WB (Single/White) vs 80-1217GB (Grey/Twin)
    target_slots = extract_product_slots("HAIER WASHING MACHINE HWM 80-1217WB", brand="Haier")
    assert target_slots.guarded_facets.tub_series == "WB"

    decision = referee_match(target_slots, "Haier Washing Machine HWM 80-1217GB", brand="Haier")
    assert decision.is_match is False
    assert "Hardware tub mismatch" in decision.reason or "Collision" in decision.reason


def test_referee_match_t3_isolation() -> None:
    # Non-T3 target strictly rejects T3 listings
    target_non_t3 = extract_product_slots("DAWLANCE SPLIT AC MAGNA 30 INVERTER", brand="Dawlance")
    assert target_non_t3.guarded_facets.t3 is False or target_non_t3.guarded_facets.t3 is None

    decision_rej = referee_match(target_non_t3, "Dawlance Magna Inverter AC 1.5 Ton T3", brand="Dawlance")
    assert decision_rej.is_match is False
    assert "T3 mismatch" in decision_rej.reason

    # T3 target strictly rejects non-T3 listings
    target_t3 = extract_product_slots("DAWLANCE SPLIT AC MAGNA T3 30 INVERTER", brand="Dawlance")
    assert target_t3.guarded_facets.t3 is True

    decision_rej_non_t3 = referee_match(target_t3, "Dawlance Magna Inverter AC 1.5 Ton", brand="Dawlance")
    assert decision_rej_non_t3.is_match is False
    assert "T3 mismatch" in decision_rej_non_t3.reason

    # T3 target matches T3 listing
    decision_acc_t3 = referee_match(target_t3, "Dawlance Magna 1.5 Ton T3 Inverter", brand="Dawlance")
    assert decision_acc_t3.is_match is True


def test_referee_match_tv_screen_size_collision() -> None:
    target_slots = extract_product_slots("HAIER LED 50S80EUX 4K SMART", brand="Haier")
    assert target_slots.guarded_facets.capacity in ("50INCH", "50")

    # 50 matches 50
    decision_pass = referee_match(target_slots, "Haier Smart 4K LED 50 S80EUX", brand="Haier")
    assert decision_pass.is_match is True

    # 50 strictly rejects 43
    decision_fail = referee_match(target_slots, "Haier Smart 4K LED 43S80EUX", brand="Haier")
    assert decision_fail.is_match is False
    assert "Capacity / screen size mismatch" in decision_fail.reason or "mismatch" in decision_fail.reason.lower()


def test_referee_match_refrigerator_color_families() -> None:
    target_slots = extract_product_slots("DAWLANCE REFRIGERATOR 276EBS SILVER", brand="Dawlance")
    assert target_slots.guarded_facets.color_family == "Grey / Silver"

    # Same family: Metallic Grey / Steel matches Silver
    decision_same_fam = referee_match(target_slots, "Dawlance Refrigerator 276EBS Metallic Grey", brand="Dawlance")
    assert decision_same_fam.is_match is True

    # Cross family: Black collides with Silver
    decision_black = referee_match(target_slots, "Dawlance Refrigerator 276EBS Midnight Black", brand="Dawlance")
    assert decision_black.is_match is False
    assert "Color collision" in decision_black.reason or "Color mismatch" in decision_black.reason

    # Model collision: 276EBS vs 276EPR
    decision_model = referee_match(target_slots, "Dawlance Refrigerator 276EPR RED", brand="Dawlance")
    assert decision_model.is_match is False


def test_referee_match_sub_series_integrity() -> None:
    # CHROME PRO vs CHROME: PRO is a required sub-series differentiator
    target_pro = extract_product_slots("DAWLANCE INVERTER CHROME PRO 30", brand="Dawlance")
    assert "PRO" in target_pro.series.upper()

    decision_missing_pro = referee_match(target_pro, "Dawlance Inverter AC Chrome 1.5 Ton", brand="Dawlance")
    assert decision_missing_pro.is_match is False
    assert "sub-series" in decision_missing_pro.reason.lower() or "missing" in decision_missing_pro.reason.lower()

    # AVANTE CLASSIC vs AVANTE ELEGANT
    target_classic = extract_product_slots("DAWLANCE AVANTE CLASSIC 30", brand="Dawlance")
    decision_diff_series = referee_match(target_classic, "Dawlance Avante Elegant 1.5 Ton", brand="Dawlance")
    assert decision_diff_series.is_match is False


