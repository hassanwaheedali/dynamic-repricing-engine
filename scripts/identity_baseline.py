"""Print the offline identity baseline as JSON. Run with python -m scripts.identity_baseline."""

import argparse
import csv
import gzip
import hashlib
import json
import platform
import re
import subprocess
from collections import Counter
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pricing_engine.matcher import (
    MatchDecision,
    extract_product_slots,
    generate_model_first_queries,
    referee_match,
)

QUANTITY = re.compile(
    r"(?<![\w.\-])(\d+(?:\.\d+)?)(\s*)(kg|tons?|litres?|liters?|ltrs?|inch(?:es)?|cu\s*ft|taps?)\b",
    re.I,
)


def decision_key(decision: MatchDecision) -> dict[str, object]:
    return {
        key: getattr(decision, key)
        for key in (
            "match_tier",
            "reason_code",
            "match_basis",
            "missing_modifier",
            "compatibility_notice",
            "detected_variant",
        )
    }


def probe_catalog(path: Path, ledger: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row_number, row in enumerate(csv.DictReader(stream), start=1):
            fields = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            title = next(
                (
                    fields[k]
                    for k in ("name", "title", "item name", "original_title")
                    if fields.get(k)
                ),
                "",
            )
            brand = fields.get("brand") or fields.get("brands", "")
            source = {
                "source": path.as_posix(),
                "data_row": row_number,
                "title": title,
                "brand": brand,
                "candidate_brand": "",
            }
            counts["rows"] += 1
            if not title:
                counts["blank_title"] += 1
                ledger.append({**source, "kind": "blank_title"})
                continue
            slots = extract_product_slots(title, brand)
            if not brand:
                counts["undeclared_brand"] += 1
                ledger.append({**source, "kind": "undeclared_brand"})
                continue
            counts["titled_with_brand"] += 1
            raw = referee_match(title, title, brand)
            prepared = referee_match(slots, title, brand)
            ledger.append(
                {
                    **source,
                    "kind": "self",
                    "candidate": title,
                    "raw": decision_key(raw),
                    "prepared": decision_key(prepared),
                }
            )
            counts[f"self_{raw.reason_code}"] += 1
            counts["raw_prepared_differences"] += decision_key(raw) != decision_key(prepared)
            match = QUANTITY.search(title)
            if match:
                altered = (
                    title[: match.start()] + str(Decimal(match[1]) + 1) + title[match.end(1) :]
                )
                counts["quantity_pairs"] += 1
                altered_raw = referee_match(title, altered, brand)
                counts["quantity_tiered"] += altered_raw.match_tier in (1, 2, 3)
                ledger.append(
                    {
                        **source,
                        "kind": "quantity_increment",
                        "candidate": altered,
                        "raw": decision_key(altered_raw),
                        "prepared": decision_key(referee_match(slots, altered, brand)),
                    }
                )
    return dict(counts)


def marketplace_inventory(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    """Index observed projections only; retain query/rank provenance across duplicate pages."""
    prefix = Path("docs/evidence")
    pages: dict[tuple[str, str], list[dict[str, Any]]] = {}
    inventory = []
    distinct = set()
    for suffix in ("sample", "retry"):
        path = prefix / f"marketplace_identity_axis_{suffix}_20261120.json"
        for page in json.loads(path.read_text("utf-8")):
            items = page.get("items", [])
            inventory.append(
                {key: value for key, value in page.items() if key != "items"}
                | {"source": path.as_posix(), "projected_items": len(items)}
            )
            key = (page["platform"], page["query"])
            if page.get("status") == 200:
                if key in pages:
                    raise ValueError(f"Multiple successful pages for {key}; resolve page identity")
                pages[key] = items
            distinct.update((page["platform"], item["id"]) for item in items)
    targets = json.loads(
        (prefix / "marketplace_identity_axis_replay_20261120.json").read_text("utf-8")
    )
    for target in targets:
        slots = extract_product_slots(target["title"], target["brand"])
        for query in target["queries"]:
            for rank, item in enumerate(pages[(target["platform"], query)], 1):
                # All projected November pages carry at most one manufacturer label.
                brands = tuple(group["title"] for group in item.get("brand") or [])
                if len(brands) > 1:
                    raise ValueError("Multiple manufacturer labels require explicit adjudication")
                brand = next(iter(brands), "")
                seller = item["title"]
                ledger.append(
                    {
                        "kind": "marketplace",
                        "source": target["file"],
                        "data_row": target["row"],
                        "title": target["title"],
                        "brand": target["brand"],
                        "candidate": seller,
                        "candidate_brand": brand,
                        "platform": target["platform"],
                        "query": query,
                        "page": 1,
                        "rank": rank,
                        "listing_id": item["id"],
                        "raw": decision_key(
                            referee_match(
                                target["title"], seller, target["brand"], candidate_brand=brand
                            )
                        ),
                        "prepared": decision_key(
                            referee_match(slots, seller, target["brand"], candidate_brand=brand)
                        ),
                    }
                )
    return {
        "pages": inventory,
        "distinct_platform_listing_ids": len(distinct),
        "coverage": "Projected first pages of selected queries; no later pages observed.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger", type=Path, help="Create a new gzip JSON Lines file of fixed pairs"
    )
    args = parser.parse_args()
    catalogs = sorted(
        p for root in ("data/inputs", "tests/fixtures") for p in Path(root).rglob("*.csv")
    )
    files = set(catalogs)
    for pattern in (
        "pricing_engine/**/*.py",
        "tests/**/*.py",
        "tests/fixtures/**/*.json",
        "docs/evidence/*20261120.*",
        "scripts/*.sql",
    ):
        files.update(Path().glob(pattern))
    files.update(
        map(
            Path,
            [
                "config.py",
                "index.py",
                "pyproject.toml",
                "requirements.txt",
                "scripts/identity_baseline.py",
                "docs/PRODUCT_IDENTITY_ENGINE_BLUEPRINT.md",
                "docs/PRICE_ENGINE_MASTER_ARCHITECTURE_PLAN.md",
            ],
        )
    )
    fixtures = Path("tests/fixtures")
    exact_cases = json.loads((fixtures / "model_identity_regressions.json").read_text("utf-8"))
    query_cases = json.loads((fixtures / "hardware_query_regressions.json").read_text("utf-8"))
    ledger: list[dict[str, Any]] = []
    results = {p.as_posix(): probe_catalog(p, ledger) for p in catalogs}
    captures = marketplace_inventory(ledger)
    ledger_hash = None
    if args.ledger:
        with (
            args.ledger.open("xb") as destination,
            gzip.GzipFile(fileobj=destination, filename="", mode="wb", mtime=0) as compressed,
        ):
            for pair in ledger:
                compressed.write((json.dumps(pair, separators=(",", ":")) + "\n").encode("utf-8"))
        ledger_hash = hashlib.sha256(args.ledger.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "branch": subprocess.check_output(
                    ["git", "branch", "--show-current"], text=True
                ).strip(),
                "python": platform.python_version(),
                "versions": {
                    p: version(p)
                    for p in ("pytest", "mypy", "ruff", "pandas", "rich", "curl_cffi", "openpyxl")
                },
                "sha256": {
                    p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)
                },
                "catalogs": results,
                "marketplace_capture_inventory": captures,
                "fixed_pairs": {
                    "counts": dict(Counter(item["kind"] for item in ledger)),
                    "gzip_sha256": ledger_hash,
                    "labels": "Diagnostic observations only. Required outcomes are separately adjudicated.",
                },
                "exact_fixture_tiers": [
                    referee_match(c["target"], o["title"], c["brand"]).match_tier
                    for c in exact_cases
                    for o in c["offers"]
                ],
                "query_fixture_pass": [
                    list(generate_model_first_queries(c["title"], c["brand"])) in c["queries"]
                    for c in query_cases["cases"]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
