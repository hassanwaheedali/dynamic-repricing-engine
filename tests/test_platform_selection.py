"""Tests for platform filtering feature (--platform all|alfa|digi).

Verifies that selecting a single platform:
1. Only queries the selected platform's scraper (skipping network calls for the other).
2. Sets clean skipped status/alert on the unselected platform instead of false monopoly wins.
3. Leaves unselected platform columns blank in output records.
4. Correctly parses CLI options (-p, --platform, --alfa-only, --digi-only).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from index import parse_args
from pricing_engine.models import (
    CostFloors,
    PlatformPricingResult,
    ProductInput,
    ScrapedOffer,
    ScrapeResult,
)
from pricing_engine.pipeline import (
    build_output_record,
    create_skipped_platform_result,
    determine_risk_alert,
    process_item_async,
)


def test_create_skipped_platform_result() -> None:
    res = create_skipped_platform_result("DigiMall")
    assert res.status == "SKIPPED"
    assert res.min_price is None
    assert res.max_price is None
    assert res.final_price is None
    assert res.real_profit is None
    assert res.effective_comm == ""
    assert "skipped" in res.reason.lower()


def test_determine_risk_alert_skipped() -> None:
    skipped_res = create_skipped_platform_result("DigiMall")
    # Risk alert for a skipped platform must be empty string, NOT SERVER_DOWN
    assert determine_risk_alert(skipped_res) == ""


def test_build_output_record_alfa_only() -> None:
    product = ProductInput(
        sno=1,
        brand="Gree",
        name="Gree Fairy 1.5 Ton GS-18FITH1G",
        length=100.0,
        width=35.0,
        height=45.0,
        net_price=150000.0,
        profit=500.0,
        raw_row={"Brand": "Gree", "Name": "Gree Fairy 1.5 Ton GS-18FITH1G"},
    )
    floors = CostFloors(
        cost_base=153000.0,
        zero_margin_10=170000.0,
        zero_margin_8=166304.0,
        floor_alfa=170556.0,
        floor_digi_10=170556.0,
        floor_digi_8=166848.0,
    )
    alfa_res = PlatformPricingResult(
        min_price=175000.0,
        max_price=180000.0,
        final_price=174899,
        real_profit=4409,
        status="Target Undercut",
        reason="Undercut lowest competitor",
        effective_comm="10.00%",
    )
    digi_res = create_skipped_platform_result("DigiMall")

    record = build_output_record(
        product=product,
        shipping=3000.0,
        floors=floors,
        baseline_calc=170556.0,
        alfa_res=alfa_res,
        digi_res=digi_res,
    )

    assert record["Final Price Alfa"] == 174899
    assert record["Alfa Real Profit"] == 4409
    assert record["Alfa Risk Alert"] == "NONE"

    # Digi columns must be empty/None when skipped
    assert record["Final Price Digi"] is None
    assert record["Digi Real Profit"] is None
    assert record["Digi Risk Alert"] == ""
    assert record["Digi Effective Commision"] == ""
    assert record["Digi Status"] == ""


def test_build_output_record_digi_only() -> None:
    product = ProductInput(
        sno=1,
        brand="Gree",
        name="Gree Fairy 1.5 Ton GS-18FITH1G",
        length=100.0,
        width=35.0,
        height=45.0,
        net_price=150000.0,
        profit=500.0,
        raw_row={"Brand": "Gree", "Name": "Gree Fairy 1.5 Ton GS-18FITH1G"},
    )
    floors = CostFloors(
        cost_base=153000.0,
        zero_margin_10=170000.0,
        zero_margin_8=166304.0,
        floor_alfa=170556.0,
        floor_digi_10=170556.0,
        floor_digi_8=166848.0,
    )
    alfa_res = create_skipped_platform_result("AlfaMall")
    digi_res = PlatformPricingResult(
        min_price=172000.0,
        max_price=178000.0,
        final_price=171899,
        real_profit=5147,
        status="Target Undercut",
        reason="Undercut at 8% rate",
        effective_comm="8.00%",
    )

    record = build_output_record(
        product=product,
        shipping=3000.0,
        floors=floors,
        baseline_calc=166848.0,
        alfa_res=alfa_res,
        digi_res=digi_res,
        platform="digi",
    )

    assert record["Final Price Digi"] == 171899
    assert record["Digi Real Profit"] == 5147
    assert record["Digi Risk Alert"] == "NONE"
    assert record["Digi Effective Commision"] == "8.00%"
    assert record["Commision"] == "8.00%"
    assert record["Final Price Alfa"] is None


def test_process_item_async_alfa_only_skips_digimall_scraper() -> None:
    product = ProductInput(
        sno=1,
        brand="Gree",
        name="Gree Fairy 1.5 Ton GS-18FITH1G",
        length=100.0,
        width=35.0,
        height=45.0,
        net_price=150000.0,
        profit=500.0,
        raw_row={"Brand": "Gree", "Name": "Gree Fairy 1.5 Ton GS-18FITH1G"},
    )
    session = AsyncMock()
    semaphore = asyncio.Semaphore(1)

    async def _test() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", new_callable=AsyncMock) as mock_alfa,
            patch("pricing_engine.pipeline.scrape_digimall", new_callable=AsyncMock) as mock_digi,
        ):
            mock_alfa.return_value = ScrapeResult(
                offers=[
                    ScrapedOffer(vendor_name="Comp A", price=175000.0, is_sold_out=False, raw_title="Gree Fairy")
                ]
            )
            # Process with platform="alfa"
            record = await process_item_async(
                product=product,
                session=session,
                semaphore=semaphore,
                verbose=False,
                platform="alfa",
            )

            assert mock_alfa.called
            assert not mock_digi.called  # DigiMall scraper must NEVER be called
            assert record["Final Price Alfa"] is not None
            assert record["Final Price Digi"] is None
            assert record["Digi Risk Alert"] == ""

    asyncio.run(_test())


def test_process_item_async_digi_only_skips_alfamall_scraper() -> None:
    product = ProductInput(
        sno=1,
        brand="Gree",
        name="Gree Fairy 1.5 Ton GS-18FITH1G",
        length=100.0,
        width=35.0,
        height=45.0,
        net_price=150000.0,
        profit=500.0,
        raw_row={"Brand": "Gree", "Name": "Gree Fairy 1.5 Ton GS-18FITH1G"},
    )
    session = AsyncMock()
    semaphore = asyncio.Semaphore(1)

    async def _test() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", new_callable=AsyncMock) as mock_alfa,
            patch("pricing_engine.pipeline.scrape_digimall", new_callable=AsyncMock) as mock_digi,
        ):
            mock_digi.return_value = ScrapeResult(
                offers=[
                    ScrapedOffer(vendor_name="Comp B", price=172000.0, is_sold_out=False, raw_title="Gree Fairy")
                ]
            )
            # Process with platform="digi"
            record = await process_item_async(
                product=product,
                session=session,
                semaphore=semaphore,
                verbose=False,
                platform="digi",
            )

            assert not mock_alfa.called  # AlfaMall scraper must NEVER be called
            assert mock_digi.called
            assert record["Final Price Alfa"] is None
            assert record["Final Price Digi"] is not None
            assert record["Alfa Risk Alert"] == ""

    asyncio.run(_test())


def test_cli_platform_arg_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["index.py", "-p", "alfa"])
    args = parse_args()
    assert args.platform == "alfa"

    monkeypatch.setattr("sys.argv", ["index.py", "--alfa-only"])
    args = parse_args()
    assert args.alfa_only is True

    monkeypatch.setattr("sys.argv", ["index.py", "--platform", "digi"])
    args = parse_args()
    assert args.platform == "digi"

    monkeypatch.setattr("sys.argv", ["index.py", "--digi-only"])
    args = parse_args()
    assert args.digi_only is True


def test_invalid_platform_raises() -> None:
    product = ProductInput(
        sno=1,
        brand="Gree",
        name="Gree Fairy 1.5 Ton GS-18FITH1G",
        length=100.0,
        width=35.0,
        height=45.0,
        net_price=150000.0,
        profit=500.0,
    )
    session = AsyncMock()
    semaphore = asyncio.Semaphore(1)

    with pytest.raises(ValueError, match="Unsupported platform"):
        asyncio.run(
            process_item_async(
                product=product,
                session=session,
                semaphore=semaphore,
                platform="daraz",
            )
        )


def test_range_process_item_alfa_only_skips_digimall() -> None:
    from pricing_engine.range_pipeline import process_range_item_async

    product = ProductInput(
        sno=1,
        brand="Gree",
        name="Gree Fairy 1.5 Ton GS-18FITH1G",
        length=100.0,
        width=35.0,
        height=45.0,
        net_price=150000.0,
        profit=500.0,
    )
    session = AsyncMock()
    semaphore = asyncio.Semaphore(1)

    async def _test() -> None:
        with (
            patch("pricing_engine.range_pipeline.scrape_alfamall", new_callable=AsyncMock) as mock_alfa,
            patch("pricing_engine.range_pipeline.scrape_digimall", new_callable=AsyncMock) as mock_digi,
        ):
            mock_alfa.return_value = ScrapeResult(
                offers=[
                    ScrapedOffer(vendor_name="Comp A", price=175000.0, is_sold_out=False, raw_title="Gree Fairy")
                ]
            )
            rec = await process_range_item_async(
                product=product,
                session=session,
                semaphore=semaphore,
                platform="alfa",
            )
            assert mock_alfa.called
            assert not mock_digi.called
            assert rec["Minimum Price Alfa"] == 175000.0
            assert rec["Minimum Price Digi"] is None
            assert rec["Digi Risk Alert"] == ""

    asyncio.run(_test())
