"""Market Range Mode: model list (Brand + Name) -> market Min/Max per platform.

Reuses the production scraper and strict variant matcher unchanged. No cost math,
no floors, no commission tiers and no final price decision: only the lowest and
highest in-stock price any vendor lists for the matched model on AlfaMall and
DigiMall, plus how many in-stock offers back those numbers.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pandas as pd
from curl_cffi.requests import AsyncSession
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pricing_engine.evaluator import evaluate_market_range
from pricing_engine.exporter import (
    RangeExportManifest,
    export_range_results,
    resolve_option_output_dir,
)
from pricing_engine.ingestion import normalize_catalog_columns
from pricing_engine.matcher import extract_search_query_and_model, generate_search_patterns
from pricing_engine.models import MarketRange, ProductInput, ScrapeResult
from pricing_engine.pipeline import parse_product_input
from pricing_engine.scraper import scrape_alfamall, scrape_digimall

console = Console(legacy_windows=False)

# Delay between launching consecutive items (WAF burst-wave protection, same as repricing).
RANGE_STAGGER_SECONDS: float = 0.4

RANGE_ALERT_NONE = "NONE"
RANGE_ALERT_NO_OFFERS = "NO_OFFERS"
RANGE_ALERT_SERVER_DOWN = "SERVER_DOWN"

SNO_ALIASES: frozenset[str] = frozenset(
    {"S.NO", "S.No", "S. No", "S.No.", "SNO", "sno", "Serial No", "Serial Number"}
)

# Columns kept in the output contract but intentionally left blank in range mode.
BLANK_COST_COLUMNS: tuple[str, ...] = (
    "Shipping Estimate",
    "Commision",
    "Digi Effective Commision",
    "Total Without Profit",
    "Calculation",
)
BLANK_DECISION_COLUMNS: tuple[str, ...] = (
    "Final Price Alfa",
    "Alfa Status",
    "Final Price Digi",
    "Digi Status",
    "Alfa Real Profit",
    "Digi Real Profit",
    "Alfa Reason",
    "Digi Reason",
)
GENERATED_COLUMNS: frozenset[str] = frozenset(
    {
        *BLANK_COST_COLUMNS,
        *BLANK_DECISION_COLUMNS,
        "Minimum Price Alfa",
        "Maximum Price Alfa",
        "Minimum Price Digi",
        "Maximum Price Digi",
        "Alfa Offers Found",
        "Digi Offers Found",
        "Alfa Risk Alert",
        "Digi Risk Alert",
    }
)


def determine_range_alert(market: MarketRange) -> str:
    """Risk alert for range mode: SERVER_DOWN, NO_OFFERS (empty market) or NONE."""
    if market.is_down:
        return RANGE_ALERT_SERVER_DOWN
    if market.offer_count == 0:
        return RANGE_ALERT_NO_OFFERS
    return RANGE_ALERT_NONE


def build_range_record(
    product: ProductInput, alfa: MarketRange, digi: MarketRange
) -> dict[str, Any]:
    """Build one output row following the standard column contract.

    Order: S.NO, input columns, blank cost columns, Min/Max (Alfa then Digi),
    offer counts, blank decision columns, risk alerts (always the final two).
    """
    record: dict[str, Any] = {"S.NO": product.sno}
    for key, value in product.raw_row.items():
        if key not in SNO_ALIASES and key not in GENERATED_COLUMNS:
            record[key] = value

    for col in BLANK_COST_COLUMNS:
        record[col] = ""

    record["Minimum Price Alfa"] = alfa.min_price
    record["Maximum Price Alfa"] = alfa.max_price
    record["Minimum Price Digi"] = digi.min_price
    record["Maximum Price Digi"] = digi.max_price
    record["Alfa Offers Found"] = alfa.offer_count
    record["Digi Offers Found"] = digi.offer_count

    for col in BLANK_DECISION_COLUMNS:
        record[col] = ""

    record["Alfa Risk Alert"] = determine_range_alert(alfa)
    record["Digi Risk Alert"] = determine_range_alert(digi)
    return record


def load_range_products(input_path: Path) -> list[ProductInput]:
    """Read a Brand+Name list and validate every row before any network call.

    Raises:
        ValueError: If the Brand or Name column is missing, or a row has an empty
            Brand/Name (a missing brand could match the wrong product).
    """
    try:
        df = pd.read_csv(input_path)
    except Exception:
        df = pd.read_csv(input_path, sep=None, engine="python")

    # If parsed as a single column containing tabs, retry with tab separator
    if len(df.columns) == 1 and "\t" in str(df.columns[0]):
        df = pd.read_csv(input_path, sep="\t")

    # Clean, strip whitespace, and normalize common column header aliases (e.g. Title, Model -> Name) without collision
    df.columns = normalize_catalog_columns(list(df.columns), preserve_name_space=True)
    name_col = "Name " if "Name " in df.columns else "Name"
    if name_col not in df.columns:
        if len(df.columns) == 1:
            df = pd.read_csv(input_path, header=None, names=["Name"])
            name_col = "Name"
        else:
            raise ValueError(f"Missing required column 'Name' in {input_path.name}.")

    if "Brand" not in df.columns:
        # Gracefully derive Brand from leading token of Name when Brand column is omitted
        df["Brand"] = df[name_col].apply(
            lambda x: str(x).strip().split()[0] if str(x).strip() and not pd.isna(x) else ""
        )

    products: list[ProductInput] = []
    for idx, row in df.iterrows():
        product = parse_product_input(int(idx), row)
        if not product.name or product.name.lower() in ("nan", "none", "product"):
            raise ValueError(f"Row {int(idx) + 1}: product 'Name' is empty or missing.")
        products.append(product)
    return products


async def process_range_item_async(
    product: ProductInput,
    session: AsyncSession,
    semaphore: asyncio.Semaphore,
    render_lock: asyncio.Lock | None = None,
    verbose: bool = False,
    item_index: int = 1,
    total_items: int = 1,
    platform: str = "all",
) -> dict[str, Any]:
    """Scrape selected mall(s) (all query tiers) and build the range record."""
    plat = platform.lower().strip()
    if plat not in ("all", "alfa", "digi"):
        raise ValueError(f"Unsupported platform: '{platform}'. Must be 'all', 'alfa', or 'digi'.")

    _, target_model = extract_search_query_and_model(product.name, brand=product.brand)
    patterns = generate_search_patterns(product.name, brand=product.brand)

    alfa_task = None
    digi_task = None
    if plat in ("all", "alfa"):
        alfa_task = scrape_alfamall(
            session,
            patterns,
            target_model,
            floor_price=None,
            brand=product.brand,
            target_desc=product.name,
        )
    if plat in ("all", "digi"):
        digi_task = scrape_digimall(
            session,
            patterns,
            target_model,
            floor_price=None,
            brand=product.brand,
            target_desc=product.name,
        )

    async with semaphore:
        if alfa_task and digi_task:
            alfa_offers, digi_offers = await asyncio.gather(alfa_task, digi_task)
        elif alfa_task:
            alfa_offers = await alfa_task
            digi_offers = ScrapeResult(offers=[])
        elif digi_task:
            alfa_offers = ScrapeResult(offers=[])
            digi_offers = await digi_task
        else:
            alfa_offers = ScrapeResult(offers=[])
            digi_offers = ScrapeResult(offers=[])

    alfa_range = (
        evaluate_market_range(alfa_offers)
        if plat in ("all", "alfa")
        else MarketRange(min_price=None, max_price=None, offer_count=0)
    )
    digi_range = (
        evaluate_market_range(digi_offers)
        if plat in ("all", "digi")
        else MarketRange(min_price=None, max_price=None, offer_count=0)
    )

    rec = build_range_record(product, alfa_range, digi_range)
    if plat == "alfa":
        rec["Digi Risk Alert"] = ""
    elif plat == "digi":
        rec["Alfa Risk Alert"] = ""

    if verbose and render_lock is not None:
        alfa_str = _fmt_range(
            rec["Minimum Price Alfa"],
            rec["Maximum Price Alfa"],
            rec["Alfa Offers Found"],
            rec["Alfa Risk Alert"],
        )
        digi_str = _fmt_range(
            rec["Minimum Price Digi"],
            rec["Maximum Price Digi"],
            rec["Digi Offers Found"],
            rec["Digi Risk Alert"],
        )
        display_name = product.name if len(product.name) <= 32 else product.name[:30] + ".."
        async with render_lock:
            console.print(
                f"  [bold cyan][{item_index:03d}/{total_items:03d}][/] "
                f"[bold white]{display_name:<32}[/] │ "
                f"[cyan]Alfa:[/] {alfa_str:<24} │ [magenta]Digi:[/] {digi_str}"
            )

    return rec


def _fmt_range(low: Any, high: Any, count: Any, alert: str) -> str:
    if alert == RANGE_ALERT_SERVER_DOWN:
        return "[bold red]DOWN[/]"
    if low is None or pd.isna(low):
        return "[dim]no offers[/]"
    return f"{int(low):,} - {int(high):,} [dim]({int(count)})[/]"


def render_range_start_banner(
    input_path: Path,
    total_items: int,
    concurrency: int,
) -> None:
    """Render the initiation banner for Market Range Mode."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", width=16)
    grid.add_column(style="white")
    grid.add_row("Input Catalog:", str(input_path.name))
    grid.add_row("Total Items:", f"[bold yellow]{total_items}[/] products")
    grid.add_row("Concurrency:", f"[bold magenta]{concurrency}[/] simultaneous searches")
    grid.add_row("Execution Mode:", "[bold green]Market Range Discovery (Min/Max)[/]")

    console.print()
    console.print(
        Panel(
            grid,
            title="[bold green]🔍 MARKET RANGE PIPELINE INITIATED[/]",
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


def render_range_summary(records: list[dict[str, Any]]) -> None:
    """Render a compact executive summary of market ranges."""
    table = Table(
        title="[bold cyan]MARKET RANGE SUMMARY[/]",
        box=box.ROUNDED,
        header_style="bold cyan",
        padding=(0, 1),
    )
    table.add_column("S#", justify="right", style="bold yellow")
    table.add_column("Model / Product", style="bold white", no_wrap=True)
    table.add_column("AlfaMall  Min - Max (offers)", justify="right")
    table.add_column("DigiMall  Min - Max (offers)", justify="right")
    for rec in records:
        name = str(rec.get("Name ", rec.get("Name", "")))
        table.add_row(
            str(rec.get("S.NO", "")),
            name if len(name) <= 28 else name[:26] + "..",
            _fmt_range(
                rec["Minimum Price Alfa"], rec["Maximum Price Alfa"],
                rec["Alfa Offers Found"], rec["Alfa Risk Alert"],
            ),
            _fmt_range(
                rec["Minimum Price Digi"], rec["Maximum Price Digi"],
                rec["Digi Offers Found"], rec["Digi Risk Alert"],
            ),
        )  # fmt: skip
    console.print()
    console.print(table)
    console.print()


def render_range_finish(manifest: RangeExportManifest, total: int, elapsed: float) -> None:
    """Render the completion banner with all produced files."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", width=18)
    grid.add_column(style="white")
    grid.add_row("Execution Status:", "[bold green]Successfully Completed[/]")
    grid.add_row("Models Processed:", str(total))
    grid.add_row("CSV (latest):", str(manifest.csv_latest.resolve()))
    if manifest.xlsx_latest is not None:
        grid.add_row("XLSX (latest):", str(manifest.xlsx_latest.resolve()))
    elif manifest.xlsx_path is not None:
        grid.add_row("XLSX:", str(manifest.xlsx_path.resolve()))
    for warning in manifest.warnings:
        grid.add_row("[yellow]Warning:[/]", f"[yellow]{warning}[/]")
    grid.add_row("Elapsed Time:", f"{elapsed:.2f} seconds")
    console.print(
        Panel(
            grid,
            title="[bold green]MARKET RANGE COMPLETE[/]",
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )


async def run_range_pipeline(
    input_path: str | Path,
    concurrency: int = 3,
    verbose: bool = True,
    export_dir: str | Path | None = None,
    platform: str = "all",
) -> pd.DataFrame:
    """Run Market Range Mode on a Brand+Name catalog and export CSV + XLSX.

    Args:
        input_path: CSV with at least ``Brand`` and ``Name`` columns.
        concurrency: Max simultaneous product lookups.
        verbose: Render summary table and finish banner.
        export_dir: Root of the range output tree (``csv/`` and ``xlsx/`` inside).
        platform: Target e-commerce platform ('all', 'alfa', or 'digi', default: 'all').

    Returns:
        DataFrame in original row order following the range column contract.
    """
    plat = platform.lower().strip()
    if plat not in ("all", "alfa", "digi"):
        raise ValueError(f"Unsupported platform: '{platform}'. Must be 'all', 'alfa', or 'digi'.")

    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found at: {path}")

    products = load_range_products(path)
    start = time.perf_counter()

    if verbose:
        render_range_start_banner(path, len(products), concurrency)

    semaphore = asyncio.Semaphore(concurrency)
    render_lock = asyncio.Lock()
    tasks: list[asyncio.Task[dict[str, Any]]] = []

    async with AsyncSession(impersonate="chrome120") as session:
        for i, product in enumerate(products):
            if plat != "all":
                coro = process_range_item_async(
                    product,
                    session,
                    semaphore,
                    render_lock=render_lock,
                    verbose=verbose,
                    item_index=i + 1,
                    total_items=len(products),
                    platform=plat,
                )
            else:
                coro = process_range_item_async(
                    product,
                    session,
                    semaphore,
                    render_lock=render_lock,
                    verbose=verbose,
                    item_index=i + 1,
                    total_items=len(products),
                )
            tasks.append(asyncio.create_task(coro))
            if i < concurrency - 1 and RANGE_STAGGER_SECONDS > 0:
                await asyncio.sleep(RANGE_STAGGER_SECONDS)
        records = await asyncio.gather(*tasks)  # gather preserves submission order

    out_df = pd.DataFrame(records)
    resolved_export_dir = (
        Path(export_dir)
        if export_dir is not None
        else resolve_option_output_dir(path, option=2)
    )
    manifest = export_range_results(out_df, path, output_dir=resolved_export_dir, render_panel=False)

    if verbose:
        render_range_summary(list(records))
        render_range_finish(manifest, len(records), time.perf_counter() - start)
    return out_df

