from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CostFloors:
    """Represents calculated margin thresholds and hard floors for a product."""

    cost_base: float
    zero_margin_10: float
    zero_margin_8: float
    floor_alfa: float
    floor_digi_10: float
    floor_digi_8: float


@dataclass(frozen=True, slots=True)
class ScrapedOffer:
    """A single competitor product offering scraped from AlfaMall or DigiMall."""

    vendor_name: str
    price: float
    is_sold_out: bool
    raw_title: str


@dataclass(frozen=True, slots=True)
class PlatformPricingResult:
    """Evaluation result and pricing decision for a single platform."""

    min_price: float | None
    max_price: float | None
    final_price: int | None
    real_profit: int
    status: str
    reason: str
    dropped: list[str] = field(default_factory=list)
    active_pool: list[str] = field(default_factory=list)
    effective_comm: str = "10.00%"


@dataclass(frozen=True, slots=True)
class ProductInput:
    """Standardized input product item read from CSV."""

    sno: int | str
    brand: str
    name: str
    length: float
    width: float
    height: float
    net_price: float
    profit: float
    raw_row: dict[str, Any] = field(default_factory=dict)
