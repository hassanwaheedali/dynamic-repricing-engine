"""Offline, repeatable architecture audit; no HTTP, database or upload calls."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pricing_engine.calculator import (
    calculate_cost_base,
    calculate_floors,
    resolve_fallback_shipping,
)
from pricing_engine.digi_discovery import generate_digimall_plan
from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.matcher import generate_search_patterns, referee_match
from pricing_engine.models import ScrapeResult
from pricing_engine.scraper import _parse_offers_with_tiers

ROOT = Path(__file__).resolve().parents[1]


def accepted(decision: Any) -> bool:
    return bool(decision.is_match or decision.is_base_match or decision.match_tier == 3)


def snapshot() -> dict[str, Any]:
    """Capture real catalog decisions, ordered queries and captured-offer pricing."""
    catalog: list[dict[str, Any]] = []
    with (ROOT / "data/inputs/100_Products/Book1.csv").open(encoding="utf-8-sig") as source:
        for index, row in enumerate(csv.DictReader(source), 1):
            title, brand = row["Title"], row["Brand"]
            probes = {
                "self": title,
                "cash": title + " CASH",
                "marketing": title + " - Friday Super Savings",
                "foreign-brand": re.sub(
                    re.escape(brand), "ForeignBrand", title, count=1, flags=re.I
                ),
            }
            decisions = {}
            for name, candidate in probes.items():
                decision = referee_match(title, candidate, brand)
                decisions[name] = {
                    "accepted": accepted(decision),
                    "tier": decision.match_tier,
                    "code": decision.reason_code,
                    "notice": decision.compatibility_notice,
                }
            try:
                digi: Any = asdict(generate_digimall_plan(title, brand))
            except ValueError as error:
                digi = {"error": str(error)}
            catalog.append(
                {
                    "item": index,
                    "brand": brand,
                    "title": title,
                    "alfa_queries": generate_search_patterns(title, brand),
                    "digi_plan": digi,
                    "decisions": decisions,
                    "shipping": resolve_fallback_shipping(title, brand),
                }
            )

    captured = []
    cases = json.loads((ROOT / "tests/fixtures/model_identity_regressions.json").read_text("utf-8"))
    for case in cases:
        title, brand = case["target"], case["brand"]
        exact, base, sibling, modifier, own, *_ = _parse_offers_with_tiers(
            case["offers"],
            "",
            brand,
            title,
        )
        selected = exact or base or sibling
        result = ScrapeResult(
            offers=selected,
            base_offers=base,
            sibling_offers=sibling,
            own_offers=own,
            active_modifier_fallback=modifier,
        )
        # Probe cost derives from observed prices, not a hardcoded platform fee/floor.
        net = min(o.price for o in selected) / 2
        shipping, _ = resolve_fallback_shipping(title, brand)
        floors = calculate_floors(calculate_cost_base(net, shipping))
        captured.append(
            {
                "title": title,
                "offers": [asdict(o) for o in selected],
                "own": [asdict(o) for o in own],
                "alfa": asdict(evaluate_alfa_pricing(floors, result)),
                "digi": asdict(evaluate_digi_pricing(floors, result)),
            }
        )
    return {"catalog": catalog, "captured": captured}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    # Compare the persisted wire shape: dataclass/query tuples serialize as arrays.
    data = json.loads(json.dumps(snapshot()))
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Captured {len(data['catalog'])} products and {len(data['captured'])} realistic offer cases"
    )
    if args.compare:
        baseline = json.loads(args.compare.read_text(encoding="utf-8"))
        report = compare_snapshots(baseline, data)
        if args.report:
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
        if report["unexplained"]:
            raise SystemExit(1)


def compare_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Explain only approved query corrections and additive internal provenance."""
    approved = []
    unexplained = []
    for old, new in zip(before["catalog"], after["catalog"], strict=True):
        changed = [key for key in old if old[key] != new[key]]
        if not changed:
            continue
        recovered_model = "error" in old["digi_plan"] and "branches" in new["digi_plan"]
        if recovered_model and set(changed) <= {"alfa_queries", "digi_plan"}:
            approved.append(
                {"item": old["item"], "correction": "structural model recovered", "fields": changed}
            )
        else:
            unexplained.append({"item": old["item"], "fields": changed})

    def external(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: external(item) for key, item in value.items() if key != "match_basis"}
        if isinstance(value, list):
            return [external(item) for item in value]
        return value

    captured_equal = external(before["captured"]) == external(after["captured"])
    if not captured_equal:
        unexplained.append({"captured": "offer, warning, identity or pricing difference"})
    return {
        "catalog_products": len(after["catalog"]),
        "matching_probes": sum(len(case["decisions"]) for case in after["catalog"]),
        "shipping_unchanged": sum(
            old["shipping"] == new["shipping"]
            for old, new in zip(before["catalog"], after["catalog"], strict=True)
        ),
        "captured_offer_pricing_cases": len(after["captured"]),
        "captured_cases_equal_excluding_default_match_basis": captured_equal,
        "approved_changes": approved,
        "unexplained": unexplained,
        "boundary": "Offline controlled probes and captured/mock evidence; no live inventory claim",
    }


if __name__ == "__main__":
    main()
