"""Market Range Mode: model list (Brand + Name) -> market Min/Max per platform.

Reuses the production scraper and strict variant matcher unchanged. No cost math,
no floors, no commission tiers and no final price decision: only the lowest and
highest in-stock price any vendor lists for the matched model on AlfaMall and
DigiMall, plus how many in-stock offers back those numbers.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from curl_cffi.requests import AsyncSession
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pricing_engine.evaluator import evaluate_market_range
from pricing_engine.exporter import RangeExportManifest, export_range_results
from pricing_engine.matcher import extract_search_query_and_model, generate_search_patterns
from pricing_engine.models import MarketRange, ProductInput, ScrapedOffer, ScrapeResult
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
    df = pd.read_csv(input_path)
    has_legacy_name_space = "Name " in df.columns
    df.columns = [
        "Name " if c == "Name " and has_legacy_name_space else str(c).strip() for c in df.columns
    ]
    name_col = "Name " if "Name " in df.columns else "Name"
    if name_col not in df.columns:
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


@dataclass(frozen=True, slots=True)
class PlatformFallback:
    """One platform repriced against base-model listings instead of the exact variant."""

    platform: str
    modifier: str
    offer_count: int


@dataclass(frozen=True, slots=True)
class RangeItemResult:
    """Output row plus any base-model fallback notices owed to the terminal."""

    record: dict[str, Any]
    fallbacks: tuple[PlatformFallback, ...] = ()


def _detect_fallbacks(
    alfa: list[ScrapedOffer] | ScrapeResult, digi: list[ScrapedOffer] | ScrapeResult
) -> tuple[PlatformFallback, ...]:
    """Read the scraper's base-model fallback metadata for each platform.

    The waterfall already segregates exact from base-model matches and records the
    modifier the market omitted; range mode used to drop that on the floor.
    """
    found: list[PlatformFallback] = []
    for label, result in (("AlfaMall", alfa), ("DigiMall", digi)):
        if isinstance(result, ScrapeResult) and result.active_modifier_fallback:
            found.append(
                PlatformFallback(
                    platform=label,
                    modifier=result.active_modifier_fallback,
                    offer_count=len(result.offers),
                )
            )
    return tuple(found)


def _fallback_marker(fallbacks: tuple[PlatformFallback, ...], platform: str) -> str:
    hit = next((f for f in fallbacks if f.platform == platform), None)
    return f" [bold yellow]⚠ BASE[/] [dim]({hit.modifier} omitted)[/]" if hit else ""


async def process_range_item_async(
    product: ProductInput,
    session: AsyncSession,
    semaphore: asyncio.Semaphore,
    render_lock: asyncio.Lock | None = None,
    verbose: bool = False,
    item_index: int = 1,
    total_items: int = 1,
) -> RangeItemResult:
    """Scrape both malls (all query tiers) and build the range record."""
    _, target_model = extract_search_query_and_model(product.name, brand=product.brand)
    patterns = generate_search_patterns(product.name, brand=product.brand)

    async with semaphore:
        alfa_offers, digi_offers = await asyncio.gather(
            scrape_alfamall(
                session,
                patterns,
                target_model,
                floor_price=None,
                brand=product.brand,
                target_desc=product.name,
            ),
            scrape_digimall(
                session,
                patterns,
                target_model,
                floor_price=None,
                brand=product.brand,
                target_desc=product.name,
            ),
        )

    rec = build_range_record(
        product, evaluate_market_range(alfa_offers), evaluate_market_range(digi_offers)
    )
    fallbacks = _detect_fallbacks(alfa_offers, digi_offers)

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
                f"[cyan]Alfa:[/] {alfa_str:<24}{_fallback_marker(fallbacks, 'AlfaMall')} │ "
                f"[magenta]Digi:[/] {digi_str}{_fallback_marker(fallbacks, 'DigiMall')}"
            )
            for fb in fallbacks:
                console.print(
                    f"      [bold yellow]⚠️  CROSS-CHECK:[/] [cyan]{fb.platform}[/] listings omitted "
                    f"[bold cyan]'{fb.modifier}'[/] → ranged against [bold green]{fb.offer_count} "
                    f"base model offer{'s' if fb.offer_count != 1 else ''}[/]"
                )

    return RangeItemResult(record=rec, fallbacks=fallbacks)


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


def render_range_fallback_notices(
    notices: list[tuple[Any, str, tuple[PlatformFallback, ...]]],
) -> None:
    """Render the consolidated base-model cross-check notice panel.

    Range mode has no cost math and no pricing reason column, so the terminal is the
    only place the operator can be told that a Min/Max came from base-model listings
    rather than the exact variant they asked for.
    """
    if not notices:
        return
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold yellow", no_wrap=True)
    grid.add_column(style="white")
    grid.add_column(style="cyan")
    for sno, name, fallbacks in notices:
        short = name if len(name) <= 46 else name[:44] + ".."
        for fb in fallbacks:
            grid.add_row(
                f"⚠️  #{sno}",
                short,
                f"{fb.platform} omitted '{fb.modifier}' → "
                f"{fb.offer_count} base model offer{'s' if fb.offer_count != 1 else ''}",
            )
    console.print()
    console.print(
        Panel(
            grid,
            title="[bold yellow]⚠️  NOTICE (DO CROSS-CHECK): RANGED AGAINST BASE MODELS[/]",
            subtitle="[dim]Min/Max for these rows excludes a modifier the market omitted[/]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(0, 1),
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
    export_dir: str | Path = "data/outputs/range",
) -> pd.DataFrame:
    """Run Market Range Mode on a Brand+Name catalog and export CSV + XLSX.

    Args:
        input_path: CSV with at least ``Brand`` and ``Name`` columns.
        concurrency: Max simultaneous product lookups.
        verbose: Render summary table and finish banner.
        export_dir: Root of the range output tree (``csv/`` and ``xlsx/`` inside).

    Returns:
        DataFrame in original row order following the range column contract.
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found at: {path}")

    products = load_range_products(path)
    start = time.perf_counter()

    if verbose:
        render_range_start_banner(path, len(products), concurrency)

    semaphore = asyncio.Semaphore(concurrency)
    render_lock = asyncio.Lock()
    tasks: list[asyncio.Task[RangeItemResult]] = []

    async with AsyncSession(impersonate="chrome120") as session:
        for i, product in enumerate(products):
            tasks.append(
                asyncio.create_task(
                    process_range_item_async(
                        product,
                        session,
                        semaphore,
                        render_lock=render_lock,
                        verbose=verbose,
                        item_index=i + 1,
                        total_items=len(products),
                    )
                )
            )
            if i < len(products) - 1 and RANGE_STAGGER_SECONDS > 0:
                await asyncio.sleep(RANGE_STAGGER_SECONDS)
        results = await asyncio.gather(*tasks)  # gather preserves submission order

    records = [r.record for r in results]
    out_df = pd.DataFrame(records)
    manifest = export_range_results(out_df, path, output_dir=export_dir, render_panel=False)

    if verbose:
        notices = [
            (products[i].sno, products[i].name, r.fallbacks)
            for i, r in enumerate(results)
            if r.fallbacks
        ]
        render_range_fallback_notices(notices)
        render_range_summary(records)
        render_range_finish(manifest, len(records), time.perf_counter() - start)
    return out_df

