"""Model-first query planning for DigiMall's broad, relevance-ranked search."""

import asyncio
import json
import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from curl_cffi.requests import AsyncSession

from pricing_engine.ingestion import INVALID_BRAND_VALUES
from pricing_engine.matcher import (
    MatchDecision,
    expand_cartesian_branches,
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
)
from pricing_engine.models import (
    DISCOVERY_PAGINATION_INCOMPLETE,
    DISCOVERY_SEARCH_FAILED,
    ScrapedOffer,
    ScrapeResult,
)

if TYPE_CHECKING:
    from pricing_engine.digi_transport import DigiDiscoveryContext
    from pricing_engine.scraper import PlatformConfig

DIGI_DISCOVERY_POLICY_VERSION = "model-first-v4"
DIGI_PAGE_SIZE = 100
DIGI_MAX_PAGES = 3


@dataclass(frozen=True, slots=True)
class DigiQueryBranch:
    """One explicitly requested product branch and its ordered query attempts."""

    description: str
    model: str
    queries: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DigiQueryPlan:
    """Target branches; success in one branch never suppresses another."""

    branches: tuple[DigiQueryBranch, ...]


def normalize_query(query: str) -> str:
    """Normalize case and whitespace without conflating model separators."""
    return " ".join(query.split()).casefold()


def is_definitive_digi_rejection(decision: MatchDecision) -> bool:
    """Explicit incompatible facets are absence evidence, not uncertain identity.

    With a known catalog anchor, an absent candidate model is rejected rather
    than guessed from brand/capacity. No product/brand-specific exceptions are used.
    """
    category = decision.reason.split(":", 1)[0].casefold()
    if category == "anchor model mismatch":
        return bool(decision.target_slots and decision.target_slots.anchor)
    return bool(re.search(r"\b(?:collision|mismatch)\b", category))


def format_digimall_summary(result: ScrapeResult) -> str:
    """Short terminal audit; raw query/page diagnostics remain in exported detail."""
    labels = {
        "COMPLETE": "Search complete",
        "CAPPED": "Scan limit reached",
        "INCOMPLETE": "Search incomplete",
        "UNKNOWN": "Coverage unknown",
        "FAILED": "Search failed",
    }
    required = sum(len(a.get("required_pages", [])) for a in result.query_audit)
    successful = sum(len(a.get("successful_pages", [])) for a in result.query_audit)
    offers = sum(not o.is_sold_out for o in result.offers)
    return (
        f"{len(result.query_audit)} searches | {successful}/{required} pages checked | "
        f"{offers} compatible sellers | {labels.get(result.coverage_status, 'Needs review')}"
    )


def generate_digimall_plan(description: str, brand: str) -> DigiQueryPlan:
    """Build up to three brandless queries per explicit catalog model branch.

    Matching always uses the original description, even when retrieval broadens.
    """
    if brand.strip().casefold() in INVALID_BRAND_VALUES:
        raise ValueError("Brand must be supplied by the catalog for DigiMall discovery")
    branches: list[DigiQueryBranch] = []
    brand_pattern = re.compile(rf"\b{re.escape(brand.strip())}\b", re.IGNORECASE)
    for branch in expand_cartesian_branches(description):
        _, model = extract_search_query_and_model(branch, brand=brand)
        model = " ".join(brand_pattern.sub(" ", model).split())
        if not re.search(r"\d", model):
            raise ValueError("No usable numeric model found for DigiMall discovery")
        queries = [model]
        # Seller listings often omit/format suffix designators differently (e.g. "(GC)" vs
        # none), and a suffixed query can be drowned by a broad relevance-ranked result set.
        # Always schedule the bare anchor stem so the suffix is verified by the matcher
        # (as a compatibility notice) instead of being required by the search engine.
        anchor = extract_product_slots(branch, brand=brand).anchor
        if anchor and re.search(r"\d", anchor) and normalize_query(anchor) != normalize_query(model):
            queries.append(anchor)
        alternate = model.replace("-", " ") if "-" in model else model.replace(" ", "")
        if normalize_query(alternate) != normalize_query(model):
            queries.append(" ".join(alternate.split()))
        # Seller listings often omit/format suffix designators differently (e.g. "(GC)" vs
        # none), and a suffixed query can be drowned by a broad relevance-ranked result set.
        # Always schedule the bare anchor stem so the suffix is verified by the matcher
        # (as a compatibility notice) instead of being required by the search engine.
        anchor = extract_product_slots(branch, brand=brand).anchor
        if anchor and re.search(r"\d", anchor) and normalize_query(anchor) != normalize_query(model):
            queries.append(anchor)
        for candidate in generate_search_patterns(branch, brand=brand).get("tier_2", []):
            clean = " ".join(brand_pattern.sub(" ", candidate).split())
            if len(queries) < 3 and re.search(r"\d", clean) and normalize_query(clean) not in {
                normalize_query(q) for q in queries
            }:
                queries.append(clean)
                break
        branches.append(DigiQueryBranch(branch, model, tuple(queries)))
    if not branches:
        raise ValueError("No usable model found for DigiMall discovery")
    return DigiQueryPlan(tuple(branches))


def _dedupe_available(offers: list[ScrapedOffer]) -> list[ScrapedOffer]:
    """Prefer in-stock copies before applying the canonical metadata deduplicator."""
    from pricing_engine.scraper import _offer_dedupe_key, deduplicate_offers

    available_keys = {_offer_dedupe_key(o) for o in offers if not o.is_sold_out}
    preferred = [
        o for o in offers if not o.is_sold_out or _offer_dedupe_key(o) not in available_keys
    ]
    merged = deduplicate_offers(preferred)
    counts: dict[tuple[str, float, str, str], int] = {}
    for offer in offers:
        key = _offer_dedupe_key(offer)
        counts[key] = counts.get(key, 0) + offer.duplicate_count
    return [replace(o, duplicate_count=counts[_offer_dedupe_key(o)]) for o in merged]


async def _fetch_query(
    config: "PlatformConfig",
    session: AsyncSession[Any],
    context: "DigiDiscoveryContext",
    query: str,
    model: str,
    description: str,
    brand: str,
    timeout: float,
    max_retries: int,
) -> ScrapeResult:
    """Fetch a query's entire page budget before evaluating offer eligibility."""
    from pricing_engine.digi_transport import required_pages
    from pricing_engine.scraper import _parse_offers_with_tiers

    first = await context.fetch(config, session, query, 1, timeout, max_retries)
    required = required_pages(first.total) if first.success else (1,)
    later = await asyncio.gather(
        *[context.fetch(config, session, query, p, timeout, max_retries) for p in required[1:]]
    )
    pages = [first, *later]
    successful = [p for p in pages if p.success]
    problems = [p.error for p in pages if not p.success]
    observed_totals = {p.total for p in successful if p.total is not None}
    if len(observed_totals) > 1:
        problems.append(f"Conflicting reported counts: {sorted(observed_totals)}")
        for page in successful:
            context.discard(config, query, page.number)
    reference_total = first.total
    if reference_total is None and len(observed_totals) == 1:
        reference_total = next(iter(observed_totals))
    seen_pages: set[str] = set()
    for page in successful:
        if reference_total is not None:
            expected = min(
                DIGI_PAGE_SIZE, max(0, reference_total - (page.number - 1) * DIGI_PAGE_SIZE)
            )
            if len(page.items) != expected:
                context.discard(config, query, page.number)
                problems.append(
                    f"Page {page.number}: expected {expected} items, received {len(page.items)}"
                )
            if page.total is not None and page.total != reference_total:
                problems.append(
                    f"Page {page.number}: count changed from {first.total} to {page.total}"
                )
        if page.items:
            fingerprint = json.dumps(
                sorted(json.dumps(item, sort_keys=True, default=str) for item in page.items)
            )
            if fingerprint in seen_pages:
                context.discard(config, query, page.number)
                problems.append(f"Page {page.number}: repeated whole-page listings")
            seen_pages.add(fingerprint)
    coverage = "COMPLETE"
    if not successful:
        coverage = "FAILED"
    elif problems:
        coverage = "INCOMPLETE"
    elif first.total is None:
        coverage = "UNKNOWN"
    elif first.total > DIGI_PAGE_SIZE * DIGI_MAX_PAGES:
        coverage = "CAPPED"
    raw = [item for page in successful for item in page.items]
    exact, base, sibling, mod, own, count, rejected, reasons, suspicious, extended = (
        _parse_offers_with_tiers(raw, model, brand=brand, target_desc=description,
                                definitive_rejection=is_definitive_digi_rejection)
    )
    audit: dict[str, Any] = {
        "query": query,
        "required_pages": list(required),
        "successful_pages": [p.number for p in successful],
        "failed_pages": [p.number for p in pages if not p.success],
        "total": first.total,
        "coverage": coverage,
        "errors": problems,
    }
    detail = (
        f"{query!r}: required={list(required)}, successful={audit['successful_pages']}, "
        f"failed={audit['failed_pages']}, total={first.total}, coverage={coverage}"
    )
    if problems:
        detail += "; " + "; ".join(problems)
    return ScrapeResult(
        offers=exact,
        base_offers=base,
        sibling_offers=sibling,
        own_offers=own,
        active_modifier_fallback=mod,
        is_success=bool(successful),
        status_code=200 if successful else first.status_code,
        error_detail="; ".join(problems) or None,
        raw_candidate_count=count,
        rejected_count=rejected,
        rejection_reasons=reasons,
        suspicious_rejected_count=suspicious,
        pages_fetched=len(successful),
        total_available=first.total,
        pagination_complete=coverage == "COMPLETE",
        extended_model_designation=extended,
        coverage_status=coverage,
        coverage_detail=detail,
        query_audit=[audit],
    )


async def discover_digimall(
    session: AsyncSession[Any],
    query: str | dict[str, list[str]] | DigiQueryPlan,
    target_model: str,
    timeout: float,
    max_retries: int,
    floor_price: float | None,
    brand: str,
    target_desc: str,
    exhaustive: bool,
    context: "DigiDiscoveryContext | None" = None,
) -> ScrapeResult:
    """Run adaptive plans or explicit legacy queries, preserving matcher tier semantics."""
    from pricing_engine.digi_transport import DigiDiscoveryContext
    from pricing_engine.scraper import DIGIMALL_CONFIG, _execute_waterfall, _offer_dedupe_key

    planned = isinstance(query, DigiQueryPlan)
    if (planned or brand) and brand.strip().casefold() in INVALID_BRAND_VALUES:
        return ScrapeResult(
            is_success=False,
            status_code=None,
            coverage_status="FAILED",
            coverage_detail="Invalid catalog Brand",
            error_detail="Invalid catalog Brand",
            pagination_complete=False,
        )
    ctx = context if context is not None else DigiDiscoveryContext()
    if isinstance(query, DigiQueryPlan):
        groups = [
            (branch.description, branch.model, branch.queries, "") for branch in query.branches
        ]
    elif isinstance(query, str):
        groups = [(target_desc, target_model, (query,), "tier_1")]
    else:
        # Caller-supplied dictionaries remain explicit, exhaustive query requests.
        tiers: list[str] = [key for key in ("tier_1", "tier_2", "tier_3") if key in query]
        tiers.extend(key for key in query if key not in tiers)
        groups = [(target_desc, target_model, tuple(query[tier]), tier) for tier in tiers]
    results: list[ScrapeResult] = []
    names: list[str] = []
    query_tiers: list[str] = []
    tier_summary: dict[str, int] = {}
    explicit_seen: set[str] = set()
    for description, model, queries, group_tier in groups:
        if not planned:
            tier_summary.setdefault(group_tier, 0)
        branch_exact = False
        seen_queries: set[str] = set() if planned else explicit_seen
        for attempt, text in enumerate(queries):
            text = " ".join(text.split())
            if not text or normalize_query(text) in seen_queries:
                continue
            seen_queries.add(normalize_query(text))
            # Reuse HTTP pages across branches, but revalidate every branch separately.
            result = await _fetch_query(
                DIGIMALL_CONFIG, session, ctx, text, model, description, brand, timeout, max_retries
            )
            results.append(result)
            names.append(text)
            tier = f"tier_{attempt + 1}" if planned else group_tier
            tier_summary.setdefault(tier, 0)
            query_tiers.append(tier)
            branch_exact = branch_exact or any(not o.is_sold_out for o in result.offers)
            if planned and (result.coverage_status in {"FAILED", "INCOMPLETE"} or branch_exact):
                break
        if (
            not planned
            and not exhaustive
            and sum(
                not o.is_sold_out
                for o in _dedupe_available([offer for result in results for offer in result.offers])
            )
            >= 2
        ):
            break
    if not results:
        return ScrapeResult(
            is_success=False,
            status_code=None,
            coverage_status="FAILED",
            coverage_detail="No usable DigiMall query",
            error_detail="No usable DigiMall query",
            pagination_complete=False,
        )
    seen_exact: set[tuple[str, float, str, str]] = set()
    for tier, result in zip(query_tiers, results, strict=True):
        for offer in result.offers:
            key = _offer_dedupe_key(offer)
            if key not in seen_exact:
                seen_exact.add(key)
                tier_summary[tier] += 1
    pools = {
        name: _dedupe_available([offer for result in results for offer in getattr(result, name)])
        for name in ("offers", "base_offers", "sibling_offers", "own_offers")
    }
    reasons: dict[str, int] = {}
    for result in results:
        for name, count in result.rejection_reasons.items():
            reasons[name] = reasons.get(name, 0) + count
    combined = ScrapeResult(
        offers=pools["offers"],
        base_offers=pools["base_offers"],
        sibling_offers=pools["sibling_offers"],
        own_offers=pools["own_offers"],
        is_success=any(r.is_success for r in results),
        status_code=200 if any(r.is_success for r in results) else results[0].status_code,
        raw_candidate_count=sum(r.raw_candidate_count for r in results),
        rejected_count=sum(r.rejected_count for r in results),
        rejection_reasons=reasons,
        suspicious_rejected_count=sum(r.suspicious_rejected_count for r in results),
        extended_model_designation=next(
            (r.extended_model_designation for r in results if r.extended_model_designation), None
        ),
    )

    async def collected(**kwargs: Any) -> ScrapeResult:
        return combined

    merged = await _execute_waterfall(
        collected,
        session,
        {"tier_1": [names[0]]},
        target_model,
        timeout,
        max_retries,
        floor_price=floor_price,
        brand=brand,
        target_desc=target_desc,
    )
    statuses = {r.coverage_status for r in results}
    coverage = next((s for s in ("INCOMPLETE", "UNKNOWN", "CAPPED") if s in statuses), "COMPLETE")
    if "FAILED" in statuses:
        coverage = "INCOMPLETE" if combined.is_success else "FAILED"
    discovery = merged.discovery_status
    if coverage != "COMPLETE":
        discovery = (
            DISCOVERY_PAGINATION_INCOMPLETE if combined.is_success else DISCOVERY_SEARCH_FAILED
        )
    ordered = sorted(merged.offers, key=lambda o: (o.is_sold_out, o.price))
    return replace(
        merged,
        offers=ordered,
        executed_queries=list(dict.fromkeys(names)),
        tier_summary=tier_summary,
        matched_tier=next((tier for tier, count in tier_summary.items() if count), None),
        is_success=combined.is_success,
        discovery_status=discovery,
        error_detail="; ".join(r.error_detail for r in results if r.error_detail) or None,
        coverage_status=coverage,
        coverage_detail=" | ".join(r.coverage_detail for r in results),
        query_audit=[a for r in results for a in r.query_audit],
        pagination_complete=coverage == "COMPLETE",
        pages_fetched=max(r.pages_fetched for r in results),
        total_available=max(
            (r.total_available for r in results if r.total_available is not None), default=None
        ),
        lowest_offers=[o for o in ordered if not o.is_sold_out][:5],
    )
