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

import config
from pricing_engine.models import (
    WINNING_5PCT_GOALS,
    format_comm_pct_label,
    get_winning_comm_goals,
    has_compatibility_or_fallback_notice,
)

console = Console()

PRICE_INT_COLUMNS: list[str] = [
    "Total Without Profit (Alfa)",
    "Total Without Profit (Digi)",
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


def format_export_shipping(val: Any) -> str:
    """Format Shipping Estimate without .0 integer float drift while preserving exact fractional paisas."""
    if val is None or pd.isna(val):
        return ""
    try:
        clean = str(val).replace(",", "").strip()
        if not clean or clean.lower() in ("nan", "none"):
            return ""
        f = round(float(clean), 2)
        if f.is_integer():
            return str(int(f))
        return f"{f:.2f}".rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return ""


_DYNAMIC_COMM_COL_RE = re.compile(r"^My [\d.]+% Commission$")
_DYNAMIC_MIN_TARGET_COL_RE = re.compile(r"^Min Profit Target \([\d.]+% \+ \d+\)$")
_DYNAMIC_ALFA_GOAL_COL_RE = re.compile(r"^Alfa [\d.]+% Goal$")
_DYNAMIC_DIGI_GOAL_COL_RE = re.compile(r"^Digi [\d.]+% Goal$")


def is_price_int_column(col_name: Any) -> bool:
    """Return True if column holds an integer PKR price, seller count, or commission target."""
    s = str(col_name).strip()
    return (
        s in PRICE_INT_COLUMNS
        or bool(_DYNAMIC_COMM_COL_RE.match(s))
        or bool(_DYNAMIC_MIN_TARGET_COL_RE.match(s))
    )


def _excel_payout_expr(cell_ref: str, default_payout: float) -> str:
    """Generate Excel formula expression computing (1 - commission) dynamically.

    Handles numeric percentage cells (e.g. 0.08 or 0.10), fractional values (e.g. 0.075),
    percentage text strings (e.g. '7.50%'), and blank cells without precision truncation.
    """
    default_payout_str = f"{round(default_payout, 6):g}"
    return (
        f'IF(OR(ISBLANK({cell_ref}), {cell_ref}=""), {default_payout_str}, '
        f"IF(ISNUMBER({cell_ref}), 1-{cell_ref}, "
        f'1-SUBSTITUTE({cell_ref}, "%", "")/100))'
    )


def _excel_comm_expr(cell_ref: str, default_comm: float) -> str:
    """Generate Excel formula expression extracting commission decimal dynamically from cell."""
    default_comm_str = f"{round(default_comm, 6):g}"
    return (
        f'IF(OR(ISBLANK({cell_ref}), {cell_ref}=""), {default_comm_str}, '
        f"IF(ISNUMBER({cell_ref}), {cell_ref}, "
        f'SUBSTITUTE({cell_ref}, "%", "")/100))'
    )


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
      - Shipping Estimate: =ROUNDUP(((Length*Width*Height)/5000)*70, 2)
      - Total Without Profit (Alfa): =ROUND((Net Price + Shipping)[*(1+Ins)] / (1 - Alfa Commission), 0)
      - Total Without Profit (Digi): =ROUND((Net Price + Shipping)[*(1+Ins)] / (1 - Digi Commission), 0)
      - Alfa Real Profit: =IF(ISBLANK(Final Price Alfa), "", ROUND((Final Price Alfa * (1 - Alfa Comm)) - (Net Price + Shipping)[*(1+Ins)], 0))
      - Digi Real Profit: =IF(ISBLANK(Final Price Digi), "", ROUND((Final Price Digi * (1 - Digi Comm)) - (Net Price + Shipping)[*(1+Ins)], 0))
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
    notice_fill = PatternFill(start_color="FFF9C4", end_color="FFF9C4", fill_type="solid")
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
    price_cols_set = set(PRICE_INT_COLUMNS) | {"Net Price", "Profit", "Shipping Estimate"}

    # Hoist row-invariant column mappings and validated configuration outside the row loop
    net = col_map.get("Net Price")
    l_col = col_map.get("Length")
    w_col = col_map.get("Width")
    h_col = col_map.get("Height")
    ship = col_map.get("Shipping Estimate")
    alfa_comm_col = col_map.get("Alfa Commission")
    digi_comm_col = col_map.get("Digi Commission")
    twop_alfa = col_map.get("Total Without Profit (Alfa)")
    twop_digi = col_map.get("Total Without Profit (Digi)")
    final_alfa = col_map.get("Final Price Alfa")
    final_digi = col_map.get("Final Price Digi")
    prof_alfa = col_map.get("Alfa Real Profit")
    prof_digi = col_map.get("Digi Real Profit")
    ins_col = col_map.get("Insurance")

    vol_divisor = (
        int(config.VOLUMETRIC_DIVISOR)
        if config.VOLUMETRIC_DIVISOR.is_integer()
        else config.VOLUMETRIC_DIVISOR
    )
    courier_rate = (
        int(config.COURIER_RATE_PER_KG)
        if config.COURIER_RATE_PER_KG.is_integer()
        else config.COURIER_RATE_PER_KG
    )
    # Resolve only active platform payout rates cleanly to preserve vendor isolation
    alfa_payout = (
        config.get_alfa_payout_rate()
        if (twop_alfa or prof_alfa or alfa_comm_col)
        else None
    )
    digi_payout = (
        config.get_digi_payout_rate()
        if (twop_digi or prof_digi or digi_comm_col)
        else None
    )
    min_profit_val = (
        int(config.COMPANY_MIN_PROFIT_PKR)
        if config.COMPANY_MIN_PROFIT_PKR.is_integer()
        else config.COMPANY_MIN_PROFIT_PKR
    )
    lbl = format_comm_pct_label(personal_comm_pct)
    my_comm_col = col_map.get(f"My {lbl}% Commission") or next(
        (col_map[h] for h in headers if _DYNAMIC_COMM_COL_RE.match(str(h))), None
    )
    min_target_col = col_map.get(f"Min Profit Target ({lbl}% + {min_profit_val})") or next(
        (col_map[h] for h in headers if _DYNAMIC_MIN_TARGET_COL_RE.match(str(h))), None
    )
    co_alfa_col = col_map.get("Alfa Company Profit")
    co_digi_col = col_map.get("Digi Company Profit")
    comm_mult = (
        (personal_comm_pct / 100.0)
        if personal_comm_pct > 0
        else (config.DEFAULT_PERSONAL_COMM_PCT / 100.0)
    )
    vendor_specs = (
        (twop_alfa, prof_alfa, final_alfa, alfa_comm_col, alfa_payout),
        (twop_digi, prof_digi, final_digi, digi_comm_col, digi_payout),
    )

    # Populate data rows
    for row_idx, (_, row) in enumerate(df.iterrows(), start=2):
        ws.row_dimensions[row_idx].height = 20
        row_vals: list[Any] = []
        for col_name in headers:
            val = row[col_name]
            if pd.isna(val):
                row_vals.append(None)
            elif col_name in price_cols_set or is_price_int_column(col_name):
                try:
                    clean = str(val).replace(",", "").strip()
                    row_vals.append(float(clean) if clean else None)
                except (ValueError, TypeError):
                    row_vals.append(val)
            elif col_name == "S.NO":
                row_vals.append(format_export_sno(val))
            elif col_name in ("Alfa Commission", "Digi Commission", "Insurance"):
                try:
                    clean = str(val).replace("%", "").strip()
                    row_vals.append(round(float(clean) / 100.0, 6) if clean else None)
                except (ValueError, TypeError):
                    row_vals.append(val)
            else:
                row_vals.append(val)

        ws.append(row_vals)

        r = row_idx
        # Insurance % is added on cost: (Net + Shipping) x (1 + ins), BEFORE commission/profit
        ins_factor = f"(1+{_excel_comm_expr(f'{ins_col}{r}', 0.0)})" if ins_col else ""
        ins_mul = f"*{ins_factor}" if ins_col else ""

        # 1. Shipping Estimate
        if ship and l_col and w_col and h_col:
            l_val = _safe_float(row.get("Length"), 0.0)
            w_val = _safe_float(row.get("Width"), 0.0)
            h_val = _safe_float(row.get("Height"), 0.0)
            if l_val > 0 and w_val > 0 and h_val > 0:
                ws[f"{ship}{r}"] = (
                    f"=ROUNDUP((({l_col}{r}*{w_col}{r}*{h_col}{r})/{vol_divisor})*{courier_rate}, 2)"
                )

        # 2-5. Per-vendor Total Without Profit & Real Profit formulas
        for twop_col, prof_col, final_col, comm_col, payout in vendor_specs:
            if payout is None:
                continue
            payout_expr = (
                _excel_payout_expr(f"{comm_col}{r}", payout)
                if comm_col
                else f"{round(payout, 6):g}"
            )
            if twop_col and net and ship:
                ws[f"{twop_col}{r}"] = (
                    f"=ROUND(({net}{r}+{ship}{r}){ins_mul}/{payout_expr}, 0)"
                )
            if prof_col and final_col and net and ship:
                ws[f"{prof_col}{r}"] = (
                    f'=IF(ISBLANK({final_col}{r}), "", ROUND(({final_col}{r}*{payout_expr})-(({net}{r}+{ship}{r}){ins_mul}), 0))'
                )

        # 6. Personal Commission & Company Profit Breakdown
        if my_comm_col:
            if prof_alfa and prof_digi:
                profit_basis = f"MAX(0, MAX({prof_alfa}{r}, {prof_digi}{r}))"
            elif prof_alfa:
                profit_basis = f"MAX(0, {prof_alfa}{r})"
            elif prof_digi:
                profit_basis = f"MAX(0, {prof_digi}{r})"
            else:
                profit_basis = "0"
            ws[f"{my_comm_col}{r}"] = f"=ROUND({profit_basis}*{comm_mult:g}, 0)"
        if min_target_col:
            ws[f"{min_target_col}{r}"] = f"=ROUNDUP({min_profit_val}/(1-{comm_mult:g}), 0)"
        if co_alfa_col and prof_alfa:
            ws[f"{co_alfa_col}{r}"] = (
                f'=IF(ISBLANK({prof_alfa}{r}), "", {prof_alfa}{r}-ROUND(MAX(0, {prof_alfa}{r})*{comm_mult:g}, 0))'
            )
        if co_digi_col and prof_digi:
            ws[f"{co_digi_col}{r}"] = (
                f'=IF(ISBLANK({prof_digi}{r}), "", {prof_digi}{r}-ROUND(MAX(0, {prof_digi}{r})*{comm_mult:g}, 0))'
            )

        # Apply cell formats, borders & soft yellow fill for compatibility/fallback notices
        row_has_notice = has_compatibility_or_fallback_notice(
            row.get("Alfa Reason")
        ) or has_compatibility_or_fallback_notice(row.get("Digi Reason"))
        for c_idx, col_name in enumerate(headers, start=1):
            cell = ws.cell(row=r, column=c_idx)
            cell.border = thin_border
            if row_has_notice:
                cell.fill = notice_fill
            if col_name in price_cols_set or is_price_int_column(col_name):
                cell.number_format = currency_format
                cell.alignment = Alignment(horizontal="right")
            elif col_name in ("Alfa Commission", "Digi Commission", "Insurance"):
                cell.number_format = "0.00%"
                cell.alignment = Alignment(horizontal="center")
            elif (
                col_name in {"S.NO", "Alfa Status", "Digi Status"}
                or _DYNAMIC_ALFA_GOAL_COL_RE.match(str(col_name))
                or _DYNAMIC_DIGI_GOAL_COL_RE.match(str(col_name))
            ):
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
    retained_cols = [col for col in df.columns if "digi" not in str(col).lower()]
    return df[retained_cols]


def filter_digi_only_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Filter DataFrame to exclude alfa-key columns when Digi-only export is requested.

    Preserves input columns, general cost/shipping columns, and Digi columns,
    while excluding any column containing 'alfa' (case-insensitive).
    """
    retained_cols = [col for col in df.columns if "alfa" not in str(col).lower()]
    return df[retained_cols]


def normalize_export_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Strip unnamed/blank columns, anchor Insurance after commissions, and place Risk Alerts last."""
    clean_df = df.copy()
    unnamed_cols = [
        c for c in clean_df.columns if str(c).lower().startswith("unnamed:") or not str(c).strip()
    ]
    if unnamed_cols:
        clean_df = clean_df.drop(columns=unnamed_cols)
    risk_cols = [c for c in ("Alfa Risk Alert", "Digi Risk Alert") if c in clean_df.columns]
    if risk_cols:
        clean_df = clean_df[[c for c in clean_df.columns if c not in risk_cols] + risk_cols]
    if "Insurance" in clean_df.columns:
        cols_wo_ins = [c for c in clean_df.columns if c != "Insurance"]
        anchor = next(
            (c for c in ("Digi Commission", "Alfa Commission") if c in cols_wo_ins), None
        )
        if anchor is not None:
            pos = cols_wo_ins.index(anchor) + 1
            clean_df = clean_df[cols_wo_ins[:pos] + ["Insurance"] + cols_wo_ins[pos:]]
    return clean_df


def _format_csv_export_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Apply pure-integer formatting to CSV output columns without mutating caller DataFrame."""
    csv_df = df.copy()
    if "Shipping Estimate" in csv_df.columns:
        csv_df["Shipping Estimate"] = csv_df["Shipping Estimate"].apply(format_export_shipping)
    for col in csv_df.columns:
        if is_price_int_column(col):
            csv_df[col] = csv_df[col].apply(format_export_price)
    return csv_df


def _write_dedicated_platform_files(
    df: pd.DataFrame,
    csv_path: Path,
    xlsx_path: Path,
    personal_comm_pct: float,
) -> None:
    """Write a dedicated single-vendor CSV and XLSX pair safely."""
    plat_df = df.copy()
    if "S.NO" in plat_df.columns:
        plat_df["S.NO"] = plat_df["S.NO"].apply(format_export_sno)
    export_excel_workbook(plat_df, xlsx_path, personal_comm_pct=personal_comm_pct)
    _format_csv_export_frame(plat_df).to_csv(csv_path, index=False)


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
    plat_key = config.normalize_platform(platform, allow_all=True)
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

    clean_base_df = normalize_export_dataframe(df)
    export_df = clean_base_df.copy()
    if plat_key == "alfa":
        export_df = filter_alfa_only_columns(export_df)
    elif plat_key == "digi":
        export_df = filter_digi_only_columns(export_df)
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
    export_df = _format_csv_export_frame(export_df)
    export_df.to_csv(timestamped_csv_path, index=False)
    shutil.copyfile(timestamped_csv_path, latest_csv_path)

    # 3. Generate dedicated platform files independently when running unified dual mode (all)
    if plat_key == "all":
        for suffix, filter_fn in (
            ("alfa", filter_alfa_only_columns),
            ("digi", filter_digi_only_columns),
        ):
            try:
                _write_dedicated_platform_files(
                    df=filter_fn(clean_base_df),
                    csv_path=csv_dir / f"{stem}_repriced_{suffix}_latest.csv",
                    xlsx_path=xlsx_dir / f"{stem}_repriced_{suffix}_latest.xlsx",
                    personal_comm_pct=personal_comm_pct,
                )
            except Exception as exc:
                console.print(f"[bold yellow]⚠️  Dedicated {suffix} export notice:[/] {exc}")

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
    plat_key = config.normalize_platform(platform, allow_all=True)
    lbl = format_comm_pct_label(personal_comm_pct)
    alfa_goal_col = (
        f"Alfa {lbl}% Goal"
        if f"Alfa {lbl}% Goal" in df.columns
        else next((c for c in df.columns if _DYNAMIC_ALFA_GOAL_COL_RE.match(str(c))), None)
    )
    digi_goal_col = (
        f"Digi {lbl}% Goal"
        if f"Digi {lbl}% Goal" in df.columns
        else next((c for c in df.columns if _DYNAMIC_DIGI_GOAL_COL_RE.match(str(c))), None)
    )
    if alfa_goal_col is None and digi_goal_col is None:
        return None, None, 0

    win_goals = WINNING_5PCT_GOALS | get_winning_comm_goals(personal_comm_pct)
    win_goal_re = re.compile(r"^(?:WIN \+ [\d.]+% ACHIEVED|SOLO \([\d.]+% COVERED\))$")

    def _matches_win_goal(series: pd.Series) -> pd.Series:
        s_str = series.fillna("").astype(str)
        return series.isin(win_goals) | s_str.str.match(win_goal_re)

    alfa_win = (
        _matches_win_goal(df[alfa_goal_col])
        if alfa_goal_col is not None
        else pd.Series(False, index=df.index)
    )
    digi_win = (
        _matches_win_goal(df[digi_goal_col])
        if digi_goal_col is not None
        else pd.Series(False, index=df.index)
    )
    if "Digi Discovery Coverage" in df.columns:
        digi_win &= df["Digi Discovery Coverage"].fillna("").isin(["", "COMPLETE", "CAPPED"])
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

    pct_slug = lbl.replace(".", "_")
    ts_csv = csv_dir / f"{stem}_winning_{pct_slug}pct_{ts_str}.csv"
    latest_csv = csv_dir / f"{stem}_winning_{pct_slug}pct_latest.csv"
    ts_xlsx = xlsx_dir / f"{stem}_winning_{pct_slug}pct_{ts_str}.xlsx"
    latest_xlsx = xlsx_dir / f"{stem}_winning_{pct_slug}pct_latest.xlsx"

    export_df = normalize_export_dataframe(winners_df)
    if plat_key == "alfa":
        export_df = filter_alfa_only_columns(export_df)
    elif plat_key == "digi":
        export_df = filter_digi_only_columns(export_df)
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

    if "Shipping Estimate" in export_df.columns:
        export_df["Shipping Estimate"] = export_df["Shipping Estimate"].apply(
            format_export_shipping
        )
    for col in export_df.columns:
        if is_price_int_column(col):
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
    plat_key = config.normalize_platform(platform, allow_all=True)
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
    if plat_key == "alfa":
        working_df = filter_alfa_only_columns(working_df)
    elif plat_key == "digi":
        working_df = filter_digi_only_columns(working_df)

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
