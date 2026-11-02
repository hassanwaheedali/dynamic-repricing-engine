"""Adversarial and boundary stress tests for generic category shipping fallback logic."""

from __future__ import annotations

import time
from typing import Any

import config
from pricing_engine.calculator import (
    _extract_numeric_capacity,
    calculate_cost_base,
    calculate_floors,
    calculate_shipping_estimate,
    calculate_volumetric_weight,
    resolve_fallback_shipping,
)
from pricing_engine.models import CostFloors, ProductInput
from pricing_engine.pipeline import resolve_shipping_estimate
from tests.conftest import (
    get_configured_category_default,
    get_configured_global_shipping_default,
    get_configured_washer_rate,
)


class TestAdversarialInputsAndEdgeCases:
    """Stress test the generic category shipping resolution against malformed or extreme inputs."""

    def test_empty_string_and_null_inputs(self) -> None:
        rate, label = resolve_fallback_shipping("", brand="")
        assert rate == get_configured_global_shipping_default()
        assert label == "General Appliance"

        rate, label = resolve_fallback_shipping("   ", brand="   ")
        assert rate == get_configured_global_shipping_default()
        assert label == "General Appliance"

    def test_empty_and_corrupted_config_tables(self) -> None:
        # Empty dict
        rate, label = resolve_fallback_shipping(
            "Haier Twin Tub 10 KG", brand="Haier", config_table={}
        )
        assert rate == get_configured_global_shipping_default()
        assert label == "General Appliance"

        # Missing categories key
        rate, label = resolve_fallback_shipping(
            "Haier Twin Tub 10 KG", brand="Haier", config_table={"default": 2800.0}
        )
        assert rate == 2800.0
        assert label == "General Appliance"

        # Corrupted category entries (missing keywords, missing sub_types, missing brackets)
        corrupted_config: dict[str, Any] = {
            "categories": [
                {"id": "broken_1"},
                {"id": "broken_2", "keywords": ["washer"]},
                {
                    "id": "broken_3",
                    "keywords": ["ac"],
                    "sub_types": [
                        {"name": "broken_sub"},
                        {"name": "broken_sub_brackets", "brackets": [{"invalid": True}]},
                    ],
                },
            ],
            "default": 3200.0,
        }
        rate, label = resolve_fallback_shipping(
            "Haier washer", brand="Haier", config_table=corrupted_config
        )
        assert rate == 3500.0  # Category default fallback
        assert label == "broken_2"

        rate, label = resolve_fallback_shipping(
            "Gree ac", brand="Gree", config_table=corrupted_config
        )
        assert rate == 3500.0  # Category default fallback
        assert label == "broken_3"

    def test_extreme_and_boundary_capacities(self) -> None:
        # Micro washer (3.5kg) -> hits lowest bracket <= 8.5kg
        rate, label = resolve_fallback_shipping("Haier Single Tub Washer 3.5 KG", brand="Haier")
        assert rate == get_configured_washer_rate("Single Tub", 3.5)
        assert "3.5kg" in label

        # Giant industrial washer (25kg) -> hits highest bracket <= 999kg
        rate, label = resolve_fallback_shipping(
            "Haier Automatic Washer 25 KG Industrial", brand="Haier"
        )
        assert rate == get_configured_washer_rate("Automatic", 25.0)
        assert "25kg" in label

        # Boundary exact values: 8.5kg
        rate, label = resolve_fallback_shipping("Dawlance Twin Tub 8.5kg", brand="Dawlance")
        assert rate == get_configured_washer_rate("Twin Tub", 8.5)

        # Boundary exact values: 10.0kg
        rate, label = resolve_fallback_shipping("Dawlance Twin Tub 10kg", brand="Dawlance")
        assert rate == get_configured_washer_rate("Twin Tub", 10.0)

        # Boundary exact values: 11.0kg
        rate, label = resolve_fallback_shipping("Dawlance Twin Tub 11kg", brand="Dawlance")
        assert rate == get_configured_washer_rate("Twin Tub", 11.0)

        # Boundary exact values: 12.0kg
        rate, label = resolve_fallback_shipping("Dawlance Twin Tub 12kg", brand="Dawlance")
        assert rate == get_configured_washer_rate("Twin Tub", 12.0)

        # Boundary exact values: 15.0kg
        rate, label = resolve_fallback_shipping("Dawlance Twin Tub 15kg", brand="Dawlance")
        assert rate == get_configured_washer_rate("Twin Tub", 15.0)

    def test_titles_with_no_capacity_numbers(self) -> None:
        cat_default = get_configured_category_default("washing_machine")
        # Washing machine with zero numbers in title
        rate, label = resolve_fallback_shipping(
            "Haier Fully Automatic Top Load Washing Machine Grey", brand="Haier"
        )
        # Should gracefully fallback to category default
        assert rate == cat_default
        assert label == "Automatic Washer"

        # Twin tub with zero numbers
        rate, label = resolve_fallback_shipping(
            "Super Asia Semi Automatic Twin Tub Washer", brand="Super Asia"
        )
        assert rate == cat_default
        assert label == "Twin Tub Washer"

    def test_model_stem_capacity_extraction_extremes(self) -> None:
        # Out of bounds model numbers (should NOT be treated as kg)
        # E.g. HWM-3500 (3500 is not a 50-250 stem)
        cap = _extract_numeric_capacity("Haier HWM-3500", unit="kg")
        assert cap is None

        # Number less than 50 (e.g. 25-model)
        cap = _extract_numeric_capacity("Haier 25-100", unit="kg")
        assert cap is None

        # Valid stem 120 -> 12.0kg
        cap = _extract_numeric_capacity("Haier HWM-120-1678", unit="kg")
        assert cap == 12.0

        # Valid stem 80 -> 8.0kg
        cap = _extract_numeric_capacity("Haier 80-826", unit="kg")
        assert cap == 8.0

        # Valid stem 105 -> 10.5kg
        cap = _extract_numeric_capacity("Haier HW 105", unit="kg")
        assert cap == 10.5

    def test_injection_strings_and_special_characters(self) -> None:
        # SQL injection strings in title
        expected_washer_10 = get_configured_washer_rate("Automatic", 10.0)
        injection_title = "Haier Washer 10kg'; DROP TABLE repricing_runs; --"
        rate, label = resolve_fallback_shipping(injection_title, brand="Haier")
        assert rate == expected_washer_10
        assert "10kg" in label

        # Regex metacharacters in title
        regex_title = "Haier Washer [10kg] (Special) + Edition * Premium? {Deluxe}"
        rate, label = resolve_fallback_shipping(regex_title, brand="Haier")
        assert rate == expected_washer_10
        assert "10kg" in label

    def test_negative_and_zero_dimension_combinations(self) -> None:
        expected_washer_10 = get_configured_washer_rate("Automatic", 10.0)
        # Negative length
        p1 = ProductInput(1, "Haier", "Haier Automatic 10kg", -60.0, 60.0, 85.0, 50000, 500, {})
        ship1, fb1 = resolve_shipping_estimate(p1)
        assert ship1 == expected_washer_10
        assert fb1 is True

        # One dimension is zero
        p2 = ProductInput(2, "Haier", "Haier Automatic 10kg", 60.0, 0.0, 85.0, 50000, 500, {})
        ship2, fb2 = resolve_shipping_estimate(p2)
        assert ship2 == expected_washer_10
        assert fb2 is True

        # All dimensions positive
        p3 = ProductInput(3, "Haier", "Haier Automatic 10kg", 60.0, 60.0, 85.0, 50000, 500, {})
        expected_vol = calculate_volumetric_weight(60.0, 60.0, 85.0)
        expected_shipping = calculate_shipping_estimate(expected_vol)
        ship3, fb3 = resolve_shipping_estimate(p3)
        assert ship3 == expected_shipping
        assert fb3 is False


class TestCostMathIntegrityWithShippingFallback:
    """Verify that shipping fallback integrates 100% correctly with cost base and profit floors."""

    def test_floors_mathematical_precision(self) -> None:
        net_price = 50000.0
        shipping = get_configured_washer_rate("Automatic", 10.0)
        cost_base = calculate_cost_base(net_price, shipping)
        assert cost_base == net_price + shipping

        floors = calculate_floors(cost_base, min_profit=config.COMPANY_MIN_PROFIT_PKR, net_price=net_price)
        assert isinstance(floors, CostFloors)

        # Floor Alfa: (cost_base + min_profit) / alfa_payout
        expected_floor_alfa = (cost_base + config.COMPANY_MIN_PROFIT_PKR) / config.get_alfa_payout_rate()
        assert round(floors.floor_alfa, 2) == round(expected_floor_alfa, 2)

        # Floor Digi 8%: (cost_base + min_profit) / digi_lev_payout
        expected_floor_digi_8 = (cost_base + config.COMPANY_MIN_PROFIT_PKR) / config.get_digi_leverage_payout_rate()
        assert round(floors.floor_digi_8, 2) == round(expected_floor_digi_8, 2)

        # Guaranteed profit check at Alfa floor price:
        alfa_payout = floors.floor_alfa * config.get_alfa_payout_rate()
        net_profit_alfa = alfa_payout - cost_base
        assert round(net_profit_alfa, 2) == config.COMPANY_MIN_PROFIT_PKR

        # Guaranteed profit check at Digi 8% floor price:
        digi_payout = floors.floor_digi_8 * config.get_digi_leverage_payout_rate()
        net_profit_digi = digi_payout - cost_base
        assert round(net_profit_digi, 2) == config.COMPANY_MIN_PROFIT_PKR


class TestPerformanceThroughput:
    """Ensure generic category shipping resolution is ultra-fast with zero memory leaks."""

    def test_high_throughput_resolution(self) -> None:
        titles = [
            "Haier Single Tub Washing Machine 8 KG",
            "Haier Twin Tub Washing Machine 10 KG",
            "Haier Fully Automatic Top Load 12 KG",
            "Gree Inverter AC 1.5 Ton 18AITH21W",
            "Dawlance 4467 SD Mini Bar Refrigerator",
            "Philips Electric Kettle 1.7L",
        ]

        start_time = time.perf_counter()
        # Resolve 12,000 items in a tight loop
        iterations = 2000
        for _ in range(iterations):
            for t in titles:
                resolve_fallback_shipping(t, brand="Haier")
        elapsed = time.perf_counter() - start_time

        # 12,000 resolutions should comfortably take under 0.5 seconds on modern CPU
        assert elapsed < 1.0, f"Performance too slow: {elapsed:.3f}s for 12,000 resolutions"
