# ruff: noqa: E402
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from curl_cffi.requests import AsyncSession

from pricing_engine.calculator import (
    calculate_cost_base,
    calculate_floors,
    calculate_shipping_estimate,
    calculate_volumetric_weight,
)
from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.matcher import (
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    referee_match,
)
from pricing_engine.models import ProductInput
from pricing_engine.scraper import (
    _raw_items_cache,
    scrape_alfamall,
    scrape_digimall,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PRODUCTS_TO_TEST: list[dict[str, Any]] = [
    {
        "sno": 1,
        "brand": "Gree",
        "name": "GREE SPLIT AC 18AITH21B-T3",
        "category": "AIR_CONDITIONER",
        "net_price": 183000.0,
        "length": 108.0,
        "width": 33.0,
        "height": 25.0,
        "profit": 500.0,
        "challenge": "Color embedded in SKU ('B' Black vs 'W' White). Must reject 18AITH21W (White) and 12/24AITH.",
    },
    {
        "sno": 2,
        "brand": "Gree",
        "name": "GREE SPLIT AC GS-18PITC12W-T3",
        "category": "AIR_CONDITIONER",
        "net_price": 153000.0,
        "length": 108.0,
        "width": 33.0,
        "height": 25.0,
        "profit": 500.0,
        "challenge": "Cool Only ('PITC') vs Heat & Cool ('PITH'). Must reject Heat & Cool listings to prevent mispricing.",
    },
    {
        "sno": 3,
        "brand": "Haier",
        "name": "Haier 150-826S6 GC Automatic Washing Machine",
        "category": "WASHING_MACHINE",
        "net_price": 76000.0,
        "length": 68.0,
        "width": 65.0,
        "height": 98.0,
        "profit": 500.0,
        "challenge": "Capacity 150 (15kg) vs 100/120 (10/12kg) + Soft feature 'GC' (Glass Cover/Door).",
    },
    {
        "sno": 4,
        "brand": "Haier",
        "name": "Haier HW 105-BD14376PGU1 Front Load Washing Machine",
        "category": "WASHING_MACHINE",
        "net_price": 170000.0,
        "length": 65.0,
        "width": 57.0,
        "height": 92.0,
        "profit": 500.0,
        "challenge": "Front Load ('HW') 10.5kg ('105') with complex alphanumeric SKU. Must reject top load / 100 models.",
    },
    {
        "sno": 5,
        "brand": "Dawlance",
        "name": "DMB 4467 SD MINI BAR",
        "category": "REFRIGERATOR",
        "net_price": 34000.0,
        "length": 52.0,
        "width": 50.0,
        "height": 85.0,
        "profit": 500.0,
        "challenge": "Brand prefix verification ('DMB-4467'), 'SD' Single Door, Mini Bar. Must collide with 'DD'.",
    },
    {
        "sno": 6,
        "brand": "Dawlance",
        "name": "9060 INVERTER GD",
        "category": "REFRIGERATOR",
        "net_price": 288000.0,
        "length": 90.0,
        "width": 70.0,
        "height": 180.0,
        "profit": 500.0,
        "challenge": "Pure numeric model '9060', Inverter, 'GD' Glass Door. Must strictly collide against '9060 INOX'.",
    },
    {
        "sno": 7,
        "brand": "Dawlance",
        "name": "Dawlance DWT-1166 X ADS+ 9KG Top Load Automatic Washing Machine",
        "category": "WASHING_MACHINE",
        "net_price": 85000.0,
        "length": 60.0,
        "width": 60.0,
        "height": 100.0,
        "profit": 500.0,
        "challenge": "Auto Dose ('ADS+') with special punctuation '+', 9KG, model DWT-1166 vs 1165.",
    },
    {
        "sno": 8,
        "brand": "TCL",
        "name": "TCL 40 Inch QLED Smart TV 40S59K Full HD Google TV",
        "category": "LED_TV",
        "net_price": 65000.0,
        "length": 95.0,
        "width": 15.0,
        "height": 60.0,
        "profit": 500.0,
        "challenge": "Screen size '40 Inch' embedded in model '40S59K', QLED vs standard LED. Must reject 32/43 inch.",
    },
    {
        "sno": 9,
        "brand": "Gree",
        "name": "Gree 2 Ton Zeno Series GS-24ZITH1/2-T3 Inverter Heat And Cool Split Air Conditioner-White",
        "category": "AIR_CONDITIONER",
        "net_price": 222000.0,
        "length": 115.0,
        "width": 35.0,
        "height": 28.0,
        "profit": 500.0,
        "challenge": "Slash-separated series 'GS-24ZITH1/2', 2 Ton capacity, T3 tropical compressor, Heat & Cool.",
    },
    {
        "sno": 10,
        "brand": "Haier",
        "name": "Haier HRF-216 EBD 8 Cu Ft Metallic Grey E-Star Non-Inverter Refrigerator",
        "category": "REFRIGERATOR",
        "net_price": 52000.0,
        "length": 60.0,
        "width": 60.0,
        "height": 150.0,
        "profit": 500.0,
        "challenge": "Model 216 with prefix 'HRF-', 8 Cu Ft, Non-Inverter vs Inverter, Metallic Grey color.",
    },
]


def audit_raw_items_against_matcher(
    raw_items: list[dict[str, Any]], target_model: str, brand: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Audit every single raw API item against the referee matcher."""
    matched = []
    rejected = []
    seen = set()

    for item in raw_items:
        title = str(item.get("title", ""))
        variant = item.get("variant_detail", {})
        price_str = variant.get("discounted_price") or variant.get("original_price") or "0"
        try:
            price = float(str(price_str).replace(",", "").strip())
        except ValueError:
            price = 0.0

        vendor = (item.get("vendor") or {}).get("name") or "Unknown Vendor"
        sold_out = bool(item.get("sold_out", False))

        key = (title, price, vendor)
        if key in seen:
            continue
        seen.add(key)

        decision = referee_match(target_model, title, brand=brand)
        item_diag = {
            "title": title,
            "vendor": vendor,
            "price": price,
            "sold_out": sold_out,
            "decision": {
                "is_match": decision.is_match,
                "is_base_match": decision.is_base_match,
                "reason": decision.reason,
                "missing_modifier": decision.missing_modifier,
            },
        }

        if decision.is_match or decision.is_base_match:
            matched.append(item_diag)
        else:
            rejected.append(item_diag)

    return matched, rejected


async def run_single_product_test(session: AsyncSession, p_data: dict[str, Any]) -> dict[str, Any]:
    prod = ProductInput(
        sno=p_data["sno"],
        brand=p_data["brand"],
        name=p_data["name"],
        length=p_data["length"],
        width=p_data["width"],
        height=p_data["height"],
        profit=p_data.get("profit", 500.0),
        net_price=p_data["net_price"],
        raw_row=p_data,
    )

    query_str, target_model = extract_search_query_and_model(prod.name, brand=prod.brand)
    patterns = generate_search_patterns(prod.name, brand=prod.brand)
    slots = extract_product_slots(prod.name, brand=prod.brand)

    vol_wt = calculate_volumetric_weight(prod.length, prod.width, prod.height)
    shipping = calculate_shipping_estimate(vol_wt)
    cost_base = calculate_cost_base(prod.net_price, shipping)
    floors = calculate_floors(cost_base, min_profit=500.0)

    # Scrape both platforms
    alfa_task = scrape_alfamall(
        session, patterns, target_model, floor_price=floors.floor_alfa, brand=prod.brand
    )
    digi_task = scrape_digimall(
        session, patterns, target_model, floor_price=floors.floor_digi_8, brand=prod.brand
    )
    alfa_res, digi_res = await asyncio.gather(alfa_task, digi_task)

    # Evaluate pricing
    alfa_pricing = evaluate_alfa_pricing(floors, alfa_res)
    digi_pricing = evaluate_digi_pricing(floors, digi_res)

    # Collect raw items from scraper cache for audit
    alfa_raw_items = []
    for q in alfa_res.executed_queries:
        cache_key = ("alfamall", q.strip().upper())
        if cache_key in _raw_items_cache:
            alfa_raw_items.extend(_raw_items_cache[cache_key])

    digi_raw_items = []
    for q in digi_res.executed_queries:
        cache_key = ("digimall", q.strip().upper())
        if cache_key in _raw_items_cache:
            digi_raw_items.extend(_raw_items_cache[cache_key])

    alfa_matched, alfa_rejected = audit_raw_items_against_matcher(
        alfa_raw_items, target_model, prod.brand
    )
    digi_matched, digi_rejected = audit_raw_items_against_matcher(
        digi_raw_items, target_model, prod.brand
    )

    return {
        "product": p_data,
        "extracted_query": query_str,
        "target_model": target_model,
        "patterns": patterns,
        "slots": {
            "anchor": slots.anchor,
            "series": slots.series,
            "facets": {
                "capacity": slots.guarded_facets.capacity,
                "tub_series": slots.guarded_facets.tub_series,
                "color_family": slots.guarded_facets.color_family,
                "color_raw": slots.guarded_facets.color_raw,
                "door_finish": slots.guarded_facets.door_finish,
                "cool_only": slots.guarded_facets.cool_only,
                "heat_and_cool": slots.guarded_facets.heat_and_cool,
                "door_type": slots.guarded_facets.door_type,
                "is_inverter": slots.guarded_facets.is_inverter,
                "capabilities": list(slots.guarded_facets.capabilities),
            },
            "residuals": slots.residuals,
        },
        "shipping": shipping,
        "cost_base": cost_base,
        "floors": {
            "floor_alfa": floors.floor_alfa,
            "floor_digi_10": floors.floor_digi_10,
            "floor_digi_8": floors.floor_digi_8,
        },
        "alfa_audit": {
            "executed_queries": alfa_res.executed_queries,
            "matched_tier": alfa_res.matched_tier,
            "total_raw_scraped": len(alfa_raw_items),
            "matched_count": len(alfa_matched),
            "rejected_count": len(alfa_rejected),
            "matched_items": alfa_matched,
            "rejected_items": alfa_rejected,
            "pricing": {
                "min_comp": alfa_pricing.min_price,
                "final_price": alfa_pricing.final_price,
                "real_profit": alfa_pricing.real_profit,
                "status": alfa_pricing.status,
                "reason": alfa_pricing.reason,
                "dropped": alfa_pricing.dropped,
            },
        },
        "digi_audit": {
            "executed_queries": digi_res.executed_queries,
            "matched_tier": digi_res.matched_tier,
            "total_raw_scraped": len(digi_raw_items),
            "matched_count": len(digi_matched),
            "rejected_count": len(digi_rejected),
            "matched_items": digi_matched,
            "rejected_items": digi_rejected,
            "pricing": {
                "min_comp": digi_pricing.min_price,
                "final_price": digi_pricing.final_price,
                "real_profit": digi_pricing.real_profit,
                "effective_comm": digi_pricing.effective_comm,
                "status": digi_pricing.status,
                "reason": digi_pricing.reason,
                "dropped": digi_pricing.dropped,
            },
        },
    }


async def main():
    print("=" * 80)
    print("🚀 LIVE API STRESS TEST: 10 HARDEST REAL-WORLD PRODUCTS")
    print("Direct JSON calls to AlfaMall & DigiMall via curl_cffi Chrome 120")
    print("=" * 80)

    results = []
    async with AsyncSession(impersonate="chrome120") as session:
        for p in PRODUCTS_TO_TEST:
            print(f"\n[{p['sno']}/10] Testing: {p['brand']} - {p['name']}...")
            try:
                res = await run_single_product_test(session, p)
                results.append(res)

                alfa = res["alfa_audit"]
                digi = res["digi_audit"]
                print(f"  Model: '{res['target_model']}' | Anchor: '{res['slots']['anchor']}'")
                print(
                    f"  AlfaMall: {alfa['total_raw_scraped']} raw items -> {alfa['matched_count']} matched, {alfa['rejected_count']} rejected"
                )
                print(
                    f"    -> Final Price: {alfa['pricing']['final_price']} | Profit: Rs. {alfa['pricing']['real_profit']} | Reason: {alfa['pricing']['reason'][:60]}..."
                )
                print(
                    f"  DigiMall: {digi['total_raw_scraped']} raw items -> {digi['matched_count']} matched, {digi['rejected_count']} rejected"
                )
                print(
                    f"    -> Final Price: {digi['pricing']['final_price']} | Profit: Rs. {digi['pricing']['real_profit']} | Comm: {digi['pricing']['effective_comm']}"
                )

                if alfa["rejected_items"]:
                    print("    [Alfa Rejections Sample]:")
                    for rej in alfa["rejected_items"][:2]:
                        print(
                            f"      ❌ '{rej['title'][:55]}...' -> REASON: {rej['decision']['reason']}"
                        )

                if digi["rejected_items"]:
                    print("    [Digi Rejections Sample]:")
                    for rej in digi["rejected_items"][:2]:
                        print(
                            f"      ❌ '{rej['title'][:55]}...' -> REASON: {rej['decision']['reason']}"
                        )

            except Exception as e:
                print(f"  ❌ FAILED with error: {e}")
                import traceback

                traceback.print_exc()

    out_file = Path("scripts/live_stress_test_results.json")
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[+] Full detailed JSON diagnostics saved to: {out_file.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
