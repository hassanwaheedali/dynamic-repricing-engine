import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import json
import time

import pandas as pd
from curl_cffi.requests import AsyncSession
from rich.console import Console
from rich.table import Table

from pricing_engine.matcher import (
    extract_search_query_and_model,
    generate_search_patterns,
)
from pricing_engine.scraper import scrape_alfamall, scrape_digimall

console = Console(width=120)

async def audit_single_product(session: AsyncSession, row: pd.Series, idx: int, total: int, sem: asyncio.Semaphore) -> dict:
    name = row["Name"]
    brand = row["Brands"]
    cat = row["category"]

    clean_q, target_model = extract_search_query_and_model(name, brand=brand)
    patterns = generate_search_patterns(name, brand=brand)

    async with sem:
        try:
            alfa_res = await scrape_alfamall(session, patterns, target_model, brand=brand, timeout=8.0, max_retries=2)
        except Exception:
            alfa_res = None

        try:
            digi_res = await scrape_digimall(session, patterns, target_model, brand=brand, timeout=8.0, max_retries=2)
        except Exception:
            digi_res = None

    alfa_exact = len(alfa_res.offers) if alfa_res else 0
    alfa_base = len(alfa_res.base_offers) if alfa_res else 0
    alfa_mod = alfa_res.active_modifier_fallback if alfa_res else None

    digi_exact = len(digi_res.offers) if digi_res else 0
    digi_base = len(digi_res.base_offers) if digi_res else 0
    digi_mod = digi_res.active_modifier_fallback if digi_res else None

    # Print compact progress line
    console.print(
        f"[dim]{idx+1:03d}/{total:03d}[/] "
        f"[{'cyan' if cat == 'AIR_CONDITIONER' else 'green' if cat == 'REFRIGERATOR' else 'yellow'}]{cat[:14]:14s}[/] "
        f"[bold white]{target_model[:18]:18s}[/] | "
        f"Alfa: [green]{alfa_exact} ex[/], [dim]{alfa_base} bs[/]"
        f"{f' ({alfa_mod})' if alfa_mod else ''} | "
        f"Digi: [green]{digi_exact} ex[/], [dim]{digi_base} bs[/]"
        f"{f' ({digi_mod})' if digi_mod else ''}"
    )

    return {
        "index": idx + 1,
        "name": name,
        "brand": brand,
        "category": cat,
        "target_model": target_model,
        "alfa": {
            "status": alfa_res.status_code if alfa_res else None,
            "exact_count": alfa_exact,
            "base_count": alfa_base,
            "fallback_modifier": alfa_mod,
            "executed_queries": alfa_res.executed_queries if alfa_res else [],
            "top_offers": [{"price": o.price, "title": o.raw_title, "vendor": o.vendor_name} for o in (alfa_res.offers[:2] if alfa_res else [])],
        },
        "digi": {
            "status": digi_res.status_code if digi_res else None,
            "exact_count": digi_exact,
            "base_count": digi_base,
            "fallback_modifier": digi_mod,
            "executed_queries": digi_res.executed_queries if digi_res else [],
            "top_offers": [{"price": o.price, "title": o.raw_title, "vendor": o.vendor_name} for o in (digi_res.offers[:2] if digi_res else [])],
        }
    }

async def run_audit():
    df = pd.read_csv("tests/fixtures/selected_100_stress_products.csv")
    total = len(df)
    console.print(f"\n[bold green]STARTING LIVE 100-PRODUCT MARKETPLACE AUDIT[/] ({total} products loaded)\n")

    sem = asyncio.Semaphore(4)
    results = []

    start_time = time.time()
    async with AsyncSession(impersonate="chrome120") as session:
        tasks = [
            audit_single_product(session, row, idx, total, sem)
            for idx, row in df.iterrows()
        ]
        results = await asyncio.gather(*tasks)

    elapsed = time.time() - start_time
    console.print(f"\n[bold green]AUDIT COMPLETED IN {elapsed:.1f} SECONDS[/]\n")

    # Save detailed JSON report
    out_dir = Path("data/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "live_100_audit_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    console.print(f"Detailed JSON results saved to: [bold white]{json_path}[/]")

    # Category Summary Table
    cat_summary = {}
    for r in results:
        c = r["category"]
        if c not in cat_summary:
            cat_summary[c] = {"total": 0, "alfa_exact": 0, "digi_exact": 0, "any_found": 0, "fallback_count": 0}
        cat_summary[c]["total"] += 1
        alfa_hit = r["alfa"]["exact_count"] > 0
        digi_hit = r["digi"]["exact_count"] > 0
        if alfa_hit:
            cat_summary[c]["alfa_exact"] += 1
        if digi_hit:
            cat_summary[c]["digi_exact"] += 1
        if alfa_hit or digi_hit or r["alfa"]["base_count"] > 0 or r["digi"]["base_count"] > 0:
            cat_summary[c]["any_found"] += 1
        if r["alfa"]["fallback_modifier"] or r["digi"]["fallback_modifier"]:
            cat_summary[c]["fallback_count"] += 1

    tbl = Table(title="Live Marketplace Audit Summary by Category", show_header=True, header_style="bold cyan")
    tbl.add_column("Category", style="white", width=20)
    tbl.add_column("Tested Items", justify="right", width=14)
    tbl.add_column("Market Presence", justify="right", width=16)
    tbl.add_column("AlfaMall Hits", justify="right", width=14)
    tbl.add_column("DigiMall Hits", justify="right", width=14)
    tbl.add_column("Fallback Modifiers", justify="right", width=18)

    for c, s in sorted(cat_summary.items(), key=lambda x: x[1]["total"], reverse=True):
        tbl.add_row(
            c,
            str(s["total"]),
            f"{s['any_found']}/{s['total']} ({s['any_found']/s['total']*100:.0f}%)",
            str(s["alfa_exact"]),
            str(s["digi_exact"]),
            str(s["fallback_count"])
        )
    console.print(tbl)

if __name__ == "__main__":
    asyncio.run(run_audit())
