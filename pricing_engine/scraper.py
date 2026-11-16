import asyncio
import contextlib
import logging
import math
import random
import sys
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pricing_engine.digi_discovery import DigiQueryPlan
    from pricing_engine.digi_transport import DigiDiscoveryContext

from curl_cffi.requests import AsyncSession
from rich.console import Console

from pricing_engine import offer_processing as _processing
from pricing_engine.models import (
    DISCOVERY_SEARCH_FAILED,
    RejectedCandidate,
    ScrapedOffer,
    ScrapeResult,
    is_non_competitor_vendor,
    merge_rejected_examples,
)

_offer_dedupe_key = _processing.offer_dedupe_key
_parse_offers_with_tiers = _processing.parse_offers_with_tiers
_parse_offers_with_diagnostics = _processing.parse_offers_with_diagnostics
_parse_offers_from_raw_items = _processing.parse_offers_from_raw_items
_select_winning_offer = _processing._select_winning_offer
_select_winning_modifier_meta = _processing._select_winning_modifier_meta
_select_winning_compatibility_notice = _processing._select_winning_compatibility_notice
_select_active_tier_pool = _processing._select_active_tier_pool
_select_winning_modifier = _processing._select_winning_modifier
deduplicate_offers = _processing.deduplicate_offers
_own_offer_identity_key = _processing._own_offer_identity_key
deduplicate_own_offers = _processing.deduplicate_own_offers
parse_price_value = _processing.parse_price_value
_has_viable_above_floor_offer = _processing._has_viable_above_floor_offer
_listing_brands = _processing._listing_brands
finalize_offers = _processing.finalize_offers

# Configure UTF-8 encoding safely for Windows CLI terminals
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)
console = Console(legacy_windows=False)


def _safe_console_print(msg: str) -> None:
    """Print message to console, gracefully falling back to ascii on encoding error."""
    try:
        console.print(msg)
    except UnicodeEncodeError:
        try:
            safe_msg = msg.encode("ascii", "replace").decode("ascii")
            console.print(safe_msg)
        except Exception:
            pass
    except Exception:
        pass


ALFA_SEARCH_URL = "https://be.alfamall.com/storefront/search_products"
DIGI_SEARCH_URL = "https://digimall-be.faysalbank.com/storefront/search_products"

COMMON_HEADERS: dict[str, str] = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate, br, zstd",
    "content-type": "application/json",
    "sec-ch-ua": '"Google Chrome";v="120", "Chromium";v="120", "Not?A_Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """Configuration descriptor for a specific storefront search API."""

    platform_name: str
    display_name: str
    search_url: str
    base_params: dict[str, str]
    headers: dict[str, str]


ALFAMALL_CONFIG = PlatformConfig(
    platform_name="alfamall",
    display_name="AlfaMall",
    search_url=ALFA_SEARCH_URL,
    base_params={
        "page": "1",
        "limit": "100",
        "storefront": "23",
        "storefront_domain": "alfamall.com",
    },
    headers={
        **COMMON_HEADERS,
        "origin": "https://alfamall.com",
        "referer": "https://alfamall.com/",
    },
)

DIGIMALL_CONFIG = PlatformConfig(
    platform_name="digimall",
    display_name="DigiMall",
    search_url=DIGI_SEARCH_URL,
    base_params={
        "storefront": "23",
        "page": "1",
        "limit": "100",
    },
    headers={
        **COMMON_HEADERS,
        "origin": "https://digimall.faysalbank.com",
        "referer": "https://digimall.faysalbank.com/",
    },
)

# Run-scoped on-demand cache: (platform, query, target_desc) -> ScrapeResult
_query_cache: dict[tuple[str, str, str], ScrapeResult] = {}
_raw_items_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
_raw_items_meta_cache: dict[tuple[str, str], tuple[int | None, bool]] = {}


def clear_scraper_cache() -> None:
    """Clear all in-memory query search cache entries."""
    _query_cache.clear()
    _raw_items_cache.clear()
    _raw_items_meta_cache.clear()


def get_scraper_cache() -> dict[tuple[str, str, str], ScrapeResult]:
    """Return a read-only copy of current query cache."""
    return dict(_query_cache)




















async def _execute_waterfall(
    single_scraper_fn: Callable[..., Coroutine[Any, Any, ScrapeResult]],
    session: AsyncSession[Any],
    patterns: dict[str, list[str]],
    target_model: str,
    timeout: float,
    max_retries: int,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
    exhaustive: bool = True,
) -> ScrapeResult:
    """Execute 3-tier multi-pattern waterfall candidate retrieval across query tiers.

    By default (`exhaustive=True`), all 3 tiers (`tier_1`, `tier_2`, `tier_3`) are
    queried to ensure a complete candidate pool across hyphenated, unhyphenated, and
    spaced seller title variations. If `exhaustive=False`, exits early when a tier
    accumulates 2 or more exact offers.
    """
    collected_offers: list[ScrapedOffer] = []
    collected_base_offers: list[ScrapedOffer] = []
    collected_sibling_offers: list[ScrapedOffer] = []
    collected_own_offers: list[ScrapedOffer] = []
    seen_offers: set[tuple[str, float, str, str]] = set()
    seen_sibling_offers: set[tuple[str, float, str, str]] = set()
    detected_missing_modifier: str | None = None
    detected_missing_source: str = "target"
    any_success = False
    any_failure = False
    first_failure_status: int | None = None
    first_failure_error: str | None = None
    last_status: int | None = None
    last_error: str | None = None
    executed_queries: list[str] = []
    tier_summary: dict[str, int] = {}
    matched_tier: str | None = None
    total_raw_count = 0
    total_rejected_count = 0
    merged_rejection_reasons: dict[str, int] = {}
    merged_examples: list[RejectedCandidate] = []
    total_suspicious_rejected = 0
    max_pages_fetched = 1
    max_total_available: int | None = None
    all_pagination_complete = True
    collected_extended_designation: str | None = None

    tier_order = ["tier_1", "tier_2", "tier_3"]
    all_tiers = [t for t in tier_order if t in patterns] + [
        t for t in patterns if t not in tier_order and t != "series_fallback"
    ]
    if "series_fallback" in patterns:
        all_tiers.append("series_fallback")

    executed_lower: set[str] = set()
    for tier_name in all_tiers:
        if tier_name == "series_fallback":
            from pricing_engine.series_fallback import has_active_model_offers

            if any_failure or has_active_model_offers(
                collected_offers, collected_base_offers, collected_sibling_offers, collected_own_offers
            ):
                continue
        tier_queries = patterns[tier_name]
        tier_offers_count = 0
        unique_tier_queries: list[str] = []
        for q in tier_queries:
            q_str = str(q).strip()
            if not q_str:
                continue
            execution_key = q_str.lower() + (
                "|SERIES_FALLBACK" if tier_name == "series_fallback" else ""
            )
            if execution_key in executed_lower:
                continue
            executed_lower.add(execution_key)
            executed_queries.append(q_str)
            unique_tier_queries.append(q_str)

        if unique_tier_queries:
            sub_results = await asyncio.gather(
                *[
                    single_scraper_fn(
                        session=session,
                        query=q_str,
                        target_model=target_model,
                        timeout=timeout,
                        max_retries=max_retries,
                        floor_price=floor_price,
                        brand=brand,
                        target_desc=target_desc,
                        **({"series_fallback": True} if tier_name == "series_fallback" else {}),
                    )
                    for q_str in unique_tier_queries
                ]
            )
            for sub_res in sub_results:
                if sub_res.is_success:
                    any_success = True
                else:
                    any_failure = True
                    if first_failure_status is None and sub_res.status_code is not None:
                        first_failure_status = sub_res.status_code
                    if first_failure_error is None and sub_res.error_detail:
                        first_failure_error = sub_res.error_detail
                last_status = sub_res.status_code
                if sub_res.error_detail:
                    last_error = sub_res.error_detail

                total_raw_count += sub_res.raw_candidate_count
                total_rejected_count += sub_res.rejected_count
                merged_examples = merge_rejected_examples([
                    *merged_examples, *getattr(sub_res, "rejected_examples", [])
                ])
                for r_k, r_v in sub_res.rejection_reasons.items():
                    merged_rejection_reasons[r_k] = merged_rejection_reasons.get(r_k, 0) + r_v
                total_suspicious_rejected += sub_res.suspicious_rejected_count
                max_pages_fetched = max(max_pages_fetched, sub_res.pages_fetched)
                if sub_res.total_available is not None:
                    max_total_available = max(max_total_available or 0, sub_res.total_available)
                if not sub_res.pagination_complete:
                    all_pagination_complete = False
                if sub_res.extended_model_designation and not collected_extended_designation:
                    collected_extended_designation = sub_res.extended_model_designation

                for off in sub_res.offers:
                    dedupe_key = _offer_dedupe_key(off)
                    if dedupe_key not in seen_offers:
                        seen_offers.add(dedupe_key)
                        collected_offers.append(off)
                        tier_offers_count += 1

                for off in sub_res.base_offers:
                    collected_base_offers.append(off)

                for off in getattr(sub_res, "sibling_offers", []):
                    dedupe_key = _offer_dedupe_key(off)
                    if dedupe_key not in seen_sibling_offers:
                        seen_sibling_offers.add(dedupe_key)
                        collected_sibling_offers.append(off)

                collected_own_offers.extend(sub_res.own_offers)

                if sub_res.active_modifier_fallback and not detected_missing_modifier:
                    detected_missing_modifier = sub_res.active_modifier_fallback
                    detected_missing_source = sub_res.active_modifier_source

        tier_summary[tier_name] = tier_offers_count
        if tier_offers_count > 0 and matched_tier is None:
            matched_tier = tier_name
        instock_exact_count = sum(1 for o in collected_offers if not o.is_sold_out)
        if not exhaustive and instock_exact_count >= 2:
            break

    selection = finalize_offers(ScrapeResult(
        offers=collected_offers, base_offers=collected_base_offers,
        sibling_offers=collected_sibling_offers, own_offers=collected_own_offers,
        active_modifier_fallback=detected_missing_modifier,
        active_modifier_source=detected_missing_source,
    ), target_model, floor_price)
    final_offers = selection.offers
    collected_base_offers = selection.base_offers
    collected_sibling_offers = selection.sibling_offers
    collected_own_offers = selection.own_offers
    active_fallback = selection.active_modifier_fallback
    active_source = selection.active_modifier_source
    ambiguity = selection.ambiguity_conflict
    final_compat_notice = selection.compatibility_notice

    # AUD-CRIT-06: During partial waterfall outages (any_failure=True), own-store listings and
    # sold-out/sub-floor listings do NOT prove healthy external competitor discovery.
    min_int_floor = math.ceil(floor_price) if floor_price is not None else None
    has_viable_external_competitor = any(
        not o.is_sold_out
        and not is_non_competitor_vendor(o.vendor_name)
        and (min_int_floor is None or o.price > min_int_floor)
        for o in final_offers
    )
    if any_failure:
        overall_success = has_viable_external_competitor
    else:
        overall_success = any_success or bool(
            final_offers
            or collected_base_offers
            or collected_sibling_offers
            or collected_own_offers
        )
    final_status = (
        (first_failure_status or last_status)
        if not overall_success
        else (last_status if last_status is not None else (200 if any_success else None))
    )
    final_error = None if overall_success else (first_failure_error or last_error)

    discovery_status = _processing.classify_discovery(replace(
        selection, is_success=overall_success, pagination_complete=all_pagination_complete,
        suspicious_rejected_count=total_suspicious_rejected,
    ))

    return ScrapeResult(
        offers=final_offers,
        active_modifier_fallback=active_fallback,
        active_modifier_source=active_source,
        base_offers=collected_base_offers,
        sibling_offers=collected_sibling_offers,
        own_offers=collected_own_offers,
        is_success=overall_success,
        status_code=final_status,
        error_detail=final_error,
        executed_queries=executed_queries,
        matched_tier=matched_tier,
        tier_summary=tier_summary,
        ambiguity_conflict=ambiguity,
        discovery_status=discovery_status,
        raw_candidate_count=total_raw_count,
        rejected_count=total_rejected_count,
        rejection_reasons=merged_rejection_reasons,
        rejected_examples=merged_examples,
        suspicious_rejected_count=total_suspicious_rejected,
        pages_fetched=max_pages_fetched,
        total_available=max_total_available,
        pagination_complete=all_pagination_complete,
        extended_model_designation=collected_extended_designation,
        compatibility_notice=final_compat_notice,
    )




MAX_SEARCH_PAGES: int = 3











async def _scrape_platform_single_query(
    config: PlatformConfig,
    session: AsyncSession[Any],
    query: str,
    target_model: str,
    timeout: float = 15.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
    series_fallback: bool = False,
) -> ScrapeResult:
    """Generic single-query scraper for e-commerce storefront search APIs.

    Features:
    - On-demand in-memory caching with strict poisoning guard (only 200 OK + non-empty offers).
    - Modern Chrome 120 headers.
    - Soft 200 OK WAF challenge detection & schema validation for both 'results' and 'data' keys.
    - Fast timeout with jittered exponential backoff.
    - Live terminal telemetry badges on retries/stalls.
    - Conditional sub-floor page 2 probing.
    """
    rejected_examples: list[RejectedCandidate] = []
    raw_cache_key = (config.platform_name, query.strip().upper())
    cache_key = (
        config.platform_name,
        query.strip().upper(),
        (target_desc.strip() or target_model).upper()
        + ("|SERIES_FALLBACK" if series_fallback else ""),
    )
    if raw_cache_key in _raw_items_cache:
        raw_cached = list(_raw_items_cache[raw_cache_key])
        (
            e_cached,
            b_cached,
            s_cached,
            d_cached,
            o_cached,
            r_cnt_c,
            rej_cnt_c,
            rej_reasons_c,
            susp_cnt_c,
            ext_des_c,
        ) = _parse_offers_with_tiers(
            raw_cached,
            target_model,
            brand=brand,
            target_desc=target_desc,
            rejected_examples=rejected_examples,
            query=query,
            series_fallback=series_fallback,
        )
        cached_meta = _raw_items_meta_cache.get(raw_cache_key)
        cached_total = cached_meta[0] if cached_meta else None
        p_complete = cached_meta[1] if (cached_meta and len(cached_meta) >= 2) else True
        pages_probed = 1 if not p_complete else 2

        active_cached_probe = _select_active_tier_pool(e_cached, b_cached, s_cached)
        has_instock_cached = any(
            not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
            for o in active_cached_probe
        )
        has_viable_cached = _has_viable_above_floor_offer(active_cached_probe, floor_price)
        needs_more_pages = (
            cached_total is not None
            and cached_total > len(raw_cached)
            and len(raw_cached) > 0
            and pages_probed < MAX_SEARCH_PAGES
            and (not has_instock_cached or (floor_price is not None and not has_viable_cached))
        )
        if needs_more_pages:
            for next_page in range(pages_probed + 1, MAX_SEARCH_PAGES + 1):
                if len(raw_cached) >= (cached_total or 0):
                    break
                params_p = {**config.base_params, "q": query, "page": str(next_page)}
                try:
                    resp_p = await session.get(
                        config.search_url, params=params_p, headers=config.headers, timeout=timeout
                    )
                    if resp_p.status_code == 200:
                        data_p = resp_p.json() if hasattr(resp_p, "json") else {}
                        raw_p = data_p.get("results") if isinstance(data_p, dict) else None
                        if raw_p is None and isinstance(data_p, dict):
                            raw_p = data_p.get("data")
                        if isinstance(raw_p, list):
                            if not raw_p:
                                break
                            pages_probed = next_page
                            raw_cached.extend(raw_p)
                            _raw_items_cache[raw_cache_key] = list(raw_cached)
                            (
                                e_p,
                                b_p,
                                s_p,
                                d_p,
                                o_p,
                                r_p,
                                rej_p,
                                reasons_p,
                                susp_p,
                                ext_p,
                            ) = _parse_offers_with_tiers(
                                raw_p,
                                target_model,
                                brand=brand,
                                target_desc=target_desc,
                                rejected_examples=rejected_examples,
                                query=query,
                                series_fallback=series_fallback,
                            )
                            e_cached.extend(e_p)
                            b_cached.extend(b_p)
                            s_cached.extend(s_p)
                            o_cached.extend(o_p)
                            r_cnt_c += r_p
                            rej_cnt_c += rej_p
                            for rk, rv in reasons_p.items():
                                rej_reasons_c[rk] = rej_reasons_c.get(rk, 0) + rv
                            susp_cnt_c += susp_p
                            if d_p and not d_cached:
                                d_cached = d_p
                            if ext_p and not ext_des_c:
                                ext_des_c = ext_p
                            _raw_items_meta_cache[raw_cache_key] = (cached_total, p_complete)
                            cur_pool_c = _select_active_tier_pool(e_cached, b_cached, s_cached)
                            if floor_price is not None and _has_viable_above_floor_offer(
                                cur_pool_c, floor_price
                            ):
                                break
                            if floor_price is None and any(
                                not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
                                for o in cur_pool_c
                            ):
                                break
                            if brand and not (e_p or b_p or s_p):
                                b_lower = brand.lower()
                                if not any(
                                    b_lower in str(it.get("title", "")).lower() for it in raw_p
                                ):
                                    break
                    else:
                        p_complete = False
                        _raw_items_meta_cache[raw_cache_key] = (cached_total, p_complete)
                        break
                except Exception as exc_p:
                    p_complete = False
                    _raw_items_meta_cache[raw_cache_key] = (cached_total, p_complete)
                    logger.debug(
                        "%s cached page %d probe exception: %s",
                        config.display_name,
                        next_page,
                        exc_p,
                    )
                    break

        e_cached = deduplicate_offers(e_cached)
        b_cached = deduplicate_offers(b_cached)
        s_cached = deduplicate_offers(s_cached)
        o_cached = deduplicate_own_offers(o_cached)
        d_src_cached = "target"
        if b_cached:
            d_cached, d_src_cached = _select_winning_modifier_meta(
                b_cached, d_cached, "target", floor_price=floor_price
            )
        elif e_cached:
            d_cached, d_src_cached = _select_winning_modifier_meta(
                e_cached, d_cached, "target", floor_price=floor_price
            )
        compat_cached = _select_winning_compatibility_notice(
            _select_active_tier_pool(e_cached, b_cached, s_cached), floor_price=floor_price
        )
        return ScrapeResult(
            rejected_examples=list(rejected_examples),
            offers=e_cached,
            base_offers=b_cached,
            sibling_offers=s_cached,
            own_offers=o_cached,
            active_modifier_fallback=d_cached,
            active_modifier_source=d_src_cached,
            is_success=True,
            status_code=200,
            error_detail=None,
            raw_candidate_count=r_cnt_c,
            rejected_count=rej_cnt_c,
            rejection_reasons=rej_reasons_c,
            suspicious_rejected_count=susp_cnt_c,
            pages_fetched=pages_probed,
            total_available=cached_total,
            pagination_complete=p_complete,
            extended_model_designation=ext_des_c,
            compatibility_notice=compat_cached,
        )
    if cache_key in _query_cache:
        cached = _query_cache[cache_key]
        return ScrapeResult(
            rejected_examples=list(cached.rejected_examples),
            offers=[replace(o) for o in cached.offers],
            base_offers=[replace(o) for o in cached.base_offers],
            sibling_offers=[replace(o) for o in cached.sibling_offers],
            own_offers=[replace(o) for o in cached.own_offers],
            active_modifier_fallback=cached.active_modifier_fallback,
            active_modifier_source=cached.active_modifier_source,
            is_success=cached.is_success,
            status_code=cached.status_code,
            error_detail=cached.error_detail,
            discovery_status=cached.discovery_status,
            raw_candidate_count=cached.raw_candidate_count,
            rejected_count=cached.rejected_count,
            rejection_reasons=dict(cached.rejection_reasons),
            suspicious_rejected_count=cached.suspicious_rejected_count,
            pages_fetched=cached.pages_fetched,
            total_available=cached.total_available,
            pagination_complete=cached.pagination_complete,
            extended_model_designation=cached.extended_model_designation,
            compatibility_notice=cached.compatibility_notice,
        )

    params = {**config.base_params, "q": query}
    headers = config.headers

    exact_offers: list[ScrapedOffer] = []
    base_offers: list[ScrapedOffer] = []
    sibling_offers: list[ScrapedOffer] = []
    own_offers: list[ScrapedOffer] = []
    detected_modifier: str | None = None
    last_status: int | None = None
    last_error: str | None = None

    for attempt in range(max_retries):
        cur_timeout = timeout + (attempt * 5.0)
        try:
            resp = await session.get(
                config.search_url, params=params, headers=headers, timeout=cur_timeout
            )
            last_status = resp.status_code

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception as exc:
                    last_error = f"Invalid JSON / WAF challenge: {exc}"
                    logger.warning(
                        "%s returned non-JSON body on 200 OK for query '%s'",
                        config.display_name,
                        query,
                    )
                    continue

                if not isinstance(data, dict):
                    last_error = "Invalid response schema (expected JSON object)"
                    continue

                # Support both 'results' and 'data' keys
                raw_items = data.get("results")
                if raw_items is None:
                    raw_items = data.get("data")

                if not isinstance(raw_items, list):
                    last_error = "Missing results/data array in payload"
                    continue

                (
                    e_items,
                    b_items,
                    s_items,
                    d_mod,
                    o_items,
                    r_cnt,
                    rej_cnt,
                    rej_reasons,
                    susp_cnt,
                    ext_des,
                ) = _parse_offers_with_tiers(
                    raw_items,
                    target_model,
                    brand=brand,
                    target_desc=target_desc,
                    rejected_examples=rejected_examples,
                    query=query,
                    series_fallback=series_fallback,
                )
                exact_offers.extend(e_items)
                base_offers.extend(b_items)
                sibling_offers.extend(s_items)
                own_offers.extend(o_items)
                if d_mod and not detected_modifier:
                    detected_modifier = d_mod
                active_extended_designation = ext_des

                total_raw_count = r_cnt
                total_rejected_count = rej_cnt
                merged_rejection_reasons = dict(rej_reasons)
                total_suspicious_rejected = susp_cnt

                total_count_raw = data.get("count") or data.get("total")
                total_count = int(total_count_raw) if isinstance(total_count_raw, int) else None
                combined_raw_items = list(raw_items)
                pages_fetched = 1
                pagination_complete = True

                active_p1_probe = _select_active_tier_pool(
                    exact_offers, base_offers, sibling_offers
                )
                has_instock_p1 = any(
                    not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
                    for o in active_p1_probe
                )
                has_viable_p1 = _has_viable_above_floor_offer(active_p1_probe, floor_price)
                needs_pagination = (
                    total_count is not None
                    and total_count > len(raw_items)
                    and len(raw_items) > 0
                    and (not has_instock_p1 or (floor_price is not None and not has_viable_p1))
                )

                if needs_pagination:
                    for next_page in range(2, MAX_SEARCH_PAGES + 1):
                        if len(combined_raw_items) >= (total_count or 0):
                            break
                        params_next = {**params, "page": str(next_page)}
                        try:
                            resp_next = await session.get(
                                config.search_url,
                                params=params_next,
                                headers=headers,
                                timeout=cur_timeout,
                            )
                            if resp_next.status_code == 200:
                                data_next = resp_next.json() if hasattr(resp_next, "json") else {}
                                raw_next = (
                                    data_next.get("results")
                                    if isinstance(data_next, dict)
                                    else None
                                )
                                if raw_next is None and isinstance(data_next, dict):
                                    raw_next = data_next.get("data")
                                if isinstance(raw_next, list):
                                    if not raw_next:
                                        break
                                    pages_fetched = next_page
                                    combined_raw_items.extend(raw_next)
                                    (
                                        e_p,
                                        b_p,
                                        s_p,
                                        d_p,
                                        o_p,
                                        r_p,
                                        rej_p,
                                        reasons_p,
                                        susp_p,
                                        ext_p,
                                    ) = _parse_offers_with_tiers(
                                        raw_next,
                                        target_model,
                                        brand=brand,
                                        target_desc=target_desc,
                                        rejected_examples=rejected_examples,
                                        query=query,
                                        series_fallback=series_fallback,
                                    )
                                    exact_offers.extend(e_p)
                                    base_offers.extend(b_p)
                                    sibling_offers.extend(s_p)
                                    own_offers.extend(o_p)
                                    total_raw_count += r_p
                                    total_rejected_count += rej_p
                                    for rk, rv in reasons_p.items():
                                        merged_rejection_reasons[rk] = (
                                            merged_rejection_reasons.get(rk, 0) + rv
                                        )
                                    total_suspicious_rejected += susp_p
                                    if d_p and not detected_modifier:
                                        detected_modifier = d_p
                                    if ext_p and not active_extended_designation:
                                        active_extended_designation = ext_p
                                    cur_pool_p = _select_active_tier_pool(
                                        exact_offers, base_offers, sibling_offers
                                    )
                                    if floor_price is not None and _has_viable_above_floor_offer(
                                        cur_pool_p, floor_price
                                    ):
                                        break
                                    if floor_price is None and any(
                                        not o.is_sold_out
                                        and not is_non_competitor_vendor(o.vendor_name)
                                        for o in cur_pool_p
                                    ):
                                        break
                                    if brand and not (e_p or b_p or s_p):
                                        b_lower = brand.lower()
                                        if not any(
                                            b_lower in str(it.get("title", "")).lower()
                                            for it in raw_next
                                        ):
                                            break
                            else:
                                pagination_complete = False
                                logger.warning(
                                    "%s page %d returned status %s for query %s",
                                    config.display_name,
                                    next_page,
                                    resp_next.status_code,
                                    query,
                                )
                                break
                        except Exception as exc_p:
                            pagination_complete = False
                            logger.debug(
                                "%s page %d probe exception: %s",
                                config.display_name,
                                next_page,
                                exc_p,
                            )
                            break

                exact_offers = deduplicate_offers(exact_offers)
                base_offers = deduplicate_offers(base_offers)
                sibling_offers = deduplicate_offers(sibling_offers)
                own_offers = deduplicate_own_offers(own_offers)
                detected_source = "target"
                if base_offers:
                    detected_modifier, detected_source = _select_winning_modifier_meta(
                        base_offers, detected_modifier, "target", floor_price=floor_price
                    )
                elif exact_offers:
                    detected_modifier, detected_source = _select_winning_modifier_meta(
                        exact_offers, detected_modifier, "target", floor_price=floor_price
                    )
                compat_single = _select_winning_compatibility_notice(
                    _select_active_tier_pool(exact_offers, base_offers, sibling_offers),
                    floor_price=floor_price,
                )

                # Strict Cache Guard: Only cache when response is valid and offers exist
                result = ScrapeResult(
                    rejected_examples=list(rejected_examples),
                    offers=exact_offers,
                    base_offers=base_offers,
                    sibling_offers=sibling_offers,
                    own_offers=own_offers,
                    active_modifier_fallback=detected_modifier,
                    active_modifier_source=detected_source,
                    is_success=True,
                    status_code=200,
                    error_detail=None,
                    raw_candidate_count=total_raw_count,
                    rejected_count=total_rejected_count,
                    rejection_reasons=merged_rejection_reasons,
                    suspicious_rejected_count=total_suspicious_rejected,
                    pages_fetched=pages_fetched,
                    total_available=total_count,
                    pagination_complete=pagination_complete,
                    extended_model_designation=active_extended_designation,
                    compatibility_notice=compat_single,
                )
                # Raw responses are target/mode independent, even when every
                # current candidate was rejected. Revalidate them for later stages.
                _raw_items_cache[raw_cache_key] = list(combined_raw_items)
                _raw_items_meta_cache[raw_cache_key] = (total_count, pagination_complete)
                if exact_offers or base_offers or sibling_offers or own_offers or not raw_items:
                    _query_cache[cache_key] = result
                return result

            elif resp.status_code in (429, 500, 502, 503, 504):
                last_error = f"HTTP {resp.status_code} Server/Gateway Error"
                backoff = (0.6 * (2**attempt)) + random.uniform(0.1, 0.3)
                if resp.status_code == 429:
                    console.print(
                        f"  [bold red]⛔ [{config.display_name}][/] [dim]{query}[/] "
                        f"WAF Rate-limit (429) hit (Attempt {attempt + 1}/{max_retries}) — Cooling down {backoff:.1f}s..."
                    )
                else:
                    console.print(
                        f"  [bold yellow]⚠️  [{config.display_name}][/] [dim]{query}[/] "
                        f"Server error {resp.status_code} (Attempt {attempt + 1}/{max_retries}) — Retrying in {backoff:.1f}s..."
                    )
                await asyncio.sleep(backoff)
            else:
                last_error = f"HTTP {resp.status_code} Unexpected Status"
                logger.warning(
                    "%s search API returned status %s for query %s",
                    config.display_name,
                    resp.status_code,
                    query,
                )
                break
        except Exception as exc:
            last_error = str(exc) or "Network Connection/Timeout Error"
            err_str = str(exc).lower()
            is_socket_drop = any(
                k in err_str for k in ("wsarecv", "connection was aborted", "reset", "closed")
            )
            is_timeout = any(k in err_str for k in ("28", "timed out", "timeout"))

            if is_timeout:
                backoff = random.uniform(3.5, 5.0) + (attempt * 1.5)
                _safe_console_print(
                    f"  [bold yellow][!] [{config.display_name}][/] [dim]{query}[/] "
                    f"Connection timeout (Attempt {attempt + 1}/{max_retries}) - Backoff cool-down in {backoff:.1f}s..."
                )
            elif is_socket_drop:
                backoff = (0.8 * (2**attempt)) + random.uniform(0.2, 0.5)
                _safe_console_print(
                    f"  [bold yellow][!] [{config.display_name}][/] [dim]{query}[/] "
                    f"Socket drop/aborted (Attempt {attempt + 1}/{max_retries}) - Auto-recovering in {backoff:.1f}s..."
                )
            else:
                backoff = (0.5 * (2**attempt)) + random.uniform(0.1, 0.4)
                _safe_console_print(
                    f"  [bold yellow][!] [{config.display_name}][/] [dim]{query}[/] "
                    f"Network error (Attempt {attempt + 1}/{max_retries}) - Retrying in {backoff:.1f}s..."
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    "%s failed after %d attempts for query '%s': %s",
                    config.display_name,
                    max_retries,
                    query,
                    exc,
                )

    return ScrapeResult(
        rejected_examples=list(rejected_examples),
        offers=[],
        is_success=False,
        status_code=last_status,
        error_detail=last_error or "Exhausted all retries without successful response",
        pagination_complete=False,
        discovery_status=DISCOVERY_SEARCH_FAILED,
    )


async def _scrape_alfamall_single_query(
    session: AsyncSession[Any],
    query: str,
    target_model: str,
    timeout: float = 15.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
    series_fallback: bool = False,
) -> ScrapeResult:
    """Internal single-query scraper for AlfaMall storefront search API."""
    return await _scrape_platform_single_query(
        config=ALFAMALL_CONFIG,
        session=session,
        query=query,
        target_model=target_model,
        timeout=timeout,
        max_retries=max_retries,
        floor_price=floor_price,
        brand=brand,
        target_desc=target_desc,
        series_fallback=series_fallback,
    )


async def scrape_alfamall(
    session: AsyncSession[Any],
    query: str | dict[str, list[str]],
    target_model: str,
    timeout: float = 15.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
    exhaustive: bool = True,
) -> ScrapeResult:
    """Query AlfaMall storefront search API and extract verified product offers with retries.

    Supports both single search query strings and tiered waterfall pattern dictionaries.

    Args:
        session: Active curl_cffi AsyncSession with Chrome impersonation.
        query: Search keyword string or tiered patterns dictionary.
        target_model: Target model string for strict variant validation.
        timeout: HTTP request timeout in seconds (default: 15.0s).
        max_retries: Number of retry attempts on network/timeout failure (default: 3).
        floor_price: Optional price floor to probe page 2 if all page 1 items are sub-floor.
        brand: Optional brand name for strict matching.
        target_desc: Optional full catalog product description for comprehensive facet matching.

    Returns:
        ScrapeResult containing verified offers and explicit success/failure flags.
    """
    if isinstance(query, str):
        if not query.strip():
            return await _scrape_alfamall_single_query(
                session=session,
                query=query,
                target_model=target_model,
                timeout=timeout,
                max_retries=max_retries,
                floor_price=floor_price,
                brand=brand,
                target_desc=target_desc,
            )
        query = {"tier_1": [query]}
    from pricing_engine.series_fallback import build_series_search

    fallback = build_series_search(target_desc, brand)
    if fallback is not None:
        query = {**query, "series_fallback": [fallback.query]}
    return await _execute_waterfall(
        single_scraper_fn=_scrape_alfamall_single_query,
        session=session,
        patterns=query,
        target_model=target_model,
        timeout=timeout,
        max_retries=max_retries,
        floor_price=floor_price,
        brand=brand,
        target_desc=target_desc,
        exhaustive=exhaustive,
    )


async def _scrape_digimall_single_query(
    session: AsyncSession[Any],
    query: str,
    target_model: str,
    timeout: float = 15.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
) -> ScrapeResult:
    """Internal single-query scraper for DigiMall storefront search API."""
    return await scrape_digimall(
        session=session,
        query=query,
        target_model=target_model,
        timeout=timeout,
        max_retries=max_retries,
        floor_price=floor_price,
        brand=brand,
        target_desc=target_desc,
    )


async def scrape_digimall(
    session: AsyncSession[Any],
    query: "str | dict[str, list[str]] | DigiQueryPlan",
    target_model: str,
    timeout: float = 15.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
    exhaustive: bool = True,
    *,
    context: "DigiDiscoveryContext | None" = None,
) -> ScrapeResult:
    """Query DigiMall (Faysal Bank) storefront search API and extract verified product offers.

    Supports both single search query strings and tiered waterfall pattern dictionaries.

    Args:
        session: Active curl_cffi AsyncSession with Chrome impersonation.
        query: Explicit keyword, legacy tiered dictionary, or adaptive DigiQueryPlan.
        target_model: Target model string for strict variant validation.
        timeout: HTTP request timeout in seconds (default: 15.0s).
        max_retries: Number of retry attempts on network/timeout failure (default: 3).
        floor_price: Price floor used for reference metadata, never pagination exits.
        brand: Optional brand name for strict matching.
        target_desc: Optional full catalog product description for comprehensive facet matching.
        context: Optional shared run-scoped raw-page cache and bounded request budget.

    Returns:
        ScrapeResult containing verified offers and explicit success/failure flags.
    """
    from pricing_engine.digi_discovery import discover_digimall

    return await discover_digimall(
        session,
        query,
        target_model,
        timeout,
        max_retries,
        floor_price,
        brand,
        target_desc,
        exhaustive,
        context,
    )
