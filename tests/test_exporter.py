"""Tests for exporter module and timestamped catalog management."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from pricing_engine.exporter import (
    ExportManifest,
    export_range_results,
    export_results,
    export_winning_5pct_results,
    filter_alfa_only_columns,
    format_export_price,
    resolve_option_output_dir,
)


def test_format_export_price() -> None:
    assert format_export_price(147000) == "147000"
    assert format_export_price(147000.0) == "147000"
    assert format_export_price("147,000") == "147000"
    assert format_export_price(None) == ""
    assert format_export_price(float("nan")) == ""
    assert format_export_price("NaN") == ""
    assert format_export_price("") == ""


def test_export_results_creates_both_files_and_dir(tmp_path: Path) -> None:
    out_dir = tmp_path / "custom_outputs"
    assert not out_dir.exists()

    df = pd.DataFrame(
        {
            "Brand": ["Gree", "Gree"],
            "Name": ["Gree AC 1", "Gree AC 2"],
            "Final Price Alfa": [147000.0, 183000.0],
            "Final Price Digi": [145000.0, float("nan")],
            "Alfa Real Profit": [4500.0, 5200.0],
        }
    )

    fixed_dt = datetime(2026, 9, 30, 13, 30, 15)
    manifest = export_results(
        df=df,
        source_filename="Gree_AC.csv",
        output_dir=out_dir,
        timestamp=fixed_dt,
        render_panel=False,
    )

    assert isinstance(manifest, ExportManifest)
    assert out_dir.is_dir()
    assert manifest.timestamp == "20260930_133015"
    assert manifest.total_rows == 2

    expected_ts_file = out_dir / "csv" / "Gree_AC_repriced_20260930_133015.csv"
    expected_latest_file = out_dir / "csv" / "Gree_AC_repriced_latest.csv"

    assert manifest.timestamped_path == expected_ts_file
    assert manifest.latest_path == expected_latest_file

    assert expected_ts_file.is_file()
    assert expected_latest_file.is_file()

    # Content of both files must be identical
    ts_content = expected_ts_file.read_text(encoding="utf-8")
    latest_content = expected_latest_file.read_text(encoding="utf-8")
    assert ts_content == latest_content

    # Check pure integer formatting (no .0 drift)
    loaded_df = pd.read_csv(expected_latest_file, dtype=str)
    assert loaded_df["Final Price Alfa"].iloc[0] == "147000"
    assert loaded_df["Final Price Alfa"].iloc[1] == "183000"
    assert loaded_df["Final Price Digi"].iloc[0] == "145000"
    # NaN price should be empty string
    assert pd.isna(loaded_df["Final Price Digi"].iloc[1]) or loaded_df["Final Price Digi"].iloc[1] == ""


def test_export_results_handles_existing_repriced_suffix(tmp_path: Path) -> None:
    out_dir = tmp_path / "outputs"
    df = pd.DataFrame({"Brand": ["Haier"]})

    manifest = export_results(
        df=df,
        source_filename="Haier_Washers_repriced.csv",
        output_dir=out_dir,
        timestamp=datetime(2026, 9, 30, 12, 0, 0),
        render_panel=False,
    )

    assert manifest.timestamped_path.name == "Haier_Washers_repriced_20260930_120000.csv"
    assert manifest.latest_path.name == "Haier_Washers_repriced_latest.csv"


def test_resolve_option_output_dir(tmp_path: Path) -> None:
    input_file = tmp_path / "inputs" / "wm.csv"
    input_file.parent.mkdir(parents=True, exist_ok=True)
    input_file.write_text("Brand,Name,Net Price\n", encoding="utf-8")

    # Default base_dir is data/outputs
    opt1_default = resolve_option_output_dir(input_file, option=1)
    assert opt1_default == Path("data/outputs") / "wm" / "option_1"

    # Custom base_dir
    custom_base = tmp_path / "outputs"
    opt1_dir = resolve_option_output_dir(input_file, option=1, base_dir=custom_base)
    assert opt1_dir == custom_base / "wm" / "option_1"
    assert opt1_dir.is_dir()

    # Option 1 aliases
    assert resolve_option_output_dir(input_file, option="reprice", base_dir=custom_base) == opt1_dir
    assert resolve_option_output_dir(input_file, option="option_1", base_dir=custom_base) == opt1_dir

    # Option 2: Market range
    opt2_dir = resolve_option_output_dir(input_file, option=2, base_dir=custom_base)
    assert opt2_dir == custom_base / "wm" / "option_2"
    assert opt2_dir.is_dir()
    assert resolve_option_output_dir(input_file, option="range", base_dir=custom_base) == opt2_dir

    # Option 3: 5% personal commission
    opt3_dir = resolve_option_output_dir(input_file, option=3, base_dir=custom_base)
    assert opt3_dir == custom_base / "wm" / "option_3"
    assert opt3_dir.is_dir()
    assert resolve_option_output_dir(input_file, option="5pct", base_dir=custom_base) == opt3_dir


def test_export_results_creates_csv_and_xlsx_subfolders(tmp_path: Path) -> None:
    out_dir = tmp_path / "option_1"
    df = pd.DataFrame(
        {
            "Brand": ["Haier"],
            "Name": ["Haier Washer 15KG"],
            "Net Price": [50000],
            "Final Price Alfa": [60000],
            "Final Price Digi": [59000],
            "Alfa Real Profit": [1000],
            "Digi Real Profit": [1500],
        }
    )

    manifest = export_results(
        df=df,
        source_filename="wm.csv",
        output_dir=out_dir,
        timestamp=datetime(2026, 10, 27, 12, 0, 0),
        render_panel=False,
    )

    assert (out_dir / "csv").is_dir()
    assert (out_dir / "xlsx").is_dir()

    expected_csv_ts = out_dir / "csv" / "wm_repriced_20261027_120000.csv"
    expected_csv_latest = out_dir / "csv" / "wm_repriced_latest.csv"
    expected_xlsx_ts = out_dir / "xlsx" / "wm_repriced_20261027_120000.xlsx"
    expected_xlsx_latest = out_dir / "xlsx" / "wm_repriced_latest.xlsx"

    assert manifest.timestamped_path == expected_csv_ts
    assert manifest.latest_path == expected_csv_latest
    assert manifest.timestamped_xlsx_path == expected_xlsx_ts
    assert manifest.latest_xlsx_path == expected_xlsx_latest

    assert expected_csv_ts.is_file()
    assert expected_csv_latest.is_file()
    assert expected_xlsx_ts.is_file()
    assert expected_xlsx_latest.is_file()


def test_export_winning_5pct_results_creates_csv_and_xlsx_subfolders(tmp_path: Path) -> None:
    out_dir = tmp_path / "option_3"
    df = pd.DataFrame(
        [
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name": "GS-18AITH21W",
                "Net Price": 100000,
                "Alfa 5% Goal": "WIN + 5% ACHIEVED",
                "Digi 5% Goal": "WIN + 5% ACHIEVED",
                "Alfa Active Sellers": 3,
                "Digi Active Sellers": 2,
                "My 5% Commission": 5000,
                "Alfa Real Profit": 6000,
                "Digi Real Profit": 6500,
            }
        ]
    )

    latest_csv, latest_xlsx, count = export_winning_5pct_results(
        df=df,
        source_filename="wm.csv",
        output_dir=out_dir,
        timestamp=datetime(2026, 10, 27, 12, 0, 0),
        personal_comm_pct=5.0,
    )

    assert count == 1
    assert (out_dir / "csv").is_dir()
    assert (out_dir / "xlsx").is_dir()

    expected_csv_ts = out_dir / "csv" / "wm_winning_5pct_20261027_120000.csv"
    expected_csv_latest = out_dir / "csv" / "wm_winning_5pct_latest.csv"
    expected_xlsx_ts = out_dir / "xlsx" / "wm_winning_5pct_20261027_120000.xlsx"
    expected_xlsx_latest = out_dir / "xlsx" / "wm_winning_5pct_latest.xlsx"

    assert latest_csv == expected_csv_latest
    assert latest_xlsx == expected_xlsx_latest
    assert expected_csv_ts.is_file()
    assert expected_csv_latest.is_file()
    assert expected_xlsx_ts.is_file()
    assert expected_xlsx_latest.is_file()


def test_full_tree_structure_options_1_2_3(tmp_path: Path) -> None:
    input_file = tmp_path / "inputs" / "wm.csv"
    input_file.parent.mkdir(parents=True, exist_ok=True)
    input_file.write_text("Brand,Name,Net Price\nHaier,Washer,50000\n", encoding="utf-8")

    custom_base = tmp_path / "outputs"
    parent_folder = custom_base / "wm"
    assert not parent_folder.exists()

    df_sample = pd.DataFrame(
        [
            {
                "S.NO": 1,
                "Brand": "Haier",
                "Name": "Haier Washer 15KG",
                "Net Price": 50000,
                "Final Price Alfa": 60000,
                "Final Price Digi": 59000,
                "Minimum Price Alfa": 60000,
                "Maximum Price Alfa": 65000,
                "Minimum Price Digi": 59000,
                "Maximum Price Digi": 64000,
                "Alfa Offers Found": 2,
                "Digi Offers Found": 1,
                "Alfa 5% Goal": "WIN + 5% ACHIEVED",
                "Digi 5% Goal": "WIN + 5% ACHIEVED",
                "Alfa Active Sellers": 2,
                "Digi Active Sellers": 1,
                "My 5% Commission": 2500,
                "Alfa Real Profit": 5000,
                "Digi Real Profit": 5500,
            }
        ]
    )

    # 1. Option 1 Export
    opt1_dir = resolve_option_output_dir(input_file, option=1, base_dir=custom_base)
    ts1 = datetime(2026, 10, 27, 10, 0, 0)
    m1 = export_results(df=df_sample, source_filename=input_file, output_dir=opt1_dir, timestamp=ts1, render_panel=False)
    assert m1.timestamped_path == parent_folder / "option_1" / "csv" / "wm_repriced_20261027_100000.csv"
    assert m1.latest_path == parent_folder / "option_1" / "csv" / "wm_repriced_latest.csv"
    assert m1.timestamped_xlsx_path == parent_folder / "option_1" / "xlsx" / "wm_repriced_20261027_100000.xlsx"
    assert m1.latest_xlsx_path == parent_folder / "option_1" / "xlsx" / "wm_repriced_latest.xlsx"

    # Second run of Option 1 with different timestamp (non-overwrite test)
    ts1_v2 = datetime(2026, 10, 27, 10, 30, 0)
    m1_v2 = export_results(df=df_sample, source_filename=input_file, output_dir=opt1_dir, timestamp=ts1_v2, render_panel=False)
    assert (parent_folder / "option_1" / "csv" / "wm_repriced_20261027_100000.csv").is_file()
    assert (parent_folder / "option_1" / "csv" / "wm_repriced_20261027_103000.csv").is_file()
    assert m1_v2.latest_path == parent_folder / "option_1" / "csv" / "wm_repriced_latest.csv"

    # 2. Option 2 Export
    opt2_dir = resolve_option_output_dir(input_file, option=2, base_dir=custom_base)
    ts2 = datetime(2026, 10, 27, 11, 0, 0)
    m2 = export_range_results(df=df_sample, source_filename=input_file, output_dir=opt2_dir, timestamp=ts2, render_panel=False)
    assert m2.csv_path == parent_folder / "option_2" / "csv" / "wm_range_20261027_110000.csv"
    assert m2.csv_latest == parent_folder / "option_2" / "csv" / "wm_range_latest.csv"
    assert m2.xlsx_path == parent_folder / "option_2" / "xlsx" / "wm_range_20261027_110000.xlsx"
    assert m2.xlsx_latest == parent_folder / "option_2" / "xlsx" / "wm_range_latest.xlsx"

    # 3. Option 3 Export
    ts3 = datetime(2026, 10, 27, 12, 0, 0)
    opt3_dir = resolve_option_output_dir(input_file, option=3, base_dir=custom_base)
    export_results(df=df_sample, source_filename=input_file, output_dir=opt3_dir, timestamp=ts3, render_panel=False)
    w_csv, w_xlsx, _ = export_winning_5pct_results(
        df=df_sample, source_filename=input_file, output_dir=opt3_dir, timestamp=ts3
    )
    assert w_csv == parent_folder / "option_3" / "csv" / "wm_winning_5pct_latest.csv"
    assert w_xlsx == parent_folder / "option_3" / "xlsx" / "wm_winning_5pct_latest.xlsx"
    assert (parent_folder / "option_3" / "csv" / "wm_repriced_latest.csv").is_file()
    assert (parent_folder / "option_3" / "xlsx" / "wm_repriced_latest.xlsx").is_file()

    # Complete structural integrity check
    for opt in ("option_1", "option_2", "option_3"):
        assert (parent_folder / opt / "csv").is_dir()
        assert (parent_folder / opt / "xlsx").is_dir()

    # Ensure output is strictly separated and NOT created inside input directory
    assert not (input_file.parent / "wm").exists()


def test_resolve_option_output_dir_security(tmp_path: Path) -> None:
    # Reject invalid/traversal option
    with pytest.raises(ValueError, match="Unsupported pricing option"):
        resolve_option_output_dir("catalog.csv", option="../../escaped", base_dir=tmp_path)

    # Empty or pure dot input raises ValueError
    with pytest.raises(ValueError, match="Invalid catalog stem"):
        resolve_option_output_dir("..", option=1, base_dir=tmp_path)

    # Stem is safely sanitized
    safe_dir = resolve_option_output_dir("weird/../../path/my@catalog!.csv", option=1, base_dir=tmp_path)
    assert safe_dir.is_relative_to(tmp_path.resolve())
    assert "option_1" in str(safe_dir)


def test_filter_alfa_only_columns_unit() -> None:
    """Verify filter_alfa_only_columns excludes every digi-key column while retaining all others."""
    df = pd.DataFrame(
        [
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name": "GS-18AITH21W",
                "Net Price": 100000,
                "Shipping Estimate": 3500,
                "Commision": "10.00%",
                "Digi Effective Commision": "8.00%",
                "Total Without Profit": 112500,
                "Calculation": 115000,
                "Minimum Price Alfa": 120000,
                "Maximum Price Alfa": 130000,
                "Minimum Price Digi": 119000,
                "Maximum Price Digi": 129000,
                "Final Price Alfa": 124899,
                "Final Price Digi": 123899,
                "Alfa Real Profit": 8909,
                "Digi Real Profit": 10487,
                "Alfa Reason": "Undercut lowest competitor",
                "Digi Reason": "Undercut at 8% tier",
                "Alfa Risk Alert": "NONE",
                "Digi Risk Alert": "NONE",
            }
        ]
    )
    filtered = filter_alfa_only_columns(df)
    for col in filtered.columns:
        assert "digi" not in col.lower(), f"Unexpected digi column in filtered output: {col}"
    assert "Minimum Price Alfa" in filtered.columns
    assert "Final Price Alfa" in filtered.columns
    assert "Alfa Real Profit" in filtered.columns
    assert "Alfa Reason" in filtered.columns
    assert "Alfa Risk Alert" in filtered.columns
    assert "Net Price" in filtered.columns
    assert "S.NO" in filtered.columns


def test_export_results_with_alfa_flag_excludes_digi_in_csv_and_xlsx(tmp_path: Path) -> None:
    """Verify export_results with platform='alfa' produces consistent CSV and XLSX without digi columns."""
    import openpyxl

    out_dir = tmp_path / "export_alfa"
    df = pd.DataFrame(
        [
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name": "GS-18AITH21W",
                "Net Price": 100000,
                "Shipping Estimate": 3500,
                "Commision": "10.00%",
                "Digi Effective Commision": "8.00%",
                "Total Without Profit": 112500,
                "Calculation": 115000,
                "Minimum Price Alfa": 120000,
                "Maximum Price Alfa": 130000,
                "Minimum Price Digi": 119000,
                "Maximum Price Digi": 129000,
                "Final Price Alfa": 124899,
                "Final Price Digi": 123899,
                "Alfa Real Profit": 8909,
                "Digi Real Profit": 10487,
                "Alfa Reason": "Undercut competitor",
                "Digi Reason": "Undercut at 8%",
                "Alfa Risk Alert": "NONE",
                "Digi Risk Alert": "NONE",
            }
        ]
    )

    manifest = export_results(
        df=df,
        source_filename="catalog.csv",
        output_dir=out_dir,
        platform="alfa",
    )

    # 1. Check CSV output
    csv_df = pd.read_csv(manifest.latest_path)
    csv_cols = list(csv_df.columns)
    for col in csv_cols:
        assert "digi" not in col.lower(), f"Digi column '{col}' found in CSV"
    assert "Final Price Alfa" in csv_cols
    assert "Alfa Real Profit" in csv_cols

    # 2. Check XLSX output
    assert manifest.latest_xlsx_path is not None and manifest.latest_xlsx_path.is_file()
    wb = openpyxl.load_workbook(manifest.latest_xlsx_path)
    ws = wb.active
    xlsx_cols = [cell.value for cell in ws[1]]
    for col in xlsx_cols:
        assert "digi" not in str(col).lower(), f"Digi column '{col}' found in XLSX"
    assert "Final Price Alfa" in xlsx_cols
    assert "Alfa Real Profit" in xlsx_cols

    # 3. CSV and XLSX columns must be 100% consistent with each other
    assert csv_cols == xlsx_cols


def test_export_results_default_keeps_all_columns(tmp_path: Path) -> None:
    """Verify default export (platform='all' or omitted) retains all platform columns."""
    out_dir = tmp_path / "export_default"
    df = pd.DataFrame(
        [
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name": "GS-18AITH21W",
                "Net Price": 100000,
                "Final Price Alfa": 124899,
                "Final Price Digi": 123899,
                "Digi Effective Commision": "8.00%",
                "Alfa Risk Alert": "NONE",
                "Digi Risk Alert": "NONE",
            }
        ]
    )

    manifest = export_results(
        df=df,
        source_filename="catalog.csv",
        output_dir=out_dir,
    )
    csv_df = pd.read_csv(manifest.latest_path)
    assert "Final Price Alfa" in csv_df.columns
    assert "Final Price Digi" in csv_df.columns
    assert "Digi Effective Commision" in csv_df.columns
    assert "Alfa Risk Alert" in csv_df.columns
    assert "Digi Risk Alert" in csv_df.columns



