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




