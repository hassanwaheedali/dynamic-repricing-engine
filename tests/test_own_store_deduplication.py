"""Regression tests for strict own-store compatibility, deduplication, and terminal summary."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import config
from pricing_engine.calculator import calculate_floors
from pricing_engine.digi_discovery import generate_digimall_plan
from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.models import PlatformPricingResult, ScrapedOffer, ScrapeResult
from pricing_engine.pipeline import build_scraped_sellers_table
from pricing_engine.scraper import (
    clear_scraper_cache,
    deduplicate_own_offers,
    scrape_alfamall,
    scrape_digimall,
)


def _mock_response(items: list[dict[str, Any]], total: int | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    payload: dict[str, Any] = {"results": items}
    if total is not None:
        payload["count"] = total
    resp.json.return_value = payload
    return resp


def _render_table_text(tbl: Any) -> str:
    cells: list[str] = []
    for col in tbl.columns:
        for cell in col._cells:
            cells.append(str(cell))
    return " ".join(cells)


class TestStrictOwnStoreCompatibility:
    """Requirement A: Seller identity alone is never enough; product compatibility must hold."""

    def setup_method(self) -> None:
        clear_scraper_cache()

    def test_1_our_seller_exact_compatible_product_is_confirmed_own_store(self) -> None:
        async def _run() -> None:
            items = [
                {
                    "id": "70926143806343970",
                    "handle": "dawlance-9149wb-9-cu-ft-e-chrome-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft E-Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,399"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd", "handle": "kia-chahiye-pvt-ltd"},
                }
            ]
            sess = AsyncMock()
            sess.get.return_value = _mock_response(items)
            res = await scrape_alfamall(
                sess,
                "Dawlance 9149WB",
                "9149WB",
                brand="Dawlance",
                target_desc=(
                    "Dawlance 9149WB E-Chrome 9 Cu Ft Non-Inverter Top Mount Refrigerator Metallic Grey"
                ),
            )
            assert len(res.own_offers) == 1
            assert res.own_offers[0].price == 72399.0
            assert res.own_offers[0].product_handle == "dawlance-9149wb-9-cu-ft-e-chrome-refrigerator"
            assert len(res.offers) == 0

        asyncio.run(_run())

    def test_2_our_seller_unrelated_product_is_not_own_store(self) -> None:
        async def _run() -> None:
            items = [
                {
                    "id": "111",
                    "handle": "dawlance-9173wb-12-cu-ft-e-chrome-refrigerator",
                    "title": "Dawlance 9173WB 12 Cu Ft E-Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "88,000"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "222",
                    "handle": "haier-washing-machine-hwm-80",
                    "title": "Haier HWM 80-826 Twin Tub Washing Machine",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "32,000"},
                    "vendor": {"name": "KiaChahye"},
                },
            ]
            sess = AsyncMock()
            sess.get.return_value = _mock_response(items)
            res = await scrape_alfamall(
                sess,
                "Dawlance 9149WB",
                "9149WB",
                brand="Dawlance",
                target_desc=(
                    "Dawlance 9149WB E-Chrome 9 Cu Ft Non-Inverter Top Mount Refrigerator Metallic Grey"
                ),
            )
            assert res.own_offers == []
            assert res.offers == []

        asyncio.run(_run())

    def test_3_our_seller_incompatible_variant_or_series_is_not_own_store(self) -> None:
        """9149WB Chrome, Avante, Chrome Pro, or incompatible color/variant must NOT match 9149WB E-Chrome."""

        async def _run() -> None:
            items = [
                {
                    "id": "70926143810735981",
                    "handle": "dawlance-9149wb-9-cu-ft-chrome-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "64,999"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "70926143814425880",
                    "handle": "dawlance-9149wb-9-cu-ft-chrome-refrigerator-1",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,799"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "70926143817692630",
                    "handle": "dawlance-9149wb-9-cu-ft-avante-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft Avante Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,399"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "70926143899999999",
                    "handle": "dawlance-9149wb-9-cu-ft-chrome-pro-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Pro Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "78,000"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
            ]
            sess = AsyncMock()
            sess.get.return_value = _mock_response(items)
            res = await scrape_alfamall(
                sess,
                "Dawlance 9149WB",
                "9149WB",
                brand="Dawlance",
                target_desc=(
                    "Dawlance 9149WB E-Chrome 9 Cu Ft Non-Inverter Top Mount Refrigerator Metallic Grey"
                ),
            )
            assert res.own_offers == []

        asyncio.run(_run())

    def test_4_other_seller_compatible_product_is_competitor(self) -> None:
        async def _run() -> None:
            items = [
                {
                    "id": "9001",
                    "handle": "dawlance-ref-9149-wb-e-chrome-grey",
                    "title": "Dawlance REF 9149 WB E-Chrome Grey",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "75,600"},
                    "vendor": {"name": "Fahad Electronics"},
                }
            ]
            sess = AsyncMock()
            sess.get.return_value = _mock_response(items)
            res = await scrape_alfamall(
                sess,
                "Dawlance 9149WB",
                "9149WB",
                brand="Dawlance",
                target_desc=(
                    "Dawlance 9149WB E-Chrome 9 Cu Ft Non-Inverter Top Mount Refrigerator Metallic Grey"
                ),
            )
            assert len(res.offers) == 1
            assert res.offers[0].vendor_name == "Fahad Electronics"
            assert res.own_offers == []

        asyncio.run(_run())


class TestOwnStoreDeduplicationAndTerminalSummary:
    """Requirements B & C: Canonical listing deduplication across tiers and concise terminal summary."""

    def setup_method(self) -> None:
        clear_scraper_cache()

    def test_5_same_listing_found_in_multiple_tiers_yields_one_unique_listing(self) -> None:
        async def _run() -> None:
            same_item = {
                "id": "70926143806343970",
                "handle": "dawlance-9149wb-9-cu-ft-e-chrome-refrigerator",
                "title": "Dawlance 9149WB 9 Cu Ft E-Chrome Refrigerator",
                "sold_out": False,
                "variant_detail": {"discounted_price": "72,399"},
                "vendor": {"name": "Kia Chahiye Pvt Ltd"},
            }
            sess = AsyncMock()
            sess.get.return_value = _mock_response([same_item])
            patterns = {
                "tier_1": ["Dawlance 9149WB", "9149WB Metallic Grey"],
                "tier_2": ["9149WB"],
                "tier_3": ["9149 WB", "9149-WB"],
            }
            res = await scrape_alfamall(
                sess,
                patterns,
                "9149WB",
                brand="Dawlance",
                target_desc=(
                    "Dawlance 9149WB E-Chrome 9 Cu Ft Non-Inverter Top Mount Refrigerator Metallic Grey"
                ),
                exhaustive=True,
            )
            assert len(res.own_offers) == 1
            assert res.own_offers[0].duplicate_count == 1
            assert res.own_offers[0].price == 72399.0

        asyncio.run(_run())

    def test_6_three_genuine_distinct_compatible_listings_preserved_and_summarized_once(
        self,
    ) -> None:
        async def _run() -> None:
            items = [
                {
                    "id": "101",
                    "handle": "dawlance-9149wb-e-chrome-listing-a",
                    "title": "Dawlance 9149WB 9 Cu Ft E-Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "64,999"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "102",
                    "handle": "dawlance-9149wb-e-chrome-listing-b",
                    "title": "Dawlance 9149WB 9 Cu Ft E-Chrome Refrigerator Metallic Grey",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,399"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "103",
                    "handle": "dawlance-9149wb-e-chrome-listing-c",
                    "title": "Dawlance REF-9149WB E-Chrome 9 CFT Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,799"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
            ]
            sess = AsyncMock()
            sess.get.return_value = _mock_response(items)
            res = await scrape_alfamall(
                sess,
                "Dawlance 9149WB",
                "9149WB",
                brand="Dawlance",
                target_desc=(
                    "Dawlance 9149WB E-Chrome 9 Cu Ft Non-Inverter Top Mount Refrigerator Metallic Grey"
                ),
            )
            # All 3 genuine distinct listings are preserved internally
            assert len(res.own_offers) == 3

            floors = calculate_floors(67000.0)
            alfa_eval = evaluate_alfa_pricing(floors, res)
            assert len(alfa_eval.own_offers) == 3
            assert (
                "[OWN STORE ACTIVE: Kia Chahiye Pvt Ltd (3 distinct listings: Rs. 64,999–72,799)]"
                in alfa_eval.reason
            )

            empty_digi = ScrapeResult(offers=[])
            digi_eval = PlatformPricingResult(None, None, None, status="SKIPPED", reason="Skipped")
            tbl = build_scraped_sellers_table(floors, res, empty_digi, alfa_eval, digi_eval)
            rendered = _render_table_text(tbl)
            assert "★ Our Store: 3 distinct verified listings | Rs. 64,999–72,799" in rendered
            assert rendered.count("★ Our Store") == 1

        asyncio.run(_run())

    def test_7_same_seller_different_listing_ids_and_different_products_not_aggregated(
        self,
    ) -> None:
        async def _run() -> None:
            items = [
                {
                    "id": "70926143810735981",
                    "handle": "dawlance-9149wb-9-cu-ft-chrome-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "64,999"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "70926143806343970",
                    "handle": "dawlance-9149wb-9-cu-ft-e-chrome-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft E-Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,399"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "70926143814425880",
                    "handle": "dawlance-9149wb-9-cu-ft-chrome-refrigerator-1",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,799"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "70926143817692630",
                    "handle": "dawlance-9149wb-9-cu-ft-avante-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft Avante Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,399"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
            ]
            sess = AsyncMock()
            sess.get.return_value = _mock_response(items)
            res = await scrape_alfamall(
                sess,
                "Dawlance 9149WB",
                "9149WB",
                brand="Dawlance",
                target_desc=(
                    "Dawlance 9149WB E-Chrome 9 Cu Ft Non-Inverter Top Mount Refrigerator Metallic Grey"
                ),
            )
            assert len(res.own_offers) == 1
            assert res.own_offers[0].price == 72399.0
            assert (
                res.own_offers[0].product_handle
                == "dawlance-9149wb-9-cu-ft-e-chrome-refrigerator"
            )

        asyncio.run(_run())

    def test_8_missing_listing_identity_uses_conservative_deterministic_fallback(self) -> None:
        offers = [
            ScrapedOffer(
                vendor_name="KiaChahye",
                price=72500.0,
                is_sold_out=False,
                raw_title="Dawlance 9149WB E-Chrome Refrigerator",
                product_handle=None,
                duplicate_count=2,
            ),
            ScrapedOffer(
                vendor_name="KiaChahye",
                price=72500.0,
                is_sold_out=False,
                raw_title="Dawlance  9149WB   E-Chrome Refrigerator",
                product_handle=None,
                duplicate_count=1,
            ),
        ]
        deduped = deduplicate_own_offers(offers)
        assert len(deduped) == 1
        assert deduped[0].duplicate_count == 1

    def test_9_and_10_alfamall_and_digimall_remain_independent_and_pricing_uses_validated_only(
        self,
    ) -> None:
        async def _run() -> None:
            target_desc = (
                "Dawlance 9149WB E-Chrome 9 Cu Ft Non-Inverter Top Mount Refrigerator Metallic Grey"
            )
            alfa_items = [
                {
                    "id": "a1",
                    "handle": "dawlance-9149wb-9-cu-ft-chrome-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "64,999"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "a2",
                    "handle": "dawlance-9149wb-9-cu-ft-e-chrome-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft E-Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,399"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "a3",
                    "handle": "dawlance-ref-9149-wb-e-chrome-grey",
                    "title": "Dawlance REF 9149 WB E-Chrome Grey",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "75,600"},
                    "vendor": {"name": "Fahad Electronics"},
                },
            ]
            digi_items = [
                {
                    "id": "d1",
                    "handle": "dawlance-9149wb-9-cu-ft-chrome-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,500"},
                    "vendor": {"name": "KiaChahiye PVT LTD"},
                },
                {
                    "id": "d2",
                    "handle": "dawlance-9149wb-9-cu-ft-chrome-refrigerator-1",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,500"},
                    "vendor": {"name": "KiaChahiye PVT LTD"},
                },
                {
                    "id": "d3",
                    "handle": "dawlance-9149wb-9-cu-ft-e-chrome-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft E-Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,500"},
                    "vendor": {"name": "KiaChahiye PVT LTD"},
                },
                {
                    "id": "d4",
                    "handle": "dawlance-e-chrome-ref-9149wb",
                    "title": "Dawlance E Chrome Freezer-On-Top Refrigerator (REF-9149WB)",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "70,999"},
                    "vendor": {"name": "iShopping Team"},
                },
            ]

            alfa_sess = AsyncMock()
            alfa_sess.get.return_value = _mock_response(alfa_items, total=3)
            digi_sess = AsyncMock()
            digi_sess.get.return_value = _mock_response(digi_items, total=4)

            alfa_res = await scrape_alfamall(
                alfa_sess, "Dawlance 9149WB", "9149WB", brand="Dawlance", target_desc=target_desc
            )
            plan = generate_digimall_plan(target_desc, "Dawlance")
            digi_res = await scrape_digimall(
                digi_sess, plan, "9149WB", brand="Dawlance", target_desc=target_desc
            )

            assert len(alfa_res.own_offers) == 1
            assert alfa_res.own_offers[0].price == 72399.0
            assert len(digi_res.own_offers) == 1
            assert digi_res.own_offers[0].price == 72500.0
            assert digi_res.own_offers[0].duplicate_count == 1

            with (
                patch.object(config, "ALFA_COMMISSION_PCT", 10.0),
                patch.object(config, "DIGI_COMMISSION_PCT", 8.0),
                patch.object(config, "COMPANY_MIN_PROFIT_PKR", 500.0),
            ):
                floors = calculate_floors(
                    67000.0, min_profit=config.COMPANY_MIN_PROFIT_PKR, personal_comm_pct=5.0
                )
                alfa_eval = evaluate_alfa_pricing(floors, alfa_res)
                digi_eval = evaluate_digi_pricing(floors, digi_res)

            assert alfa_eval.final_price == 75499
            assert "[OWN STORE ACTIVE: Kia Chahiye Pvt Ltd @ Rs. 72,399]" in alfa_eval.reason
            assert "64,999" not in alfa_eval.reason

            assert digi_eval.final_price == 74999
            assert "[OWN STORE ACTIVE: KiaChahiye PVT LTD @ Rs. 72,500]" in digi_eval.reason

        asyncio.run(_run())

    def test_11_echrome_hard_rejects_chrome_and_chrome_pro_even_when_echrome_missing(
        self,
    ) -> None:
        """E-Chrome and Chrome are distinct products: Chrome and Chrome Pro are hard-rejected for both competitors and Own Store."""

        async def _run() -> None:
            target_desc = (
                "Dawlance 9149WB E-Chrome 9 Cu Ft Non-Inverter Top Mount Refrigerator Metallic Grey"
            )
            items = [
                {
                    "id": "a1",
                    "handle": "dawlance-9149wb-9-cu-ft-chrome-refrigerator",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "64,999"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "c1",
                    "handle": "competitor-9149wb-chrome",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "76,500"},
                    "vendor": {"name": "Fahad Electronics"},
                },
                {
                    "id": "c2",
                    "handle": "competitor-9149wb-chrome-pro",
                    "title": "Dawlance 9149WB 9 Cu Ft Chrome Pro Refrigerator",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "71,000"},
                    "vendor": {"name": "Tech House"},
                },
            ]
            sess = AsyncMock()
            sess.get.return_value = _mock_response(items, total=3)
            res = await scrape_alfamall(
                sess, "Dawlance 9149WB", "9149WB", brand="Dawlance", target_desc=target_desc
            )
            # Both Chrome and Chrome Pro are hard-rejected when target is E-Chrome
            assert res.offers == []
            assert res.own_offers == []

        asyncio.run(_run())

    def test_12_dw_md_compound_prefix_matches_md_directly_as_tier_1_exact_without_fallback(
        self,
    ) -> None:
        """DW-MD models (DW-MD 15, DW-MD4, DW-MD 7, DW-MD 20 INV) match both DW-MD and MD directly as Tier 1 Exact (no fallback)."""
        from pricing_engine.matcher import generate_search_patterns, referee_match

        # 1. Referee direct Tier 1 exact matching (with DW and without DW)
        for target_str, cand_str in [
            (
                "Dawlance Classic Series DW-MD 15 20 Ltr Solo Microwave Oven",
                "DawlanceDW-MD 15 20 Ltr Solo Microwave Oven".replace("DawlanceDW", "Dawlance DW"),
            ),
            (
                "Dawlance Classic Series DW-MD 15 20 Ltr Solo Microwave Oven",
                "Dawlance MD 15 20 Ltr Solo Microwave Oven",
            ),
            (
                "Dawlance DW MD-15 20 Ltr Solo Microwave Oven",
                "Dawlance MD-15 20L Microwave Oven",
            ),
            (
                "Dawlance DW-MD4 20 Ltr Microwave Oven",
                "Dawlance MD4 20 Ltr Microwave Oven",
            ),
            (
                "Dawlance DW-MD4 20 Ltr Microwave Oven",
                "Dawlance MD-4 20 Ltr Microwave Oven",
            ),
            (
                "Dawlance DW-MD 7 20 Ltr Microwave Oven",
                "Dawlance MD 7 20 Ltr Microwave Oven",
            ),
            (
                "Dawlance DW-MD 20 INV 25 Ltr Inverter Microwave Oven",
                "Dawlance MD 20 Inverter 25L Microwave Oven",
            ),
        ]:
            dec = referee_match(target_str, cand_str, brand="Dawlance")
            assert dec.is_match is True, f"Expected match for {target_str} vs {cand_str}: {dec.reason}"
            assert dec.match_tier == 1, f"Expected Tier 1 for {target_str} vs {cand_str}, got {dec.match_tier}"
            assert dec.missing_modifier is None
            assert dec.compatibility_notice is None

        # 2. Search patterns & DigiMall plan include MD-15 / MD4 / MD-7 directly
        for model_str, expected_sub in [
            ("DW-MD 15", "MD-15"),
            ("DW-MD4", "MD4"),
            ("DW-MD 7", "MD-7"),
        ]:
            pats = generate_search_patterns(model_str, brand="Dawlance")
            assert expected_sub in pats["tier_1"]
            plan = generate_digimall_plan(model_str, "Dawlance")
            assert any(expected_sub in q for b in plan.branches for q in b.queries)

        # 3. End-to-end scraper check: Tier 1 exact offer with zero fallback warning
        async def _run() -> None:
            target_desc = "Dawlance Classic Series DW-MD 15 20 Ltr Solo Microwave Oven"
            items = [
                {
                    "id": "m1",
                    "handle": "dawlance-md-15-microwave",
                    "title": "Dawlance MD 15 20 Ltr Solo Microwave Oven",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "16,500"},
                    "vendor": {"name": "Fahad Electronics"},
                }
            ]
            sess = AsyncMock()
            sess.get.return_value = _mock_response(items, total=1)
            res = await scrape_alfamall(
                sess, "DW-MD-15", "DW-MD-15", brand="Dawlance", target_desc=target_desc
            )
            assert len(res.offers) == 1
            assert res.offers[0].vendor_name == "Fahad Electronics"
            assert res.offers[0].match_tier == 1
            assert res.active_modifier_fallback is None
            assert res.offers[0].compatibility_notice is None

        asyncio.run(_run())

    def test_13_dw_md_rejects_cross_category_and_conflicting_subprefixes(self) -> None:
        """Short stems (MD4, MD7, MD15) must never strip to bare numbers or match conflicting sub-prefixes."""
        from pricing_engine.matcher import referee_match

        for target_str, cand_str in [
            ("Dawlance DW-MD4 Microwave Oven", "Dawlance 4 Cu Ft Single Door Refrigerator"),
            ("Dawlance MD-4 Microwave Oven", "Dawlance 4 Cu Ft Mini Bar Fridge"),
            ("Dawlance DW-MD 7 Microwave Oven", "Dawlance 7 KG Single Tub Washing Machine"),
            ("Dawlance MD-7 Microwave Oven", "Dawlance 7 KG Spinner Dryer"),
            ("Dawlance DW-MD 15 Microwave Oven", "Dawlance Inverter 15 1 Ton Split AC"),
            ("Dawlance DW-MD 15 Microwave Oven", "Dawlance DW-15 Microwave"),
            ("Dawlance DW-MD 15 Microwave Oven", "Dawlance DW-FD 15 Air Fryer"),
            ("Dawlance DW-MD4 Microwave Oven", "Dawlance DW-FD4 Air Fryer"),
            ("Dawlance DW-200 Washing Machine", "Dawlance DW-MD-200 Microwave Oven"),
        ]:
            dec = referee_match(target_str, cand_str, brand="Dawlance")
            assert dec.is_match is False, f"Expected rejection for {target_str} vs {cand_str}"

    def test_14_series_subseries_isolation_and_spaced_echrome(self) -> None:
        """Verify Chrome Pro vs Chrome, Avante+ vs Avante, spaced E Chrome, and E-Chrome Hairline."""
        from pricing_engine.matcher import referee_match

        # Must reject conflicting sub-series
        for target_str, cand_str in [
            ("Dawlance 9169WB Chrome Pro Refrigerator", "Dawlance 9169WB Chrome Refrigerator"),
            ("Dawlance 9173WB Avante+ Refrigerator", "Dawlance 9173WB Avante Refrigerator"),
            ("Dawlance 9149 WB E CHROME FH Refrigerator", "Dawlance 9149WB Chrome Refrigerator"),
            ("Dawlance 9149WB Chrome Refrigerator", "Dawlance 9149WB E Chrome Refrigerator"),
        ]:
            dec = referee_match(target_str, cand_str, brand="Dawlance")
            assert dec.is_match is False, f"Expected sub-series rejection for {target_str} vs {cand_str}"

        # Spaced E Chrome matches hyphenated E-Chrome, and series-omitted Hairline matches E-Chrome Hairline
        assert (
            referee_match(
                "Dawlance 9149 WB E CHROME FH Refrigerator",
                "Dawlance 9149WB E-Chrome Refrigerator",
                brand="Dawlance",
            ).is_match
            is True
        )
        assert (
            referee_match(
                "Dawlance 9173WB E-Chrome 11 Cu Ft Double Door Refrigerator Hairline Golden",
                "Dawlance 9173WB 11 Cu Ft Double Door Refrigerator Hairline Golden",
                brand="Dawlance",
            ).is_match
            is True
        )

    def test_15_deduplicate_own_offers_never_overwrites_instock_with_sold_out(self) -> None:
        """An in-stock own-store listing must never be overwritten by a sold-out listing for the same handle."""
        offers = [
            ScrapedOffer(
                vendor_name="Kia Chahiye Pvt Ltd",
                price=72399.0,
                is_sold_out=False,
                raw_title="Dawlance 9149WB E-Chrome Refrigerator",
                product_handle="dawlance-9149wb-e-chrome",
                match_tier=2,
                missing_modifier="Variant W",
            ),
            ScrapedOffer(
                vendor_name="Kia Chahiye Pvt Ltd",
                price=72399.0,
                is_sold_out=True,
                raw_title="Dawlance 9149WB E-Chrome Refrigerator",
                product_handle="dawlance-9149wb-e-chrome",
                match_tier=1,
                missing_modifier=None,
            ),
        ]
        deduped = deduplicate_own_offers(offers)
        assert len(deduped) == 1
        assert deduped[0].is_sold_out is False

    def test_16_non_ac_prose_not_fused_and_4letter_nonbrand_prefix_isolated(self) -> None:
        """Prose words before SKUs must not fuse, and non-brand 4-letter prefixes must stay isolated."""
        from pricing_engine.matcher import referee_match

        go_dec = referee_match("Gree Go GS-18AC", "Gree GS-18AC", brand="Gree")
        assert go_dec.is_match is True
        assert go_dec.match_tier == 1

        for brand, t_str, c_str in [
            ("Samsung", "Samsung SHFD-15 Microwave", "Samsung FD-15 Microwave"),
            ("Samsung", "Samsung WDFD-15 Microwave", "Samsung FD-15 Microwave"),
            ("Dawlance", "Dawlance SHMD-15 Microwave", "Dawlance MD-15 Microwave"),
        ]:
            dec = referee_match(t_str, c_str, brand=brand)
            assert dec.is_match is False, f"Expected prefix collision rejection: {t_str} vs {c_str}"

    def test_17_3digit_compound_dw_md_direct_and_digi_inv_plan(self) -> None:
        """3-digit compound prefixes (DW-MD 200, DW-MD 105) and DigiMall DW-MD 20 INV plans resolve cleanly."""
        from pricing_engine.matcher import referee_match

        for t_str, c_str in [
            ("Dawlance DW-MD 200 Microwave", "Dawlance MD 200 Microwave"),
            ("Dawlance DW-MD 105 Microwave", "Dawlance MD 105 Microwave"),
            ("Dawlance DWMD15 Microwave", "Dawlance MD 15 Microwave"),
        ]:
            dec = referee_match(t_str, c_str, brand="Dawlance")
            assert dec.is_match is True
            assert dec.match_tier == 1
            assert dec.missing_modifier is None
            assert dec.compatibility_notice is None

        plan = generate_digimall_plan("Dawlance DW-MD 20 INV Microwave", "Dawlance")
        all_queries = [q for b in plan.branches for q in b.queries]
        assert "MD-20" in all_queries

    def test_18_numeric_2letter_suffix_and_trailing_plus_series_isolation(self) -> None:
        """Numeric+2-letter suffix models (9178LF, 9149WB) never bypass series or trailing '+' checks."""
        from pricing_engine.matcher import referee_match

        for t_str, c_str in [
            ("Dawlance 9173 WB Avante +", "Dawlance 9173 WB Avante"),
            ("Dawlance 9173WB Avante+ Hairline Golden", "Dawlance 9173WB Avante Hairline Golden"),
            ("Dawlance 9178LF Avante Refrigerator", "Dawlance 9178LF E-Chrome Refrigerator"),
            (
                "Dawlance DW-9178LF Avante+ Inverter Grey Refrigerator",
                "Dawlance DW-9178LF Avante Inverter Grey Refrigerator",
            ),
            ("Dawlance 9149WB Chrome Refrigerator", "Dawlance E Chrome REF-9149WB"),
        ]:
            dec = referee_match(t_str, c_str, brand="Dawlance")
            assert dec.is_match is False, f"Expected series rejection: {t_str} vs {c_str}"

        assert (
            referee_match(
                "Dawlance 9173WB Avante+ Hairline Golden",
                "Dawlance 9173WB Hairline Golden",
                brand="Dawlance",
            ).is_match
            is True
        )

    def test_19_vendor_handle_official_store_and_tier2_own_store_annotations(self) -> None:
        """Official stores matched via vendor_handle stay distinct, and Tier 2 own-store offers show Base Fallback."""

        async def _run() -> None:
            items = [
                {
                    "id": "o1",
                    "handle": "haier-hwm-120-826s-own",
                    "title": "Haier HWM 120-826S 12KG Washing Machine",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "125,000"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                },
                {
                    "id": "f1",
                    "handle": "haier-hwm-120-826-official",
                    "title": "Haier HWM 120-826 12KG Washing Machine",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "132,000"},
                    "vendor": {"name": "Brand Boutique", "handle": "haier-official-store"},
                },
            ]
            sess = AsyncMock()
            sess.get.return_value = _mock_response(items, total=2)
            res = await scrape_alfamall(
                sess,
                "HWM 120-826",
                "HWM 120-826",
                brand="Haier",
                target_desc="Haier HWM 120-826 12KG Washing Machine",
            )
            assert len(res.own_offers) == 2
            own_only = [o for o in res.own_offers if o.vendor_name == "Kia Chahiye Pvt Ltd"]
            off_only = [o for o in res.own_offers if o.vendor_name == "Brand Boutique"]
            assert len(own_only) == 1 and own_only[0].detected_variant == "S"
            assert own_only[0].match_tier == 2 and own_only[0].missing_modifier == "Variant S"
            assert len(off_only) == 1 and off_only[0].vendor_handle == "haier-official-store"

            floors = calculate_floors(110000.0)
            alfa_eval = evaluate_alfa_pricing(floors, res)
            assert (
                "[OWN STORE ACTIVE: Kia Chahiye Pvt Ltd [Base Fallback: Variant S] @ Rs. 125,000]"
                in alfa_eval.reason
            )
            assert "[OFFICIAL STORE: Brand Boutique @ Rs. 132,000]" in alfa_eval.reason

            empty_digi = ScrapeResult(offers=[])
            digi_eval = PlatformPricingResult(None, None, None, status="SKIPPED", reason="Skipped")
            rendered = _render_table_text(
                build_scraped_sellers_table(floors, res, empty_digi, alfa_eval, digi_eval)
            )
            assert "Base Fallback: Variant S" in rendered
            assert "Official Flagship (Excluded)" in rendered

        asyncio.run(_run())

    def test_20_multi_listing_own_store_partial_oos_grouped_summary(self) -> None:
        """Mixed active + sold-out own-store handles render one concise grouped row with active (OOS) counts."""
        floors = calculate_floors(67000.0)
        res = ScrapeResult(
            offers=[],
            own_offers=[
                ScrapedOffer(
                    vendor_name="Kia Chahiye Pvt Ltd",
                    price=72399.0,
                    is_sold_out=False,
                    raw_title="Dawlance 9149WB E-Chrome Refrigerator",
                    product_handle="listing-1",
                ),
                ScrapedOffer(
                    vendor_name="Kia Chahiye Pvt Ltd",
                    price=70999.0,
                    is_sold_out=True,
                    raw_title="Dawlance 9149WB E-Chrome Refrigerator",
                    product_handle="listing-2",
                ),
            ],
        )
        alfa_eval = evaluate_alfa_pricing(floors, res)
        empty_digi = ScrapeResult(offers=[])
        digi_eval = PlatformPricingResult(None, None, None, status="SKIPPED", reason="Skipped")
        rendered = _render_table_text(
            build_scraped_sellers_table(floors, res, empty_digi, alfa_eval, digi_eval)
        )
        assert "★ Our Store: 1 active (1 OOS) | Rs. 72,399" in rendered
        assert rendered.count("★ Our Store") == 1
