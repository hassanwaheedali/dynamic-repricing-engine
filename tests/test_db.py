import asyncio
from unittest.mock import AsyncMock, MagicMock

from pricing_engine.db import SupabaseClient


def test_supabase_client_unconfigured_graceful_fallback() -> None:
    """When credentials are not set, client should not crash and return empty defaults."""

    async def _test() -> None:
        client = SupabaseClient(url="", key="")
        assert client.is_configured is False

        capacities = await client.fetch_approved_capacities()
        assert capacities == []

        synonyms = await client.fetch_approved_synonyms()
        assert synonyms == []

        recorded = await client.record_observations_batch(
            [
                {
                    "brand": "Haier",
                    "category": "WASHING_MACHINE",
                    "anchor_model": "120-826S6",
                    "target_residual": "GC",
                    "candidate_residual": "GLASS DOOR",
                    "vendor_name": "Vendor A",
                    "normalized_merchant": "vendora",
                    "raw_title": "Haier 120-826S6 Glass Door",
                }
            ]
        )
        assert recorded == 0

    asyncio.run(_test())


def test_supabase_client_fetches_approved_capacities() -> None:
    """When configured, client calls Supabase REST endpoint for capacity registry."""

    async def _test() -> None:
        client = SupabaseClient(url="https://mock.supabase.co", key="mock-anon-key")
        assert client.is_configured is True

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"brand": "DAWLANCE", "code": "30", "tonnage": "1.5", "status": "APPROVED"}
        ]

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp
        client._session = mock_session

        caps = await client.fetch_approved_capacities(brand="Dawlance")
        assert len(caps) == 1
        assert caps[0]["code"] == "30"
        assert mock_session.get.call_count == 1
        url_called = mock_session.get.call_args[0][0]
        assert "capacity_registry" in url_called
        assert "brand=eq.DAWLANCE" in url_called

    asyncio.run(_test())


def test_supabase_client_fetches_approved_synonyms_with_category_isolation() -> None:
    """Client filters synonyms by both brand and category to maintain category isolation."""

    async def _test() -> None:
        client = SupabaseClient(url="https://mock.supabase.co", key="mock-anon-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "brand": "HAIER",
                "category": "WASHING_MACHINE",
                "tag": "GC",
                "alias": "GLASS DOOR",
                "status": "APPROVED",
            }
        ]

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp
        client._session = mock_session

        syns = await client.fetch_approved_synonyms(brand="Haier", category="Washing_Machine")
        assert len(syns) == 1
        assert syns[0]["tag"] == "GC"
        url_called = mock_session.get.call_args[0][0]
        assert "synonym_registry" in url_called
        assert "category=eq.WASHING_MACHINE" in url_called

    asyncio.run(_test())


def test_supabase_client_batch_records_observations_without_n_plus_one() -> None:
    """Client posts batch observation payload in a single HTTP POST request."""

    async def _test() -> None:
        client = SupabaseClient(url="https://mock.supabase.co", key="mock-anon-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = [{"id": "1"}, {"id": "2"}]

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_resp
        client._session = mock_session

        batch = [
            {
                "brand": "HAIER",
                "category": "WASHING_MACHINE",
                "anchor_model": "120-826S6",
                "target_residual": "GC",
                "candidate_residual": "GLASS DOOR",
                "vendor_name": "Vendor A",
                "normalized_merchant": "vendora",
                "raw_title": "Haier 120-826S6 Glass Door",
            },
            {
                "brand": "HAIER",
                "category": "WASHING_MACHINE",
                "anchor_model": "120-826S6",
                "target_residual": "GC",
                "candidate_residual": "GLASS COVER",
                "vendor_name": "Vendor B",
                "normalized_merchant": "vendorb",
                "raw_title": "Haier 120-826S6 Glass Cover",
            },
        ]

        recorded = await client.record_observations_batch(batch)
        assert recorded == 2
        assert mock_session.post.call_count == 1
        post_args = mock_session.post.call_args
        assert "learning_observations" in post_args[0][0]
        assert len(post_args[1]["json"]) == 2
        assert post_args[1]["headers"]["Prefer"] == "resolution=ignore-duplicates"

    asyncio.run(_test())


def test_supabase_client_handles_network_error_gracefully() -> None:
    """When network raises exception, client catches it and returns empty results."""

    async def _test() -> None:
        client = SupabaseClient(url="https://mock.supabase.co", key="mock-anon-key")

        mock_session = AsyncMock()
        mock_session.get.side_effect = RuntimeError("Connection refused")
        mock_session.post.side_effect = RuntimeError("Connection timeout")
        client._session = mock_session

        assert await client.fetch_approved_capacities() == []
        assert await client.fetch_approved_synonyms() == []
        assert await client.record_observations_batch([{"dummy": "data"}]) == 0

    asyncio.run(_test())
