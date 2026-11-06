"""DigiMall-specific retrieval policy regressions (all HTTP is mocked)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pricing_engine.digi_discovery import generate_digimall_plan
from pricing_engine.scraper import clear_scraper_cache, scrape_digimall


@pytest.fixture(autouse=True)
def reset_cache() -> None:
    clear_scraper_cache()


def item(price: int, index: int = 0, *, title: str = "Haier 120-316S6", sold: bool = False) -> dict:
    return {
        "id": str(index),
        "title": title,
        "sold_out": sold,
        "variant_detail": {"discounted_price": str(price)},
        "vendor": {"name": f"External Seller {index}"},
    }


def response(items: list[dict], count: object = 1, status: int = 200) -> MagicMock:
    result = MagicMock(status_code=status)
    result.json.return_value = {"results": items, "count": count}
    return result


def test_required_pages_are_fetched_despite_viable_page_one() -> None:
    async def run() -> None:
        session = AsyncMock()
        pages = {
            1: [item(179999, i) for i in range(100)],
            2: [item(178913, 100 + i) for i in range(100)],
            3: [item(174565, 200)],
        }

        async def get(*args: object, **kwargs: object) -> MagicMock:
            return response(pages[int(kwargs["params"]["page"])], 201)

        session.get.side_effect = get
        result = await scrape_digimall(
            session, "120-316S6", "120-316S6", brand="Haier", floor_price=100000
        )
        assert {c.kwargs["params"]["page"] for c in session.get.call_args_list} == {"1", "2", "3"}
        assert result.offers[0].price == 174565
        assert result.coverage_status == "COMPLETE"
        assert len(result.lowest_offers) == 5
        assert len(result.offers) == 201

    asyncio.run(run())


def test_failed_required_page_preserves_observed_offers_as_incomplete() -> None:
    async def run() -> None:
        session = AsyncMock()
        session.get.side_effect = [
            response([item(80000, i) for i in range(100)], 101),
            response([], 101, 500),
        ]
        result = await scrape_digimall(
            session, "120-316S6", "120-316S6", brand="Haier", floor_price=100000, max_retries=1
        )
        assert result.is_success
        assert result.offers[0].price == 80000
        assert result.coverage_status == "INCOMPLETE"
        assert not result.pagination_complete

    asyncio.run(run())


def test_available_duplicate_survives_sold_out_first_copy() -> None:
    async def run() -> None:
        session = AsyncMock()
        session.get.return_value = response([item(179999, sold=True), item(179999)], 2)
        result = await scrape_digimall(session, "120-316S6", "120-316S6", brand="Haier")
        assert len(result.offers) == 1
        assert not result.offers[0].is_sold_out

    asyncio.run(run())


def test_model_first_queries_preserve_variant_and_exclude_brand() -> None:
    plan = generate_digimall_plan("Gree 12AITH21W-T3 Inverter AC", "Gree")
    assert plan.branches[0].queries[0] == "12AITH21W-T3"
    assert plan.branches[0].queries[1] == "12AITH21W T3"
    assert all("gree" not in q.lower() for q in plan.branches[0].queries)
    assert len(plan.branches[0].queries) <= 3


@pytest.mark.parametrize("brand", ["", "unknown", "N/A"])
def test_planner_requires_catalog_brand(brand: str) -> None:
    with pytest.raises(ValueError, match="Brand"):
        generate_digimall_plan("12AITH21W", brand)


def test_planner_requires_numeric_model() -> None:
    with pytest.raises(ValueError, match="model"):
        generate_digimall_plan("Acme generic appliance", "Acme")


def test_partial_price_is_provisional_without_changing_the_calculation() -> None:
    from pricing_engine.calculator import calculate_floors
    from pricing_engine.evaluator import evaluate_digi_pricing, evaluate_market_range
    from pricing_engine.models import ScrapedOffer, ScrapeResult
    from pricing_engine.range_pipeline import determine_range_alert

    offers = [ScrapedOffer("External", 179999, False, "Haier 120-316S6")]
    floors = calculate_floors(150000)
    complete = evaluate_digi_pricing(floors, offers)
    partial = ScrapeResult(
        offers=offers,
        pagination_complete=False,
        coverage_status="INCOMPLETE",
        coverage_detail="Page 2 timed out",
    )
    provisional = evaluate_digi_pricing(floors, partial)
    assert provisional.final_price == complete.final_price
    assert provisional.status == "Provisional Price"
    assert provisional.coverage_status == "INCOMPLETE"
    assert determine_range_alert(evaluate_market_range(partial)) == "INCOMPLETE_DISCOVERY"


@pytest.mark.parametrize("coverage", ["UNKNOWN", "INCOMPLETE"])
def test_noncomplete_empty_result_never_becomes_monopoly(coverage: str) -> None:
    from pricing_engine.calculator import calculate_floors
    from pricing_engine.evaluator import evaluate_digi_pricing
    from pricing_engine.models import ScrapeResult

    result = evaluate_digi_pricing(
        calculate_floors(90000), ScrapeResult(coverage_status=coverage, pagination_complete=False)
    )
    assert result.final_price is None
    assert "Monopoly" not in result.status


@pytest.mark.parametrize("count", [0, 1, 99, 100, 101, 200, 201, 300, 301])
def test_count_boundaries_and_cap(count: int) -> None:
    async def run() -> None:
        session = AsyncMock()

        async def get(*args: object, **kwargs: object) -> MagicMock:
            page = int(kwargs["params"]["page"])
            start = (page - 1) * 100
            return response(
                [item(170000 + i, i) for i in range(start, min(start + 100, count))], count
            )

        session.get.side_effect = get
        result = await scrape_digimall(session, "120-316S6", "120-316S6", brand="Haier")
        assert session.get.call_count == min(3, max(1, (count + 99) // 100))
        assert result.coverage_status == ("CAPPED" if count > 300 else "COMPLETE")
        assert result.pagination_complete == (count <= 300)

    asyncio.run(run())


def test_brand_absence_on_page_two_does_not_hide_page_three() -> None:
    async def run() -> None:
        session = AsyncMock()

        async def get(*args: object, **kwargs: object) -> MagicMock:
            page = int(kwargs["params"]["page"])
            if page == 2:
                return response(
                    [item(50000, i + 100, title="Gree 12AITH21W") for i in range(100)], 201
                )
            return response(
                [
                    item(180000 if page == 1 else 174565, i + (page - 1) * 100)
                    for i in range(100 if page == 1 else 1)
                ],
                201,
            )

        session.get.side_effect = get
        result = await scrape_digimall(session, "120-316S6", "120-316S6", brand="Haier")
        assert result.offers[0].price == 174565
        assert result.coverage_status == "COMPLETE"

    asyncio.run(run())


def test_planned_primary_success_skips_fallback_but_not_pages() -> None:
    async def run() -> None:
        plan = generate_digimall_plan("Haier HWM 120-316S6 Washing Machine", "Haier")
        session = AsyncMock()
        session.get.return_value = response([item(179999)], 1)
        result = await scrape_digimall(session, plan, "120-316S6", brand="Haier")
        assert result.executed_queries == [plan.branches[0].queries[0]]
        assert session.get.call_count == 1

    asyncio.run(run())


def test_planned_no_matches_tries_alternate_and_rechecks_compatibility() -> None:
    async def run() -> None:
        plan = generate_digimall_plan("Haier HWM 120-316S6 Washing Machine", "Haier")
        session = AsyncMock()
        session.get.side_effect = [
            response([item(10000, title="Gree 12AITH21W")], 1),
            response([item(179999)], 1),
        ]
        result = await scrape_digimall(session, plan, "120-316S6", brand="Haier")
        assert result.executed_queries == list(plan.branches[0].queries[:2])
        assert [o.price for o in result.offers] == [179999]

    asyncio.run(run())


def test_page_cache_retries_missing_page_and_recomputes_coverage() -> None:
    from pricing_engine.digi_transport import DigiDiscoveryContext

    async def run() -> None:
        context = DigiDiscoveryContext()
        session = AsyncMock()
        session.get.side_effect = [
            response([item(180000, i) for i in range(100)], 101),
            response([], 101, 503),
            response([item(174565, 100)], 101),
        ]
        first = await scrape_digimall(
            session, "120-316S6", "120-316S6", brand="Haier", context=context, max_retries=1
        )
        second = await scrape_digimall(
            session, "120-316S6", "120-316S6", brand="Haier", context=context, max_retries=1
        )
        assert first.coverage_status == "INCOMPLETE"
        assert second.coverage_status == "COMPLETE"
        assert [c.kwargs["params"]["page"] for c in session.get.call_args_list] == ["1", "2", "2"]
        assert second.offers[0].price == 174565

    asyncio.run(run())


def test_concurrent_queries_share_pages_and_obey_request_limit() -> None:
    from pricing_engine.digi_transport import DigiDiscoveryContext

    async def run() -> None:
        context = DigiDiscoveryContext(2)
        session = AsyncMock()
        active = peak = 0

        async def get(*args: object, **kwargs: object) -> MagicMock:
            nonlocal active, peak
            active += 1
            peak = max(active, peak)
            await asyncio.sleep(0.001)
            active -= 1
            page = int(kwargs["params"]["page"])
            return response(
                [item(180000, (page - 1) * 100 + i) for i in range(100 if page < 3 else 1)], 201
            )

        session.get.side_effect = get
        results = await asyncio.gather(
            *[
                scrape_digimall(session, "120-316S6", "120-316S6", brand="Haier", context=context)
                for _ in range(3)
            ]
        )
        assert session.get.call_count == 3
        assert peak == 2
        assert all(r.coverage_status == "COMPLETE" for r in results)
        assert not context.inflight

    asyncio.run(run())


@pytest.mark.parametrize("count", [None, True, -1, "bad"])
def test_invalid_counts_are_unknown_not_empty_market(count: object) -> None:
    async def run() -> None:
        session = AsyncMock()
        session.get.side_effect = [
            response([item(179999)], count),
            response([], count),
            response([], count),
        ]
        result = await scrape_digimall(session, "120-316S6", "120-316S6", brand="Haier")
        assert result.coverage_status == "UNKNOWN"
        assert session.get.call_count == 3

    asyncio.run(run())


@pytest.mark.parametrize("key", ["count", "total", "total_count"])
def test_count_aliases_accept_digit_strings(key: str) -> None:
    from pricing_engine.digi_transport import parse_total

    assert parse_total({key: "101"}) == 101
    assert parse_total({"count": 0, "total": 101}) == 0


def test_all_failed_requests_keep_the_actual_http_status() -> None:
    async def run() -> None:
        session = AsyncMock()
        session.get.return_value = response([], 0, 503)
        result = await scrape_digimall(session, "120-316S6", "120-316S6", max_retries=1)
        assert not result.is_success
        assert result.status_code == 503
        assert result.coverage_status == "FAILED"

    asyncio.run(run())


def test_missing_initial_count_does_not_hide_conflicting_later_totals() -> None:
    async def run() -> None:
        session = AsyncMock()
        session.get.side_effect = [
            response([item(180000)], None),
            response([item(179000, 1)], 200),
            response([item(178000, 2)], 300),
        ]
        result = await scrape_digimall(session, "120-316S6", "120-316S6")
        assert result.coverage_status == "INCOMPLETE"

    asyncio.run(run())


def test_explicit_dictionary_uses_canonical_tier_order_and_finishes_tier() -> None:
    async def run() -> None:
        session = AsyncMock()
        session.get.return_value = response([item(179999), item(180000, 1)], 2)
        result = await scrape_digimall(
            session,
            {"tier_2": ["broad"], "tier_1": ["first", "second"]},
            "120-316S6",
            exhaustive=False,
        )
        assert result.executed_queries == ["first", "second"]

    asyncio.run(run())


def test_planned_discovery_requires_brand_even_for_constructed_plan() -> None:
    async def run() -> None:
        session = AsyncMock()
        plan = generate_digimall_plan("Haier 120-316S6", "Haier")
        result = await scrape_digimall(session, plan, "120-316S6")
        assert not result.is_success
        assert not session.get.called

    asyncio.run(run())


def test_short_cached_page_can_recover_on_next_call() -> None:
    from pricing_engine.digi_transport import DigiDiscoveryContext

    async def run() -> None:
        context = DigiDiscoveryContext()
        session = AsyncMock()
        session.get.side_effect = [
            response([item(179999)], 2),
            response([item(179999), item(174565, 1)], 2),
        ]
        first = await scrape_digimall(session, "120-316S6", "120-316S6", context=context)
        second = await scrape_digimall(session, "120-316S6", "120-316S6", context=context)
        assert first.coverage_status == "INCOMPLETE"
        assert second.coverage_status == "COMPLETE"
        assert second.offers[0].price == 174565

    asyncio.run(run())


def test_cancelled_shared_waiter_does_not_cancel_other_customer() -> None:
    from pricing_engine.digi_transport import DigiDiscoveryContext

    async def run() -> None:
        context = DigiDiscoveryContext(1)
        session = AsyncMock()
        started, release = asyncio.Event(), asyncio.Event()

        async def get(*args: object, **kwargs: object) -> MagicMock:
            started.set()
            await release.wait()
            return response([item(179999)], 1)

        session.get.side_effect = get
        first = asyncio.create_task(
            scrape_digimall(session, "120-316S6", "120-316S6", context=context)
        )
        await started.wait()
        second = asyncio.create_task(
            scrape_digimall(session, "120-316S6", "120-316S6", context=context)
        )
        await asyncio.sleep(0)
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)
        release.set()
        assert (await second).coverage_status == "COMPLETE"
        assert session.get.call_count == 1
        assert not context.inflight
        assert not context.semaphore.locked()

    asyncio.run(run())


def test_last_waiter_cancellation_releases_request_and_inflight_entry() -> None:
    from pricing_engine.digi_transport import DigiDiscoveryContext

    async def run() -> None:
        context = DigiDiscoveryContext(1)
        session = AsyncMock()
        started = asyncio.Event()

        async def get(*args: object, **kwargs: object) -> MagicMock:
            started.set()
            await asyncio.Event().wait()
            return response([], 0)

        session.get.side_effect = get
        task = asyncio.create_task(
            scrape_digimall(session, "120-316S6", "120-316S6", context=context)
        )
        await started.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert not context.inflight
        assert not context.waiters
        assert not context.semaphore.locked()

    asyncio.run(run())


def test_raw_cache_is_target_and_parameter_independent() -> None:
    from dataclasses import replace

    from pricing_engine.digi_transport import DigiDiscoveryContext
    from pricing_engine.scraper import DIGIMALL_CONFIG

    async def run() -> None:
        context = DigiDiscoveryContext()
        session = AsyncMock()
        session.get.return_value = response([item(179999)], 1)
        matched = await scrape_digimall(
            session, "120-316S6", "120-316S6", context=context, brand="Haier"
        )
        foreign = await scrape_digimall(
            session, "120-316S6", "120-316S6", context=context, brand="Gree"
        )
        assert matched.offers and not foreign.offers
        assert session.get.call_count == 1
        changed = replace(
            DIGIMALL_CONFIG, base_params={**DIGIMALL_CONFIG.base_params, "storefront": "24"}
        )
        await context.fetch(changed, session, "120-316S6", 1, 15, 1)
        assert session.get.call_count == 2

    asyncio.run(run())


def test_retry_uses_increasing_timeout_without_refetching_successful_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pricing_engine.digi_transport import DigiDiscoveryContext

    monkeypatch.setattr("pricing_engine.digi_transport.retry_delay", lambda *args: 0)

    async def run() -> None:
        context = DigiDiscoveryContext(1)
        session = AsyncMock()
        session.get.side_effect = [response([], 0, 503), response([item(179999)], 1)]
        result = await scrape_digimall(
            session, "120-316S6", "120-316S6", context=context, max_retries=2
        )
        assert result.coverage_status == "COMPLETE"
        assert [c.kwargs["timeout"] for c in session.get.call_args_list] == [15.0, 20.0]
        assert not context.semaphore.locked()

    asyncio.run(run())


def test_lowest_five_do_not_remove_sixth_viable_offer() -> None:
    from pricing_engine.calculator import calculate_floors
    from pricing_engine.evaluator import evaluate_digi_pricing

    async def run() -> None:
        session = AsyncMock()
        session.get.return_value = response(
            [item(80000 + i, i) for i in range(5)] + [item(100000, 5)], 6
        )
        result = await scrape_digimall(session, "120-316S6", "120-316S6")
        priced = evaluate_digi_pricing(calculate_floors(90000), result)
        assert len(result.lowest_offers) == 5
        assert len(result.offers) == 6
        assert priced.final_price is not None
        assert priced.final_price < 100000
        assert priced.status != "Safe Fallback"

    asyncio.run(run())


def test_each_explicit_model_branch_is_searched() -> None:
    from pricing_engine.digi_discovery import DigiQueryBranch, DigiQueryPlan

    async def run() -> None:
        plan = DigiQueryPlan(
            (
                DigiQueryBranch("Haier 120-316S6", "120-316S6", ("120-316S6",)),
                DigiQueryBranch("Haier 120-826S6", "120-826S6", ("120-826S6",)),
            )
        )
        session = AsyncMock()
        session.get.side_effect = [
            response([item(179999)], 1),
            response([item(180000, 1, title="Haier 120-826S6")], 1),
        ]
        result = await scrape_digimall(session, plan, "120-316S6", brand="Haier")
        assert len(result.executed_queries) == 2
        assert len(result.offers) == 2

    asyncio.run(run())


@pytest.mark.parametrize(
    "payload", [None, [], {"bad": []}, {"results": [None]}, {"results": [{"variant_detail": None}]}]
)
def test_malformed_page_schema_is_failed_not_empty_market(payload: object) -> None:
    async def run() -> None:
        session = AsyncMock()
        raw = MagicMock(status_code=200)
        raw.json.return_value = payload
        session.get.return_value = raw
        result = await scrape_digimall(session, "120-316S6", "120-316S6", max_retries=1)
        assert not result.is_success
        assert result.coverage_status == "FAILED"

    asyncio.run(run())


@pytest.mark.parametrize(
    "message", ["Connection timeout", "Connection reset", "Temporary network error"]
)
def test_network_retries_release_permits_before_backoff(message: str) -> None:
    from unittest.mock import patch

    from pricing_engine.digi_transport import DigiDiscoveryContext

    async def run() -> None:
        context = DigiDiscoveryContext(1)
        session = AsyncMock()
        session.get.side_effect = [RuntimeError(message), response([item(179999)], 1)]

        async def backoff(delay: float) -> None:
            assert delay > 0
            assert not context.semaphore.locked()

        with patch("pricing_engine.digi_transport.asyncio.sleep", side_effect=backoff):
            result = await scrape_digimall(
                session, "120-316S6", "120-316S6", max_retries=2, context=context
            )
        assert result.coverage_status == "COMPLETE"

    asyncio.run(run())


def test_legacy_early_exit_counts_unique_offers_not_duplicate_query_hits() -> None:
    async def run() -> None:
        session = AsyncMock()
        session.get.return_value = response([item(179999)], 1)
        result = await scrape_digimall(
            session,
            {"tier_1": ["first", "second"], "tier_2": ["third"]},
            "120-316S6",
            exhaustive=False,
        )
        assert result.executed_queries == ["first", "second", "third"]

    asyncio.run(run())


def test_legacy_query_tier_metadata_survives_combined_offer_selection() -> None:
    async def run() -> None:
        session = AsyncMock()
        session.get.side_effect = [response([], 0), response([item(179999)], 1)]
        result = await scrape_digimall(
            session, {"tier_1": ["first"], "tier_3": ["third"]}, "120-316S6"
        )
        assert result.matched_tier == "tier_3"
        assert result.tier_summary == {"tier_1": 0, "tier_3": 1}

    asyncio.run(run())


def test_later_total_alone_still_detects_impossible_extra_pages() -> None:
    async def run() -> None:
        session = AsyncMock()
        session.get.side_effect = [
            response([item(180000, i) for i in range(100)], None),
            response([item(179000, i + 100) for i in range(100)], 100),
            response([item(178000, i + 200) for i in range(100)], 100),
        ]
        result = await scrape_digimall(session, "120-316S6", "120-316S6")
        assert result.coverage_status == "INCOMPLETE"

    asyncio.run(run())


def test_timeouts_show_all_retry_attempts_before_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notices: list[str] = []
    monkeypatch.setattr("pricing_engine.scraper._safe_console_print", notices.append)
    monkeypatch.setattr("pricing_engine.digi_transport.retry_delay", lambda *args: 0)

    async def run() -> None:
        session = AsyncMock()
        session.get.side_effect = TimeoutError("Connection timed out")
        result = await scrape_digimall(session, "120-316S6", "120-316S6", max_retries=3)
        assert session.get.call_count == 3
        assert [c.kwargs["timeout"] for c in session.get.call_args_list] == [15, 20, 25]
        assert any("Retry 2/3" in notice for notice in notices)
        assert any("Retry 3/3" in notice for notice in notices)
        assert "Page retrieval failed" in notices[-1]
        assert result.coverage_status == "FAILED"

    asyncio.run(run())
