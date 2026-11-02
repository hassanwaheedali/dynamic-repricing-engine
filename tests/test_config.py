"""Tests for central configuration module (config.py) and dynamic setting overrides."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

import config
from pricing_engine.calculator import (
    calculate_floors,
    calculate_personal_commission,
    calculate_shipping_estimate,
    calculate_volumetric_weight,
)
from pricing_engine.models import ScrapedOffer
from pricing_engine.pipeline import parse_product_input, process_product_with_offers


def test_config_default_constants_and_payout_helpers() -> None:
    assert isinstance(config.ALFA_COMMISSION_PCT, (int, float)) and config.ALFA_COMMISSION_PCT > 0
    assert isinstance(config.DIGI_STANDARD_COMMISSION_PCT, (int, float)) and config.DIGI_STANDARD_COMMISSION_PCT > 0
    assert isinstance(config.DIGI_LEVERAGE_COMMISSION_PCT, (int, float)) and config.DIGI_LEVERAGE_COMMISSION_PCT > 0
    assert isinstance(config.DEFAULT_PERSONAL_COMM_PCT, (int, float)) and config.DEFAULT_PERSONAL_COMM_PCT >= 0
    assert isinstance(config.ALFA_PERSONAL_COMM_PCT, (int, float)) and config.ALFA_PERSONAL_COMM_PCT >= 0
    assert isinstance(config.DIGI_PERSONAL_COMM_PCT, (int, float)) and config.DIGI_PERSONAL_COMM_PCT >= 0
    assert isinstance(config.COMPANY_MIN_PROFIT_PKR, (int, float)) and config.COMPANY_MIN_PROFIT_PKR > 0
    assert isinstance(config.MONOPOLY_PROFIT_PKR, (int, float)) and config.MONOPOLY_PROFIT_PKR > 0
    assert isinstance(config.FALLBACK_PROFIT_PKR, (int, float)) and config.FALLBACK_PROFIT_PKR > 0
    assert isinstance(config.LARGE_GAP_PROFIT_CAP_PKR, (int, float)) and config.LARGE_GAP_PROFIT_CAP_PKR > 0
    assert isinstance(config.THIN_BUFFER_THRESHOLD_PKR, (int, float)) and config.THIN_BUFFER_THRESHOLD_PKR > 0
    assert isinstance(config.COURIER_RATE_PER_KG, (int, float)) and config.COURIER_RATE_PER_KG > 0
    assert isinstance(config.VOLUMETRIC_DIVISOR, (int, float)) and config.VOLUMETRIC_DIVISOR > 0

    assert round(config.get_alfa_payout_rate(), 4) == round(1.0 - config.ALFA_COMMISSION_PCT / 100.0, 4)
    assert round(config.get_digi_standard_payout_rate(), 4) == round(1.0 - config.DIGI_STANDARD_COMMISSION_PCT / 100.0, 4)
    assert round(config.get_digi_leverage_payout_rate(), 4) == round(1.0 - config.DIGI_LEVERAGE_COMMISSION_PCT / 100.0, 4)


def test_calculator_respects_config_overrides() -> None:
    with (
        patch.object(config, "COURIER_RATE_PER_KG", 80.0),
        patch.object(config, "COMPANY_MIN_PROFIT_PKR", 1000.0),
        patch.object(config, "ALFA_COMMISSION_PCT", 12.0),
        patch.object(config, "DIGI_LEVERAGE_COMMISSION_PCT", 7.0),
    ):
        vol = calculate_volumetric_weight(100, 50, 50)
        assert vol == 50.0
        # Uses patched config.COURIER_RATE_PER_KG (80.0) when rate_per_kg is omitted
        assert calculate_shipping_estimate(vol) == 4000.0

        # Uses patched COMPANY_MIN_PROFIT_PKR (1000), ALFA_COMMISSION_PCT (12% -> 0.88),
        # and DIGI_LEVERAGE_COMMISSION_PCT (7% -> 0.93)
        floors = calculate_floors(cost_base=100000.0)
        assert round(floors.floor_alfa, 2) == round(101000.0 / 0.88, 2)
        assert round(floors.floor_digi_8, 2) == round(101000.0 / 0.93, 2)


def test_per_platform_personal_commission_from_config() -> None:
    # Suppose user sets Alfa personal commission to 6% and Digi personal commission to 4% in config.py
    with (
        patch.object(config, "ALFA_PERSONAL_COMM_PCT", 6.0),
        patch.object(config, "DIGI_PERSONAL_COMM_PCT", 4.0),
    ):
        floors = calculate_floors(
            cost_base=102000.0,
            net_price=100000.0,
            personal_comm_pct=config.DEFAULT_PERSONAL_COMM_PCT,
        )
        expected_alfa_c = round((config.COMPANY_MIN_PROFIT_PKR / 0.94) - config.COMPANY_MIN_PROFIT_PKR)
        expected_digi_c = round((config.COMPANY_MIN_PROFIT_PKR / 0.96) - config.COMPANY_MIN_PROFIT_PKR)
        assert floors.alfa_personal_comm == expected_alfa_c
        assert floors.digi_personal_comm == expected_digi_c
        assert round(floors.floor_alfa) == round((102000.0 + (config.COMPANY_MIN_PROFIT_PKR / 0.94)) / config.get_alfa_payout_rate())
        assert round(floors.floor_digi_8) == round((102000.0 + (config.COMPANY_MIN_PROFIT_PKR / 0.96)) / config.get_digi_leverage_payout_rate())

        product = parse_product_input(
            0,
            pd.Series(
                {
                    "S.NO": 1,
                    "Brand": "Gree",
                    "Name": "Gree 1.5 Ton GS-18AITH21W",
                    "Shipping Estimate": 2000,
                    "Net Price": 100000,
                }
            ),
        )
        offers = [ScrapedOffer("Comp1", 130000.0, False, "Gree GS-18AITH21W")]
        rec = process_product_with_offers(
            product, offers, offers, personal_comm_pct=config.DEFAULT_PERSONAL_COMM_PCT
        )
        # Verify company profit deducts personal commission from real profit
        alfa_c = calculate_personal_commission(
            rec["Alfa Real Profit"], config.DEFAULT_PERSONAL_COMM_PCT
        )
        digi_c = calculate_personal_commission(
            rec["Digi Real Profit"], config.DEFAULT_PERSONAL_COMM_PCT
        )
        assert rec["Alfa Company Profit"] == rec["Alfa Real Profit"] - alfa_c
        assert rec["Digi Company Profit"] == rec["Digi Real Profit"] - digi_c
        assert calculate_personal_commission(1000.0) == 50
        assert calculate_personal_commission(4000.0) == 200
