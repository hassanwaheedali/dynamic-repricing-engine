"""Timestamped Output Manager for Repriced Catalogs.

Handles saving repriced DataFrames to structured directories with
timestamps and maintaining an always-current latest copy.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pricing_engine.models import WINNING_5PCT_GOALS

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
    "My 5% Commission",
    "Min Profit Target (5% + 500)",
    "Alfa Active Sellers",
    "Digi Active Sellers",
    "Alfa Company Profit",
    "Digi Company Profit",
]


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert value to float handling commas and NaNs."""
    if val is None or pd.isna(val):
        return default
    try:
        clean = str(val).replace(",", "").strip()
        return float(clean)
    except (ValueError, TypeError):
        return default


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
    timestamped_xlsx_path: Path | None = None
    latest_xlsx_path: Path | None = None


def export_excel_workbook(
    df: pd.DataFrame, file_path: Path, personal_comm_pct: float = 5.0
) -> None:
    """Export DataFrame to a styled Excel workbook with live dynamic formulas.

    Dynamically binds Excel formulas for:
      - Shipping Estimate: =ROUNDUP(((Length*Width*Height)/5000)*70, 0)
      - Total Without Profit: =ROUND((Net Price + Shipping) / (1 - Effective Comm), 0)
      - Calculation: =ROUND((Net Price + Shipping + Profit) / 0.90, 0)
      - Alfa Real Profit: =IF(ISBLANK(Final Price Alfa), "", ROUND((Final Price Alfa * 0.90) - (Net Price + Shipping), 0))
      - Digi Real Profit: =IF(ISBLANK(Final Price Digi), "", ROUND((Final Price Digi * (1 - Effective Comm)) - (Net Price + Shipping), 0))
    """
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Repriced Catalog"

    # Filter out any stray Unnamed or empty column headers
    df = df.loc[:, ~df.columns.astype(str).str.lower().str.startswith("unnamed:")]
    df = df.loc[:, df.columns.astype(str).str.strip() != ""]

    headers = list(df.columns)
    ws.append(headers)

    col_map = {name: get_column_letter(idx + 1) for idx, name in enumerate(headers)}

    # Header styling: Dark navy with bold white text
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=False)
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    ws.row_dimensions[1].height = 28
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    currency_format = "#,##0"
    price_cols_set = {
        "Net Price",
        "Profit",
        "Shipping Estimate",
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
        "My 5% Commission",
        "Min Profit Target (5% + 500)",
        "Alfa Active Sellers",
        "Digi Active Sellers",
        "Alfa Company Profit",
        "Digi Company Profit",
    }

    # Populate data rows
    for row_idx, (_, row) in enumerate(df.iterrows(), start=2):
        ws.row_dimensions[row_idx].height = 20
        row_vals: list[Any] = []
        for col_name in headers:
            val = row[col_name]
            if pd.isna(val):
                row_vals.append(None)
            elif col_name in price_cols_set:
                try:
                    clean = str(val).replace(",", "").strip()
                    row_vals.append(float(clean) if clean else None)
                except (ValueError, TypeError):
                    row_vals.append(val)
            elif col_name == "S.NO":
                row_vals.append(format_export_sno(val))
            else:
                row_vals.append(val)

        ws.append(row_vals)

        # Inject dynamic formulas for row_idx
        r = row_idx
        net = col_map.get("Net Price")
        l_col = col_map.get("Length")
        w_col = col_map.get("Width")
        h_col = col_map.get("Height")
        p_col = col_map.get("Profit")
        ship = col_map.get("Shipping Estimate")
        comm = col_map.get("Digi Effective Commision")
        twop = col_map.get("Total Without Profit")
        calc = col_map.get("Calculation")
        final_alfa = col_map.get("Final Price Alfa")
        final_digi = col_map.get("Final Price Digi")
        prof_alfa = col_map.get("Alfa Real Profit")
        prof_digi = col_map.get("Digi Real Profit")

        # 1. Shipping Estimate
        if ship and l_col and w_col and h_col:
            l_val = _safe_float(row.get("Length"), 0.0)
            w_val = _safe_float(row.get("Width"), 0.0)
            h_val = _safe_float(row.get("Height"), 0.0)
            if l_val > 0 and w_val > 0 and h_val > 0:
                ws[f"{ship}{r}"] = f"=ROUNDUP((({l_col}{r}*{w_col}{r}*{h_col}{r})/5000)*70, 0)"

        # 2. Total Without Profit
        if twop and net and ship:
            if comm:
                ws[f"{twop}{r}"] = (
                    f'=ROUND(({net}{r}+{ship}{r})/IF(ISNUMBER({comm}{r}), 1-{comm}{r}, '
                    f'IF(ISNUMBER(FIND("8", {comm}{r})), 0.92, 0.90)), 0)'
                )
            else:
                ws[f"{twop}{r}"] = f"=ROUND(({net}{r}+{ship}{r})/0.90, 0)"

        # 3. Calculation (Baseline Target)
        if calc and net and ship:
            if p_col:
                ws[f"{calc}{r}"] = f"=ROUND(({net}{r}+{ship}{r}+IF(ISBLANK({p_col}{r}), 500, {p_col}{r}))/0.90, 0)"
            else:
                ws[f"{calc}{r}"] = f"=ROUND(({net}{r}+{ship}{r}+500)/0.90, 0)"

        # 4. Alfa Real Profit
        if prof_alfa and final_alfa and net and ship:
            ws[f"{prof_alfa}{r}"] = (
                f'=IF(ISBLANK({final_alfa}{r}), "", ROUND(({final_alfa}{r}*0.90)-({net}{r}+{ship}{r}), 0))'
            )

        # 7. Digi Real Profit
        if prof_digi and final_digi and net and ship:
            if comm:
                ws[f"{prof_digi}{r}"] = (
                    f'=IF(ISBLANK({final_digi}{r}), "", ROUND(({final_digi}{r}*'
                    f'IF(ISNUMBER({comm}{r}), 1-{comm}{r}, IF(ISNUMBER(FIND("8", {comm}{r})), 0.92, 0.90)))'
                    f'-({net}{r}+{ship}{r}), 0))'
                )
            else:
                ws[f"{prof_digi}{r}"] = (
                    f'=IF(ISBLANK({final_digi}{r}), "", ROUND(({final_digi}{r}*0.90)-({net}{r}+{ship}{r}), 0))'
                )

        # 8. Personal 5% Commission & Company Profit Breakdown
        my_comm_col = col_map.get("My 5% Commission")
        min_target_col = col_map.get("Min Profit Target (5% + 500)")
        co_alfa_col = col_map.get("Alfa Company Profit")
        co_digi_col = col_map.get("Digi Company Profit")

        if my_comm_col:
            comm_mult = (personal_comm_pct / 100.0) if personal_comm_pct > 0 else 0.05
            if prof_alfa and prof_digi:
                ws[f"{my_comm_col}{r}"] = f'=ROUND(MAX(0, MAX({prof_alfa}{r}, {prof_digi}{r}))*{comm_mult:g}, 0)'
            elif prof_alfa:
                ws[f"{my_comm_col}{r}"] = f'=ROUND(MAX(0, {prof_alfa}{r})*{comm_mult:g}, 0)'
            elif prof_digi:
                ws[f"{my_comm_col}{r}"] = f'=ROUND(MAX(0, {prof_digi}{r})*{comm_mult:g}, 0)'
            else:
                ws[f"{my_comm_col}{r}"] = f'=ROUND(0*{comm_mult:g}, 0)'
        if min_target_col:
            comm_mult = (personal_comm_pct / 100.0) if personal_comm_pct > 0 else 0.05
            ws[f"{min_target_col}{r}"] = f"=ROUND(500/(1-{comm_mult:g}), 0)"
        if co_alfa_col and prof_alfa:
            comm_mult = (personal_comm_pct / 100.0) if personal_comm_pct > 0 else 0.05
            ws[f"{co_alfa_col}{r}"] = f'=IF(ISBLANK({prof_alfa}{r}), "", {prof_alfa}{r}-ROUND(MAX(0, {prof_alfa}{r})*{comm_mult:g}, 0))'
        if co_digi_col and prof_digi:
            comm_mult = (personal_comm_pct / 100.0) if personal_comm_pct > 0 else 0.05
            ws[f"{co_digi_col}{r}"] = f'=IF(ISBLANK({prof_digi}{r}), "", {prof_digi}{r}-ROUND(MAX(0, {prof_digi}{r})*{comm_mult:g}, 0))'

        # Apply cell formats & borders
        for c_idx, col_name in enumerate(headers, start=1):
            cell = ws.cell(row=r, column=c_idx)
            cell.border = thin_border
            if col_name in price_cols_set:
                cell.number_format = currency_format
                cell.alignment = Alignment(horizontal="right")
            elif col_name in {
                "Commision",
                "Digi Effective Commision",
                "S.NO",
                "Alfa Status",
                "Digi Status",
                "Alfa 5% Goal",
                "Digi 5% Goal",
            }:
                cell.alignment = Alignment(horizontal="center")

    # Freeze top row
    ws.freeze_panes = "A2"

    # Auto-fit column widths
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val_str = str(cell.value or "")
            if val_str.startswith("="):
                val_str = "123,456"
            max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 40)

    wb.save(file_path)


def render_export_panel(manifest: ExportManifest) -> None:
    """Render a clean Rich finish panel with output file paths."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column(style="green")

    table.add_row("Portal Upload CSV:", str(manifest.latest_path))
    if manifest.latest_xlsx_path:
        table.add_row("Dynamic Excel (.xlsx):", str(manifest.latest_xlsx_path))
    table.add_row("Timestamped Audit CSV:", str(manifest.timestamped_path))
    if manifest.timestamped_xlsx_path:
        table.add_row("Timestamped Audit Excel:", str(manifest.timestamped_xlsx_path))
    table.add_row("Rows Exported:", str(manifest.total_rows))
    table.add_row("Generated At:", manifest.timestamp)

    panel = Panel(
        table,
        title="[bold green]💾 Catalog Repricing Exported (CSV + Dynamic Excel)[/bold green]",
        border_style="green",
        expand=False,
    )
    console.print(panel)


def sanitize_catalog_stem(filename: str | Path) -> str:
    """Extract clean, safe filename stem removing repricing suffixes and path traversal characters."""
    raw_stem = Path(filename).stem.strip()
    clean_stem = raw_stem
    if clean_stem.endswith("_repriced_latest"):
        clean_stem = clean_stem[: -len("_repriced_latest")]
    elif clean_stem.endswith("_repriced"):
        clean_stem = clean_stem[: -len("_repriced")]

    sanitized = re.sub(r"[^\w\-. ]", "_", clean_stem).strip(". ")
    if not sanitized:
        raise ValueError(f"Invalid catalog stem: '{raw_stem}' derived from '{filename}'")
    return sanitized


def resolve_option_output_dir(
    input_path: str | Path,
    option: int | str = 1,
    base_dir: str | Path = "data/outputs",
) -> Path:
    """Derive structured output directory grouped by input stem and option subfolder.

    Directory structure:
        {base_dir}/{stem}/option_{1|2|3}/

    Args:
        input_path: Path to the input catalog file.
        option: 1 (Full Repricing), 2 (Market Range), or 3 (5% Personal Commission / Winners).
        base_dir: Base outputs directory (default: 'data/outputs').

    Returns:
        Path to the ensured option subfolder in the separate output directory.
    """
    stem = sanitize_catalog_stem(input_path)

    opt_key = str(option).lower().strip()
    if opt_key in ("1", "reprice", "repricing", "full", "option_1"):
        subfolder = "option_1"
    elif opt_key in ("2", "range", "market_range", "option_2"):
        subfolder = "option_2"
    elif opt_key in ("3", "5pct", "comm", "commission", "reprice_5pct", "option_3"):
        subfolder = "option_3"
    else:
        raise ValueError(
            f"Unsupported pricing option: '{option}'. Expected 1 (Reprice), 2 (Range), or 3 (5% Commission)."
        )

    resolved_base = Path(base_dir).resolve()
    resolved_target = (resolved_base / stem / subfolder).resolve()
    if not resolved_target.is_relative_to(resolved_base):
        raise ValueError(f"Path traversal detected: '{input_path}' escapes '{base_dir}'")

    target_dir = Path(base_dir) / stem / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def filter_alfa_only_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Filter DataFrame to exclude digi-key columns when Alfa-only export is requested.

    Preserves input columns, general cost/shipping columns, and Alfa columns,
    while excluding any column containing 'digi' (case-insensitive).
    """
    retained_cols = [col for col in df.columns if "digi" not in col.lower()]
    return df[retained_cols]


def export_results(
    df: pd.DataFrame,
    source_filename: str | Path,
    output_dir: str | Path | None = None,
    timestamp: datetime | None = None,
    render_panel: bool = True,
    personal_comm_pct: float = 5.0,
    platform: str = "all",
) -> ExportManifest:
    """Format and export results DataFrame to timestamped and latest CSV and XLSX files.

    Files are separated into `csv/` and `xlsx/` subfolders within output_dir.

    Args:
        df: Processed DataFrame containing repricing results.
        source_filename: Source catalog name/path used to derive output stem.
        output_dir: Target directory where outputs should be saved (default: derived via resolve_option_output_dir).
        timestamp: Optional explicit datetime (defaults to datetime.now()).
        render_panel: If True, prints Rich finish panel.
        personal_comm_pct: Personal commission percentage for formula calculations.

    Returns:
        ExportManifest with paths to generated files.
    """
    if output_dir is None:
        out_dir = resolve_option_output_dir(source_filename, option=1)
    else:
        out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_dir = out_dir / "csv"
    xlsx_dir = out_dir / "xlsx"
    csv_dir.mkdir(parents=True, exist_ok=True)
    xlsx_dir.mkdir(parents=True, exist_ok=True)

    dt = timestamp or datetime.now()
    ts_str = dt.strftime("%Y%m%d_%H%M%S")
    stem = sanitize_catalog_stem(source_filename)

    timestamped_csv_filename = f"{stem}_repriced_{ts_str}.csv"
    latest_csv_filename = f"{stem}_repriced_latest.csv"

    timestamped_xlsx_filename = f"{stem}_repriced_{ts_str}.xlsx"
    latest_xlsx_filename = f"{stem}_repriced_latest.xlsx"

    timestamped_csv_path = csv_dir / timestamped_csv_filename
    latest_csv_path = csv_dir / latest_csv_filename

    timestamped_xlsx_path = xlsx_dir / timestamped_xlsx_filename
    latest_xlsx_path = xlsx_dir / latest_xlsx_filename

    export_df = df.copy()
    unnamed_cols = [
        c for c in export_df.columns if str(c).lower().startswith("unnamed:") or not str(c).strip()
    ]
    if unnamed_cols:
        export_df = export_df.drop(columns=unnamed_cols)
    if platform.lower().strip() == "alfa":
        export_df = filter_alfa_only_columns(export_df)
    if "S.NO" in export_df.columns:
        export_df["S.NO"] = export_df["S.NO"].apply(format_export_sno)

    # 1. Export Excel workbook with dynamic formulas first (from full precision numbers)
    try:
        export_excel_workbook(export_df, timestamped_xlsx_path, personal_comm_pct=personal_comm_pct)
        try:
            shutil.copyfile(timestamped_xlsx_path, latest_xlsx_path)
        except OSError as exc:
            console.print(
                f"[bold yellow]⚠️  {latest_xlsx_filename} is open in Excel and cannot be overwritten ({exc}). Timestamped copy saved: {timestamped_xlsx_filename}[/]"
            )
            latest_xlsx_path = None  # type: ignore[assignment]
    except Exception as exc:
        console.print(f"[bold yellow]⚠️  Excel export warning:[/] {exc}")
        timestamped_xlsx_path = None  # type: ignore[assignment]
        latest_xlsx_path = None  # type: ignore[assignment]

    # 2. Format pure integer strings for portal upload CSV (eliminating float drift .0)
    for col in PRICE_INT_COLUMNS:
        if col in export_df.columns:
            export_df[col] = export_df[col].apply(format_export_price)

    export_df.to_csv(timestamped_csv_path, index=False)
    shutil.copyfile(timestamped_csv_path, latest_csv_path)

    manifest = ExportManifest(
        timestamped_path=timestamped_csv_path,
        latest_path=latest_csv_path,
        timestamp=ts_str,
        total_rows=len(export_df),
        timestamped_xlsx_path=timestamped_xlsx_path,
        latest_xlsx_path=latest_xlsx_path,
    )

    if render_panel:
        render_export_panel(manifest)

    return manifest


def export_winning_5pct_results(
    df: pd.DataFrame,
    source_filename: str | Path,
    output_dir: str | Path | None = None,
    timestamp: datetime | None = None,
    personal_comm_pct: float = 5.0,
    platform: str = "all",
) -> tuple[Path | None, Path | None, int]:
    """Filter and export only high-demand Winning + Full 5% Commission products to CSV and Excel.

    Winning Condition:
    - Product has active competitors in the market (proven demand)
    - Our Final Price strictly beats the lowest market competitor (WIN / CAPPED win)
    - Real Profit covers BOTH 5% Personal Commission on Net Price AND Rs. 500 Company Profit
      (i.e. 'Alfa 5% Goal' == 'WIN + 5% ACHIEVED' or 'Digi 5% Goal' == 'WIN + 5% ACHIEVED')

    Rows are sorted by total active sellers (highest market demand first) and 5% commission descending.
    """
    if "Alfa 5% Goal" not in df.columns and "Digi 5% Goal" not in df.columns:
        return None, None, 0

    win_goals = WINNING_5PCT_GOALS
    alfa_win = (
        df["Alfa 5% Goal"].isin(win_goals)
        if "Alfa 5% Goal" in df.columns
        else pd.Series(False, index=df.index)
    )
    digi_win = (
        df["Digi 5% Goal"].isin(win_goals)
        if "Digi 5% Goal" in df.columns
        else pd.Series(False, index=df.index)
    )
    win_mask = alfa_win | digi_win
    winners_df = df[win_mask].copy()

    if winners_df.empty:
        return None, None, 0

    # Sort winning products strictly by Input Order / Serial Number (S# 1, 2, 5, 6, 7... ascending)
    if "S.NO" in winners_df.columns:
        sno_numeric = pd.to_numeric(
            winners_df["S.NO"].astype(str).str.replace(",", "").str.strip(),
            errors="coerce",
        )
        if sno_numeric.notna().all():
            winners_df = (
                winners_df.assign(_sno_numeric_sort=sno_numeric)
                .sort_values(by="_sno_numeric_sort", ascending=True, kind="stable")
                .drop(columns=["_sno_numeric_sort"])
            )
        else:
            winners_df = winners_df.sort_index(kind="stable")
    else:
        winners_df = winners_df.sort_index(kind="stable")

    if output_dir is None:
        out_dir = resolve_option_output_dir(source_filename, option=3)
    else:
        out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_dir = out_dir / "csv"
    xlsx_dir = out_dir / "xlsx"
    csv_dir.mkdir(parents=True, exist_ok=True)
    xlsx_dir.mkdir(parents=True, exist_ok=True)

    dt = timestamp or datetime.now()
    ts_str = dt.strftime("%Y%m%d_%H%M%S")
    stem = sanitize_catalog_stem(source_filename)

    ts_csv = csv_dir / f"{stem}_winning_5pct_{ts_str}.csv"
    latest_csv = csv_dir / f"{stem}_winning_5pct_latest.csv"
    ts_xlsx = xlsx_dir / f"{stem}_winning_5pct_{ts_str}.xlsx"
    latest_xlsx = xlsx_dir / f"{stem}_winning_5pct_latest.xlsx"

    export_df = winners_df.copy()
    unnamed_cols = [
        c for c in export_df.columns if str(c).lower().startswith("unnamed:") or not str(c).strip()
    ]
    if unnamed_cols:
        export_df = export_df.drop(columns=unnamed_cols)
    if platform.lower().strip() == "alfa":
        export_df = filter_alfa_only_columns(export_df)
    if "S.NO" in export_df.columns:
        export_df["S.NO"] = export_df["S.NO"].apply(format_export_sno)

    saved_xlsx: Path | None = latest_xlsx
    try:
        export_excel_workbook(export_df, ts_xlsx, personal_comm_pct=personal_comm_pct)
        try:
            shutil.copyfile(ts_xlsx, latest_xlsx)
        except OSError as exc:
            console.print(
                f"[bold yellow]⚠️  {latest_xlsx.name} is open in Excel and cannot be overwritten ({exc}). Timestamped copy saved: {ts_xlsx.name}[/]"
            )
            saved_xlsx = ts_xlsx
    except Exception:
        saved_xlsx = None

    for col in PRICE_INT_COLUMNS:
        if col in export_df.columns:
            export_df[col] = export_df[col].apply(format_export_price)

    export_df.to_csv(ts_csv, index=False)
    shutil.copyfile(ts_csv, latest_csv)

    return latest_csv, saved_xlsx, len(export_df)


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

    # Filter out any stray Unnamed or empty column headers
    df = df.loc[:, ~df.columns.astype(str).str.lower().str.startswith("unnamed:")]
    df = df.loc[:, df.columns.astype(str).str.strip() != ""]

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
    output_dir: str | Path | None = None,
    timestamp: datetime | None = None,
    render_panel: bool = True,
    platform: str = "all",
) -> RangeExportManifest:
    """Export Market Range results to ``csv/`` and ``xlsx/`` (timestamped + latest each).

    CSV uses pure-integer strings (no ``.0`` drift). XLSX uses real numeric cells.
    XLSX problems (openpyxl missing, file locked by Excel) never abort the run: the CSV
    is always written first and issues are reported in ``manifest.warnings``.
    """
    if output_dir is None:
        root = resolve_option_output_dir(source_filename, option=2)
    else:
        root = Path(output_dir)
    csv_dir, xlsx_dir = root / "csv", root / "xlsx"
    csv_dir.mkdir(parents=True, exist_ok=True)
    xlsx_dir.mkdir(parents=True, exist_ok=True)

    ts_str = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    stem = sanitize_catalog_stem(source_filename)

    working_df = df.copy()
    unnamed_cols = [
        c for c in working_df.columns if str(c).lower().startswith("unnamed:") or not str(c).strip()
    ]
    if unnamed_cols:
        working_df = working_df.drop(columns=unnamed_cols)
    if platform.lower().strip() == "alfa":
        working_df = filter_alfa_only_columns(working_df)

    csv_path = csv_dir / f"{stem}_range_{ts_str}.csv"
    csv_latest = csv_dir / f"{stem}_range_latest.csv"
    csv_df = working_df.copy()
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
    xl_df = _range_xlsx_frame(working_df)
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
        total_rows=len(working_df),
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
