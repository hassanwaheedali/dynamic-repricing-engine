import math

from pricing_engine.models import CostFloors

# Standard psychological price endings ordered from highest to lowest margin
PSYCHOLOGICAL_ENDINGS: tuple[int, ...] = (999, 899, 799, 499, 299, 199, 99)


def calculate_volumetric_weight(
    length: float, width: float, height: float, divisor: float = 5000.0
) -> float:
    """Calculate volumetric weight in kilograms.

    Args:
        length: Package length in centimeters.
        width: Package width in centimeters.
        height: Package height in centimeters.
        divisor: Courier volumetric divisor (default 5000.0).

    Returns:
        Volumetric weight in kilograms.
    """
    if divisor <= 0:
        raise ValueError("Divisor must be greater than zero.")
    return (length * width * height) / divisor


def calculate_shipping_estimate(volumetric_weight: float, rate_per_kg: float = 70.0) -> float:
    """Calculate courier shipping estimate based on volumetric weight.

    Args:
        volumetric_weight: Volumetric weight in KG.
        rate_per_kg: Courier rate per KG (default 70.0 PKR).

    Returns:
        Estimated shipping cost rounded to 2 decimal places.
    """
    return round(volumetric_weight * rate_per_kg, 2)


def calculate_cost_base(net_price: float, shipping: float) -> float:
    """Calculate the base landed cost before marketplace commission or profit.

    Args:
        net_price: Vendor wholesale/purchase price.
        shipping: Courier delivery cost estimate.

    Returns:
        Total base cost.
    """
    return round(net_price + shipping, 2)


def calculate_floors(cost_base: float, min_profit: float = 500.0) -> CostFloors:
    """Calculate breakeven costs and absolute minimum profit floors.

    Args:
        cost_base: Total landed cost base.
        min_profit: Minimum profit guarantee in PKR (default 500.0).

    Returns:
        CostFloors object with 0% margin and hard floors (+500 PKR) for Alfa and Digi.
    """
    zero_margin_10 = cost_base / 0.90
    zero_margin_8 = cost_base / 0.92
    floor_alfa = (cost_base + min_profit) / 0.90
    floor_digi_10 = (cost_base + min_profit) / 0.90
    floor_digi_8 = (cost_base + min_profit) / 0.92

    return CostFloors(
        cost_base=cost_base,
        zero_margin_10=zero_margin_10,
        zero_margin_8=zero_margin_8,
        floor_alfa=floor_alfa,
        floor_digi_10=floor_digi_10,
        floor_digi_8=floor_digi_8,
    )


def calculate_baseline(cost_base: float, target_profit: float) -> float:
    """Calculate standard baseline price for comparison.

    Args:
        cost_base: Landed cost base.
        target_profit: Target profit margin from input catalog.

    Returns:
        Baseline catalog price at standard 10% commission.
    """
    return (cost_base + target_profit) / 0.90


def find_winning_psychological_price(
    floor_min: float,
    competitor_price: float,
    undercut_buffer: float = 100.0,
    max_ceiling: float | None = None,
) -> int | None:
    """Determine the optimal winning price strictly undercutting the competitor.

    Constraint:
        floor_min <= Our Price < competitor_price (and <= max_ceiling if specified)

    Prices prioritize standard psychological thresholds (.999, .899, .799, .499, .299, .199, .099).

    Args:
        floor_min: Absolute minimum price floor (+500 PKR profit guaranteed).
        competitor_price: The lowest viable competitor price to undercut.
        undercut_buffer: Safety undercut margin below competitor (default 100.0 PKR).
        max_ceiling: Optional ceiling price cap (e.g. from maximum profit limit).

    Returns:
        Optimal integer price if profitable, otherwise None.
    """
    # Strict win requirement: our price must be strictly lower than competitor
    if competitor_price <= floor_min:
        return None

    floor_ceil = math.ceil(floor_min)
    if floor_ceil >= competitor_price:
        return None

    # Calculate effective maximum ceiling that strictly beats competitor
    target_ceiling = competitor_price - undercut_buffer
    if max_ceiling is not None:
        target_ceiling = min(target_ceiling, max_ceiling)

    if target_ceiling < floor_ceil:
        effective_max = int(competitor_price - 1.0)
        if max_ceiling is not None:
            effective_max = min(effective_max, int(max_ceiling))
    else:
        effective_max = int(target_ceiling)

    if effective_max < floor_ceil:
        effective_max = floor_ceil

    # 1. Search for standard psychological endings in allowed range [floor_ceil, effective_max]
    base_k = int(effective_max // 1000) * 1000
    candidates: list[int] = []

    for b in (base_k, base_k - 1000, base_k - 2000):
        for e in PSYCHOLOGICAL_ENDINGS:
            p = b + e
            if floor_ceil <= p <= effective_max and p < competitor_price:
                candidates.append(p)

    if candidates:
        return max(candidates)

    # 2. Clean 50-step round numbers (e.g. 173,050, 176,850)
    candidate_50 = (effective_max // 50) * 50
    if floor_ceil <= candidate_50 < competitor_price:
        return candidate_50

    # 3. Clean 10-step round numbers (e.g. 173,040, 173,060)
    candidate_10 = (effective_max // 10) * 10
    if floor_ceil <= candidate_10 < competitor_price:
        return candidate_10

    # 4. Clean 5-step round numbers (e.g. 173,045)
    candidate_5 = (effective_max // 5) * 5
    if floor_ceil <= candidate_5 < competitor_price:
        return candidate_5

    # 5. Fallback: match to effective_max or floor_ceil
    if floor_ceil <= effective_max < competitor_price:
        return effective_max

    if floor_ceil < competitor_price:
        return floor_ceil

    return None


def get_monopoly_psychological_price(raw_target: float) -> int:
    """Calculate attractive psychological price when 0 competitors exist.

    Args:
        raw_target: Calculated target price (cost_base + monopoly_profit) / 0.90.

    Returns:
        Psychological price ending in 999 or 499.
    """
    val = round(raw_target)
    base = (val // 1000) * 1000
    remainder = val % 1000
    if remainder >= 500:
        return base + 999
    return base + 499


def get_fallback_psychological_price(
    cost_base: float,
    floor_min: float,
    payout_rate: float,
    profit_target: float = 1500.0,
) -> int:
    """Calculate attractive psychological price when all market competitors are selling at a loss.

    Ensures the price is strictly above the minimum floor, delivers at least profit_target,
    and always terminates in standard retail .999 promo ending.

    Args:
        cost_base: Landed cost base.
        floor_min: Absolute minimum floor.
        payout_rate: Bank payout rate (e.g. 0.92 for Digi, 0.90 for Alfa).
        profit_target: Minimum target profit (default 1500.0 PKR).

    Returns:
        Attractive integer psychological price ending strictly in 999.
    """
    raw_target = (cost_base + profit_target) / payout_rate
    effective_min = max(raw_target, floor_min)
    base = (int(effective_min) // 1000) * 1000
    candidate = base + 999
    if candidate < effective_min:
        candidate = (base + 1000) + 999
    return candidate


def calculate_adaptive_target_price(
    floor_min: float,
    competitor_price: float,
    undercut_buffer: float = 100.0,
    cost_base: float | None = None,
    payout_rate: float = 0.90,
    large_gap_profit_target: float = 10000.0,
    min_buffer_3_zeros: float = 1000.0,
) -> float:
    """Calculate an adaptive target price based on the gap between floor and competitor.

    Tiers:
    - Tier 5 (Gap < 800 PKR, e.g. <= 799): Closest Rs. 100 undercut (or competitor - 1 if tight).
    - Tier 4 (800 <= Gap < 1,500 PKR, e.g. 800, 900, 1000, 1200): Rs. 200 undercut.
    - Tier 3 (1,500 <= Gap < 2,000 PKR, e.g. 1500, 1800, 1900): Rs. 500 customer discount (competitor - 500), min 1,000 buffer.
    - Tier 2 (2,000 <= Gap < 10,000 PKR, 3 Zeros): Proportional 50% split with min 1,000 PKR buffer.
    - Tier 1 (Gap >= 10,000 PKR, 4 Zeros): Option A sweet spot capped around ~10,000 target profit.

    Args:
        floor_min: Minimum selling price floor (+500 PKR profit guaranteed).
        competitor_price: Viable competitor price.
        undercut_buffer: Default undercut margin below competitor (default 100.0).
        cost_base: Optional landed cost base for exact profit targeting.
        payout_rate: Marketplace payout multiplier (e.g. 0.92 for Digi, 0.90 for Alfa).
        large_gap_profit_target: Target profit cap for large gaps (default 10,000.0).
        min_buffer_3_zeros: Minimum profit buffer above floor for 3 zeros (default 1,000.0).

    Returns:
        Target ceiling price before psychological rounding.
    """
    gap = competitor_price - floor_min

    if gap <= 0:
        return competitor_price - undercut_buffer

    # Tier 5: Gap < 800 PKR (e.g. <= 799) -> Closest Rs. 100 undercut (or competitor - 1 if tight)
    if gap < 800.0:
        if gap < 100.0:
            return competitor_price - 1.0
        return competitor_price - 100.0

    # Tier 4: Gap 800 to 1,499 PKR (e.g. 800, 900, 1000, 1200) -> Rs. 200 undercut
    if gap < 1500.0:
        return max(floor_min, competitor_price - 200.0)

    # Tier 3: Gap 1,500 to 1,999 PKR (e.g. 1500, 1800, 1900) -> Rs. 500 discount, min 1,000 buffer
    if gap < 2000.0:
        target = competitor_price - 500.0
        return max(floor_min + 1000.0, target)

    # Tier 2: Gap 2,000 to 9,999 PKR (3 Zeros) -> 50% split with min 1,000 buffer
    if gap < 10000.0:
        buffer = max(gap * 0.50, min_buffer_3_zeros)
        return floor_min + buffer

    # Tier 1: Gap >= 10,000 PKR (4 Zeros) -> Option A: Profit-targeted sweet spot (~10k)
    competitor_ceiling = competitor_price - undercut_buffer
    if cost_base is not None and payout_rate > 0:
        target_profit_price = (cost_base + large_gap_profit_target) / payout_rate
        floor_k = (int(floor_min) // 1000) * 1000
        next_999 = (floor_k + 999) if (floor_k + 999) >= floor_min else (floor_k + 1999)
        bounded_target = max(target_profit_price, float(next_999))
        return min(competitor_ceiling, bounded_target)

    # Fallback to 50% midpoint if cost_base is not provided
    return floor_min + (gap * 0.50)
