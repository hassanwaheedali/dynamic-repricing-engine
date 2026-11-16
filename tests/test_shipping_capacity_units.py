"""Shipping consumes canonical unit vocabulary but retains its own inference policy."""

import pytest

from pricing_engine.calculator import resolve_fallback_shipping
from tests.conftest import get_configured_washer_rate


@pytest.mark.parametrize("unit", ["KG", "KGS", "KILO", "KILOS", "K.G"])
def test_washer_shipping_supports_shared_unit_aliases(unit: str) -> None:
    amount, _ = resolve_fallback_shipping(f"Acme Twin Tub Washing Machine 8 {unit}", "Acme")
    assert amount == get_configured_washer_rate("Twin Tub", 8)
