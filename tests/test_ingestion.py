"""Tests for catalog CSV ingestion and pre-flight validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from pricing_engine.ingestion import IngestionReport, ingest_catalog


def test_ingest_catalog_clean_6_column_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "catalog.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92\n"
        "Gree,GREE SPLIT AC 18AITH21W-T3,183000,104,39,103\n",
        encoding="utf-8",
    )

    products, report = ingest_catalog(csv_file, render_banner=False)

    assert len(products) == 2
    assert isinstance(report, IngestionReport)
    assert report.total_rows == 2
    assert report.valid_rows == 2
    assert report.profit_source == "default"

    p1 = products[0]
    assert p1.sno == 1
    assert p1.brand == "Gree"
    assert p1.name == "GREE SPLIT AC 12AITH21W-T3"
    assert p1.net_price == 147000.0
    assert p1.length == 87.0
    assert p1.width == 35.5
    assert p1.height == 92.0
    assert p1.profit == 500.0


def test_ingest_catalog_7_column_csv_with_profit(tmp_path: Path) -> None:
    csv_file = tmp_path / "catalog_profit.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height,Profit\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92,1500\n"
        "Gree,GREE SPLIT AC 18AITH21W-T3,183000,104,39,103,\n",
        encoding="utf-8",
    )

    products, report = ingest_catalog(csv_file, render_banner=False)

    assert len(products) == 2
    assert report.profit_source == "column"
    assert products[0].profit == 1500.0
    # Empty cell defaults gracefully to 500.0
    assert products[1].profit == 500.0


def test_ingest_catalog_handles_price_with_commas(tmp_path: Path) -> None:
    csv_file = tmp_path / "catalog_commas.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n"
        'Dawlance,Dawlance Refrigerator,"125,500",60,60,160\n',
        encoding="utf-8",
    )

    products, _ = ingest_catalog(csv_file, render_banner=False)

    assert len(products) == 1
    assert products[0].net_price == 125500.0


def test_ingest_catalog_strips_column_whitespace(tmp_path: Path) -> None:
    csv_file = tmp_path / "catalog_whitespace.csv"
    csv_file.write_text(
        " Brand , Name  , Net Price , Length , Width , Height \n"
        "Haier,Haier Washing Machine,65000,60,60,85\n",
        encoding="utf-8",
    )

    products, report = ingest_catalog(csv_file, render_banner=False)

    assert len(products) == 1
    assert products[0].brand == "Haier"
    assert products[0].name == "Haier Washing Machine"


def test_ingest_catalog_missing_net_price_column_raises(tmp_path: Path) -> None:
    csv_file = tmp_path / "invalid_catalog.csv"
    csv_file.write_text(
        "Brand,Name,Length,Width,Height\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,87,35.5,92\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        ingest_catalog(csv_file, render_banner=False)

    assert "Missing required columns in CSV" in str(exc_info.value)
    assert "Net Price" in str(exc_info.value)


def test_ingest_catalog_missing_brand_column_raises(tmp_path: Path) -> None:
    csv_file = tmp_path / "invalid_catalog.csv"
    csv_file.write_text(
        "Name,Net Price,Length,Width,Height\n"
        "Gree AC,140000,87,35.5,92\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        ingest_catalog(csv_file, render_banner=False)

    assert "Brand" in str(exc_info.value)


def test_ingest_catalog_file_not_found_raises() -> None:
    with pytest.raises(FileNotFoundError):
        ingest_catalog("non_existent_file_xyz_123.csv", render_banner=False)


def test_ingest_catalog_empty_csv_headers_only(tmp_path: Path) -> None:
    csv_file = tmp_path / "empty_catalog.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n",
        encoding="utf-8",
    )

    products, report = ingest_catalog(csv_file, render_banner=False)

    assert len(products) == 0
    assert report.total_rows == 0
    assert report.valid_rows == 0


def test_ingest_catalog_legacy_gree_csv() -> None:
    legacy_path = Path("Gree_Uploading_on_DigiMall_and_Price.csv")
    if not legacy_path.is_file():
        pytest.skip("Root Gree CSV not found in workspace")

    products, report = ingest_catalog(legacy_path, render_banner=False)

    assert len(products) > 0
    assert report.total_rows == len(products)
    assert products[0].brand == "Gree"
    assert products[0].net_price > 0


def test_ingest_catalog_legacy_haier_csv() -> None:
    legacy_path = Path("Haier_Washing_Machines_Uploading_and_Price.csv")
    if not legacy_path.is_file():
        pytest.skip("Root Haier CSV not found in workspace")

    products, report = ingest_catalog(legacy_path, render_banner=False)

    assert len(products) > 0
    assert report.total_rows == len(products)
    assert products[0].brand == "Haier"
