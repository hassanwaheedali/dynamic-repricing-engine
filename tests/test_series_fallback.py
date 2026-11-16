"""Model-first retrieval, bounded series fallback, and missing-suffix regressions."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from pricing_engine.matcher import referee_match

MIDEA = "Midea MSEZ1B-12HRFN1-QC2 1 Ton Titan Series Inverter Wall Mounted Split Air Conditioner"
SAMSUNG = "Samsung 55Q7FAA 55 Inch Qled Smart Led TV"


def listing(title: str, *, api_brand: str = "Midea", price: int = 163599) -> dict:
    return {
        "title": title,
        "sold_out": False,
        "id": title,
        "brand": [{"title": api_brand}],
        "vendor": {"name": "External Seller"},
        "variant_detail": {"discounted_price": str(price)},
    }


def response(items: list[dict]) -> MagicMock:
    result = MagicMock(status_code=200)
    result.json.return_value = {"results": items, "count": len(items)}
    return result


def test_capacity_led_base_model_has_yellow_missing_suffix_fallback() -> None:
    decision = referee_match(SAMSUNG, "Samsung 55 Inch QLED Vision AI Smart TV 55Q7F", "Samsung")
    assert not decision.is_match and decision.is_base_match and decision.match_tier == 2
    assert decision.missing_modifier and "AA" in decision.missing_modifier
    assert decision.compatibility_notice and "FALLBACK MODEL" in decision.compatibility_notice


def test_model_queries_include_structured_base_before_series() -> None:
    from pricing_engine.digi_discovery import generate_digimall_plan
    from pricing_engine.matcher import generate_search_patterns

    patterns = generate_search_patterns(SAMSUNG, "Samsung")
    assert "55Q7F" in patterns["tier_2"]
    plan = generate_digimall_plan(SAMSUNG, "Samsung")
    assert plan.branches[0].queries[0] == "55Q7FAA"
    assert "55Q7F" in plan.branches[0].queries


@pytest.mark.parametrize("model", ["55Q7", "55Q70F", "55Q7FBB", "65Q7F"])
def test_display_base_fallback_keeps_identity_and_capacity(model: str) -> None:
    decision = referee_match(SAMSUNG, f"Samsung 55 Inch Smart QLED TV {model}", "Samsung")
    assert not decision.is_match and not decision.is_base_match


def test_clear_product_brand_survives_bad_marketplace_brand_tag() -> None:
    from pricing_engine.scraper import _parse_offers_with_tiers

    raw = listing("Midea Titan 1 Ton Inverter AC MSEZ1B-12 HRFN1-QC2", api_brand="Other")
    parsed = _parse_offers_with_tiers([raw], "MSEZ1B-12HRFN1-QC2", "Midea", MIDEA)
    assert parsed[0] and not parsed[6]


@pytest.mark.parametrize(
    "title",
    [
        "Midea Xtreme 1 Ton Inverter Split AC MSEF1C-12HRFN1-QC2",
        "Midea Titanium 1 Ton Inverter Split AC",
        "Haier Titan 1 Ton Inverter Split AC",
        "Midea Titan 1.5 Ton Inverter Split AC MSEZ1C-18HRFN1-QC2",
        "Midea Titan 1 Ton Non-Inverter Split AC",
        "Midea Titan 1 Ton Inverter Window AC",
        "Midea Titan 1 Ton Inverter Washing Machine",
        "Midea Titan Inverter Split AC",
    ],
)
def test_series_fallback_requires_same_brand_whole_series_and_capacity(title: str) -> None:
    from pricing_engine.series_fallback import referee_series_match

    decision = referee_series_match(MIDEA, title, "Midea")
    assert not decision.is_match and not decision.is_base_match and decision.match_tier is None


def test_different_model_same_series_is_rejected_by_approved_sku_policy() -> None:
    from pricing_engine.series_fallback import referee_series_match

    title = "Midea Titan 1 Ton Inverter Split AC MSEZ1D-12HRFN1-QC2"
    assert not referee_match(MIDEA, title, "Midea").is_match
    decision = referee_series_match(MIDEA, title, "Midea")
    # Approved correction: an explicit conflicting SKU cannot enter series-only fallback.
    assert not decision.is_base_match and not decision.is_match and decision.match_tier is None


@pytest.mark.parametrize("platform", ["alfa", "digi"])
def test_series_search_runs_only_after_model_queries_fail(platform: str) -> None:
    async def run() -> None:
        from pricing_engine.digi_discovery import generate_digimall_plan
        from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall, scrape_digimall

        clear_scraper_cache()
        session = AsyncMock()

        async def get(*args: object, **kwargs: object) -> MagicMock:
            query = kwargs["params"]["q"]
            if query == "Midea Titan 1 Ton":
                return response([listing("Midea Titan 1 Ton Inverter Split AC")])
            return response([])

        session.get.side_effect = get
        if platform == "alfa":
            result = await scrape_alfamall(
                session,
                {"tier_1": ["MSEZ1B-12HRFN1-QC2"]},
                "MSEZ1B-12HRFN1-QC2",
                brand="Midea",
                target_desc=MIDEA,
            )
        else:
            result = await scrape_digimall(
                session,
                generate_digimall_plan(MIDEA, "Midea"),
                "MSEZ1B-12HRFN1-QC2",
                brand="Midea",
                target_desc=MIDEA,
            )
        queries = [call.kwargs["params"]["q"] for call in session.get.call_args_list]
        assert queries[-1] == "Midea Titan 1 Ton"
        assert result.offers and all(offer.match_tier == 2 for offer in result.offers)
        assert result.compatibility_notice and "Series" in result.compatibility_notice
        assert result.active_modifier_fallback

    asyncio.run(run())


@pytest.mark.parametrize("platform", ["alfa", "digi"])
def test_matching_model_never_starts_series_search(platform: str) -> None:
    async def run() -> None:
        from pricing_engine.digi_discovery import generate_digimall_plan
        from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall, scrape_digimall

        clear_scraper_cache()
        session = AsyncMock()
        session.get.return_value = response(
            [listing("Midea Titan 1 Ton Inverter AC MSEZ1B-12 HRFN1-QC2")]
        )
        if platform == "alfa":
            result = await scrape_alfamall(
                session,
                {"tier_1": ["MSEZ1B-12HRFN1-QC2"]},
                "MSEZ1B-12HRFN1-QC2",
                brand="Midea",
                target_desc=MIDEA,
            )
        else:
            result = await scrape_digimall(
                session,
                generate_digimall_plan(MIDEA, "Midea"),
                "MSEZ1B-12HRFN1-QC2",
                brand="Midea",
                target_desc=MIDEA,
            )
        assert result.offers
        assert all(
            call.kwargs["params"]["q"] != "Midea Titan 1 Ton" for call in session.get.call_args_list
        )

    asyncio.run(run())


@pytest.mark.parametrize("platform", ["alfa", "digi"])
def test_same_query_can_be_revalidated_for_series_without_another_http_request(
    platform: str,
) -> None:
    async def run() -> None:
        from pricing_engine.digi_discovery import DigiQueryBranch, DigiQueryPlan
        from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall, scrape_digimall

        clear_scraper_cache()
        session = AsyncMock()
        session.get.return_value = response([listing("Midea Titan 1 Ton Inverter Split AC")])
        query = "Midea Titan 1 Ton"
        if platform == "alfa":
            result = await scrape_alfamall(
                session, {"tier_1": [query]}, "MSEZ1B-12HRFN1-QC2", brand="Midea", target_desc=MIDEA
            )
        else:
            plan = DigiQueryPlan((DigiQueryBranch(MIDEA, "MSEZ1B-12HRFN1-QC2", (query,)),))
            result = await scrape_digimall(
                session, plan, "MSEZ1B-12HRFN1-QC2", brand="Midea", target_desc=MIDEA
            )
        assert result.offers and result.offers[0].match_tier == 2
        assert session.get.call_count == 1

    asyncio.run(run())


@pytest.mark.parametrize("platform", ["alfa", "digi"])
def test_failed_model_request_does_not_trigger_series_search(platform: str) -> None:
    async def run() -> None:
        from pricing_engine.digi_discovery import generate_digimall_plan
        from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall, scrape_digimall

        clear_scraper_cache()
        session = AsyncMock()
        failed = response([])
        failed.status_code = 503
        session.get.return_value = failed
        if platform == "alfa":
            result = await scrape_alfamall(
                session,
                {"tier_1": ["MSEZ1B-12HRFN1-QC2"]},
                "MSEZ1B-12HRFN1-QC2",
                brand="Midea",
                target_desc=MIDEA,
                max_retries=1,
            )
        else:
            result = await scrape_digimall(
                session,
                generate_digimall_plan(MIDEA, "Midea"),
                "MSEZ1B-12HRFN1-QC2",
                brand="Midea",
                target_desc=MIDEA,
                max_retries=1,
            )
        assert not result.is_success
        assert all(
            call.kwargs["params"]["q"] != "Midea Titan 1 Ton" for call in session.get.call_args_list
        )

    asyncio.run(run())


def test_series_query_still_prefers_an_exact_model_over_an_approximate_model() -> None:
    async def run() -> None:
        from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall

        clear_scraper_cache()
        session = AsyncMock()

        async def get(*args: object, **kwargs: object) -> MagicMock:
            if kwargs["params"]["q"] == "Midea Titan 1 Ton":
                return response(
                    [
                        listing("Midea Titan 1 Ton Inverter Split AC MSEZ1B-12 HRFN1-QC2"),
                        listing(
                            "Midea Titan 1 Ton Inverter Split AC MSEZ1D-12HRFN1-QC2", price=150000
                        ),
                    ]
                )
            return response([])

        session.get.side_effect = get
        result = await scrape_alfamall(
            session,
            {"tier_1": ["MSEZ1B-12HRFN1-QC2"]},
            "MSEZ1B-12HRFN1-QC2",
            brand="Midea",
            target_desc=MIDEA,
        )
        assert len(result.offers) == 1
        assert result.offers[0].match_tier == 1 and result.offers[0].price == 163599

    asyncio.run(run())


def test_extra_model_tiers_finish_before_series_fallback() -> None:
    async def run() -> None:
        from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall

        clear_scraper_cache()
        session = AsyncMock()
        session.get.return_value = response([])
        await scrape_alfamall(
            session,
            {
                "tier_1": ["model-1"],
                "series_fallback": ["Midea Titan 1 Ton"],
                "extra_model_tier": ["model-2"],
            },
            "MSEZ1B-12HRFN1-QC2",
            brand="Midea",
            target_desc=MIDEA,
        )
        assert [call.kwargs["params"]["q"] for call in session.get.call_args_list] == [
            "model-1",
            "model-2",
            "Midea Titan 1 Ton",
        ]

    asyncio.run(run())


@pytest.mark.parametrize("query", ["model-1", {"tier_1": ["model-1"], "tier_2": ["model-2"]}])
def test_explicit_digi_model_queries_use_same_final_fallback(query: object) -> None:
    async def run() -> None:
        from pricing_engine.scraper import clear_scraper_cache, scrape_digimall

        clear_scraper_cache()
        session = AsyncMock()

        async def get(*args: object, **kwargs: object) -> MagicMock:
            return (
                response([listing("Midea Titan 1 Ton Inverter Split AC")])
                if kwargs["params"]["q"] == "Midea Titan 1 Ton"
                else response([])
            )

        session.get.side_effect = get
        result = await scrape_digimall(
            session, query, "MSEZ1B-12HRFN1-QC2", brand="Midea", target_desc=MIDEA
        )
        assert result.offers and result.compatibility_notice
        assert session.get.call_args_list[-1].kwargs["params"]["q"] == "Midea Titan 1 Ton"

    asyncio.run(run())


@pytest.mark.parametrize("platform", ["alfa", "digi"])
def test_active_own_model_prevents_series_widening(platform: str) -> None:
    async def run() -> None:
        from pricing_engine.digi_discovery import generate_digimall_plan
        from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall, scrape_digimall

        clear_scraper_cache()
        raw = listing("Midea Titan 1 Ton Inverter AC MSEZ1B-12 HRFN1-QC2")
        raw["vendor"] = {"name": "Kia Chahiye Pvt Ltd"}
        session = AsyncMock()
        session.get.return_value = response([raw])
        query = (
            {"tier_1": ["MSEZ1B-12HRFN1-QC2"]}
            if platform == "alfa"
            else generate_digimall_plan(MIDEA, "Midea")
        )
        scraper = scrape_alfamall if platform == "alfa" else scrape_digimall
        result = await scraper(
            session, query, "MSEZ1B-12HRFN1-QC2", brand="Midea", target_desc=MIDEA
        )
        assert result.own_offers and not result.offers
        assert "Midea Titan 1 Ton" not in result.executed_queries

    asyncio.run(run())


def test_series_rules_work_without_a_known_brand_or_model() -> None:
    from pricing_engine.series_fallback import build_series_search, referee_series_match

    target = "Acme AX-1200 1.5 Ton Aurora Series Inverter Split AC"
    search = build_series_search(target, "Acme")
    assert search is not None and search.query == "Acme Aurora 1.5 Ton"
    assert referee_series_match(
        search, "Acme Aurora 1.5 Ton Inverter Split AC", "Acme"
    ).is_base_match
    assert build_series_search("Acme AX-1200 1.5 Ton Inverter Split AC", "Acme") is None
    assert build_series_search("Acme AX-1200 Aurora Series Inverter Split AC", "Acme") is None


@pytest.mark.parametrize("mode", ["pricing", "range"])
def test_fallbacks_reach_both_pipeline_exports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Mock HTTP and DB only; run real ingestion, discovery, matching and exports."""
    import pandas as pd
    from openpyxl import load_workbook

    from pricing_engine.pipeline import default_learner, run_pipeline
    from pricing_engine.range_pipeline import run_range_pipeline

    catalog = tmp_path / "catalog.csv"
    pd.DataFrame(
        [
            {"S.NO": 1, "Brand": "Samsung", "Name": SAMSUNG, "Net Price": 150000},
            {"S.NO": 2, "Brand": "Midea", "Name": MIDEA, "Net Price": 100000},
        ]
    ).to_csv(catalog, index=False)
    titles = {
        "55Q7F": "Samsung 55 Inch QLED Smart TV 55Q7F",
        # Series-only pricing now requires omitted SKU, not a different stated SKU.
        "Midea Titan 1 Ton": "Midea Titan 1 Ton Inverter Split AC",
    }
    session = AsyncMock()

    async def get(*args: object, **kwargs: object) -> MagicMock:
        query = kwargs["params"]["q"]
        if query not in titles:
            return response([])
        title = titles[query]
        brand = title.split()[0]
        good = listing(title, api_brand=brand, price=210000)
        own = listing(title, api_brand=brand, price=205000)
        own.update(id="own-" + title, vendor={"name": "Kia Chahiye Pvt Ltd"})
        sold = listing(title, api_brand=brand, price=1)
        sold.update(id="sold-" + title, sold_out=True)
        wrong = listing(
            title.replace("55 Inch", "65 Inch").replace("1 Ton", "1.5 Ton"),
            api_brand=brand,
            price=2,
        )
        return response([good, good.copy(), own, sold, wrong])

    session.get.side_effect = get
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    offline_db = MagicMock(is_configured=False, close=AsyncMock())
    learn = MagicMock(wraps=default_learner.buffer_observation)
    monkeypatch.setattr(default_learner, "buffer_observation", learn)
    monkeypatch.setattr("pricing_engine.pipeline.AsyncSession", factory)
    monkeypatch.setattr("pricing_engine.range_pipeline.AsyncSession", factory)
    monkeypatch.setattr("pricing_engine.pipeline.SupabaseClient", lambda: offline_db)
    monkeypatch.setattr(
        "pricing_engine.checkpoint.DEFAULT_CHECKPOINT_DIR", tmp_path / "checkpoints"
    )
    monkeypatch.setattr("pricing_engine.range_pipeline.RANGE_STAGGER_SECONDS", 0)
    out_dir = tmp_path / "out"
    if mode == "pricing":
        frame = asyncio.run(run_pipeline(catalog, export_dir=out_dir, verbose=False, resume=False))
    else:
        frame = asyncio.run(run_range_pipeline(catalog, export_dir=out_dir, verbose=False))
    assert list(frame["S.NO"]) == [1, 2] and frame.columns[0] == "S.NO"
    for platform in ("Alfa", "Digi"):
        assert frame[f"Minimum Price {platform}"].astype(int).tolist() == [210000, 210000]
        assert frame[f"Maximum Price {platform}"].astype(int).tolist() == [210000, 210000]
        if mode == "pricing":
            assert frame[f"Final Price {platform}"].astype(int).between(1, 209999).all()
            assert frame[f"{platform} Reason"].str.contains("FALLBACK MODEL").all()
            assert not frame[f"{platform} Reason"].str.contains("Monopoly").any()
        else:
            assert frame[f"{platform} Offers Found"].astype(int).tolist() == [1, 1]
    assert any(
        call.kwargs["params"]["q"] == "Midea Titan 1 Ton" for call in session.get.call_args_list
    )
    filename = "catalog_repriced_latest.csv" if mode == "pricing" else "catalog_range_latest.csv"
    exported = list(out_dir.rglob(filename))
    assert len(exported) == 1
    saved = pd.read_csv(exported[0])
    assert saved["Minimum Price Digi"].tolist() == [210000, 210000]
    workbook_path = exported[0].with_suffix(".xlsx")
    if not workbook_path.exists():
        workbook_path = next(out_dir.rglob(filename.replace(".csv", ".xlsx")))
    workbook = load_workbook(workbook_path)
    if mode == "pricing":
        learn.assert_not_called()
        sheet = workbook.active
        assert sheet is not None
        reason_column = next(cell.column for cell in sheet[1] if cell.value == "Digi Reason")
        assert sheet.cell(2, reason_column).fill.fgColor.rgb.endswith("FFF9C4")
        assert sheet.cell(3, reason_column).fill.fgColor.rgb.endswith("FFF9C4")
    workbook.close()
