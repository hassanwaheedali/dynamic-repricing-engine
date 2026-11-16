"""Exact capacity values and shared unit vocabulary; no product inference policy."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

CapacityUnit = Literal["T", "INCH", "KG", "CFT", "L", "TAP"]

# Unit spellings are domain vocabulary, not product/category exceptions.
UNIT_PATTERNS: dict[CapacityUnit, str] = {
    "T": r"(?:TONS?|ΤΟ[NΝ]|T)",
    "INCH": r"(?:INCH(?:ES)?|IN|\"|''|')",
    "KG": r"(?:KGS?|K\.G|KILOS?)",
    "CFT": r"(?:CU\.?\s*FT\.?|CFT|CUBIC\s*(?:FEET|FOOT|FT))",
    "L": r"(?:LTRS?|LITRES?|LITERS?|L)",
    "TAP": r"(?:TAPS?|FAUCETS?)",
}
QUERY_UNITS: dict[CapacityUnit, str] = {
    "T": "Ton",
    "INCH": "Inch",
    "KG": "KG",
    "CFT": "CFT",
    "L": "L",
    "TAP": "Tap",
}


def format_amount(amount: Decimal) -> str:
    """Format without exponent or context-dependent Decimal rounding."""
    value = format(amount, "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


@dataclass(frozen=True)
class Capacity:
    """Comparable exact amount plus dimension; no implicit cross-unit conversion."""

    amount: Decimal
    unit: CapacityUnit

    def __str__(self) -> str:
        return f"{format_amount(self.amount)}{self.unit}"

    def query_text(self) -> str:
        return f"{format_amount(self.amount)} {QUERY_UNITS[self.unit]}"


def parse_capacity(value: str | None) -> Capacity | None:
    """Parse one complete positive capacity, rejecting unknown units and prose."""
    for unit, pattern in UNIT_PATTERNS.items():
        match = re.fullmatch(rf"\s*(\d+(?:\.\d+)?)\s*[-]?\s*{pattern}\s*", value or "", re.I)
        if match:
            try:
                amount = Decimal(match[1])
            except InvalidOperation:
                return None
            return Capacity(amount, unit) if amount > 0 else None
    return None


def find_capacity(text: str, unit: CapacityUnit) -> Capacity | None:
    """Read an explicit bounded measurement; caller owns category/SKU context."""
    pattern = rf"(?<![\w./])(\d+(?:\.\d+)?)\s*[-]?\s*{UNIT_PATTERNS[unit]}(?!\w)"
    match = re.search(pattern, text, re.I)
    return parse_capacity(match[0]) if match else None
