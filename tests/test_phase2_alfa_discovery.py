"""Phase 2 Comprehensive Regression Suite: AlfaMall Discovery, Refined Matching, and False-Monopoly Guards.

Covers:
1. Target Case 1: Haier Solar Hybrid-III T3 18 pattern generation, tokenization, and matching.
2. Target Case 2: Dawlance Dual Pro T3 15 and 30 series matching and capacity isolation.
3. Target Case 3: Haier 20HFT / HFTEX compatibility notice, OW/DG color variant preservation, and Avante vs Avante+ isolation.
4. Target Case 4: Haier 13HFCP exact matching and cross-submodel rejection.
5. Target Case 5: Haier HSU-24HFAB spaced SKU normalization and multi-page pagination.
6. Negative Isolation: Rejection of incompatible sub-models (18HFPCA vs 18HFP, 19HFPAA vs 19HFP, etc.).
7. False Monopoly Suppression: Suppression of blind Monopoly on incomplete discovery or rejected candidates.
8. Yellow Compatibility Notice: Propagation of legitimate extended model designations.
9. Inherent descriptive T3 vs SKU upgrade -T3 distinction.
10. HVAC marketing token stripping without damaging SKU tokens.
11. Technical electrical slash patterns (18HE/DC).
12. 1.0T <-> 1.25T equivalence on 14k BTU models.
13. TV screen size collision protection in AC context.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pricing_engine.calculator import calculate_cost_base, calculate_floors
from pricing_engine.evaluator import evaluate_alfa_pricing
from pricing_engine.matcher import (
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    referee_match,
)
from pricing_engine.models import (
    DISCOVERY_CANDIDATES_REJECTED,
    DISCOVERY_COMPLETE_NO_COMPETITORS,
    DISCOVERY_COMPLETE_WITH_OFFERS,
    DISCOVERY_PAGINATION_INCOMPLETE,
    STATUS_CANDIDATES_REJECTED,
    STATUS_INCOMPLETE_DISCOVERY,
    ScrapedOffer,
    ScrapeResult,
)
from pricing_engine.pipeline import (
    determine_platform_status,
    determine_risk_alert,
)
from pricing_engine.scraper import (
    ALFAMALL_CONFIG,
    _offer_dedupe_key,
    _scrape_platform_single_query,
    clear_scraper_cache,
    deduplicate_offers,
)

# ==============================================================================
# 1. Target Case 1: Haier Solar Hybrid-III T3 18
# ==============================================================================


def test_target_case_1_haier_solar_hybrid_iii_pattern_and_matching() -> None:
    """Ensure Haier Solar Hybrid-III T3 18 generates robust search patterns and matches correctly."""
    title = "Haier 1.5 Ton Solar Hybrid-III T3 Inverter AC 18"
    brand = "Haier"

    query, model = extract_search_query_and_model(title, brand)
    patterns = generate_search_patterns(model, brand=brand)

    # Patterns must cover Solar Hybrid combinations without dropping roman numerals
    all_queries = [q for t in patterns.values() for q in t]
    assert any("SOLAR" in q.upper() for q in all_queries)

    # Referee matching against valid marketplace titles
    m_res = referee_match(
        title,
        "Haier 1.5 Ton Solar Hybrid-III T3 Inverter Split AC Model 18",
        brand=brand,
    )
    assert m_res.is_match is True


# ==============================================================================
# 2. Target Case 2: Dawlance Dual Pro T3 15 and 30
# ==============================================================================


def test_target_case_2_dawlance_dual_pro_t3_matching_and_capacity_isolation() -> None:
    """Ensure Dawlance Dual Pro T3 15 matches 1.5 Ton and isolates from 30 (2.0 Ton)."""
    title_15 = "Dawlance Inverter AC 1.5 Ton Dual Pro T3 15"
    brand = "Dawlance"

    # Valid match against 15
    res_15 = referee_match(
        title_15,
        "Dawlance 1.5 Ton Dual Pro T3 15 Inverter Split AC",
        brand=brand,
    )
    assert res_15.is_match is True

    # Capacity collision against 30 (2.0 Ton)
    res_30 = referee_match(
        title_15,
        "Dawlance 2.0 Ton Dual Pro T3 30 Inverter Split AC",
        brand=brand,
    )
    assert res_30.is_match is False
    assert (
        "capacity" in (res_30.reason or "").lower() or "mismatch" in (res_30.reason or "").lower()
    )


# ==============================================================================
# 3. Target Case 3: Haier 20HFT / HFTEX, OW/DG, and Avante vs Avante+
# ==============================================================================


def test_target_case_3_haier_20hft_hftex_compatibility_and_notice() -> None:
    """Ensure 20HFT matches HSU-20HFTEX with compatibility notice, not as a blind error."""
    target_title = "Haier 1.5 Ton Inverter AC HSU-20HFT"
    brand = "Haier"

    res = referee_match(
        target_title,
        "Haier 1.5 Ton T3 Plus Inverter AC HSU-20HFTEX-OW Off White",
        brand=brand,
    )
    assert res.is_match is True
    assert res.missing_modifier is not None
    assert "Extended Edition" in res.missing_modifier or "HSU-20HFTEX" in res.missing_modifier


def test_target_case_3_ow_and_dg_color_variants_not_collapsed() -> None:
    """Ensure identical-price OW and DG color variants are preserved in deduplication."""
    off_ow = ScrapedOffer(
        vendor_name="SuperVendor",
        price=185000.0,
        is_sold_out=False,
        raw_title="Haier 1.5 Ton Inverter AC HSU-20HFTEX-OW Off White",
        color_family="White",
        scraped_model="HSU-20HFTEX",
    )
    off_dg = ScrapedOffer(
        vendor_name="SuperVendor",
        price=185000.0,
        is_sold_out=False,
        raw_title="Haier 1.5 Ton Inverter AC HSU-20HFTEX-DG Dark Grey",
        color_family="Grey / Silver",
        scraped_model="HSU-20HFTEX",
    )

    k_ow = _offer_dedupe_key(off_ow)
    k_dg = _offer_dedupe_key(off_dg)
    assert k_ow != k_dg

    deduped = deduplicate_offers([off_ow, off_dg])
    assert len(deduped) == 2


def test_target_case_3_avante_vs_avante_plus_strict_isolation() -> None:
    """Ensure Dawlance Avante and Avante+ are never matched cross-series."""
    res = referee_match(
        "Dawlance 1.5 Ton Avante 15 Inverter AC",
        "Dawlance 1.5 Ton Avante+ 15 Inverter AC",
        brand="Dawlance",
    )
    assert res.is_match is False
    assert (
        "plus" in (res.reason or "").lower()
        or "variant" in (res.reason or "").lower()
        or "collision" in (res.reason or "").lower()
    )


def test_glamour_vs_glamour_plus_strict_isolation() -> None:
    """Ensure Orient Glamour and Glamour+ are never matched cross-series."""
    res = referee_match(
        "Orient 1.5 Ton Glamour 18 Inverter AC",
        "Orient 1.5 Ton Glamour+ 18 Inverter AC",
        brand="Orient",
    )
    assert res.is_match is False


# ==============================================================================
# 4. Target Case 4: Haier 13HFCP Exact Matching and Rejection
# ==============================================================================


def test_target_case_4_haier_13hfcp_matching_and_rejections() -> None:
    """Ensure 13HFCP matches HSU-13HFCP and strictly rejects 13HFP or 13LF."""
    target_title = "Haier 1.0 Ton DC Inverter Split AC 13HFCP"
    brand = "Haier"

    # Valid exact match
    res_valid = referee_match(
        target_title,
        "Haier 1 Ton Inverter AC HSU-13HFCP",
        brand=brand,
    )
    assert res_valid.is_match is True

    # Incompatible model 13HFP
    res_incompat_hfp = referee_match(
        target_title,
        "Haier 1 Ton Inverter AC HSU-13HFP",
        brand=brand,
    )
    assert res_incompat_hfp.is_match is False

    # Incompatible model 13LF
    res_incompat_lf = referee_match(
        target_title,
        "Haier 1 Ton Inverter AC HSU-13LF",
        brand=brand,
    )
    assert res_incompat_lf.is_match is False


# ==============================================================================
# 5. Target Case 5: Haier HSU-24HFAB Spaced SKU and Pagination
# ==============================================================================


def test_target_case_5_haier_24hfab_spaced_sku_matching() -> None:
    """Ensure spaced '24 HFAB' is normalized and matches HSU-24HFAB."""
    target_title = "Haier 2.0 Ton DC Inverter Split AC HSU-24HFAB"
    brand = "Haier"

    res = referee_match(
        target_title,
        "Haier 2 Ton Inverter AC 24 HFAB UPS Enabled",
        brand=brand,
    )
    assert res.is_match is True


def test_target_case_5_zero_matches_page1_triggers_pagination_to_page2() -> None:
    """Ensure 0 accepted matches on Page 1 triggers Page 2 pagination when total_count > len(p1)."""

    async def _run() -> None:
        clear_scraper_cache()
        session = AsyncMock()

        # Page 1 has 10 unrelated TV products
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "count": 22,
            "results": [
                {
                    "title": f"TCL 4K UHD LED TV Model {i}",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "90,000"},
                    "vendor": {"name": "TVStore"},
                }
                for i in range(10)
            ],
        }

        # Page 2 has the actual AC listing
        resp_p2 = MagicMock()
        resp_p2.status_code = 200
        resp_p2.json.return_value = {
            "count": 22,
            "results": [
                {
                    "title": "Haier 2 Ton Inverter AC 24HFAB",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "220,000"},
                    "vendor": {"name": "AirCool"},
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
            target_desc="Haier 2.0 Ton DC Inverter Split AC HSU-24HFAB",
        )

        assert len(res.offers) == 1
        assert res.offers[0].vendor_name == "AirCool"
        assert res.pages_fetched == 2
        assert res.pagination_complete is True

    asyncio.run(_run())


# ==============================================================================
# 6. Negative Isolation: Incompatible Sub-Models
# ==============================================================================


@pytest.mark.parametrize(
    ("target_desc", "scraped_title", "brand"),
    [
        ("Haier 1.5 Ton HSU-18HFPCA", "Haier 1.5 Ton Inverter AC HSU-18HFP", "Haier"),
        ("Haier 1.5 Ton HSU-18HFP", "Haier 1.5 Ton Inverter AC 18HFPAAS", "Haier"),
        ("Haier 1.5 Ton HSU-19HFPAA", "Haier 1.5 Ton Inverter AC HSU-19HFP", "Haier"),
        ("Haier 1.5 Ton HSU-19HFC", "Haier 1.5 Ton Inverter AC HSU-19HFCS", "Haier"),
        ("Haier 1.0 Ton HSU-13LF", "Haier 1.0 Ton Inverter AC HSU-13HFP", "Haier"),
    ],
)
def test_negative_isolation_incompatible_submodels_rejected(
    target_desc: str, scraped_title: str, brand: str
) -> None:
    """Ensure incompatible AC sub-models are strictly rejected by referee."""
    res = referee_match(
        target_desc,
        scraped_title,
        brand=brand,
    )
    assert res.is_match is False


# ==============================================================================
# 7. False Monopoly Suppression
# ==============================================================================


def test_false_monopoly_suppressed_when_discovery_incomplete() -> None:
    """Ensure pagination or network failure suppresses Monopoly and flags INCOMPLETE_DISCOVERY."""
    cost_base = calculate_cost_base(100000.0, 3000.0)
    floors = calculate_floors(cost_base, min_profit=500.0, net_price=100000.0)

    scrape_res = ScrapeResult(
        offers=[],
        is_success=True,
        status_code=200,
        raw_candidate_count=25,
        rejected_count=10,
        pagination_complete=False,
        discovery_status=DISCOVERY_PAGINATION_INCOMPLETE,
    )

    eval_res = evaluate_alfa_pricing(floors, scrape_res)

    assert eval_res.final_price is None
    assert eval_res.status == STATUS_INCOMPLETE_DISCOVERY
    assert determine_risk_alert(eval_res) == "INCOMPLETE_DISCOVERY"
    assert (
        determine_platform_status(
            eval_res.final_price, None, eval_res.reason, "INCOMPLETE_DISCOVERY"
        )
        == "INCOMPLETE"
    )


def test_false_monopoly_suppressed_when_all_candidates_rejected() -> None:
    """Ensure candidate rejection suppresses Monopoly and flags CANDIDATES_REJECTED."""
    cost_base = calculate_cost_base(100000.0, 3000.0)
    floors = calculate_floors(cost_base, min_profit=500.0, net_price=100000.0)

    scrape_res = ScrapeResult(
        offers=[],
        is_success=True,
        status_code=200,
        raw_candidate_count=8,
        rejected_count=8,
        rejection_reasons={"Appliance category collision (Air Conditioner vs Refrigerator)": 8},
        pagination_complete=True,
        discovery_status=DISCOVERY_CANDIDATES_REJECTED,
    )

    eval_res = evaluate_alfa_pricing(floors, scrape_res)

    assert eval_res.final_price is None
    assert eval_res.status == STATUS_CANDIDATES_REJECTED
    assert determine_risk_alert(eval_res) == "CANDIDATES_REJECTED"
    assert (
        determine_platform_status(
            eval_res.final_price, None, eval_res.reason, "CANDIDATES_REJECTED"
        )
        == "REJECTED"
    )


def test_genuine_monopoly_pricing_when_no_candidates_found() -> None:
    """Ensure genuine Monopoly is applied only when discovery is complete with 0 candidates."""
    cost_base = calculate_cost_base(100000.0, 3000.0)
    floors = calculate_floors(cost_base, min_profit=500.0, net_price=100000.0)

    scrape_res = ScrapeResult(
        offers=[],
        is_success=True,
        status_code=200,
        raw_candidate_count=0,
        rejected_count=0,
        pagination_complete=True,
        discovery_status=DISCOVERY_COMPLETE_NO_COMPETITORS,
    )

    eval_res = evaluate_alfa_pricing(floors, scrape_res)

    assert eval_res.final_price is not None
    assert eval_res.status == "Monopoly Win"
    assert eval_res.real_profit >= 4000
    assert determine_risk_alert(eval_res) == "NONE"


# ==============================================================================
# 8. Yellow Compatibility Notice
# ==============================================================================


def test_yellow_compatibility_notice_propagated_to_result() -> None:
    """Ensure accepted extended model designations produce compatibility notices."""
    cost_base = calculate_cost_base(150000.0, 3500.0)
    floors = calculate_floors(cost_base, min_profit=500.0, net_price=150000.0)

    offer = ScrapedOffer(
        vendor_name="CoolVendor",
        price=190000.0,
        is_sold_out=False,
        raw_title="Haier 1.5 Ton T3 Inverter AC HSU-20HFTEX",
        scraped_model="HSU-20HFTEX",
        missing_modifier="Extended Edition (HSU-20HFTEX)",
    )

    scrape_res = ScrapeResult(
        offers=[offer],
        is_success=True,
        status_code=200,
        extended_model_designation="HSU-20HFTEX",
        discovery_status=DISCOVERY_COMPLETE_WITH_OFFERS,
    )

    eval_res = evaluate_alfa_pricing(floors, scrape_res)

    assert eval_res.final_price is not None
    assert eval_res.compatibility_notice is not None
    assert "HSU-20HFTEX" in eval_res.compatibility_notice
    assert "[COMPATIBILITY NOTICE:" in eval_res.reason


# ==============================================================================
# 9. Inherent Descriptive T3 vs SKU Upgrade -T3
# ==============================================================================


def test_descriptive_t3_in_title_matches_target_without_t3_in_sku() -> None:
    """Ensure marketing descriptive 'T3' does not prevent matching alphanumeric SKU."""
    res = referee_match(
        "Haier 1.5 Ton DC Inverter Split AC HSU-18HFP",
        "Haier 1.5 Ton T3 DC Inverter AC HSU-18HFP",
        brand="Haier",
    )
    assert res.is_match is True


def test_sku_upgrade_dash_t3_rejected_when_not_in_target() -> None:
    """Ensure explicit SKU upgrade '-T3' is rejected when target is base model."""
    res = referee_match(
        "Gree 1 Ton Inverter AC 12AITH21W",
        "Gree 1 Ton Inverter AC 12AITH21W-T3",
        brand="Gree",
    )
    assert res.is_match is False


# ==============================================================================
# 10. HVAC Marketing Token Stripping
# ==============================================================================


def test_hvac_marketing_tokens_stripped_cleanly() -> None:
    """Ensure UPS ENABLED, SELF CLEANING, TURBO, and AMPERE do not corrupt matching."""
    res = referee_match(
        "Haier 1.5 Ton Inverter AC HSU-18HFP",
        "Haier 1.5 Ton Inverter AC HSU-18HFP UPS ENABLED SELF CLEANING TURBO AMPERE",
        brand="Haier",
    )
    assert res.is_match is True


# ==============================================================================
# 11. Technical Electrical Slash Patterns
# ==============================================================================


def test_technical_electrical_slash_preserved() -> None:
    """Ensure electrical slashes like 18HE/DC are not split as separate branches."""
    res = referee_match(
        "PEL 1.5 Ton Inverter AC 18HE/DC",
        "PEL 1.5 Ton Inverter AC 18HE/DC",
        brand="PEL",
    )
    assert res.is_match is True


# ==============================================================================
# 12. 1.0T <-> 1.25T Equivalence on 14k BTU
# ==============================================================================


def test_14k_btu_1_ton_vs_1_25_ton_equivalence() -> None:
    """Ensure identical 14k BTU model is accepted between 1.0T and 1.25T."""
    res = referee_match(
        "Haier 1.25 Ton Inverter AC 14HFT",
        "Haier 1.0 Ton Inverter AC HSU-14HFT",
        brand="Haier",
    )
    assert res.is_match is True


# ==============================================================================
# 13. TV Screen Size Collision Protection in AC Context
# ==============================================================================


def test_tv_screen_size_collision_protection() -> None:
    """Ensure TV screen size detection does not corrupt AC BTU numbers."""
    slots = extract_product_slots("Haier 2 Ton Inverter Split AC 24HFAB", "Haier")
    assert slots.guarded_facets.capacity in ("2.0T", "2.0 Ton", "24000BTU", "2T")
    assert not any("INCH" in str(f) for f in (slots.guarded_facets.capacity or ""))
