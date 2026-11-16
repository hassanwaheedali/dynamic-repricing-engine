"""Ambiguous unit letters cannot erase structurally supported model digits."""

import pytest

from pricing_engine.matcher import (
    extract_product_slots,
    extract_search_query_and_model,
    referee_match,
)


@pytest.mark.parametrize(
    "brand,prefix,number",
    [("Dawlance", "DWAF", "6321"), ("Acme", "AXAF", "7423"), ("Novus", "NVAF", "8534")],
)
@pytest.mark.parametrize("separator", [" ", "-"])
def test_model_suffix_l_survives_measurement_removal(
    brand: str, prefix: str, number: str, separator: str
) -> None:
    title = f"{brand} {prefix}{separator}{number}{separator}L XL 5.5 L Manual Air Fryer"
    _, model = extract_search_query_and_model(title, brand)
    slots = extract_product_slots(title, brand)
    assert number in model and number in slots.anchor
    assert "5.5" not in model and "5.5" not in slots.anchor
    decision = referee_match(title, f"{brand} {prefix}-{number}L 5.5 L Air Fryer", brand)
    assert decision.is_match or decision.is_base_match, decision.reason
