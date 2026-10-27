"""Catalog CSV Ingestion & Pre-flight Validation.

Reads, sanitizes, and validates catalog CSV files with strict required
column enforcement, whitespace cleanup, and backward compatibility.
"""

from __future__ import annotations

import csv
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
]

COLUMN_ALIASES: dict[str, str] = {
    "title": "Name",
    "product name": "Name",
    "product title": "Name",
    "product": "Name",
    "model": "Name",
    "netprice": "Net Price",
    "net_price": "Net Price",
    "purchase price": "Net Price",
    "cost": "Net Price",
}

INVALID_BRAND_VALUES: frozenset[str] = frozenset(
    {"", "-", "--", "---", "_", ".", "/", "\\", "n/a", "na", "nan", "none", "null", "?"}
)

INVALID_NAME_VALUES: frozenset[str] = frozenset(
    {"", "-", "--", "---", "_", ".", "/", "\\", "n/a", "na", "nan", "none", "null", "?"}
)


def normalize_catalog_columns(
    columns: list[Any],
    preserve_name_space: bool = False,
) -> list[str]:
    """Normalize catalog column headers using canonical aliases without collision.

    If a target canonical column (e.g. 'Name' or 'Net Price') is already present
    in the headers, alias columns (e.g. 'Title' or 'Cost') are preserved as-is to
    prevent duplicate column name collisions in Pandas.

    Args:
        columns: List of raw column headers from CSV.
        preserve_name_space: If True and 'Name ' is present, preserve trailing space for legacy exports.
    """
    cleaned = [str(c).strip() for c in columns]
    has_legacy_name_space = "Name " in columns

    existing = set(cleaned)
    result: list[str] = []
    for raw, clean in zip(columns, cleaned, strict=True):
        if raw == "Name " and has_legacy_name_space and preserve_name_space:
            result.append("Name ")
            continue
        lower = clean.lower()
        if lower in COLUMN_ALIASES:
            target = COLUMN_ALIASES[lower]
            if target not in existing:
                result.append(target)
                existing.add(target)
            else:
                result.append(clean)
        else:
            result.append(clean)
    return result


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


def _clean_catalog_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Drop any stray empty or 'Unnamed:' columns created by trailing commas."""
    if df is None or df.empty:
        return df
    cols_to_keep = [
        c for c in df.columns if not (str(c).lower().startswith("unnamed:") or not str(c).strip())
    ]
    return df.loc[:, cols_to_keep]


def read_catalog_csv(csv_path: str | Path) -> pd.DataFrame:
    """Robustly read catalog CSV handling delimiter detection, BOMs, and jagged rows with trailing commas.

    First attempts standard Pandas comma-separated read (fast and avoids single-column space sniffing).
    If a tab delimiter is detected or parsing fails due to jagged rows, stray trailing delimiters,
    or C engine tokenization mismatches, falls back to Python engine and Python's built-in csv reader
    with whitespace and trailing column normalization so no valid product rows are dropped.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Input catalog CSV not found: {path}")

    # 1. Standard comma-separated read first (prevents sniffing space on single-column files)
    try:
        df = pd.read_csv(path)
        if len(df.columns) == 1 and "\t" in str(df.columns[0]):
            return _clean_catalog_frame(pd.read_csv(path, sep="\t"))
        return _clean_catalog_frame(df)
    except Exception:
        pass

    # 2. Delimiter auto-detection via Python engine (e.g. tabs or custom separators)
    try:
        df = pd.read_csv(path, sep=None, engine="python")
        if not (len(df.columns) == 1 and "\t" in str(df.columns[0])):
            return _clean_catalog_frame(df)
    except Exception:
        pass

    # 3. Resilient fallback for jagged CSVs with trailing commas / empty fields
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(path, encoding=encoding, errors="replace") as f:
                sample = f.read(4096)
                delimiter = "\t" if "\t" in sample and "," not in sample else ","
                f.seek(0)
                reader = csv.reader(f, delimiter=delimiter)
                raw_rows = [r for r in reader if any(cell.strip() for cell in r)]

            if not raw_rows:
                return pd.DataFrame()

            headers = [c.strip() for c in raw_rows[0]]
            expected_cols = len(headers)
            cleaned_rows = []
            for r in raw_rows[1:]:
                if len(r) > expected_cols and all(not c.strip() for c in r[expected_cols:]):
                    cleaned_rows.append(r[:expected_cols])
                elif len(r) < expected_cols:
                    cleaned_rows.append(r + [""] * (expected_cols - len(r)))
                else:
                    cleaned_rows.append(r[:expected_cols])

            return _clean_catalog_frame(pd.DataFrame(cleaned_rows, columns=headers))
        except Exception:
            continue

    return _clean_catalog_frame(pd.read_csv(path, on_bad_lines="skip"))


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
    df = read_catalog_csv(path)

    # Clean, strip whitespace, and normalize common column header aliases (e.g. Title -> Name) without collision
    df.columns = normalize_catalog_columns(list(df.columns))

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
