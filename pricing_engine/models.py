import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

STATUS_SERVER_DOWN: str = "Server Down / Unreachable"
WINNING_5PCT_GOALS: frozenset[str] = frozenset({"WIN + 5% ACHIEVED", "SOLO (5% COVERED)"})

# List of vendor names/handles excluded from competitor pricing and market discovery
# (e.g. brand-owned official flagship stores or own merchant stores that shouldn't be competed against)
NON_COMPETITOR_VENDORS: set[str] = {
    "haier-official-store",
    "haier official store",
    "haierofficialstore",
    "kiachahye",
    "kia chahye",
    "kia-chahye",
    "kiachahye.com",
    "kiachahiye",
    "kia chahiye",
    "kia-chahiye",
    "kiachahiye.com",
    "kia chahiye pvt ltd",
    "kia-chahiye-pvt-ltd",
    "ajmer",
    "ajmer electronics",
    "ajmer-electronics",
    "ajmerelectronics",
}


def classify_non_competitor_vendor(vendor_name: str | None) -> str | None:
    """Classify a vendor into 'OWN_STORE', 'OFFICIAL_STORE', or None if external competitor."""
    if not vendor_name:
        return None
    norm = re.sub(r"[^a-z0-9]", "", str(vendor_name).lower())
    if any(norm.startswith(k) for k in ("kiachah", "ajmer")):
        return "OWN_STORE"
    if any(norm.startswith(k) for k in ("haierofficial", "haierflagship")):
        return "OFFICIAL_STORE"
    for excluded in NON_COMPETITOR_VENDORS:
        if norm == re.sub(r"[^a-z0-9]", "", excluded.lower()):
            if "haier" in norm:
                return "OFFICIAL_STORE"
            return "OWN_STORE"
    return None


def is_non_competitor_vendor(vendor_name: str | None) -> bool:
    """Check if a vendor should be excluded from competitive repricing and market discovery."""
    return classify_non_competitor_vendor(vendor_name) is not None



@dataclass(frozen=True, slots=True)
class CostFloors:
    """Represents calculated margin thresholds and hard floors for a product."""

    cost_base: float
    zero_margin_10: float
    zero_margin_8: float
    floor_alfa: float
    floor_digi_10: float
    floor_digi_8: float
    personal_comm: int = 0
    alfa_personal_comm: int = 0
    digi_personal_comm: int = 0

    def __post_init__(self) -> None:
        if self.alfa_personal_comm == 0 and self.personal_comm > 0:
            object.__setattr__(self, "alfa_personal_comm", self.personal_comm)
        if self.digi_personal_comm == 0 and self.personal_comm > 0:
            object.__setattr__(self, "digi_personal_comm", self.personal_comm)


@dataclass(frozen=True, slots=True)
class ScrapedOffer:
    """A single competitor product offering scraped from AlfaMall or DigiMall."""

    vendor_name: str
    price: float
    is_sold_out: bool
    raw_title: str
    duplicate_count: int = 1



@dataclass(frozen=True, slots=True)
class ScrapeResult:
    """Rich scrape result contract explicitly distinguishing healthy scrape from server errors."""

    offers: list[ScrapedOffer] = field(default_factory=list)
    is_success: bool = True
    status_code: int | None = 200
    error_detail: str | None = None
    executed_queries: list[str] = field(default_factory=list)
    matched_tier: str | None = None
    tier_summary: dict[str, int] = field(default_factory=dict)
    active_modifier_fallback: str | None = None
    base_offers: list[ScrapedOffer] = field(default_factory=list)
    own_offers: list[ScrapedOffer] = field(default_factory=list)

    def __iter__(self) -> Iterator[ScrapedOffer]:
        return iter(self.offers)

    def __len__(self) -> int:
        return len(self.offers)

    def __getitem__(self, index: int) -> ScrapedOffer:
        return self.offers[index]


@dataclass(frozen=True, slots=True)
class MarketRange:
    """Market min/max of in-stock offers on one platform (no floors, no pricing decision)."""

    min_price: float | None
    max_price: float | None
    offer_count: int
    is_down: bool = False
    error_detail: str | None = None


@dataclass(frozen=True, slots=True)
class PlatformPricingResult:
    """Evaluation result and pricing decision for a single platform."""

    min_price: float | None
    max_price: float | None
    final_price: int | None
    real_profit: int | None = None
    status: str = ""
    reason: str = ""
    dropped: list[str] = field(default_factory=list)
    active_pool: list[str] = field(default_factory=list)
    effective_comm: str = "10.00%"
    own_offers: list[ScrapedOffer] = field(default_factory=list)


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
