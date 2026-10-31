"""Forensic Regression Test Suite (TASK-01 through TASK-20 / BUG-01..BUG-20 & NEW-BUG-22..NEW-BUG-26).

Verifies all 20 tasks from the approved Master Implementation Plan across:
- Cross-model base-match contamination prevention (NEW-BUG-22 / TASK-13)
- Glued vs spaced 3-letter Haier variant isolation (NEW-BUG-23 / TASK-04)
- Marketplace pipe delimiter & hyphenated descriptor cleaning (NEW-BUG-24 / TASK-01, TASK-02)
- Dawlance Glass Lid (G), Clear Lid (C), and White Flat Lid (WFL/W) variants (NEW-BUG-25 / TASK-09)
- Exhaustive 3-tier waterfall & diagnostic script compatibility (NEW-BUG-26, BUG-19 / TASK-15)
- Pakistani price-string currency parsing (BUG-17 / TASK-03)
- Glued single-letter E and spaced Haier drum models (BUG-05, BUG-08, BUG-09 / TASK-05, TASK-09)
- Dawlance ADS+ capability extraction & base-vs-upgraded isolation (BUG-01 / TASK-06)
- Washing machine tub & automation classification (BUG-02 / TASK-07)
- Decimal washing-machine capacities 7.5KG, 8.5KG, 9.5KG (BUG-07 / TASK-08)
- Dual-colour slash listing detection & Cross-Check Notice attribution (BUG-06 / TASK-10)
- Single-number compound model guard & washer+spinner bundle guard (BUG-10, BUG-11 / TASK-11, TASK-12)
- Search pattern coverage for Haier HWM and Dawlance glued variants (BUG-12 / TASK-14)
- Winning-offer modifier attribution & sold-out exact fallback (BUG-13, BUG-14, BUG-18 / TASK-16)
- Unknown-vendor deduplication handle preservation (BUG-16 / TASK-17)
- Cached Page-2 sub-floor probing (BUG-15 / TASK-18)
- Partial waterfall outage HTTP 429/5xx safety (BUG-20 / TASK-19)
"""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock

from pricing_engine.evaluator import evaluate_alfa_pricing, format_fallback_descriptions
from pricing_engine.matcher import (
    extract_product_slots,
    generate_search_patterns,
    is_strict_model_match,
    referee_match,
)
from pricing_engine.models import CostFloors, ScrapedOffer
from pricing_engine.scraper import (
    clear_scraper_cache,
    deduplicate_offers,
    parse_price_value,
    scrape_alfamall,
    scrape_digimall,
)


def test_task01_pipe_delimiter_seller_store_with_digits_stripped() -> None:
    """TASK-01 / NEW-BUG-24a: Pipe-delimited store names with digits ('|3AZ Mart') must not pollute capabilities."""
    target = "TCL 40S59K 40 Inch QLED FHD Smart Android TV"
    cand = "TCL 40S59K 40 Inch FHD QLED Google TV |3AZ Mart"
    slots_cand = extract_product_slots(cand, brand="TCL")
    assert "3AZ" not in slots_cand.guarded_facets.capabilities
    assert "MART" not in slots_cand.guarded_facets.capabilities
    dec = referee_match(target, cand, brand="TCL")
    assert dec.is_match is True
    assert dec.is_base_match is False


def test_task01_pipe_delimiter_own_store_signature_stripped() -> None:
    """TASK-01: Pipe-delimited store suffix '| Kia Chahiye Pvt Ltd' is cleanly stripped."""
    slots = extract_product_slots(
        "Haier HWM 130-1217 13KG Top Load Fully Automatic Washing Machine - Grey | Kia Chahiye Pvt Ltd",
        brand="Haier",
    )
    assert slots.anchor == "130-1217"
    assert slots.series == ""
    assert not slots.guarded_facets.capabilities


def test_task02_hyphenated_english_descriptors_do_not_inject_capabilities_or_series() -> None:
    """TASK-02 / NEW-BUG-24b: 'E-Star' and 'Non-Inverter' must not inject 'STAR' cap or 'Non' series."""
    title = "Haier HRF-216 EBD 8 Cu Ft Metallic Grey E-Star Non-Inverter Refrigerator"
    slots = extract_product_slots(title, brand="Haier")
    assert slots.anchor == "HRF-216"
    assert slots.series == ""
    assert slots.guarded_facets.is_inverter is False
    assert "STAR" not in slots.guarded_facets.capabilities
    assert "EBD" in slots.guarded_facets.capabilities


def test_task02_zero_percent_markup_and_processing_fees_cleaned() -> None:
    """TASK-02 / NEW-BUG-24: '0% MARK UP-UE004' and '(0% PROCESSING FEES)' do not pollute slots."""
    s_gree = extract_product_slots(
        "Gree 1.5 Ton Inverter Split AC GS-18PITH11W 0% MARK UP-UE004",
        brand="Gree",
    )
    assert s_gree.anchor == "GS-18PITH11W"
    assert s_gree.series == ""
    assert not s_gree.guarded_facets.capabilities

    s_daw = extract_product_slots(
        "Dawlance DWT 1166 ADS+ 11Kg Top Load Washing Machine - ET (0% PROCESSING FEES)",
        brand="Dawlance",
    )
    assert s_daw.anchor == "DWT-1166"
    assert "ET" not in s_daw.guarded_facets.capabilities
    assert "FEES" not in s_daw.guarded_facets.capabilities


def test_task02_pakistani_cities_and_marketing_words_excluded_from_series() -> None:
    """TASK-02 / BUG-01: Pakistani city names and marketing phrases do not pollute series."""
    s_city = extract_product_slots(
        "Dawlance Top Load Washing Machine DWT 1166 ADS+ Free Home Delivery in Karachi Lahore Islamabad",
        brand="Dawlance",
    )
    assert s_city.series == ""

    s_noise = extract_product_slots(
        "Dawlance DWT 9060 EZ 9KG Top Load Automatic Washing Machine Energy Saving Low Noise Silent",
        brand="Dawlance",
    )
    assert s_noise.series == ""
    assert "EZ" in s_noise.guarded_facets.capabilities


def test_task03_pakistani_price_string_parsing_variants() -> None:
    """TASK-03 / BUG-17: parse_price_value handles Rs., PKR, commas, decimals, and '/-' suffixes."""
    assert parse_price_value("84,999") == 84999.0
    assert parse_price_value("Rs. 84,999") == 84999.0
    assert parse_price_value("Rs 84,999/-") == 84999.0
    assert parse_price_value("PKR 119,999.50") == 119999.5
    assert parse_price_value(95000) == 95000.0
    assert parse_price_value("N/A") == 0.0
    assert parse_price_value("") == 0.0


def test_task04_glued_three_letter_haier_refrigerator_variants_isolated() -> None:
    """TASK-04 / NEW-BUG-23: Glued HRF-216EBS and HRF-216EPR must not match HRF-216 EBD as base models."""
    target = "Haier HRF-216 EBD 8 Cu Ft Metallic Grey E-Star Non-Inverter Refrigerator"
    cand_ebs = "Haier HRF-216EBS 8 Cu Ft E-Star Silver Metal Door Non-Inverter Refrigerator"
    cand_epr = "Haier HRF-216EPR 8 Cu Ft E-Star Red Glass Door Non-Inverter Refrigerator"
    cand_ebd_glued = "Haier HRF-216EBD 8 Cu Ft E-Star Metallic Grey Non-Inverter Refrigerator"

    dec_ebs = referee_match(target, cand_ebs, brand="Haier")
    assert dec_ebs.is_match is False
    assert dec_ebs.is_base_match is False

    dec_epr = referee_match(target, cand_epr, brand="Haier")
    assert dec_epr.is_match is False
    assert dec_epr.is_base_match is False

    dec_ebd = referee_match(target, cand_ebd_glued, brand="Haier")
    assert dec_ebd.is_match is True
    assert dec_ebd.is_base_match is False


def test_task04_haier_hrf_306_ipra_vs_ipg_and_epr_glued_isolation() -> None:
    """TASK-04: Haier HRF-306 IPRA rejects glued HRF-306IPG and HRF-306EPR."""
    target = "Haier HRF-306 IPRA Inverter Refrigerator"
    dec_ipg = referee_match(target, "Haier HRF-306IPG Inverter Refrigerator", brand="Haier")
    assert dec_ipg.is_match is False and dec_ipg.is_base_match is False

    dec_epr = referee_match(target, "Haier HRF-306EPR Refrigerator", brand="Haier")
    assert dec_epr.is_match is False and dec_epr.is_base_match is False

    dec_exact = referee_match(target, "Haier HRF-306IPRA Inverter Refrigerator", brand="Haier")
    assert dec_exact.is_match is True


def test_task05_glued_single_letter_e_and_spaced_haier_drum_models() -> None:
    """TASK-05 / BUG-08, BUG-09: Glued 150-826E matches 150-826 E and falls back cleanly on 150-826."""
    s_glued = extract_product_slots("Haier HWM 150-826E Top Load Washing Machine", brand="Haier")
    s_spaced = extract_product_slots("Haier HWM 150-826 E Top Load Washing Machine", brand="Haier")
    assert s_glued.anchor == "150-826"
    assert s_spaced.anchor == "150-826"

    dec_exact = referee_match(
        "Haier HWM 150-826 E Top Load Washing Machine",
        "Haier HWM 150-826E Top Load Washing Machine",
        brand="Haier",
    )
    assert dec_exact.is_match is True

    dec_base = referee_match(
        "Haier HWM 150-826E Top Load Washing Machine",
        "Haier HWM 150-826 Top Load Washing Machine",
        brand="Haier",
    )
    assert dec_base.is_match is False
    assert dec_base.is_base_match is True
    assert dec_base.missing_modifier == "Variant E"


def test_task05_spaced_alphanumeric_haier_drum_stem_preserved() -> None:
    """TASK-05 / BUG-09: Spaced 'Haier HWM 130 B699S8' preserves 'B699S8' in anchor."""
    slots = extract_product_slots(
        "Haier HWM 130 B699S8 13KG Top Load Washing Machine", brand="Haier"
    )
    assert "B699S8" in slots.anchor
    dec = referee_match(
        "Haier HWM 130-B699S8 13KG Top Load Washing Machine",
        "Haier HWM 130 B699S8 13KG Top Load Washing Machine",
        brand="Haier",
    )
    assert dec.is_match is True


def test_task06_ads_plus_capability_extraction_and_isolation() -> None:
    """TASK-06 / BUG-01d: ADS+ is extracted as capability 'ADS'; base model rejects upgraded ADS+."""
    s_ads = extract_product_slots(
        "Dawlance DWT 1166 ADS+ Top Load Washing Machine", brand="Dawlance"
    )
    assert "ADS" in s_ads.guarded_facets.capabilities
    assert s_ads.series == ""

    dec_upgrade = referee_match(
        "Dawlance DWT 1166 Top Load Washing Machine",
        "Dawlance DWT 1166 ADS+ Top Load Washing Machine",
        brand="Dawlance",
    )
    assert dec_upgrade.is_match is False
    assert dec_upgrade.is_base_match is False

    dec_fallback = referee_match(
        "Dawlance DWT 1166 ADS+ Top Load Washing Machine",
        "Dawlance DWT 1166 Top Load Washing Machine",
        brand="Dawlance",
    )
    assert dec_fallback.is_match is False
    assert dec_fallback.is_base_match is True
    assert dec_fallback.missing_modifier == "ADS"


def test_task06_dwt_270_lvs_plus_soft_compatibility_preserved() -> None:
    """TASK-06 / BUG-03: Un-suffixed DWT-270 continues to match DWT-270 LVS+ without regression."""
    dec = referee_match("Dawlance DWT-270", "Dawlance DWT-270 LVS+", brand="Dawlance")
    assert dec.is_match is True


def test_task07_washing_machine_tub_and_automation_classification() -> None:
    """TASK-07 / BUG-02: Twin Tub with 'Automatic' or 'Washer and Dryer' matches Semi-Auto Twin Tub."""
    dec_auto_twin = referee_match(
        "Dawlance DW 6550 C Automatic Twin Tub Washing Machine",
        "Dawlance DW 6550 C Semi Automatic Twin Tub Washing Machine",
        brand="Dawlance",
    )
    assert dec_auto_twin.is_match is True

    dec_washer_dryer = referee_match(
        "Dawlance DW 9100 C Twin Tub Washing Machine",
        "Dawlance DW 9100 C Washer and Dryer",
        brand="Dawlance",
    )
    assert dec_washer_dryer.is_match is True

    dec_spin_dryer = referee_match(
        "Dawlance DW 9100 C Twin Tub Washing Machine",
        "Dawlance DW 9100 C Twin Tub Washer and Spin Dryer",
        brand="Dawlance",
    )
    assert dec_spin_dryer.is_match is True


def test_task07_single_tub_spinner_only_vs_twin_tub_rejected() -> None:
    """TASK-07: Single Tub Spinner Only collides with Twin Tub Washing Machine."""
    dec = referee_match(
        "Dawlance DW 6550 C Twin Tub Washing Machine",
        "Dawlance DW 6550 C Single Tub Spinner Only",
        brand="Dawlance",
    )
    assert dec.is_match is False
    assert "Tub type collision" in dec.reason


def test_task08_decimal_washing_machine_capacities_preserved() -> None:
    """TASK-08 / BUG-07: Decimal capacities (7.5KG, 8.5KG, 9.5KG) do not truncate to integers."""
    dec_75_vs_70 = referee_match(
        "Dawlance DW 6550 C 7.5 KG Twin Tub Washing Machine",
        "Dawlance DW 6550 C 7 KG Twin Tub Washing Machine",
        brand="Dawlance",
    )
    assert dec_75_vs_70.is_match is False
    assert "7.5KG vs 7KG" in dec_75_vs_70.reason

    dec_95 = referee_match(
        "Haier HWM 95-1678 ES8 9.5 KG Top Load Washing Machine",
        "Haier HWM 95-1678 ES8 Top Load Washing Machine",
        brand="Haier",
    )
    assert dec_95.is_match is True


def test_task08_haier_85_and_105_decimal_anchor_capacities() -> None:
    """TASK-08: Haier 85-xxx -> 8.5KG and 105-xxx -> 10.5KG match explicit decimal KG."""
    s85 = extract_product_slots("Haier HWM 85-1678 Top Load Washing Machine", brand="Haier")
    assert s85.guarded_facets.capacity == "8.5KG"

    s105 = extract_product_slots("Haier HWM 105-BD14376 Front Load Washing Machine", brand="Haier")
    assert s105.guarded_facets.capacity == "10.5KG"


def test_task09_dawlance_glass_lid_clear_lid_and_white_lid_isolation() -> None:
    """TASK-09 / NEW-BUG-25: Dawlance Glass Lid (G), Clear Lid (C), and White Flat Lid (WFL/W) are isolated."""
    dec_g_vs_c = referee_match(
        "Dawlance DW 7500 Glass Lid Single Tub Washer",
        "Dawlance DW-7500 C Single Tub Washing Machine Clear Lid",
        brand="Dawlance",
    )
    assert dec_g_vs_c.is_match is False
    assert dec_g_vs_c.is_base_match is False
    assert "G vs C" in dec_g_vs_c.reason

    dec_c_vs_wfl = referee_match(
        "Dawlance DW 9200 C Clear Lid Twin Tub Washing Machine",
        "Dawlance DW 9200 WFL White Flat Lid Twin Tub Washing Machine",
        brand="Dawlance",
    )
    assert dec_c_vs_wfl.is_match is False
    assert dec_c_vs_wfl.is_base_match is False
    assert "C vs W" in dec_c_vs_wfl.reason

    dec_g_exact = referee_match(
        "Dawlance DW 7500 Glass Lid Single Tub Washer",
        "Dawlance DW-7500 G Single Tub Washing Machine",
        brand="Dawlance",
    )
    assert dec_g_exact.is_match is True


def test_task09_dawlance_cfl_and_wfl_acronyms_mapped_to_c_and_w() -> None:
    """TASK-09: CFL maps to C (Clear Lid) and WFL maps to W (White Lid)."""
    dec_cfl = referee_match(
        "Dawlance DW 6550 C Clear Lid Twin Tub",
        "Dawlance DW 6550 CFL Twin Tub",
        brand="Dawlance",
    )
    assert dec_cfl.is_match is True

    dec_wfl = referee_match(
        "Dawlance DW 9200 White Flat Lid Twin Tub",
        "Dawlance DW 9200 WFL Twin Tub",
        brand="Dawlance",
    )
    assert dec_wfl.is_match is True


def test_task09_haier_alphanumeric_submodel_single_letter_e_suffix() -> None:
    """TASK-09 / BUG-05: Trailing 'E' after alphanumeric sub-stem ('1678S8 E') is extracted."""
    dec_omit = referee_match(
        "Haier HWM 120-1678S8 E Top Load Washing Machine",
        "Haier HWM 120-1678S8 Top Load Washing Machine",
        brand="Haier",
    )
    assert dec_omit.is_match is False
    assert dec_omit.is_base_match is True
    assert dec_omit.missing_modifier == "Variant E"


def test_task10_dual_colour_slash_listing_detection_and_cross_check_notice() -> None:
    """TASK-10 / BUG-06: Single-color target matching 'White / Grey' sets Dual-Color Cross-Check Notice."""
    dec_w = referee_match(
        "Dawlance DW 6550 C White Twin Tub Washing Machine",
        "Dawlance DW 6550 C White / Grey Twin Tub Washing Machine",
        brand="Dawlance",
    )
    assert dec_w.is_match is True
    assert dec_w.missing_modifier == "Dual-Color (White/Grey)"

    dec_g = referee_match(
        "Dawlance DW 6550 C Grey Twin Tub Washing Machine",
        "Dawlance DW 6550 C White / Grey Twin Tub Washing Machine",
        brand="Dawlance",
    )
    assert dec_g.is_match is True
    assert dec_g.missing_modifier == "Dual-Color (White/Grey)"

    audit, reason, _ = format_fallback_descriptions("Dual-Color (White/Grey)")
    assert "DUAL-COLOR" in audit
    assert "CROSS-CHECK NOTICE" in reason


def test_task10_standalone_opposing_colors_still_hard_reject() -> None:
    """TASK-10 / BUG-06: Standalone White vs Silver/Grey without slash still hard-rejects."""
    dec = referee_match(
        "Dawlance DW 6550 C White Twin Tub Washing Machine",
        "Dawlance DW 6550 C Grey Twin Tub Washing Machine",
        brand="Dawlance",
    )
    assert dec.is_match is False
    assert dec.is_base_match is False
    assert "Color collision" in dec.reason


def test_task11_single_number_target_rejects_unrelated_compound_models() -> None:
    """TASK-11 / BUG-10: Single-number stem does not match compound drum model sharing one number."""
    dec1 = referee_match(
        "Dawlance DWT-255 Top Load Washing Machine",
        "Dawlance 120-255 Top Load Washing Machine",
        brand="Dawlance",
    )
    assert dec1.is_match is False
    assert dec1.is_base_match is False

    dec2 = referee_match(
        "Haier HWM 120 Washing Machine",
        "Haier HWM 120-826 Washing Machine",
        brand="Haier",
    )
    assert dec2.is_match is False
    assert dec2.is_base_match is False


def test_task12_washer_and_spinner_combo_bundles_rejected_for_single_unit_target() -> None:
    """TASK-12 / BUG-11: Multi-machine Washer + Spinner combo bundles do not match single washer targets."""
    dec1 = referee_match(
        "Dawlance DW-6550 C Twin Tub Washing Machine",
        "Dawlance DW-6550 C Twin Tub Washing Machine + DSS-6550 Spinner Combo",
        brand="Dawlance",
    )
    assert dec1.is_match is False
    assert "Bundle/Combo collision" in dec1.reason

    dec2 = referee_match(
        "Dawlance DW 6550 C Washing Machine",
        "Dawlance DW 6550 C Washing Machine with WD 6550 Spinner",
        brand="Dawlance",
    )
    assert dec2.is_match is False
    assert "Bundle/Combo collision" in dec2.reason


def test_task12_single_unit_premium_bundle_text_not_falsely_rejected() -> None:
    """TASK-12: Single-unit 'Premium Bundle' without spinner/second SKU is not falsely rejected."""
    dec = referee_match(
        "Haier HWM 120-316S6 Automatic Washing Machine",
        "Haier 120-316S6 Premium Bundle",
        brand="Haier",
    )
    assert dec.is_match is True


def test_task13_inverter_omission_never_bypasses_anchor_model_check() -> None:
    """TASK-13 / NEW-BUG-22a: Haier 130-B699S8 Inverter must NEVER base-match 130-1217 non-inverter."""
    dec = referee_match(
        "Haier HWM 130-B699S8 13KG Double Drive Inverter Automatic Top Load Washing Machine",
        "Haier HWM 130-1217 13KG Top Load Fully Automatic Washing Machine - Grey | Kia Chahiye Pvt Ltd",
        brand="Haier",
    )
    assert dec.is_match is False
    assert dec.is_base_match is False
    assert "Anchor model mismatch" in dec.reason


def test_task13_haier_100_316hs8_inverter_never_base_matches_80_1217() -> None:
    """TASK-13 / NEW-BUG-22: Haier 100-316HS8 10KG Inverter must NEVER base-match 80-1217 or 130-1217."""
    dec = referee_match(
        "Haier HWM 100-316HS8 10KG Inverter Top Load Washing Machine",
        "Haier HWM 80-1217 8KG Top Load Automatic Washing Machine | Kia Chahiye Pvt Ltd",
        brand="Haier",
    )
    assert dec.is_match is False
    assert dec.is_base_match is False
    assert "Anchor model mismatch" in dec.reason


def test_task13_door_finish_omission_never_bypasses_anchor_model_check() -> None:
    """TASK-13 / NEW-BUG-22b: Dawlance 9178LF Avante+ GD must NEVER base-match 9122LF White."""
    dec = referee_match(
        "Dawlance Refrigerator 9178LF Avante+ GD Inverter",
        "Dawlance Refrigerator 9122LF White Inverter",
        brand="Dawlance",
    )
    assert dec.is_match is False
    assert dec.is_base_match is False
    assert "Anchor model mismatch" in dec.reason


def test_task13_omitted_modifier_still_validates_capacity_and_color_guards() -> None:
    """TASK-13: Omitted GD or Inverter must still fail if candidate has conflicting capacity or color."""
    dec_color = referee_match(
        "Dawlance 9178LF GD White Refrigerator",
        "Dawlance 9178LF Black Refrigerator",
        brand="Dawlance",
    )
    assert dec_color.is_match is False
    assert dec_color.is_base_match is False
    assert "Color collision" in dec_color.reason

    dec_cap = referee_match(
        "Haier HWM 120-826S6 12KG Inverter Washing Machine",
        "Haier HWM 120-826S6 10KG Washing Machine",
        brand="Haier",
    )
    assert dec_cap.is_match is False
    assert dec_cap.is_base_match is False
    assert "Capacity" in dec_cap.reason


def test_task13_multi_modifier_base_fallback_combines_variant_and_capability() -> None:
    """TASK-13 / BUG-04: When both Variant S and capability EZ are omitted on same anchor, both are reported."""
    dec = referee_match(
        "Dawlance DWT 260 S EZ Top Load Washing Machine",
        "Dawlance DWT 260 Top Load Washing Machine",
        brand="Dawlance",
    )
    assert dec.is_match is False
    assert dec.is_base_match is True
    assert dec.missing_modifier == "Variant S, EZ"


def test_task13_5digit_dawlance_freezer_gd_omission_remains_direct_match() -> None:
    """TASK-13: 5-digit Dawlance deep freezer (91998) with omitted GD remains a direct match."""
    dec = referee_match(
        "Dawlance 91998 GD Deep Freezer",
        "Dawlance 91998 Deep Freezer",
        brand="Dawlance",
    )
    assert dec.is_match is True
    assert dec.is_base_match is False


def test_task13_5digit_dawlance_freezer_gd_omission_still_checks_anchor() -> None:
    """TASK-13: 5-digit Dawlance deep freezer (91998 GD) rejects wrong 5-digit anchor (91995)."""
    dec = referee_match(
        "Dawlance 91998 GD Deep Freezer",
        "Dawlance 91995 Deep Freezer",
        brand="Dawlance",
    )
    assert dec.is_match is False
    assert dec.is_base_match is False


def test_task14_search_patterns_include_glued_variants_and_haier_hwm_prefix() -> None:
    """TASK-14 / BUG-12: generate_search_patterns includes DWT260C and HWM 150-826."""
    p_daw = generate_search_patterns(
        "Dawlance DWT 260 C LVS+ Top Load Washing Machine", brand="Dawlance"
    )
    assert "DWT260C" in p_daw["tier_2"]

    p_haier = generate_search_patterns(
        "Haier HWM 150-826 E Top Load Washing Machine", brand="Haier"
    )
    combined_t1_t2 = p_haier["tier_1"] + p_haier["tier_2"]
    assert "HWM 150-826" in combined_t1_t2
    assert "HWM-150-826" in combined_t1_t2


def test_task15_exhaustive_parameter_supported_on_scrape_functions() -> None:
    """TASK-15 / NEW-BUG-26, BUG-19: scrape_alfamall and scrape_digimall accept exhaustive=True/False."""
    assert "exhaustive" in inspect.signature(scrape_alfamall).parameters
    assert "exhaustive" in inspect.signature(scrape_digimall).parameters

    async def _run() -> None:
        clear_scraper_cache()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 GC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "95,000"},
                    "vendor": {"name": "Seller 1"},
                },
                {
                    "title": "HAIER 120-826S6 GC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "96,000"},
                    "vendor": {"name": "Seller 2"},
                },
            ]
        }
        sess = AsyncMock()
        sess.get.return_value = resp
        patterns = {"tier_1": ["120-826S6 GC"], "tier_2": ["120-826S6"], "tier_3": ["120 826S6"]}

        res_fast = await scrape_alfamall(sess, patterns, "120-826S6 GC", exhaustive=False)
        assert len(res_fast.offers) == 2
        assert sess.get.call_count == 1

    asyncio.run(_run())


def test_task16_winning_offer_modifier_selected_over_expensive_first_offer() -> None:
    """TASK-16 / BUG-13: active_modifier_fallback reflects the lowest-priced in-stock base offer."""

    async def _run() -> None:
        clear_scraper_cache()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "results": [
                {
                    "title": "Dawlance DWT 260 Top Load Washing Machine",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "98,000"},
                    "vendor": {"name": "ExpensiveSeller"},
                },
                {
                    "title": "Dawlance DWT 260 S Top Load Washing Machine",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "79,000"},
                    "vendor": {"name": "CheapestBaseSeller"},
                },
            ]
        }
        sess = AsyncMock()
        sess.get.return_value = resp
        res = await scrape_alfamall(
            sess,
            {"tier_1": ["DWT-260-S-EZ"], "tier_2": [], "tier_3": []},
            "DWT-260-S",
            brand="Dawlance",
            target_desc="Dawlance DWT 260 S EZ Top Load Washing Machine",
        )
        assert res.active_modifier_fallback == "EZ"

    asyncio.run(_run())


def test_task16_sold_out_exact_offer_falls_back_to_instock_base_offers() -> None:
    """TASK-16 / BUG-14: When all exact offers are sold out, waterfall falls back to in-stock base offers."""

    async def _run() -> None:
        clear_scraper_cache()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "results": [
                {
                    "title": "Gree GS-18AITH24S-T3 Inverter AC",
                    "sold_out": True,
                    "variant_detail": {"discounted_price": "155,000"},
                    "vendor": {"name": "SoldOutT3Seller"},
                },
                {
                    "title": "Gree GS-18AITH24S Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "160,000"},
                    "vendor": {"name": "InStockBaseSeller"},
                },
            ]
        }
        sess = AsyncMock()
        sess.get.return_value = resp
        res = await scrape_alfamall(
            sess,
            {"tier_1": ["18AITH24S-T3"], "tier_2": [], "tier_3": []},
            "18AITH24S-T3",
            brand="Gree",
            target_desc="Gree GS-18AITH24S-T3 Inverter AC",
        )
        assert len(res.offers) == 1
        assert res.offers[0].vendor_name == "InStockBaseSeller"
        assert res.active_modifier_fallback == "T3"

        floors = CostFloors(
            cost_base=120000.0,
            zero_margin_10=133333.0,
            zero_margin_8=130435.0,
            floor_alfa=133889.0,
            floor_digi_10=133889.0,
            floor_digi_8=130978.0,
        )
        eval_res = evaluate_alfa_pricing(floors, res)
        assert eval_res.status == "Competitive Win"
        assert "[FALLBACK MODEL: Target specified 'T3'" in eval_res.reason

    asyncio.run(_run())


def test_task16_own_store_offers_preserve_missing_modifier_metadata() -> None:
    """TASK-16 / BUG-18: Own-store offers matched via base fallback retain missing_modifier."""

    async def _run() -> None:
        clear_scraper_cache()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "results": [
                {
                    "title": "Dawlance DWT 1166 Top Load Washing Machine",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "82,000"},
                    "vendor": {"name": "Kia Chahiye Pvt Ltd"},
                }
            ]
        }
        sess = AsyncMock()
        sess.get.return_value = resp
        res = await scrape_alfamall(
            sess,
            "DWT-1166",
            "DWT-1166",
            brand="Dawlance",
            target_desc="Dawlance DWT 1166 ADS+ Top Load Washing Machine",
        )
        assert len(res.own_offers) == 1
        assert res.own_offers[0].missing_modifier == "ADS"

    asyncio.run(_run())


def test_task17_unknown_vendor_offers_with_distinct_handles_not_collapsed() -> None:
    """TASK-17 / BUG-16: Missing vendor names do not collapse distinct product listings at same price."""
    offers = [
        ScrapedOffer(
            vendor_name="Unknown Vendor",
            price=64000.0,
            is_sold_out=False,
            raw_title="Dawlance DWT 260 C Listing 1",
            product_handle="dwt-260-c-seller-1",
        ),
        ScrapedOffer(
            vendor_name="Unknown Vendor",
            price=64000.0,
            is_sold_out=False,
            raw_title="Dawlance DWT 260 C Listing 2",
            product_handle="dwt-260-c-seller-2",
        ),
    ]
    deduped = deduplicate_offers(offers)
    assert len(deduped) == 2


def test_task17_vendor_handle_used_when_vendor_name_missing() -> None:
    """TASK-17 / BUG-16: When vendor.name is absent, vendor.handle is used as vendor_name."""

    async def _run() -> None:
        clear_scraper_cache()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "results": [
                {
                    "title": "Haier HWM 120-826S6 Top Load",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "91,000"},
                    "vendor": {"handle": "lahore-appliances"},
                }
            ]
        }
        sess = AsyncMock()
        sess.get.return_value = resp
        res = await scrape_alfamall(sess, "120-826S6", "120-826S6", brand="Haier")
        assert len(res.offers) == 1
        assert res.offers[0].vendor_name == "lahore-appliances"

    asyncio.run(_run())


def test_task18_cached_page1_raw_items_triggers_page2_probe_when_floor_requires() -> None:
    """TASK-18 / BUG-15: Cached Page-1 raw items do not suppress Page-2 probing for higher floor_price."""

    async def _run() -> None:
        clear_scraper_cache()
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "count": 40,
            "results": [
                {
                    "title": "Haier HWM 120-826S6 Top Load Washing Machine",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "72,000"},
                    "vendor": {"name": "SubFloorSeller"},
                }
            ],
        }
        resp_p2 = MagicMock()
        resp_p2.status_code = 200
        resp_p2.json.return_value = {
            "count": 40,
            "results": [
                {
                    "title": "Haier HWM 120-826S6 Top Load Washing Machine",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "94,000"},
                    "vendor": {"name": "Page2ViableSeller"},
                }
            ],
        }
        sess = AsyncMock()
        sess.get.side_effect = [resp_p1, resp_p2]

        r1 = await scrape_alfamall(
            sess,
            "120-826S6",
            "120-826S6",
            floor_price=None,
            brand="Haier",
            target_desc="Haier 120-826S6",
        )
        assert len(r1.offers) == 1
        assert sess.get.call_count == 1

        r2 = await scrape_alfamall(
            sess,
            "120-826S6",
            "120-826S6",
            floor_price=80000.0,
            brand="Haier",
            target_desc="Haier 120-826S6 GC",
        )
        assert len(r2.offers) == 2
        assert sess.get.call_count == 2

    asyncio.run(_run())


def test_task19_partial_waterfall_outage_does_not_trigger_false_monopoly() -> None:
    """TASK-19 / BUG-20: Empty Tier 1 (200 OK) + Failed Tier 2 (HTTP 429/503) returns is_success=False."""

    async def _run() -> None:
        clear_scraper_cache()
        resp_t1_empty = MagicMock()
        resp_t1_empty.status_code = 200
        resp_t1_empty.json.return_value = {"results": []}

        resp_t2_429 = MagicMock()
        resp_t2_429.status_code = 429

        sess = AsyncMock()
        sess.get.side_effect = [resp_t1_empty, resp_t2_429]

        res = await scrape_digimall(
            sess,
            {"tier_1": ["DWT-260-C"], "tier_2": ["DWT 260 C"], "tier_3": []},
            "DWT-260-C",
            max_retries=1,
            brand="Dawlance",
        )
        assert res.is_success is False
        assert res.status_code == 429

        floors = CostFloors(
            cost_base=50000.0,
            zero_margin_10=55556.0,
            zero_margin_8=54348.0,
            floor_alfa=56111.0,
            floor_digi_10=56111.0,
            floor_digi_8=54891.0,
        )
        eval_res = evaluate_alfa_pricing(floors, res)
        assert eval_res.final_price is None
        assert "unreachable" in eval_res.reason.lower()

    asyncio.run(_run())


def test_task19_partial_waterfall_failure_succeeds_if_valid_offers_found() -> None:
    """TASK-19: If Tier 1 finds valid offers and Tier 2 fails with 503, result is still is_success=True."""

    async def _run() -> None:
        clear_scraper_cache()
        resp_t1_ok = MagicMock()
        resp_t1_ok.status_code = 200
        resp_t1_ok.json.return_value = {
            "results": [
                {
                    "title": "Haier HWM 120-826S6 Top Load",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "92,000"},
                    "vendor": {"name": "ActiveSeller"},
                }
            ]
        }
        resp_t2_503 = MagicMock()
        resp_t2_503.status_code = 503

        sess = AsyncMock()
        sess.get.side_effect = [resp_t1_ok, resp_t2_503]
        res = await scrape_alfamall(
            sess,
            {"tier_1": ["120-826S6"], "tier_2": ["120 826S6"], "tier_3": []},
            "120-826S6",
            max_retries=1,
            brand="Haier",
        )
        assert res.is_success is True
        assert len(res.offers) == 1

    asyncio.run(_run())


def test_task20_legacy_is_strict_model_match_contract_preserved() -> None:
    """TASK-20 / BUG-21: Legacy is_strict_model_match remains callable and accurate for backward compatibility."""
    assert is_strict_model_match("Haier HWM 120-826S6 Top Load", "120-826S6", brand="Haier") is True
    assert (
        is_strict_model_match("Haier HWM 100-826S6 Top Load", "120-826S6", brand="Haier") is False
    )
