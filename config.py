"""Centralized Configuration for AlfaMall & DigiMall Dynamic Repricing Engine.

Edit the values below to customize marketplace bank commissions, personal
commission percentages (global or per-platform), profit floors, and courier
shipping rates from a single file.
"""

from __future__ import annotations

from typing import Any

# ==============================================================================
# 1. PLATFORM BANK COMMISSIONS (%)
# ==============================================================================
# AlfaMall standard marketplace commission percentage (Default: 10.0%)
ALFA_COMMISSION_PCT: float = 10.0

# DigiMall standard marketplace commission tier (Default: 10.0%)
DIGI_STANDARD_COMMISSION_PCT: float = 10.0

# DigiMall Faysal Bank special leverage commission tier (Default: 8.0%)
DIGI_LEVERAGE_COMMISSION_PCT: float = 8.0


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
# Fully data-driven: add any new category or edit brackets directly here without
# touching engine code!
# ==============================================================================
DEFAULT_CATEGORY_SHIPPING: dict[str, Any] = {
    # --------------------------------------------------------------------------
    # CATEGORIES LIST (Top-to-bottom evaluation order)
    # --------------------------------------------------------------------------
    "categories": [
        # --- 1. WASHING MACHINES ---
        {
            "id": "washing_machine",
            "name": "Washing Machine",
            "keywords": [
                "washing machine", "washer", "single tub", "twin tub",
                "spinner", "dryer", "hwm", "dwt", "wm", "front load", "top load",
                "automatic", "fully automatic", "semi automatic", "semi-automatic", "semi auto", "semi-auto",
            ],
            "capacity_unit": "kg",
            "sub_types": [
                {
                    "name": "Twin Tub Washer",
                    "keywords": [
                        "twin tub", "twin-tub", "twin", "semi auto",
                        "semi-auto", "semi automatic", "semi-automatic",
                    ],
                    "brackets": [
                        {"max_kg": 8.5, "rate": 3000.0},
                        {"max_kg": 11.0, "rate": 3500.0},
                        {"max_kg": 13.5, "rate": 3800.0},
                        {"max_kg": 999.0, "rate": 4500.0},
                    ],
                },
                {
                    "name": "Single Tub Washer",
                    "keywords": ["single tub", "single-tub", "single", "washer only"],
                    "brackets": [
                        {"max_kg": 8.5, "rate": 2500.0},
                        {"max_kg": 11.0, "rate": 3000.0},
                        {"max_kg": 999.0, "rate": 3500.0},
                    ],
                },
                {
                    "name": "Automatic Washer",
                    "keywords": ["automatic", "front load", "top load", "inverter", "fully automatic"],
                    "is_default": True,
                    "brackets": [
                        {"max_kg": 10.0, "rate": 3500.0},
                        {"max_kg": 999.0, "rate": 4500.0},
                    ],
                },
            ],
            "default": 3500.0,
        },
        # --- 2. AIR CONDITIONERS ---
        {
            "id": "air_conditioner",
            "name": "Air Conditioner",
            "keywords": ["split", "ac", "air conditioner", "inverter ac", "heat & cool", "ton", "aith", "hfn", "econo"],
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
        # --- 3. REFRIGERATORS & FREEZERS ---
        {
            "id": "refrigerator",
            "name": "Refrigerator",
            "keywords": ["refrigerator", "fridge", "freezer", "deep freezer", "hrf", "df", "glass door", "vertical freezer"],
            "sub_types": [
                {
                    "name": "Refrigerator (Small / Mini Bar)",
                    "keywords": ["mini bar", "mini-bar", "small", "single door", "bedside"],
                    "rate": 4000.0,
                },
                {
                    "name": "Refrigerator (Large / Side-by-Side)",
                    "keywords": ["side by side", "4 door", "four door", "french door", "large", "500l"],
                    "rate": 7500.0,
                },
            ],
            "default": 5500.0,
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
def get_alfa_payout_rate() -> float:
    """Return AlfaMall net payout multiplier (e.g. 0.90 for 10% commission)."""
    return 1.0 - (ALFA_COMMISSION_PCT / 100.0)


def get_digi_standard_payout_rate() -> float:
    """Return DigiMall standard tier payout multiplier (e.g. 0.90 for 10% commission)."""
    return 1.0 - (DIGI_STANDARD_COMMISSION_PCT / 100.0)


def get_digi_leverage_payout_rate() -> float:
    """Return DigiMall Faysal Bank tier payout multiplier (e.g. 0.92 for 8% commission)."""
    return 1.0 - (DIGI_LEVERAGE_COMMISSION_PCT / 100.0)
