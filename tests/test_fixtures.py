"""Test fixtures and multi-catalog data validation suite.

Validates that:
1. Haier Washing Machines input and benchmark CSVs load cleanly.
2. Cross-category catalog samples from Stock Holding Report are structured and parseable.
"""

from pathlib import Path

import pandas as pd


def test_haier_washing_machines_catalog_integrity() -> None:
    """Verify that Haier washing machines catalog contains 38 verified products."""
    catalog_path = Path("Haier_Washing_Machines_Uploading_and_Price.csv")
    assert catalog_path.exists(), "Haier washing machine catalog missing from workspace root"

    df = pd.read_csv(catalog_path)
    assert len(df) == 38, f"Expected 38 products, got {len(df)}"

    required_columns = {
        "S.NO",
        "Brand",
        "Name ",
        "Length",
        "Width",
        "Height",
        "Net Price",
        "Profit",
    }
    assert required_columns.issubset(set(df.columns)), (
        f"Missing columns: {required_columns - set(df.columns)}"
    )

    # Ensure all net prices and dimensions are valid positive numbers (strip commas if formatted as strings)
    net_prices = df["Net Price"].astype(str).str.replace(",", "").str.strip().astype(float)
    assert (net_prices > 0).all(), "Net Price must be strictly positive"
    assert (df["Length"] > 0).all(), "Length must be strictly positive"
    assert (df["Width"] > 0).all(), "Width must be strictly positive"
    assert (df["Height"] > 0).all(), "Height must be strictly positive"


def test_final_haier_repriced_benchmark_integrity() -> None:
    """Verify that the repriced Haier washing machine production benchmark is valid."""
    repriced_path = Path("final_haier_wm_repriced.csv")
    assert repriced_path.exists(), "Repriced Haier CSV missing from workspace root"

    df = pd.read_csv(repriced_path)
    assert len(df) == 38, f"Expected 38 rows, got {len(df)}"

    audit_columns = {
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
    }
    assert audit_columns.issubset(set(df.columns)), (
        f"Missing audit columns: {audit_columns - set(df.columns)}"
    )


def test_stock_holding_report_cross_category_samples() -> None:
    """Verify multi-category catalog samples across Refrigerators, ACs, Dispensers, W/M, and Microwaves."""
    stock_path = Path("Stock Holding Report - FINAC - Products - MainSheet.csv")
    assert stock_path.exists(), "Stock Holding Report missing from workspace root"

    df = pd.read_csv(stock_path)
    assert len(df) >= 700, f"Expected 700+ rows, got {len(df)}"

    categories = set(df["Category"].dropna().unique())
    assert "SPLIT AC" in categories
    assert "REFRIGERATOR" in categories
    assert "W/M" in categories
    assert "W/D" in categories

    # Verify specific representative models exist in 'Item Name' column
    names = df["Item Name"].dropna().tolist()
    assert any("276EBS SILVER" in n for n in names)
    assert any("306IDB BLACK" in n for n in names)
    assert any("MAGNA T3 INVERTER 30 MILKY" in n for n in names)
    assert any("CHROME PRO INVERTER 30" in n for n in names)
    assert any("1051 GD SILVER" in n for n in names)
    assert any("6580 CB FL" in n for n in names)
