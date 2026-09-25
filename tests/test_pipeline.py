import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd

from pricing_engine.models import ScrapedOffer
from pricing_engine.pipeline import (
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
    # Selling price 478,899 -> Profit = (478,899 * 0.92) - 430,291 = 10,296
    assert record["Final Price Digi"] == 478899
    assert record["Digi Real Profit"] == 10296
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




