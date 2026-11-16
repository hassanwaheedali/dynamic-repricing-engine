"""Centralized Configuration for AlfaMall & DigiMall Dynamic Repricing Engine.

Edit the values below to customize marketplace bank commissions, personal
commission percentages (global or per-platform), profit floors, and courier
shipping rates from a single file.
"""

from __future__ import annotations

import math
from typing import Any

from pricing_engine.capacity import explicit_capacity_pattern
from pricing_engine.models import PlatformConfig

# ==============================================================================
# 1. PLATFORM BANK COMMISSIONS (%)
# ==============================================================================
# AlfaMall fixed marketplace commission percentage (Default: 10.0%)
ALFA_COMMISSION_PCT: float = 10.0

# DigiMall fixed marketplace commission percentage (Default: 8.0%)
DIGI_COMMISSION_PCT: float = 8.0


# ==============================================================================
# 2. PERSONAL COMMISSION SETTINGS (% ON REAL NET PROFIT)
# ==============================================================================
# Default personal commission percentage when running with --5pct or Mode [3]
DEFAULT_PERSONAL_COMM_PCT: float = 5.0

# Platform-specific personal commission percentages (used when personal commission
# mode is active; change independently if AlfaMall and DigiMall have different rates)
ALFA_PERSONAL_COMM_PCT: float = 5.0
DIGI_PERSONAL_COMM_PCT: float = 5.0


# ==============================================================================
# 3. COMPANY PROFIT FLOORS & TARGETS (PKR)
# ==============================================================================
# Absolute minimum company profit guarantee per unit in PKR (Default: Rs. 500)
COMPANY_MIN_PROFIT_PKR: float = 500.0

# Target profit when 0 competitors exist in the market (Default: Rs. 4,000)
MONOPOLY_PROFIT_PKR: float = 4000.0

# Safe fallback profit when all market competitors are below floor (Default: Rs. 1,500)
FALLBACK_PROFIT_PKR: float = 1500.0

# Sweet-spot profit cap when competitor price is excessively inflated (Default: Rs. 10,000)
LARGE_GAP_PROFIT_CAP_PKR: float = 10000.0

# Minimum company profit before triggering THIN_BUFFER risk alert (Default: Rs. 700)
THIN_BUFFER_THRESHOLD_PKR: float = 700.0


# ==============================================================================
# 4. COURIER & VOLUMETRIC LOGISTICS
# ==============================================================================
# Standard zone courier rate per volumetric KG in PKR (Default: Rs. 70.0)
COURIER_RATE_PER_KG: float = 70.0

# Volumetric weight divisor: (Length * Width * Height) / VOLUMETRIC_DIVISOR
VOLUMETRIC_DIVISOR: float = 5000.0


# ==============================================================================
# 5. DEFAULT FALLBACK SHIPPING ESTIMATES (PKR)
# Used when Length x Width x Height dimensions are not provided or 0 in catalog CSV
# Fully data-driven: add any new category, capacity extractor, or edit brackets
# directly here without touching engine code!
# ==============================================================================
DEFAULT_CAPACITY_RULES: dict[str, list[dict[str, Any]]] = {
    "kg": [
        {"pattern": explicit_capacity_pattern("KG")},
        # Model code stem extraction (e.g. HWM-120 -> 12kg, HW 105 -> 10.5kg, 80-1217 -> 8kg)
        {
            "pattern": r"\b[a-z]{0,4}[- ]?(\d{2,3})(?:[- ]|\b)",
            "min": 50.0,
            "max": 250.0,
            "divisor": 10.0,
        },
    ],
    "l": [
        {"pattern": explicit_capacity_pattern("L")},
    ],
    "cuft": [
        {"pattern": explicit_capacity_pattern("CFT")},
    ],
    "inch": [
        {"pattern": explicit_capacity_pattern("INCH")},
        {
            "pattern": (
                r"\b(24|32|39|40|42|43|48|49|50|55|58|60|65|70|75|85|98|100)"
                r"(?!\s*hz\b)(?=[a-z]\w*\b)"
            )
        },
    ],
}

DEFAULT_CATEGORY_SHIPPING: dict[str, Any] = {
    # --------------------------------------------------------------------------
    # CATEGORIES LIST (Top-to-bottom evaluation order)
    # --------------------------------------------------------------------------
    "categories": [
        # --- 1. WATER DISPENSERS --- (evaluated before washing_machine so "Top Load Water Dispenser" matches here)
        {
            "id": "water_dispenser",
            "name": "Water Dispenser",
            "keywords": [
                "water dispenser",
                "dispenser",
                "w/d",
                "bottom load",
                "table top dispenser",
            ],
            "pattern": r"\bwd\b",
            "default": 3500.0,
        },
        # --- 2. WASHING MACHINES ---
        {
            "id": "washing_machine",
            "name": "Washing Machine",
            "keywords": [
                "washing machine",
                "washer",
                "single tub",
                "twin tub",
                "spinner",
                "dryer",
                "hwm",
                "dwt",
                "w/m",
                "awm",
                "front load",
                "top load",
                "automatic",
                "fully automatic",
                "semi automatic",
                "semi-automatic",
                "semi auto",
                "semi-auto",
            ],
            "pattern": r"\bwm\b",
            "capacity_unit": "kg",
            "capacity_rules": DEFAULT_CAPACITY_RULES["kg"],
            "sub_types": [
                {
                    "name": "Single Tub Washer",
                    "keywords": ["single tub", "single-tub", "washer only"],
                    "brackets": [
                        {"max_kg": 8.5, "rate": 2500.0},
                        {"max_kg": 11.0, "rate": 3000.0},
                        {"max_kg": 999.0, "rate": 3500.0},
                    ],
                },
                {
                    "name": "Twin Tub Washer",
                    "keywords": [
                        "twin tub",
                        "twin-tub",
                        "twin",
                        "semi auto",
                        "semi-auto",
                        "semi automatic",
                        "semi-automatic",
                    ],
                    "brackets": [
                        {"max_kg": 8.5, "rate": 3000.0},
                        {"max_kg": 11.0, "rate": 3500.0},
                        {"max_kg": 13.5, "rate": 3800.0},
                        {"max_kg": 999.0, "rate": 4500.0},
                    ],
                },
                {
                    "name": "Automatic Washer",
                    "keywords": [
                        "automatic",
                        "front load",
                        "top load",
                        "inverter",
                        "fully automatic",
                    ],
                    "is_default": True,
                    "brackets": [
                        {"max_kg": 10.0, "rate": 3500.0},
                        {"max_kg": 999.0, "rate": 4500.0},
                    ],
                },
            ],
            "default": 3500.0,
        },
        # --- 3. MICROWAVE OVENS ---
        {
            "id": "microwave",
            "name": "Microwave Oven",
            "keywords": [
                "microwave",
                "microwave oven",
                "m/o",
                "mwo",
                "built-in m/oven",
                "baking oven",
                "mini oven",
            ],
            "capacity_unit": "l",
            "capacity_rules": DEFAULT_CAPACITY_RULES["l"],
            "sub_types": [
                {
                    "name": "Microwave Oven",
                    "is_default": True,
                    "brackets": [
                        {"max_l": 25.0, "rate": 1000.0},
                        {"max_l": 40.0, "rate": 2000.0},
                        {"max_l": 999.0, "rate": 2500.0},
                    ],
                },
            ],
            "default": 1500.0,
        },
        # --- 4. AIR FRYERS ---
        {
            "id": "air_fryer",
            "name": "Air Fryer",
            "keywords": [
                "air fryer",
                "airfryer",
                "air-fryer",
            ],
            "default": 2500.0,
        },
        # --- 5. AIR CONDITIONERS ---
        {
            "id": "air_conditioner",
            "name": "Air Conditioner",
            "keywords": [
                "split",
                "air conditioner",
                "inverter ac",
                "heat & cool",
                "ton",
                "aith",
                "hfn",
                "econo",
                "floor standing",
                "cassette",
            ],
            "pattern": r"\bac\b",
            "sub_types": [
                {
                    "name": "Air Conditioner (2.0 Ton)",
                    "pattern": r"\b(?:24|24000|2(?:\.0)?\s*ton)\b",
                    "rate": 4500.0,
                },
                {
                    "name": "Air Conditioner (1.5 Ton)",
                    "pattern": r"\b(?:18|18000|1\.5\s*ton)\b",
                    "rate": 3500.0,
                },
                {
                    "name": "Air Conditioner (1.0 Ton)",
                    "pattern": r"\b(?:12|12000|1(?:\.0)?\s*ton)\b",
                    "rate": 3000.0,
                },
            ],
            "default": 3500.0,
        },
        # --- 6. REFRIGERATORS & FREEZERS ---
        {
            "id": "refrigerator",
            "name": "Refrigerator",
            "keywords": [
                "refrigerator",
                "fridge",
                "freezer",
                "deep freezer",
                "hrf",
                "r/f",
                "d/f",
                "glass door",
                "vertical freezer",
                "minibar",
                "mini bar",
                "mini-bar",
                "cubic",
                "cuft",
                "cft",
            ],
            "pattern": r"\b(?:df|rf|ref)\b|\bcu\.?\s*ft\b",
            "capacity_unit": "cuft",
            "capacity_rules": DEFAULT_CAPACITY_RULES["cuft"],
            "sub_types": [
                {
                    "name": "Refrigerator (Small / Mini Bar)",
                    "keywords": ["mini bar", "mini-bar", "minibar", "small", "bedside"],
                    "rate": 4000.0,
                },
                {
                    "name": "Refrigerator (Large / Side-by-Side)",
                    "keywords": [
                        "side by side",
                        "4 door",
                        "four door",
                        "french door",
                        "large",
                        "500l",
                    ],
                    "rate": 13000.0,
                },
                {
                    "name": "Refrigerator / Deep Freezer",
                    "is_default": True,
                    "brackets": [
                        {"max_cuft": 5.5, "rate": 4000.0},
                        {"max_cuft": 8.5, "rate": 7000.0},
                        {"max_cuft": 12.0, "rate": 8500.0},
                        {"max_cuft": 16.0, "rate": 10000.0},
                        {"max_cuft": 20.0, "rate": 13000.0},
                    ],
                },
            ],
            "default": 4500.0,
        },
        # --- 7. LED TVs --- (evaluated after AC/Refrigerator/Washer/Air Fryer so "LED Display" on those appliances never hits LED TV)
        {
            "id": "led_tv",
            "name": "LED TV",
            "keywords": [
                "led tv",
                "smart tv",
                "google tv",
                "android tv",
                "uhd tv",
                "4k tv",
                "television",
            ],
            "pattern": r"\b(?:led|tv|qled|oled)\b|\b(?:24|32|39|40|42|43|48|49|50|55|58|60|65|70|75|85|98|100)\s*\"",
            # Insurance: % added on the COST (Net Price + Shipping), BEFORE commission and profit:
            #   cost = (net + shipping) * (1 + pct/100); price = (cost + profit) / (1 - commission)
            # So Total Without Profit, floors, final price and real profit all include it.
            # 0 / omitted = none.
            "insurance_pct": 2,
            "capacity_unit": "inch",
            "capacity_rules": DEFAULT_CAPACITY_RULES["inch"],
            "sub_types": [
                {
                    "name": "LED TV",
                    "is_default": True,
                    "brackets": [
                        {"max_inch": 45.0, "rate": 2500.0},
                        {"max_inch": 999.0, "rate": 3500.0},
                    ],
                },
            ],
            "default": 2500.0,
        },
        # ----------------------------------------------------------------------
        # HOW TO ADD NEW CATEGORIES (EXAMPLES):
        #
        # A. Flat Rate Category (e.g. Microwave Oven):
        # {
        #     "id": "microwave",
        #     "name": "Microwave Oven",
        #     "keywords": ["microwave", "oven", "mwo"],
        #     "default": 1500.0,
        # },
        #
        # B. Bracket/Size Category (e.g. LED TV):
        # {
        #     "id": "led_tv",
        #     "name": "LED TV",
        #     "keywords": ["led", "tv", "smart tv", "google tv"],
        #     "sub_types": [
        #         {"name": "LED TV (32-43 Inch)", "pattern": r"\b(?:32|40|42|43)\b", "rate": 2000.0},
        #         {"name": "LED TV (50-65 Inch)", "pattern": r"\b(?:50|55|65)\b", "rate": 3500.0},
        #         {"name": "LED TV (75+ Inch)", "pattern": r"\b(?:75|85|98)\b", "rate": 6000.0},
        #     ],
        #     "default": 2500.0,
        # },
        # ----------------------------------------------------------------------
    ],
    # Global fallback if product matches none of the categories above
    "default": 3000.0,
}


# ==============================================================================
# HELPER FUNCTIONS (DO NOT EDIT)
# ==============================================================================
_MISSING: object = object()

_VENDOR_COMMISSION_ATTRS: dict[str, tuple[str, str]] = {
    "alfa": ("ALFA_COMMISSION_PCT", "AlfaMall"),
    "digi": ("DIGI_COMMISSION_PCT", "DigiMall"),
}


def _validate_commission_pct(value: Any, vendor_label: str, attr_name: str) -> float:
    """Validate a configured vendor commission percentage, failing fast on invalid values."""
    if value is _MISSING:
        raise ValueError(f"{vendor_label} commission configuration '{attr_name}' is missing.")
    if value is None:
        raise ValueError(f"{vendor_label} commission configuration '{attr_name}' cannot be None.")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"{vendor_label} commission configuration '{attr_name}' must be numeric, "
            f"got {type(value).__name__}."
        )
    pct = float(value)
    if not math.isfinite(pct):
        raise ValueError(f"{vendor_label} commission configuration '{attr_name}' must be finite.")
    if pct < 0.0 or pct >= 100.0:
        raise ValueError(
            f"{vendor_label} commission configuration '{attr_name}' must be >= 0 and < 100, "
            f"got {pct}."
        )
    return 0.0 if pct == 0.0 else pct


def format_commission_pct(pct: float) -> str:
    """Format a validated commission percentage preserving >2-decimal precision cleanly."""
    clean_pct = 0.0 if pct == 0.0 else float(pct)
    if math.isclose(clean_pct, round(clean_pct, 2), rel_tol=0.0, abs_tol=1e-9):
        return f"{round(clean_pct, 2):.2f}%"
    return f"{round(clean_pct, 6):g}%"


def normalize_platform(platform: Any, *, allow_all: bool = True, default_blank_to_all: bool = False) -> str:
    """Validate and normalize target platform identifier cleanly."""
    if not isinstance(platform, str):
        raise ValueError(f"Unsupported platform: {platform!r}.")
    plat = platform.strip().lower()
    if not plat and default_blank_to_all:
        plat = "all"
    valid = {"all", "alfa", "digi"} if allow_all else {"alfa", "digi"}
    if plat not in valid:
        expected = ", ".join(sorted(valid))
        raise ValueError(f"Unsupported platform: '{platform}'. Expected one of: {expected}.")
    return plat


def get_vendor_commission_pct(platform: str) -> float:
    """Return validated commission percentage configured for the given vendor ('alfa' or 'digi')."""
    plat = normalize_platform(platform, allow_all=False)
    attr_name, vendor_label = _VENDOR_COMMISSION_ATTRS[plat]
    raw_value = globals().get(attr_name, _MISSING)
    return _validate_commission_pct(raw_value, vendor_label, attr_name)


def get_vendor_payout_rate(platform: str) -> float:
    """Return validated net payout multiplier (1 - commission/100) for 'alfa' or 'digi'."""
    return 1.0 - (get_vendor_commission_pct(platform) / 100.0)


def get_alfa_commission_pct() -> float:
    """Return validated AlfaMall commission percentage from configuration."""
    return get_vendor_commission_pct("alfa")


def get_digi_commission_pct() -> float:
    """Return validated DigiMall commission percentage from configuration."""
    return get_vendor_commission_pct("digi")


def get_alfa_payout_rate() -> float:
    """Return AlfaMall net payout multiplier (e.g. 0.90 for 10% commission)."""
    return get_vendor_payout_rate("alfa")


def get_digi_payout_rate() -> float:
    """Return DigiMall net payout multiplier (e.g. 0.92 for 8% commission)."""
    return get_vendor_payout_rate("digi")


# Storefront protocol settings; retrieval policies remain platform-specific.
ALFA_SEARCH_URL = "https://be.alfamall.com/storefront/search_products"


DIGI_SEARCH_URL = "https://digimall-be.faysalbank.com/storefront/search_products"


COMMON_HEADERS: dict[str, str] = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate, br, zstd",
    "content-type": "application/json",
    "sec-ch-ua": '"Google Chrome";v="120", "Chromium";v="120", "Not?A_Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


ALFAMALL_CONFIG = PlatformConfig(
    platform_name="alfamall",
    display_name="AlfaMall",
    search_url=ALFA_SEARCH_URL,
    base_params={
        "page": "1",
        "limit": "100",
        "storefront": "23",
        "storefront_domain": "alfamall.com",
    },
    headers={
        **COMMON_HEADERS,
        "origin": "https://alfamall.com",
        "referer": "https://alfamall.com/",
    },
)


DIGIMALL_CONFIG = PlatformConfig(
    platform_name="digimall",
    display_name="DigiMall",
    search_url=DIGI_SEARCH_URL,
    base_params={
        "storefront": "23",
        "page": "1",
        "limit": "100",
    },
    headers={
        **COMMON_HEADERS,
        "origin": "https://digimall.faysalbank.com",
        "referer": "https://digimall.faysalbank.com/",
    },
)


DIGI_PAGE_SIZE = 100
DIGI_MAX_PAGES = 3
DIGI_QUERY_BUDGET = 3
