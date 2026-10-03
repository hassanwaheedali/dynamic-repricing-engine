"""Timestamped Output Manager for Repriced Catalogs.

Handles saving repriced DataFrames to structured directories with
timestamps and maintaining an always-current latest copy.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

PRICE_INT_COLUMNS: list[str] = [
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
]


def format_export_price(val: Any) -> str:
    """Format integer price values for CSV export without float drift (.0) or empty on None/NaN.

    Args:
        val: Numeric, None, or NaN price value.

    Returns:
        Pure integer string (e.g. '165000') or empty string '' if None/NaN.
    """
    if val is None or pd.isna(val):
        return ""
    try:
        clean = str(val).replace(",", "").strip()
        if not clean or clean.lower() == "nan" or clean.lower() == "none":
            return ""
        return str(int(round(float(clean))))
    except (ValueError, TypeError):
        return ""


def format_export_sno(val: Any) -> str:
    """Format S.NO value without float drift (.0) while preserving string identifiers.

    Args:
        val: Numeric, string, None, or NaN serial number.

    Returns:
        Clean string representation without decimal point if integer-equivalent.
    """
    if val is None or pd.isna(val):
        return ""
    try:
        f = float(val)
        if f.is_integer():
            return str(int(f))
    except (ValueError, TypeError):
        pass
    return str(val).strip()


@dataclass(frozen=True, slots=True)
class ExportManifest:
    """Manifest describing exported catalog artifacts."""

    timestamped_path: Path
    latest_path: Path
    timestamp: str
    total_rows: int


def render_export_panel(manifest: ExportManifest) -> None:
    """Render a clean Rich finish panel with output file paths."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column(style="green")

    table.add_row("Timestamped Audit:", str(manifest.timestamped_path))
    table.add_row("Latest Upload Ready:", str(manifest.latest_path))
    table.add_row("Rows Exported:", str(manifest.total_rows))
    table.add_row("Generated At:", manifest.timestamp)

    panel = Panel(
        table,
        title="[bold green]💾 Catalog Repricing Exported[/bold green]",
        border_style="green",
        expand=False,
    )
    console.print(panel)


def export_results(
    df: pd.DataFrame,
    source_filename: str | Path,
    output_dir: str | Path = "data/outputs",
    timestamp: datetime | None = None,
    render_panel: bool = True,
) -> ExportManifest:
    """Format and export results DataFrame to timestamped and latest CSV files.

    Args:
        df: Processed DataFrame containing repricing results.
        source_filename: Source catalog name/path used to derive output stem.
        output_dir: Target directory where outputs should be saved.
        timestamp: Optional explicit datetime (defaults to datetime.now()).
        render_panel: If True, prints Rich finish panel.

    Returns:
        ExportManifest with paths to generated files.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dt = timestamp or datetime.now()
    ts_str = dt.strftime("%Y%m%d_%H%M%S")

    stem = Path(source_filename).stem
    if stem.endswith("_repriced_latest"):
        stem = stem[: -len("_repriced_latest")]
    elif stem.endswith("_repriced"):
        stem = stem[: -len("_repriced")]

    timestamped_filename = f"{stem}_repriced_{ts_str}.csv"
    latest_filename = f"{stem}_repriced_latest.csv"

    timestamped_path = out_dir / timestamped_filename
    latest_path = out_dir / latest_filename

    export_df = df.copy()
    if "S.NO" in export_df.columns:
        export_df["S.NO"] = export_df["S.NO"].apply(format_export_sno)

    for col in PRICE_INT_COLUMNS:
        if col in export_df.columns:
            export_df[col] = export_df[col].apply(format_export_price)

    export_df.to_csv(timestamped_path, index=False)
    shutil.copyfile(timestamped_path, latest_path)

    manifest = ExportManifest(
        timestamped_path=timestamped_path,
        latest_path=latest_path,
        timestamp=ts_str,
        total_rows=len(export_df),
    )

    if render_panel:
        render_export_panel(manifest)

    return manifest


RANGE_NUMERIC_COLUMNS: list[str] = [
    "Minimum Price Alfa",
    "Maximum Price Alfa",
    "Minimum Price Digi",
    "Maximum Price Digi",
    "Alfa Offers Found",
    "Digi Offers Found",
]


@dataclass(frozen=True, slots=True)
class RangeExportManifest:
    """Manifest of Market Range Mode artifacts (xlsx entries are None if not written)."""

    csv_path: Path
    csv_latest: Path
    xlsx_path: Path | None
    xlsx_latest: Path | None
    timestamp: str
    total_rows: int
    warnings: tuple[str, ...] = ()


def _range_xlsx_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Copy of df with real numeric cells for XLSX (prices, counts and numeric S.NO)."""
    xl = df.copy()
    for col in RANGE_NUMERIC_COLUMNS:
        if col in xl.columns:
            xl[col] = pd.to_numeric(xl[col].apply(format_export_price), errors="coerce").astype(
                "Int64"
            )
    if "S.NO" in xl.columns:
        sno = xl["S.NO"].apply(format_export_sno)
        numeric = pd.to_numeric(sno, errors="coerce")
        xl["S.NO"] = numeric.astype("Int64") if numeric.notna().all() else sno
    return xl


def _write_range_xlsx(df: pd.DataFrame, path: Path) -> None:
    """Write a styled XLSX (bold header, frozen header row, auto column width)."""
    from openpyxl import load_workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    df.to_excel(path, index=False, engine="openpyxl")
    wb = load_workbook(path)
    ws = wb.active
    if ws is None:
        return
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"
    for idx, col in enumerate(df.columns, start=1):
        longest = max([len(str(col))] + [len(str(v)) for v in df[col].tolist()])
        ws.column_dimensions[get_column_letter(idx)].width = min(max(longest + 2, 10), 60)
    wb.save(path)


def export_range_results(
    df: pd.DataFrame,
    source_filename: str | Path,
    output_dir: str | Path = "data/outputs/range",
    timestamp: datetime | None = None,
    render_panel: bool = True,
) -> RangeExportManifest:
    """Export Market Range results to ``csv/`` and ``xlsx/`` (timestamped + latest each).

    CSV uses pure-integer strings (no ``.0`` drift). XLSX uses real numeric cells.
    XLSX problems (openpyxl missing, file locked by Excel) never abort the run: the CSV
    is always written first and issues are reported in ``manifest.warnings``.
    """
    root = Path(output_dir)
    csv_dir, xlsx_dir = root / "csv", root / "xlsx"
    csv_dir.mkdir(parents=True, exist_ok=True)
    xlsx_dir.mkdir(parents=True, exist_ok=True)

    ts_str = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    stem = Path(source_filename).stem

    csv_path = csv_dir / f"{stem}_range_{ts_str}.csv"
    csv_latest = csv_dir / f"{stem}_range_latest.csv"
    csv_df = df.copy()
    if "S.NO" in csv_df.columns:
        csv_df["S.NO"] = csv_df["S.NO"].apply(format_export_sno)
    for col in RANGE_NUMERIC_COLUMNS:
        if col in csv_df.columns:
            csv_df[col] = csv_df[col].apply(format_export_price)
    csv_df.to_csv(csv_path, index=False)
    shutil.copyfile(csv_path, csv_latest)

    warnings: list[str] = []
    xlsx_path: Path | None = xlsx_dir / f"{stem}_range_{ts_str}.xlsx"
    xlsx_latest: Path | None = xlsx_dir / f"{stem}_range_latest.xlsx"
    xl_df = _range_xlsx_frame(df)
    assert xlsx_path is not None and xlsx_latest is not None
    try:
        _write_range_xlsx(xl_df, xlsx_path)
    except ImportError:
        warnings.append("openpyxl is not installed; XLSX skipped (pip install openpyxl).")
        xlsx_path = xlsx_latest = None
    except OSError as exc:
        warnings.append(f"Could not write XLSX {xlsx_path.name}: {exc}")
        xlsx_path = xlsx_latest = None
    else:
        try:
            _write_range_xlsx(xl_df, xlsx_latest)
        except OSError as exc:
            warnings.append(
                f"{xlsx_latest.name} not updated (is it open in Excel?): {exc}. "
                "Timestamped copy was saved."
            )
            xlsx_latest = None

    manifest = RangeExportManifest(
        csv_path=csv_path,
        csv_latest=csv_latest,
        xlsx_path=xlsx_path,
        xlsx_latest=xlsx_latest,
        timestamp=ts_str,
        total_rows=len(df),
        warnings=tuple(warnings),
    )
    if render_panel:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column(style="green")
        table.add_row("CSV:", str(csv_path))
        table.add_row("XLSX:", str(xlsx_path) if xlsx_path else "skipped")
        table.add_row("Rows Exported:", str(manifest.total_rows))
        console.print(
            Panel(table, title="[bold green]Market Range Exported[/bold green]", expand=False)
        )
    return manifest
