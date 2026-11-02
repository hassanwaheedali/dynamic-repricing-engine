"""Focused regression tests for Slice 3 scraper diagnostics, color deduplication, pagination, and discovery status."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from pricing_engine.models import (
    DISCOVERY_CANDIDATES_REJECTED,
    DISCOVERY_COMPLETE_NO_COMPETITORS,
    DISCOVERY_PAGINATION_INCOMPLETE,
    ScrapedOffer,
)
from pricing_engine.scraper import (
    ALFAMALL_CONFIG,
    _execute_waterfall,
    _offer_dedupe_key,
    _parse_offers_from_raw_items,
    _parse_offers_with_diagnostics,
    _scrape_alfamall_single_query,
    _scrape_platform_single_query,
    clear_scraper_cache,
    deduplicate_offers,
)


def test_identical_price_ow_and_dg_variants_preserved_in_deduplication() -> None:
    """Ensure identical-price OW and DG variants from the same vendor are never collapsed."""
    off_ow = ScrapedOffer(
        vendor_name="ElectroEase",
        price=195000.0,
        is_sold_out=False,
        raw_title="Haier 1.5 Ton T3 Plus Inverter Split AC HSU-20HFTEX-OW Off White",
        color_family="White",
        scraped_model="HSU-20HFTEX",
    )
    off_dg = ScrapedOffer(
        vendor_name="ElectroEase",
        price=195000.0,
        is_sold_out=False,
        raw_title="Haier 1.5 Ton T3 Plus Inverter Split AC HSU-20HFTEX-DG Dark Grey",
        color_family="Grey / Silver",
        scraped_model="HSU-20HFTEX",
    )
    off_ow_dupe = ScrapedOffer(
        vendor_name="ElectroEase",
        price=195000.0,
        is_sold_out=False,
        raw_title="Haier 1.5 Ton T3 Plus Inverter Split AC HSU-20HFTEX-OW Off White Dupe",
        color_family="White",
        scraped_model="HSU-20HFTEX",
    )

    # 1. Dedupe key verification
    key_ow = _offer_dedupe_key(off_ow)
    key_dg = _offer_dedupe_key(off_dg)
    assert key_ow != key_dg
    assert key_ow[2] == "white"
    assert key_dg[2] == "grey / silver"

    # 2. List deduplication preserves both color editions while deduplicating genuine dupes
    deduped = deduplicate_offers([off_ow, off_dg, off_ow_dupe])
    assert len(deduped) == 2
    colors = {o.color_family for o in deduped}
    assert colors == {"White", "Grey / Silver"}
    ow_winner = next(o for o in deduped if o.color_family == "White")
    assert ow_winner.duplicate_count == 2
    dg_winner = next(o for o in deduped if o.color_family == "Grey / Silver")
    assert dg_winner.duplicate_count == 1


def test_zero_accepted_matches_on_page1_triggers_pagination() -> None:
    """Ensure when Page 1 yields 0 accepted matches and total_count > len(p1), Page 2 is probed."""

    async def _run() -> None:
        clear_scraper_cache()
        session = AsyncMock()

        # Page 1 returns unrelated items (e.g. televisions)
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "count": 25,
            "results": [
                {
                    "title": f"TCL 50P635 4K LED TV Model {i}",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "110,000"},
                    "vendor": {"name": "TVVendor"},
                }
                for i in range(10)
            ],
        }

        # Page 2 returns verified AC match
        resp_p2 = MagicMock()
        resp_p2.status_code = 200
        resp_p2.json.return_value = {
            "count": 25,
            "results": [
                {
                    "title": "Haier 2 Ton T3 Plus DC Inverter Split AC 24 HFAB UPS Enabled",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "210,000"},
                    "vendor": {"name": "ElectroMall"},
                }
            ],
        }

        session.get.side_effect = [resp_p1, resp_p2]

        res = await _scrape_platform_single_query(
            config=ALFAMALL_CONFIG,
            session=session,
            query="24HFAB",
            target_model="HSU-24HFAB",
            floor_price=180000.0,
            brand="Haier",
            target_desc="Haier 2 Ton DC Inverter Split AC HSU-24HFAB",
        )

        assert len(res.offers) == 1
        assert res.offers[0].vendor_name == "ElectroMall"
        assert res.pages_fetched == 2
        assert res.total_available == 25
        assert res.pagination_complete is True
        assert session.get.call_count == 2

    asyncio.run(_run())


def test_incomplete_pagination_on_network_failure_sets_proper_status() -> None:
    """Ensure non-200 or connection failure on Page 2 sets pagination_complete=False and proper discovery_status."""

    async def _run() -> None:
        clear_scraper_cache()
        session = AsyncMock()

        # Page 1 has 0 matches
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "count": 40,
            "results": [
                {
                    "title": "Gree 1 Ton Inverter AC Fairy Series",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "120,000"},
                    "vendor": {"name": "OtherVendor"},
                }
            ],
        }

        # Page 2 fails with HTTP 500
        resp_p2 = MagicMock()
        resp_p2.status_code = 500

        session.get.side_effect = [resp_p1, resp_p2]

        res = await _execute_waterfall(
            single_scraper_fn=_scrape_alfamall_single_query,
            session=session,
            patterns={"tier_1": ["HSU-24HFAB"]},
            target_model="HSU-24HFAB",
            timeout=15.0,
            max_retries=1,
            floor_price=180000.0,
            brand="Haier",
            target_desc="Haier 2 Ton DC Inverter Split AC HSU-24HFAB",
        )

        assert len(res.offers) == 0
        assert res.pagination_complete is False
        assert res.discovery_status == DISCOVERY_PAGINATION_INCOMPLETE

    asyncio.run(_run())


def test_suspicious_rejected_candidates_classification() -> None:
    """Ensure same-brand external candidates rejected for non-definitive reasons are flagged suspicious."""
    # Target is 18HFPCA
    target_desc = "Haier 1.5 Ton DC Inverter Split AC 18HFPCA"
    # Candidate is HSU-18HFP (rejected by referee for variant tag collision)
    raw_item = {
        "title": "Haier 1.5 Ton DC Inverter Split AC HSU-18HFP/023DC",
        "sold_out": False,
        "variant_detail": {"discounted_price": "165,000"},
        "vendor": {"name": "CompetitorElectronics"},
    }

    (
        e,
        b,
        d_mod,
        own,
        r_cnt,
        rej_cnt,
        rej_reasons,
        susp_cnt,
        ext_des,
    ) = _parse_offers_with_diagnostics(
        [raw_item],
        target_model="18HFPCA",
        brand="Haier",
        target_desc=target_desc,
    )

    assert len(e) == 0
    assert len(b) == 0
    assert r_cnt == 1
    assert rej_cnt == 1
    assert susp_cnt == 1
    assert "Variant tag collision" in rej_reasons or "Anchor model mismatch" in rej_reasons

    # Check waterfall discovery status aggregation
    fake_single = AsyncMock(
        return_value=type(
            "FakeScrapeResult",
            (),
            {
                "offers": [],
                "base_offers": [],
                "own_offers": [],
                "is_success": True,
                "status_code": 200,
                "error_detail": None,
                "raw_candidate_count": 1,
                "rejected_count": 1,
                "rejection_reasons": rej_reasons,
                "suspicious_rejected_count": 1,
                "pages_fetched": 1,
                "total_available": 1,
                "pagination_complete": True,
                "extended_model_designation": None,
                "active_modifier_fallback": None,
                "active_modifier_source": "target",
            },
        )()
    )

    wf_res = asyncio.run(
        _execute_waterfall(
            single_scraper_fn=fake_single,
            session=AsyncMock(),
            patterns={"tier_1": ["18HFPCA"]},
            target_model="18HFPCA",
            timeout=15.0,
            max_retries=1,
            brand="Haier",
            target_desc=target_desc,
        )
    )

    assert wf_res.discovery_status == DISCOVERY_CANDIDATES_REJECTED
    assert wf_res.suspicious_rejected_count == 1


def test_legitimate_zero_competitor_capacity_mismatch_not_suspicious() -> None:
    """Ensure capacity mismatch (1.5T vs 2T in Row 35) is classified as definitive, not suspicious."""
    target_desc = "Haier 1.5 Ton DC Inverter Split AC Solar Hybrid-IV T3"
    raw_item = {
        "title": "Haier 2.0 Ton Solar Hybrid-IV T3 Inverter AC",
        "sold_out": False,
        "variant_detail": {"discounted_price": "240,000"},
        "vendor": {"name": "CompetitorSolar"},
    }

    (
        e,
        b,
        d_mod,
        own,
        r_cnt,
        rej_cnt,
        rej_reasons,
        susp_cnt,
        ext_des,
    ) = _parse_offers_with_diagnostics(
        [raw_item],
        target_model="Solar Hybrid-IV T3",
        brand="Haier",
        target_desc=target_desc,
    )

    assert len(e) == 0
    assert r_cnt == 1
    assert rej_cnt == 1
    # Definitive capacity mismatch must NOT be flagged as suspicious!
    assert susp_cnt == 0
    assert "Capacity / screen size mismatch" in rej_reasons

    # Check waterfall discovery status aggregation gives COMPLETE_NO_COMPETITORS (genuine monopoly)
    fake_single = AsyncMock(
        return_value=type(
            "FakeScrapeResult",
            (),
            {
                "offers": [],
                "base_offers": [],
                "own_offers": [],
                "is_success": True,
                "status_code": 200,
                "error_detail": None,
                "raw_candidate_count": 1,
                "rejected_count": 1,
                "rejection_reasons": rej_reasons,
                "suspicious_rejected_count": 0,
                "pages_fetched": 1,
                "total_available": 1,
                "pagination_complete": True,
                "extended_model_designation": None,
                "active_modifier_fallback": None,
                "active_modifier_source": "target",
            },
        )()
    )

    wf_res = asyncio.run(
        _execute_waterfall(
            single_scraper_fn=fake_single,
            session=AsyncMock(),
            patterns={"tier_1": ["Solar Hybrid-IV T3"]},
            target_model="Solar Hybrid-IV T3",
            timeout=15.0,
            max_retries=1,
            brand="Haier",
            target_desc=target_desc,
        )
    )

    assert wf_res.discovery_status == DISCOVERY_COMPLETE_NO_COMPETITORS
    assert wf_res.suspicious_rejected_count == 0


def test_parse_offers_from_raw_items_backward_compatibility() -> None:
    """Ensure _parse_offers_from_raw_items preserves 4-tuple return contract for legacy callers."""
    raw_item = {
        "title": "Haier 1.5 Ton T3 Plus Inverter Split AC HSU-20HFTEX-OW Off White",
        "sold_out": False,
        "variant_detail": {"discounted_price": "195,000"},
        "vendor": {"name": "Vendor1"},
    }
    ret = _parse_offers_from_raw_items(
        [raw_item],
        target_model="20HFT",
        brand="Haier",
        target_desc="Haier 1.5 Ton DC Inverter Split AC 20HFT",
    )
    assert isinstance(ret, tuple)
    assert len(ret) == 4
    exact, base, d_mod, own = ret
    assert len(exact) == 1
    assert exact[0].color_family == "White"
    assert exact[0].scraped_model == "HSU-20HFTEX"
