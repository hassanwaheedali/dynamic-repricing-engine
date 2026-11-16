"""Arrival order, identity and transport must not contaminate competitor evidence."""

import asyncio
from itertools import permutations
from unittest.mock import AsyncMock, MagicMock

import pytest

from pricing_engine.models import ScrapedOffer, ScrapeResult
from pricing_engine.offer_processing import (
    deduplicate_offers,
    finalize_offers,
    parse_offers_with_tiers,
)


def test_verified_distinct_models_survive_identical_seller_price() -> None:
    offers = [
        ScrapedOffer("Seller", 100, False, model, scraped_model=model)
        for model in ["AX-120AA", "AX-120BB"]
    ]
    for order in permutations(offers):
        result = deduplicate_offers(list(order))
        assert {offer.scraped_model for offer in result} == {"AX-120AA", "AX-120BB"}


def test_sibling_models_remain_distinct_after_real_parsing() -> None:
    target = "Acme 18ABCCA 1.5 Ton Inverter Split AC"
    raw = [
        {
            "title": f"Acme {model} 1.5 Ton Inverter Split AC",
            "vendor": {"name": "Seller"},
            "variant_detail": {"discounted_price": "100000"},
        }
        for model in ["18ABCE", "18ABCCC"]
    ]
    _, _, sibling, *_ = parse_offers_with_tiers(raw, "18ABCCA", "Acme", target)
    assert len(sibling) == 2
    assert len(deduplicate_offers(sibling)) == 2


@pytest.mark.parametrize("platform", ["alfa", "digi"])
def test_instock_copy_in_later_query_wins_on_both_platforms(platform: str) -> None:
    from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall, scrape_digimall

    async def run() -> None:
        clear_scraper_cache()
        session = AsyncMock()

        async def get(*args: object, **kwargs: object) -> MagicMock:
            response = MagicMock(status_code=200)
            response.json.return_value = {
                "count": 1,
                "results": [
                    {
                        "id": "same",
                        "title": "Acme AX-900 Washer",
                        "sold_out": kwargs["params"]["q"] == "first",
                        "vendor": {"name": "Seller"},
                        "variant_detail": {"discounted_price": "10000"},
                    }
                ],
            }
            return response

        session.get.side_effect = get
        scraper = scrape_alfamall if platform == "alfa" else scrape_digimall
        result = await scraper(
            session,
            {"tier_1": ["first"], "tier_2": ["second"]},
            "AX-900",
            brand="Acme",
            target_desc="Acme AX-900 Washer",
        )
        assert len(result.offers) == 1
        assert not result.offers[0].is_sold_out

    asyncio.run(run())


def test_active_own_model_discovered_with_series_suppresses_series_competitor() -> None:
    own = ScrapedOffer("Kia Chahiye", 100, False, "Model", match_tier=1)
    series = ScrapedOffer("Seller", 90, False, "Series", match_tier=2, match_basis="series")
    result = finalize_offers(ScrapeResult(base_offers=[series], own_offers=[own]), "AX-900")
    assert result.offers == [] and result.own_offers == [own]
