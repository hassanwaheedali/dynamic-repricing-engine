"""PG-M01 payload replays through both actual scraper entrypoints (mocked HTTP)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pricing_engine.calculator import calculate_floors
from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall, scrape_digimall


@pytest.mark.parametrize("platform", ["alfa", "digi"])
@pytest.mark.parametrize("size,capacity", [(15, "1"), (30, "1.5")])
def test_mega_flex_smart_stays_in_exact_price_pool(platform: str, size: int, capacity: str) -> None:
    async def run() -> None:
        clear_scraper_cache()
        target = f"Dawlance {capacity} Ton Inverter Mega Flex {size} Split Air Conditioner"
        market = f"Dawlance {capacity} Ton Mega Flex {size} Smart Frequency AC"
        other_size = 30 if size == 15 else 15
        wrong_capacity = "1.5" if capacity == "1" else "1"
        wrong = f"Dawlance {wrong_capacity} Ton Mega Flex {other_size} Smart Frequency AC"
        payload = []
        for index, (title, price) in enumerate(
            [(market, 154255), (target, 164499), (wrong, 120000)]
        ):
            payload.append(
                {
                    "id": str(index),
                    "title": title,
                    "sold_out": False,
                    "vendor": {"name": f"External Seller {index}"},
                    "variant_detail": {"discounted_price": str(price)},
                }
            )
        response = MagicMock(status_code=200)
        response.json.return_value = {"results": payload, "count": len(payload)}
        session = AsyncMock()
        session.get.return_value = response
        scraper = scrape_alfamall if platform == "alfa" else scrape_digimall
        evaluator = evaluate_alfa_pricing if platform == "alfa" else evaluate_digi_pricing
        try:
            result = await scraper(
                session,
                f"Mega Flex {size}",
                "",
                brand="Dawlance",
                target_desc=target,
            )
            assert result.is_success
            assert [(offer.price, offer.match_tier) for offer in result.offers] == [
                (154255, 1),
                (164499, 1),
            ]
            assert not result.base_offers
            assert result.active_modifier_fallback is None
            assert result.compatibility_notice is None
            evaluated = evaluator(calculate_floors(100000), result)
            assert evaluated.min_price == 154255
            assert "CROSS-CHECK" not in evaluated.reason
            assert session.get.await_count > 0
        finally:
            clear_scraper_cache()

    asyncio.run(run())


@pytest.mark.parametrize("platform", ["alfa", "digi"])
def test_selected_exact_advisory_survives_actual_scraper(platform: str) -> None:
    async def run() -> None:
        clear_scraper_cache()
        target = "Dawlance DWT-1165 Washing Machine"
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "count": 1,
            "results": [
                {
                    "title": "Dawlance DWT-1165 ECO Washing Machine",
                    "sold_out": False,
                    "vendor": {"name": "External Seller"},
                    "variant_detail": {"discounted_price": "85000"},
                }
            ],
        }
        session = AsyncMock()
        session.get.return_value = response
        scraper = scrape_alfamall if platform == "alfa" else scrape_digimall
        evaluator = evaluate_alfa_pricing if platform == "alfa" else evaluate_digi_pricing
        try:
            result = await scraper(
                session,
                "DWT-1165",
                "DWT-1165",
                brand="Dawlance",
                target_desc=target,
            )
            assert len(result.offers) == 1
            assert result.offers[0].match_tier == 1
            assert result.active_modifier_fallback is None
            assert "CROSS-CHECK NOTICE" in (result.compatibility_notice or "")
            evaluated = evaluator(calculate_floors(72000), result)
            assert evaluated.reason.count("CROSS-CHECK NOTICE") == 1
            assert "'ECO'" in evaluated.reason
        finally:
            clear_scraper_cache()

    asyncio.run(run())
