"""Tests for Market Range Mode (Brand+Name list -> market Min/Max per platform)."""

from __future__ import annotations

from pricing_engine.evaluator import evaluate_market_range
from pricing_engine.models import MarketRange, ScrapedOffer, ScrapeResult


def _offer(vendor: str, price: float, sold_out: bool = False) -> ScrapedOffer:
    return ScrapedOffer(vendor_name=vendor, price=price, is_sold_out=sold_out, raw_title="t")


# ---------------------------------------------------------------- T1


def test_market_range_min_max_in_stock() -> None:
    rng = evaluate_market_range([_offer("A", 100_000), _offer("B", 90_000), _offer("C", 120_000)])
    assert rng == MarketRange(min_price=90_000, max_price=120_000, offer_count=3)
    assert rng.is_down is False


def test_market_range_ignores_sold_out() -> None:
    rng = evaluate_market_range(
        [_offer("A", 50_000, sold_out=True), _offer("B", 90_000), _offer("C", 95_000, True)]
    )
    assert rng.min_price == 90_000
    assert rng.max_price == 90_000
    assert rng.offer_count == 1


def test_market_range_no_floor_filter() -> None:
    """Very cheap vendors still define the market minimum (no profit floor in range mode)."""
    rng = evaluate_market_range([_offer("A", 1_000), _offer("B", 99_000)])
    assert rng.min_price == 1_000


def test_market_range_empty_is_none() -> None:
    rng = evaluate_market_range([])
    assert rng.min_price is None
    assert rng.max_price is None
    assert rng.offer_count == 0
    assert rng.is_down is False


def test_market_range_all_sold_out_is_empty() -> None:
    rng = evaluate_market_range([_offer("A", 10, True)])
    assert rng.offer_count == 0
    assert rng.min_price is None


def test_market_range_failed_scrape_is_down() -> None:
    res = ScrapeResult(offers=[], is_success=False, status_code=503, error_detail="HTTP 503")
    rng = evaluate_market_range(res)
    assert rng.is_down is True
    assert rng.min_price is None
    assert rng.error_detail == "HTTP 503"


def test_market_range_accepts_scrape_result_success() -> None:
    res = ScrapeResult(offers=[_offer("A", 5), _offer("B", 9)])
    rng = evaluate_market_range(res)
    assert (rng.min_price, rng.max_price, rng.offer_count) == (5, 9, 2)


# ---------------------------------------------------------------- T2

import pandas as pd  # noqa: E402

from pricing_engine.models import ProductInput  # noqa: E402
from pricing_engine.range_pipeline import (  # noqa: E402
    RANGE_ALERT_NO_OFFERS,
    build_range_record,
    determine_range_alert,
)


def _product(**raw: object) -> ProductInput:
    row = {"S.No": 7, "Brand": "Gree", "Name": "GS-12XPH32", **raw}
    return ProductInput(
        sno=7, brand="Gree", name="GS-12XPH32", length=0, width=0, height=0,
        net_price=0, profit=500, raw_row=row,
    )  # fmt: skip


def test_alert_none_no_offers_down() -> None:
    assert determine_range_alert(MarketRange(1, 2, 2)) == "NONE"
    assert determine_range_alert(MarketRange(None, None, 0)) == RANGE_ALERT_NO_OFFERS
    assert determine_range_alert(MarketRange(None, None, 0, is_down=True)) == "SERVER_DOWN"


def test_range_record_layout_and_values() -> None:
    rec = build_range_record(_product(Custom="x"), MarketRange(90, 120, 3), MarketRange(95, 95, 1))
    cols = list(rec)
    assert cols[0] == "S.NO" and rec["S.NO"] == 7
    assert "S.No" not in rec
    assert rec["Custom"] == "x"
    assert rec["Minimum Price Alfa"] == 90 and rec["Maximum Price Alfa"] == 120
    assert rec["Minimum Price Digi"] == 95 and rec["Maximum Price Digi"] == 95
    assert rec["Alfa Offers Found"] == 3 and rec["Digi Offers Found"] == 1
    # counts sit between Maximum Price Digi and Final Price Alfa
    assert cols.index("Maximum Price Digi") + 1 == cols.index("Alfa Offers Found")
    assert cols.index("Digi Offers Found") + 1 == cols.index("Final Price Alfa")
    # risk alerts are the final two columns
    assert cols[-2:] == ["Alfa Risk Alert", "Digi Risk Alert"]


def test_range_record_leaves_pricing_columns_empty() -> None:
    rec = build_range_record(_product(), MarketRange(1, 2, 2), MarketRange(1, 2, 2))
    for col in (
        "Shipping Estimate", "Commision", "Digi Effective Commision", "Total Without Profit",
        "Calculation", "Final Price Alfa", "Final Price Digi", "Alfa Status", "Digi Status",
        "Alfa Real Profit", "Digi Real Profit", "Alfa Reason", "Digi Reason",
    ):  # fmt: skip
        assert rec[col] == "", col


def test_range_record_down_platform_blank_with_alert() -> None:
    rec = build_range_record(
        _product(), MarketRange(10, 20, 2), MarketRange(None, None, 0, is_down=True)
    )
    assert rec["Digi Risk Alert"] == "SERVER_DOWN"
    assert rec["Alfa Risk Alert"] == "NONE"
    assert rec["Minimum Price Digi"] is None


# ---------------------------------------------------------------- T3

import asyncio  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402

from pricing_engine.range_pipeline import run_range_pipeline  # noqa: E402


def _write_catalog(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _run(path: Path, tmp_path: Path, alfa: AsyncMock, digi: AsyncMock) -> pd.DataFrame:
    with (
        patch("pricing_engine.range_pipeline.scrape_alfamall", alfa),
        patch("pricing_engine.range_pipeline.scrape_digimall", digi),
        patch("pricing_engine.range_pipeline.RANGE_STAGGER_SECONDS", 0),
    ):
        return asyncio.run(
            run_range_pipeline(path, concurrency=2, verbose=False, export_dir=tmp_path / "out")
        )


def test_range_pipeline_brand_name_only_and_order(tmp_path: Path) -> None:
    cat = _write_catalog(tmp_path / "list.csv", "Brand,Name\nGree,GS-12XPH32\nHaier,HSU-18\n")
    alfa = AsyncMock(
        side_effect=[ScrapeResult(offers=[_offer("A", 100), _offer("B", 150)])] * 2
    )
    digi = AsyncMock(side_effect=[ScrapeResult(offers=[_offer("D", 90)])] * 2)
    df = _run(cat, tmp_path, alfa, digi)
    assert list(df["S.NO"]) == [1, 2]
    assert list(df["Minimum Price Alfa"]) == [100, 100]
    assert list(df["Maximum Price Alfa"]) == [150, 150]
    assert list(df["Digi Offers Found"]) == [1, 1]


def test_range_pipeline_scrapes_without_floor(tmp_path: Path) -> None:
    cat = _write_catalog(tmp_path / "list.csv", "Brand,Name\nGree,GS-12XPH32\n")
    alfa = AsyncMock(return_value=ScrapeResult(offers=[]))
    digi = AsyncMock(return_value=ScrapeResult(offers=[]))
    _run(cat, tmp_path, alfa, digi)
    for mock in (alfa, digi):
        kwargs = mock.call_args.kwargs
        assert kwargs.get("floor_price") is None


def test_range_pipeline_one_platform_down_does_not_break(tmp_path: Path) -> None:
    cat = _write_catalog(tmp_path / "list.csv", "Brand,Name\nGree,GS-12XPH32\n")
    alfa = AsyncMock(return_value=ScrapeResult(offers=[], is_success=False, error_detail="x"))
    digi = AsyncMock(return_value=ScrapeResult(offers=[_offer("D", 90)]))
    df = _run(cat, tmp_path, alfa, digi)
    assert df.loc[0, "Alfa Risk Alert"] == "SERVER_DOWN"
    assert df.loc[0, "Digi Risk Alert"] == "NONE"
    assert df.loc[0, "Minimum Price Digi"] == 90


def test_range_pipeline_missing_brand_raises(tmp_path: Path) -> None:
    cat = _write_catalog(tmp_path / "list.csv", "Brand,Name\n,GS-12XPH32\n")
    with pytest.raises(ValueError, match="Brand"):
        _run(cat, tmp_path, AsyncMock(), AsyncMock())


def test_range_pipeline_accepts_common_column_aliases(tmp_path: Path) -> None:
    """Range mode accepts 'Title', 'Product Name', 'Model' as aliases for 'Name' just like main pipeline."""
    for col_alias in ("Title", "Product Name", "Product Title", "Model"):
        cat = _write_catalog(tmp_path / f"list_{col_alias.replace(' ', '_')}.csv", f"Brand,{col_alias}\nGree,GS-12XPH32\n")
        alfa = AsyncMock(return_value=ScrapeResult(offers=[_offer("A", 100)]))
        digi = AsyncMock(return_value=ScrapeResult(offers=[_offer("D", 90)]))
        df = _run(cat, tmp_path, alfa, digi)
        assert list(df["Name"]) == ["GS-12XPH32"]


def test_range_pipeline_missing_name_column_raises(tmp_path: Path) -> None:
    cat = _write_catalog(tmp_path / "list.csv", "Brand,Category\nGree,X\n")
    with pytest.raises(ValueError, match="Name"):
        _run(cat, tmp_path, AsyncMock(), AsyncMock())


def test_range_pipeline_name_only_auto_derives_brand(tmp_path: Path) -> None:
    """If Brand column is omitted, range mode auto-derives Brand from the leading word of Name."""
    cat = _write_catalog(tmp_path / "list.csv", "Name\nTCL 55 Inch 55C6KS UHD\nDawlance DW-6550 C\n")
    alfa = AsyncMock(return_value=ScrapeResult(offers=[_offer("A", 100)]))
    digi = AsyncMock(return_value=ScrapeResult(offers=[_offer("D", 90)]))
    df = _run(cat, tmp_path, alfa, digi)
    assert list(df["Brand"]) == ["TCL", "Dawlance"]
    assert list(df["S.NO"]) == [1, 2]


def test_range_pipeline_writes_csv_and_xlsx(tmp_path: Path) -> None:
    cat = _write_catalog(tmp_path / "list.csv", "Brand,Name\nGree,GS-12XPH32\n")
    alfa = AsyncMock(return_value=ScrapeResult(offers=[_offer("A", 100)]))
    digi = AsyncMock(return_value=ScrapeResult(offers=[_offer("D", 90)]))
    _run(cat, tmp_path, alfa, digi)
    out = tmp_path / "out"
    assert (out / "csv" / "list_range_latest.csv").is_file()
    assert (out / "xlsx" / "list_range_latest.xlsx").is_file()


# ---------------------------------------------------------------- T4

from datetime import datetime  # noqa: E402

from pricing_engine.exporter import export_range_results  # noqa: E402


def _range_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "S.NO": 1.0, "Brand": "Gree", "Name": "M1",
                "Minimum Price Alfa": 90000.0, "Maximum Price Alfa": 120000.0,
                "Minimum Price Digi": None, "Maximum Price Digi": None,
                "Alfa Offers Found": 3, "Digi Offers Found": 0,
                "Alfa Risk Alert": "NONE", "Digi Risk Alert": "NO_OFFERS",
            }
        ]
    )  # fmt: skip


def test_export_range_results_files_and_formats(tmp_path: Path) -> None:
    ts = datetime(2026, 10, 3, 12, 0, 0)
    man = export_range_results(
        _range_df(), "My List.csv", output_dir=tmp_path, timestamp=ts, render_panel=False
    )
    assert man.csv_path == tmp_path / "csv" / "My List_range_20261003_120000.csv"
    assert man.csv_latest == tmp_path / "csv" / "My List_range_latest.csv"
    assert man.xlsx_path == tmp_path / "xlsx" / "My List_range_20261003_120000.xlsx"
    assert man.xlsx_latest == tmp_path / "xlsx" / "My List_range_latest.xlsx"

    csv_text = man.csv_path.read_text(encoding="utf-8")
    assert "90000.0" not in csv_text and "90000" in csv_text
    assert csv_text.splitlines()[1].startswith("1,")

    xl = pd.read_excel(man.xlsx_path)
    assert xl.loc[0, "Minimum Price Alfa"] == 90000
    assert xl.loc[0, "S.NO"] == 1
    assert pd.isna(xl.loc[0, "Minimum Price Digi"])


def test_export_range_results_locked_xlsx_does_not_crash(tmp_path: Path) -> None:
    real = pd.DataFrame.to_excel

    def flaky(self: pd.DataFrame, target: object, *a: object, **k: object) -> None:
        if str(target).endswith("_range_latest.xlsx"):
            raise PermissionError("locked by Excel")
        real(self, target, *a, **k)  # type: ignore[arg-type]

    with patch.object(pd.DataFrame, "to_excel", flaky):
        man = export_range_results(_range_df(), "l.csv", output_dir=tmp_path, render_panel=False)
    assert man.csv_latest.is_file()
    assert man.xlsx_path is not None and man.xlsx_path.is_file()
    assert man.xlsx_latest is None
    assert man.warnings


def test_range_pipeline_headerless_single_column(tmp_path: Path) -> None:
    cat = _write_catalog(tmp_path / "raw_titles.csv", "Haier HRF-276 EBD 276 Liters\nDawlance 9173WB 12 Cu Ft\n")
    alfa = AsyncMock(return_value=ScrapeResult(offers=[_offer("A", 80_000)]))
    digi = AsyncMock(return_value=ScrapeResult(offers=[]))
    df = _run(cat, tmp_path, alfa, digi)
    assert len(df) == 2
    assert list(df["S.NO"]) == [1, 2]
    assert df.loc[0, "Name"] == "Haier HRF-276 EBD 276 Liters"
    assert df.loc[1, "Name"] == "Dawlance 9173WB 12 Cu Ft"

