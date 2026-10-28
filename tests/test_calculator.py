import math

from pricing_engine.calculator import (
    calculate_adaptive_target_price,
    calculate_baseline,
    calculate_cost_base,
    calculate_dynamic_retention_pct,
    calculate_floors,
    calculate_shipping_estimate,
    calculate_volumetric_weight,
    find_winning_psychological_price,
    format_dynamic_retention_pct,
    get_fallback_psychological_price,
    get_monopoly_psychological_price,
)


def test_volumetric_weight_calculation() -> None:
    # 100cm x 50cm x 50cm = 250,000 / 5000 = 50.0 KG
    weight = calculate_volumetric_weight(100.0, 50.0, 50.0)
    assert weight == 50.0


def test_shipping_estimate_calculation() -> None:
    # 50.0 KG * 70 PKR/KG = 3500.0 PKR
    shipping = calculate_shipping_estimate(50.0, rate_per_kg=70.0)
    assert shipping == 3500.0


def test_cost_base_calculation() -> None:
    cost_base = calculate_cost_base(net_price=70000.0, shipping=3500.0)
    assert cost_base == 73500.0


def test_calculate_floors() -> None:
    cost_base = 72000.0
    floors = calculate_floors(cost_base=cost_base, min_profit=500.0)

    # 72000 / 0.90 = 80000.0
    assert math.isclose(floors.zero_margin_10, 80000.0, rel_tol=1e-5)
    # 72000 / 0.92 = 78260.8695
    assert math.isclose(floors.zero_margin_8, 78260.8695, rel_tol=1e-4)

    # (72000 + 500) / 0.90 = 80555.55
    assert math.isclose(floors.floor_alfa, 80555.5555, rel_tol=1e-4)
    assert math.isclose(floors.floor_digi_10, 80555.5555, rel_tol=1e-4)
    # (72000 + 500) / 0.92 = 78804.3478
    assert math.isclose(floors.floor_digi_8, 78804.3478, rel_tol=1e-4)


def test_calculate_baseline() -> None:
    # (70000 + 5000) / 0.90 = 83333.33
    baseline = calculate_baseline(cost_base=70000.0, target_profit=5000.0)
    assert math.isclose(baseline, 83333.3333, rel_tol=1e-4)


def test_winning_psychological_price_standard_case() -> None:
    # Competitor is at 73,000, Floor is at 72,877
    # 73000 - 100 = 72900
    # Candidate endings: 72899 is <= 72900 and >= 72877
    price = find_winning_psychological_price(floor_min=72877.0, competitor_price=73000.0)
    assert price == 72899
    assert price < 73000
    assert price >= 72877


def test_winning_psychological_price_tight_margin() -> None:
    # Competitor at 73,000, Floor at 72,950
    # Target ceiling 72,900 is below floor 72,950
    # Fallback to competitor - 1 = 72999 (which is >= 72950)
    price = find_winning_psychological_price(floor_min=72950.0, competitor_price=73000.0)
    assert price == 72999
    assert price < 73000
    assert price >= 72950


def test_winning_psychological_price_unviable() -> None:
    # Competitor at 72,000, Floor at 72,500 -> impossible to win profitably
    price = find_winning_psychological_price(floor_min=72500.0, competitor_price=72000.0)
    assert price is None


def test_monopoly_psychological_price() -> None:
    # Remainder >= 500 -> base + 999
    assert get_monopoly_psychological_price(74600.0) == 74999
    # Remainder < 500 -> base + 499
    assert get_monopoly_psychological_price(74200.0) == 74499


def test_adaptive_target_tier5_under_800_tight_gap() -> None:
    # Gap < 800 PKR (e.g. 600 or 700 PKR) -> Closest Rs. 100 undercut
    floor = 70000.0
    competitor_600 = 70600.0
    assert (
        calculate_adaptive_target_price(floor_min=floor, competitor_price=competitor_600) == 70500.0
    )

    competitor_700 = 70700.0
    assert (
        calculate_adaptive_target_price(floor_min=floor, competitor_price=competitor_700) == 70600.0
    )


def test_adaptive_target_tier4_800_to_1500_gap() -> None:
    # 800 <= Gap < 1,500 PKR (e.g. 800, 900, 1000, 1200) -> Rs. 200 undercut
    floor = 70000.0
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=70800.0) == 70600.0
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=70900.0) == 70700.0
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=71000.0) == 70800.0
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=71200.0) == 71000.0


def test_adaptive_target_tier3_1500_to_2000_gap() -> None:
    # 1,500 <= Gap < 2,000 PKR (e.g. 1500, 1800, 1900) -> Rs. 500 customer discount, min 1000 buffer
    floor = 70000.0
    # Gap = 1,500 -> 71,500 - 500 = 71,000 (Floor + 1,000)
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=71500.0) == 71000.0
    # Gap = 1,800 -> 71,800 - 500 = 71,300 (Customer gets 500 discount, seller gets 1,300 buffer)
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=71800.0) == 71300.0
    # Gap = 1,900 -> 71,900 - 500 = 71,400 (Customer gets 500 discount, seller gets 1,400 buffer)
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=71900.0) == 71400.0


def test_adaptive_target_tier2_2000_to_10000_gap() -> None:
    # 2,000 <= Gap < 10,000 PKR (3 Zeros) -> Unified Dynamic Glide (80% at 2k down to 50% at 10k)
    floor = 70000.0
    # Gap = 2,000 -> 80% is 1,600 -> 71,600
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=72000.0) == 71600.0
    # Gap = 2,500 -> 78.125% is 1,953.125 -> 71,953.125
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=72500.0) == 71953.125
    # Gap = 5,000 -> 68.75% is 3,437.5 -> 73,437.5
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=75000.0) == 73437.5
    # Gap = 9,000 -> 53.75% is 4,837.5 -> 74,837.5
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=79000.0) == 74837.5


def test_dynamic_retention_helpers_dry() -> None:
    # 2,000 PKR boundary -> exactly 80% (0.80)
    assert calculate_dynamic_retention_pct(2000.0) == 0.80
    assert format_dynamic_retention_pct(2000.0) == "80%"

    # 5,000 PKR midpoint -> exactly 68.75% (0.6875) -> rounds to 69%
    assert calculate_dynamic_retention_pct(5000.0) == 0.6875
    assert format_dynamic_retention_pct(5000.0) == "69%"

    # 10,000 PKR boundary -> exactly 50% (0.50)
    assert calculate_dynamic_retention_pct(10000.0) == 0.50
    assert format_dynamic_retention_pct(10000.0) == "50%"

    # Clamping tests:
    # Below 2,000 PKR -> clamped to 80%
    assert calculate_dynamic_retention_pct(1000.0) == 0.80
    assert format_dynamic_retention_pct(1000.0) == "80%"

    # Above 10,000 PKR -> clamped to 50%
    assert calculate_dynamic_retention_pct(15000.0) == 0.50
    assert format_dynamic_retention_pct(15000.0) == "50%"

    # Exact fractional rounding:
    # Gap = 2,445 -> 0.80 - (445 / 8000) * 0.30 = 0.7833125 -> "78%"
    assert round(calculate_dynamic_retention_pct(2445.0), 4) == 0.7833
    assert format_dynamic_retention_pct(2445.0) == "78%"


def test_adaptive_target_4_zeros_large_gap_item1() -> None:
    # Gap >= 10,000 PKR: Item #1 scenario
    # Landed Cost = 430,291, Floor 10% = 478,656.67, Competitor = 489,999.0
    floor = 478656.67
    competitor = 489999.0
    cost_base = 430291.0
    target = calculate_adaptive_target_price(
        floor_min=floor,
        competitor_price=competitor,
        cost_base=cost_base,
        payout_rate=0.92,
        large_gap_profit_target=10000.0,
    )
    # Target should be bounded around the 10k profit point
    price = find_winning_psychological_price(
        floor_min=floor, competitor_price=competitor, max_ceiling=target
    )
    assert price == 478999
    # Profit at 478,999 on DigiMall: (478999 * 0.92) - 430291 = 10,388 (~10k sweet spot with clean .999 ending)
    profit = round((price * 0.92) - cost_base)
    assert profit == 10388


def test_tier2_to_tier1_boundary_continuity_no_cliff() -> None:
    # Cost base 63,000 PKR, Floor Alfa (10%) = (63000 + 500) / 0.90 = 70555.56 PKR
    cost_base = 63000.0
    floor = 70555.56
    payout_rate = 0.90

    # Gap = 9,999 PKR (Tier 2, 50% split)
    comp_9999 = floor + 9999.0
    t_9999 = calculate_adaptive_target_price(
        floor_min=floor, competitor_price=comp_9999, cost_base=cost_base, payout_rate=payout_rate
    )
    p_9999 = find_winning_psychological_price(floor, comp_9999, max_ceiling=t_9999)

    # Gap = 10,000 PKR (Tier 1 boundary)
    comp_10000 = floor + 10000.0
    t_10000 = calculate_adaptive_target_price(
        floor_min=floor, competitor_price=comp_10000, cost_base=cost_base, payout_rate=payout_rate
    )
    p_10000 = find_winning_psychological_price(floor, comp_10000, max_ceiling=t_10000)

    # ZERO price cliff between 9,999 and 10,000 gap
    assert p_9999 == 75499
    assert p_10000 == 75499
    assert p_9999 == p_10000

    # Gap = 12,000 PKR (Smooth transition toward 10k profit cap)
    comp_12000 = floor + 12000.0
    t_12000 = calculate_adaptive_target_price(
        floor_min=floor, competitor_price=comp_12000, cost_base=cost_base, payout_rate=payout_rate
    )
    p_12000 = find_winning_psychological_price(floor, comp_12000, max_ceiling=t_12000)
    assert p_12000 == 77499
    assert p_12000 > p_10000

    # Gap = 15,000 PKR (Reaches ~10k profit target)
    comp_15000 = floor + 15000.0
    t_15000 = calculate_adaptive_target_price(
        floor_min=floor, competitor_price=comp_15000, cost_base=cost_base, payout_rate=payout_rate
    )
    p_15000 = find_winning_psychological_price(floor, comp_15000, max_ceiling=t_15000)
    assert p_15000 == 80499

    # Gap = 25,000 PKR (Capped at large_gap_profit_target 10,000 ceiling)
    comp_25000 = floor + 25000.0
    t_25000 = calculate_adaptive_target_price(
        floor_min=floor, competitor_price=comp_25000, cost_base=cost_base, payout_rate=payout_rate
    )
    p_25000 = find_winning_psychological_price(floor, comp_25000, max_ceiling=t_25000)
    assert p_25000 == 81099  # Safely capped at ~10k profit point, never follows comp to 95k!
    assert round((p_25000 * 0.90) - cost_base) == 9989  # ~10k sweet spot profit


def test_tight_margin_under_100_selects_round_50_item18() -> None:
    # Item #18 scenario: Competitor at 173,099, 8% Floor at 173,003.26 (Gap = 95.74 PKR)
    # System selects clean rounded price 173,050 (multiple of 50) below competitor
    floor_min = 173003.26
    competitor = 173099.0
    cost_base = 158663.0

    target = calculate_adaptive_target_price(
        floor_min=floor_min,
        competitor_price=competitor,
        cost_base=cost_base,
        payout_rate=0.92,
    )
    price = find_winning_psychological_price(
        floor_min=floor_min, competitor_price=competitor, max_ceiling=target
    )

    assert price == 173050
    assert price < competitor
    assert price >= floor_min
    profit = round((price * 0.92) - cost_base)
    assert profit == 543  # Clean +543 PKR profit protected (above 500 guarantee)


def test_undercut_gap_150_selects_round_50_when_no_psychological_price() -> None:
    # Gap = 150 PKR: Competitor at 173,153, Floor at 173,003.26
    # Target ceiling is 173,053. Highest clean multiple of 50 is 173,050
    floor_min = 173003.26
    competitor = 173153.0
    cost_base = 158663.0

    target = calculate_adaptive_target_price(
        floor_min=floor_min,
        competitor_price=competitor,
        cost_base=cost_base,
        payout_rate=0.92,
    )
    price = find_winning_psychological_price(
        floor_min=floor_min, competitor_price=competitor, max_ceiling=target
    )

    assert price == 173050
    assert price < competitor
    assert price >= floor_min
    profit = round((price * 0.92) - cost_base)
    assert profit == 543  # Extra margin protected via round 50 pricing


def test_tight_gaps_roundoff_matrix() -> None:
    # Floor is 173,003.26 -> floor_ceil is 173,004
    floor_min = 173003.26

    # Case 1: Gap = 20 PKR (Competitor = 173,023) -> selects round 10 (173,020)
    p_20 = find_winning_psychological_price(floor_min=floor_min, competitor_price=173023.0)
    assert p_20 == 173020
    assert p_20 < 173023.0
    assert p_20 >= floor_min
    assert p_20 % 10 == 0

    # Case 2: Gap = 15 PKR (Competitor = 173,019) -> selects round 10 (173,010)
    p_15 = find_winning_psychological_price(floor_min=floor_min, competitor_price=173019.0)
    assert p_15 == 173010
    assert p_15 < 173019.0
    assert p_15 >= floor_min
    assert p_15 % 10 == 0

    # Case 3: Gap = 60 PKR (Competitor = 173,064) -> selects round 50 (173,050)
    p_60 = find_winning_psychological_price(floor_min=floor_min, competitor_price=173064.0)
    assert p_60 == 173050
    assert p_60 < 173064.0
    assert p_60 >= floor_min
    assert p_60 % 50 == 0

    # Case 4: Gap = 5 PKR (Competitor = 173,009) -> selects round 5 (173,005)
    p_5 = find_winning_psychological_price(floor_min=floor_min, competitor_price=173009.0)
    assert p_5 == 173005
    assert p_5 < 173009.0
    assert p_5 >= floor_min
    assert p_5 % 5 == 0

    # Case 5: Gap = 0.50 PKR (Competitor = 173,003.70) -> strictly below floor_ceil (173,004) -> None
    p_unviable = find_winning_psychological_price(floor_min=floor_min, competitor_price=173003.70)
    assert p_unviable is None


def test_fallback_psychological_price_always_ends_in_999() -> None:
    # Item #17 numbers: Cost base 137,125, Floor 149,592.39, Payout rate 0.92, Profit target 1,500
    # Must produce standard psychological ending 150,999 (not 150,899)
    price = get_fallback_psychological_price(
        cost_base=137125.0,
        floor_min=149592.39,
        payout_rate=0.92,
        profit_target=1500.0,
    )
    assert price == 150999
    assert price % 1000 == 999
    assert price >= 149592.39
    profit = round((price * 0.92) - 137125.0)
    assert profit == 1794
