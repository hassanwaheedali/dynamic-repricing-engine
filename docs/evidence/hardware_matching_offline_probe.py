"""Read-only hardware audit reproduction; prints JSON, performs no network or file writes.

Run with a dependency-light Python interpreter:
    python -B docs/evidence/hardware_matching_offline_probe.py

The default characterizes the original source. Pass --after to validate the
approved PG-M01 correction against the same inputs. Historical baseline JSON
is preserved; this diagnostic is not a replacement for pytest.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pricing_engine.matcher import referee_match  # noqa: E402
from pricing_engine.models import ScrapedOffer, ScrapeResult  # noqa: E402
from pricing_engine.offer_processing import (  # noqa: E402
    finalize_offers,
    parse_offers_with_tiers,
)


def evidence(target: str, candidate: str, brand: str) -> dict:
    decision = referee_match(target, candidate, brand)

    def slots(value: object) -> dict:
        if value is None:
            return {}
        facets = value.guarded_facets
        return {
            "anchor": value.anchor,
            "series": value.series,
            "capabilities": sorted(facets.capabilities),
            "negative": sorted(facets.negative_capabilities),
            "ambiguous": sorted(facets.ambiguous_capabilities),
            "capacity": facets.capacity,
            "inverter": facets.is_inverter,
            "bound_model_tags": sorted(getattr(value, "bound_model_tags", set())),
            "loose_model_designations": list(getattr(value, "model_designations", ())),
        }

    return {
        "target": target,
        "candidate": candidate,
        "brand": brand,
        "target_slots": slots(decision.target_slots),
        "candidate_slots": slots(decision.candidate_slots),
        "reason_code": decision.reason_code,
        "tier": decision.match_tier,
        "reason": decision.reason,
        "compatibility_notice": decision.compatibility_notice,
        "missing_modifier": decision.missing_modifier,
    }


def main() -> None:
    after = "--after" in sys.argv
    corpus = ROOT / "data/inputs/100_Products/Book1.csv"
    with corpus.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 100
    assert all(referee_match(r["Title"], r["Title"], r["Brand"]).match_tier == 1 for r in rows)

    controls = [
        (
            "alias",
            "Dawlance",
            "Dawlance DW-MD 15 20 Ltr Microwave Oven",
            "Dawlance MD 15 20 Ltr Microwave Oven",
            1,
        ),
        (
            "short-prefix",
            "Dawlance",
            "Dawlance DW-MD 15 Microwave Oven",
            "Dawlance DW-15 Microwave Oven",
            None,
        ),
        (
            "numeric-boundary",
            "Dawlance",
            "Dawlance DWT-1165 Washing Machine",
            "Dawlance DWT-11650 Washing Machine",
            None,
        ),
        (
            "e-chrome",
            "Dawlance",
            "Dawlance 9149WB E-Chrome Refrigerator",
            "Dawlance 9149WB Chrome Refrigerator",
            None,
        ),
        (
            "e-chrome-pro",
            "Dawlance",
            "Dawlance 9149WB E-Chrome Refrigerator",
            "Dawlance 9149WB Chrome Pro Refrigerator",
            None,
        ),
        (
            "t3-t4",
            "Haier",
            "Haier HSU-18HFP T3 Inverter AC",
            "Haier HSU-18HFP T4 Inverter AC",
            None,
        ),
        (
            "t3-negative",
            "Haier",
            "Haier HSU-18HFP T3 Inverter AC",
            "Haier HSU-18HFP Non-T3 Inverter AC",
            None,
        ),
        ("t3-omitted", "Haier", "Haier HSU-18HFP T3 Inverter AC", "Haier HSU-18HFP Inverter AC", 2),
        ("t3-prose", "Haier", "Haier HSU-18HFP Inverter AC", "Haier HSU-18HFP T3 Inverter AC", 1),
        (
            "t3-bound-extra",
            "Gree",
            "Gree GS-18AITH24S Inverter AC",
            "Gree GS-18AITH24S-T3 Inverter AC",
            None,
        ),
        (
            "inv-explicit",
            "Samsung",
            "Samsung WA80CK4240BWRT 8KG Inverter Washing Machine",
            "Samsung WA80CK4240BWRT 8KG Non-Inverter Washing Machine",
            None,
        ),
        (
            "inv-omitted",
            "Samsung",
            "Samsung WA80CK4240BWRT 8KG Inverter Washing Machine",
            "Samsung WA80CK4240BWRT 8KG Washing Machine",
            1,
        ),
        (
            "kg-conflict",
            "Samsung",
            "Samsung WA80CK4240BWRT 8KG Washing Machine",
            "Samsung WA80CK4240BWRT 10KG Washing Machine",
            None,
        ),
        ("color", "Gree", "Gree GS-12AITH21W Inverter AC", "Gree GS-12AITH21B Inverter AC", None),
        (
            "edition",
            "Dawlance",
            "Dawlance DWT-1165 ES Washing Machine",
            "Dawlance DWT-1165 ES8 Washing Machine",
            None,
        ),
        (
            "edition-missing",
            "Dawlance",
            "Dawlance DWT-1165 ES Washing Machine",
            "Dawlance DWT-1165 Washing Machine",
            2,
        ),
        (
            "door-finish",
            "Haier",
            "Haier HRF-538 Glass Door Refrigerator",
            "Haier HRF-538 Inox Refrigerator",
            None,
        ),
        (
            "door-structure",
            "Haier",
            "Haier HRF-538 Single Door Refrigerator",
            "Haier HRF-538 Double Door Refrigerator",
            None,
        ),
        (
            "wash-load",
            "Samsung",
            "Samsung WA80CK4240BWRT 8KG Front Load Washing Machine",
            "Samsung WA80CK4240BWRT 8KG Top Load Washing Machine",
            None,
        ),
        (
            "tub",
            "Haier",
            "Haier HWM-80-1217 Twin Tub Washing Machine",
            "Haier HWM-80-1217 Single Tub Washing Machine",
            None,
        ),
        (
            "automation",
            "Haier",
            "Haier HWM-80-1217 Fully Automatic Washing Machine",
            "Haier HWM-80-1217 Semi Automatic Washing Machine",
            None,
        ),
        (
            "defrost",
            "Haier",
            "Haier HRF-538 Direct Cool Refrigerator",
            "Haier HRF-538 No Frost Refrigerator",
            None,
        ),
        ("mount", "Haier", "Haier HSU-18HFP Split AC", "Haier HSU-18HFP Floor Standing AC", None),
        (
            "mode",
            "Haier",
            "Haier HSU-18HFP Cool Only Inverter AC",
            "Haier HSU-18HFP Heat & Cool Inverter AC",
            None,
        ),
        (
            "base",
            "Haier",
            "Haier 18HFPCA 1.5 Ton Inverter AC",
            "Haier HSU-18HFP 1.5 Ton Inverter AC",
            2,
        ),
        (
            "sibling",
            "Haier",
            "Haier 18HFPCA 1.5 Ton Inverter AC",
            "Haier HSU-18HFPE 1.5 Ton Inverter AC",
            3,
        ),
        (
            "wrong-series",
            "Haier",
            "Haier 18HFPCA 1.5 Ton Inverter AC",
            "Haier HSU-18HFA 1.5 Ton Inverter AC",
            None,
        ),
        (
            "ADS-negative",
            "Dawlance",
            "Dawlance DWT-1166 ADS+ Washing Machine",
            "Dawlance DWT-1166 Non-ADS+ Washing Machine",
            None,
        ),
    ]
    control_results = []
    for name, brand, target, candidate, expected in controls:
        result = evidence(target, candidate, brand)
        assert result["tier"] == expected, (name, result)
        control_results.append({"id": name, "expected_current_tier": expected, **result})

    counts = Counter()
    changed = []
    phrases = [
        " Smart Frequency",
        " WiFi",
        " Without WiFi",
        " | 4-Way Air Throw",
        " | Premium Performance",
    ]
    for index, row in enumerate(rows, 1):
        for phrase in phrases:
            result = evidence(row["Title"], row["Title"] + phrase, row["Brand"])
            counts[f"{phrase.strip()} => {result['reason_code']}/T{result['tier']}"] += 1
            if result["tier"] != 1:
                changed.append({"row": index, "append": phrase, **result})

    mega = "Dawlance 1.5 Ton Inverter Mega Flex 30 Split Air Conditioner"
    smart = "Dawlance 1.5 Ton Mega Flex 30 Smart Frequency AC"
    glacier = "Dawlance 2 Ton Inverter Glacier 45 Pro T3 Floor Standing Air Conditioner"
    glacier_market = "Dawlance 2 Ton Inverter Floor Standing Heat & Cool Air Conditioner (White) | Glacier Pro 45 T3 | 4-Way Air Throw | Gold Fin Coils"
    eco = "Dawlance DWT-1165 Washing Machine"
    eco_market = "Dawlance DWT-1165 ECO Washing Machine"

    def raw(title: str, vendor: str, price: str, discounted: str = "") -> dict:
        return {
            "title": title,
            "vendor": {"name": vendor},
            "sold_out": False,
            "variant_detail": {"original_price": price, "discounted_price": discounted},
        }

    def pool(items: list[dict], target: str) -> dict:
        parsed = parse_offers_with_tiers(items, "", "Dawlance", target)
        selected = finalize_offers(
            ScrapeResult(
                offers=parsed[0],
                base_offers=parsed[1],
                sibling_offers=parsed[2],
                raw_candidate_count=len(items),
                rejected_count=parsed[6],
                rejection_reasons=parsed[7],
                suspicious_rejected_count=parsed[8],
            ),
            "",
        )
        return {
            "exact": [(o.vendor_name, o.price) for o in parsed[0]],
            "base": [(o.vendor_name, o.price) for o in parsed[1]],
            "selected": [(o.vendor_name, o.price) for o in selected.offers],
            "status": selected.discovery_status,
            "rejected": parsed[6],
        }

    pool_results = {
        "mega": pool(
            [raw(smart, "Electronics World", "159855", "154255"), raw(mega, "Home Cart", "164499")],
            mega,
        ),
        "eco": pool([raw(eco_market, "External Merchant", "150000")], eco),
        "glacier": pool([raw(glacier_market, "External Merchant", "150000")], glacier),
    }
    expected_mega = (
        [("Electronics World", 154255.0), ("Home Cart", 164499.0)]
        if after
        else [("Home Cart", 164499.0)]
    )
    assert pool_results["mega"]["selected"] == expected_mega

    exact = ScrapedOffer("External Exact", 164499, False, "exact", match_tier=1)
    base = ScrapedOffer("External Base", 154255, False, "base", match_tier=2)
    sibling = ScrapedOffer("External Sibling", 144255, False, "sibling", match_tier=3)
    for e, b, s, expected in [
        ([exact], [base], [sibling], 1),
        ([], [base], [sibling], 2),
        ([], [], [sibling], 3),
    ]:
        result = finalize_offers(ScrapeResult(offers=e, base_offers=b, sibling_offers=s), "target")
        assert {offer.match_tier for offer in result.offers} == {expected}

    observed = [
        evidence(mega, smart, "Dawlance"),
        evidence(glacier, glacier_market, "Dawlance"),
        evidence(eco, eco_market, "Dawlance"),
    ]
    for label, brand, target, candidate in [
        (
            "md15-eco",
            "Dawlance",
            "Dawlance MD 15 20 Ltr Microwave Oven",
            "Dawlance MD 15 ECO 20 Ltr Microwave Oven",
        ),
        (
            "tv-smart-prose",
            "TCL",
            "TCL 32S5400 32 Inch Smart LED TV",
            "TCL 32S5400 32 Inch Non-Smart LED TV",
        ),
        (
            "iron-preserved",
            "Dawlance",
            "Dawlance DWSI 2322 CX Handheld Corded Garment Steam Iron",
            "Dawlance Dwsi 2322 CX Steam Iron Fast and efficient ironing",
        ),
        (
            "without-inverter",
            "Samsung",
            "Samsung WA80CK4240BWRT 8KG Inverter Washing Machine",
            "Samsung WA80CK4240BWRT 8KG Without Inverter Washing Machine",
        ),
        (
            "target-ambiguity",
            "Haier",
            "Haier HSU-18HFP T3 Non-T3 Inverter AC",
            "Haier HSU-18HFP T3 Inverter AC",
        ),
        (
            "litres",
            "Dawlance",
            "Dawlance DW-MD 15 20 Ltr Microwave Oven",
            "Dawlance MD 15 30 Ltr Microwave Oven",
        ),
        (
            "multiple-kg",
            "Samsung",
            "Samsung WA80CK4240BWRT 8KG Washing Machine",
            "Samsung WA80CK4240BWRT 8KG 10KG Washing Machine",
        ),
        (
            "component-display",
            "Samsung",
            "Samsung WA80CK4240BWRT 8KG Washing Machine",
            "Samsung WA80CK4240BWRT 8KG Washing Machine 6 Inch LED Display",
        ),
        (
            "tap-hidden",
            "Midea",
            "Midea YL2037S 3L 2 Taps Water Dispenser 1KG",
            "Midea YL2037S 3L 3 Taps Water Dispenser 1KG",
        ),
        (
            "missing-capacity",
            "Dawlance",
            "Dawlance 1.5 Ton Inverter Mega Flex 30 Split AC",
            "Dawlance Mega Flex Inverter Split AC",
        ),
        (
            "rpm-suspicion",
            "Samsung",
            "Samsung WA80CK4240BWRT 8KG Washing Machine",
            "Samsung WA80CK4240BWRT 8KG Washing Machine 1400RPM",
        ),
    ]:
        observed.append({"id": label, **evidence(target, candidate, brand)})

    print(
        json.dumps(
            {
                "interpreter": sys.version,
                "corpus": str(corpus.relative_to(ROOT)),
                "corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
                "row_numbering": "1-based data row, header excluded, no filtering",
                "self_matches": 100,
                "controls_passed": len(controls),
                "controls": control_results,
                "append_probes": 500,
                "append_counts": dict(counts),
                "changed_append_results": changed,
                "pool_priority_assertions_passed": 3,
                "pool_replays": pool_results,
                "additional_observations": observed,
                "boundary": (
                    "Offline PG-M01 post-correction replay; no marketplace or database requests."
                    if after
                    else "Offline original-source characterization; no production correction implemented or tested."
                ),
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
