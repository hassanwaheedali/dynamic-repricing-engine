import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd

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
    digi_offer_8 = [ScrapedOffer(vendor_name="DigiSeller", price=475000.0, is_sold_out=False, raw_title="AC")]
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
    digi_offer_10 = [ScrapedOffer(vendor_name="DigiSellerHigh", price=165000.0, is_sold_out=False, raw_title="AC")]
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
    alfa_offers = [ScrapedOffer(vendor_name="Nasim", price=479499.0, is_sold_out=False, raw_title="AC")]
    digi_offers = [ScrapedOffer(vendor_name="Scroll", price=489999.0, is_sold_out=False, raw_title="AC")]

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
    in_p = Path("Gree_Uploading_on_DigiMall_and_Price.csv")
    out_p = Path("final_repriced_uploaded_products.csv")
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
    alfa_down = ScrapeResult(offers=[], is_success=False, status_code=500, error_detail="HTTP 500: Server Error")
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
    alfa_down = ScrapeResult(offers=[], is_success=False, status_code=502, error_detail="Bad Gateway")
    digi_down = ScrapeResult(offers=[], is_success=False, status_code=504, error_detail="Gateway Timeout")

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

    # 1. Winning price undercuts Musab Mall (193,999) to 192,899 (Adaptive undercut)
    assert record["Final Price Digi"] == 192899

    # 2. Commission switched to 8.00% Emergency Tier
    assert record["Digi Effective Commision"] == "8.00%"

    # 3. Real Profit calculated: (192,899 * 0.92) - 175,978 = +1,489
    assert record["Digi Real Profit"] == 1489

    # 4. Reason documents the 8% switch undercut
    assert "8% bank rate" in record["Digi Reason"].lower() or "emergency 8%" in record["Digi Reason"].lower()

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

    record = process_product_with_offers(product, alfa_offers=filtered_offers, digi_offers=filtered_offers)

    # AlfaMall adaptive undercuts Gen 2 (153,999 - 200 -> 153,799), completely ignoring Gen 1 (130,000)
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










