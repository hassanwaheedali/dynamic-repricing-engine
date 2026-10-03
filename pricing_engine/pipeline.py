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
from pricing_engine.exporter import export_results
from pricing_engine.ingestion import INVALID_BRAND_VALUES
from pricing_engine.learner import AutonomousLearner
from pricing_engine.matcher import (
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    referee_match,
)
from pricing_engine.models import (
    STATUS_SERVER_DOWN,
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

console = Console(legacy_windows=False, width=max(105, Console().width or 105))
logger = logging.getLogger(__name__)

ZONE_PRICE: float = 70.0
DIVISOR: float = 5000.0


def _format_dupe_tag(count: int) -> str:
    """Format compact dupe tag only when duplicate listings were collapsed."""
    dupes = count - 1
    if dupes <= 0:
        return ""
    word = "dupe" if dupes == 1 else "dupes"
    return f" [dim][{dupes} {word}][/]"


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
        res.status == STATUS_SERVER_DOWN
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


def resolve_shipping_estimate(product: ProductInput) -> float:
    """Resolve shipping estimate from CSV if provided, or compute from volumetric weight."""
    csv_shipping = product.raw_row.get("Shipping Estimate")
    if pd.notna(csv_shipping) and _safe_float(csv_shipping) > 0:
        return round(_safe_float(csv_shipping), 2)
    vol_weight = calculate_volumetric_weight(
        product.length, product.width, product.height, divisor=DIVISOR
    )
    return calculate_shipping_estimate(vol_weight, rate_per_kg=ZONE_PRICE)



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


def parse_product_input(idx: int, row: pd.Series) -> ProductInput:
    """Parse and sanitize a raw CSV row into a strongly typed ProductInput.

    Args:
        idx: 0-indexed row number from DataFrame iteration.
        row: Pandas Series representing the product row.

    Returns:
        Structured ProductInput instance.
    """
    sno = _extract_sno(row, idx + 1)
    raw_brand = row.get("Brand")
    brand = str(raw_brand).strip() if (raw_brand is not None and not pd.isna(raw_brand)) else ""
    raw_name = row.get("Name ")
    if raw_name is None or pd.isna(raw_name):
        raw_name = row.get("Name", "Product")
    name = str(raw_name).strip()

    if not brand or brand.lower() in INVALID_BRAND_VALUES:
        raise ValueError(
            f"Row {idx + 1} ('{name}'): 'Brand' column is empty or invalid ('{brand or raw_brand}'). "
            "Please enter a valid brand name in the 'Brand' column for this product."
        )

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


def determine_platform_status(
    price_val: Any,
    min_comp_price: Any = None,
    reason: str = "",
    alert: str = "",
) -> str:
    """Determine outcome status badge string: e.g. 'WIN (-500)', 'SOLO', 'FALLBACK', 'CAPPED', 'SERVER_DOWN'.

    Strict Market-Wide Winning Rule:
    A price is marked as WIN if and only if:
    1. diff = (min_comp_price - price_val) > 0 (our price beats the absolute lowest competitor in the entire mall).
    2. No sub-floor competitors were dropped who are selling below our floor (i.e. 'sub-floor' not in reason).
    """
    reason_lower = str(reason).lower()
    alert_str = str(alert)

    if (
        "server is down" in reason_lower
        or "unreachable" in reason_lower
        or alert_str == "SERVER_DOWN"
    ):
        return "SERVER_DOWN"

    if alert_str == "SAFE_FALLBACK" or "safe fallback" in reason_lower:
        return "FALLBACK"

    if pd.notna(price_val) and price_val is not None and str(price_val).strip() != "":
        if (
            min_comp_price is not None
            and pd.notna(min_comp_price)
            and str(min_comp_price).strip() != ""
        ):
            try:
                min_p = float(min_comp_price)
                f_p = float(price_val)
                diff = int(round(min_p - f_p))
                if diff > 0 and "sub-floor" not in reason_lower:
                    if "capped" in reason_lower:
                        return f"CAPPED (-{diff:,})"
                    return f"WIN (-{diff:,})"
            except (ValueError, TypeError):
                pass

        if "monopoly" in reason_lower or "no competitors" in reason_lower:
            return "SOLO"
        if "capped" in reason_lower:
            return "CAPPED"
        return ""

    return ""


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
    # Guarantee S.NO is the first column in output
    out_record: dict[str, Any] = {"S.NO": product.sno}

    # Copy remaining raw_row fields, excluding any S.NO aliases
    sno_aliases = {"S.NO", "S.No", "S. No", "S.No.", "SNO", "sno", "Serial No", "Serial Number"}
    for k, v in product.raw_row.items():
        if k not in sno_aliases:
            out_record[k] = v

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

    alfa_alert = determine_risk_alert(alfa_res)
    digi_alert = determine_risk_alert(digi_res)

    out_record["Final Price Alfa"] = alfa_res.final_price
    out_record["Alfa Status"] = determine_platform_status(
        alfa_res.final_price, alfa_res.min_price, alfa_res.reason, alfa_alert
    )
    out_record["Final Price Digi"] = digi_res.final_price
    out_record["Digi Status"] = determine_platform_status(
        digi_res.final_price, digi_res.min_price, digi_res.reason, digi_alert
    )
    out_record["Alfa Real Profit"] = alfa_res.real_profit
    out_record["Digi Real Profit"] = digi_res.real_profit
    out_record["Alfa Reason"] = alfa_res.reason
    out_record["Digi Reason"] = digi_res.reason
    out_record["Alfa Risk Alert"] = alfa_alert
    out_record["Digi Risk Alert"] = digi_alert

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
    shipping = resolve_shipping_estimate(product)

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
    xlsx_path: Path | None = None,
) -> None:
    """Render clean executive completion banner."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", width=22)
    grid.add_column(style="white")
    grid.add_row("Execution Status:", "[bold green]Successfully Completed[/]")
    grid.add_row("Total Repriced:", f"{total_processed} catalog items")
    grid.add_row("Portal Upload CSV:", f"[bold white]{output_path.resolve()}[/]")
    if xlsx_path:
        grid.add_row("Dynamic Excel (.xlsx):", f"[bold green]{xlsx_path.resolve()}[/]")
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


def _render_platform_offers_to_table(
    tbl: Table,
    platform_tag: str,
    offers: list[ScrapedOffer] | ScrapeResult,
    res: PlatformPricingResult,
    floor_price: float,
    floor_label: str,
    empty_label: str,
    target_undercut_label: str,
) -> None:
    """Render verified scraped offers and drop reasons for a platform into the summary table."""
    is_down = res.status == STATUS_SERVER_DOWN or (
        isinstance(offers, ScrapeResult) and not offers.is_success
    )
    if is_down:
        tbl.add_row(
            platform_tag,
            "[bold red]Connection Failed[/]",
            "[dim]N/A[/]",
            "[bold red]Remote Portal Down / Unreachable (Skipped)[/]",
        )
        return

    if not offers:
        tbl.add_row(
            platform_tag,
            "[dim]No sellers found[/]",
            "[dim]0 scraped[/]",
            empty_label,
        )
        return

    active_offers = [o for o in offers if not o.is_sold_out]
    sorted_offers = sorted(active_offers, key=lambda x: x.price)
    sold_out = [o for o in offers if o.is_sold_out]

    dropped = [o for o in sorted_offers if o.price <= floor_price]
    viable = [o for o in sorted_offers if o.price > floor_price]

    if viable:
        # 1. Dropped sub-floor offers (first 2 + rollup + immediate predecessor before target)
        if len(dropped) > 3:
            for o in dropped[:2]:
                dupe_tag = _format_dupe_tag(o.duplicate_count)
                tbl.add_row(
                    platform_tag,
                    o.vendor_name[:21],
                    f"Rs. {o.price:,.0f}",
                    f"[red]Dropped (< {floor_label})[/]{dupe_tag}",
                )
            rem_dropped = len(dropped) - 3
            tbl.add_row(
                platform_tag,
                f"[dim]... +{rem_dropped} dropped[/]",
                f"[dim]Rs. {dropped[2].price:,.0f}+[/]",
                f"[dim red]Sub-floor offers (up to Rs. {floor_price - 1:,.0f})[/]",
            )
            # Explicitly render the closest sub-floor seller right before target undercut
            closest_dropped = dropped[-1]
            c_dupe = _format_dupe_tag(closest_dropped.duplicate_count)
            tbl.add_row(
                platform_tag,
                closest_dropped.vendor_name[:21],
                f"Rs. {closest_dropped.price:,.0f}",
                f"[red]Dropped (< {floor_label})[/]{c_dupe}",
            )
        else:
            for o in dropped:
                dupe_tag = _format_dupe_tag(o.duplicate_count)
                tbl.add_row(
                    platform_tag,
                    o.vendor_name[:21],
                    f"Rs. {o.price:,.0f}",
                    f"[red]Dropped (< {floor_label})[/]{dupe_tag}",
                )

        # 2. Target Undercut - ALWAYS explicitly rendered
        lowest_viable = viable[0]
        lv_dupe = _format_dupe_tag(lowest_viable.duplicate_count)
        lv_title = f"\n[dim white]-> {lowest_viable.raw_title[:65]}[/]" if lowest_viable.raw_title else ""
        tbl.add_row(
            platform_tag,
            lowest_viable.vendor_name[:21],
            f"Rs. {lowest_viable.price:,.0f}",
            f"{target_undercut_label}{lv_dupe}{lv_title}",
        )

        # 3. Next 2-3 viable competitors
        for o in viable[1:4]:
            v_dupe = _format_dupe_tag(o.duplicate_count)
            v_title = f"\n[dim white]-> {o.raw_title[:65]}[/]" if o.raw_title else ""
            tbl.add_row(
                platform_tag,
                o.vendor_name[:21],
                f"Rs. {o.price:,.0f}",
                f"[dim]Viable Competitor[/]{v_dupe}{v_title}",
            )

        # 4. Rollup higher offers with true max ceiling
        if len(viable) > 4:
            rem_viable = len(viable) - 4
            min_rem = viable[4].price
            max_rem = viable[-1].price
            tbl.add_row(
                platform_tag,
                f"[dim]... +{rem_viable} more[/]",
                f"[dim]Rs. {min_rem:,.0f}+[/]",
                f"[dim]Higher offers (up to Rs. {max_rem:,.0f})[/]",
            )
    else:
        # All scraped competitors are selling below floor
        for o in dropped[:3]:
            dupe_tag = _format_dupe_tag(o.duplicate_count)
            tbl.add_row(
                platform_tag,
                o.vendor_name[:21],
                f"Rs. {o.price:,.0f}",
                f"[red]Dropped (< {floor_label})[/]{dupe_tag}",
            )
        if len(dropped) > 3:
            rem_dropped = len(dropped) - 3
            min_rem = dropped[3].price
            max_rem = dropped[-1].price
            tbl.add_row(
                platform_tag,
                f"[dim]... +{rem_dropped} dropped[/]",
                f"[dim]Rs. {min_rem:,.0f}+[/]",
                f"[dim red]All sub-floor (up to Rs. {max_rem:,.0f})[/]",
            )

    for s in sold_out[:2]:
        tbl.add_row(
            platform_tag,
            s.vendor_name[:21],
            f"Rs. {s.price:,.0f}",
            "[dim red]Out of Stock (Ignored)[/]",
        )


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
    tbl.add_column("Seller / Vendor", style="bold white", width=21)
    tbl.add_column("Scraped Price", justify="right", style="bold yellow", width=13)
    tbl.add_column("Status", ratio=1)

    # 1. AlfaMall Scraped Competitors
    _render_platform_offers_to_table(
        tbl=tbl,
        platform_tag="[bold #2c4699]AlfaMall[/]",
        offers=alfa_offers,
        res=alfa_res,
        floor_price=floors.floor_alfa,
        floor_label=f"Floor Rs. {floors.floor_alfa:,.0f}",
        empty_label="[bold cyan]Monopoly Pricing (+Rs. 4,000 margin)[/]",
        target_undercut_label="[bold green]Target Undercut (Lowest Viable)[/]",
    )

    # 2. DigiMall Scraped Competitors
    digi_comm_note = "8% Viable" if digi_res.effective_comm == "8.00%" else "10% Viable"
    _render_platform_offers_to_table(
        tbl=tbl,
        platform_tag="[bold #229693]DigiMall[/]",
        offers=digi_offers,
        res=digi_res,
        floor_price=floors.floor_digi_8,
        floor_label=f"8% Floor Rs. {floors.floor_digi_8:,.0f}",
        empty_label="[bold cyan]Baseline Undercut (+2% margin)[/]",
        target_undercut_label=f"[bold green]Target Undercut ({digi_comm_note})[/]",
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
    is_alfa_down = alfa_res.status == STATUS_SERVER_DOWN or (
        isinstance(alfa_offers, ScrapeResult) and not alfa_offers.is_success
    )
    is_digi_down = digi_res.status == STATUS_SERVER_DOWN or (
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
    if alfa_res.status == STATUS_SERVER_DOWN:
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

    if digi_res.status == STATUS_SERVER_DOWN:
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
    if alfa_res.status == STATUS_SERVER_DOWN:
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

    if digi_res.status == STATUS_SERVER_DOWN:
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

    # 1b. Search Query & Waterfall Fallback Telemetry
    def _format_search_telemetry(
        p_name: str, p_color: str, offers_res: list[ScrapedOffer] | ScrapeResult
    ) -> str:
        if isinstance(offers_res, ScrapeResult) and offers_res.active_modifier_fallback:
            mod = offers_res.active_modifier_fallback
            count = len(offers_res.offers)
            return (
                f"[{p_color}]{p_name}:[/] [bold yellow]⚠️ MODIFIER '{mod}' OMITTED BY MARKET[/] -> "
                f"[bold green]Matched {count} base model offer{'s' if count != 1 else ''} (DO CROSS-CHECK)[/]"
            )
        if isinstance(offers_res, ScrapeResult) and offers_res.executed_queries:
            q_list = offers_res.executed_queries
            t_sum = offers_res.tier_summary
            if t_sum.get("tier_1", 0) > 0:
                q_disp = q_list[0] if q_list else target_model
                count = t_sum["tier_1"]
                return (
                    f"[{p_color}]{p_name}:[/] [bold white]'{q_disp}'[/] "
                    f"[green](Exact Query -> {count} verified offer{'s' if count > 1 else ''})[/]"
                )
            elif t_sum.get("tier_2", 0) > 0:
                t1_q = q_list[0] if q_list else ""
                t2_q = q_list[1] if len(q_list) > 1 else (q_list[0] if q_list else target_model)
                count = t_sum["tier_2"]
                return (
                    f"[{p_color}]{p_name}:[/] [dim]'{t1_q}' (0 found)[/] -> "
                    f"[bold yellow]Fallback Stem:[/] [bold white]'{t2_q}'[/] "
                    f"[green]({count} offer{'s' if count > 1 else ''} strictly verified)[/]"
                )
            elif t_sum.get("tier_3", 0) > 0:
                tier3_q = q_list[-1] if q_list else target_model
                count = t_sum["tier_3"]
                return (
                    f"[{p_color}]{p_name}:[/] [dim]Tiers 1 & 2 (0 found)[/] -> "
                    f"[bold yellow]Permutation Fallback:[/] [bold white]'{tier3_q}'[/] "
                    f"[green]({count} offer{'s' if count > 1 else ''} verified)[/]"
                )
            else:
                tried_str = ", ".join(f"'{q}'" for q in q_list[:2])
                return (
                    f"[{p_color}]{p_name}:[/] [dim]Queried {tried_str} (0 offers found in market)[/] -> "
                    f"[bold cyan]Monopoly Price Applied[/]"
                )
        return f"[{p_color}]{p_name}:[/] [dim]Target: '{target_model}'[/]"

    query_grid = Table.grid(padding=(0, 2), expand=True)
    query_grid.add_column(style="bold cyan", width=16)
    query_grid.add_column(style="white", ratio=1)
    query_grid.add_row(
        "Search Audit:",
        _format_search_telemetry("AlfaMall", "#2c4699", alfa_offers),
    )
    query_grid.add_row(
        "",
        _format_search_telemetry("DigiMall", "#229693", digi_offers),
    )

    content = Table.grid(padding=(1, 0), expand=True)
    content.add_row(specs)
    content.add_row(query_grid)
    content.add_row(sellers_tbl)
    content.add_row(plat_tbl)

    active_fallback_mod = (
        alfa_offers.active_modifier_fallback
        if isinstance(alfa_offers, ScrapeResult) and alfa_offers.active_modifier_fallback
        else (
            digi_offers.active_modifier_fallback
            if isinstance(digi_offers, ScrapeResult) and digi_offers.active_modifier_fallback
            else None
        )
    )
    if active_fallback_mod:
        warning_banner = Panel(
            f"[bold yellow]⚠️  NOTICE (DO CROSS-CHECK):[/] Target specified [bold cyan]'{active_fallback_mod}'[/], but marketplace listings omitted it. "
            f"Repriced against verified [bold green]base model[/] listings.",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        content.add_row(warning_banner)

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

    shipping = resolve_shipping_estimate(product)

    cost_base = calculate_cost_base(product.net_price, shipping)
    floors = calculate_floors(cost_base, min_profit=500.0)
    baseline_calc = calculate_baseline(cost_base, target_profit=product.profit)

    async with semaphore:
        alfa_task = scrape_alfamall(
            session,
            patterns,
            target_model,
            floor_price=floors.floor_alfa,
            brand=product.brand,
            target_desc=product.name,
        )
        digi_task = scrape_digimall(
            session,
            patterns,
            target_model,
            floor_price=floors.floor_digi_8,
            brand=product.brand,
            target_desc=product.name,
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


def _format_summary_price(
    price_val: Any,
    min_comp_price: Any = None,
    reason: str = "",
    alert: str = "",
    brand_color: str = "white",
) -> str:
    """Format product price string with inline market winning badges for terminal executive summary table."""
    status = determine_platform_status(price_val, min_comp_price, reason, alert)
    if status == "SERVER_DOWN":
        return "[bold red]DOWN[/]"
    if pd.isna(price_val) or price_val is None or str(price_val).strip() == "":
        return "SKIP"

    raw_p = f"{int(float(price_val)):,}"
    price_str = f"[{brand_color}]{raw_p}[/]"
    is_modifier_fallback = "fallback model" in reason.lower()
    mod_tag = " [bold yellow]CROSS-CHECK[/]" if is_modifier_fallback else ""

    if status == "FALLBACK":
        return f"[bold red]{raw_p}[/] [red]FALLBACK[/]{mod_tag}"
    if status.startswith("WIN"):
        return f"{price_str} [bold green]{status}[/]{mod_tag}"
    if status == "SOLO":
        return f"{price_str} [dim]SOLO[/]{mod_tag}"
    if status.startswith("CAPPED"):
        return f"{price_str} [bold yellow]{status}[/]{mod_tag}"
    return f"{price_str}{mod_tag}"


def _format_summary_profit(
    price_val: Any,
    profit_val: Any,
    reason: str,
    alert: str,
) -> str:
    """Format profit string for terminal executive summary table."""
    reason_lower = reason.lower()
    if (
        "server is down" in reason_lower
        or "unreachable" in reason_lower
        or alert == "SERVER_DOWN"
    ):
        return "[dim red]0[/]"
    if pd.notna(price_val) and price_val is not None and str(price_val).strip() != "":
        p_val = float(profit_val or 0)
        if p_val <= 0:
            return f"[bold white on red]{int(p_val):,}[/]"
        if p_val < 700:
            return f"[bold red]+{int(p_val):,}[/]"
        return f"[bold green]+{int(p_val):,}[/]"
    return "0"


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
    table.add_column("Model / Product", style="bold white", no_wrap=True)
    table.add_column("Cost Base", justify="right", style="dim")
    table.add_column("Alfa Price", justify="right", no_wrap=True)
    table.add_column("Alfa Net", justify="right")
    table.add_column("Digi Price", justify="right", no_wrap=True)
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
        alfa_min_val = rec.get("Minimum Price Alfa")
        alfa_reason = str(rec.get("Alfa Reason", ""))
        alfa_alert = str(rec.get("Alfa Risk Alert", ""))
        alfa_p = _format_summary_price(
            alfa_p_val,
            min_comp_price=alfa_min_val,
            reason=alfa_reason,
            alert=alfa_alert,
            brand_color="bold #2c4699",
        )
        alfa_profit = _format_summary_profit(
            alfa_p_val, rec.get("Alfa Real Profit", 0), alfa_reason, alfa_alert
        )

        digi_p_val = rec.get("Final Price Digi")
        digi_min_val = rec.get("Minimum Price Digi")
        digi_reason = str(rec.get("Digi Reason", ""))
        digi_alert = str(rec.get("Digi Risk Alert", ""))
        digi_p = _format_summary_price(
            digi_p_val,
            min_comp_price=digi_min_val,
            reason=digi_reason,
            alert=digi_alert,
            brand_color="bold #229693",
        )
        digi_profit = _format_summary_profit(
            digi_p_val, rec.get("Digi Real Profit", 0), digi_reason, digi_alert
        )

        if (
            "server is down" in digi_reason.lower()
            or "unreachable" in digi_reason.lower()
            or digi_alert == "SERVER_DOWN"
        ):
            digi_comm = "[dim red]N/A[/]"
        elif pd.notna(digi_p_val) and digi_p_val is not None and str(digi_p_val).strip() != "":
            raw_digi_comm = (
                str(rec.get("Digi Effective Commision", "10.00%")).replace("%", "") + "%"
            )
            if "8" in raw_digi_comm:
                digi_comm = f"[bold yellow]{raw_digi_comm}[/]"
            else:
                digi_comm = f"[blue]{raw_digi_comm}[/]"
        else:
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
        "[bold green]GREEN[/]: Optimal Win | "
        "[bold yellow]CROSS-CHECK[/]: Target modifier omitted in listings (priced against base model)"
    )
    console.print()


async def run_pipeline(
    input_path: str | Path,
    output_path: str | Path | None = None,
    concurrency: int = 3,
    verbose: bool = True,
    use_structured_export: bool = False,
    export_dir: str | Path = "data/outputs",
) -> pd.DataFrame:
    """Run dynamic repricing pipeline on an input CSV and export results to output CSV.

    Features:
    - Micro-staggered launch (200ms) to prevent T=0 burst wave / WAF socket drops.
    - True bounded concurrency via asyncio.Semaphore(concurrency).
    - Atomic terminal audit rendering protected by asyncio.Lock.
    - 100% deterministic output row sorting preserving original CSV row sequence.
    - Optional structured export to data/outputs/ with timestamp and latest copy.

    Args:
        input_path: Path to the source CSV file.
        output_path: Optional path where repriced CSV should be written.
        concurrency: Max simultaneous product search requests (default: 3).
        verbose: Print visual terminal audit cards if True.
        use_structured_export: If True or output_path is None, exports structured files.
        export_dir: Directory where structured outputs are saved (default: data/outputs).

    Returns:
        Processed DataFrame with repriced data.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found at: {input_path}")

    df = pd.read_csv(input_path)
    # Strip whitespace from column headers, preserving legacy 'Name ' key if present
    has_legacy_name_space = "Name " in df.columns
    df.columns = [
        "Name " if c == "Name " and has_legacy_name_space else str(c).strip()
        for c in df.columns
    ]
    start_time = time.perf_counter()

    supabase_client = SupabaseClient()
    if supabase_client.is_configured:
        await InMemoryRegistry.load_from_db(supabase_client)

    banner_output_path = (
        Path(output_path)
        if output_path is not None
        else Path(export_dir) / f"{input_path.stem}_repriced_latest.csv"
    )

    if verbose:
        render_start_banner(
            input_path=input_path,
            output_path=banner_output_path,
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

    effective_finish_path: Path
    effective_xlsx_path: Path | None = None
    if output_path is not None:
        target_out = Path(output_path)
        if target_out.parent and not target_out.parent.exists():
            target_out.parent.mkdir(parents=True, exist_ok=True)
        out_df.to_csv(target_out, index=False)
        effective_finish_path = target_out
    else:
        manifest = export_results(
            df=out_df,
            source_filename=input_path,
            output_dir=export_dir,
            render_panel=False,
        )
        effective_finish_path = manifest.timestamped_path
        effective_xlsx_path = manifest.latest_xlsx_path

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
            output_path=effective_finish_path,
            total_processed=len(records),
            elapsed_seconds=elapsed,
            xlsx_path=effective_xlsx_path,
        )

    return out_df
