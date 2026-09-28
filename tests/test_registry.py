import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from pricing_engine.registry import InMemoryRegistry


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    InMemoryRegistry.reset_to_defaults()


def test_registry_seed_defaults_are_available_immediately() -> None:
    """Registry should contain standard seed capacities and synonyms right out of the box."""
    # Universal AC
    assert InMemoryRegistry.get_tonnage(code="18", brand="Gree") == "1.5"
    assert InMemoryRegistry.get_tonnage(code="24", brand="Haier") == "2"

    # Dawlance AC custom codes
    assert InMemoryRegistry.get_tonnage(code="10", brand="Dawlance") == "0.75"
    assert InMemoryRegistry.get_tonnage(code="15", brand="Dawlance") == "1"
    assert InMemoryRegistry.get_tonnage(code="30", brand="Dawlance") == "1.5"

    # Seed synonyms for Haier washing machine
    assert (
        InMemoryRegistry.get_canonical_tag(
            alias="GLASS DOOR", brand="Haier", category="WASHING_MACHINE"
        )
        == "GC"
    )
    assert InMemoryRegistry.are_synonyms(
        "GC", "GLASS DOOR", brand="Haier", category="WASHING_MACHINE"
    )


def test_registry_lookup_latency_is_under_microsecond() -> None:
    """RAM cache lookup must execute in < 0.01ms to ensure zero matching latency."""
    start = time.perf_counter()
    for _ in range(10_000):
        _ = InMemoryRegistry.get_tonnage("30", "Dawlance")
        _ = InMemoryRegistry.are_synonyms(
            "GC", "GLASS DOOR", brand="Haier", category="WASHING_MACHINE"
        )
    duration = time.perf_counter() - start
    avg_call_ms = (duration / 20_000) * 1000
    assert avg_call_ms < 0.01, f"Lookup took {avg_call_ms:.5f}ms, expected <0.01ms"


def test_registry_load_from_db_merges_cloud_knowledge() -> None:
    """load_from_db asynchronously fetches from SupabaseClient and populates RAM cache."""

    async def _test() -> None:
        mock_client = AsyncMock()
        mock_client.is_configured = True
        # Future code '14' -> 1.0 Ton learned from market
        mock_client.fetch_approved_capacities.return_value = [
            {"brand": "DAWLANCE", "code": "14", "tonnage": "1.0", "status": "APPROVED"}
        ]
        mock_client.fetch_approved_synonyms.return_value = [
            {
                "brand": "DAWLANCE",
                "category": "AIR_CONDITIONER",
                "tag": "CHROME",
                "alias": "CHROME PRO",
                "status": "APPROVED",
            }
        ]

        await InMemoryRegistry.load_from_db(mock_client)

        # Discovered code '14' is now instantly available in RAM!
        assert InMemoryRegistry.get_tonnage(code="14", brand="Dawlance") == "1.0"
        assert InMemoryRegistry.are_synonyms(
            "CHROME", "CHROME PRO", brand="Dawlance", category="AIR_CONDITIONER"
        )

    asyncio.run(_test())


def test_registry_hot_reload_without_restart() -> None:
    """hot_reload updates RAM cache dynamically in-place."""
    assert InMemoryRegistry.get_tonnage("99", "Dawlance") is None

    InMemoryRegistry.hot_reload(
        new_capacities=[{"brand": "DAWLANCE", "code": "99", "tonnage": "5.0"}]
    )

    assert InMemoryRegistry.get_tonnage("99", "Dawlance") == "5.0"


def test_registry_category_isolation_prevents_cross_contamination() -> None:
    """GC in Washing Machine must NOT be considered synonym in Refrigerator or AC."""
    # In Washing Machine, GC == GLASS DOOR
    assert InMemoryRegistry.are_synonyms(
        "GC", "GLASS DOOR", brand="Haier", category="WASHING_MACHINE"
    )
    # In Refrigerator, GC is NOT Glass Door (Category-bounded isolation!)
    assert not InMemoryRegistry.are_synonyms(
        "GC", "GLASS DOOR", brand="Haier", category="REFRIGERATOR"
    )
