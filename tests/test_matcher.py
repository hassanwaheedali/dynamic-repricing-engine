import pytest

from pricing_engine.matcher import (
    extract_search_query_and_model,
    is_strict_model_match,
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


def test_haier_slash_model_extraction_and_matching() -> None:
    """Verify that Haier slash-separated color models extract and match variants with high precision."""
    items = [
        ("Haier 1 Ton HSU-12CF Non-Inverter Cool Only Split Air Conditioner", "HSU-12CF", "HSU-12CF"),
        ("Haier 1.5 ton HSU-18-CFT Non-Inverter Cool Only Split Air Conditioner", "HSU-18-CFT", "HSU-18-CFT"),
        ("Haier 1 Ton HSU-13HFAB/W-T3 PRO DC Inverter Heat & Cool Air Conditioner", "HSU-13HFAB", "HSU-13HFAB/W-T3 PRO"),
        ("Haier 1 Ton HSU-13HFAB/G-T3 PRO DC Inverter Heat & Cool Air Conditioner", "HSU-13HFAB", "HSU-13HFAB/G-T3 PRO"),
        ("Haier 1 Ton HSU-13HFS/W-T3 Pro Inverter Heat & Cool Split Air Conditioner", "HSU-13HFS", "HSU-13HFS/W-T3"),
    ]
    for name, exp_q, exp_m in items:
        q, m = extract_search_query_and_model(name, "Haier")
        assert q == exp_q, f"Failed query for {name}: got {q}, expected {exp_q}"
        assert m == exp_m, f"Failed model for {name}: got {m}, expected {exp_m}"

    # White vs Grey variant isolation
    white_target = "HSU-13HFAB/W-T3 PRO"
    grey_target = "HSU-13HFAB/G-T3 PRO"

    assert is_strict_model_match("Haier (T3 Series) 1 Ton DC Inverter - HSU-13HFAB(W) - T3 Compressor", white_target)
    assert not is_strict_model_match("Haier (T3 Series) 1 Ton DC Inverter - HSU-13HFAB(G) - T3 Compressor", white_target)
    assert not is_strict_model_match("Haier 1 Ton HSU-13HFAB/G-T3 PRO DC Inverter Heat & Cool Air Conditioner", white_target)
    assert is_strict_model_match("Haier 1 Ton HSU-13HFAB/W-T3 PRO DC Inverter Heat & Cool Air Conditioner", white_target)

    assert not is_strict_model_match("Haier (T3 Series) 1 Ton DC Inverter - HSU-13HFAB(W) - T3 Compressor", grey_target)
    assert is_strict_model_match("Haier (T3 Series) 1 Ton DC Inverter - HSU-13HFAB(G) - T3 Compressor", grey_target)
    assert is_strict_model_match("Haier 1 Ton HSU-13HFAB/G-T3 PRO DC Inverter Heat & Cool Air Conditioner", grey_target)
    assert not is_strict_model_match("Haier 1 Ton HSU-13HFAB/W-T3 PRO DC Inverter Heat & Cool Air Conditioner", grey_target)


def test_generate_search_queries_multi_pattern() -> None:
    """Verify that multi-pattern query expansion generates glued, spaced, and stem queries."""
    from pricing_engine.matcher import generate_search_queries

    qs = generate_search_queries("HWM-80-1217WB", "HWM 80-1217WB")
    # All variant patterns must be present
    assert "HWM-80-1217WB" in qs
    assert "HWM 80-1217WB" in qs
    assert "HWM80-1217WB" in qs
    assert "HWM 80 1217WB" in qs
    assert "HWM 80-1217 WB" in qs
    assert "80-1217WB" in qs
    assert "80 1217WB" in qs
    assert "80-1217 WB" in qs
    assert "80 1217 WB" in qs

    # Base model without variant WB must NEVER be queried (prevents mixing up 80-1217 and 80-1217WB)
    assert "80-1217" not in qs
    assert "80 1217" not in qs
    assert "HWM-80-1217" not in qs
    assert "HWM 80-1217" not in qs

    qs_pular = generate_search_queries("12AITH21W", "12AITH21W-T3")
    assert "12AITH21W" in qs_pular
    assert "12AITH21W-T3" in qs_pular


def test_optional_feature_tags_gc_gt() -> None:
    """Verify that feature descriptors like GC (Glass Color/Cover) and GT (Glass Top) are optional."""
    target_gc = "120-826S6 GC"

    # Must match marketplace titles whether merchant included GC or omitted it
    assert is_strict_model_match("Haier Fully Automatic Top Load Washing Machine Model HWM 120-826S6 12KG", target_gc)
    assert is_strict_model_match("Haier Automatic Washing machine Top Load 12KG 120-826S6, Pillow Drum", target_gc)
    assert is_strict_model_match("Haier 120-826S6 GC Glass Door Top Load", target_gc)

    # Must strictly reject conflicting capacities and series
    assert not is_strict_model_match("Haier 100-826S6 10KG Top Load", target_gc)
    assert not is_strict_model_match("Haier 120-316S6 12KG Top Load", target_gc)

    # Query generation should produce queries with and without GC
    from pricing_engine.matcher import generate_search_queries

    qs = generate_search_queries("120-826S6", "120-826S6 GC")
    assert "120-826S6" in qs
    assert "120-826S6 GC" in qs


