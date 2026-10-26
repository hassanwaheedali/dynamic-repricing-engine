import contextlib
import math
import re
from typing import Any

import config
from pricing_engine.models import CostFloors

# Standard psychological price endings ordered from highest to lowest margin
PSYCHOLOGICAL_ENDINGS: tuple[int, ...] = (999, 899, 799, 499, 299, 199, 99)


def _extract_numeric_capacity(text: str, unit: str = "kg") -> float | None:
    """Extract numeric capacity or size from title or model code."""
    if unit == "kg":
        kg_match = re.search(r"(\d+(?:\.\d+)?)\s*[-]?\s*(?:kg|k\.g|kilo)\b", text)
        if kg_match:
            with contextlib.suppress(ValueError, TypeError):
                return float(kg_match.group(1))
        # Model code stem extraction (e.g. HWM-120 -> 12kg, HW 105 -> 10.5kg, 80-1217 -> 8kg, 150- -> 15kg)
        model_match = re.search(r"\b[a-z]{0,4}[- ]?(\d{2,3})(?:[- ]|\b)", text)
        if model_match:
            with contextlib.suppress(ValueError, TypeError):
                raw_num = float(model_match.group(1))
                if 50 <= raw_num <= 250:
                    return raw_num / 10.0
    return None


def resolve_fallback_shipping(
    product_name: str,
    brand: str = "",
    config_table: dict[str, Any] | None = None,
) -> tuple[float, str]:
    """Dynamically resolve default fallback shipping from config without hardcoded category logic.

    Inspects config.DEFAULT_CATEGORY_SHIPPING['categories'] rules in declared order.
    Matches keywords or patterns, resolves sub-types and capacity brackets, and returns
    the matched shipping rate and display label.

    Args:
        product_name: Product title or description from input catalog.
        brand: Brand name.
        config_table: Optional custom configuration dictionary (defaults to config.DEFAULT_CATEGORY_SHIPPING).

    Returns:
        Tuple of (shipping_amount: float, fallback_label: str).
    """
    table = config.DEFAULT_CATEGORY_SHIPPING if config_table is None else config_table
    text = f"{brand} {product_name}".lower()

    for cat in table.get("categories", []):
        cat_keywords: list[str] = cat.get("keywords", [])
        cat_pattern: str | None = cat.get("pattern")
        cat_name: str = cat.get("name", cat.get("id", "Appliance"))

        is_match = bool(
            (cat_pattern and re.search(cat_pattern, text))
            or any(kw in text for kw in cat_keywords)
        )

        if not is_match:
            continue

        # Category matched! Check sub-types
        sub_types = cat.get("sub_types", [])
        chosen_sub: dict[str, Any] | None = None
        default_sub: dict[str, Any] | None = None

        for sub in sub_types:
            if sub.get("is_default"):
                default_sub = sub
            sub_pat = sub.get("pattern")
            sub_kws = sub.get("keywords", [])
            if sub_pat and re.search(sub_pat, text):
                chosen_sub = sub
                break
            if any(kw in text for kw in sub_kws):
                chosen_sub = sub
                break

        sub_to_use = chosen_sub or default_sub
        if sub_to_use:
            sub_label = sub_to_use.get("name", cat_name)
            # Direct fixed rate on sub-type
            if "rate" in sub_to_use:
                return float(sub_to_use["rate"]), sub_label

            # Capacity bracket matching
            brackets = sub_to_use.get("brackets", [])
            if brackets:
                unit = cat.get("capacity_unit", "kg")
                cap_val = _extract_numeric_capacity(text, unit=unit)
                if cap_val is not None:
                    for b in brackets:
                        max_limit = b.get("max", b.get("max_kg", 999.0))
                        if cap_val <= max_limit:
                            rate = float(b.get("rate", cat.get("default", 3500.0)))
                            return rate, f"{sub_label} ({cap_val:g}{unit})"

            # Default rate on sub-type or category
            sub_default = sub_to_use.get("default", cat.get("default", cat.get("default_rate", 3500.0)))
            return float(sub_default), sub_label

        # Default rate on category
        cat_default = cat.get("default", cat.get("default_rate", 3500.0))
        return float(cat_default), cat_name

    # Global fallback if no category matched
    global_default = table.get("default", table.get("default_rate", 3000.0))
    return float(global_default), "General Appliance"


def calculate_volumetric_weight(
    length: float, width: float, height: float, divisor: float | None = None
) -> float:
    """Calculate volumetric weight in kilograms.

    Args:
        length: Package length in centimeters.
        width: Package width in centimeters.
        height: Package height in centimeters.
        divisor: Courier volumetric divisor (defaults to config.VOLUMETRIC_DIVISOR).

    Returns:
        Volumetric weight in kilograms.
    """
    eff_divisor = config.VOLUMETRIC_DIVISOR if divisor is None else divisor
    if eff_divisor <= 0:
        raise ValueError("Divisor must be greater than zero.")
    return (length * width * height) / eff_divisor


def calculate_shipping_estimate(
    volumetric_weight: float, rate_per_kg: float | None = None
) -> float:
    """Calculate courier shipping estimate based on volumetric weight.

    Args:
        volumetric_weight: Volumetric weight in KG.
        rate_per_kg: Courier rate per KG (defaults to config.COURIER_RATE_PER_KG).

    Returns:
        Estimated shipping cost rounded to 2 decimal places.
    """
    eff_rate = config.COURIER_RATE_PER_KG if rate_per_kg is None else rate_per_kg
    return round(volumetric_weight * eff_rate, 2)


def calculate_cost_base(net_price: float, shipping: float) -> float:
    """Calculate the base landed cost before marketplace commission or profit.

    Args:
        net_price: Vendor wholesale/purchase price.
        shipping: Courier delivery cost estimate.

    Returns:
        Total base cost.
    """
    return round(net_price + shipping, 2)


def calculate_personal_commission(
    amount: float, personal_comm_pct: float | None = None
) -> int:
    """Calculate personal commission strictly on Real Net Profit.

    Args:
        amount: Real Net Profit amount in PKR.
        personal_comm_pct: Personal commission percentage (defaults to config.DEFAULT_PERSONAL_COMM_PCT).

    Returns:
        Rounded integer personal commission in PKR.
    """
    eff_pct = config.DEFAULT_PERSONAL_COMM_PCT if personal_comm_pct is None else personal_comm_pct
    if amount <= 0 or eff_pct <= 0:
        return 0
    return round(amount * (eff_pct / 100.0))


def calculate_effective_min_profit(
    base_min_profit: float | None = None,
    personal_comm_pct: float = 0.0,
) -> float:
    """Calculate the minimum total net profit required so that the company receives at least base_min_profit.

    Formula: base_min_profit / (1.0 - (personal_comm_pct / 100.0))
    For 5% commission and Rs. 500 company floor: 500 / 0.95 = 526.315... PKR.

    Args:
        base_min_profit: Minimum company net profit guarantee (defaults to config.COMPANY_MIN_PROFIT_PKR).
        personal_comm_pct: Personal commission percentage on Real Net Profit.

    Returns:
        Float effective gross profit target in PKR before rounding.
    """
    base = config.COMPANY_MIN_PROFIT_PKR if base_min_profit is None else base_min_profit
    if personal_comm_pct <= 0:
        return float(base)
    rate = personal_comm_pct / 100.0
    if rate >= 1.0:
        return float(base)
    return float(base / (1.0 - rate))


def calculate_effective_target_profit(
    catalog_profit: float | None = None,
    personal_comm_pct: float = 0.0,
    base_min_profit: float | None = None,
) -> int:
    """Calculate effective target profit for catalog repricing under personal commission.

    Ensures target profit is at least ceil(effective_min_profit) so that the company's
    net profit after personal commission deduction remains >= base_min_profit.

    Args:
        catalog_profit: Profit target specified in input catalog (defaults to config.COMPANY_MIN_PROFIT_PKR).
        personal_comm_pct: Personal commission percentage on Real Net Profit.
        base_min_profit: Minimum company floor profit (defaults to config.COMPANY_MIN_PROFIT_PKR).

    Returns:
        Integer target profit in PKR.
    """
    base = config.COMPANY_MIN_PROFIT_PKR if base_min_profit is None else base_min_profit
    eff_min = math.ceil(calculate_effective_min_profit(base, personal_comm_pct))
    if catalog_profit is None:
        return eff_min
    return max(math.ceil(catalog_profit), eff_min)


def split_real_profit(
    real_profit: float | None,
    personal_comm_pct: float = 0.0,
) -> tuple[int, int | None]:
    """Split real net profit into personal commission and company profit.

    Args:
        real_profit: Total real net profit in PKR (None if unpriced or skipped).
        personal_comm_pct: Personal commission percentage on real profit.

    Returns:
        Tuple of (my_commission: int, company_profit: int | None).
        - If real_profit is None -> (0, None)
        - If real_profit <= 0 -> (0, round(real_profit))
        - If real_profit > 0 -> (round(real_profit * (comm_pct / 100)), round(real_profit) - my_commission)
    """
    if real_profit is None:
        return 0, None
    if real_profit <= 0 or personal_comm_pct <= 0:
        return 0, round(real_profit)
    my_comm = round(real_profit * (personal_comm_pct / 100.0))
    company_profit = round(real_profit) - my_comm
    return my_comm, company_profit


def calculate_floors(
    cost_base: float,
    min_profit: float | None = None,
    net_price: float = 0.0,
    personal_comm_pct: float = 0.0,
) -> CostFloors:
    """Calculate breakeven costs and absolute minimum profit floors.

    When personal_comm_pct > 0, the hard floor guarantees that the company receives at least
    min_profit (default config.COMPANY_MIN_PROFIT_PKR) as its (100 - personal_comm_pct)% share
    of Total Real Profit.

    Formula: Total Min Profit = min_profit / (1.0 - (personal_comm_pct / 100.0)).
    For 5% commission and Rs. 500 company floor: 500 / 0.95 = Rs. 526.32.

    Args:
        cost_base: Total landed cost base.
        min_profit: Minimum company profit guarantee in PKR (defaults to config.COMPANY_MIN_PROFIT_PKR).
        net_price: Kept for backwards compatibility.
        personal_comm_pct: Personal commission percentage on Real Net Profit (default 0.0).

    Returns:
        CostFloors object with 0% margin and hard floors for Alfa and Digi.
    """
    base_min_profit = config.COMPANY_MIN_PROFIT_PKR if min_profit is None else min_profit

    if personal_comm_pct > 0:
        eff_pct = personal_comm_pct
        alfa_comm_pct = config.ALFA_PERSONAL_COMM_PCT if personal_comm_pct == config.DEFAULT_PERSONAL_COMM_PCT else eff_pct
        digi_comm_pct = config.DIGI_PERSONAL_COMM_PCT if personal_comm_pct == config.DEFAULT_PERSONAL_COMM_PCT else eff_pct

        alfa_eff_profit = calculate_effective_min_profit(base_min_profit, alfa_comm_pct)
        digi_eff_profit = calculate_effective_min_profit(base_min_profit, digi_comm_pct)
        global_eff_profit = calculate_effective_min_profit(base_min_profit, eff_pct)

        alfa_personal_comm = round(alfa_eff_profit - base_min_profit)
        digi_personal_comm = round(digi_eff_profit - base_min_profit)
        personal_comm = round(global_eff_profit - base_min_profit)
    else:
        alfa_eff_profit = base_min_profit
        digi_eff_profit = base_min_profit
        alfa_personal_comm = 0
        digi_personal_comm = 0
        personal_comm = 0

    alfa_rate = config.get_alfa_payout_rate()
    digi_std_rate = config.get_digi_standard_payout_rate()
    digi_lev_rate = config.get_digi_leverage_payout_rate()

    zero_margin_10 = cost_base / alfa_rate
    zero_margin_8 = cost_base / digi_lev_rate
    floor_alfa = (cost_base + alfa_eff_profit) / alfa_rate
    floor_digi_10 = (cost_base + digi_eff_profit) / digi_std_rate
    floor_digi_8 = (cost_base + digi_eff_profit) / digi_lev_rate

    return CostFloors(
        cost_base=cost_base,
        zero_margin_10=zero_margin_10,
        zero_margin_8=zero_margin_8,
        floor_alfa=floor_alfa,
        floor_digi_10=floor_digi_10,
        floor_digi_8=floor_digi_8,
        personal_comm=personal_comm,
        alfa_personal_comm=alfa_personal_comm,
        digi_personal_comm=digi_personal_comm,
    )


def calculate_baseline(cost_base: float, target_profit: float) -> float:
    """Calculate standard baseline price for comparison.

    Args:
        cost_base: Landed cost base.
        target_profit: Target profit margin from input catalog.

    Returns:
        Baseline catalog price at standard AlfaMall commission.
    """
    return (cost_base + target_profit) / config.get_alfa_payout_rate()


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
