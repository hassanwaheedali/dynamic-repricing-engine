"""Exact capacity semantics, independent of platform and configurable prices."""

import pytest

from pricing_engine.capacity import parse_capacity
from pricing_engine.matcher import extract_product_slots, referee_match


@pytest.mark.parametrize(
    "left,right",
    [("1T", "1.0T"), ("8.5CFT", "8.50 CU FT"), ("100 Inch", "100INCH"), ("8 KG", "8 KGS")],
)
def test_capacity_aliases_equal_without_unit_conversion(left: str, right: str) -> None:
    assert parse_capacity(left) is not None
    assert parse_capacity(left) == parse_capacity(right)


@pytest.mark.parametrize(
    "text", [None, "", "0 KG", "-1 Ton", "NaN KG", "8 XYZ", "AX-800", "8 KG extra"]
)
def test_invalid_capacity_does_not_invent_a_value(text: str | None) -> None:
    assert parse_capacity(text) is None


@pytest.mark.parametrize(
    "left,right", [("1 Ton", "1.0 Ton"), ("1T", "1.0 Ton"), ("8.5 CFT", "8.50 CU FT")]
)
def test_equal_explicit_capacity_keeps_normal_match(left: str, right: str) -> None:
    decision = referee_match(f"Acme AX-900 {left}", f"Acme AX-900 {right}", "Acme")
    assert decision.is_match, decision.reason


@pytest.mark.parametrize("brand,prefix", [("Acme", "AX"), ("Novus", "NV")])
@pytest.mark.parametrize(
    "left,right", [("8 CFT", "8.5 CFT"), ("1 Ton", "1.25 Ton"), ("100 Inch", "98 Inch")]
)
def test_explicit_different_capacities_reject(
    brand: str, prefix: str, left: str, right: str
) -> None:
    family = (
        "Refrigerator" if "CFT" in left else "QLED TV" if "Inch" in left else "Inverter Split AC"
    )
    model = "14HFT" if "Ton" in left else f"{prefix}-900"
    decision = referee_match(
        f"{brand} {model} {left} {family}", f"{brand} {model} {right} {family}", brand
    )
    assert not (decision.is_match or decision.is_base_match or decision.match_tier == 3)
    assert decision.reason_code == "FACET_CONFLICT"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("8.5 CFT Refrigerator", "8.5CFT"),
        ("100 Inch QLED TV", "100INCH"),
        ("1.0 Ton Split AC", "1T"),
        ("1T Split AC", "1T"),
        ("8 KGS Washer", "8KG"),
    ],
)
def test_explicit_capacity_is_canonical(text: str, expected: str) -> None:
    assert extract_product_slots(f"Acme AX-900 {text}", "Acme").guarded_facets.capacity == expected
