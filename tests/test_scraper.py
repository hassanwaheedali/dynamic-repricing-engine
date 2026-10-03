import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pricing_engine.scraper import (
    clear_scraper_cache,
    get_scraper_cache,
    scrape_alfamall,
    scrape_digimall,
)


@pytest.fixture(autouse=True)
def reset_cache() -> None:
    clear_scraper_cache()


def test_query_cache_stores_valid_offers() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "GREE 36TFIH FLOOR STANDING",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "489,999"},
                    "vendor": {"name": "Test Vendor"},
                }
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        offers1 = await scrape_alfamall(mock_session, "36TFIH", "36TFIH")
        assert len(offers1) == 1
        assert mock_session.get.call_count == 1

        # Second call should hit in-memory cache with 0 remote network calls!
        offers2 = await scrape_alfamall(mock_session, "36TFIH", "36TFIH")
        assert len(offers2) == 1
        assert offers2[0].vendor_name == "Test Vendor"
        assert mock_session.get.call_count == 1  # Still 1! 0ms cache hit

    asyncio.run(_test())


def test_query_cache_never_caches_empty_or_failures() -> None:
    async def _test() -> None:
        # First call fails with 429
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp_429

        offers_failed = await scrape_alfamall(mock_session, "36TFIH", "36TFIH", max_retries=1)
        assert len(offers_failed) == 0

        # Ensure empty failure was NOT cached
        cache = get_scraper_cache()
        assert ("alfamall", "36TFIH") not in cache

        # Next call with 200 OK should fetch fresh and not return poisoned empty list
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {
            "results": [
                {
                    "title": "GREE 36TFIH",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "489,999"},
                    "vendor": {"name": "Real Seller"},
                }
            ]
        }
        mock_session.get.return_value = mock_resp_200

        offers_recovered = await scrape_alfamall(mock_session, "36TFIH", "36TFIH")
        assert len(offers_recovered) == 1
        assert offers_recovered[0].vendor_name == "Real Seller"

    asyncio.run(_test())


def test_digimall_cache_guard_prevents_false_monopoly() -> None:
    async def _test() -> None:
        # If DigiMall fails on first attempt, ensure it does not cache empty
        mock_resp_timeout = MagicMock()
        mock_resp_timeout.status_code = 502

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp_timeout

        offers = await scrape_digimall(mock_session, "12AITH21W", "12AITH21W", max_retries=1)
        assert len(offers) == 0
        assert offers.is_success is False

        cache = get_scraper_cache()
        assert ("digimall", "12AITH21W") not in cache

    asyncio.run(_test())


def test_scraper_soft_200_html_challenge_returns_failure() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Simulate HTML WAF challenge where resp.json() raises JSONDecodeError
        mock_resp.json.side_effect = ValueError("Invalid JSON / HTML challenge")

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        result = await scrape_alfamall(mock_session, "36TFIH", "36TFIH", max_retries=1)
        assert result.is_success is False
        assert len(result.offers) == 0
        assert "Invalid JSON" in (result.error_detail or "")

    asyncio.run(_test())


def test_scraper_supports_data_key_schema() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Storefront returns 'data' key instead of 'results'
        mock_resp.json.return_value = {
            "data": [
                {
                    "title": "GREE SPLIT AC 12AITH21W-T3",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "165,999"},
                    "vendor": {"name": "DataKey Vendor"},
                }
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        result = await scrape_digimall(mock_session, "12AITH21W-T3", "12AITH21W-T3")
        assert result.is_success is True
        assert len(result.offers) == 1
        assert result.offers[0].vendor_name == "DataKey Vendor"

    asyncio.run(_test())


def test_scraper_http_500_returns_failure_result() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        result = await scrape_alfamall(mock_session, "36TFIH", "36TFIH", max_retries=1)
        assert result.is_success is False
        assert result.status_code == 500
        assert len(result.offers) == 0

    asyncio.run(_test())


def test_waterfall_early_exit_when_tier_1_has_two_or_more_offers() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 GC WASHING MACHINE",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "95,000"},
                    "vendor": {"name": "Vendor A"},
                },
                {
                    "title": "HAIER 120-826S6 GC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "97,000"},
                    "vendor": {"name": "Vendor B"},
                },
            ]
        }
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        patterns = {
            "tier_1": ["120-826S6 GC"],
            "tier_2": ["120-826S6"],
            "tier_3": ["120 826S6"],
        }
        result = await scrape_alfamall(mock_session, patterns, "120-826S6 GC")

        assert result.is_success is True
        assert len(result.offers) == 2
        # Exhaustive 3-Tier Multi-Pattern Search: All 3 tiers are queried to ensure complete candidate pool
        assert mock_session.get.call_count == 3

    asyncio.run(_test())


def test_waterfall_cascades_to_tier_2_when_tier_1_has_few_offers() -> None:
    async def _test() -> None:
        # First call (Tier 1) returns 1 offer
        resp_tier1 = MagicMock()
        resp_tier1.status_code = 200
        resp_tier1.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 GC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "95,000"},
                    "vendor": {"name": "Vendor A"},
                }
            ]
        }

        # Second call (Tier 2) returns 1 additional offer
        resp_tier2 = MagicMock()
        resp_tier2.status_code = 200
        resp_tier2.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 AUTOMATIC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "96,000"},
                    "vendor": {"name": "Vendor B"},
                }
            ]
        }

        # Third call (Tier 3) returns 0 offers
        resp_tier3 = MagicMock()
        resp_tier3.status_code = 200
        resp_tier3.json.return_value = {"results": []}

        mock_session = AsyncMock()
        mock_session.get.side_effect = [resp_tier1, resp_tier2, resp_tier3]

        patterns = {
            "tier_1": ["120-826S6 GC"],
            "tier_2": ["120-826S6"],
            "tier_3": ["120 826S6"],
        }
        result = await scrape_digimall(mock_session, patterns, "120-826S6")

        assert result.is_success is True
        assert len(result.offers) == 2
        # Exhaustive search queries all tiers (total 3 HTTP calls across Tier 1, 2, 3)
        assert mock_session.get.call_count == 3

    asyncio.run(_test())


def test_waterfall_deduplicates_overlapping_offers_across_tiers() -> None:
    async def _test() -> None:
        # Tier 1 returns Seller A
        resp_tier1 = MagicMock()
        resp_tier1.status_code = 200
        resp_tier1.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 GC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "95,000"},
                    "vendor": {"name": "Vendor A"},
                }
            ]
        }

        # Tier 2 returns Seller A (same item/price) AND Seller B
        resp_tier2 = MagicMock()
        resp_tier2.status_code = 200
        resp_tier2.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 GC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "95,000"},
                    "vendor": {"name": "Vendor A"},
                },
                {
                    "title": "HAIER 120-826S6",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "98,000"},
                    "vendor": {"name": "Vendor B"},
                },
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.side_effect = [resp_tier1, resp_tier2]

        patterns = {
            "tier_1": ["120-826S6 GC"],
            "tier_2": ["120-826S6"],
            "tier_3": ["120 826S6"],
        }
        result = await scrape_alfamall(mock_session, patterns, "120-826S6")

        assert result.is_success is True
        # Deduplication check: Vendor A should appear only ONCE
        assert len(result.offers) == 2
        vendors = [o.vendor_name for o in result.offers]
        assert vendors.count("Vendor A") == 1
        assert vendors.count("Vendor B") == 1

    asyncio.run(_test())


def test_waterfall_prefers_t3_offers_over_base_offers() -> None:
    async def _test() -> None:
        base_response = MagicMock()
        base_response.status_code = 200
        base_response.json.return_value = {
            "results": [
                {
                    "title": "GREE 12AITH21W Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "150,000"},
                    "vendor": {"name": "Base Seller"},
                }
            ]
        }

        t3_response = MagicMock()
        t3_response.status_code = 200
        t3_response.json.return_value = {
            "results": [
                {
                    "title": "GREE 12AITH21W-T3 Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "155,000"},
                    "vendor": {"name": "T3 Seller"},
                }
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.side_effect = [base_response, t3_response]

        result = await scrape_alfamall(
            mock_session,
            {
                "tier_1": ["12AITH21W"],
                "tier_2": ["12AITH21W-T3"],
                "tier_3": [],
            },
            "12AITH21W-T3",
            brand="Gree",
        )

        assert [offer.vendor_name for offer in result.offers] == ["T3 Seller"]
        assert result.active_modifier_fallback is None

    asyncio.run(_test())


def test_waterfall_falls_back_to_base_when_no_t3_offer_exists() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "GREE 12AITH21W Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "150,000"},
                    "vendor": {"name": "Base Seller"},
                }
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        result = await scrape_alfamall(
            mock_session,
            {"tier_1": ["12AITH21W"], "tier_2": [], "tier_3": []},
            "12AITH21W-T3",
            brand="Gree",
        )

        assert [offer.vendor_name for offer in result.offers] == ["Base Seller"]
        assert result.active_modifier_fallback == "T3"

    asyncio.run(_test())


def test_scraper_deduplicates_seller_duplicate_spam_at_same_price() -> None:
    async def _test() -> None:
        # Simulate Tech House spamming identical offers with slightly different title suffixes
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "Haier Top Load Automatic Washing Machine HWM 120-316S6 -By Tech House314",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": "Tech House"},
                },
                {
                    "title": "Haier Top Load Automatic Washing Machine HWM 120-316S6 -By Tech House306",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": "Tech House"},
                },
                {
                    "title": "Haier Top Load Automatic Washing Machine HWM 120-316S6 -By Tech House322",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": "Tech House"},
                },
                {
                    "title": "Haier 120-316S6 Premium Bundle",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "85,000"},
                    "vendor": {"name": "Tech House"},  # Genuine different price
                },
                {
                    "title": "Haier HWM 120-316S6 Washing Machine",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": "One Stop Mall"},  # Distinct vendor at same price
                },
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        result = await scrape_alfamall(mock_session, "120-316S6", "120-316S6")
        assert result.is_success is True

        # Tech House @ 81,500 should appear only ONCE, with duplicate_count = 3
        # Tech House @ 85,000 should appear ONCE, with duplicate_count = 1
        # One Stop Mall @ 81,500 should appear ONCE, with duplicate_count = 1
        # Total offers should be 3 (not 5)
        assert len(result.offers) == 3

        th_81500 = [o for o in result.offers if o.price == 81500 and o.vendor_name == "Tech House"]
        assert len(th_81500) == 1
        assert th_81500[0].duplicate_count == 3

        th_85000 = [o for o in result.offers if o.price == 85000 and o.vendor_name == "Tech House"]
        assert len(th_85000) == 1
        assert th_85000[0].duplicate_count == 1

        osm_81500 = [o for o in result.offers if o.price == 81500 and o.vendor_name == "One Stop Mall"]
        assert len(osm_81500) == 1
        assert osm_81500[0].duplicate_count == 1

    asyncio.run(_test())


def test_scraper_uses_limit_100_for_single_call_market_depth() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        await scrape_alfamall(mock_session, "120-316S6", "120-316S6")
        assert mock_session.get.call_count == 1
        alfa_params = mock_session.get.call_args_list[0].kwargs.get("params") or {}
        assert alfa_params.get("limit") == "100"

        mock_session.reset_mock()
        await scrape_digimall(mock_session, "120-316S6", "120-316S6")
        assert mock_session.get.call_count == 1
        digi_params = mock_session.get.call_args_list[0].kwargs.get("params") or {}
        assert digi_params.get("limit") == "100"

    asyncio.run(_test())



def test_scraper_subfloor_probe_fetches_page_2_when_page_1_is_all_subfloor() -> None:
    async def _test() -> None:
        # Page 1 has 50 items all below floor Rs. 88,000, with total count = 75
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "results": [
                {
                    "title": f"Haier 120-316S6 Seller {i}",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": f"SubFloor Seller {i}"},
                }
                for i in range(50)
            ],
            "count": 75,
        }

        # Page 2 has the viable competitor @ Rs. 88,599
        resp_p2 = MagicMock()
        resp_p2.status_code = 200
        resp_p2.json.return_value = {
            "results": [
                {
                    "title": "Haier 120-316S6",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "88,599"},
                    "vendor": {"name": "Kia Chahiye"},
                }
            ],
            "count": 75,
        }

        mock_session = AsyncMock()
        mock_session.get.side_effect = [resp_p1, resp_p2]

        result = await scrape_alfamall(
            mock_session, "120-316S6", "120-316S6", floor_price=88000.0
        )
        assert result.is_success is True
        # Should have called page 1 then page 2
        assert mock_session.get.call_count == 2
        p2_call = mock_session.get.call_args_list[1].kwargs.get("params") or {}
        assert p2_call.get("page") == "2"

        # Viable competitor from page 2 should be in offers
        viable = [o for o in result.offers if o.price == 88599]
        assert len(viable) == 1
        assert viable[0].vendor_name == "Kia Chahiye"

    asyncio.run(_test())


def test_scraper_subfloor_probe_skips_page_2_when_viable_seller_found_on_page_1() -> None:
    async def _test() -> None:
        # Page 1 contains a viable seller @ 88,599 (> floor 88,000)
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "results": [
                {
                    "title": "Haier 120-316S6",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": "Tech House"},
                },
                {
                    "title": "Haier 120-316S6",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "88,599"},
                    "vendor": {"name": "Kia Chahiye"},
                },
            ],
            "count": 100,  # Even though count is 100, viable seller is already found!
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = resp_p1

        result = await scrape_alfamall(
            mock_session, "120-316S6", "120-316S6", floor_price=88000.0
        )
        assert result.is_success is True
        # Should NOT call page 2! Zero unnecessary latency
        assert mock_session.get.call_count == 1

    asyncio.run(_test())


def test_deduplicate_offers_tracks_duplicate_counts() -> None:
    from pricing_engine.models import ScrapedOffer
    from pricing_engine.scraper import deduplicate_offers

    raw_offers = [
        ScrapedOffer("Tech House", 81500.0, False, "Title 1"),
        ScrapedOffer("Tech House", 81500.0, False, "Title 2"),
        ScrapedOffer("Tech House", 81500.0, False, "Title 3"),
        ScrapedOffer("Tech House", 85000.0, False, "Title 4"),
        ScrapedOffer("Kia Chahiye", 88599.0, False, "Title 5"),
    ]

    deduped = deduplicate_offers(raw_offers)
    assert len(deduped) == 3

    th_81500 = next(o for o in deduped if o.vendor_name == "Tech House" and o.price == 81500.0)
    assert th_81500.duplicate_count == 3

    th_85000 = next(o for o in deduped if o.vendor_name == "Tech House" and o.price == 85000.0)
    assert th_85000.duplicate_count == 1

    kc = next(o for o in deduped if o.vendor_name == "Kia Chahiye")
    assert kc.duplicate_count == 1



def test_subfloor_probe_skips_when_count_less_than_or_equal_to_page_items() -> None:
    async def _test() -> None:
        # Page 1 has 15 items, all sub-floor, but total catalog count is 15 (no more items)
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "results": [
                {
                    "title": f"Haier 120-316S6 Seller {i}",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": f"SubFloor Seller {i}"},
                }
                for i in range(15)
            ],
            "count": 15,
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = resp_p1

        result = await scrape_alfamall(
            mock_session, "120-316S6", "120-316S6", floor_price=88000.0
        )
        assert result.is_success is True
        # Should NOT probe page 2 because count (15) <= len(raw_items) (15)
        assert mock_session.get.call_count == 1

    asyncio.run(_test())


def test_digimall_subfloor_probe_fetches_page_2_when_needed() -> None:
    async def _test() -> None:
        # DigiMall page 1 has 50 sub-floor items, total count = 80
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "results": [
                {
                    "title": f"Haier 120-316S6 Seller {i}",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "80,000"},
                    "vendor": {"name": f"Digi SubFloor {i}"},
                }
                for i in range(50)
            ],
            "count": 80,
        }

        # Page 2 has the viable competitor
        resp_p2 = MagicMock()
        resp_p2.status_code = 200
        resp_p2.json.return_value = {
            "results": [
                {
                    "title": "Haier 120-316S6",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "86,702"},
                    "vendor": {"name": "Electronics World"},
                }
            ],
            "count": 80,
        }

        mock_session = AsyncMock()
        mock_session.get.side_effect = [resp_p1, resp_p2]

        result = await scrape_digimall(
            mock_session, "120-316S6", "120-316S6", floor_price=86307.0
        )
        assert result.is_success is True
        assert mock_session.get.call_count == 2
        p2_call = mock_session.get.call_args_list[1].kwargs.get("params") or {}
        assert p2_call.get("page") == "2"

        viable = [o for o in result.offers if o.price == 86702]
        assert len(viable) == 1
        assert viable[0].vendor_name == "Electronics World"

    asyncio.run(_test())



