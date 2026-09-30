"""Catalog CSV Ingestion & Pre-flight Validation.

Reads, sanitizes, and validates catalog CSV files with strict required
column enforcement, whitespace cleanup, and backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pricing_engine.models import ProductInput

console = Console()

REQUIRED_COLUMNS: list[str] = [
    "Brand",
    "Name",
    "Net Price",
    "Length",
    "Width",
    "Height",
]

INVALID_BRAND_VALUES: frozenset[str] = frozenset(
    {"", "-", "--", "---", "_", ".", "/", "\\", "n/a", "na", "nan", "none", "null", "?"}
)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert arbitrary values to float, handling strings with commas or NaNs."""
    if val is None or pd.isna(val):
        return default
    try:
        clean_str = str(val).replace(",", "").strip()
        return float(clean_str)
    except (ValueError, TypeError):
        return default


def _extract_sno(row: pd.Series | dict[str, Any], default: int) -> int | str:
    """Extract serial number from row checking various casing or fallback to 1-based index."""
    for key in ("S.NO", "S.No", "S. No", "S.No.", "SNO", "sno", "Serial No", "Serial Number"):
        val = row.get(key)
        if val is not None and not pd.isna(val) and str(val).strip() != "":
            try:
                f = float(val)
                if f.is_integer():
                    return int(f)
            except (ValueError, TypeError):
                pass
            return str(val).strip()
    return default


@dataclass(frozen=True, slots=True)
class IngestionReport:
    """Pre-flight audit report generated upon ingesting a catalog CSV."""

    source_file: str
    total_rows: int
    valid_rows: int
    profit_source: str  # 'column' | 'default'


def render_ingestion_banner(report: IngestionReport) -> None:
    """Render a clean Rich pre-flight banner showing ingestion statistics."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column(style="green")

    table.add_row("Source File:", report.source_file)
    table.add_row("Total Items:", str(report.total_rows))
    table.add_row("Valid Items:", str(report.valid_rows))
    table.add_row("Profit Policy:", f"From {report.profit_source.upper()} (Rs. 500 default)")

    panel = Panel(
        table,
        title="[bold green]📦 Catalog Pre-flight Ingestion[/bold green]",
        border_style="green",
        expand=False,
    )
    console.print(panel)


def ingest_catalog(
    csv_path: str | Path,
    render_banner: bool = True,
) -> tuple[list[ProductInput], IngestionReport]:
    """Ingest, clean, and validate a catalog CSV file.

    Args:
        csv_path: Path to the input CSV file.
        render_banner: If True, renders a Rich pre-flight banner to console.

    Returns:
        A tuple of (list of ProductInput models, IngestionReport).

    Raises:
        FileNotFoundError: If the provided file does not exist.
        ValueError: If any required column is missing from the CSV.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Input catalog CSV not found: {path}")

    df = pd.read_csv(path)

    # Clean and strip whitespace from all column headers
    df.columns = [str(c).strip() for c in df.columns]

    # Validate required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in CSV: {sorted(missing)}. "
            f"Expected at least: {REQUIRED_COLUMNS}"
        )

    has_profit_col = "Profit" in df.columns
    profit_source = "column" if has_profit_col else "default"

    products: list[ProductInput] = []
    for idx, (_, row) in enumerate(df.iterrows()):
        sno = _extract_sno(row, idx + 1)

        raw_name = row.get("Name")
        name = str(raw_name).strip() if (raw_name is not None and not pd.isna(raw_name)) else ""
        if not name or name.lower() in ("nan", "none", "-", "--", "n/a"):
            raise ValueError(
                f"Row {idx + 1}: Product 'Name' is empty or missing in CSV. Please enter the product name."
            )

        raw_brand = row.get("Brand")
        brand = str(raw_brand).strip() if (raw_brand is not None and not pd.isna(raw_brand)) else ""

        # Strictly enforce non-empty, valid brand value in Brand column
        if not brand or brand.lower() in INVALID_BRAND_VALUES:
            raise ValueError(
                f"Row {idx + 1} ('{name}'): 'Brand' column is empty or invalid ('{brand or raw_brand}'). "
                "Please enter a valid brand name in the 'Brand' column for this product. "
                "Products cannot be processed or matched without a brand because without it, the wrong product could be matched."
            )

        length = _safe_float(row.get("Length"), 0.0)
        width = _safe_float(row.get("Width"), 0.0)
        height = _safe_float(row.get("Height"), 0.0)
        net_price = _safe_float(row.get("Net Price"), 0.0)

        # Per-row profit: use column if provided and valid, otherwise fallback to 500.0
        profit_val = row.get("Profit") if has_profit_col else None
        profit = _safe_float(profit_val, 500.0) if profit_val is not None else 500.0

        product = ProductInput(
            sno=sno,
            brand=brand,
            name=name,
            length=length,
            width=width,
            height=height,
            net_price=net_price,
            profit=profit,
            raw_row=row.to_dict(),
        )
        products.append(product)

    report = IngestionReport(
        source_file=path.name,
        total_rows=len(df),
        valid_rows=len(products),
        profit_source=profit_source,
    )

    if render_banner and len(products) > 0:
        render_ingestion_banner(report)

    return products, report
