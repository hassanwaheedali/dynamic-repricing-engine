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

        result = await scrape_digimall(mock_session, "12AITH21W", "12AITH21W")
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
