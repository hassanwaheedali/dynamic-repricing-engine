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


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _get_fixture(filename: str) -> Path:
    p = FIXTURES_DIR / filename
    if p.exists():
        return p
    return Path(filename)


def test_ingest_catalog_legacy_gree_csv() -> None:
    legacy_path = _get_fixture("Gree_Uploading_on_DigiMall_and_Price.csv")
    if not legacy_path.is_file():
        pytest.skip("Gree CSV fixture not found")

    products, report = ingest_catalog(legacy_path, render_banner=False)

    assert len(products) > 0
    assert report.total_rows == len(products)
    assert products[0].brand == "Gree"
    assert products[0].net_price > 0


def test_ingest_catalog_legacy_haier_csv() -> None:
    legacy_path = _get_fixture("Haier_Washing_Machines_Uploading_and_Price.csv")
    if not legacy_path.is_file():
        pytest.skip("Haier CSV fixture not found")

    products, report = ingest_catalog(legacy_path, render_banner=False)

    assert len(products) > 0
    assert report.total_rows == len(products)
    assert products[0].brand == "Haier"


def test_ingest_catalog_empty_brand_cell_raises(tmp_path: Path) -> None:
    csv_file = tmp_path / "empty_brand.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n"
        ",Dawlance 4467 SD MINI BAR,55000,50,50,85\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        ingest_catalog(csv_file, render_banner=False)

    assert "'Brand' column is empty or invalid" in str(exc_info.value)
    assert "Please enter a valid brand name in the 'Brand' column" in str(exc_info.value)


def test_ingest_catalog_with_title_alias(tmp_path: Path) -> None:
    csv_file = tmp_path / "title_catalog.csv"
    csv_file.write_text(
        "Brand,Title,Net Price\n"
        "Haier,Haier Automatic Washing Machine 10 KG,70000\n",
        encoding="utf-8",
    )
    products, report = ingest_catalog(csv_file, render_banner=False)
    assert len(products) == 1
    assert products[0].brand == "Haier"
    assert products[0].name == "Haier Automatic Washing Machine 10 KG"
    assert products[0].net_price == 70000.0


def test_ingest_catalog_tab_separated(tmp_path: Path) -> None:
    tsv_file = tmp_path / "catalog.tsv"
    tsv_file.write_text(
        "Brand\tTitle\tNet Price\n"
        "Gree\tGREE SPLIT AC 1.5 TON\t185000\n",
        encoding="utf-8",
    )
    products, report = ingest_catalog(tsv_file, render_banner=False)
    assert len(products) == 1
    assert products[0].brand == "Gree"
    assert products[0].name == "GREE SPLIT AC 1.5 TON"
    assert products[0].net_price == 185000.0


def test_normalize_catalog_columns_prevents_duplicate_collisions() -> None:
    from pricing_engine.ingestion import normalize_catalog_columns

    # Case 1: Only Title present -> mapped to Name
    assert normalize_catalog_columns(["Brand", "Title", "Net Price"]) == ["Brand", "Name", "Net Price"]

    # Case 2: Both Name and Title present -> Title is NOT renamed to Name (avoids collision!)
    assert normalize_catalog_columns(["Brand", "Name", "Title", "Net Price"]) == ["Brand", "Name", "Title", "Net Price"]

    # Case 3: Both Net Price and Cost present -> Cost is NOT renamed to Net Price
    assert normalize_catalog_columns(["Brand", "Name", "Net Price", "Cost"]) == ["Brand", "Name", "Net Price", "Cost"]

    # Case 4: Legacy Name with space stripped by default for ingestion
    assert normalize_catalog_columns(["Brand", "Name ", "Net Price"]) == ["Brand", "Name", "Net Price"]

    # Case 5: Legacy Name with space preserved when preserve_name_space=True
    assert normalize_catalog_columns(["Brand", "Name ", "Net Price"], preserve_name_space=True) == ["Brand", "Name ", "Net Price"]


def test_ingest_catalog_with_both_name_and_title(tmp_path: Path) -> None:
    csv_file = tmp_path / "dual_col.csv"
    csv_file.write_text(
        "Brand,Name,Title,Net Price\n"
        "Dawlance,DWT 9057 EZ,Dawlance DWT 9057 EZ Washing Machine,48000\n",
        encoding="utf-8",
    )
    products, report = ingest_catalog(csv_file, render_banner=False)
    assert len(products) == 1
    assert products[0].brand == "Dawlance"
    assert products[0].name == "DWT 9057 EZ"
    assert products[0].net_price == 48000.0


def test_read_catalog_csv_handles_trailing_commas_and_jagged_rows(tmp_path: Path) -> None:
    """Verify read_catalog_csv handles stray trailing commas on jagged rows without dropping data."""
    from pricing_engine.ingestion import read_catalog_csv

    csv_file = tmp_path / "jagged.csv"
    csv_file.write_text(
        'Brand,Title,Net Price\n'
        'Dawlance,Dawlance DW 10115 - 10KG,"21,500"\n'
        'Dawlance,Dawlance DW 90100 - 9KG,"21,500",\n'  # Trailing comma causing 4 fields instead of 3
        'Dawlance,Dawlance DW 15140 15 KG,"43,500"\n',
        encoding="utf-8",
    )
    df = read_catalog_csv(csv_file)
    assert len(df) == 3
    assert list(df["Brand"]) == ["Dawlance", "Dawlance", "Dawlance"]
    assert "Dawlance DW 90100 - 9KG" in list(df["Title"])
    assert list(df["Net Price"]) == ['21,500', '21,500', '43,500']


def test_read_catalog_csv_drops_unnamed_trailing_header_columns(tmp_path: Path) -> None:
    """Verify read_catalog_csv and ingest_catalog drop stray Unnamed: columns from trailing header commas."""
    from pricing_engine.ingestion import read_catalog_csv

    # Simulate dawlance.csv header which had: 'Title,Brand,Net Price,'
    csv_file = tmp_path / "trailing_header_comma.csv"
    csv_file.write_text(
        "Title,Brand,Net Price,\n"
        "Dawlance DW 10090,Dawlance,33000,\n"
        "Dawlance DW 10095,Dawlance,28000,\n",
        encoding="utf-8",
    )
    df = read_catalog_csv(csv_file)
    assert len(df) == 2
    assert "Unnamed: 3" not in df.columns
    assert list(df.columns) == ["Title", "Brand", "Net Price"]

    products, report = ingest_catalog(csv_file, render_banner=False)
    assert len(products) == 2
    for p in products:
        assert not any(str(k).lower().startswith("unnamed:") for k in p.raw_row)




