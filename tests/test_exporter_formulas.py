"""Tests for dynamic Excel formula generation and dual CSV/XLSX export."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pandas as pd

import config
from pricing_engine.exporter import (
    ExportManifest,
    export_results,
)


def test_export_results_dual_artifacts_with_formulas(tmp_path: Path) -> None:
    out_dir = tmp_path / "outputs"
    df = pd.DataFrame(
        {
            "S.NO": [1, 2],
            "Brand": ["Haier", "Gree"],
            "Name": ["Haier Washer 15KG", "Gree Split AC 1.5T"],
            "Net Price": [100000, 140000],
            "Length": [60.0, 100.0],
            "Width": [60.0, 40.0],
            "Height": [85.0, 90.0],
            "Profit": [1000, 1500],
            "Shipping Estimate": [4284, 5040],
            "Commision": ["10.00%", "10.00%"],
            "Digi Effective Commision": ["8.00%", "10.00%"],
            "Total Without Profit": [113352, 161156],
            "Calculation": [117000, 162800],
            "Minimum Price Alfa": [116427, 161711],
            "Maximum Price Alfa": [140000, 190000],
            "Minimum Price Digi": [113896, 161711],
            "Maximum Price Digi": [140000, 190000],
            "Final Price Alfa": [122899, 168999],
            "Alfa Status": ["WINNER", "WINNER"],
            "Final Price Digi": [121899, 167899],
            "Digi Status": ["WINNER", "WINNER"],
            "Alfa Real Profit": [6325, 7059],
            "Digi Real Profit": [7863, 6069],
            "Alfa Reason": ["Undercut lowest competitor", "Undercut lowest competitor"],
            "Digi Reason": ["Undercut lowest competitor", "Undercut lowest competitor"],
            "Alfa Risk Alert": ["NONE", "NONE"],
            "Digi Risk Alert": ["NONE", "NONE"],
        }
    )

    fixed_dt = datetime(2026, 10, 2, 10, 30, 0)
    manifest = export_results(
        df=df,
        source_filename="catalog_input.csv",
        output_dir=out_dir,
        timestamp=fixed_dt,
        render_panel=False,
    )

    assert isinstance(manifest, ExportManifest)
    assert manifest.total_rows == 2

    # 1. Verify both CSV artifacts exist
    assert manifest.timestamped_path.is_file()
    assert manifest.latest_path.is_file()
    assert manifest.timestamped_path.name == "catalog_input_repriced_20261002_103000.csv"
    assert manifest.latest_path.name == "catalog_input_repriced_latest.csv"

    # 2. Verify both XLSX artifacts exist
    assert manifest.timestamped_xlsx_path is not None
    assert manifest.latest_xlsx_path is not None
    assert manifest.timestamped_xlsx_path.is_file()
    assert manifest.latest_xlsx_path.is_file()
    assert manifest.timestamped_xlsx_path.name == "catalog_input_repriced_20261002_103000.xlsx"
    assert manifest.latest_xlsx_path.name == "catalog_input_repriced_latest.xlsx"

    # 3. Load Excel workbook and verify dynamic formulas
    wb = openpyxl.load_workbook(manifest.latest_xlsx_path)
    ws = wb.active
    assert ws.title == "Repriced Catalog"

    # Verify freeze pane
    assert ws.freeze_panes == "A2"

    # Read row 2 (first product) formulas
    headers = [cell.value for cell in ws[1]]
    col_map = {h: openpyxl.utils.get_column_letter(i + 1) for i, h in enumerate(headers)}

    # Shipping Estimate formula check
    ship_val = ws[f"{col_map['Shipping Estimate']}2"].value
    assert isinstance(ship_val, str) and ship_val.startswith("=ROUNDUP")
    assert f"{col_map['Length']}2" in ship_val
    assert f"{col_map['Width']}2" in ship_val
    assert f"{col_map['Height']}2" in ship_val

    # Total Without Profit formula check
    twop_val = ws[f"{col_map['Total Without Profit']}2"].value
    assert isinstance(twop_val, str) and twop_val.startswith("=ROUND")
    assert f"{col_map['Net Price']}2" in twop_val
    assert f"{col_map['Shipping Estimate']}2" in twop_val

    # Calculation formula check (dynamic cell reference to Commision)
    calc_val = ws[f"{col_map['Calculation']}2"].value
    assert isinstance(calc_val, str) and calc_val.startswith("=ROUND")
    assert f"{col_map['Profit']}2" in calc_val
    assert f"{col_map['Commision']}2" in calc_val

    # Commission cell numeric percentage check
    comm_cell = ws[f"{col_map['Commision']}2"]
    assert comm_cell.value == round(config.ALFA_COMMISSION_PCT / 100.0, 4)
    assert comm_cell.number_format == "0.00%"

    # Minimum Price Alfa & Digi check (real scraped market numbers, NOT formulas)
    min_alfa_val = ws[f"{col_map['Minimum Price Alfa']}2"].value
    min_digi_val = ws[f"{col_map['Minimum Price Digi']}2"].value
    assert min_alfa_val == 116427
    assert min_digi_val == 113896

    # Real Profit formulas check
    prof_alfa_val = ws[f"{col_map['Alfa Real Profit']}2"].value
    prof_digi_val = ws[f"{col_map['Digi Real Profit']}2"].value
    assert isinstance(prof_alfa_val, str) and f"{config.get_alfa_payout_rate():.2f}" in prof_alfa_val
    assert (
        isinstance(prof_digi_val, str)
        and f"{col_map['Digi Effective Commision']}2" in prof_digi_val
    )

    # 4. Verify CSV content remains clean integer format for portal upload
    csv_df = pd.read_csv(manifest.latest_path, dtype=str)
    assert csv_df["Final Price Alfa"].iloc[0] == "122899"
    assert csv_df["Total Without Profit"].iloc[0] == "113352"
    assert csv_df["Calculation"].iloc[0] == "117000"
    assert not csv_df["Total Without Profit"].iloc[0].startswith("=")


def test_excel_formulas_with_mutated_commissions_and_no_find_hacks(tmp_path: Path) -> None:
    """Verify Excel formulas adapt dynamically under non-standard commission rates with zero FIND hacks."""
    out_dir = tmp_path / "mutated_outputs"
    df = pd.DataFrame(
        {
            "S.NO": [1],
            "Brand": ["Dawlance"],
            "Name": ["Dawlance Inverter AC"],
            "Net Price": [100000],
            "Length": [60.0],
            "Width": [40.0],
            "Height": [80.0],
            "Profit": [750],
            "Shipping Estimate": [4000],
            "Commision": ["12.00%"],
            "Digi Effective Commision": ["7.00%"],
            "Total Without Profit": [111828],
            "Calculation": [114489],
            "Minimum Price Alfa": [115000],
            "Maximum Price Alfa": [120000],
            "Minimum Price Digi": [114000],
            "Maximum Price Digi": [119000],
            "Final Price Alfa": [118999],
            "Alfa Status": ["WINNER"],
            "Final Price Digi": [117999],
            "Digi Status": ["WINNER"],
            "Alfa Real Profit": [4719],
            "Digi Real Profit": [9739],
            "Alfa Reason": ["Won"],
            "Digi Reason": ["Won"],
            "Alfa Risk Alert": ["NONE"],
            "Digi Risk Alert": ["NONE"],
        }
    )

    with (
        patch.object(config, "ALFA_COMMISSION_PCT", 12.0),
        patch.object(config, "DIGI_STANDARD_COMMISSION_PCT", 12.0),
        patch.object(config, "DIGI_LEVERAGE_COMMISSION_PCT", 7.0),
        patch.object(config, "COMPANY_MIN_PROFIT_PKR", 750.0),
        patch.object(config, "COURIER_RATE_PER_KG", 85.0),
        patch.object(config, "VOLUMETRIC_DIVISOR", 4500.0),
    ):
        manifest = export_results(
            df=df,
            source_filename="mutated_catalog.csv",
            output_dir=out_dir,
            render_panel=False,
        )
        wb = openpyxl.load_workbook(manifest.latest_xlsx_path)
        ws = wb.active
        headers = [c.value for c in ws[1]]
        col_map = {h: openpyxl.utils.get_column_letter(i + 1) for i, h in enumerate(headers)}

        twop_formula = ws[f"{col_map['Total Without Profit']}2"].value
        calc_formula = ws[f"{col_map['Calculation']}2"].value
        alfa_profit_formula = ws[f"{col_map['Alfa Real Profit']}2"].value
        digi_profit_formula = ws[f"{col_map['Digi Real Profit']}2"].value

        # 1. Zero 'FIND' substring hacks in any formula
        for f_name, f_val in [
            ("Total Without Profit", twop_formula),
            ("Calculation", calc_formula),
            ("Alfa Real Profit", alfa_profit_formula),
            ("Digi Real Profit", digi_profit_formula),
        ]:
            assert "FIND(" not in str(f_val), f"Fragile FIND() hack detected in {f_name}: {f_val}"

        # 2. Total Without Profit dynamically references commission column
        assert f"{col_map['Digi Effective Commision']}2" in twop_formula

        # 3. Calculation dynamically references Commision column and configured profit target 750
        assert f"{col_map['Commision']}2" in calc_formula
        assert "750" in calc_formula

        # 4. Profit formulas dynamically reference commission cell
        assert f"{col_map['Commision']}2" in alfa_profit_formula
        assert f"{col_map['Digi Effective Commision']}2" in digi_profit_formula
