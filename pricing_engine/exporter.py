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
    timestamped_xlsx_path: Path | None = None
    latest_xlsx_path: Path | None = None


def export_excel_workbook(df: pd.DataFrame, file_path: Path) -> None:
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
    }

    # Populate data rows
    for row_idx, (_, row) in enumerate(df.iterrows(), start=2):
        ws.row_dimensions[row_idx].height = 20
        row_vals = []
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

        # Apply cell formats & borders
        for c_idx, col_name in enumerate(headers, start=1):
            cell = ws.cell(row=r, column=c_idx)
            cell.border = thin_border
            if col_name in price_cols_set:
                cell.number_format = currency_format
                cell.alignment = Alignment(horizontal="right")
            elif col_name in {"Commision", "Digi Effective Commision", "S.NO", "Alfa Status", "Digi Status"}:
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


def export_results(
    df: pd.DataFrame,
    source_filename: str | Path,
    output_dir: str | Path = "data/outputs",
    timestamp: datetime | None = None,
    render_panel: bool = True,
) -> ExportManifest:
    """Format and export results DataFrame to timestamped and latest CSV and XLSX files.

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

    timestamped_csv_filename = f"{stem}_repriced_{ts_str}.csv"
    latest_csv_filename = f"{stem}_repriced_latest.csv"

    timestamped_xlsx_filename = f"{stem}_repriced_{ts_str}.xlsx"
    latest_xlsx_filename = f"{stem}_repriced_latest.xlsx"

    timestamped_csv_path = out_dir / timestamped_csv_filename
    latest_csv_path = out_dir / latest_csv_filename

    timestamped_xlsx_path = out_dir / timestamped_xlsx_filename
    latest_xlsx_path = out_dir / latest_xlsx_filename

    export_df = df.copy()
    if "S.NO" in export_df.columns:
        export_df["S.NO"] = export_df["S.NO"].apply(format_export_sno)

    # 1. Export Excel workbook with dynamic formulas first (from full precision numbers)
    try:
        export_excel_workbook(export_df, timestamped_xlsx_path)
        shutil.copyfile(timestamped_xlsx_path, latest_xlsx_path)
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
