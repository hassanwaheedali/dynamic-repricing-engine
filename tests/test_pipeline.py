import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from pricing_engine.matcher import extract_search_query_and_model, is_strict_model_match
from pricing_engine.models import ScrapedOffer, ScrapeResult
from pricing_engine.pipeline import (
    determine_risk_alert,
    format_export_price,
    parse_product_input,
    process_product_with_offers,
    run_pipeline,
)


def test_parse_product_input_clean() -> None:
    row = pd.Series(
        {
            "S.NO": 1,
            "Brand": "Gree",
            "Name ": "Gree Inverter AC 1.5 Ton GS-18PITH11W",
            "Length": 100,
            "Width": 35,
            "Height": 45,
            "Net Price": "150,000",
            "Profit": "5,000",
        }
    )
    product = parse_product_input(0, row)
    assert product.sno == 1
    assert product.brand == "Gree"
    assert product.name == "Gree Inverter AC 1.5 Ton GS-18PITH11W"
    assert product.length == 100.0
    assert product.width == 35.0
    assert product.height == 45.0
    assert product.net_price == 150000.0
    assert product.profit == 5000.0


def test_parse_product_input_missing_defaults() -> None:
    row = pd.Series(
        {
            "Brand": "Gree",
            "Name": "Generic AC",
            "Net Price": 70000,
        }
    )
    product = parse_product_input(2, row)
    assert product.sno == 3  # idx + 1
    assert product.length == 0.0
    assert product.profit == 500.0


def test_process_product_with_offers_monopoly() -> None:
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "Gree Fairy 12AITH21W",
                "Length": 90,
                "Width": 30,
                "Height": 30,
                "Net Price": 80000,
                "Profit": 3000,
            }
        ),
    )
    # Zero offers from both platforms
    alfa_offers: list[ScrapedOffer] = []
    digi_offers: list[ScrapedOffer] = []

    record = process_product_with_offers(product, alfa_offers, digi_offers)

    assert record["Final Price Alfa"] is not None
    assert record["Final Price Digi"] is not None
    assert record["Commision"] == "10.00%"
    assert record["Digi Effective Commision"] == "10.00%"
    assert "Monopoly" in record["Alfa Reason"]
    assert record["Alfa Real Profit"] >= 4000
    assert record["Digi Real Profit"] >= 4000


def test_build_output_record_contains_all_schema_columns() -> None:
    product = parse_product_input(
        0,
        pd.Series({"S.NO": 1, "Brand": "Gree", "Name ": "AC", "Net Price": 50000}),
    )
    record = process_product_with_offers(product, [], [])

    expected_cols = [
        "Shipping Estimate",
        "Commision",
        "Digi Effective Commision",
        "Total Without Profit",
        "Calculation",
        "Minimum Price Alfa",
        "Maximum Price Alfa",
        "Minimum Price Digi",
        "Maximum Price Digi",
        "Final Price Alfa",
        "Final Price Digi",
        "Alfa Real Profit",
        "Digi Real Profit",
        "Alfa Reason",
        "Digi Reason",
    ]
    for col in expected_cols:
        assert col in record


def test_total_without_profit_matches_digi_effective_commission() -> None:
    # Net Price = 415,000, Shipping = 15,291 -> Cost Base = 430,291
    # 8% breakeven: 430,291 / 0.92 = 467,707.6 -> 467,708
    # 10% breakeven: 430,291 / 0.90 = 478,101.1 -> 478,101
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "GREE FLOOR STANDING 36TFIH AA+",
                "Shipping Estimate": 15291,
                "Net Price": "415,000",
            }
        ),
    )
    # Competitor triggers 8% switch (e.g. at 475,000 which is between 8% floor 468,251 and 10% floor 478,657)
    digi_offer_8 = [
        ScrapedOffer(vendor_name="DigiSeller", price=475000.0, is_sold_out=False, raw_title="AC")
    ]
    record_8 = process_product_with_offers(product, [], digi_offer_8)

    assert record_8["Digi Effective Commision"] == "8.00%"
    assert record_8["Total Without Profit"] == 467708

    # When competitor on a standard product is above 10% floor and within profit cap -> 10% default tier
    prod_standard = parse_product_input(
        1,
        pd.Series(
            {
                "S.NO": 2,
                "Brand": "Gree",
                "Name ": "GREE SPLIT AC 18AITH21W",
                "Shipping Estimate": 5000,
                "Net Price": "140,000",
            }
        ),
    )
    # Cost base = 145,000, 10% floor = 161,667. Competitor at 165,000 is viable at 10% tier
    digi_offer_10 = [
        ScrapedOffer(
            vendor_name="DigiSellerHigh", price=165000.0, is_sold_out=False, raw_title="AC"
        )
    ]
    record_10 = process_product_with_offers(prod_standard, [], digi_offer_10)

    assert record_10["Digi Effective Commision"] == "10.00%"
    assert record_10["Total Without Profit"] == 161111


def test_exact_real_profit_formula_matches_user_bank_payout() -> None:
    # Net Price = 415,000, Shipping = 15,291 -> Cost Base = 430,291
    # If Alfa price is 479,299 at 10%:
    # Profit = (479,299 * 0.90) - 430,291 = 431,369.1 - 430,291 = 1,078
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "FS 36TFIH",
                "Shipping Estimate": 15291,
                "Net Price": 415000,
            }
        ),
    )
    alfa_offers = [
        ScrapedOffer(vendor_name="Nasim", price=479499.0, is_sold_out=False, raw_title="AC")
    ]
    digi_offers = [
        ScrapedOffer(vendor_name="Scroll", price=489999.0, is_sold_out=False, raw_title="AC")
    ]

    record = process_product_with_offers(product, alfa_offers, digi_offers)

    # Alfa undercut Nasim (479,499) to 479,299 -> Profit = 1,078
    assert record["Final Price Alfa"] == 479299
    assert record["Alfa Real Profit"] == 1078

    # Digi caps inflated Scroll (489,999) at Default 10% Tier sweet-spot (~Rs. 10,000 profit):
    # Selling price 478,999 -> Profit = (478,999 * 0.92) - 430,291 = 10,388
    assert record["Final Price Digi"] == 478999
    assert record["Digi Real Profit"] == 10388
    assert record["Digi Effective Commision"] == "10.00%"


def test_ui_rendering_functions_execute_cleanly(tmp_path: Path) -> None:
    from pricing_engine.calculator import calculate_cost_base, calculate_floors
    from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
    from pricing_engine.pipeline import (
        render_audit_card,
        render_finish_banner,
        render_start_banner,
        render_summary_table,
    )

    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "FS 36TFIH AA+",
                "Shipping Estimate": 15291,
                "Net Price": 415000,
                "Length": 127,
                "Width": 43,
                "Height": 200,
            }
        ),
    )
    floors = calculate_floors(calculate_cost_base(product.net_price, 15291))
    alfa_res = evaluate_alfa_pricing(floors, [])
    digi_res = evaluate_digi_pricing(floors, [])

    # Test audit card rendering without raising exceptions
    render_audit_card(
        product=product,
        shipping=15291.0,
        floors=floors,
        baseline_calc=482999.0,
        target_model="GS-36TFIH",
        alfa_offers=[],
        digi_offers=[],
        alfa_res=alfa_res,
        digi_res=digi_res,
    )

    # Test start and finish banners
    in_p = Path("tests/fixtures/Gree_Uploading_on_DigiMall_and_Price.csv")
    out_p = Path("data/outputs/Gree_AC_repriced_latest.csv")
    render_start_banner(in_p, out_p, 25, 3)
    render_finish_banner(out_p, 25, 5.23)

    # Test summary table with mixed (active + skip) rows
    records = [
        {
            "S.NO": 1,
            "Name ": "GREE FLOOR STANDING 36TFIH",
            "Net Price": 415000,
            "Shipping Estimate": 15291,
            "Final Price Alfa": 482999,
            "Alfa Real Profit": 4408,
            "Final Price Digi": 482999,
            "Digi Effective Commision": "10.00%",
            "Digi Real Profit": 14068,
        },
        {
            "S.NO": 2,
            "Name ": "GREE SPLIT AC 18AITH21W-T3",
            "Net Price": 140000,
            "Shipping Estimate": 5292,
            "Final Price Alfa": None,
            "Alfa Real Profit": 0,
            "Final Price Digi": 168499,
            "Digi Effective Commision": "8.00%",
            "Digi Real Profit": 9727,
        },
    ]
    render_summary_table(records)


def test_pipeline_csv_index_preservation_when_completion_is_unordered(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"

    # Create dummy 3-item CSV
    df = pd.DataFrame(
        [
            {"S.NO": 1, "Brand": "Gree", "Name ": "Product A", "Net Price": 50000},
            {"S.NO": 2, "Brand": "Gree", "Name ": "Product B", "Net Price": 60000},
            {"S.NO": 3, "Brand": "Gree", "Name ": "Product C", "Net Price": 70000},
        ]
    )
    df.to_csv(input_csv, index=False)

    # Mock process_item_async to simulate reverse or scrambled completion times
    delays = {1: 0.2, 2: 0.05, 3: 0.1}

    async def mock_process(
        product: Any,
        session: Any,
        semaphore: Any,
        render_lock: Any = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        await asyncio.sleep(delays.get(product.sno, 0.01))
        return {
            "S.NO": product.sno,
            "Final Price Alfa": 55000,
            "Final Price Digi": 55000,
        }

    with patch("pricing_engine.pipeline.process_item_async", side_effect=mock_process):
        asyncio.run(
            run_pipeline(input_path=input_csv, output_path=output_csv, concurrency=3, verbose=False)
        )

    out_df = pd.read_csv(output_csv)
    # Original sequence S.NO: 1, 2, 3 must be strictly preserved!
    assert list(out_df["S.NO"]) == [1, 2, 3]
    # Temporary sorting key must be removed
    assert "_original_idx" not in out_df.columns


def test_process_product_with_offers_server_down_isolation() -> None:
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "Gree Split AC 12AITH21W",
                "Length": 90,
                "Width": 30,
                "Height": 30,
                "Net Price": 80000,
                "Profit": 3000,
            }
        ),
    )
    # Alfa is down (500), Digi is live with 0 offers (Monopoly)
    alfa_down = ScrapeResult(
        offers=[], is_success=False, status_code=500, error_detail="HTTP 500: Server Error"
    )
    digi_ok = ScrapeResult(offers=[], is_success=True, status_code=200)

    record = process_product_with_offers(product, alfa_down, digi_ok)

    # AlfaMall must be Server Down (SKIP / NaN, real profit 0)
    assert record["Final Price Alfa"] is None
    assert record["Alfa Real Profit"] == 0
    assert "unreachable" in record["Alfa Reason"].lower()
    assert "server is down" in record["Alfa Reason"].lower()

    # DigiMall must be unaffected and win legitimate Monopoly
    assert record["Final Price Digi"] is not None
    assert record["Digi Real Profit"] >= 4000
    assert "Monopoly" in record["Digi Reason"]


def test_process_product_with_offers_both_servers_down() -> None:
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "Gree Split AC 12AITH21W",
                "Length": 90,
                "Width": 30,
                "Height": 30,
                "Net Price": 80000,
                "Profit": 3000,
            }
        ),
    )
    alfa_down = ScrapeResult(
        offers=[], is_success=False, status_code=502, error_detail="Bad Gateway"
    )
    digi_down = ScrapeResult(
        offers=[], is_success=False, status_code=504, error_detail="Gateway Timeout"
    )

    record = process_product_with_offers(product, alfa_down, digi_down)

    assert record["Final Price Alfa"] is None
    assert record["Final Price Digi"] is None
    assert record["Alfa Real Profit"] == 0
    assert record["Digi Real Profit"] == 0
    assert "unreachable" in record["Alfa Reason"].lower()
    assert "server is down" in record["Alfa Reason"].lower()
    assert "unreachable" in record["Digi Reason"].lower()
    assert "server is down" in record["Digi Reason"].lower()


def test_format_export_price_integers_and_nulls() -> None:
    assert format_export_price(None) == ""
    assert format_export_price(float("nan")) == ""
    assert format_export_price("nan") == ""
    assert format_export_price("NaN") == ""
    assert format_export_price("") == ""
    assert format_export_price(165000) == "165000"
    assert format_export_price(165000.0) == "165000"
    assert format_export_price("165,000") == "165000"
    assert format_export_price("165000.0") == "165000"
    assert format_export_price("invalid") == ""


def test_pipeline_csv_export_pure_integers_without_float_drift(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"

    # Row 1 will have price, Row 2 will have None (Server Down simulation)
    df = pd.DataFrame(
        [
            {"S.NO": 1, "Brand": "Gree", "Name ": "Product A", "Net Price": 50000},
            {"S.NO": 2, "Brand": "Gree", "Name ": "Product B", "Net Price": 60000},
        ]
    )
    df.to_csv(input_csv, index=False)

    async def mock_process(
        product: Any,
        session: Any,
        semaphore: Any,
        render_lock: Any = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        if product.sno == 1:
            return {
                "S.NO": product.sno,
                "Final Price Alfa": 55000,
                "Final Price Digi": 56000,
                "Total Without Profit": 52000,
                "Calculation": 55000,
                "Minimum Price Alfa": 53000,
                "Maximum Price Alfa": 58000,
                "Minimum Price Digi": 54000,
                "Maximum Price Digi": 59000,
                "Alfa Real Profit": 2000,
                "Digi Real Profit": 3000,
                "Alfa Reason": "Undercut",
                "Digi Reason": "Undercut",
            }
        else:
            return {
                "S.NO": product.sno,
                "Final Price Alfa": None,
                "Final Price Digi": None,
                "Total Without Profit": 63000,
                "Calculation": 66000,
                "Minimum Price Alfa": None,
                "Maximum Price Alfa": None,
                "Minimum Price Digi": None,
                "Maximum Price Digi": None,
                "Alfa Real Profit": 0,
                "Digi Real Profit": 0,
                "Alfa Reason": "Server Down / Unreachable (HTTP 500)",
                "Digi Reason": "Server Down / Unreachable (HTTP 500)",
            }

    with patch("pricing_engine.pipeline.process_item_async", side_effect=mock_process):
        asyncio.run(
            run_pipeline(input_path=input_csv, output_path=output_csv, concurrency=2, verbose=False)
        )

    # Read raw text lines of output CSV to inspect exact string formatting
    csv_text = output_csv.read_text(encoding="utf-8")
    lines = [line.strip() for line in csv_text.strip().splitlines()]
    header = lines[0].split(",")
    row1 = lines[1].split(",")
    row2 = lines[2].split(",")

    row1_dict = dict(zip(header, row1, strict=True))
    row2_dict = dict(zip(header, row2, strict=True))

    # Row 1 should have pure integer strings (no .0 float drift)
    assert row1_dict["Final Price Alfa"] == "55000"
    assert row1_dict["Final Price Digi"] == "56000"
    assert row1_dict["Minimum Price Alfa"] == "53000"
    assert row1_dict["Alfa Real Profit"] == "2000"

    # Row 2 should have empty string "" for None prices (not NaN or null)
    assert row2_dict["Final Price Alfa"] == ""
    assert row2_dict["Final Price Digi"] == ""
    assert row2_dict["Minimum Price Alfa"] == ""
    assert row2_dict["Alfa Real Profit"] == "0"


def test_render_audit_card_and_summary_with_server_down() -> None:
    from pricing_engine.calculator import calculate_cost_base, calculate_floors
    from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
    from pricing_engine.pipeline import render_audit_card, render_summary_table

    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "Gree Split AC 12AITH21W",
                "Shipping Estimate": 4000,
                "Net Price": 150000,
            }
        ),
    )
    floors = calculate_floors(calculate_cost_base(product.net_price, 4000))
    down_alfa = ScrapeResult(offers=[], is_success=False, status_code=500, error_detail="HTTP 500")
    down_digi = ScrapeResult(offers=[], is_success=False, status_code=502, error_detail="HTTP 502")

    alfa_res = evaluate_alfa_pricing(floors, down_alfa)
    digi_res = evaluate_digi_pricing(floors, down_digi)

    # Must execute and render without any exception
    render_audit_card(
        product=product,
        shipping=4000.0,
        floors=floors,
        baseline_calc=171111.0,
        target_model="12AITH21W",
        alfa_offers=down_alfa,
        digi_offers=down_digi,
        alfa_res=alfa_res,
        digi_res=digi_res,
    )

    records = [
        {
            "S.NO": 1,
            "Name ": "Gree Split AC 12AITH21W",
            "Net Price": 150000,
            "Shipping Estimate": 4000,
            "Final Price Alfa": None,
            "Alfa Real Profit": 0,
            "Alfa Reason": "Server Down / Unreachable (HTTP 500)",
            "Final Price Digi": None,
            "Digi Real Profit": 0,
            "Digi Reason": "Server Down / Unreachable (HTTP 502)",
            "Digi Effective Commision": "10.00%",
        }
    ]
    render_summary_table(records)


def test_determine_risk_alert_states() -> None:
    from pricing_engine.models import PlatformPricingResult

    # 1. SERVER_DOWN: status is Server Down or final_price is None or real_profit is None
    down_res = PlatformPricingResult(
        min_price=None,
        max_price=None,
        final_price=None,
        real_profit=0,
        status="Server Down / Unreachable",
        reason="Error",
    )
    assert determine_risk_alert(down_res) == "SERVER_DOWN"

    null_profit_res = PlatformPricingResult(
        min_price=None,
        max_price=None,
        final_price=None,
        real_profit=0,
        status="Some Status",
        reason="Error",
    )
    assert determine_risk_alert(null_profit_res) == "SERVER_DOWN"

    # 2. NEGATIVE_MARGIN: profit <= 0 when final_price is present
    loss_res = PlatformPricingResult(
        min_price=100000,
        max_price=120000,
        final_price=105000,
        real_profit=-500,
        status="Manual Loss",
        reason="Underpriced",
    )
    assert determine_risk_alert(loss_res) == "NEGATIVE_MARGIN"

    zero_res = PlatformPricingResult(
        min_price=100000,
        max_price=120000,
        final_price=105000,
        real_profit=0,
        status="Zero Margin",
        reason="Breakeven",
    )
    assert determine_risk_alert(zero_res) == "NEGATIVE_MARGIN"

    # 3. SAFE_FALLBACK: all competitors below floor
    fallback_res = PlatformPricingResult(
        min_price=100000,
        max_price=120000,
        final_price=110000,
        real_profit=1950,
        status="Safe Fallback",
        reason="Fallback price",
    )
    assert determine_risk_alert(fallback_res) == "SAFE_FALLBACK"

    # 4. THIN_BUFFER: 0 < profit < 700 (courier packaging re-weighing risk)
    thin_res = PlatformPricingResult(
        min_price=100000,
        max_price=120000,
        final_price=105000,
        real_profit=502,
        status="Competitive Win",
        reason="Undercut",
    )
    assert determine_risk_alert(thin_res) == "THIN_BUFFER"

    # 5. NONE: profit >= 700
    healthy_res = PlatformPricingResult(
        min_price=100000,
        max_price=120000,
        final_price=105000,
        real_profit=1078,
        status="Competitive Win",
        reason="Undercut",
    )
    assert determine_risk_alert(healthy_res) == "NONE"


def test_build_output_record_includes_risk_alerts() -> None:
    product = parse_product_input(
        0,
        pd.Series({"S.NO": 1, "Brand": "Gree", "Name ": "AC", "Net Price": 50000}),
    )
    record = process_product_with_offers(product, [], [])
    assert "Alfa Risk Alert" in record
    assert "Digi Risk Alert" in record
    valid_alerts = {"NONE", "THIN_BUFFER", "SAFE_FALLBACK", "SERVER_DOWN", "NEGATIVE_MARGIN"}
    assert record["Alfa Risk Alert"] in valid_alerts
    assert record["Digi Risk Alert"] in valid_alerts


def test_render_summary_table_risk_visuals() -> None:
    from pricing_engine.pipeline import render_summary_table

    records = [
        {
            "S.NO": 1,
            "Name ": "GREE SPLIT AC 12AITH21W-T3",
            "Net Price": 120000,
            "Shipping Estimate": 4000,
            "Final Price Alfa": 145999,
            "Alfa Real Profit": 1950,
            "Alfa Reason": "Safe Fallback: all competitors below floor",
            "Alfa Risk Alert": "SAFE_FALLBACK",
            "Final Price Digi": 143899,
            "Digi Real Profit": 578,
            "Digi Reason": "Emergency 8% switch: undercut viable seller",
            "Digi Effective Commision": "8.00%",
            "Digi Risk Alert": "THIN_BUFFER",
        },
        {
            "S.NO": 2,
            "Name ": "GREE SPLIT AC 24AITH21W",
            "Net Price": 200000,
            "Shipping Estimate": 6000,
            "Final Price Alfa": 235999,
            "Alfa Real Profit": 6500,
            "Alfa Reason": "Undercut competitor",
            "Alfa Risk Alert": "NONE",
            "Final Price Digi": 234999,
            "Digi Real Profit": 10388,
            "Digi Reason": "Capped at sweet-spot (~Rs. 10,000 profit)",
            "Digi Effective Commision": "10.00%",
            "Digi Risk Alert": "NONE",
        },
        {
            "S.NO": 3,
            "Name ": "GREE FLOOR STANDING 36TFIH",
            "Net Price": 400000,
            "Shipping Estimate": 15000,
            "Final Price Alfa": None,
            "Alfa Real Profit": 0,
            "Alfa Reason": "Server Down / Unreachable (HTTP 500)",
            "Alfa Risk Alert": "SERVER_DOWN",
            "Final Price Digi": 450000,
            "Digi Real Profit": -200,
            "Digi Reason": "Corrupt cost base margin loss",
            "Digi Effective Commision": "10.00%",
            "Digi Risk Alert": "NEGATIVE_MARGIN",
        },
        {
            "S.NO": 4,
            "Name ": "GREE SPLIT AC 18AITH24",
            "Net Price": 160000,
            "Shipping Estimate": 5000,
            "Final Price Alfa": None,
            "Alfa Real Profit": 0,
            "Alfa Reason": "Skip: all competitors unviable",
            "Alfa Risk Alert": "SERVER_DOWN",
            "Final Price Digi": None,
            "Digi Real Profit": 0,
            "Digi Reason": "Skip: all competitors unviable",
            "Digi Effective Commision": "10.00%",
            "Digi Risk Alert": "SERVER_DOWN",
        },
    ]

    # Verify rendering completes cleanly without raising any exceptions
    render_summary_table(records)


def test_pipeline_csv_export_includes_risk_alerts_without_ansi_leakage(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"

    df = pd.DataFrame(
        [
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "Item 1",
                "Length": 100,
                "Width": 50,
                "Height": 40,
                "Net Price": 100000,
                "Profit": 4000,
            },
            {
                "S.NO": 2,
                "Brand": "Gree",
                "Name ": "Item 2",
                "Length": 100,
                "Width": 50,
                "Height": 40,
                "Net Price": 120000,
                "Profit": 4000,
            },
        ]
    )
    df.to_csv(input_csv, index=False)

    async def mock_process(
        product: Any,
        session: Any,
        semaphore: Any,
        render_lock: Any = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        if product.sno == 1:
            return {
                "S.NO": 1,
                "Final Price Alfa": 115999,
                "Final Price Digi": 114899,
                "Alfa Real Profit": 520,
                "Digi Real Profit": 1050,
                "Alfa Reason": "Undercut seller",
                "Digi Reason": "Undercut seller",
                "Alfa Risk Alert": "THIN_BUFFER",
                "Digi Risk Alert": "NONE",
            }
        return {
            "S.NO": 2,
            "Final Price Alfa": 140999,
            "Final Price Digi": None,
            "Alfa Real Profit": 1950,
            "Digi Real Profit": 0,
            "Alfa Reason": "Safe Fallback: all below floor",
            "Digi Reason": "Server Down / Unreachable",
            "Alfa Risk Alert": "SAFE_FALLBACK",
            "Digi Risk Alert": "SERVER_DOWN",
        }

    with patch("pricing_engine.pipeline.process_item_async", side_effect=mock_process):
        asyncio.run(
            run_pipeline(input_path=input_csv, output_path=output_csv, concurrency=2, verbose=False)
        )

    csv_text = output_csv.read_text(encoding="utf-8")
    lines = [line.strip() for line in csv_text.strip().splitlines()]
    header = lines[0].split(",")

    # Verify risk alert columns are at the end of the CSV header
    assert "Alfa Risk Alert" in header
    assert "Digi Risk Alert" in header
    assert header[-2] == "Alfa Risk Alert"
    assert header[-1] == "Digi Risk Alert"

    # Verify rows contain exact clean string values
    row1 = dict(zip(header, lines[1].split(","), strict=True))
    row2 = dict(zip(header, lines[2].split(","), strict=True))

    assert row1["Alfa Risk Alert"] == "THIN_BUFFER"
    assert row1["Digi Risk Alert"] == "NONE"
    assert row2["Alfa Risk Alert"] == "SAFE_FALLBACK"
    assert row2["Digi Risk Alert"] == "SERVER_DOWN"

    # Absolute verification: NO Rich/ANSI markup in entire CSV content
    assert "[" not in csv_text
    assert "]" not in csv_text
    assert "bold" not in csv_text
    assert "red" not in csv_text
    assert "green" not in csv_text
    assert "yellow" not in csv_text


def test_item_3_slash_expansion_digimall_reprice_win() -> None:
    """Verify Item #3 (12AITH24S-T3 Silver) matches GS-12AITH24W/S on DigiMall.

    Tests that slash variant expansion successfully extracts competitors and
    triggers an Emergency 8% Bank Switch undercutting Rs. 193,999 to Rs. 193,899,
    yielding +Rs. 2,409 healthy net profit instead of false Monopoly fallback.
    """
    product = parse_product_input(
        2,
        pd.Series(
            {
                "S.NO": 3,
                "Brand": "Gree",
                "Name ": "GREE SPLIT AC 12AITH24S-T3",
                "Length": 87,
                "Width": 35.5,
                "Height": 92,
                "Net Price": 172000,
                "Profit": 4000,
            }
        ),
    )

    digi_offers = [
        ScrapedOffer(
            vendor_name="Musab Mall",
            price=193999.0,
            is_sold_out=False,
            raw_title="GREE Airy Pro 1 TON Split AC Inverter G-Boost AI T3 GS-12AITH24W/S",
        ),
        ScrapedOffer(
            vendor_name="Tech House",
            price=193999.0,
            is_sold_out=False,
            raw_title="GREE Airy Pro 1 TON Split AC Inverter G-Boost AI T3 GS-12AITH24W/S",
        ),
        ScrapedOffer(
            vendor_name="YZ International",
            price=194099.0,
            is_sold_out=False,
            raw_title="GREE Airy Pro 1 TON Split AC Inverter G-Boost AI T3 GS-12AITH24W/S",
        ),
    ]

    record = process_product_with_offers(product, alfa_offers=[], digi_offers=digi_offers)

    # 1. Winning price undercuts Musab Mall (193,999) to 193,499 (Adaptive undercut via dynamic glide)
    assert record["Final Price Digi"] == 193499

    # 2. Commission switched to 8.00% Emergency Tier
    assert record["Digi Effective Commision"] == "8.00%"

    # 3. Real Profit calculated: (193,499 * 0.92) - 175,978 = +2,041
    assert record["Digi Real Profit"] == 2041

    # 4. Reason documents the 8% switch undercut
    assert (
        "8% bank rate" in record["Digi Reason"].lower()
        or "emergency 8%" in record["Digi Reason"].lower()
    )

    # 5. Risk Alert is NONE (Healthy margin >= 700)
    assert record["Digi Risk Alert"] == "NONE"


def test_item_17_zith2_rejects_cheaper_zith1_competitor() -> None:
    """Verify Item #17 (GS-12ZITH2W-T3) isolates from cheaper Gen 1 (ZITH1) listings.

    Tests that when scraping market offers for 12ZITH2W, any cheaper GS-12ZITH1W
    offers (which would otherwise trigger false undercuts or false loss flags)
    are strictly rejected by the matcher, ensuring only genuine GS-12ZITH2W
    offers are repriced against.
    """
    product = parse_product_input(
        16,
        pd.Series(
            {
                "S.NO": 17,
                "Brand": "Gree",
                "Name ": "GREE SPLIT AC GS-12ZITH2W-T3",
                "Length": 87,
                "Width": 35.5,
                "Height": 92,
                "Net Price": 133147,
                "Profit": 4000,
            }
        ),
    )

    _, model_code = extract_search_query_and_model(product.name, brand=product.brand)

    raw_offers = [
        # Cheaper Gen 1 offer that must be filtered out
        ScrapedOffer(
            vendor_name="Cheap Seller Gen1",
            price=130000.0,
            is_sold_out=False,
            raw_title="Gree Zeno 1 Ton GS-12ZITH1W Inverter",
        ),
        # Real Gen 2 offer that must be retained
        ScrapedOffer(
            vendor_name="Legit Seller Gen2",
            price=153999.0,
            is_sold_out=False,
            raw_title="Gree Zeno 1 Ton GS-12ZITH2W Inverter",
        ),
    ]

    # Scraper strictly filters by model match
    filtered_offers = [o for o in raw_offers if is_strict_model_match(o.raw_title, model_code)]
    assert len(filtered_offers) == 1
    assert filtered_offers[0].vendor_name == "Legit Seller Gen2"

    record = process_product_with_offers(
        product, alfa_offers=filtered_offers, digi_offers=filtered_offers
    )

    # AlfaMall undercuts Gen 2 (153,999 -> Tier 4 adaptive undercut 153,799), completely ignoring Gen 1 (130,000)
    assert record["Final Price Alfa"] == 153799
    assert "Legit Seller Gen2" in record["Alfa Reason"]
    assert "Cheap Seller Gen1" not in record["Alfa Reason"]


def test_item_22_pular_batch_slash_digimall_reprice_win() -> None:
    """Verify Item #22 (GS-24PITH15G-T3) matches GS-24PITH15/17G on DigiMall.

    Tests that shared-color batch expansion (GS-24PITH15/17G) matches Grey 15G,
    strictly rejects White 15W, and undercuts Tech House (247,999) to win
    at 8% bank rate with healthy net profit instead of false Monopoly baseline.
    """
    product = parse_product_input(
        21,
        pd.Series(
            {
                "S.NO": 22,
                "Brand": "Gree",
                "Name ": "GREE SPLIT AC GS-24PITH15G-T3",
                "Length": 106,
                "Width": 42,
                "Height": 110,
                "Net Price": 220000,
                "Profit": 4000,
            }
        ),
    )

    _, model_code = extract_search_query_and_model(product.name, brand=product.brand)

    digi_raw = [
        ScrapedOffer(
            vendor_name="Tech House",
            price=247999.0,
            is_sold_out=False,
            raw_title="GREE Pular T3 2 TON Split AC GS-24PITH15/17G - T3",
        ),
        ScrapedOffer(
            vendor_name="YZ International",
            price=248099.0,
            is_sold_out=False,
            raw_title="GREE Pular T3 2 TON Split AC GS-24PITH15/17G - T3",
        ),
        ScrapedOffer(
            vendor_name="Wrong Color White",
            price=247999.0,
            is_sold_out=False,
            raw_title="GREE Pular T3 2 TON Split AC GS-24PITH15/17W - T3",
        ),
    ]

    filtered = [o for o in digi_raw if is_strict_model_match(o.raw_title, model_code)]
    assert len(filtered) == 2
    assert all(o.vendor_name in ("Tech House", "YZ International") for o in filtered)

    record = process_product_with_offers(product, alfa_offers=[], digi_offers=filtered)

    # 1. Final Price undercuts Tech House (247,999)
    assert record["Final Price Digi"] < 247999
    # 2. Commission switched to 8.00%
    assert record["Digi Effective Commision"] == "8.00%"
    # 3. Real Profit is healthy (+Rs. 1,119)
    assert record["Digi Real Profit"] == 1119
    # 4. Reason documents Tech House undercut and 8% bank rate
    assert "tech house" in record["Digi Reason"].lower()
    assert "8% faysal bank rate" in record["Digi Reason"].lower()
    # 5. Risk Alert is NONE
    assert record["Digi Risk Alert"] == "NONE"


def test_pipeline_autonomous_learner_buffering() -> None:
    """Validate that accepted candidate offers with residual cosmetic differences buffer observations."""
    from pricing_engine.pipeline import default_learner, process_item_async

    default_learner.clear_buffer()

    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Haier",
                "Category": "WASHING_MACHINE",
                "Name ": "Haier HWM 120-826S6 GC Automatic Washing Machine",
                "Length": 60,
                "Width": 60,
                "Height": 90,
                "Net Price": 80000,
                "Profit": 4000,
            }
        ),
    )

    candidate_offers = [
        ScrapedOffer(
            vendor_name="Mega Store Lahore",
            price=85000.0,
            is_sold_out=False,
            raw_title="Haier 120-826S6 Glass Door Automatic Washing Machine",
        )
    ]

    async def _run() -> None:
        from unittest.mock import AsyncMock

        mock_session = AsyncMock()
        sem = asyncio.Semaphore(1)
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", return_value=candidate_offers),
            patch("pricing_engine.pipeline.scrape_digimall", return_value=[]),
        ):
            _ = await process_item_async(product, mock_session, sem, verbose=False)

        assert default_learner.buffer_size >= 1
        obs = default_learner._buffer[-1]
        assert obs["brand"] == "HAIER"
        assert obs["category"] == "WASHING_MACHINE"
        assert obs["anchor_model"] == "120-826S6"
        assert obs["target_residual"] == "GC"
        assert obs["candidate_residual"] == "GLASS DOOR"
        assert obs["normalized_merchant"] == "megastorelahore"

    asyncio.run(_run())


def test_build_scraped_sellers_table_smart_formatting() -> None:
    """Verify smart table formatting renders dropped summary, target undercut, and true ceiling."""
    from pricing_engine.models import CostFloors, PlatformPricingResult, ScrapedOffer
    from pricing_engine.pipeline import build_scraped_sellers_table

    floors = CostFloors(
        floor_alfa=88226.0,
        floor_digi_10=88226.0,
        floor_digi_8=86307.0,
        cost_base=78903.0,
        zero_margin_10=87670.0,
        zero_margin_8=85764.0,
    )

    # 5 sub-floor sellers and 3 viable sellers (total 8 sellers)
    alfa_offers = [
        ScrapedOffer(vendor_name="Sub Seller 1", price=81500.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Sub Seller 2", price=81500.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Sub Seller 3", price=82000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Sub Seller 4", price=83000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Sub Seller 5", price=84000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Kia Chahiye", price=88599.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Electronics World", price=91499.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Ceiling Seller", price=102078.0, is_sold_out=False, raw_title=""),
    ]

    alfa_res = PlatformPricingResult(
        final_price=88499.0,
        min_price=88499.0,
        max_price=88499.0,
        real_profit=746.0,
        reason="Undercut lowest viable",
        status="Won",
        effective_comm="10.00%",
    )
    digi_res = PlatformPricingResult(
        final_price=88499.0,
        min_price=88499.0,
        max_price=88499.0,
        real_profit=2516.0,
        reason="Won at 10%",
        status="Won",
        effective_comm="10.00%",
    )

    tbl = build_scraped_sellers_table(floors, alfa_offers, [], alfa_res, digi_res)

    # Convert table rows to string to inspect contents
    rows_text = []
    for col in tbl.columns:
        for cell in col._cells:
            rows_text.append(str(cell))
    full_table_text = " ".join(rows_text)

    # 1. Target Undercut (Lowest Viable) MUST be present in the table
    assert "Target Undercut (Lowest Viable)" in full_table_text
    assert "Kia Chahiye" in full_table_text
    assert "88,599" in full_table_text

    # 2. Sub-floor rollup must be present because there are 5 dropped sellers (> 3)
    assert "dropped" in full_table_text or "more sub-floor" in full_table_text or "Sub-floor offers" in full_table_text
    assert "Sub Seller 1" in full_table_text
    assert "Sub Seller 2" in full_table_text

    # 3. Market ceiling must be visible
    assert "102,078" in full_table_text


def test_build_scraped_sellers_table_all_subfloor_lossmakers() -> None:
    """Verify clean rendering when all scraped competitors are below the floor."""
    from pricing_engine.models import CostFloors, PlatformPricingResult, ScrapedOffer
    from pricing_engine.pipeline import build_scraped_sellers_table

    floors = CostFloors(
        floor_alfa=88226.0,
        floor_digi_10=88226.0,
        floor_digi_8=86307.0,
        cost_base=78903.0,
        zero_margin_10=87670.0,
        zero_margin_8=85764.0,
    )

    alfa_offers = [
        ScrapedOffer(vendor_name=f"Loss Seller {i}", price=80000.0 + (i * 500), is_sold_out=False, raw_title="")
        for i in range(6)
    ]

    alfa_res = PlatformPricingResult(
        final_price=89999.0,
        min_price=89999.0,
        max_price=89999.0,
        real_profit=2096.0,
        reason="All competitors selling at loss",
        status="Safe Fallback",
        effective_comm="10.00%",
    )
    digi_res = PlatformPricingResult(
        final_price=89999.0,
        min_price=89999.0,
        max_price=89999.0,
        real_profit=3896.0,
        reason="All competitors selling at loss",
        status="Safe Fallback",
        effective_comm="8.00%",
    )

    tbl = build_scraped_sellers_table(floors, alfa_offers, [], alfa_res, digi_res)
    rows_text = []
    for col in tbl.columns:
        for cell in col._cells:
            rows_text.append(str(cell))
    full_table_text = " ".join(rows_text)

    # When all are sub-floor, should render dropped status and loss-makers rollup
    assert "All sub-floor" in full_table_text
    assert "dropped" in full_table_text or "more loss-makers" in full_table_text
    assert "Loss Seller 0" in full_table_text


def test_build_scraped_sellers_table_digimall_two_tier_switch() -> None:
    """Verify DigiMall correctly renders Target Undercut (8% Viable) on emergency switch."""
    from pricing_engine.models import CostFloors, PlatformPricingResult, ScrapedOffer
    from pricing_engine.pipeline import build_scraped_sellers_table

    floors = CostFloors(
        floor_alfa=88226.0,
        floor_digi_10=88226.0,
        floor_digi_8=86307.0,
        cost_base=78903.0,
        zero_margin_10=87670.0,
        zero_margin_8=85764.0,
    )

    digi_offers = [
        ScrapedOffer(vendor_name="Sub Seller", price=85000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Electronics World", price=86702.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Kia Chahiye", price=87500.0, is_sold_out=False, raw_title=""),
    ]

    alfa_res = PlatformPricingResult(
        final_price=88499.0,
        min_price=88499.0,
        max_price=88499.0,
        real_profit=746.0,
        reason="Won",
        status="Won",
        effective_comm="10.00%",
    )
    digi_res = PlatformPricingResult(
        final_price=86499.0,
        min_price=86499.0,
        max_price=86499.0,
        real_profit=677.0,
        reason="Triggered emergency 8% switch",
        status="Won",
        effective_comm="8.00%",
    )

    tbl = build_scraped_sellers_table(floors, [], digi_offers, alfa_res, digi_res)
    rows_text = []
    for col in tbl.columns:
        for cell in col._cells:
            rows_text.append(str(cell))
    full_table_text = " ".join(rows_text)

    # Must display 8% Viable badge
    assert "Target Undercut (8% Viable)" in full_table_text
    assert "Electronics World" in full_table_text
    assert "86,702" in full_table_text


def test_build_scraped_sellers_table_target_predecessor_visibility() -> None:
    """Verify that with many sub-floor sellers, the seller right above target undercut is always visible."""
    from pricing_engine.models import CostFloors, PlatformPricingResult, ScrapedOffer
    from pricing_engine.pipeline import build_scraped_sellers_table

    floors = CostFloors(
        floor_alfa=33964.0,
        floor_digi_10=33964.0,
        floor_digi_8=33226.0,
        cost_base=30000.0,
        zero_margin_10=33333.0,
        zero_margin_8=32608.0,
    )

    # 9 dropped sellers (Allure Beauty, Tech House, etc.) + MZ Electronics as target undercut
    alfa_offers = [
        ScrapedOffer(vendor_name="Allure Beauty", price=16498.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Tech House", price=27999.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Tech House", price=28289.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Other Seller 1", price=30435.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Other Seller 2", price=31000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Other Seller 3", price=31500.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Other Seller 4", price=32000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Other Seller 5", price=32500.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Nearest Predecessor", price=33500.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="MZ Electonics", price=34400.0, is_sold_out=False, raw_title=""),
    ]

    alfa_res = PlatformPricingResult(
        final_price=34299.0,
        min_price=34400.0,
        max_price=34400.0,
        real_profit=869.0,
        reason="Undercut lowest viable",
        status="Won",
        effective_comm="10.00%",
    )
    digi_res = PlatformPricingResult(
        final_price=34299.0,
        min_price=34400.0,
        max_price=34400.0,
        real_profit=1557.0,
        reason="Won",
        status="Won",
        effective_comm="10.00%",
    )

    tbl = build_scraped_sellers_table(floors, alfa_offers, [], alfa_res, digi_res)
    rows_text = []
    for col in tbl.columns:
        for cell in col._cells:
            rows_text.append(str(cell))
    full_table_text = " ".join(rows_text)

    # 1. First 2 dropped sellers must be visible
    assert "Allure Beauty" in full_table_text
    assert "16,498" in full_table_text
    assert "Tech House" in full_table_text

    # 2. Middle rollup must be visible (+6 dropped)
    assert "+6 dropped" in full_table_text

    # 3. CRITICAL: The closest seller right before target undercut MUST be visible
    assert "Nearest Predecessor" in full_table_text
    assert "33,500" in full_table_text

    # 4. Target undercut must follow immediately
    assert "MZ Electonics" in full_table_text
    assert "Target Undercut (Lowest Viable)" in full_table_text


def test_run_pipeline_structured_export_mode(tmp_path: Path) -> None:
    """Verify run_pipeline with output_path=None saves to structured export directory."""
    csv_file = tmp_path / "catalog.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92\n",
        encoding="utf-8",
    )
    export_dir = tmp_path / "data_outputs"

    mock_empty = ScrapeResult(offers=[], is_success=True, status_code=200)

    async def _run() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_empty),
            patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_empty),
        ):
            out_df = await run_pipeline(
                input_path=csv_file,
                output_path=None,
                concurrency=1,
                verbose=False,
                use_structured_export=True,
                export_dir=export_dir,
            )
            assert len(out_df) == 1
            latest_file = export_dir / "csv" / "catalog_repriced_latest.csv"
            assert latest_file.is_file()
            ts_files = list((export_dir / "csv").glob("catalog_repriced_*.csv"))
            assert len(ts_files) >= 2

    asyncio.run(_run())


def test_parse_product_input_invalid_brand_raises_error() -> None:
    for bad_brand in ["", "-", "--", "n/a", "none", "null", "?"]:
        row = pd.Series(
            {
                "S.NO": 1,
                "Brand": bad_brand,
                "Name": "Dawlance Inverter AC",
                "Net Price": 50000,
            }
        )
        with pytest.raises(ValueError, match="Brand.*empty or invalid"):
            parse_product_input(0, row)


def test_parse_product_input_with_title_alias() -> None:
    row = pd.Series(
        {
            "Brand": "Dawlance",
            "Title": "Dawlance DWT 9057 EZ Fully Automatic Washing Machine - 9.5KG",
            "Net Price": 48000,
        }
    )
    product = parse_product_input(0, row)
    assert product.brand == "Dawlance"
    assert product.name == "Dawlance DWT 9057 EZ Fully Automatic Washing Machine - 9.5KG"
    assert product.net_price == 48000.0


def test_parse_product_input_missing_name_raises_error() -> None:
    for bad_name in ["", "-", "--", "n/a", "none", "nan", None]:
        row = pd.Series(
            {
                "Brand": "Dawlance",
                "Name": bad_name,
                "Net Price": 50000,
            }
        )
        with pytest.raises(ValueError, match="Product.*empty or missing"):
            parse_product_input(0, row)



def test_in_order_card_dispatcher_sequence() -> None:
    """Verify that InOrderCardDispatcher outputs in strictly ascending sequence even when workers finish out of order."""
    from pricing_engine.pipeline import InOrderCardDispatcher

    printed_order: list[int] = []

    def make_renderer(val: int):
        return lambda: printed_order.append(val)

    async def _test() -> None:
        dispatcher = InOrderCardDispatcher()
        # Simulate workers finishing in random/reverse order: 3, 1, 0, 2
        await dispatcher.dispatch(3, make_renderer(3))
        assert printed_order == []  # 0 not ready yet

        await dispatcher.dispatch(1, make_renderer(1))
        assert printed_order == []  # 0 still not ready

        await dispatcher.dispatch(0, make_renderer(0))
        # 0 is dispatched, triggering 0 and 1! (2 is not ready, so 3 waits)
        assert printed_order == [0, 1]

        await dispatcher.dispatch(2, make_renderer(2))
        # 2 is dispatched, which immediately triggers 2 and the waiting 3!
        assert printed_order == [0, 1, 2, 3]

    asyncio.run(_test())


def test_in_order_card_dispatcher_skip_on_error() -> None:
    """Verify that dispatcher.skip prevents deadlocks when an intermediate worker fails."""
    from pricing_engine.pipeline import InOrderCardDispatcher

    printed_order: list[int] = []

    def make_renderer(val: int):
        return lambda: printed_order.append(val)

    async def _test() -> None:
        dispatcher = InOrderCardDispatcher()
        # 0 finishes
        await dispatcher.dispatch(0, make_renderer(0))
        assert printed_order == [0]

        # 2 and 3 finish, but 1 has an error
        await dispatcher.dispatch(2, make_renderer(2))
        await dispatcher.dispatch(3, make_renderer(3))
        assert printed_order == [0]

        # 1 fails and calls skip(1)
        await dispatcher.skip(1)
        # Sequence should cleanly continue: 2, 3
        assert printed_order == [0, 2, 3]

    asyncio.run(_test())


def test_build_scraped_sellers_table_renders_own_store_badges() -> None:
    from pricing_engine.models import CostFloors, PlatformPricingResult, ScrapedOffer, ScrapeResult
    from pricing_engine.pipeline import build_scraped_sellers_table

    floors = CostFloors(
        floor_alfa=80555.0,
        floor_digi_10=80555.0,
        floor_digi_8=78804.0,
        cost_base=72000.0,
        zero_margin_10=80000.0,
        zero_margin_8=78260.0,
    )

    alfa_scrape = ScrapeResult(
        offers=[],
        own_offers=[
            ScrapedOffer(vendor_name="KiaChahye", price=85000.0, is_sold_out=False, raw_title=""),
        ],
    )
    alfa_res = PlatformPricingResult(
        final_price=84499.0,
        min_price=None,
        max_price=None,
        real_profit=4049.0,
        reason="[OWN STORE ACTIVE: KiaChahye @ Rs. 85,000] Applied Monopoly pricing.",
        status="Monopoly Win",
        effective_comm="10.00%",
        own_offers=alfa_scrape.own_offers,
    )
    digi_scrape = ScrapeResult(
        offers=[
            ScrapedOffer(vendor_name="Fahad Electronics", price=83000.0, is_sold_out=False, raw_title=""),
        ],
        own_offers=[
            ScrapedOffer(vendor_name="Haier Official Store", price=92000.0, is_sold_out=False, raw_title=""),
        ],
    )
    digi_res = PlatformPricingResult(
        final_price=82899.0,
        min_price=83000.0,
        max_price=83000.0,
        real_profit=4267.0,
        reason="[OFFICIAL STORE: Haier Official Store @ Rs. 92,000] Undercut competitor.",
        status="Competitive Win",
        effective_comm="8.00%",
        own_offers=digi_scrape.own_offers,
    )

    tbl = build_scraped_sellers_table(floors, alfa_scrape, digi_scrape, alfa_res, digi_res)
    rows_text = []
    for col in tbl.columns:
        for cell in col._cells:
            rows_text.append(str(cell))
    full_table_text = " ".join(rows_text)

    # AlfaMall shows KiaChahye with Our Store badge and No external sellers
    assert "KiaChahye" in full_table_text
    assert "★ Our Store (Active Listing)" in full_table_text
    assert "No external sellers" in full_table_text

    # DigiMall shows Haier Official Store with Official Flagship badge and Fahad Electronics
    assert "Haier Official Store" in full_table_text
    assert "Official Flagship (Excluded)" in full_table_text
    assert "Fahad Electronics" in full_table_text


def test_final_price_card_badges_undercut_capped_monopoly_fallback() -> None:
    """Verify that build_platform_decision_table displays explicit badges for all price outcomes."""
    from pricing_engine.models import PlatformPricingResult
    from pricing_engine.pipeline import build_platform_decision_table

    # Case 1: Standard Winning Undercut
    alfa_undercut = PlatformPricingResult(
        final_price=36499,
        min_price=36599.0,
        max_price=40000.0,
        real_profit=1500,
        reason="Undercut viable competitor Afzal Corporation to winning price Rs. 36,499.",
        status="Undercut Win",
    )
    digi_undercut_8pct = PlatformPricingResult(
        final_price=36299,
        min_price=36599.0,
        max_price=40000.0,
        real_profit=2100,
        reason="Triggered emergency 8% rate to undercut competitor to winning price Rs. 36,299.",
        status="Undercut Win (8% Tier)",
        effective_comm="8.00%",
    )
    tbl1 = build_platform_decision_table(
        alfa_res=alfa_undercut,
        digi_res=digi_undercut_8pct,
        alfa_offers=[],
        digi_offers=[],
        personal_comm_pct=5.0,
    )
    rendered_text1 = " ".join(str(cell) for col in tbl1.columns for cell in col._cells)
    assert "(WINNING UNDERCUT)" in rendered_text1
    assert "(WINNING UNDERCUT (8% RATE))" in rendered_text1

    # Case 2: Capped Sweet-Spot Win
    alfa_capped = PlatformPricingResult(
        final_price=98999,
        min_price=99200.0,
        max_price=108000.0,
        real_profit=1099,
        reason="Filtered 9 sub-floor offer(s). Competitor price is inflated. Capped price at Rs. 98,999 to ensure sales volume.",
        status="Capped Sweet-Spot",
    )
    digi_monopoly = PlatformPricingResult(
        final_price=104999,
        min_price=None,
        max_price=None,
        real_profit=4000,
        reason="No competitors found in market. Applied Monopoly pricing.",
        status="Monopoly Win",
    )
    tbl2 = build_platform_decision_table(
        alfa_res=alfa_capped,
        digi_res=digi_monopoly,
        alfa_offers=[],
        digi_offers=[],
        personal_comm_pct=5.0,
    )
    rendered_text2 = " ".join(str(cell) for col in tbl2.columns for cell in col._cells)
    assert "(CAPPED SWEET-SPOT)" in rendered_text2
    assert "(MONOPOLY WIN)" in rendered_text2

    # Case 3: Safe Fallback & Digi 50% Split Midpoint
    alfa_fallback = PlatformPricingResult(
        final_price=54499,
        min_price=45000.0,
        max_price=50000.0,
        real_profit=500,
        reason="All competitors are selling at a loss. Listed at Safe Fallback Price Rs. 54,499.",
        status="Safe Fallback",
    )
    digi_50pct = PlatformPricingResult(
        final_price=47499,
        min_price=50000.0,
        max_price=50000.0,
        real_profit=3699,
        reason="Large price gap (Rs. 5,000) above floor. Applied 50% split midpoint to capped winning psychological price Rs. 47,499 (+Rs. 3,699 profit on 8% Faysal Bank rate) for maximum conversion.",
        status="Safe Win (10% Tier)",
    )
    tbl3 = build_platform_decision_table(
        alfa_res=alfa_fallback,
        digi_res=digi_50pct,
        alfa_offers=[],
        digi_offers=[],
        personal_comm_pct=5.0,
    )
    rendered_text3 = " ".join(str(cell) for col in tbl3.columns for cell in col._cells)
    assert "(SAFE FALLBACK)" in rendered_text3
    assert "(CAPPED SWEET-SPOT)" in rendered_text3


def test_determine_platform_status_viable_undercut_consistent_win_and_capped() -> None:
    """Verify determine_platform_status accurately identifies pure and viable wins without uncompetitive text."""
    from pricing_engine.pipeline import determine_5pct_goal_status, determine_platform_status

    # Sub-floor filtered, but viable competitor undercut standardly
    s1 = determine_platform_status(
        price_val=36499,
        min_comp_price=35000,  # Cheaper junk seller was dropped (< floor)
        reason="Filtered 2 sub-floor offer(s). Undercut viable competitor to winning price Rs. 36,499.",
    )
    assert s1 == "WIN"
    # Because sub-floor competitors exist in the mall, this is NOT a pure win against the whole platform
    assert determine_5pct_goal_status(s1, real_profit=1500, target_profit_5pct=526, active_sellers=5) == "SUB-FLOOR CHEAPER"

    # Sub-floor filtered, viable competitor capped (e.g. Dawlance DW-10500 Item #25)
    s2 = determine_platform_status(
        price_val=98999,
        min_comp_price=45000,  # Dropped sub-floor seller (< floor)
        reason="Filtered 7 sub-floor offer(s). Competitor Nasim & Sons price is inflated. Capped price at Rs. 98,999.",
    )
    assert s2 == "CAPPED"
    # Because 7 sub-floor sellers are cheaper than our floor, this must NOT falsely claim WIN + 5% ACHIEVED!
    assert determine_5pct_goal_status(s2, real_profit=1099, target_profit_5pct=526, active_sellers=10) == "SUB-FLOOR CHEAPER"

    # Pure market win without sub-floor
    s3 = determine_platform_status(
        price_val=50000,
        min_comp_price=50200,
        reason="Undercut lowest viable competitor to winning price Rs. 50,000.",
    )
    assert s3 == "WIN (-200)"
    assert determine_5pct_goal_status(s3, real_profit=1000, target_profit_5pct=526, active_sellers=3) == "WIN + 5% ACHIEVED"

    # Pure market win with capping
    s4 = determine_platform_status(
        price_val=50000,
        min_comp_price=60000,
        reason="Competitor price is inflated. Capped price at Rs. 50,000.",
    )
    assert s4 == "CAPPED (-10,000)"
    assert determine_5pct_goal_status(s4, real_profit=2000, target_profit_5pct=526, active_sellers=2) == "WIN + 5% ACHIEVED"

    # Pure market win with 50% split midpoint
    s5 = determine_platform_status(
        price_val=47499,
        min_comp_price=50000,
        reason="Large price gap (Rs. 5,000) above floor. Applied dynamic adaptive split (69%) to capped winning psychological price Rs. 47,499 (+Rs. 2,749 profit) for maximum conversion.",
    )
    assert s5 == "CAPPED (-2,501)"
    assert determine_5pct_goal_status(s5, real_profit=2749, target_profit_5pct=526, active_sellers=1) == "WIN + 5% ACHIEVED"

    # 50% split midpoint with sub-floor filtered (viable competitor capped, but sub-floor existed)
    s6 = determine_platform_status(
        price_val=47499,
        min_comp_price=40000,
        reason="Filtered 1 sub-floor offer(s). Large price gap (Rs. 5,000) above floor. Applied dynamic adaptive split (69%) to capped winning psychological price Rs. 47,499 (+Rs. 2,749 profit) for maximum conversion.",
    )
    assert s6 == "CAPPED"
    assert determine_5pct_goal_status(s6, real_profit=2749, target_profit_5pct=526, active_sellers=2) == "SUB-FLOOR CHEAPER"

    # Vendor named with "Split" (e.g. Split AC Hub) on ordinary undercut must NOT trigger false-positive CAPPED
    s7 = determine_platform_status(
        price_val=79899,
        min_comp_price=80000,
        reason="Undercut lowest competitor Gree Split AC Hub (Rs. 80,000) to winning price Rs. 79,899.",
    )
    assert s7 == "WIN (-101)"



