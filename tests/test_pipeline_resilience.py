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

