"""Shared pytest fixtures and dynamic configuration helper utilities.

Provides centralized helpers so all test files dynamically query active application
settings from config.py rather than duplicating hardcoded rates, fees, or thresholds.
"""

from __future__ import annotations

from typing import Any

import pytest

import config
from pricing_engine.calculator import calculate_floors
from pricing_engine.models import CostFloors


@pytest.fixture
def app_config():
    """Fixture providing active configuration module."""
    return config


@pytest.fixture
def sample_floors() -> CostFloors:
    """Standard baseline floors for cost_base=72,000 PKR computed dynamically from active config."""
    return calculate_floors(cost_base=72000.0)


# ==============================================================================
# DYNAMIC CATEGORY SHIPPING CONFIGURATION QUERY HELPERS
# ==============================================================================


def get_configured_ac_rate(ton_label: str) -> float:
    """Extract configured rate for Air Conditioner sub-type from config.DEFAULT_CATEGORY_SHIPPING.

    Args:
        ton_label: Sub-type capacity identifier, e.g. "1.0 Ton", "1.5 Ton", "2.0 Ton", or "Air Conditioner".

    Returns:
        Configured float shipping rate in PKR.
    """
    categories = config.DEFAULT_CATEGORY_SHIPPING.get("categories", [])
    ac_cat = next((c for c in categories if c.get("id") == "air_conditioner"), None)
    if not ac_cat:
        return float(config.DEFAULT_CATEGORY_SHIPPING.get("default", 3000.0))

    # If asking for category-level default (e.g. "Air Conditioner" with no ton specified)
    if ton_label.strip().lower() in ("air conditioner", "ac", "default"):
        return float(ac_cat.get("default", 3500.0))

    for sub in ac_cat.get("sub_types", []):
        sub_name = sub.get("name", "").lower()
        # Check specific ton patterns, e.g. "1.0 ton", "1.5 ton", "2.0 ton"
        if ton_label.lower() in sub_name:
            return float(sub["rate"])

    return float(ac_cat.get("default", 3500.0))


def get_configured_washer_rate(sub_type_name: str, capacity_kg: float) -> float:
    """Extract configured rate for Washing Machine sub-type & capacity bracket.

    Args:
        sub_type_name: Washer sub-type name ("Single Tub", "Twin Tub", "Automatic").
        capacity_kg: Capacity in KG.

    Returns:
        Configured float shipping rate in PKR.
    """
    categories = config.DEFAULT_CATEGORY_SHIPPING.get("categories", [])
    wm_cat = next((c for c in categories if c.get("id") == "washing_machine"), None)
    if not wm_cat:
        return float(config.DEFAULT_CATEGORY_SHIPPING.get("default", 3000.0))

    sub_types = wm_cat.get("sub_types", [])
    matched_sub: dict[str, Any] | None = None
    default_sub: dict[str, Any] | None = None

    for sub in sub_types:
        if sub.get("is_default"):
            default_sub = sub
        if sub_type_name.lower() in sub.get("name", "").lower():
            matched_sub = sub
            break

    target_sub = matched_sub or default_sub
    if not target_sub:
        return float(wm_cat.get("default", 3500.0))

    if "rate" in target_sub:
        return float(target_sub["rate"])

    brackets = target_sub.get("brackets", [])
    for b in brackets:
        max_kg = b.get("max_kg", b.get("max", 999.0))
        if capacity_kg <= max_kg:
            return float(b.get("rate", wm_cat.get("default", 3500.0)))

    return float(target_sub.get("default", wm_cat.get("default", 3500.0)))


def get_configured_refrigerator_rate(sub_type_name: str) -> float:
    """Extract configured rate for Refrigerator sub-type.

    Args:
        sub_type_name: e.g. "Small / Mini Bar", "Large / Side-by-Side", or general "Refrigerator".

    Returns:
        Configured float shipping rate in PKR.
    """
    categories = config.DEFAULT_CATEGORY_SHIPPING.get("categories", [])
    rf_cat = next((c for c in categories if c.get("id") == "refrigerator"), None)
    if not rf_cat:
        return float(config.DEFAULT_CATEGORY_SHIPPING.get("default", 3000.0))

    # If asking for category-level default (e.g. standard "Refrigerator")
    if sub_type_name.strip().lower() in ("refrigerator", "fridge", "default"):
        return float(rf_cat.get("default", 5500.0))

    for sub in rf_cat.get("sub_types", []):
        sub_name = sub.get("name", "").lower()
        if sub_type_name.lower() in sub_name:
            return float(sub["rate"])

    return float(rf_cat.get("default", 5500.0))


def get_configured_global_shipping_default() -> float:
    """Return global fallback shipping default from active config."""
    return float(config.DEFAULT_CATEGORY_SHIPPING.get("default", 3000.0))


def get_configured_category_default(category_id: str) -> float:
    """Return default rate for a given category id from active config."""
    categories = config.DEFAULT_CATEGORY_SHIPPING.get("categories", [])
    cat = next((c for c in categories if c.get("id") == category_id), None)
    if cat and "default" in cat:
        return float(cat["default"])
    return get_configured_global_shipping_default()
