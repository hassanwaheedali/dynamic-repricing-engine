"""Tests for central configuration module (config.py) and dynamic setting overrides."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

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
    assert isinstance(config.ALFA_COMMISSION_PCT, (int, float)) and 0 <= config.ALFA_COMMISSION_PCT < 100
    assert isinstance(config.DIGI_COMMISSION_PCT, (int, float)) and 0 <= config.DIGI_COMMISSION_PCT < 100
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

    assert not hasattr(config, "DIGI_STANDARD_COMMISSION_PCT")
    assert not hasattr(config, "DIGI_LEVERAGE_COMMISSION_PCT")
    assert not hasattr(config, "get_digi_standard_payout_rate")
    assert not hasattr(config, "get_digi_leverage_payout_rate")

    assert config.get_alfa_commission_pct() == float(config.ALFA_COMMISSION_PCT)
    assert config.get_digi_commission_pct() == float(config.DIGI_COMMISSION_PCT)
    assert config.get_vendor_commission_pct("ALFA") == float(config.ALFA_COMMISSION_PCT)
    assert config.get_vendor_commission_pct(" digi ") == float(config.DIGI_COMMISSION_PCT)
    assert round(config.get_alfa_payout_rate(), 6) == round(
        1.0 - config.ALFA_COMMISSION_PCT / 100.0, 6
    )
    assert round(config.get_digi_payout_rate(), 6) == round(
        1.0 - config.DIGI_COMMISSION_PCT / 100.0, 6
    )


@pytest.mark.parametrize(
    "bad_val",
    [None, True, False, "8%", "bad", float("nan"), float("inf"), float("-inf"), -0.1, 100.0, 105.0],
)
def test_invalid_commission_config_fails_fast(bad_val: object) -> None:
    with patch.object(config, "DIGI_COMMISSION_PCT", bad_val):
        with pytest.raises(ValueError):
            config.get_digi_commission_pct()
        with pytest.raises(ValueError):
            config.get_digi_payout_rate()
        with pytest.raises(ValueError):
            calculate_floors(cost_base=100000.0)
    with patch.object(config, "ALFA_COMMISSION_PCT", bad_val):
        with pytest.raises(ValueError):
            config.get_alfa_commission_pct()
        with pytest.raises(ValueError):
            config.get_alfa_payout_rate()


def test_missing_commission_config_attr_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(config, "DIGI_COMMISSION_PCT")
    with pytest.raises(ValueError, match="missing"):
        config.get_digi_commission_pct()
    with pytest.raises(ValueError, match="Unsupported platform"):
        config.get_vendor_commission_pct("other")


def test_calculator_respects_config_overrides() -> None:
    with (
        patch.object(config, "COURIER_RATE_PER_KG", 80.0),
        patch.object(config, "COMPANY_MIN_PROFIT_PKR", 1000.0),
        patch.object(config, "ALFA_COMMISSION_PCT", 12.0),
        patch.object(config, "DIGI_COMMISSION_PCT", 7.5),
    ):
        vol = calculate_volumetric_weight(100, 50, 50)
        assert vol == 50.0
        # Uses patched config.COURIER_RATE_PER_KG (80.0) when rate_per_kg is omitted
        assert calculate_shipping_estimate(vol) == 4000.0

        # Uses patched COMPANY_MIN_PROFIT_PKR (1000), ALFA_COMMISSION_PCT (12% -> 0.88),
        # and DIGI_COMMISSION_PCT (7.5% -> 0.925)
        floors = calculate_floors(cost_base=100000.0)
        assert round(floors.floor_alfa, 2) == round(101000.0 / 0.88, 2)
        assert round(floors.floor_digi, 2) == round(101000.0 / 0.925, 2)
        assert round(floors.zero_margin_alfa, 2) == round(100000.0 / 0.88, 2)
        assert round(floors.zero_margin_digi, 2) == round(100000.0 / 0.925, 2)


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
        assert round(floors.floor_digi) == round((102000.0 + (config.COMPANY_MIN_PROFIT_PKR / 0.96)) / config.get_digi_payout_rate())

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
        assert calculate_personal_commission(1000.0) == round(
            1000.0 * (config.DEFAULT_PERSONAL_COMM_PCT / 100.0)
        )
        assert calculate_personal_commission(4000.0) == round(
            4000.0 * (config.DEFAULT_PERSONAL_COMM_PCT / 100.0)
        )
