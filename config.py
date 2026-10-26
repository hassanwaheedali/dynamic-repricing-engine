"""Centralized Configuration for AlfaMall & DigiMall Dynamic Repricing Engine.

Edit the values below to customize marketplace bank commissions, personal
commission percentages (global or per-platform), profit floors, and courier
shipping rates from a single file.
"""

from __future__ import annotations

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
