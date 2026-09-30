"""Tests for exporter module and timestamped catalog management."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from pricing_engine.exporter import (
    ExportManifest,
    export_results,
    format_export_price,
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

    expected_ts_file = out_dir / "Gree_AC_repriced_20260930_133015.csv"
    expected_latest_file = out_dir / "Gree_AC_repriced_latest.csv"

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
