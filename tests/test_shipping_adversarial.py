"""Adversarial and boundary stress tests for generic category shipping fallback logic."""

from __future__ import annotations

import time
from typing import Any

from pricing_engine.calculator import (
    _extract_numeric_capacity,
    calculate_cost_base,
    calculate_floors,
    resolve_fallback_shipping,
)
from pricing_engine.models import CostFloors, ProductInput
from pricing_engine.pipeline import resolve_shipping_estimate


class TestAdversarialInputsAndEdgeCases:
    """Stress test the generic category shipping resolution against malformed or extreme inputs."""

    def test_empty_string_and_null_inputs(self) -> None:
        rate, label = resolve_fallback_shipping("", brand="")
        assert rate == 3000.0
        assert label == "General Appliance"

        rate, label = resolve_fallback_shipping("   ", brand="   ")
        assert rate == 3000.0
        assert label == "General Appliance"

    def test_empty_and_corrupted_config_tables(self) -> None:
        # Empty dict
        rate, label = resolve_fallback_shipping("Haier Twin Tub 10 KG", brand="Haier", config_table={})
        assert rate == 3000.0
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
        rate, label = resolve_fallback_shipping("Haier washer", brand="Haier", config_table=corrupted_config)
        assert rate == 3500.0  # Category default fallback
        assert label == "broken_2"

        rate, label = resolve_fallback_shipping("Gree ac", brand="Gree", config_table=corrupted_config)
        assert rate == 3500.0  # Category default fallback
        assert label == "broken_3"

    def test_extreme_and_boundary_capacities(self) -> None:
        # Micro washer (3.5kg) -> hits lowest bracket <= 8.5kg
        rate, label = resolve_fallback_shipping("Haier Single Tub Washer 3.5 KG", brand="Haier")
        assert rate == 2500.0
        assert "3.5kg" in label

        # Giant industrial washer (25kg) -> hits highest bracket <= 999kg
        rate, label = resolve_fallback_shipping("Haier Automatic Washer 25 KG Industrial", brand="Haier")
        assert rate == 4500.0
        assert "25kg" in label

        # Boundary exact values: 8.5kg
        rate, label = resolve_fallback_shipping("Dawlance Twin Tub 8.5kg", brand="Dawlance")
        assert rate == 3000.0

        # Boundary exact values: 10.0kg
        rate, label = resolve_fallback_shipping("Dawlance Twin Tub 10kg", brand="Dawlance")
        assert rate == 3500.0

        # Boundary exact values: 11.0kg
        rate, label = resolve_fallback_shipping("Dawlance Twin Tub 11kg", brand="Dawlance")
        assert rate == 3500.0

        # Boundary exact values: 12.0kg
        rate, label = resolve_fallback_shipping("Dawlance Twin Tub 12kg", brand="Dawlance")
        assert rate == 3800.0

        # Boundary exact values: 15.0kg
        rate, label = resolve_fallback_shipping("Dawlance Twin Tub 15kg", brand="Dawlance")
        assert rate == 4500.0

    def test_titles_with_no_capacity_numbers(self) -> None:
        # Washing machine with zero numbers in title
        rate, label = resolve_fallback_shipping("Haier Fully Automatic Top Load Washing Machine Grey", brand="Haier")
        # Should gracefully fallback to category default (Rs. 3500)
        assert rate == 3500.0
        assert label == "Automatic Washer"

        # Twin tub with zero numbers
        rate, label = resolve_fallback_shipping("Super Asia Semi Automatic Twin Tub Washer", brand="Super Asia")
        assert rate == 3500.0
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
        injection_title = "Haier Washer 10kg'; DROP TABLE repricing_runs; --"
        rate, label = resolve_fallback_shipping(injection_title, brand="Haier")
        assert rate == 3500.0
        assert "10kg" in label

        # Regex metacharacters in title
        regex_title = "Haier Washer [10kg] (Special) + Edition * Premium? {Deluxe}"
        rate, label = resolve_fallback_shipping(regex_title, brand="Haier")
        assert rate == 3500.0
        assert "10kg" in label

    def test_negative_and_zero_dimension_combinations(self) -> None:
        # Negative length
        p1 = ProductInput(1, "Haier", "Haier Automatic 10kg", -60.0, 60.0, 85.0, 50000, 500, {})
        ship1, fb1 = resolve_shipping_estimate(p1)
        assert ship1 == 3500.0
        assert fb1 is True

        # One dimension is zero
        p2 = ProductInput(2, "Haier", "Haier Automatic 10kg", 60.0, 0.0, 85.0, 50000, 500, {})
        ship2, fb2 = resolve_shipping_estimate(p2)
        assert ship2 == 3500.0
        assert fb2 is True

        # All dimensions positive
        p3 = ProductInput(3, "Haier", "Haier Automatic 10kg", 60.0, 60.0, 85.0, 50000, 500, {})
        ship3, fb3 = resolve_shipping_estimate(p3)
        assert ship3 == 4284.0
        assert fb3 is False


class TestCostMathIntegrityWithShippingFallback:
    """Verify that shipping fallback integrates 100% correctly with cost base and profit floors."""

    def test_floors_mathematical_precision(self) -> None:
        # Product with 50,000 net price and 3,500 shipping fallback
        net_price = 50000.0
        shipping = 3500.0
        cost_base = calculate_cost_base(net_price, shipping)
        assert cost_base == 53500.0

        floors = calculate_floors(cost_base, min_profit=500.0, net_price=net_price)
        assert isinstance(floors, CostFloors)

        # Floor Alfa (10% commission): (53,500 + 500) / 0.90 = 54,000 / 0.90 = 60,000.0
        assert round(floors.floor_alfa, 2) == 60000.0

        # Floor Digi 8% (8% commission): (53,500 + 500) / 0.92 = 54,000 / 0.92 = 58,695.65
        assert round(floors.floor_digi_8, 2) == 58695.65

        # Guaranteed profit check at Alfa floor price:
        # Revenue after 10% commission: 60,000 * 0.90 = 54,000.0
        # Net profit = 54,000.0 - 53,500.0 = 500.0 (Guaranteed +Rs. 500 profit floor!)
        alfa_payout = floors.floor_alfa * 0.90
        net_profit_alfa = alfa_payout - cost_base
        assert round(net_profit_alfa, 2) == 500.0

        # Guaranteed profit check at Digi 8% floor price:
        digi_payout = floors.floor_digi_8 * 0.92
        net_profit_digi = digi_payout - cost_base
        assert round(net_profit_digi, 2) == 500.0


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
