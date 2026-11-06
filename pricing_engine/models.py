import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

STATUS_SERVER_DOWN: str = "Server Down / Unreachable"
STATUS_INCOMPLETE_DISCOVERY: str = "Incomplete Discovery"
STATUS_CANDIDATES_REJECTED: str = "Needs Review (Candidates Rejected)"

DISCOVERY_COMPLETE_WITH_OFFERS: str = "COMPLETE_WITH_OFFERS"
DISCOVERY_COMPLETE_NO_COMPETITORS: str = "COMPLETE_NO_COMPETITORS"
DISCOVERY_INCOMPLETE: str = "INCOMPLETE_DISCOVERY"
DISCOVERY_SEARCH_FAILED: str = "SEARCH_FAILED"
DISCOVERY_CANDIDATES_REJECTED: str = "CANDIDATES_REJECTED"
DISCOVERY_PAGINATION_INCOMPLETE: str = "PAGINATION_INCOMPLETE"

PROVISIONAL_COVERAGES: frozenset[str] = frozenset({"INCOMPLETE", "UNKNOWN", "CAPPED"})


def discovery_coverage_alert(coverage: str) -> str:
    """Map retrieval coverage to its reporting risk without changing profit math."""
    if coverage == "CAPPED":
        return "CAPPED_DISCOVERY"
    if coverage in {"INCOMPLETE", "UNKNOWN"}:
        return "INCOMPLETE_DISCOVERY"
    if coverage == "FAILED":
        return "SERVER_DOWN"
    return ""


INCOMPLETE_DISCOVERY_STATUSES: frozenset[str] = frozenset(
    {
        DISCOVERY_INCOMPLETE,
        DISCOVERY_SEARCH_FAILED,
        DISCOVERY_CANDIDATES_REJECTED,
        DISCOVERY_PAGINATION_INCOMPLETE,
    }
)

WINNING_5PCT_GOALS: frozenset[str] = frozenset({"WIN + 5% ACHIEVED", "SOLO (5% COVERED)"})

COMPATIBILITY_NOTICE_MARKERS: tuple[str, ...] = (
    "fallback model",
    "sibling sub-model fallback",
    "optional specification",
    "cross-check notice",
    "compatibility notice",
)


def has_compatibility_or_fallback_notice(text: Any) -> bool:
    """Return True if a reason or notice string contains any compatibility or fallback marker."""
    if text is None:
        return False
    low = str(text).lower()
    return any(marker in low for marker in COMPATIBILITY_NOTICE_MARKERS)


def format_comm_pct_label(personal_comm_pct: float = 5.0) -> str:
    """Format personal commission percentage for dynamic column headers and badges (e.g. '5', '8', '3.5')."""
    eff_pct = personal_comm_pct if personal_comm_pct > 0 else 5.0
    return f"{eff_pct:g}"


def get_winning_comm_goals(personal_comm_pct: float = 5.0) -> frozenset[str]:
    """Return winning goal badge strings for a given personal commission percentage."""
    lbl = format_comm_pct_label(personal_comm_pct)
    return frozenset({f"WIN + {lbl}% ACHIEVED", f"SOLO ({lbl}% COVERED)"})


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
    detected_variant: str | None = None
    missing_modifier: str | None = None
    modifier_source: str = "target"
    product_handle: str | None = None
    scraped_model: str | None = None
    color_family: str | None = None
    match_tier: int | None = None
    compatibility_notice: str | None = None


@dataclass(frozen=True, slots=True)
class AmbiguousVariantConflict:
    """Represents a conflict where an un-suffixed base model matches multiple distinct marketplace variants."""

    stem_model: str
    detected_variants: list[str] = field(default_factory=list)
    variant_offers: dict[str, list[ScrapedOffer]] = field(default_factory=dict)


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
    active_modifier_source: str = "target"
    base_offers: list[ScrapedOffer] = field(default_factory=list)
    sibling_offers: list[ScrapedOffer] = field(default_factory=list)
    own_offers: list[ScrapedOffer] = field(default_factory=list)
    ambiguity_conflict: AmbiguousVariantConflict | None = None
    discovery_status: str = ""
    raw_candidate_count: int = 0
    rejected_count: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    suspicious_rejected_count: int = 0
    pages_fetched: int = 1
    total_available: int | None = None
    pagination_complete: bool = True
    extended_model_designation: str | None = None
    compatibility_notice: str | None = None
    coverage_status: str = ""
    coverage_detail: str = ""
    query_audit: list[dict[str, Any]] = field(default_factory=list)
    lowest_offers: list[ScrapedOffer] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.discovery_status:
            if not self.is_success:
                object.__setattr__(self, "discovery_status", DISCOVERY_SEARCH_FAILED)
            elif self.offers or self.base_offers or self.sibling_offers:
                object.__setattr__(self, "discovery_status", DISCOVERY_COMPLETE_WITH_OFFERS)
            elif not self.pagination_complete:
                object.__setattr__(self, "discovery_status", DISCOVERY_PAGINATION_INCOMPLETE)
            else:
                object.__setattr__(self, "discovery_status", DISCOVERY_COMPLETE_NO_COMPETITORS)

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
    coverage_status: str = ""
    coverage_detail: str = ""


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
    discovery_status: str = ""
    compatibility_notice: str | None = None
    coverage_status: str = ""
    coverage_detail: str = ""


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


@dataclass
class CheckpointState:
    """Persistent run state for resuming partial or interrupted catalog runs."""

    catalog_name: str
    catalog_path: str
    catalog_mtime: float
    total_items: int
    completed_records: dict[int, dict[str, Any]] = field(default_factory=dict)
    row_fingerprints: dict[int, str] = field(default_factory=dict)
    pending_indices: list[int] = field(default_factory=list)
    pending_reasons: dict[int, str] = field(default_factory=dict)
    updated_at: str = ""
