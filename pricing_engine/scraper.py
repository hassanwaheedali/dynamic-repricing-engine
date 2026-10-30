import asyncio
import contextlib
import logging
import random
import sys
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession
from rich.console import Console

from pricing_engine.matcher import referee_match
from pricing_engine.models import (
    AmbiguousVariantConflict,
    ScrapedOffer,
    ScrapeResult,
    is_non_competitor_vendor,
)

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


def clear_scraper_cache() -> None:
    """Clear all in-memory query search cache entries."""
    _query_cache.clear()
    _raw_items_cache.clear()


def get_scraper_cache() -> dict[tuple[str, str, str], ScrapeResult]:
    """Return a read-only copy of current query cache."""
    return dict(_query_cache)


def deduplicate_offers(offers: list[ScrapedOffer]) -> list[ScrapedOffer]:
    """Deduplicate offers by (vendor_name.lower().strip(), round(price, 2)), tracking duplicate counts."""
    counts: dict[tuple[str, float], int] = {}
    first_seen: dict[tuple[str, float], ScrapedOffer] = {}
    for off in offers:
        key = (off.vendor_name.lower().strip(), round(off.price, 2))
        counts[key] = counts.get(key, 0) + (off.duplicate_count or 1)
        if key not in first_seen:
            first_seen[key] = off

    unique_offers: list[ScrapedOffer] = []
    for key, off in first_seen.items():
        total_dupes = counts[key]
        if total_dupes > 1:
            unique_offers.append(
                ScrapedOffer(
                    vendor_name=off.vendor_name,
                    price=off.price,
                    is_sold_out=off.is_sold_out,
                    raw_title=off.raw_title,
                    duplicate_count=total_dupes,
                )
            )
        else:
            unique_offers.append(off)
    return unique_offers


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
) -> ScrapeResult:
    """Execute tiered early-exit waterfall candidate retrieval across query tiers.

    Tiers are queried in sequence: tier_1 -> tier_2 -> tier_3.
    Exact matches take priority. If no exact matches exist and target had an
    auxiliary modifier, falls back safely to base model offers with metadata.
    """
    collected_offers: list[ScrapedOffer] = []
    collected_base_offers: list[ScrapedOffer] = []
    collected_own_offers: list[ScrapedOffer] = []
    seen_offers: set[tuple[str, float]] = set()
    seen_base_offers: set[tuple[str, float]] = set()
    seen_own_offers: set[tuple[str, float]] = set()
    detected_missing_modifier: str | None = None
    any_success = False
    last_status: int | None = None
    last_error: str | None = None
    executed_queries: list[str] = []
    tier_summary: dict[str, int] = {}
    matched_tier: str | None = None

    tier_order = ["tier_1", "tier_2", "tier_3"]
    all_tiers = [t for t in tier_order if t in patterns] + [
        t for t in patterns if t not in tier_order
    ]

    executed_lower: set[str] = set()
    for tier_name in all_tiers:
        tier_queries = patterns[tier_name]
        tier_offers_count = 0
        unique_tier_queries: list[str] = []
        for q in tier_queries:
            q_str = str(q).strip()
            if not q_str:
                continue
            if q_str.lower() in executed_lower:
                continue
            executed_lower.add(q_str.lower())
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
                    )
                    for q_str in unique_tier_queries
                ]
            )
            for sub_res in sub_results:
                if sub_res.is_success:
                    any_success = True
                last_status = sub_res.status_code
                if sub_res.error_detail:
                    last_error = sub_res.error_detail

                for off in sub_res.offers:
                    dedupe_key = (off.vendor_name.lower().strip(), round(off.price, 2))
                    if dedupe_key not in seen_offers:
                        seen_offers.add(dedupe_key)
                        collected_offers.append(off)
                        tier_offers_count += 1

                for off in sub_res.base_offers:
                    dedupe_key = (off.vendor_name.lower().strip(), round(off.price, 2))
                    if dedupe_key not in seen_base_offers:
                        seen_base_offers.add(dedupe_key)
                        collected_base_offers.append(off)

                for off in sub_res.own_offers:
                    dedupe_key = (off.vendor_name.lower().strip(), round(off.price, 2))
                    if dedupe_key not in seen_own_offers:
                        seen_own_offers.add(dedupe_key)
                        collected_own_offers.append(off)

                if sub_res.active_modifier_fallback and not detected_missing_modifier:
                    detected_missing_modifier = sub_res.active_modifier_fallback

        tier_summary[tier_name] = tier_offers_count
        if tier_offers_count > 0 and matched_tier is None:
            matched_tier = tier_name

    # Priority 1: Exact matches always take precedence if any exist in market
    if collected_offers:
        final_offers = collected_offers
        active_fallback = None
        ambiguity = None
    elif collected_base_offers:
        # Priority 2: When zero exact matches exist and target had an auxiliary modifier, fallback to base model
        final_offers = collected_base_offers
        active_fallback = detected_missing_modifier or "Base Model"
        # Pure Dynamic Multi-Variant Conflict Referee (Zero Static Lists)
        variant_groups: dict[str, list[ScrapedOffer]] = {}
        for off in collected_base_offers:
            if off.detected_variant:
                variant_groups.setdefault(off.detected_variant, []).append(off)
        if len(variant_groups.keys()) > 1:
            ambiguity = AmbiguousVariantConflict(
                stem_model=target_model,
                detected_variants=sorted(variant_groups.keys()),
                variant_offers=variant_groups,
            )
        else:
            ambiguity = None
    else:
        final_offers = []
        active_fallback = None
        ambiguity = None

    return ScrapeResult(
        offers=final_offers,
        active_modifier_fallback=active_fallback,
        base_offers=collected_base_offers,
        own_offers=collected_own_offers,
        is_success=any_success if (any_success or not final_offers) else True,
        status_code=last_status if last_status is not None else (200 if any_success else None),
        error_detail=None if any_success else last_error,
        executed_queries=executed_queries,
        matched_tier=matched_tier,
        tier_summary=tier_summary,
        ambiguity_conflict=ambiguity,
    )


def _parse_offers_from_raw_items(
    raw_items: list[dict[str, Any]],
    target_model: str,
    brand: str = "",
    target_desc: str = "",
) -> tuple[list[ScrapedOffer], list[ScrapedOffer], str | None, list[ScrapedOffer]]:
    """Extract and validate offers from raw API items array, segregating exact from base matches and own stores."""
    exact_offers: list[ScrapedOffer] = []
    base_offers: list[ScrapedOffer] = []
    own_offers: list[ScrapedOffer] = []
    detected_modifier: str | None = None
    match_target = target_desc.strip() if target_desc and target_desc.strip() else target_model

    for item in raw_items:
        title = str(item.get("title", ""))
        decision = referee_match(match_target, title, brand=brand)
        is_exact = decision.is_match
        is_base = decision.is_base_match

        if not is_exact and not is_base:
            continue

        sold_out = bool(item.get("sold_out", False))
        variant = item.get("variant_detail", {})
        price_str = variant.get("discounted_price") or variant.get("original_price") or "0"
        try:
            price = float(str(price_str).replace(",", "").strip())
        except ValueError:
            continue

        vendor_obj = item.get("vendor") or {}
        vendor = vendor_obj.get("name") or "Unknown Vendor"
        vendor_handle = vendor_obj.get("handle") or ""
        is_non_comp = is_non_competitor_vendor(str(vendor)) or is_non_competitor_vendor(str(vendor_handle))

        cand_var: str | None = None
        if is_base and decision.missing_modifier and "candidate has variant suffix" in decision.reason.lower():
            raw_mod = decision.missing_modifier.strip()
            upper_mod = raw_mod.upper()
            if upper_mod.startswith("MARKET VARIANT "):
                cand_var = upper_mod.replace("MARKET VARIANT ", "").strip()
            elif upper_mod.startswith("VARIANT "):
                cand_var = upper_mod.replace("VARIANT ", "").strip()
            else:
                cand_var = upper_mod

        if price > 0:
            offer = ScrapedOffer(
                vendor_name=str(vendor),
                price=price,
                is_sold_out=sold_out,
                raw_title=title,
                detected_variant=cand_var,
            )
            if is_non_comp:
                own_offers.append(offer)
            elif is_exact:
                exact_offers.append(offer)
            elif is_base:
                base_offers.append(offer)
                if decision.missing_modifier and not detected_modifier:
                    detected_modifier = decision.missing_modifier

    return exact_offers, base_offers, detected_modifier, own_offers


async def _scrape_platform_single_query(
    config: PlatformConfig,
    session: AsyncSession[Any],
    query: str,
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
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
    raw_cache_key = (config.platform_name, query.strip().upper())
    cache_key = (config.platform_name, query.strip().upper(), (target_desc.strip() or target_model).upper())
    if raw_cache_key in _raw_items_cache:
        raw_cached = _raw_items_cache[raw_cache_key]
        e_cached, b_cached, d_cached, o_cached = _parse_offers_from_raw_items(
            raw_cached, target_model, brand=brand, target_desc=target_desc
        )
        e_cached = deduplicate_offers(e_cached)
        b_cached = deduplicate_offers(b_cached)
        o_cached = deduplicate_offers(o_cached)
        return ScrapeResult(
            offers=e_cached,
            base_offers=b_cached,
            own_offers=o_cached,
            active_modifier_fallback=d_cached,
            is_success=True,
            status_code=200,
            error_detail=None,
        )
    if cache_key in _query_cache:
        cached = _query_cache[cache_key]
        return ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name=o.vendor_name,
                    price=o.price,
                    is_sold_out=o.is_sold_out,
                    raw_title=o.raw_title,
                    duplicate_count=o.duplicate_count,
                )
                for o in cached.offers
            ],
            base_offers=[
                ScrapedOffer(
                    vendor_name=o.vendor_name,
                    price=o.price,
                    is_sold_out=o.is_sold_out,
                    raw_title=o.raw_title,
                    duplicate_count=o.duplicate_count,
                )
                for o in cached.base_offers
            ],
            own_offers=[
                ScrapedOffer(
                    vendor_name=o.vendor_name,
                    price=o.price,
                    is_sold_out=o.is_sold_out,
                    raw_title=o.raw_title,
                    duplicate_count=o.duplicate_count,
                )
                for o in cached.own_offers
            ],
            active_modifier_fallback=cached.active_modifier_fallback,
            is_success=cached.is_success,
            status_code=cached.status_code,
            error_detail=cached.error_detail,
        )

    params = {**config.base_params, "q": query}
    headers = config.headers

    exact_offers: list[ScrapedOffer] = []
    base_offers: list[ScrapedOffer] = []
    own_offers: list[ScrapedOffer] = []
    detected_modifier: str | None = None
    last_status: int | None = None
    last_error: str | None = None

    for attempt in range(max_retries):
        try:
            resp = await session.get(
                config.search_url, params=params, headers=headers, timeout=timeout
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

                e_items, b_items, d_mod, o_items = _parse_offers_from_raw_items(
                    raw_items, target_model, brand=brand, target_desc=target_desc
                )
                exact_offers.extend(e_items)
                base_offers.extend(b_items)
                own_offers.extend(o_items)
                if d_mod and not detected_modifier:
                    detected_modifier = d_mod

                # Conditional page 2 probe if all page 1 offers are sub-floor
                total_count = data.get("count") or data.get("total")
                active_probe_offers = exact_offers or base_offers
                if (
                    floor_price is not None
                    and isinstance(total_count, int)
                    and total_count > len(raw_items)
                    and active_probe_offers
                    and all(o.price <= floor_price for o in active_probe_offers)
                ):
                    params_p2 = {**params, "page": "2"}
                    try:
                        resp_p2 = await session.get(
                            config.search_url, params=params_p2, headers=headers, timeout=timeout
                        )
                        if resp_p2.status_code == 200:
                            data_p2 = resp_p2.json() if hasattr(resp_p2, "json") else {}
                            raw_p2 = data_p2.get("results") or data_p2.get("data") or []
                            if isinstance(raw_p2, list):
                                e_p2, b_p2, d_p2, o_p2 = _parse_offers_from_raw_items(
                                    raw_p2, target_model, brand=brand, target_desc=target_desc
                                )
                                exact_offers.extend(e_p2)
                                base_offers.extend(b_p2)
                                own_offers.extend(o_p2)
                                if d_p2 and not detected_modifier:
                                    detected_modifier = d_p2
                    except Exception as exc_p2:
                        logger.debug("%s page 2 probe exception: %s", config.display_name, exc_p2)

                exact_offers = deduplicate_offers(exact_offers)
                base_offers = deduplicate_offers(base_offers)
                own_offers = deduplicate_offers(own_offers)

                # Strict Cache Guard: Only cache when response is valid and offers exist
                result = ScrapeResult(
                    offers=exact_offers,
                    base_offers=base_offers,
                    own_offers=own_offers,
                    active_modifier_fallback=detected_modifier,
                    is_success=True,
                    status_code=200,
                    error_detail=None,
                )
                if exact_offers or base_offers or own_offers:
                    _query_cache[cache_key] = result
                    if raw_items:
                        _raw_items_cache[raw_cache_key] = list(raw_items)
                elif raw_items is not None and not raw_items:
                    _query_cache[cache_key] = result
                    _raw_items_cache[raw_cache_key] = []

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
        offers=[],
        is_success=False,
        status_code=last_status,
        error_detail=last_error or "Exhausted all retries without successful response",
    )


async def _scrape_alfamall_single_query(
    session: AsyncSession[Any],
    query: str,
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
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
    )


async def scrape_alfamall(
    session: AsyncSession[Any],
    query: str | dict[str, list[str]],
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
) -> ScrapeResult:
    """Query AlfaMall storefront search API and extract verified product offers with retries.

    Supports both single search query strings and tiered waterfall pattern dictionaries.

    Args:
        session: Active curl_cffi AsyncSession with Chrome impersonation.
        query: Search keyword string or tiered patterns dictionary.
        target_model: Target model string for strict variant validation.
        timeout: HTTP request timeout in seconds (default: 10.0s).
        max_retries: Number of retry attempts on network/timeout failure (default: 3).
        floor_price: Optional price floor to probe page 2 if all page 1 items are sub-floor.
        brand: Optional brand name for strict matching.
        target_desc: Optional full catalog product description for comprehensive facet matching.

    Returns:
        ScrapeResult containing verified offers and explicit success/failure flags.
    """
    if isinstance(query, str):
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
    )


async def _scrape_digimall_single_query(
    session: AsyncSession[Any],
    query: str,
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
) -> ScrapeResult:
    """Internal single-query scraper for DigiMall storefront search API."""
    return await _scrape_platform_single_query(
        config=DIGIMALL_CONFIG,
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
    query: str | dict[str, list[str]],
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
    target_desc: str = "",
) -> ScrapeResult:
    """Query DigiMall (Faysal Bank) storefront search API and extract verified product offers.

    Supports both single search query strings and tiered waterfall pattern dictionaries.

    Args:
        session: Active curl_cffi AsyncSession with Chrome impersonation.
        query: Search keyword string or tiered patterns dictionary.
        target_model: Target model string for strict variant validation.
        timeout: HTTP request timeout in seconds (default: 10.0s).
        max_retries: Number of retry attempts on network/timeout failure (default: 3).
        floor_price: Optional price floor for conditional sub-floor page 2 probing.
        brand: Optional brand name for strict matching.
        target_desc: Optional full catalog product description for comprehensive facet matching.

    Returns:
        ScrapeResult containing verified offers and explicit success/failure flags.
    """
    if isinstance(query, str):
        return await _scrape_digimall_single_query(
            session=session,
            query=query,
            target_model=target_model,
            timeout=timeout,
            max_retries=max_retries,
            floor_price=floor_price,
            brand=brand,
            target_desc=target_desc,
        )
    return await _execute_waterfall(
        single_scraper_fn=_scrape_digimall_single_query,
        session=session,
        patterns=query,
        target_model=target_model,
        timeout=timeout,
        max_retries=max_retries,
        floor_price=floor_price,
        brand=brand,
        target_desc=target_desc,
    )
