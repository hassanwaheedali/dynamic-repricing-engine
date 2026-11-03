"""Comprehensive regression and unit tests for Generic Model Variants, Polarity & Matching Accuracy.

Organized incrementally by vertical implementation slice and covering REG-01 through REG-25.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pricing_engine.matcher import (
    expand_cartesian_branches,
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    referee_match,
)
from pricing_engine.scraper import clear_scraper_cache, scrape_alfamall, scrape_digimall

# ==============================================================================
# SLICE A: Collateral-Safe Pre-Normalization (REG-15 .. REG-21, REG-25)
# ==============================================================================


def test_reg_15_dawlance_top_load_washer_isolated_x_neutralized() -> None:
    """REG-15: Dawlance DWT-1166 X ADS+ matches Dawlance DWT-1166 ADS+ cleanly with 0 warnings."""
    dec_fwd = referee_match(
        "Dawlance DWT-1166 X ADS+",
        "Dawlance DWT-1166 ADS+ Top Load Washing Machine",
        brand="Dawlance",
    )
    assert dec_fwd.is_match is True
    assert dec_fwd.is_base_match is False
    assert dec_fwd.missing_modifier is None

    dec_rev = referee_match(
        "Dawlance DWT-1166 ADS+",
        "Dawlance DWT-1166 X ADS+ Top Load Washing Machine",
        brand="Dawlance",
    )
    assert dec_rev.is_match is True
    assert dec_rev.is_base_match is False
    assert dec_rev.missing_modifier is None


def test_reg_16_dawlance_front_load_washer_isolated_x_neutralized() -> None:
    """REG-16: Dawlance DWF 8200 X INV matches Dawlance DWF 8200 INV cleanly without X anchor suffix."""
    slots = extract_product_slots("Dawlance DWF 8200 X INV", brand="Dawlance")
    assert slots.anchor.upper() == "DWF-8200"

    dec = referee_match(
        "Dawlance DWF 8200 X INV",
        "Dawlance DWF 8200 INV Front Load Washing Machine",
        brand="Dawlance",
    )
    assert dec.is_match is True
    assert dec.is_base_match is False
    assert dec.missing_modifier is None

    dec_daw = referee_match(
        "DAW AUTO W/M FRONT LOAD 8200 X INV",
        "Dawlance DWF-8200 Inverter Front Load Washing Machine",
        brand="Dawlance",
    )
    assert dec_daw.is_match is True


def test_reg_17_spaced_wattage_and_litre_sda_bound_not_white() -> None:
    """REG-17: Spaced '20 L' and '1270 W' after WF-825 bind as specs; 'W' is never White."""
    slots = extract_product_slots("Westpoint WF-825 20 L 1270 W Air Fryer", brand="Westpoint")
    assert slots.anchor.upper() == "WF-825"
    assert slots.guarded_facets.color_family is None

    dec = referee_match(
        "Westpoint WF-825 20 L 1270 W Air Fryer",
        "Westpoint WF-825 Black Air Fryer",
        brand="Westpoint",
    )
    assert dec.is_match is True


@pytest.mark.parametrize(
    ("erp_title", "clean_candidate", "brand"),
    [
        ("Dawlance R/F 91060 Refrigerator", "Dawlance 91060 White Refrigerator", "Dawlance"),
        ("Dawlance D/F 91998 Deep Freezer", "Dawlance 91998 White Deep Freezer", "Dawlance"),
        ("Dawlance W/D 1051 Water Dispenser", "Dawlance WD-1051 Silver Water Dispenser", "Dawlance"),
        ("Westpoint M/O WF-825 Microwave Oven", "Westpoint WF-825 Black Microwave Oven", "Westpoint"),
    ],
)
def test_reg_18_erp_category_slashes_neutralized_before_cartesian_and_color(
    erp_title: str, clean_candidate: str, brand: str
) -> None:
    """REG-18: R/F, D/F, W/D, M/O never split into Cartesian branches or trigger Red/Black color."""
    branches = expand_cartesian_branches(erp_title)
    assert len(branches) == 1

    slots = extract_product_slots(erp_title, brand=brand)
    assert slots.guarded_facets.color_family is None

    dec = referee_match(erp_title, clean_candidate, brand=brand)
    assert dec.is_match is True


@pytest.mark.parametrize(
    ("target_title", "white_candidate", "black_candidate", "brand"),
    [
        (
            "Dawlance DWT 255 W",
            "Dawlance DWT-255 White Washing Machine",
            "Dawlance DWT-255 Black Washing Machine",
            "Dawlance",
        ),
        (
            "Haier HWM 150-826 W",
            "Haier HWM 150-826 White Washing Machine",
            "Haier HWM 150-826 B Washing Machine",
            "Haier",
        ),
        (
            "Haier HWM 150 826 W",
            "Haier HWM 150-826 White Washing Machine",
            "Haier HWM 150-826 Black Washing Machine",
            "Haier",
        ),
        (
            "Dawlance 91999 W Refrigerator",
            "Dawlance 91999 White Refrigerator",
            "Dawlance 91999 Black Refrigerator",
            "Dawlance",
        ),
    ],
)
def test_reg_19_trailing_w_preserved_as_white_color(
    target_title: str, white_candidate: str, black_candidate: str, brand: str
) -> None:
    """REG-19: Trailing 'W' on prefixed, hyphenated, drum-spaced, or primary stems stays White."""
    slots = extract_product_slots(target_title, brand=brand)
    assert slots.guarded_facets.color_family == "White"

    dec_white = referee_match(target_title, white_candidate, brand=brand)
    assert dec_white.is_match is True

    dec_black = referee_match(target_title, black_candidate, brand=brand)
    assert dec_black.is_match is False
    assert any(
        k in dec_black.reason
        for k in ("Color collision", "Single-letter variant suffix collision")
    )


def test_reg_20_non_dawlance_x_series_strictly_enforced() -> None:
    """REG-20: Non-Dawlance 'X' series (TCL 55\" X Series QLED TV) strictly rejects C Series."""
    dec = referee_match(
        'TCL 55" X Series QLED TV',
        'TCL 55" C Series QLED TV',
        brand="TCL",
    )
    assert dec.is_match is False


def test_reg_21_dimension_x_between_digits_preserved() -> None:
    """REG-21: 'X' between digits (24 X 24) is preserved even for Dawlance."""
    _, model = extract_search_query_and_model(
        "Dawlance Kitchen Hood 24 X 24 Stainless", brand="Dawlance"
    )
    dec_match = referee_match(
        "Dawlance Kitchen Hood DHS-900 24 X 24 Stainless",
        "Dawlance Kitchen Hood DHS-900 24 X 24 Stainless",
        brand="Dawlance",
    )
    assert dec_match.is_match is True
    assert model != ""


def test_reg_25_dynamic_spaced_prefix_pinv_12k() -> None:
    """REG-25: Spaced 'PINV 12K' binds dynamically to 'PINV-12K' and is not dropped as resolution."""
    query, model = extract_search_query_and_model("Pel PINV 12K Inverter AC", brand="Pel")
    assert "PINV-12K" in model.upper()
    assert "12K" in query.upper()

    slots = extract_product_slots("Pel PINV 12K Inverter AC", brand="Pel")
    assert slots.anchor.upper() == "PINV-12K"

    dec = referee_match(
        "Pel PINV 12K Inverter AC",
        "Pel PINV-12K 1 Ton DC Inverter AC",
        brand="Pel",
    )
    assert dec.is_match is True


# ==============================================================================
# SLICE B: Item #23 AC Subordinate Slash & AC-Only DC Inference (REG-10, 14, 24)
# ==============================================================================


def test_slice_b_item_23_subordinate_ac_slash_and_dc_inverter() -> None:
    """REG-10 (Matcher): HPU-48HE/012DC(GE)-T3 isolates 012DC(GE), prevents orphan GE, and sets AC inverter."""
    cand_title = "Haier HPU-48HE/012DC(GE)-T3 4 Ton Heat & Cool Cabinet Air Conditioner"
    cand_slots = extract_product_slots(cand_title, brand="Haier")
    assert cand_slots.anchor.upper() == "HPU-48HE"
    assert "012DC(GE)" in [c.upper() for c in cand_slots.subordinate_codes]
    assert "GE" not in cand_slots.guarded_facets.capabilities
    assert cand_slots.guarded_facets.is_inverter is True
    assert "T3" in cand_slots.guarded_facets.capabilities

    dec = referee_match(
        "Haier 4 Ton Inverter Floor Standing AC HPU-48HE",
        cand_title,
        brand="Haier",
    )
    assert dec.is_match is True


def test_slice_b_ac_dc_suffix_respects_explicit_non_inverter() -> None:
    """Explicit Non-Inverter / Fixed Speed must never be overridden by /DC suffix."""
    slots = extract_product_slots("Haier Non-Inverter 18HE/DC Split AC", brand="Haier")
    assert slots.guarded_facets.is_inverter is False


def test_reg_14_non_ac_direct_cool_refrigerator_dc_isolated() -> None:
    """REG-14: Direct Cool ('DC') refrigerator never triggers AC is_inverter=True."""
    slots = extract_product_slots("Dawlance Refrigerator DC 91060", brand="Dawlance")
    assert slots.guarded_facets.is_inverter is None

    dec = referee_match(
        "Dawlance Refrigerator DC 91060",
        "Dawlance Refrigerator 91060",
        brand="Dawlance",
    )
    assert dec.is_match is True


def test_reg_24_non_ac_color_slash_wb_preserved_and_enforced() -> None:
    """REG-24: /WB on refrigerator SKU is untouched by AC subordinate regex and enforces Wood Brown."""
    slots = extract_product_slots("Dawlance DMB-91060/WB Refrigerator", brand="Dawlance")
    assert slots.anchor.upper() == "DMB-91060"
    assert slots.subordinate_codes == []
    assert slots.guarded_facets.color_family == "Brown / Wood"

    dec_match = referee_match(
        "Dawlance DMB-91060/WB Refrigerator",
        "Dawlance DMB-91060 Wood Brown Refrigerator",
        brand="Dawlance",
    )
    assert dec_match.is_match is True

    dec_gd = referee_match(
        "Dawlance DMB-91060/WB Refrigerator",
        "Dawlance DMB-91060/GD Refrigerator",
        brand="Dawlance",
    )
    assert dec_gd.is_match is False

    dec_white = referee_match(
        "Dawlance DMB-91060/WB Refrigerator",
        "Dawlance DMB-91060 White Refrigerator",
        brand="Dawlance",
    )
    assert dec_white.is_match is False


# ==============================================================================
# SLICE C: AC SKU Decomposition & Fallback Search Emission
# ==============================================================================


def test_slice_c_ac_sku_decomposition_exact_boundaries() -> None:
    """2-digit capacity + 3-letter AC core series stem + optional 1-2 char sub-model tag."""
    s_ca = extract_product_slots("Haier 1.5 Ton Inverter AC 18HFPCA", brand="Haier")
    assert s_ca.base_stem == "18HFP"
    assert s_ca.sub_model_tag == "CA"

    s_e = extract_product_slots("Haier 1.5 Ton Inverter AC HSU-18HFPE", brand="Haier")
    assert s_e.base_stem == "18HFP"
    assert s_e.sub_model_tag == "E"

    s_base = extract_product_slots("Haier 1.5 Ton Inverter AC HSU-18HFP", brand="Haier")
    assert s_base.base_stem == "18HFP"
    assert s_base.sub_model_tag == ""

    s_hfa = extract_product_slots("Haier 1.5 Ton Inverter AC HSU-18HFA", brand="Haier")
    assert s_hfa.base_stem == "18HFA"
    assert s_hfa.sub_model_tag == ""
    assert s_hfa.base_stem != s_ca.base_stem

    # 3-char suffix 'AAS' exceeds 1-2 char sub-edition bound -> must NOT decompose
    s_aas = extract_product_slots("Haier 1.5 Ton Inverter AC 18HFPAAS", brand="Haier")
    assert s_aas.base_stem == ""
    assert s_aas.sub_model_tag == ""

    # Non-AC refrigerator must never populate AC base_stem
    s_ref = extract_product_slots("Haier HRF-306EBS Refrigerator", brand="Haier")
    assert s_ref.base_stem == ""
    assert s_ref.sub_model_tag == ""


def test_slice_c_search_patterns_emit_base_stem_fallback() -> None:
    """When AC SKU decomposes into base_stem + sub_model_tag, search patterns include base_stem."""
    pats = generate_search_patterns("Haier 1.5 Ton DC Inverter Split AC 18HFPCA", brand="Haier")
    fallback_queries = [q.upper() for q in pats["tier_2"] + pats["tier_3"]]
    assert "18HFP" in fallback_queries
    assert "HAIER 18HFP" in fallback_queries


# ==============================================================================
# SLICE D & SLICE E: Capability Polarity, Ambiguity & Canonical 3-Tier Referee
# (REG-01 .. REG-09, REG-12, REG-13, REG-22, REG-23)
# ==============================================================================


def test_reg_01_exact_t3_match_tier_1_zero_warnings() -> None:
    """REG-01: Haier 18HFP T3 vs Haier 18HFP T3 Inverter -> Match (Tier 1), 0 warnings."""
    dec = referee_match("Haier 18HFP T3", "Haier 18HFP T3 Inverter", brand="Haier")
    assert dec.is_match is True
    assert dec.match_tier == 1
    assert dec.compatibility_notice is None


@pytest.mark.parametrize(
    ("reg_id", "negated_candidate"),
    [
        ("REG-02", "Haier 18HFP Non-T3 Inverter"),
        ("REG-03", "Haier 18HFP Non_T3 Inverter"),
        ("REG-04", "Haier 18HFP Non T3 Inverter"),
        ("REG-05", "Haier 18HFP NonT3 Inverter"),
    ],
)
def test_reg_02_to_05_negated_t3_all_delimiters_rejected(
    reg_id: str, negated_candidate: str
) -> None:
    """REG-02..REG-05: Negated T3 with hyphen, underscore, space, or glued -> Rule B REJECT."""
    cand_slots = extract_product_slots(negated_candidate, brand="Haier")
    assert "T3" in cand_slots.guarded_facets.negative_capabilities
    assert "T3" not in cand_slots.guarded_facets.capabilities

    dec = referee_match("Haier 18HFP T3", negated_candidate, brand="Haier")
    assert dec.is_match is False
    assert dec.is_base_match is False
    assert dec.match_tier is None
    assert "contradiction" in dec.reason.lower(), f"{reg_id} failed: {dec.reason}"


def test_reg_06_internal_ambiguity_t3_non_t3_rejected() -> None:
    """REG-06: Candidate claiming both 'T3' and 'Non-T3' -> Rule A 100% REJECT."""
    cand_slots = extract_product_slots("Haier 18HFP T3 Non-T3 Inverter", brand="Haier")
    assert "T3" in cand_slots.guarded_facets.ambiguous_capabilities
    assert "T3" not in cand_slots.guarded_facets.capabilities
    assert "T3" not in cand_slots.guarded_facets.negative_capabilities

    dec = referee_match("Haier 18HFP T3", "Haier 18HFP T3 Non-T3 Inverter", brand="Haier")
    assert dec.is_match is False
    assert dec.match_tier is None
    assert "ambiguous specification conflict" in dec.reason.lower()


def test_reg_07_internal_ambiguity_wifi_without_wifi_rejected() -> None:
    """REG-07: Candidate claiming both 'WiFi' and 'Without-WiFi' -> Rule A 100% REJECT."""
    cand_slots = extract_product_slots("Dawlance Inverter WiFi Without-WiFi AC", brand="Dawlance")
    assert "WIFI" in cand_slots.guarded_facets.ambiguous_capabilities

    dec = referee_match(
        "Dawlance 1.5 Ton Sprinter 30 Inverter AC",
        "Dawlance 1.5 Ton Sprinter 30 Inverter WiFi Without-WiFi AC",
        brand="Dawlance",
    )
    assert dec.is_match is False
    assert dec.match_tier is None
    assert "ambiguous specification conflict" in dec.reason.lower()


def test_reg_08_negated_wifi_contradiction_rejected() -> None:
    """REG-08: Target(+WIFI) vs Candidate(Without-WiFi) -> Rule B 100% REJECT."""
    dec = referee_match(
        "Dawlance Sprinter 30 WiFi Inverter AC",
        "Dawlance Sprinter 30 Without-WiFi Inverter AC",
        brand="Dawlance",
    )
    assert dec.is_match is False
    assert dec.match_tier is None
    assert "contradiction" in dec.reason.lower()


def test_reg_09_optional_t3_prose_rule_c_notice() -> None:
    """REG-09: Target omits T3 (not negated), candidate specifies +T3 -> Tier 1 + Rule C Notice."""
    dec = referee_match("Haier 18HFP Inverter", "Haier 18HFP T3 Inverter", brand="Haier")
    assert dec.is_match is True
    assert dec.match_tier == 1
    assert (
        dec.compatibility_notice
        == "ℹ️ [OPTIONAL SPECIFICATION: Target did not specify 'T3', but market listing specifies 'T3']"
    )


def test_unrelated_negative_promo_prose_does_not_negate_t3() -> None:
    """Unrelated 'No Markup' / 'Without Interest' prose must never negate nearby T3."""
    dec = referee_match(
        "Haier 18HFP T3 Inverter",
        "Haier 18HFP No Markup Without Interest T3 Inverter AC",
        brand="Haier",
    )
    assert dec.is_match is True
    assert dec.match_tier == 1


def test_reg_12_item_64_base_model_tier_2_referee_and_notice() -> None:
    """REG-12 (Referee): 18HFPCA vs HSU-18HFP -> Tier 2 Base Fallback + Yellow Notice."""
    dec = referee_match(
        "Haier 18HFPCA 1.5 Ton Inverter AC",
        "Haier HSU-18HFP 1.5 Ton Inverter AC",
        brand="Haier",
    )
    assert dec.is_match is False
    assert dec.is_base_match is True
    assert dec.match_tier == 2
    assert (
        dec.compatibility_notice
        == "⚠️ [FALLBACK MODEL: Target specified '18HFPCA', but market listing is base model 'HSU-18HFP']"
    )


def test_reg_13_item_64_sibling_tier_3_and_cross_series_isolation() -> None:
    """REG-13 (Referee): 18HFPCA vs HSU-18HFPE -> Tier 3 Sibling Fallback; 18HFA strictly rejected."""
    dec_sib = referee_match(
        "Haier 18HFPCA 1.5 Ton Inverter AC",
        "Haier HSU-18HFPE 1.5 Ton Inverter AC",
        brand="Haier",
    )
    assert dec_sib.is_match is False
    assert dec_sib.is_base_match is False
    assert dec_sib.match_tier == 3
    assert (
        dec_sib.compatibility_notice
        == "⚠️ [SIBLING SUB-MODEL FALLBACK: Target specified '18HFPCA', but market listing is sibling edition 'HSU-18HFPE' sharing base '18HFP']"
    )

    # Distinct 3-letter series stem (18HFA Marvel vs 18HFP Pearl) -> 100% REJECT
    dec_hfa = referee_match(
        "Haier 18HFPCA 1.5 Ton Inverter AC",
        "Haier HSU-18HFA 1.5 Ton Inverter AC",
        brand="Haier",
    )
    assert dec_hfa.is_match is False
    assert dec_hfa.is_base_match is False
    assert dec_hfa.match_tier is None

    # Guarded facet invariance across Tier 2 & Tier 3: Cool Only vs Heat & Cool or Non-Inverter must REJECT!
    dec_bad_inv = referee_match(
        "Haier 18HFPCA 1.5 Ton Inverter AC",
        "Haier HSU-18HFPE 1.5 Ton Non-Inverter AC",
        brand="Haier",
    )
    assert dec_bad_inv.match_tier is None

    dec_bad_mode = referee_match(
        "Haier 18HFPCA 1.5 Ton Cool Only Inverter AC",
        "Haier HSU-18HFPE 1.5 Ton Heat & Cool Inverter AC",
        brand="Haier",
    )
    assert dec_bad_mode.match_tier is None


def test_reg_22_ads_plus_trailing_plus_boundary_preserved() -> None:
    """REG-22: (?!\\w) preserves '+' in 'ADS+' before space and hyphen; ADS vs ADS+ stays distinct."""
    s_space = extract_product_slots("Dawlance DWT-1166 X ADS+ Washing Machine", brand="Dawlance")
    assert "ADS+" in s_space.guarded_facets.capabilities

    s_hyphen = extract_product_slots("Dawlance DWT-1166 ADS+-11KG Washing Machine", brand="Dawlance")
    assert "ADS+" in s_hyphen.guarded_facets.capabilities

    dec_exact = referee_match(
        "Dawlance DWT-1166 X ADS+ Washing Machine",
        "Dawlance DWT-1166 ADS+ Washing Machine",
        brand="Dawlance",
    )
    assert dec_exact.is_match is True
    assert dec_exact.match_tier == 1
    assert dec_exact.compatibility_notice is None

    dec_contra = referee_match(
        "Dawlance DWT-1166 ADS+ Washing Machine",
        "Dawlance DWT-1166 Non-ADS+ Washing Machine",
        brand="Dawlance",
    )
    assert dec_contra.is_match is False
    assert dec_contra.match_tier is None


def test_reg_23_omitted_target_t3_rule_d_demoted_to_tier_2() -> None:
    """REG-23: Target specifies T3, candidate omits T3 -> Rule D demotes to Tier 2 Fallback + Notice."""
    dec = referee_match("Haier 18HFP T3 Inverter", "Haier 18HFP Inverter", brand="Haier")
    assert dec.is_match is False
    assert dec.is_base_match is True
    assert dec.match_tier == 2
    assert (
        dec.compatibility_notice
        == "⚠️ [FALLBACK MODEL: Target specified 'T3', but market listing omitted 'T3']"
    )


# ==============================================================================
# SLICE F: Per-Platform 3-Tier Waterfall Priority (REG-11, REG-12, REG-13)
# ==============================================================================


def _mock_storefront_session(items: list[dict[str, object]]) -> AsyncMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"results": items}
    sess = AsyncMock()
    sess.get.return_value = resp
    return sess


def test_reg_11_waterfall_tier_1_wins_over_cheaper_tier_2_and_3_any_order() -> None:
    """REG-11: Exact Tier 1 (18HFPCA @ 148k) always beats cheaper Tier 2 (140k) & Tier 3 (139k)."""
    item_t1 = {
        "title": "Haier 1.5 Ton Inverter AC 18HFPCA",
        "sold_out": False,
        "variant_detail": {"discounted_price": "148,000"},
        "vendor": {"name": "ExactSeller"},
    }
    item_t2 = {
        "title": "Haier 1.5 Ton Inverter AC HSU-18HFP",
        "sold_out": False,
        "variant_detail": {"discounted_price": "140,000"},
        "vendor": {"name": "BaseSeller"},
    }
    item_t3 = {
        "title": "Haier 1.5 Ton Inverter AC HSU-18HFPE",
        "sold_out": False,
        "variant_detail": {"discounted_price": "139,000"},
        "vendor": {"name": "SiblingSeller"},
    }

    async def _run() -> None:
        for ordered_items in ([item_t1, item_t2, item_t3], [item_t3, item_t2, item_t1]):
            clear_scraper_cache()
            sess = _mock_storefront_session(ordered_items)
            res = await scrape_alfamall(
                sess,
                {"tier_1": ["Haier 18HFPCA"], "tier_2": ["Haier 18HFP"]},
                target_model="18HFPCA",
                brand="Haier",
                target_desc="Haier 18HFPCA 1.5 Ton Inverter AC",
            )
            assert len(res.offers) == 1
            assert res.offers[0].vendor_name == "ExactSeller"
            assert res.offers[0].price == 148000.0
            assert res.offers[0].match_tier == 1
            assert res.compatibility_notice is None
            assert len(res.sibling_offers) == 1

    asyncio.run(_run())


def test_slice_f_sold_out_tier_1_falls_back_to_in_stock_tier_2() -> None:
    """REG-12 (Waterfall): Sold-out Tier 1 falls back to in-stock Tier 2 HSU-18HFP with notice."""
    items = [
        {
            "title": "Haier 1.5 Ton Inverter AC 18HFPCA",
            "sold_out": True,
            "variant_detail": {"discounted_price": "145,000"},
            "vendor": {"name": "SoldOutExact"},
        },
        {
            "title": "Haier 1.5 Ton Inverter AC HSU-18HFP",
            "sold_out": False,
            "variant_detail": {"discounted_price": "142,000"},
            "vendor": {"name": "InStockBase"},
        },
        {
            "title": "Haier 1.5 Ton Inverter AC HSU-18HFPE",
            "sold_out": False,
            "variant_detail": {"discounted_price": "138,000"},
            "vendor": {"name": "CheaperSibling"},
        },
    ]

    async def _run() -> None:
        clear_scraper_cache()
        sess = _mock_storefront_session(items)
        res = await scrape_alfamall(
            sess,
            {"tier_1": ["Haier 18HFPCA"], "tier_2": ["Haier 18HFP"]},
            target_model="18HFPCA",
            brand="Haier",
            target_desc="Haier 18HFPCA 1.5 Ton Inverter AC",
        )
        assert len(res.offers) == 1
        assert res.offers[0].vendor_name == "InStockBase"
        assert res.offers[0].match_tier == 2
        assert (
            res.compatibility_notice
            == "⚠️ [FALLBACK MODEL: Target specified '18HFPCA', but market listing is base model 'HSU-18HFP']"
        )

    asyncio.run(_run())


def test_slice_f_missing_tier_1_and_2_falls_back_to_tier_3_sibling() -> None:
    """REG-13 (Waterfall): Zero Tier 1 & Tier 2 offers -> falls back to Tier 3 HSU-18HFPE; rejects 18HFA."""
    items = [
        {
            "title": "Haier 1.5 Ton Inverter AC HSU-18HFA",
            "sold_out": False,
            "variant_detail": {"discounted_price": "130,000"},
            "vendor": {"name": "WrongMarvelSeries"},
        },
        {
            "title": "Haier 1.5 Ton Inverter AC HSU-18HFPE",
            "sold_out": False,
            "variant_detail": {"discounted_price": "144,000"},
            "vendor": {"name": "SiblingPearlSeries"},
        },
    ]

    async def _run() -> None:
        clear_scraper_cache()
        sess = _mock_storefront_session(items)
        res = await scrape_alfamall(
            sess,
            {"tier_1": ["Haier 18HFPCA"], "tier_2": ["Haier 18HFP"]},
            target_model="18HFPCA",
            brand="Haier",
            target_desc="Haier 18HFPCA 1.5 Ton Inverter AC",
        )
        assert len(res.offers) == 1
        assert res.offers[0].vendor_name == "SiblingPearlSeries"
        assert res.offers[0].price == 144000.0
        assert res.offers[0].match_tier == 3
        assert (
            res.compatibility_notice
            == "⚠️ [SIBLING SUB-MODEL FALLBACK: Target specified '18HFPCA', but market listing is sibling edition 'HSU-18HFPE' sharing base '18HFP']"
        )

    asyncio.run(_run())


def test_slice_f_per_platform_independence_alfa_vs_digi() -> None:
    """AlfaMall Tier 1 exact win never suppresses or leaks into DigiMall Tier 3 sibling fallback."""
    alfa_items = [
        {
            "title": "Haier 1.5 Ton Inverter AC 18HFPCA",
            "sold_out": False,
            "variant_detail": {"discounted_price": "148,000"},
            "vendor": {"name": "AlfaExactSeller"},
        }
    ]
    digi_items = [
        {
            "title": "Haier 1.5 Ton Inverter AC HSU-18HFPE",
            "sold_out": False,
            "variant_detail": {"discounted_price": "144,000"},
            "vendor": {"name": "DigiSiblingSeller"},
        }
    ]

    async def _run() -> None:
        clear_scraper_cache()
        alfa_res = await scrape_alfamall(
            _mock_storefront_session(alfa_items),
            {"tier_1": ["Haier 18HFPCA"], "tier_2": ["Haier 18HFP"]},
            target_model="18HFPCA",
            brand="Haier",
            target_desc="Haier 18HFPCA 1.5 Ton Inverter AC",
        )
        digi_res = await scrape_digimall(
            _mock_storefront_session(digi_items),
            {"tier_1": ["Haier 18HFPCA"], "tier_2": ["Haier 18HFP"]},
            target_model="18HFPCA",
            brand="Haier",
            target_desc="Haier 18HFPCA 1.5 Ton Inverter AC",
        )
        assert alfa_res.offers[0].match_tier == 1
        assert alfa_res.compatibility_notice is None
        assert digi_res.offers[0].match_tier == 3
        assert digi_res.compatibility_notice is not None
        assert "SIBLING SUB-MODEL FALLBACK" in digi_res.compatibility_notice

    asyncio.run(_run())


# ==============================================================================
# SLICE G: Evaluator & Pricing Integration (REG-10 & Notice Propagation)
# ==============================================================================


def test_slice_g_evaluator_propagates_rule_c_optional_specification_notice() -> None:
    """Rule C Tier 1 match propagates OPTIONAL SPECIFICATION notice without false FALLBACK MODEL."""
    from pricing_engine.calculator import calculate_cost_base, calculate_floors
    from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing

    items = [
        {
            "title": "Haier 1.5 Ton T3 DC Inverter AC HSU-18HFP",
            "sold_out": False,
            "variant_detail": {"discounted_price": "165,000"},
            "vendor": {"name": "MarketSeller"},
        }
    ]

    async def _run() -> None:
        clear_scraper_cache()
        res = await scrape_alfamall(
            _mock_storefront_session(items),
            {"tier_1": ["Haier HSU-18HFP"]},
            target_model="HSU-18HFP",
            brand="Haier",
            target_desc="Haier 1.5 Ton DC Inverter Split AC HSU-18HFP",
        )
        floors = calculate_floors(calculate_cost_base(125000.0, 2500.0))
        alfa_eval = evaluate_alfa_pricing(floors, res)
        digi_eval = evaluate_digi_pricing(floors, res)

        expected = (
            "ℹ️ [OPTIONAL SPECIFICATION: Target did not specify 'T3', "
            "but market listing specifies 'T3']"
        )
        assert alfa_eval.compatibility_notice == expected
        assert digi_eval.compatibility_notice == expected
        assert "[OPTIONAL SPECIFICATION:" in alfa_eval.reason
        assert "[OPTIONAL SPECIFICATION:" in digi_eval.reason
        assert "[FALLBACK MODEL:" not in alfa_eval.reason
        assert "[FALLBACK MODEL:" not in digi_eval.reason

    asyncio.run(_run())


def test_slice_g_evaluator_propagates_tier_2_and_tier_3_notices_without_duplication() -> None:
    """Tier 2 and Tier 3 AC sub-model notices propagate cleanly into evaluator reason once."""
    from pricing_engine.calculator import calculate_cost_base, calculate_floors
    from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
    from pricing_engine.models import ScrapeResult

    floors = calculate_floors(calculate_cost_base(115000.0, 2500.0))

    async def _run() -> None:
        # 1. Tier 2 base model fallback (18HFPCA -> HSU-18HFP)
        clear_scraper_cache()
        t2_items = [
            {
                "title": "Haier 1.5 Ton Inverter AC HSU-18HFP",
                "sold_out": False,
                "variant_detail": {"discounted_price": "148,000"},
                "vendor": {"name": "BaseSeller"},
            }
        ]
        res_t2 = await scrape_alfamall(
            _mock_storefront_session(t2_items),
            {"tier_1": ["Haier 18HFPCA"], "tier_2": ["Haier 18HFP"]},
            target_model="18HFPCA",
            brand="Haier",
            target_desc="Haier 18HFPCA 1.5 Ton Inverter AC",
        )
        eval_t2 = evaluate_alfa_pricing(floors, res_t2)
        assert (
            eval_t2.compatibility_notice
            == "⚠️ [FALLBACK MODEL: Target specified '18HFPCA', but market listing is base model 'HSU-18HFP']"
        )
        assert eval_t2.reason.count("[FALLBACK MODEL:") == 1
        assert "base model 'HSU-18HFP'" in eval_t2.reason

        # 2. Tier 3 sibling fallback (18HFPCA -> HSU-18HFPE)
        clear_scraper_cache()
        t3_items = [
            {
                "title": "Haier 1.5 Ton Inverter AC HSU-18HFPE",
                "sold_out": False,
                "variant_detail": {"discounted_price": "146,000"},
                "vendor": {"name": "SiblingSeller"},
            }
        ]
        res_t3 = await scrape_digimall(
            _mock_storefront_session(t3_items),
            {"tier_1": ["Haier 18HFPCA"], "tier_2": ["Haier 18HFP"]},
            target_model="18HFPCA",
            brand="Haier",
            target_desc="Haier 18HFPCA 1.5 Ton Inverter AC",
        )
        eval_t3 = evaluate_digi_pricing(floors, res_t3)
        assert (
            eval_t3.compatibility_notice
            == "⚠️ [SIBLING SUB-MODEL FALLBACK: Target specified '18HFPCA', but market listing is sibling edition 'HSU-18HFPE' sharing base '18HFP']"
        )
        assert eval_t3.reason.count("[SIBLING SUB-MODEL FALLBACK:") == 1
        assert "[FALLBACK MODEL:" not in eval_t3.reason

        # 3. Monopoly & Server Down suppress compatibility prefixes
        mono_res = ScrapeResult(
            offers=[],
            is_success=True,
            status_code=200,
            compatibility_notice="⚠️ [SIBLING SUB-MODEL FALLBACK: stale]",
        )
        eval_mono = evaluate_alfa_pricing(floors, mono_res)
        assert eval_mono.status == "Monopoly Win"
        assert "[SIBLING SUB-MODEL FALLBACK:" not in eval_mono.reason
        assert eval_mono.compatibility_notice is None

    asyncio.run(_run())


def test_reg_10_item_23_floor_math_own_store_monopoly_and_external_undercut() -> None:
    """REG-10: Item #23 Haier HPU-48HE Option [1]/[3] floors, Kia Chahiye monopoly, and external undercut."""
    import math

    from pricing_engine.calculator import (
        calculate_cost_base,
        calculate_floors,
        find_winning_psychological_price,
    )
    from pricing_engine.evaluator import evaluate_alfa_pricing
    from pricing_engine.matcher import generate_search_patterns

    cost_base = calculate_cost_base(490000.0, 3500.0)
    assert cost_base == 493500.0

    floors_opt1 = calculate_floors(cost_base, min_profit=500.0, personal_comm_pct=0.0)
    floors_opt3 = calculate_floors(cost_base, min_profit=500.0, personal_comm_pct=5.0)
    assert math.ceil(floors_opt1.floor_alfa) == 548889
    assert math.ceil(floors_opt3.floor_alfa) == 548919
    assert find_winning_psychological_price(floors_opt3.floor_alfa, 580000.0) == 579899

    target_desc = "Haier 4 Ton Cabinet AC HPU-48HE"
    patterns = generate_search_patterns(target_desc, brand="Haier")

    async def _run() -> None:
        # 1. Actual own-store listing (Kia Chahiye Pvt Ltd @ Rs. 580,000) -> Monopoly Rs. 552,999
        clear_scraper_cache()
        own_items = [
            {
                "title": "Haier Floor Standing Inverter 4 Ton HPU-48HE/012DC(GE)-T3",
                "sold_out": False,
                "variant_detail": {"discounted_price": "580,000"},
                "vendor": {"name": "Kia Chahiye Pvt Ltd"},
            }
        ]
        res_own = await scrape_alfamall(
            _mock_storefront_session(own_items),
            patterns,
            target_model="HPU-48HE",
            brand="Haier",
            target_desc=target_desc,
        )
        assert len(res_own.offers) == 0
        assert len(res_own.own_offers) == 1
        eval_own = evaluate_alfa_pricing(floors_opt1, res_own)
        assert eval_own.status == "Monopoly Win"
        assert eval_own.final_price == 552999
        assert "[OWN STORE ACTIVE: Kia Chahiye Pvt Ltd @ Rs. 580,000]" in eval_own.reason

        # 2. Hypothetical external competitor @ Rs. 580,000 -> uncapped psychological 579,899 & sweet-spot win
        clear_scraper_cache()
        ext_items = [
            {
                "title": "Haier Floor Standing Inverter 4 Ton HPU-48HE/012DC(GE)-T3",
                "sold_out": False,
                "variant_detail": {"discounted_price": "580,000"},
                "vendor": {"name": "External HVAC Store"},
            }
        ]
        res_ext = await scrape_alfamall(
            _mock_storefront_session(ext_items),
            patterns,
            target_model="HPU-48HE",
            brand="Haier",
            target_desc=target_desc,
        )
        assert len(res_ext.offers) == 1
        assert find_winning_psychological_price(floors_opt3.floor_alfa, res_ext.offers[0].price) == 579899
        eval_ext = evaluate_alfa_pricing(floors_opt3, res_ext)
        assert eval_ext.status == "Competitive Win"
        assert eval_ext.final_price is not None
        assert 548919 <= eval_ext.final_price < 580000
        assert eval_ext.compatibility_notice is not None
        assert "[OPTIONAL SPECIFICATION:" in eval_ext.reason

    asyncio.run(_run())


# ==============================================================================
# SLICE H: Terminal Cards, Summary Badges & CSV/XLSX Soft Yellow Fill
# ==============================================================================


def test_slice_h_summary_price_cross_check_badge_all_notice_types() -> None:
    """_format_summary_price triggers CROSS-CHECK badge for all compatibility & fallback notices."""
    from pricing_engine.pipeline import _format_summary_price

    clean_out = _format_summary_price(
        147899,
        min_comp_price=148000.0,
        reason="Undercut lowest competitor ExactSeller (Rs. 148,000) to winning price Rs. 147,899.",
    )
    assert "CROSS-CHECK" not in clean_out

    for notice_reason in (
        "⚠️ [FALLBACK MODEL: Target specified '18HFPCA', but market listing is base model 'HSU-18HFP'] Undercut lowest competitor.",
        "⚠️ [SIBLING SUB-MODEL FALLBACK: Target specified '18HFPCA', but market listing is sibling edition 'HSU-18HFPE' sharing base '18HFP'] Undercut lowest competitor.",
        "ℹ️ [OPTIONAL SPECIFICATION: Target did not specify 'T3', but market listing specifies 'T3'] Undercut lowest competitor.",
        "⚠️ [CROSS-CHECK NOTICE: Market listing includes 'WIFI' not specified in target catalog] Undercut lowest competitor.",
        "[COMPATIBILITY NOTICE: Accepted legitimate extended model designation 'HSU-20HFTEX' — verify edition/color alignment] Undercut lowest competitor.",
    ):
        badge_out = _format_summary_price(143899, min_comp_price=144000.0, reason=notice_reason)
        assert "CROSS-CHECK" in badge_out, f"Missing CROSS-CHECK for: {notice_reason}"


def test_slice_h_audit_card_renders_single_clean_notice_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    """render_audit_card renders yellow compatibility/fallback notice panel cleanly without duplication."""
    from io import StringIO

    from rich.console import Console

    import pricing_engine.pipeline as pipeline_mod
    from pricing_engine.calculator import calculate_baseline, calculate_cost_base, calculate_floors
    from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
    from pricing_engine.models import ProductInput, ScrapedOffer, ScrapeResult

    buf = StringIO()
    test_console = Console(file=buf, width=120, force_terminal=False, color_system=None)
    monkeypatch.setattr(pipeline_mod, "console", test_console)

    product = ProductInput(
        sno=64,
        brand="Haier",
        name="Haier 18HFPCA 1.5 Ton Inverter AC",
        length=0.0,
        width=0.0,
        height=0.0,
        net_price=115000.0,
        profit=500.0,
        raw_row={"Brand": "Haier", "Name": "Haier 18HFPCA 1.5 Ton Inverter AC", "Net Price": 115000},
    )
    cost_base = calculate_cost_base(115000.0, 2500.0)
    floors = calculate_floors(cost_base)
    baseline = calculate_baseline(cost_base, 500.0)

    sib_notice = (
        "⚠️ [SIBLING SUB-MODEL FALLBACK: Target specified '18HFPCA', "
        "but market listing is sibling edition 'HSU-18HFPE' sharing base '18HFP']"
    )
    sib_offer = ScrapedOffer(
        vendor_name="SiblingSeller",
        price=144000.0,
        is_sold_out=False,
        raw_title="Haier 1.5 Ton Inverter AC HSU-18HFPE",
        missing_modifier="CA->E",
        modifier_source="market",
        scraped_model="HSU-18HFPE",
        match_tier=3,
        compatibility_notice=sib_notice,
    )
    alfa_scrape = ScrapeResult(
        offers=[sib_offer],
        sibling_offers=[sib_offer],
        active_modifier_fallback="CA->E",
        active_modifier_source="market",
        compatibility_notice=sib_notice,
    )
    digi_scrape = ScrapeResult(offers=[])
    alfa_res = evaluate_alfa_pricing(floors, alfa_scrape)
    digi_res = evaluate_digi_pricing(floors, digi_scrape)

    pipeline_mod.render_audit_card(
        product=product,
        shipping=2500.0,
        floors=floors,
        baseline_calc=baseline,
        target_model="18HFPCA",
        alfa_offers=alfa_scrape,
        digi_offers=digi_scrape,
        alfa_res=alfa_res,
        digi_res=digi_res,
        is_shipping_fallback=True,
    )
    rendered = buf.getvalue()
    assert "SIBLING SUB-MODEL FALLBACK" in rendered
    assert "MARKET VARIANT 'CA->E' DETECTED" not in rendered


def test_slice_h_csv_schema_preserved_and_xlsx_soft_yellow_fill_applied(tmp_path: object) -> None:
    """Option A + Soft Yellow Fill: CSV schema unchanged; XLSX highlights notice rows in soft yellow."""
    from pathlib import Path

    import openpyxl
    import pandas as pd

    from pricing_engine.calculator import calculate_baseline, calculate_cost_base, calculate_floors
    from pricing_engine.exporter import export_results
    from pricing_engine.models import PlatformPricingResult, ProductInput
    from pricing_engine.pipeline import build_output_record

    out_dir = Path(str(tmp_path)) / "exports"
    cost_base = calculate_cost_base(115000.0, 2500.0)
    floors = calculate_floors(cost_base)
    baseline = calculate_baseline(cost_base, 500.0)

    p_clean = ProductInput(
        sno=1,
        brand="Haier",
        name="Haier 18HFP T3 Inverter AC",
        length=0.0,
        width=0.0,
        height=0.0,
        net_price=115000.0,
        profit=500.0,
        raw_row={"Brand": "Haier", "Name": "Haier 18HFP T3 Inverter AC", "Net Price": 115000},
    )
    r_clean = build_output_record(
        product=p_clean,
        shipping=2500.0,
        floors=floors,
        baseline_calc=baseline,
        alfa_res=PlatformPricingResult(
            min_price=148000.0,
            max_price=148000.0,
            final_price=141499,
            real_profit=9849,
            status="Competitive Win",
            reason="Undercut lowest competitor ExactSeller (Rs. 148,000) to winning price Rs. 141,499.",
        ),
        digi_res=PlatformPricingResult(
            min_price=148000.0,
            max_price=148000.0,
            final_price=141499,
            real_profit=12679,
            status="Tier 1 Safe Win",
            reason="Undercut lowest competitor ExactSeller (Rs. 148,000) to winning price Rs. 141,499.",
        ),
    )

    p_notice = ProductInput(
        sno=2,
        brand="Haier",
        name="Haier 18HFPCA Inverter AC",
        length=0.0,
        width=0.0,
        height=0.0,
        net_price=115000.0,
        profit=500.0,
        raw_row={"Brand": "Haier", "Name": "Haier 18HFPCA Inverter AC", "Net Price": 115000},
    )
    r_notice = build_output_record(
        product=p_notice,
        shipping=2500.0,
        floors=floors,
        baseline_calc=baseline,
        alfa_res=PlatformPricingResult(
            min_price=146000.0,
            max_price=146000.0,
            final_price=141499,
            real_profit=9849,
            status="Competitive Win",
            reason=(
                "ℹ️ [OPTIONAL SPECIFICATION: Target did not specify 'T3', but market listing specifies 'T3'] "
                "Undercut lowest competitor SellerA (Rs. 146,000) to winning price Rs. 141,499."
            ),
            compatibility_notice="ℹ️ [OPTIONAL SPECIFICATION: Target did not specify 'T3', but market listing specifies 'T3']",
        ),
        digi_res=PlatformPricingResult(
            min_price=144000.0,
            max_price=144000.0,
            final_price=141499,
            real_profit=12679,
            status="Tier 1 Safe Win",
            reason=(
                "⚠️ [SIBLING SUB-MODEL FALLBACK: Target specified '18HFPCA', but market listing is sibling edition 'HSU-18HFPE' sharing base '18HFP'] "
                "Undercut lowest competitor SellerB (Rs. 144,000) to winning price Rs. 141,499."
            ),
            compatibility_notice="⚠️ [SIBLING SUB-MODEL FALLBACK: Target specified '18HFPCA', but market listing is sibling edition 'HSU-18HFPE' sharing base '18HFP']",
        ),
    )

    df = pd.DataFrame([r_clean, r_notice])
    manifest = export_results(df, "test_catalog.csv", output_dir=out_dir, render_panel=False)

    csv_df = pd.read_csv(manifest.latest_path)
    assert list(csv_df.columns)[0] == "S.NO"
    assert list(csv_df.columns)[-2:] == ["Alfa Risk Alert", "Digi Risk Alert"]
    assert "Compatibility Notice" not in csv_df.columns
    assert "[OPTIONAL SPECIFICATION:" in str(csv_df.loc[1, "Alfa Reason"])
    assert "[SIBLING SUB-MODEL FALLBACK:" in str(csv_df.loc[1, "Digi Reason"])

    assert manifest.latest_xlsx_path is not None
    wb = openpyxl.load_workbook(manifest.latest_xlsx_path)
    ws = wb.active
    assert ws is not None
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    alfa_reason_col = headers.index("Alfa Reason") + 1
    digi_reason_col = headers.index("Digi Reason") + 1

    # Row 2 in Excel = clean item (no fill)
    clean_cell = ws.cell(row=2, column=alfa_reason_col)
    assert clean_cell.fill.fill_type is None

    # Row 3 in Excel = compatibility/fallback notice item (soft yellow fill FFF9C4)
    alfa_notice_cell = ws.cell(row=3, column=alfa_reason_col)
    digi_notice_cell = ws.cell(row=3, column=digi_reason_col)
    assert alfa_notice_cell.fill.fill_type == "solid"
    assert str(alfa_notice_cell.fill.start_color.rgb or "").endswith("FFF9C4")
    assert digi_notice_cell.fill.fill_type == "solid"
    assert str(digi_notice_cell.fill.start_color.rgb or "").endswith("FFF9C4")


# ==============================================================================
# ADVERSARIAL DOUBT-DRIVEN REGRESSION SUITE (Defects 1 - 6)
# ==============================================================================


def test_adv_01_unprefixed_btu_k_tokens_never_hijack_anchor_while_prefixed_pinv_12k_matches() -> None:
    """Unprefixed 12K/18K/24K BTU tokens must stay spec tokens, while prefixed PINV 12K binds cleanly."""
    # 1. Downstream real SKU after unprefixed 12K / 18K must be extracted as anchor
    s_gree = extract_product_slots("Gree 12K Split AC GS-12PITH11W", brand="Gree")
    assert s_gree.anchor == "GS-12PITH11W"
    assert s_gree.guarded_facets.capacity == "1T"

    dec_haier = referee_match(
        "Haier Inverter AC HSU-18HFP",
        "Haier 18K Inverter AC HSU-18HFP",
        brand="Haier",
    )
    assert dec_haier.is_match is True
    assert dec_haier.match_tier == 1

    # 2. Bare 'Dawlance 18K Inverter AC' without SKU or series must reject for insufficient identity
    dec_bare = referee_match(
        "Dawlance 18K Inverter AC",
        "Dawlance 18K Elegance Inverter AC",
        brand="Dawlance",
    )
    assert dec_bare.is_match is False
    assert dec_bare.match_tier is None

    # 3. Prefixed 'Pel PINV 12K Inverter AC' (REG-25) still extracts PINV-12K and matches Tier 1
    s_pel = extract_product_slots("Pel PINV 12K Inverter AC", brand="Pel")
    assert s_pel.anchor == "PINV-12K"
    assert referee_match("Pel PINV 12K Inverter AC", "Pel PINV-12K 1 Ton DC Inverter AC", brand="Pel").match_tier == 1


def test_adv_02_measurement_unit_binder_preserves_color_w_after_washer_prefix_and_ltrs() -> None:
    """_bind_standalone_measurement_units must never swallow color 'W' on HWM-150 826 W or after 250 LTRS."""
    s_washer = extract_product_slots("Haier HWM-150 826 W Washing Machine", brand="Haier")
    assert s_washer.guarded_facets.color_family == "White"
    dec_washer_blk = referee_match(
        "Haier HWM-150 826 W Washing Machine",
        "Haier HWM-150-826 Black Washing Machine",
        brand="Haier",
    )
    assert dec_washer_blk.is_match is False

    s_fridge = extract_product_slots("Dawlance 250 LTRS 91060 W Refrigerator", brand="Dawlance")
    assert s_fridge.guarded_facets.color_family == "White"
    dec_fridge_blk = referee_match(
        "Dawlance 250 LTRS 91060 W Refrigerator",
        "Dawlance 91060 Black Refrigerator",
        brand="Dawlance",
    )
    assert dec_fridge_blk.is_match is False


def test_adv_03_slash_wb_series_cleanliness_glass_door_reflexivity_and_washer_tub_wb() -> None:
    """Slash /WB must not leak into series, break Glass Door reflexivity, or corrupt washer Wide Body."""
    s_dmb = extract_product_slots("Dawlance DMB-91060/WB Refrigerator", brand="Dawlance")
    assert s_dmb.anchor == "DMB-91060"
    assert s_dmb.series == ""
    assert s_dmb.guarded_facets.color_family == "Brown / Wood"

    # Self-reflexive & prose Wood Brown + Glass Door compatibility
    dec_self_gd = referee_match(
        "Dawlance DMB-91060/WB Glass Door Refrigerator",
        "Dawlance DMB-91060/WB Glass Door Refrigerator",
        brand="Dawlance",
    )
    assert dec_self_gd.is_match is True
    assert dec_self_gd.match_tier == 1

    dec_prose_gd = referee_match(
        "Dawlance DMB-91060/WB Refrigerator",
        "Dawlance DMB-91060 Wood Brown Glass Door Refrigerator",
        brand="Dawlance",
    )
    assert dec_prose_gd.is_match is True

    # Competing slash code /GD without Wood Brown still rejects
    dec_competing_gd = referee_match(
        "Dawlance DMB-91060/WB Refrigerator",
        "Dawlance DMB-91060/GD Refrigerator",
        brand="Dawlance",
    )
    assert dec_competing_gd.is_match is False

    # Washing machine /WB preserves Wide Body tub_series and explicit White color
    s_wm = extract_product_slots("Haier HWM-150-826/WB White Washing Machine", brand="Haier")
    assert s_wm.anchor == "HWM-150-826"
    assert s_wm.guarded_facets.tub_series == "WB"
    assert s_wm.guarded_facets.color_family == "White"
    assert s_wm.series == ""
    assert (
        referee_match(
            "Haier HWM-150-826/WB Washing Machine",
            "Haier HWM-150-826/GB Washing Machine",
            brand="Haier",
        ).is_match
        is False
    )


def test_adv_04_tier_3_sibling_enforces_guarded_facet_invariance_and_tier_2_reports_co_omissions() -> None:
    """Tier 3 sibling rejects missing guarded facets (T3/Inverter); Tier 2 base surfaces co-occurring omissions."""
    # Sibling missing required T3 -> rejected (guarded capabilities invariant on Tier 3)
    dec_sib_no_t3 = referee_match(
        "Haier 18HFPCA T3 1.5 Ton Inverter AC",
        "Haier HSU-18HFPE 1.5 Ton Inverter AC",
        brand="Haier",
    )
    assert dec_sib_no_t3.is_match is False
    assert dec_sib_no_t3.match_tier is None

    # Sibling missing required Inverter -> rejected
    dec_sib_no_inv = referee_match(
        "Haier 18HFPCA 1.5 Ton Inverter AC",
        "Haier HSU-18HFPE 1.5 Ton Split AC",
        brand="Haier",
    )
    assert dec_sib_no_inv.is_match is False
    assert dec_sib_no_inv.match_tier is None

    # Sibling satisfying T3 + Inverter -> Tier 3 match
    dec_sib_ok = referee_match(
        "Haier 18HFPCA T3 1.5 Ton Inverter AC",
        "Haier HSU-18HFPE T3 1.5 Ton Inverter AC",
        brand="Haier",
    )
    assert dec_sib_ok.match_tier == 3

    # Tier 2 parent base model omitting T3 surfaces both base fallback and omitted T3
    dec_t2_co = referee_match(
        "Haier 18HFPCA T3 1.5 Ton Inverter AC",
        "Haier HSU-18HFP 1.5 Ton Inverter AC",
        brand="Haier",
    )
    assert dec_t2_co.match_tier == 2
    assert dec_t2_co.compatibility_notice is not None
    assert "T3" in dec_t2_co.compatibility_notice


def test_adv_05_smart_polarity_contradiction_and_ambiguity_on_tvs_and_wifi_cooccurrence() -> None:
    """Smart vs Non-Smart rejects on TVs (Rule B) and Smart+Non-Smart rejects even alongside WiFi (Rule A)."""
    dec_tv_contra_1 = referee_match(
        "TCL 32 Inch Smart LED TV 32S5400",
        "TCL 32 Inch Non-Smart LED TV 32S5400",
        brand="TCL",
    )
    assert dec_tv_contra_1.is_match is False
    assert dec_tv_contra_1.match_tier is None

    dec_tv_contra_2 = referee_match(
        "TCL 32 Inch Non-Smart LED TV 32S5400",
        "TCL 32 Inch Smart LED TV 32S5400",
        brand="TCL",
    )
    assert dec_tv_contra_2.is_match is False
    assert dec_tv_contra_2.match_tier is None

    dec_tv_ambig = referee_match(
        "TCL 32 Inch Smart LED TV 32S5400",
        "TCL 32 Inch Smart Non-Smart LED TV 32S5400",
        brand="TCL",
    )
    assert dec_tv_ambig.is_match is False
    assert "Ambiguous" in dec_tv_ambig.reason

    dec_wifi_ambig = referee_match(
        "Haier 1.5 Ton WiFi Inverter AC HSU-18HFP",
        "Haier 1.5 Ton WiFi Smart Non-Smart Inverter AC HSU-18HFP",
        brand="Haier",
    )
    assert dec_wifi_ambig.is_match is False
    assert "Ambiguous" in dec_wifi_ambig.reason


def test_adv_06_non_exhaustive_waterfall_continues_past_sold_out_tier_1_to_instock_tier_2() -> None:
    """exhaustive=False must not stop at 2 sold-out Tier 1 offers when Tier 2 query has an in-stock base match."""
    from unittest.mock import AsyncMock

    class _Resp:
        def __init__(self, payload: dict[str, object]) -> None:
            self.status_code = 200
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    async def _fake_get(url: str, params: dict[str, str] | None = None, **kwargs: object) -> _Resp:
        q = (params or {}).get("q", "")
        if "18HFPCA" in q.upper():
            return _Resp(
                {
                    "results": [
                        {
                            "title": "Haier 1.5 Ton Inverter AC HSU-18HFPCA",
                            "sold_out": True,
                            "variant_detail": {"discounted_price": "148,000"},
                            "vendor": {"name": "SoldOutSeller1"},
                        },
                        {
                            "title": "Haier 1.5 Ton Inverter AC HSU-18HFPCA",
                            "sold_out": True,
                            "variant_detail": {"discounted_price": "149,000"},
                            "vendor": {"name": "SoldOutSeller2"},
                        },
                    ],
                    "count": 2,
                }
            )
        return _Resp(
            {
                "results": [
                    {
                        "title": "Haier 1.5 Ton Inverter AC HSU-18HFP",
                        "sold_out": False,
                        "variant_detail": {"discounted_price": "145,000"},
                        "vendor": {"name": "InStockBaseSeller"},
                    }
                ],
                "count": 1,
            }
        )

    session = AsyncMock()
    session.get = AsyncMock(side_effect=_fake_get)

    async def _run() -> None:
        clear_scraper_cache()
        res = await scrape_alfamall(
            session,
            {"tier_1": ["Haier 18HFPCA"], "tier_2": ["Haier 18HFP"]},
            target_model="18HFPCA",
            brand="Haier",
            target_desc="Haier 18HFPCA 1.5 Ton Inverter AC",
            exhaustive=False,
        )
        assert len(res.offers) == 1
        assert res.offers[0].vendor_name == "InStockBaseSeller"
        assert res.offers[0].match_tier == 2
        assert res.compatibility_notice is not None
        assert "base model 'HSU-18HFP'" in res.compatibility_notice

    asyncio.run(_run())

