import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
from curl_cffi.requests import AsyncSession
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pricing_engine.calculator import (
    calculate_baseline,
    calculate_cost_base,
    calculate_floors,
    calculate_shipping_estimate,
    calculate_volumetric_weight,
)
from pricing_engine.db import SupabaseClient
from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.learner import AutonomousLearner
from pricing_engine.matcher import (
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    referee_match,
)
from pricing_engine.models import (
    CostFloors,
    PlatformPricingResult,
    ProductInput,
    ScrapedOffer,
    ScrapeResult,
)
from pricing_engine.registry import InMemoryRegistry
from pricing_engine.scraper import scrape_alfamall, scrape_digimall

default_learner = AutonomousLearner()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

console = Console(legacy_windows=False)
logger = logging.getLogger(__name__)

ZONE_PRICE: float = 70.0
DIVISOR: float = 5000.0


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


def determine_risk_alert(res: PlatformPricingResult) -> str:
    """Determine standardized commercial risk alert code following priority hierarchy.

    Priority hierarchy:
    1. SERVER_DOWN: Connection failed, portal down, or final price/profit missing.
    2. NEGATIVE_MARGIN: Defensive check in case profit is zero or negative.
    3. SAFE_FALLBACK: Competitors are dumping below floor, price is uncompetitive.
    4. THIN_BUFFER: Profit is between Rs. 1 and Rs. 699 (courier re-weighing risk).
    5. NONE: Healthy optimal margin (profit >= Rs. 700).

    Args:
        res: PlatformPricingResult from platform evaluation.

    Returns:
        One of 'SERVER_DOWN', 'NEGATIVE_MARGIN', 'SAFE_FALLBACK', 'THIN_BUFFER', 'NONE'.
    """
    if (
        res.status == "Server Down / Unreachable"
        or res.final_price is None
        or res.real_profit is None
    ):
        return "SERVER_DOWN"
    if res.real_profit <= 0:
        return "NEGATIVE_MARGIN"
    if res.status == "Safe Fallback":
        return "SAFE_FALLBACK"
    if res.real_profit < 700:
        return "THIN_BUFFER"
    return "NONE"


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert arbitrary values to float, handling strings with commas or NaNs."""
    if val is None or pd.isna(val):
        return default
    try:
        clean_str = str(val).replace(",", "").strip()
        return float(clean_str)
    except (ValueError, TypeError):
        return default


def parse_product_input(idx: int, row: pd.Series) -> ProductInput:
    """Parse and sanitize a raw CSV row into a strongly typed ProductInput.

    Args:
        idx: 0-indexed row number from DataFrame iteration.
        row: Pandas Series representing the product row.

    Returns:
        Structured ProductInput instance.
    """
    sno = row.get("S.NO", idx + 1)
    brand = str(row.get("Brand", "Brand")).strip()

    raw_name = row.get("Name ")
    if raw_name is None or pd.isna(raw_name):
        raw_name = row.get("Name", "Product")
    name = str(raw_name).strip()

    length = _safe_float(row.get("Length"), 0.0)
    width = _safe_float(row.get("Width"), 0.0)
    height = _safe_float(row.get("Height"), 0.0)
    net_price = _safe_float(row.get("Net Price"), 0.0)
    profit = _safe_float(row.get("Profit"), 500.0)

    return ProductInput(
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


def build_output_record(
    product: ProductInput,
    shipping: float,
    floors: CostFloors,
    baseline_calc: float,
    alfa_res: PlatformPricingResult,
    digi_res: PlatformPricingResult,
) -> dict[str, Any]:
    """Combine input row data and calculated platform results into final output dictionary.

    Args:
        product: Input product item.
        shipping: Calculated or catalog shipping estimate.
        floors: CostFloors object.
        baseline_calc: Standard baseline catalog price.
        alfa_res: PlatformPricingResult for AlfaMall.
        digi_res: PlatformPricingResult for DigiMall.

    Returns:
        Dictionary adhering to the target CSV schema.
    """
    out_record: dict[str, Any] = dict(product.raw_row)
    out_record["Shipping Estimate"] = shipping
    out_record["Commision"] = "10.00%"
    out_record["Digi Effective Commision"] = digi_res.effective_comm

    # Total Without Profit: If Digi uses 8%, record 8% breakeven (cost_base / 0.92)
    # If 10%, record 10% breakeven (cost_base / 0.90)
    if digi_res.effective_comm == "8.00%":
        out_record["Total Without Profit"] = round(floors.zero_margin_8)
    else:
        out_record["Total Without Profit"] = round(floors.zero_margin_10)

    out_record["Calculation"] = round(baseline_calc)

    out_record["Minimum Price Alfa"] = alfa_res.min_price
    out_record["Maximum Price Alfa"] = alfa_res.max_price
    out_record["Minimum Price Digi"] = digi_res.min_price
    out_record["Maximum Price Digi"] = digi_res.max_price

    out_record["Final Price Alfa"] = alfa_res.final_price
    out_record["Final Price Digi"] = digi_res.final_price
    out_record["Alfa Real Profit"] = alfa_res.real_profit
    out_record["Digi Real Profit"] = digi_res.real_profit
    out_record["Alfa Reason"] = alfa_res.reason
    out_record["Digi Reason"] = digi_res.reason
    out_record["Alfa Risk Alert"] = determine_risk_alert(alfa_res)
    out_record["Digi Risk Alert"] = determine_risk_alert(digi_res)

    return out_record


def process_product_with_offers(
    product: ProductInput,
    alfa_offers: list[ScrapedOffer] | ScrapeResult,
    digi_offers: list[ScrapedOffer] | ScrapeResult,
) -> dict[str, Any]:
    """Execute complete cost math and pricing decisions given fetched competitor offers.

    Args:
        product: ProductInput instance.
        alfa_offers: Offers scraped from AlfaMall (or ScrapeResult).
        digi_offers: Offers scraped from DigiMall (or ScrapeResult).

    Returns:
        Repriced output dictionary.
    """
    csv_shipping = product.raw_row.get("Shipping Estimate")
    if pd.notna(csv_shipping) and _safe_float(csv_shipping) > 0:
        shipping = round(_safe_float(csv_shipping), 2)
    else:
        vol_weight = calculate_volumetric_weight(
            product.length, product.width, product.height, divisor=DIVISOR
        )
        shipping = calculate_shipping_estimate(vol_weight, rate_per_kg=ZONE_PRICE)

    cost_base = calculate_cost_base(product.net_price, shipping)
    floors = calculate_floors(cost_base, min_profit=500.0)
    baseline_calc = calculate_baseline(cost_base, target_profit=product.profit)

    alfa_res = evaluate_alfa_pricing(floors, alfa_offers)
    digi_res = evaluate_digi_pricing(floors, digi_offers)

    return build_output_record(
        product=product,
        shipping=shipping,
        floors=floors,
        baseline_calc=baseline_calc,
        alfa_res=alfa_res,
        digi_res=digi_res,
    )


def render_start_banner(
    input_path: Path,
    output_path: Path,
    total_items: int,
    concurrency: int,
) -> None:
    """Render executive startup banner with operational parameters."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", width=18)
    grid.add_column(style="white")
    grid.add_row("Source Catalog:", f"{input_path.name} ({total_items} items loaded)")
    grid.add_row("Output Target:", f"{output_path.name}")
    grid.add_row("Scraper Workers:", f"Direct JSON Search APIs ({concurrency} concurrent workers)")
    grid.add_row(
        "Pricing Strategy:", "AlfaMall 10% Floor | DigiMall Two-Tier (10% -> 8% Bank Switch)"
    )

    console.print()
    console.print(
        Panel(
            grid,
            title="[bold green]ALFAMALL & DIGIMALL DYNAMIC REPRICING ENGINE[/]",
            subtitle="[dim]Real-time Competitive Price Discovery & Margin Optimization[/]",
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


def render_finish_banner(
    output_path: Path,
    total_processed: int,
    elapsed_seconds: float,
) -> None:
    """Render clean executive completion banner."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", width=18)
    grid.add_column(style="white")
    grid.add_row("Execution Status:", "[bold green]Successfully Completed[/]")
    grid.add_row("Total Repriced:", f"{total_processed} catalog items")
    grid.add_row("Exported File:", f"[bold white]{output_path.resolve()}[/]")
    grid.add_row("Elapsed Time:", f"{elapsed_seconds:.2f} seconds")

    console.print()
    console.print(
        Panel(
            grid,
            title="[bold green]PIPELINE EXECUTION COMPLETE[/]",
            subtitle="[dim]All catalog items evaluated & exported to disk[/]",
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


def build_scraped_sellers_table(
    floors: CostFloors,
    alfa_offers: list[ScrapedOffer] | ScrapeResult,
    digi_offers: list[ScrapedOffer] | ScrapeResult,
    alfa_res: PlatformPricingResult,
    digi_res: PlatformPricingResult,
) -> Table:
    """Build a crystal-clear table listing all scraped competitor sellers, prices, and status."""
    tbl = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
        expand=True,
    )
    tbl.add_column("Platform", width=9)
    tbl.add_column("Seller / Vendor", style="bold white", width=17)
    tbl.add_column("Scraped Price", justify="right", style="bold yellow", width=13)
    tbl.add_column("Engine Evaluation / Status", ratio=1)

    # 1. AlfaMall Scraped Competitors
    is_alfa_down = alfa_res.status == "Server Down / Unreachable" or (
        isinstance(alfa_offers, ScrapeResult) and not alfa_offers.is_success
    )

    if is_alfa_down:
        tbl.add_row(
            "[bold #2c4699]AlfaMall[/]",
            "[bold red]Connection Failed[/]",
            "[dim]N/A[/]",
            "[bold red]Remote Portal Down / Unreachable (Skipped)[/]",
        )
    elif not alfa_offers:
        tbl.add_row(
            "[bold #2c4699]AlfaMall[/]",
            "[dim]No sellers found[/]",
            "[dim]0 scraped[/]",
            "[bold cyan]Monopoly Pricing (+Rs. 4,000 margin)[/]",
        )
    else:
        active_alfa = [o for o in alfa_offers if not o.is_sold_out]
        sorted_alfa = sorted(active_alfa, key=lambda x: x.price)
        sold_out_alfa = [o for o in alfa_offers if o.is_sold_out]

        dropped_alfa = [o for o in sorted_alfa if o.price <= floors.floor_alfa]
        viable_alfa = [o for o in sorted_alfa if o.price > floors.floor_alfa]

        if viable_alfa:
            # 1. Dropped sub-floor offers (top 3 if > 3, else all)
            if len(dropped_alfa) > 3:
                for o in dropped_alfa[:3]:
                    dupe_tag = f" [dim][{o.duplicate_count - 1} dupes dropped][/]" if o.duplicate_count > 1 else ""
                    tbl.add_row(
                        "[bold #2c4699]AlfaMall[/]",
                        o.vendor_name[:17],
                        f"Rs. {o.price:,.0f}",
                        f"[red]Dropped (< Floor Rs. {floors.floor_alfa:,.0f})[/]{dupe_tag}",
                    )
                rem_dropped = len(dropped_alfa) - 3
                tbl.add_row(
                    "[bold #2c4699]AlfaMall[/]",
                    f"[dim]... +{rem_dropped} more sub-floor[/]",
                    f"[dim]Rs. {dropped_alfa[3].price:,.0f}+[/]",
                    f"[dim red]Dropped (< Floor Rs. {floors.floor_alfa:,.0f})[/]",
                )
            else:
                for o in dropped_alfa:
                    dupe_tag = f" [dim][{o.duplicate_count - 1} dupes dropped][/]" if o.duplicate_count > 1 else ""
                    tbl.add_row(
                        "[bold #2c4699]AlfaMall[/]",
                        o.vendor_name[:17],
                        f"Rs. {o.price:,.0f}",
                        f"[red]Dropped (< Floor Rs. {floors.floor_alfa:,.0f})[/]{dupe_tag}",
                    )

            # 2. Target Undercut (Lowest Viable) - ALWAYS explicitly rendered
            lowest_viable = viable_alfa[0]
            lv_dupe = f" [dim][{lowest_viable.duplicate_count - 1} dupes dropped][/]" if lowest_viable.duplicate_count > 1 else ""
            tbl.add_row(
                "[bold #2c4699]AlfaMall[/]",
                lowest_viable.vendor_name[:17],
                f"Rs. {lowest_viable.price:,.0f}",
                f"[bold green]Target Undercut (Lowest Viable)[/]{lv_dupe}",
            )

            # 3. Next 2-3 viable competitors
            for o in viable_alfa[1:4]:
                v_dupe = f" [dim][{o.duplicate_count - 1} dupes dropped][/]" if o.duplicate_count > 1 else ""
                tbl.add_row(
                    "[bold #2c4699]AlfaMall[/]",
                    o.vendor_name[:17],
                    f"Rs. {o.price:,.0f}",
                    f"[dim]Viable Competitor[/]{v_dupe}",
                )

            # 4. Rollup higher offers with true max ceiling
            if len(viable_alfa) > 4:
                rem_viable = len(viable_alfa) - 4
                min_rem = viable_alfa[4].price
                max_rem = viable_alfa[-1].price
                tbl.add_row(
                    "[bold #2c4699]AlfaMall[/]",
                    f"[dim]... +{rem_viable} more sellers[/]",
                    f"[dim]Rs. {min_rem:,.0f}+[/]",
                    f"[dim]Higher offers (up to Rs. {max_rem:,.0f})[/]",
                )
        else:
            # All scraped competitors are selling below floor
            for o in dropped_alfa[:3]:
                dupe_tag = f" [dim][{o.duplicate_count - 1} dupes dropped][/]" if o.duplicate_count > 1 else ""
                tbl.add_row(
                    "[bold #2c4699]AlfaMall[/]",
                    o.vendor_name[:17],
                    f"Rs. {o.price:,.0f}",
                    f"[red]Dropped (< Floor Rs. {floors.floor_alfa:,.0f})[/]{dupe_tag}",
                )
            if len(dropped_alfa) > 3:
                rem_dropped = len(dropped_alfa) - 3
                min_rem = dropped_alfa[3].price
                max_rem = dropped_alfa[-1].price
                tbl.add_row(
                    "[bold #2c4699]AlfaMall[/]",
                    f"[dim]... +{rem_dropped} more loss-makers[/]",
                    f"[dim]Rs. {min_rem:,.0f}+[/]",
                    f"[dim red]All sub-floor (up to Rs. {max_rem:,.0f})[/]",
                )

        for s in sold_out_alfa[:2]:
            tbl.add_row(
                "[bold #2c4699]AlfaMall[/]",
                s.vendor_name[:17],
                f"Rs. {s.price:,.0f}",
                "[dim red]Out of Stock (Ignored)[/]",
            )

    # 2. DigiMall Scraped Competitors
    is_digi_down = digi_res.status == "Server Down / Unreachable" or (
        isinstance(digi_offers, ScrapeResult) and not digi_offers.is_success
    )

    hard_digi_floor = floors.floor_digi_8

    if is_digi_down:
        tbl.add_row(
            "[bold #229693]DigiMall[/]",
            "[bold red]Connection Failed[/]",
            "[dim]N/A[/]",
            "[bold red]Remote Portal Down / Unreachable (Skipped)[/]",
        )
    elif not digi_offers:
        tbl.add_row(
            "[bold #229693]DigiMall[/]",
            "[dim]No sellers found[/]",
            "[dim]0 scraped[/]",
            "[bold cyan]Baseline Undercut (+2% margin)[/]",
        )
    else:
        active_digi = [o for o in digi_offers if not o.is_sold_out]
        sorted_digi = sorted(active_digi, key=lambda x: x.price)
        sold_out_digi = [o for o in digi_offers if o.is_sold_out]

        dropped_digi = [o for o in sorted_digi if o.price <= hard_digi_floor]
        viable_digi = [o for o in sorted_digi if o.price > hard_digi_floor]

        if viable_digi:
            # 1. Dropped sub-floor offers (top 3 if > 3, else all)
            if len(dropped_digi) > 3:
                for o in dropped_digi[:3]:
                    dupe_tag = f" [dim][{o.duplicate_count - 1} dupes dropped][/]" if o.duplicate_count > 1 else ""
                    tbl.add_row(
                        "[bold #229693]DigiMall[/]",
                        o.vendor_name[:17],
                        f"Rs. {o.price:,.0f}",
                        f"[red]Dropped (< 8% Floor Rs. {hard_digi_floor:,.0f})[/]{dupe_tag}",
                    )
                rem_dropped = len(dropped_digi) - 3
                tbl.add_row(
                    "[bold #229693]DigiMall[/]",
                    f"[dim]... +{rem_dropped} more sub-floor[/]",
                    f"[dim]Rs. {dropped_digi[3].price:,.0f}+[/]",
                    f"[dim red]Dropped (< 8% Floor Rs. {hard_digi_floor:,.0f})[/]",
                )
            else:
                for o in dropped_digi:
                    dupe_tag = f" [dim][{o.duplicate_count - 1} dupes dropped][/]" if o.duplicate_count > 1 else ""
                    tbl.add_row(
                        "[bold #229693]DigiMall[/]",
                        o.vendor_name[:17],
                        f"Rs. {o.price:,.0f}",
                        f"[red]Dropped (< 8% Floor Rs. {hard_digi_floor:,.0f})[/]{dupe_tag}",
                    )

            # 2. Target Undercut - ALWAYS explicitly rendered
            lowest_viable = viable_digi[0]
            comm_note = "8% Viable" if digi_res.effective_comm == "8.00%" else "10% Viable"
            lv_dupe = f" [dim][{lowest_viable.duplicate_count - 1} dupes dropped][/]" if lowest_viable.duplicate_count > 1 else ""
            tbl.add_row(
                "[bold #229693]DigiMall[/]",
                lowest_viable.vendor_name[:17],
                f"Rs. {lowest_viable.price:,.0f}",
                f"[bold green]Target Undercut ({comm_note})[/]{lv_dupe}",
            )

            # 3. Next 2-3 viable competitors
            for o in viable_digi[1:4]:
                v_dupe = f" [dim][{o.duplicate_count - 1} dupes dropped][/]" if o.duplicate_count > 1 else ""
                tbl.add_row(
                    "[bold #229693]DigiMall[/]",
                    o.vendor_name[:17],
                    f"Rs. {o.price:,.0f}",
                    f"[dim]Viable Competitor[/]{v_dupe}",
                )

            # 4. Rollup higher offers with true max ceiling
            if len(viable_digi) > 4:
                rem_viable = len(viable_digi) - 4
                min_rem = viable_digi[4].price
                max_rem = viable_digi[-1].price
                tbl.add_row(
                    "[bold #229693]DigiMall[/]",
                    f"[dim]... +{rem_viable} more sellers[/]",
                    f"[dim]Rs. {min_rem:,.0f}+[/]",
                    f"[dim]Higher offers (up to Rs. {max_rem:,.0f})[/]",
                )
        else:
            # All scraped competitors are selling below floor
            for o in dropped_digi[:3]:
                dupe_tag = f" [dim][{o.duplicate_count - 1} dupes dropped][/]" if o.duplicate_count > 1 else ""
                tbl.add_row(
                    "[bold #229693]DigiMall[/]",
                    o.vendor_name[:17],
                    f"Rs. {o.price:,.0f}",
                    f"[red]Dropped (< 8% Floor Rs. {hard_digi_floor:,.0f})[/]{dupe_tag}",
                )
            if len(dropped_digi) > 3:
                rem_dropped = len(dropped_digi) - 3
                min_rem = dropped_digi[3].price
                max_rem = dropped_digi[-1].price
                tbl.add_row(
                    "[bold #229693]DigiMall[/]",
                    f"[dim]... +{rem_dropped} more loss-makers[/]",
                    f"[dim]Rs. {min_rem:,.0f}+[/]",
                    f"[dim red]All sub-floor (up to Rs. {max_rem:,.0f})[/]",
                )

        for s in sold_out_digi[:2]:
            tbl.add_row(
                "[bold #229693]DigiMall[/]",
                s.vendor_name[:17],
                f"Rs. {s.price:,.0f}",
                "[dim red]Out of Stock (Ignored)[/]",
            )

    return tbl


def render_audit_card(
    product: ProductInput,
    shipping: float,
    floors: CostFloors,
    baseline_calc: float,
    target_model: str,
    alfa_offers: list[ScrapedOffer] | ScrapeResult,
    digi_offers: list[ScrapedOffer] | ScrapeResult,
    alfa_res: PlatformPricingResult,
    digi_res: PlatformPricingResult,
) -> None:
    """Print a polished, executive-grade audit card enclosed in a rounded box."""
    tot_10 = round(floors.zero_margin_10)
    tot_8 = round(floors.zero_margin_8)

    # 1. Logistics and Cost Breakdown Grid
    specs = Table.grid(padding=(0, 3), expand=True)
    specs.add_column(style="cyan")
    specs.add_column(style="bold white")
    specs.add_column(style="cyan")
    specs.add_column(style="bold white")

    dim_str = f"{product.length:g}x{product.width:g}x{product.height:g} cm"
    specs.add_row(
        "Net Catalog Price:",
        f"Rs. {product.net_price:,.0f}",
        "[#2c4699]Alfa 10% (Without 500):[/]",
        f"Rs. {tot_10:,}",
    )
    specs.add_row(
        "Courier Shipping:",
        f"Rs. {shipping:,.2f}",
        "[bold #2c4699]Alfa 10% Floor (+500):[/]",
        f"[bold #2c4699]Rs. {floors.floor_alfa:,.0f}[/]",
    )
    specs.add_row(
        "Real Landed Cost:",
        f"[bold green]Rs. {floors.cost_base:,.2f}[/]",
        "[#229693]Digi 8% (Without 500):[/]",
        f"Rs. {tot_8:,}",
    )
    specs.add_row(
        "Dimensions:",
        dim_str,
        "[bold #229693]Digi 8% Floor (+500):[/]",
        f"[bold #229693]Rs. {floors.floor_digi_8:,.0f}[/]",
    )

    # 2. Competitor Sellers Table
    sellers_tbl = build_scraped_sellers_table(
        floors=floors,
        alfa_offers=alfa_offers,
        digi_offers=digi_offers,
        alfa_res=alfa_res,
        digi_res=digi_res,
    )

    # 3. Platform Comparison Table
    plat_tbl = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
        expand=True,
    )
    plat_tbl.add_column("Decision Metric", style="bold cyan", width=16)
    plat_tbl.add_column("[bold #2c4699]AlfaMall (Strict 10%)[/]", style="white", ratio=1)
    plat_tbl.add_column("[bold #229693]DigiMall (Two-Tier Switch)[/]", style="white", ratio=1)

    # Active offers summary
    is_alfa_down = alfa_res.status == "Server Down / Unreachable" or (
        isinstance(alfa_offers, ScrapeResult) and not alfa_offers.is_success
    )
    is_digi_down = digi_res.status == "Server Down / Unreachable" or (
        isinstance(digi_offers, ScrapeResult) and not digi_offers.is_success
    )

    if is_alfa_down:
        alfa_offers_str = "[bold red]Connection Failed (Down)[/]"
    else:
        alfa_active_count = len([o for o in alfa_offers if not o.is_sold_out])
        alfa_drop_count = len(alfa_res.dropped)
        alfa_offers_str = f"{alfa_active_count} verified offers"
        if alfa_drop_count > 0:
            alfa_offers_str += f" ({alfa_drop_count} dropped)"

    if is_digi_down:
        digi_offers_str = "[bold red]Connection Failed (Down)[/]"
    else:
        digi_active_count = len([o for o in digi_offers if not o.is_sold_out])
        digi_drop_count = len(digi_res.dropped)
        digi_offers_str = f"{digi_active_count} verified offers"
        if digi_drop_count > 0:
            digi_offers_str += f" ({digi_drop_count} dropped)"

    plat_tbl.add_row("Scraped Offers", alfa_offers_str, digi_offers_str)

    # Commission tier applied
    if digi_res.effective_comm == "8.00%":
        digi_comm_badge = "[bold blue]8.00% Emergency Switch[/]"
    else:
        digi_comm_badge = "[#229693]8% + 2% Spread[/]"
    plat_tbl.add_row("Bank Commission", "10.00% Standard", digi_comm_badge)

    # Final Price
    if alfa_res.status == "Server Down / Unreachable":
        alfa_p_str = "[bold red][SERVER DOWN - RETRY LATER][/]"
    elif alfa_res.final_price is not None:
        if alfa_res.status == "Safe Fallback":
            alfa_p_str = (
                f"[bold red]Rs. {alfa_res.final_price:,} (SAFE FALLBACK - UNCOMPETITIVE)[/]"
            )
        elif "capped" in (alfa_res.reason or "").lower():
            alfa_p_str = f"[bold yellow]Rs. {alfa_res.final_price:,} (CAPPED SWEET-SPOT)[/]"
        else:
            alfa_p_str = f"[bold #2c4699]Rs. {alfa_res.final_price:,}[/]"
    else:
        alfa_p_str = "[bold yellow]SKIP / NaN (Loss Prevented)[/]"

    if digi_res.status == "Server Down / Unreachable":
        digi_p_str = "[bold red][SERVER DOWN - RETRY LATER][/]"
    elif digi_res.final_price is not None:
        if digi_res.status == "Safe Fallback":
            digi_p_str = (
                f"[bold red]Rs. {digi_res.final_price:,} (SAFE FALLBACK - UNCOMPETITIVE)[/]"
            )
        elif "capped" in (digi_res.reason or "").lower():
            digi_p_str = f"[bold yellow]Rs. {digi_res.final_price:,} (CAPPED SWEET-SPOT)[/]"
        else:
            digi_p_str = f"[bold #229693]Rs. {digi_res.final_price:,}[/]"
    else:
        digi_p_str = "[bold yellow]SKIP / NaN (Loss Prevented)[/]"

    plat_tbl.add_row("Final Price", alfa_p_str, digi_p_str)

    # Real Profit
    if alfa_res.status == "Server Down / Unreachable":
        alfa_prof_str = "[dim red]Rs. 0 (Server Down)[/]"
    elif alfa_res.final_price is not None:
        if alfa_res.real_profit <= 0:
            alfa_prof_str = f"[bold white on red]Rs. {alfa_res.real_profit:,} (NEGATIVE MARGIN)[/]"
        elif alfa_res.real_profit < 700:
            alfa_prof_str = (
                f"[bold red]+Rs. {alfa_res.real_profit:,} (THIN BUFFER - VOLUMETRIC RISK)[/]"
            )
        else:
            alfa_prof_str = f"[bold green]+Rs. {alfa_res.real_profit:,}[/]"
    else:
        alfa_prof_str = "[dim]Rs. 0 (Loss Prevented)[/]"

    if digi_res.status == "Server Down / Unreachable":
        digi_prof_str = "[dim red]Rs. 0 (Server Down)[/]"
    elif digi_res.final_price is not None:
        if digi_res.real_profit <= 0:
            digi_prof_str = f"[bold white on red]Rs. {digi_res.real_profit:,} (NEGATIVE MARGIN)[/]"
        elif digi_res.real_profit < 700:
            digi_prof_str = (
                f"[bold red]+Rs. {digi_res.real_profit:,} (THIN BUFFER - VOLUMETRIC RISK)[/]"
            )
        else:
            digi_prof_str = f"[bold green]+Rs. {digi_res.real_profit:,}[/]"
    else:
        digi_prof_str = "[dim]Rs. 0 (Loss Prevented)[/]"

    plat_tbl.add_row("Real Net Profit", alfa_prof_str, digi_prof_str)
    plat_tbl.add_row("Strategy Reason", alfa_res.reason, digi_res.reason)

    content = Table.grid(padding=(1, 0), expand=True)
    content.add_row(specs)
    content.add_row(sellers_tbl)
    content.add_row(plat_tbl)

    card = Panel(
        content,
        title=(
            f"[bold yellow]ITEM #{product.sno}[/] [bold white]{product.name}[/]"
            f" [dim](Model: {target_model})[/]"
        ),
        border_style="blue",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print()
    console.print(card)


async def process_item_async(
    product: ProductInput,
    session: AsyncSession,
    semaphore: asyncio.Semaphore,
    render_lock: asyncio.Lock | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Execute scraping and pricing calculations for a single product with concurrency control."""
    _, target_model = extract_search_query_and_model(product.name, brand=product.brand)
    patterns = generate_search_patterns(product.name, brand=product.brand)

    csv_shipping = product.raw_row.get("Shipping Estimate")
    if pd.notna(csv_shipping) and _safe_float(csv_shipping) > 0:
        shipping = round(_safe_float(csv_shipping), 2)
    else:
        vol_weight = calculate_volumetric_weight(
            product.length, product.width, product.height, divisor=DIVISOR
        )
        shipping = calculate_shipping_estimate(vol_weight, rate_per_kg=ZONE_PRICE)

    cost_base = calculate_cost_base(product.net_price, shipping)
    floors = calculate_floors(cost_base, min_profit=500.0)
    baseline_calc = calculate_baseline(cost_base, target_profit=product.profit)

    async with semaphore:
        alfa_task = scrape_alfamall(
            session, patterns, target_model, floor_price=floors.floor_alfa
        )
        digi_task = scrape_digimall(
            session, patterns, target_model, floor_price=floors.floor_digi_8
        )
        alfa_offers, digi_offers = await asyncio.gather(alfa_task, digi_task)

    alfa_res = evaluate_alfa_pricing(floors, alfa_offers)
    digi_res = evaluate_digi_pricing(floors, digi_offers)

    # Autonomous Multi-Catalog Learning Ingestion (ADR-003)
    target_slots = extract_product_slots(product.name, brand=product.brand)
    all_raw_offers: list[ScrapedOffer] = []
    if isinstance(alfa_offers, ScrapeResult):
        all_raw_offers.extend(alfa_offers.offers)
    elif isinstance(alfa_offers, list):
        all_raw_offers.extend(alfa_offers)

    if isinstance(digi_offers, ScrapeResult):
        all_raw_offers.extend(digi_offers.offers)
    elif isinstance(digi_offers, list):
        all_raw_offers.extend(digi_offers)

    category = str(product.raw_row.get("Category", "")).strip() or "APPLIANCE"
    for offer in all_raw_offers:
        if offer.is_sold_out:
            continue
        match_dec = referee_match(target_slots, offer.raw_title, brand=product.brand)
        if (
            match_dec.is_match
            and target_slots.residuals
            and match_dec.candidate_slots
            and match_dec.candidate_slots.residuals
        ):
            for t_res in target_slots.residuals:
                for c_res in match_dec.candidate_slots.residuals:
                    default_learner.buffer_observation(
                        brand=product.brand,
                        category=category,
                        anchor_model=target_slots.anchor,
                        target_residual=t_res,
                        candidate_residual=c_res,
                        vendor_name=offer.vendor_name,
                        raw_title=offer.raw_title,
                    )

    if verbose:
        if render_lock is not None:
            async with render_lock:
                render_audit_card(
                    product=product,
                    shipping=shipping,
                    floors=floors,
                    baseline_calc=baseline_calc,
                    target_model=target_model,
                    alfa_offers=alfa_offers,
                    digi_offers=digi_offers,
                    alfa_res=alfa_res,
                    digi_res=digi_res,
                )
        else:
            render_audit_card(
                product=product,
                shipping=shipping,
                floors=floors,
                baseline_calc=baseline_calc,
                target_model=target_model,
                alfa_offers=alfa_offers,
                digi_offers=digi_offers,
                alfa_res=alfa_res,
                digi_res=digi_res,
            )

    return build_output_record(
        product=product,
        shipping=shipping,
        floors=floors,
        baseline_calc=baseline_calc,
        alfa_res=alfa_res,
        digi_res=digi_res,
    )


async def _process_item_worker(
    idx: int,
    product: ProductInput,
    session: AsyncSession,
    semaphore: asyncio.Semaphore,
    render_lock: asyncio.Lock,
    verbose: bool = True,
) -> dict[str, Any]:
    """Helper worker to execute an item and attach its original row index for deterministic sorting."""
    record = await process_item_async(
        product=product,
        session=session,
        semaphore=semaphore,
        render_lock=render_lock,
        verbose=verbose,
    )
    record["_original_idx"] = idx
    return record


def render_summary_table(records: list[dict[str, Any]]) -> None:
    """Render a crystal-clear executive summary table of all repriced products."""
    table = Table(
        title="[bold cyan]DYNAMIC REPRICING EXECUTIVE SUMMARY[/]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
        expand=False,
    )
    table.add_column("S#", justify="right", style="bold yellow")
    table.add_column("Model / Product", style="bold white")
    table.add_column("Cost Base", justify="right", style="dim")
    table.add_column("Alfa Price", justify="right", style="bold #2c4699")
    table.add_column("Alfa Net", justify="right", style="bold green")
    table.add_column("Digi Price", justify="right", style="bold #229693")
    table.add_column("Rate", justify="center", style="blue")
    table.add_column("Digi Net", justify="right", style="bold green")

    for rec in records:
        sno = str(rec.get("S.NO", ""))
        name = str(rec.get("Name ", rec.get("Name", "Product")))
        short_name = name.replace("GREE SPLIT AC ", "").replace("GREE FLOOR STANDING ", "FS ")
        if len(short_name) > 18:
            short_name = short_name[:16] + ".."

        net_val = _safe_float(rec.get("Net Price", 0))
        ship_val = _safe_float(rec.get("Shipping Estimate", 0))
        real_cost_str = f"{(net_val + ship_val):,.0f}"

        alfa_p_val = rec.get("Final Price Alfa")
        alfa_reason = str(rec.get("Alfa Reason", ""))
        alfa_reason_lower = alfa_reason.lower()
        alfa_alert = str(rec.get("Alfa Risk Alert", ""))

        if (
            "server is down" in alfa_reason_lower
            or "unreachable" in alfa_reason_lower
            or alfa_alert == "SERVER_DOWN"
        ):
            alfa_p = "[bold red]DOWN[/]"
            alfa_profit = "[dim red]0[/]"
        elif pd.notna(alfa_p_val) and alfa_p_val is not None and str(alfa_p_val).strip() != "":
            raw_alfa_p = f"{int(float(alfa_p_val)):,}"
            if alfa_alert == "SAFE_FALLBACK" or "safe fallback" in alfa_reason_lower:
                alfa_p = f"[bold red]{raw_alfa_p}[/]"
            elif "capped" in alfa_reason_lower:
                alfa_p = f"[bold yellow]{raw_alfa_p}[/]"
            else:
                alfa_p = f"[bold #2c4699]{raw_alfa_p}[/]"

            alfa_prof_val = float(rec.get("Alfa Real Profit", 0))
            if alfa_prof_val <= 0:
                alfa_profit = f"[bold white on red]{int(alfa_prof_val):,}[/]"
            elif alfa_prof_val < 700:
                alfa_profit = f"[bold red]+{int(alfa_prof_val):,}[/]"
            else:
                alfa_profit = f"[bold green]+{int(alfa_prof_val):,}[/]"
        else:
            alfa_p = "SKIP"
            alfa_profit = "0"

        digi_p_val = rec.get("Final Price Digi")
        digi_reason = str(rec.get("Digi Reason", ""))
        digi_reason_lower = digi_reason.lower()
        digi_alert = str(rec.get("Digi Risk Alert", ""))

        if (
            "server is down" in digi_reason_lower
            or "unreachable" in digi_reason_lower
            or digi_alert == "SERVER_DOWN"
        ):
            digi_p = "[bold red]DOWN[/]"
            digi_profit = "[dim red]0[/]"
            digi_comm = "[dim red]N/A[/]"
        elif pd.notna(digi_p_val) and digi_p_val is not None and str(digi_p_val).strip() != "":
            raw_digi_p = f"{int(float(digi_p_val)):,}"
            if digi_alert == "SAFE_FALLBACK" or "safe fallback" in digi_reason_lower:
                digi_p = f"[bold red]{raw_digi_p}[/]"
            elif "capped" in digi_reason_lower:
                digi_p = f"[bold yellow]{raw_digi_p}[/]"
            else:
                digi_p = f"[bold #229693]{raw_digi_p}[/]"

            digi_prof_val = float(rec.get("Digi Real Profit", 0))
            if digi_prof_val <= 0:
                digi_profit = f"[bold white on red]{int(digi_prof_val):,}[/]"
            elif digi_prof_val < 700:
                digi_profit = f"[bold red]+{int(digi_prof_val):,}[/]"
            else:
                digi_profit = f"[bold green]+{int(digi_prof_val):,}[/]"

            raw_digi_comm = (
                str(rec.get("Digi Effective Commision", "10.00%")).replace("%", "") + "%"
            )
            if "8" in raw_digi_comm:
                digi_comm = f"[bold yellow]{raw_digi_comm}[/]"
            else:
                digi_comm = f"[blue]{raw_digi_comm}[/]"
        else:
            digi_p = "SKIP"
            digi_profit = "0"
            digi_comm = str(rec.get("Digi Effective Commision", "10.00%")).replace("%", "") + "%"

        table.add_row(
            sno,
            short_name,
            real_cost_str,
            alfa_p,
            alfa_profit,
            digi_p,
            digi_comm,
            digi_profit,
        )

    console.print()
    console.print(table)
    console.print(
        "[dim]LEGEND:[/dim] "
        "[bold red]RED[/]: Safe Fallback (Market Below Floor) / Thin Margin (< Rs. 700) | "
        "[bold yellow]YELLOW[/]: Capped Sweet-Spot / 8% Bank Switch | "
        "[bold green]GREEN[/]: Optimal Win"
    )
    console.print()


async def run_pipeline(
    input_path: Path,
    output_path: Path,
    concurrency: int = 3,
    verbose: bool = True,
) -> pd.DataFrame:
    """Run dynamic repricing pipeline on an input CSV and export results to output CSV.

    Features:
    - Micro-staggered launch (200ms) to prevent T=0 burst wave / WAF socket drops.
    - True bounded concurrency via asyncio.Semaphore(concurrency).
    - Atomic terminal audit rendering protected by asyncio.Lock.
    - 100% deterministic output row sorting preserving original CSV row sequence.

    Args:
        input_path: Path to the source CSV file.
        output_path: Path where repriced CSV should be written.
        concurrency: Max simultaneous product search requests (default: 3).
        verbose: Print visual terminal audit cards if True.

    Returns:
        Processed DataFrame with repriced data.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found at: {input_path}")

    df = pd.read_csv(input_path)
    start_time = time.perf_counter()

    supabase_client = SupabaseClient()
    if supabase_client.is_configured:
        await InMemoryRegistry.load_from_db(supabase_client)

    if verbose:
        render_start_banner(
            input_path=input_path,
            output_path=output_path,
            total_items=len(df),
            concurrency=concurrency,
        )

    semaphore = asyncio.Semaphore(concurrency)
    render_lock = asyncio.Lock()
    tasks: list[asyncio.Task[dict[str, Any]]] = []

    async with AsyncSession(impersonate="chrome120") as session:
        for idx, row in df.iterrows():
            product = parse_product_input(idx, row)
            task = asyncio.create_task(
                _process_item_worker(
                    idx=int(idx),
                    product=product,
                    session=session,
                    semaphore=semaphore,
                    render_lock=render_lock,
                    verbose=verbose,
                )
            )
            tasks.append(task)
            if idx < len(df) - 1:
                # Micro-stagger launch by 400ms to eliminate burst wave against WAF
                await asyncio.sleep(0.4)

        raw_records = await asyncio.gather(*tasks)

    # Guarantee deterministic 1:1 original CSV row sorting
    raw_records.sort(key=lambda r: int(r.get("_original_idx", 0)))
    records: list[dict[str, Any]] = []
    for r in raw_records:
        r.pop("_original_idx", None)
        records.append(r)

    out_df = pd.DataFrame(records)

    price_int_cols = [
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
    for col in price_int_cols:
        if col in out_df.columns:
            out_df[col] = out_df[col].apply(format_export_price)

    out_df.to_csv(output_path, index=False)

    if supabase_client.is_configured and default_learner.buffer_size > 0:
        flushed_count = await default_learner.flush_observations(supabase_client)
        if verbose and flushed_count > 0:
            console.print(
                f"  [bold cyan]☁️  [Supabase Memory][/] Synchronized {flushed_count} new market observations to cloud registry."
            )

    if verbose and records:
        render_summary_table(records)

    elapsed = time.perf_counter() - start_time
    if verbose:
        render_finish_banner(
            output_path=output_path,
            total_processed=len(records),
            elapsed_seconds=elapsed,
        )

    return out_df
