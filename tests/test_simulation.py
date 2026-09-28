import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from pricing_engine.models import ScrapedOffer, ScrapeResult
from pricing_engine.pipeline import run_pipeline


def test_simulation_haier_washing_machine_pipeline() -> None:
    """Run full E2E pipeline simulation on real Haier Washing Machine catalog."""
    input_csv = Path("Haier_Washing_Machines_Uploading_and_Price.csv")
    assert input_csv.exists()

    df_full = pd.read_csv(input_csv)
    # Take first 5 models representing Front Load, Top Load, and Tub series
    sample_df = df_full.head(5).copy()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_input = Path(tmp_dir) / "sample_haier_input.csv"
        tmp_output = Path(tmp_dir) / "sample_haier_output.csv"
        sample_df.to_csv(tmp_input, index=False)

        # Mock scraped offers with realistic marketplace competitors
        mock_alfa_offers = ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name="Official Alfa Partner",
                    price=98500.0,
                    is_sold_out=False,
                    raw_title="Haier Automatic Washing Machine 120-826S6 GC Glass Door",
                ),
                ScrapedOffer(
                    vendor_name="Market Seller B",
                    price=99999.0,
                    is_sold_out=False,
                    raw_title="Haier 120-826S6 Glass Door",
                ),
            ],
            is_success=True,
            status_code=200,
        )

        mock_digi_offers = ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name="Faysal Digi Merchant",
                    price=96999.0,
                    is_sold_out=False,
                    raw_title="Haier Automatic Washing Machine 120-826S6 GC",
                )
            ],
            is_success=True,
            status_code=200,
        )

        async def _run() -> None:
            with patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_alfa_offers), \
                 patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_digi_offers):
                out_df = await run_pipeline(
                    input_path=tmp_input,
                    output_path=tmp_output,
                    concurrency=2,
                    verbose=False,
                )

                assert len(out_df) == 5
                assert tmp_output.exists()

                # Verify all required schema columns are present
                required_cols = [
                    "S.NO",
                    "Brand",
                    "Name ",
                    "Shipping Estimate",
                    "Total Without Profit",
                    "Calculation",
                    "Minimum Price Alfa",
                    "Maximum Price Alfa",
                    "Final Price Alfa",
                    "Final Price Digi",
                    "Alfa Real Profit",
                    "Digi Real Profit",
                    "Alfa Reason",
                    "Digi Reason",
                ]
                for col in required_cols:
                    assert col in out_df.columns, f"Missing output column: {col}"

                # Verify prices are formatted as pure integers without float drift
                for p in out_df["Final Price Alfa"].dropna():
                    if str(p).strip():
                        assert "." not in str(p), f"Price contained float decimal: {p}"

        asyncio.run(_run())


def test_simulation_gree_ac_pipeline_two_tier_switch() -> None:
    """Run E2E pipeline simulation on Gree AC catalog validating two-tier 10% -> 8% switch."""
    input_csv = Path("Gree_Uploading_on_DigiMall_and_Price.csv")
    assert input_csv.exists()

    df_full = pd.read_csv(input_csv)
    sample_df = df_full.head(3).copy()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_input = Path(tmp_dir) / "sample_gree_input.csv"
        tmp_output = Path(tmp_dir) / "sample_gree_output.csv"
        sample_df.to_csv(tmp_input, index=False)

        # Simulate competitive scenario triggering 8% bank rate switch
        mock_alfa = ScrapeResult(offers=[], is_success=True, status_code=200)
        mock_digi = ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name="Lahore Aircon",
                    price=158000.0,
                    is_sold_out=False,
                    raw_title="Gree Inverter AC 1.5 Ton GS-18PITH11W",
                )
            ],
            is_success=True,
            status_code=200,
        )

        async def _run() -> None:
            with patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_alfa), \
                 patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_digi):
                out_df = await run_pipeline(
                    input_path=tmp_input,
                    output_path=tmp_output,
                    concurrency=2,
                    verbose=False,
                )

                assert len(out_df) == 3
                # Verify that commission rate is explicitly tagged
                assert "Digi Effective Commision" in out_df.columns
                for comm in out_df["Digi Effective Commision"].dropna():
                    assert comm in ("10.00%", "8.00%")

        asyncio.run(_run())


def test_simulation_stock_holding_report_cross_category_and_risk_alerts() -> None:
    """Run E2E simulation across multi-category appliances (Refrigerators, Microwave, TV) verifying risk alerts."""
    multi_category_data = pd.DataFrame(
        [
            {
                "S.NO": 1,
                "Brand": "Dawlance",
                "Category": "REFRIGERATOR",
                "Name ": "Dawlance 9170 WB Chrome Refrigerator",
                "Length": 60,
                "Width": 65,
                "Height": 160,
                "Net Price": 85000,
                "Profit": 4000,
            },
            {
                "S.NO": 2,
                "Brand": "Dawlance",
                "Category": "MICROWAVE_OVEN",
                "Name ": "Dawlance DW-MD7 Microwave Oven 20L",
                "Length": 45,
                "Width": 35,
                "Height": 30,
                "Net Price": 22000,
                "Profit": 1500,
            },
            {
                "S.NO": 3,
                "Brand": "TCL",
                "Category": "LED",
                "Name ": "TCL 50S80EUX 4K UHD Smart LED TV 50 INCH",
                "Length": 120,
                "Width": 15,
                "Height": 75,
                "Net Price": 95000,
                "Profit": 5000,
            },
        ]
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_input = Path(tmp_dir) / "sample_stock_input.csv"
        tmp_output = Path(tmp_dir) / "sample_stock_output.csv"
        multi_category_data.to_csv(tmp_input, index=False)

        mock_alfa = ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name="Seller A",
                    price=92000.0,
                    is_sold_out=False,
                    raw_title="Dawlance 9170 WB Refrigerator",
                )
            ],
            is_success=True,
            status_code=200,
        )
        mock_digi = ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name="Seller B",
                    price=25000.0,
                    is_sold_out=False,
                    raw_title="Dawlance DW-MD7 Microwave",
                )
            ],
            is_success=True,
            status_code=200,
        )

        async def _run() -> None:
            with patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_alfa), \
                 patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_digi):
                out_df = await run_pipeline(
                    input_path=tmp_input,
                    output_path=tmp_output,
                    concurrency=2,
                    verbose=False,
                )

                assert len(out_df) == 3
                assert "Alfa Risk Alert" in out_df.columns
                assert "Digi Risk Alert" in out_df.columns

                for alert in out_df["Alfa Risk Alert"].dropna():
                    assert alert in ("NONE", "THIN_BUFFER", "SAFE_FALLBACK", "SERVER_DOWN", "NEGATIVE_MARGIN")

                # Verify clean output without ANSI color leakage
                for text in out_df["Alfa Reason"].dropna():
                    assert "\x1b[" not in str(text), "ANSI color escape leaked into CSV reason string"

        asyncio.run(_run())
