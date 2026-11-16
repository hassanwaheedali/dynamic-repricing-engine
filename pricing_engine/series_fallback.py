"""Explicit, last-resort brand/series/capacity matching shared by both stores."""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from pricing_engine.capacity import parse_capacity
from pricing_engine.matcher import (
    MatchDecision,
    ProductSlots,
    extract_product_slots,
    normalize_series_tokens,
    referee_series_candidate,
)
from pricing_engine.models import ScrapedOffer


def has_active_model_offers(*pools: Iterable[ScrapedOffer]) -> bool:
    """Any compatible in-stock model, including own stores, suppresses widening."""
    return any(
        not offer.is_sold_out and offer.match_basis == "model" for pool in pools for offer in pool
    )


@dataclass(frozen=True)
class SeriesSearch:
    """Catalog-supplied named series and capacity; never inferred from a brand list."""

    query: str
    series: str
    target: ProductSlots


def build_series_search(description: str, brand: str) -> SeriesSearch | None:
    """Build one bounded query only when the catalog explicitly identifies a series."""
    if not brand.strip() or not re.search(r"\bSERIES\b", description, re.IGNORECASE):
        return None
    slots = extract_product_slots(description, brand)
    capacity = parse_capacity(slots.guarded_facets.capacity)
    words = normalize_series_tokens(slots.series)
    if not capacity or not words or len(words) > 4 or any(re.search(r"\d", word) for word in words):
        return None
    query = f"{brand.strip()} {slots.series} {capacity.query_text()}"
    return SeriesSearch(query, slots.series, slots)


def referee_series_match(description: str | SeriesSearch, title: str, brand: str) -> MatchDecision:
    """Relax model identity only; retain the shared explicit physical-attribute guards."""
    search = (
        description
        if isinstance(description, SeriesSearch)
        else build_series_search(description, brand)
    )
    if search is None:
        return MatchDecision(
            False,
            "Series fallback requires explicit catalog series and product brand",
            reason_code="MISSING_IDENTITY",
            match_basis="series",
        )
    return referee_series_candidate(search.target, title, brand)
