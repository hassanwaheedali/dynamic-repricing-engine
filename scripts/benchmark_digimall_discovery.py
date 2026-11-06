"""Compare old and new retrieval against identical in-memory HTTP replays.

Run from the repository root: python -m scripts.benchmark_digimall_discovery
No network, catalog writes, price exports or database access occur.
"""

import asyncio
import csv
import json
from pathlib import Path
from time import perf_counter
from typing import Any
from unittest.mock import MagicMock

from pricing_engine.digi_discovery import generate_digimall_plan
from pricing_engine.digi_transport import DigiDiscoveryContext
from pricing_engine.matcher import extract_search_query_and_model, generate_search_patterns
from pricing_engine.scraper import (
    DIGIMALL_CONFIG,
    _execute_waterfall,
    _scrape_platform_single_query,
    clear_scraper_cache,
    scrape_digimall,
)


class ReplaySession:
    """Controlled 2ms HTTP latency with target-compatible immutable responses."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.calls = 0
        self.active = 0
        self.peak = 0

    async def get(self, *args: Any, **kwargs: Any) -> MagicMock:
        self.calls += 1
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.002)
            response = MagicMock(status_code=200)
            response.json.return_value = {
                "count": 2,
                "results": [
                    {
                        "id": str(i),
                        "title": self.title,
                        "sold_out": False,
                        "variant_detail": {"discounted_price": str(price)},
                        "vendor": {"name": f"Replay Seller {i}"},
                    }
                    for i, price in enumerate((181500, 174565))
                ],
            }
            return response
        finally:
            self.active -= 1


async def measure(title: str, brand: str, adaptive: bool) -> dict[str, Any]:
    """Run three simultaneous identical products to measure real request sharing."""
    clear_scraper_cache()
    session: Any = ReplaySession(title)
    _, model = extract_search_query_and_model(title, brand=brand)
    patterns = generate_search_patterns(title, brand=brand)
    context = DigiDiscoveryContext(3)

    async def legacy_single(**kwargs: Any) -> Any:
        return await _scrape_platform_single_query(DIGIMALL_CONFIG, **kwargs)

    started = perf_counter()
    if adaptive:
        plan = generate_digimall_plan(title, brand)
        results = await asyncio.gather(
            *[
                scrape_digimall(
                    session, plan, model, brand=brand, target_desc=title, context=context
                )
                for _ in range(3)
            ]
        )
    else:
        results = await asyncio.gather(
            *[
                _execute_waterfall(
                    legacy_single, session, patterns, model, 15, 1, brand=brand, target_desc=title
                )
                for _ in range(3)
            ]
        )
    elapsed = perf_counter() - started
    prices = [offer.price for offer in results[0].offers if not offer.is_sold_out]
    return {
        "http_calls": session.calls,
        "peak_requests": session.peak,
        "elapsed_ms": round(elapsed * 1000, 2),
        "observed_min": min(prices, default=None),
        "compatible_offers": len(prices),
    }


async def main() -> None:
    """Use the first product from each of five fixture brands without model exceptions."""
    path = Path(__file__).resolve().parents[1] / "tests/fixtures/selected_100_stress_products.csv"
    selected: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            brand = row["Brands"]
            selected.setdefault(brand, row["Name"])
            if len(selected) == 5:
                break
    for brand, title in selected.items():
        before = await measure(title, brand, False)
        after = await measure(title, brand, True)
        print(
            json.dumps(
                {
                    "brand": brand,
                    "title": title,
                    "legacy": before,
                    "adaptive": after,
                    "same_observed_min": before["observed_min"] == after["observed_min"],
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
