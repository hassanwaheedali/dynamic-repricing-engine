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
