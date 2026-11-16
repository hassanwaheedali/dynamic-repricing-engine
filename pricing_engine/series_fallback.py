"""Explicit, last-resort brand/series/capacity matching shared by both stores."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace

from pricing_engine.capacity import parse_capacity
from pricing_engine.matcher import (
    MatchDecision,
    ProductSlots,
    _tokenize_series_words,
    extract_product_slots,
    referee_match,
)
from pricing_engine.models import ScrapedOffer


def has_active_model_offers(*pools: Iterable[ScrapedOffer]) -> bool:
    """Any compatible in-stock model, including own stores, suppresses widening."""
    return any(not offer.is_sold_out for pool in pools for offer in pool)


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
    words = _tokenize_series_words(slots.series)
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
    candidate = extract_product_slots(title, brand)
    if search is None or not re.match(
        rf"^\s*{re.escape(brand.strip())}\b", candidate.normalized_title, re.IGNORECASE
    ):
        return MatchDecision(
            False,
            "Series fallback requires explicit catalog series and product brand",
            reason_code="MISSING_IDENTITY",
        )
    if not _tokenize_series_words(search.series).issubset(_tokenize_series_words(candidate.series)):
        return MatchDecision(
            False,
            "Series fallback requires the complete named series",
            search.target,
            candidate,
            reason_code="SERIES_CONFLICT",
        )
    if parse_capacity(search.target.guarded_facets.capacity) != parse_capacity(
        candidate.guarded_facets.capacity
    ):
        return MatchDecision(
            False,
            "Series fallback requires verified matching capacity",
            search.target,
            candidate,
            reason_code="FACET_CONFLICT",
        )
    # Reuse the referee for physical evidence, but substitute only model identity.
    # The original normalized title is retained for category and mounting guards.
    target = replace(
        search.target,
        anchor=candidate.anchor,
        base_stem=candidate.base_stem,
        sub_model_tag=candidate.sub_model_tag,
        guarded_facets=replace(
            search.target.guarded_facets, capacity=candidate.guarded_facets.capacity
        ),
    )
    decision = referee_match(target, title, brand)
    if not (decision.is_match or decision.is_base_match or decision.match_tier == 3):
        return decision
    notice = (
        f"[FALLBACK MODEL: Series '{search.series}' / {search.target.guarded_facets.capacity}; "
        f"catalog model '{search.target.anchor}' not verified; market model '{candidate.anchor or 'not stated'}']"
    )
    if decision.compatibility_notice:
        notice += " " + decision.compatibility_notice
    return replace(
        decision,
        is_match=False,
        is_base_match=True,
        match_tier=2,
        reason_code="BASE_MATCH",
        missing_modifier=f"Series {search.series} {search.target.guarded_facets.capacity}",
        modifier_source="market",
        detected_variant=None,
        compatibility_notice=notice,
        reason=f"Series-only fallback after model matching failed: {search.series} / {search.target.guarded_facets.capacity}",
    )
