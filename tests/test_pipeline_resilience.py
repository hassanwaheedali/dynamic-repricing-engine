"""Deep resilience and edge-case testing for Phase 1 pipeline.

Tests multi-angle variations:
1. User provides S.NO explicitly (e.g. 101, 102).
2. User provides S.No (lowercase 'o' or casing variants).
3. User provides string/alphanumeric S.NO ("SKU-001", "GREE-12A").
4. User does not provide S.NO column at all (auto-generation 1, 2, 3...).
5. User provides S.NO with empty/blank cells.
6. User provides custom extra columns (e.g. "Color", "Supplier").
7. Concurrent pipeline execution preserves deterministic row sequence.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from pricing_engine.models import ScrapeResult
from pricing_engine.pipeline import (
    _extract_sno,
    build_output_record,
    parse_product_input,
    run_pipeline,
)


def test_extract_sno_various_casings() -> None:
    assert _extract_sno({"S.NO": 10}, 1) == 10
    assert _extract_sno({"S.No": 20}, 1) == 20
    assert _extract_sno({"S. No": 30}, 1) == 30
    assert _extract_sno({"SNO": 40}, 1) == 40
    assert _extract_sno({"sno": 50}, 1) == 50
    assert _extract_sno({"Serial No": "A-1"}, 1) == "A-1"
    # Empty cell / NaN falls back to default
    assert _extract_sno({"S.NO": float("nan")}, 99) == 99
    assert _extract_sno({"S.NO": ""}, 99) == 99
    assert _extract_sno({"S.NO": None}, 99) == 99
    assert _extract_sno({}, 99) == 99


def test_extract_sno_handles_float_drift() -> None:
    # Float 1.0 converts to int 1
    assert _extract_sno({"S.No": 1.0}, 99) == 1
    # String float "2.0" converts to int 2
    assert _extract_sno({"S.NO": "2.0"}, 99) == 2
    # Alphanumeric string preserved
    assert _extract_sno({"sno": "SKU-99"}, 99) == "SKU-99"


def test_parse_product_input_with_explicit_sno() -> None:
    row = pd.Series(
        {
            "S.NO": 105,
            "Brand": "Gree",
            "Name": "Gree Split AC 12AITH21W",
            "Net Price": 140000,
            "Length": 87,
            "Width": 35.5,
            "Height": 92,
        }
    )
    product = parse_product_input(0, row)
    assert product.sno == 105
    assert product.brand == "Gree"
    assert product.length == 87.0


def test_parse_product_input_with_lowercase_sno() -> None:
    row = pd.Series(
        {
            "S.No": "GREE-01",
            "Brand": "Gree",
            "Name": "Gree Split AC 12AITH21W",
            "Net Price": 140000,
            "Length": 87,
            "Width": 35.5,
            "Height": 92,
        }
    )
    product = parse_product_input(4, row)
    assert product.sno == "GREE-01"


def test_parse_product_input_without_sno_column_defaults_to_1_indexed() -> None:
    row = pd.Series(
        {
            "Brand": "Dawlance",
            "Name": "Dawlance Refrigerator",
            "Net Price": 95000,
            "Length": 60,
            "Width": 60,
            "Height": 160,
        }
    )
    product = parse_product_input(0, row)
    assert product.sno == 1

    product_row_5 = parse_product_input(4, row)
    assert product_row_5.sno == 5


def test_build_output_record_guarantees_sno_present_and_clean() -> None:
    # 1. Product without S.NO in raw_row gets product.sno assigned to 'S.NO'
    product = parse_product_input(
        2,  # row index 2 -> sno = 3
        pd.Series(
            {
                "Brand": "Haier",
                "Name": "Haier Washing Machine",
                "Net Price": 80000,
                "Length": 60,
                "Width": 60,
                "Height": 85,
            }
        ),
    )

    from pricing_engine.calculator import calculate_cost_base, calculate_floors
    from pricing_engine.models import PlatformPricingResult

    floors = calculate_floors(calculate_cost_base(80000, 3500))
    dummy_res = PlatformPricingResult(
        min_price=90000,
        max_price=95000,
        final_price=92999,
        real_profit=3500,
        reason="Won",
        status="Won",
        effective_comm="10.00%",
    )

    rec = build_output_record(
        product=product,
        shipping=3500.0,
        floors=floors,
        baseline_calc=95000.0,
        alfa_res=dummy_res,
        digi_res=dummy_res,
    )

    # Must contain "S.NO" with value 3
    assert "S.NO" in rec
    assert rec["S.NO"] == 3


def test_build_output_record_normalizes_lowercase_sno_alias() -> None:
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.No": 999,
                "Brand": "Haier",
                "Name": "Haier Washer",
                "Net Price": 75000,
                "Length": 60,
                "Width": 60,
                "Height": 85,
            }
        ),
    )

    from pricing_engine.calculator import calculate_cost_base, calculate_floors
    from pricing_engine.models import PlatformPricingResult

    floors = calculate_floors(calculate_cost_base(75000, 3000))
    dummy_res = PlatformPricingResult(
        min_price=85000,
        max_price=90000,
        final_price=87999,
        real_profit=3000,
        reason="Won",
        status="Won",
        effective_comm="10.00%",
    )

    rec = build_output_record(
        product=product,
        shipping=3000.0,
        floors=floors,
        baseline_calc=88000.0,
        alfa_res=dummy_res,
        digi_res=dummy_res,
    )

    assert rec["S.NO"] == 999
    # The lower-case alias "S.No" must be removed to prevent duplicate columns
    assert "S.No" not in rec


def test_full_pipeline_with_various_sno_and_missing_sno(tmp_path: Path) -> None:
    """Test full pipeline run with a CSV having mixed S.NO (explicit, alphanumeric, empty)."""
    input_csv = tmp_path / "mixed_sno_catalog.csv"
    input_csv.write_text(
        "S.NO,Brand,Name,Net Price,Length,Width,Height,Custom Tag\n"
        "101,Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92,Special Edition\n"
        "SKU-99,Haier,Haier Washing Machine HW80,75000,60,60,85,In Stock\n"
        ",Dawlance,Dawlance Refrigerator 9170,110000,60,65,165,Best Seller\n",
        encoding="utf-8",
    )
    output_csv = tmp_path / "repriced_output.csv"

    mock_offers = ScrapeResult(offers=[], is_success=True, status_code=200)

    async def _run() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_offers),
            patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_offers),
        ):
            out_df = await run_pipeline(
                input_path=input_csv,
                output_path=output_csv,
                concurrency=2,
                verbose=False,
            )

            assert len(out_df) == 3
            # Check S.NO values
            assert str(out_df["S.NO"].iloc[0]) == "101"
            assert str(out_df["S.NO"].iloc[1]) == "SKU-99"
            # Row 3 with empty S.NO auto-filled with row number 3
            assert str(out_df["S.NO"].iloc[2]) == "3"
            # Custom tag column preserved
            assert out_df["Custom Tag"].iloc[0] == "Special Edition"
            # Pricing calculated (Monopoly since 0 offers)
            assert out_df["Final Price Alfa"].iloc[0] != ""
            assert out_df["Final Price Digi"].iloc[0] != ""

    asyncio.run(_run())


def test_full_pipeline_pure_clean_template_without_sno(tmp_path: Path) -> None:
    """Test full pipeline with clean 6-column template that has NO S.NO column."""
    input_csv = tmp_path / "pure_clean_template.csv"
    input_csv.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92\n"
        "Gree,GREE SPLIT AC 18AITH21W-T3,183000,104,39,103\n",
        encoding="utf-8",
    )
    export_dir = tmp_path / "structured_outputs"

    mock_offers = ScrapeResult(offers=[], is_success=True, status_code=200)

    async def _run() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_offers),
            patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_offers),
        ):
            out_df = await run_pipeline(
                input_path=input_csv,
                output_path=None,
                concurrency=2,
                verbose=False,
                use_structured_export=True,
                export_dir=export_dir,
            )

            assert len(out_df) == 2
            # S.NO automatically created as 1, 2
            assert "S.NO" in out_df.columns
            assert list(out_df["S.NO"]) == [1, 2]

            # Output files exist in export directory
            latest_file = export_dir / "pure_clean_template_repriced_latest.csv"
            assert latest_file.is_file()
            read_back = pd.read_csv(latest_file)
            assert "S.NO" in read_back.columns
            assert list(read_back["S.NO"]) == [1, 2]
            # Ensure S.NO is the first column in the exported CSV
            assert list(read_back.columns)[0] == "S.NO"

    asyncio.run(_run())


def test_format_export_sno() -> None:
    from pricing_engine.exporter import format_export_sno

    assert format_export_sno(1) == "1"
    assert format_export_sno(1.0) == "1"
    assert format_export_sno("2.0") == "2"
    assert format_export_sno("SKU-100") == "SKU-100"
    assert format_export_sno(None) == ""
    assert format_export_sno(float("nan")) == ""


def test_full_pipeline_lowercase_sno_first_column(tmp_path: Path) -> None:
    """Test when input has 'S.No' as first column, output standardizes to 'S.NO' in first column."""
    input_csv = tmp_path / "lowercase_sno_first.csv"
    input_csv.write_text(
        "S.No,Brand,Name,Net Price,Length,Width,Height\n"
        "10,Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92\n"
        "20,Haier,Haier Washing Machine,75000,60,60,85\n",
        encoding="utf-8",
    )
    output_csv = tmp_path / "standardized_output.csv"

    mock_offers = ScrapeResult(offers=[], is_success=True, status_code=200)

    async def _run() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_offers),
            patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_offers),
        ):
            out_df = await run_pipeline(
                input_path=input_csv,
                output_path=output_csv,
                concurrency=2,
                verbose=False,
            )

            assert list(out_df.columns)[0] == "S.NO"
            assert "S.No" not in out_df.columns
            assert list(out_df["S.NO"]) == [10, 20]

    asyncio.run(_run())


def test_haier_washer_hyphenated_and_spaced_matching() -> None:
    from pricing_engine.matcher import referee_match

    # 1. Spaced model prefix matching candidate with glued SKU
    t1 = "Haier HW 90-BP12357S8 Front Load Washing Machine"
    c1 = "Haier HW90-BP12357S8 9 KG Front Load Inverter Automatic Washing Machine"
    assert referee_match(t1, c1, brand="Haier").is_match is True

    # 2. Form factor Single Tub with promotional noise trailer
    t2 = "Haier HWM 130-1217 WB Single Tub Washing Machine"
    c2 = "Haier HWM 130-1217 13kg Top Load Washing Machine - Manual Control Washer | Big Capacity, Strong Performance, Home Use"
    assert referee_match(t2, c2, brand="Haier").is_match is True


def test_haier_lowercase_variant_tag_matching() -> None:
    from pricing_engine.matcher import referee_match

    # Lowercase color code 'ow' (Off White) matching HSU-14HFTEX-OW
    t = "14hft ow"
    c = "HAIER 1.25 TON HSU-14HFTEX-OW T3 PLUS INVERTER AIR CONDITIONER"
    assert referee_match(t, c, brand="Haier").is_match is True


def test_dawlance_refrigerator_soft_styling_optionality() -> None:
    from pricing_engine.matcher import referee_match

    # Soft styling trim (Chrome FH) omitted by seller for unique model stems
    t1 = "9173 WB Chrome FH"
    c1 = "Dawlance 9173WB 12 Cu Ft Coral Red Refrigerator"
    assert referee_match(t1, c1, brand="Dawlance").is_match is True

    t2 = "91999 WB Chrome FH"
    c2 = "Dawlance DW-91999 20 Cu Ft Coral Red Double Door Refrigerator"
    assert referee_match(t2, c2, brand="Dawlance").is_match is True

    t3 = "9140 WB LVS FH"
    c3 = "Dawlance REF-9140WB 8 Cu Ft Grey Double Door Refrigerator"
    assert referee_match(t3, c3, brand="Dawlance").is_match is True


def test_dawlance_refrigerator_series_collision_protection() -> None:
    from pricing_engine.matcher import referee_match

    # Distinct series (Avante, Acce, Graze) must never match Chrome model
    target = "9173 WB Chrome FH"
    cand_avante = "Dawlance 9173-WB-Avante+ 12 Cu Ft Cloud White Refrigerator"
    cand_acce = "Dawlance 9173LF-Acce-Pro 12 Cu Ft Crimson Red Refrigerator"
    cand_graze = "Dawlance 9173 12 Cu Ft Graze+ Gem Black Glass Refrigerator"

    assert referee_match(target, cand_avante, brand="Dawlance").is_match is False
    assert referee_match(target, cand_acce, brand="Dawlance").is_match is False
    assert referee_match(target, cand_graze, brand="Dawlance").is_match is False


def test_gree_ac_screen_size_guard_and_energy_rating() -> None:
    from pricing_engine.matcher import referee_match

    # Floor standing AC with AA+ energy rating must not be treated as screen size or series AA
    t1 = "GREE FLOOR STANDING 36TFIH AA+"
    c1 = "GREE 3 TON GF-36TFIH-T3 INVERTER FLOOR STANDING AIR CONDITIONER"
    assert referee_match(t1, c1, brand="Gree").is_match is True

    # 1.5T Pular with AAA energy badge must not fail on screen size or AAA series
    t2 = "GREE SPLIT AC 18PITH11G AAA"
    c2 = "Gree 1.5 Ton Pular Series GS-18PITH11G Inverter Heat and Cool Split Air Conditioner"
    assert referee_match(t2, c2, brand="Gree").is_match is True

    # 1T Airy Pro GS-12AITH24S-T3 must match without capacity screen size conflict
    t3 = "GREE SPLIT AC 12AITH24S-T3"
    c3 = "Gree 1 Ton Airy Pro GS-12AITH24S-T3 Inverter Heat & Cool Split Air Conditioner"
    assert referee_match(t3, c3, brand="Gree").is_match is True


def test_category1_soft_descriptor_sd_and_dd_isolation() -> None:
    """Category 1: Soft descriptors (SD, GD) match base model and fullforms, but reject opposing finishes (DD, INOX)."""
    from pricing_engine.matcher import referee_match

    target = "DMB-4467 SD"
    brand = "Dawlance"

    # Must match with-tag listing
    assert referee_match(target, "Dawlance Minibar DMB-4467 SD", brand=brand).is_match is True
    # Must match fullform expansion
    assert referee_match(target, "Dawlance Minibar DMB-4467 Single Door", brand=brand).is_match is True
    # Must match base model listing seamlessly (physically identical machine)
    assert referee_match(target, "Dawlance Minibar DMB-4467", brand=brand).is_match is True

    # Must strictly reject opposing door structure
    dec_dd = referee_match(target, "Dawlance Minibar DMB-4467 DD", brand=brand)
    assert dec_dd.is_match is False
    assert "Door structure collision" in dec_dd.reason

    dec_double = referee_match(target, "Dawlance Minibar DMB-4467 Double Door", brand=brand)
    assert dec_double.is_match is False
    assert "Door structure collision" in dec_double.reason


def test_category2_hardware_modifier_fallback_and_cross_check_notices() -> None:
    """Category 2: When target specifies T3, exact is preferred; if omitted, falls back with cross-check notices."""
    from unittest.mock import AsyncMock, MagicMock

    from pricing_engine.calculator import calculate_floors
    from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
    from pricing_engine.pipeline import _format_summary_price
    from pricing_engine.scraper import scrape_alfamall

    # 1. Exact Priority when T3 exists in marketplace
    async def _test_exact() -> None:
        base_resp = MagicMock()
        base_resp.status_code = 200
        base_resp.json.return_value = {
            "results": [
                {
                    "title": "GREE 18AITH24S Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "190,000"},
                    "vendor": {"name": "Base Store"},
                }
            ]
        }
        t3_resp = MagicMock()
        t3_resp.status_code = 200
        t3_resp.json.return_value = {
            "results": [
                {
                    "title": "GREE 18AITH24S-T3 Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "195,000"},
                    "vendor": {"name": "T3 Store"},
                }
            ]
        }
        mock_session = AsyncMock()
        mock_session.get.side_effect = [base_resp, t3_resp]

        res = await scrape_alfamall(
            mock_session,
            {"tier_1": ["18AITH24S"], "tier_2": ["18AITH24S-T3"], "tier_3": []},
            "18AITH24S-T3",
            brand="Gree",
        )
        assert [o.vendor_name for o in res.offers] == ["T3 Store"]
        assert res.active_modifier_fallback is None

    asyncio.run(_test_exact())

    # 2. Safe Fallback to Base Model when market omitted T3
    async def _test_fallback() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "GREE 18AITH24S Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "190,000"},
                    "vendor": {"name": "Base Store"},
                }
            ]
        }
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        res = await scrape_alfamall(
            mock_session,
            {"tier_1": ["18AITH24S"], "tier_2": [], "tier_3": []},
            "18AITH24S-T3",
            brand="Gree",
        )
        assert [o.vendor_name for o in res.offers] == ["Base Store"]
        assert res.active_modifier_fallback == "T3"

        # Evaluator reason annotation
        floors = calculate_floors(150000.0)
        alfa_eval = evaluate_alfa_pricing(floors, res)
        assert alfa_eval.status == "Competitive Win"
        assert "[FALLBACK MODEL: Target specified 'T3', but market listings omitted it; repriced against base model]" in alfa_eval.reason

        digi_eval = evaluate_digi_pricing(floors, res)
        assert "Safe Win" in digi_eval.status
        assert "[FALLBACK MODEL: Target specified 'T3', but market listings omitted it; repriced against base model]" in digi_eval.reason

        # Executive summary table badge
        disp_price = _format_summary_price(alfa_eval.final_price, min_comp_price=190000.0, reason=alfa_eval.reason)
        assert "CROSS-CHECK" in disp_price

    asyncio.run(_test_fallback())



