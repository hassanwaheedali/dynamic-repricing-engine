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
    "CFT": r"(?:CU\.?\s*FT\.?|CFT|CUBIC(?:\s*(?:FEET|FOOT|FT))?)",
    "L": r"(?:LTRS?|LITRES?|LITERS?|L)",
    "TAP": r"(?:TAPS?|FAUCETS?)",
}
# Prose matching excludes bare 'IN' and quote marks ('', ', ") so English prepositions
# ('2 in Black') and quoted model names ("'Icon 2'") never corrupt screen-size extraction;
# valid screen quotes (32", 32”) are canonicalised upfront by normalize_screen_units.
PROSE_UNIT_PATTERNS: dict[CapacityUnit, str] = {
    **UNIT_PATTERNS,
    "INCH": r"(?:INCH(?:ES)?)",
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


def parse_amount(value: object) -> Decimal | None:
    """Normalize numeric evidence without binary floating point or nonfinite values."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return amount if amount.is_finite() else None


RANGE_SEPARATOR_PATTERN = r"[-\u2013\u2014/]"
_RANGE_LOWER_BOUND_RE = re.compile(
    rf"(?<![A-Za-z0-9\-\u2013\u2014_/])(\d+(?:\.\d+)?)\s*{RANGE_SEPARATOR_PATTERN}\s*$"
)
_RANGE_UPPER_BOUND_RE = re.compile(r"\d+(?:\.\d+)?")
VALID_TAP_COUNTS: frozenset[Decimal] = frozenset(
    {Decimal(1), Decimal(2), Decimal(3), Decimal(4)}
)


def is_numeric_range_continuation(text: str, match_start: int) -> bool:
    """Return True when a unit match sits on the right side of an ascending numeric range.

    Both unspaced ('2-3 Taps', '2.5-3 Taps', '2/3 Taps') and spaced ('2 - 3 Taps') pairs must
    be strictly ascending (lower < upper) so descending '<model>-<capacity>' tokens
    ('9173-12CFT', '120-10KG') and clause separators ('DW 120 - 10 KG') are never misclassified
    as measurement ranges.
    """
    lower = _RANGE_LOWER_BOUND_RE.search(text[:match_start])
    if lower is None:
        return False
    upper = _RANGE_UPPER_BOUND_RE.match(text, match_start)
    if upper is None:
        return False
    low_amount, high_amount = parse_amount(lower.group(1)), parse_amount(upper.group(0))
    return low_amount is not None and high_amount is not None and low_amount < high_amount


def _unbounded_capacity_pattern(unit_pattern: str) -> str:
    return rf"(?i:(\d+(?:\.\d+)?)\s*[-]?\s*{unit_pattern}(?!\w))"


def _bounded_capacity_pattern(unit_pattern: str) -> str:
    return rf"(?i:(?<![\w./])(\d+(?:\.\d+)?)\s*[-]?\s*{unit_pattern}(?!\w))"


def explicit_capacity_pattern(unit: CapacityUnit) -> str:
    """Configured extraction pattern; inference and scaling stay with the caller."""
    return _bounded_capacity_pattern(UNIT_PATTERNS[unit])


def prose_capacity_pattern(unit: CapacityUnit) -> str:
    """Prose-safe extraction pattern excluding preposition/quote tokens normalized upstream."""
    return _bounded_capacity_pattern(PROSE_UNIT_PATTERNS[unit])


CAPACITY_MEASUREMENT_PATTERN = "|".join(prose_capacity_pattern(unit) for unit in UNIT_PATTERNS)
UNBOUNDED_CAPACITY_MEASUREMENT_PATTERN = "|".join(
    _unbounded_capacity_pattern(PROSE_UNIT_PATTERNS[unit]) for unit in UNIT_PATTERNS
)
UNBOUNDED_TAP_PATTERN = _unbounded_capacity_pattern(PROSE_UNIT_PATTERNS["TAP"])
SPEC_ONLY_UNIT_PATTERN = r"(?:FEET|FT|MM|CM|GM|SETS?|WATTS?|W|VOLTS?|V|AMPS?|HZ|BTU|RPM|GALLONS?|GAL)"
NON_TAP_MEASUREMENT_UNIT_PATTERN = "|".join(
    [
        *(pattern for unit, pattern in PROSE_UNIT_PATTERNS.items() if unit != "TAP"),
        SPEC_ONLY_UNIT_PATTERN,
    ]
)
TOKEN_MEASUREMENT_UNIT_PATTERN = "|".join(
    [
        r"(?:TONS?|ΤΟ[NΝ])",
        PROSE_UNIT_PATTERNS["INCH"],
        PROSE_UNIT_PATTERNS["KG"],
        PROSE_UNIT_PATTERNS["CFT"],
        PROSE_UNIT_PATTERNS["L"],
        PROSE_UNIT_PATTERNS["TAP"],
        SPEC_ONLY_UNIT_PATTERN,
    ]
)


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
            amount = parse_amount(match[1])
            return Capacity(amount, unit) if amount is not None and amount > 0 else None
    return None


def find_capacity(text: str, unit: CapacityUnit) -> Capacity | None:
    """Read an explicit bounded measurement; caller owns category/SKU context."""
    for match in re.finditer(prose_capacity_pattern(unit), text):
        if is_numeric_range_continuation(text, match.start()):
            continue
        return parse_capacity(match[0])
    return None
