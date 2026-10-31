import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("scripts/live_stress_test_results.json", encoding="utf-8") as f:
    data = json.load(f)

for item in data[5:7]:
    p = item["product"]
    alfa = item["alfa_audit"]
    digi = item["digi_audit"]
    print("=" * 80)
    print(f"Product #{p['sno']}: [{p['brand']}] {p['name']}")
    print(f"  Category: {p['category']} | Net Price: Rs. {p['net_price']:,.0f}")
    print(f"  Target Model: '{item['target_model']}' | Anchor: '{item['slots']['anchor']}'")
    print(f"  Guarded Facets: {item['slots']['facets']}")
    print(
        f"  Floors: Alfa={item['floors']['floor_alfa']:,.0f} | Digi 10%={item['floors']['floor_digi_10']:,.0f} | Digi 8%={item['floors']['floor_digi_8']:,.0f}"
    )

    print("\n  [ALFAMALL AUDIT]:")
    print(
        f"    Raw Items: {alfa['total_raw_scraped']} | Matched: {alfa['matched_count']} | Rejected: {alfa['rejected_count']}"
    )
    print(
        f"    Lowest Comp: {alfa['pricing']['min_comp']} | Final Price: {alfa['pricing']['final_price']} | Profit: Rs. {alfa['pricing']['real_profit']:,} | Status: {alfa['pricing']['status']}"
    )
    print(f"    Reason: {alfa['pricing']['reason']}")
    if alfa["matched_items"]:
        print("    -> Matched Samples:")
        for m in alfa["matched_items"][:3]:
            print(f"       ✓ Rs. {m['price']:,.0f} | {m['vendor']} | {m['title'][:65]}")
    if alfa["rejected_items"]:
        print("    -> Rejected Samples:")
        for r in alfa["rejected_items"][:3]:
            print(f"       ❌ {r['title'][:65]} -> {r['decision']['reason']}")

    print("\n  [DIGIMALL AUDIT]:")
    print(
        f"    Raw Items: {digi['total_raw_scraped']} | Matched: {digi['matched_count']} | Rejected: {digi['rejected_count']}"
    )
    print(
        f"    Lowest Comp: {digi['pricing']['min_comp']} | Final Price: {digi['pricing']['final_price']} | Profit: Rs. {digi['pricing']['real_profit']:,} | Effective Comm: {digi['pricing']['effective_comm']}"
    )
    print(f"    Reason: {digi['pricing']['reason']}")
    if digi["matched_items"]:
        print("    -> Matched Samples:")
        for m in digi["matched_items"][:3]:
            print(f"       ✓ Rs. {m['price']:,.0f} | {m['vendor']} | {m['title'][:65]}")
    if digi["rejected_items"]:
        print("    -> Rejected Samples:")
        for r in digi["rejected_items"][:3]:
            print(f"       ❌ {r['title'][:65]} -> {r['decision']['reason']}")
    print()
