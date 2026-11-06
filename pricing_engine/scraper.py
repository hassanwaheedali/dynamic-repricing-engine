import asyncio
import contextlib
import logging
import math
import random
import re
import sys
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pricing_engine.digi_discovery import DigiQueryPlan
    from pricing_engine.digi_transport import DigiDiscoveryContext

from curl_cffi.requests import AsyncSession
from rich.console import Console

from pricing_engine.matcher import MatchDecision, referee_match
from pricing_engine.models import (
    DISCOVERY_CANDIDATES_REJECTED,
    DISCOVERY_COMPLETE_NO_COMPETITORS,
    DISCOVERY_COMPLETE_WITH_OFFERS,
    DISCOVERY_INCOMPLETE,
    DISCOVERY_PAGINATION_INCOMPLETE,
    DISCOVERY_SEARCH_FAILED,
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
_raw_items_meta_cache: dict[tuple[str, str], tuple[int | None, bool]] = {}


def clear_scraper_cache() -> None:
    """Clear all in-memory query search cache entries."""
    _query_cache.clear()
    _raw_items_cache.clear()
    _raw_items_meta_cache.clear()


def get_scraper_cache() -> dict[tuple[str, str, str], ScrapeResult]:
    """Return a read-only copy of current query cache."""
    return dict(_query_cache)


def _offer_dedupe_key(off: ScrapedOffer) -> tuple[str, float, str, str]:
    """Build deduplication key, preserving distinct color/variant listings even from the same vendor."""
    v_norm = off.vendor_name.lower().strip()
    if not v_norm or v_norm == "unknown vendor":
        fallback_id = (off.product_handle or off.raw_title).lower().strip()
        v_norm = f"unknown::{fallback_id}"
    col = (off.color_family or "").lower().strip()
    var = (off.detected_variant or "").lower().strip()
    return (v_norm, round(off.price, 2), col, var)


def _select_winning_offer(
    offers: list[ScrapedOffer],
    floor_price: float | None = None,
) -> ScrapedOffer | None:
    """Select the winning external reference offer (viable in-stock > sub-floor in-stock > sold-out)."""
    in_stock = [
        o for o in offers if not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
    ]
    if in_stock:
        if floor_price is not None:
            min_int_floor = math.ceil(floor_price)
            viable = [o for o in in_stock if o.price > min_int_floor]
            if viable:
                return min(viable, key=lambda x: x.price)
        return min(in_stock, key=lambda x: x.price)
    any_ext = [o for o in offers if not is_non_competitor_vendor(o.vendor_name)]
    if any_ext:
        return min(any_ext, key=lambda x: x.price)
    return None


def _select_winning_modifier_meta(
    offers: list[ScrapedOffer],
    fallback_mod: str | None = None,
    fallback_src: str = "target",
    floor_price: float | None = None,
) -> tuple[str | None, str]:
    """Select (missing_modifier, modifier_source) from the winning reference offer.

    Considers ALL in-stock external offers (including exact matches with missing_modifier=None)
    so an exact single-color winner is never contaminated by a costlier Dual-Color listing,
    and prefers viable offers (> floor_price) over discarded sub-floor offers.
    """
    best = _select_winning_offer(offers, floor_price=floor_price)
    if best is not None:
        return best.missing_modifier, best.modifier_source
    return fallback_mod, fallback_src


def _select_winning_compatibility_notice(
    offers: list[ScrapedOffer],
    floor_price: float | None = None,
) -> str | None:
    """Select compatibility_notice from the winning external reference offer."""
    best = _select_winning_offer(offers, floor_price=floor_price)
    return best.compatibility_notice if best is not None else None


def _select_active_tier_pool(
    exact_offers: list[ScrapedOffer],
    base_offers: list[ScrapedOffer],
    sibling_offers: list[ScrapedOffer],
) -> list[ScrapedOffer]:
    """Return the highest-priority tier offer pool containing at least one in-stock offer."""
    if exact_offers and any(not o.is_sold_out for o in exact_offers):
        return exact_offers
    if base_offers and any(not o.is_sold_out for o in base_offers):
        return base_offers
    if sibling_offers and any(not o.is_sold_out for o in sibling_offers):
        return sibling_offers
    return exact_offers or base_offers or sibling_offers


def _select_winning_modifier(
    offers: list[ScrapedOffer],
    fallback_mod: str | None = None,
    floor_price: float | None = None,
) -> str | None:
    """Select the missing_modifier from the winning reference offer."""
    return _select_winning_modifier_meta(
        offers, fallback_mod=fallback_mod, floor_price=floor_price
    )[0]


def deduplicate_offers(offers: list[ScrapedOffer]) -> list[ScrapedOffer]:
    """Deduplicate offers by vendor key, price, color family, and variant, tracking duplicate counts and preserving metadata."""
    counts: dict[tuple[str, float, str, str], int] = {}
    first_seen: dict[tuple[str, float, str, str], ScrapedOffer] = {}
    for off in offers:
        key = _offer_dedupe_key(off)
        counts[key] = counts.get(key, 0) + (off.duplicate_count or 1)
        if (
            key not in first_seen
            or (first_seen[key].missing_modifier is not None and off.missing_modifier is None)
            or (
                first_seen[key].compatibility_notice is not None
                and off.compatibility_notice is None
            )
        ):
            first_seen[key] = off

    unique_offers: list[ScrapedOffer] = []
    for key, off in first_seen.items():
        total_dupes = counts[key]
        if total_dupes > 1:
            unique_offers.append(replace(off, duplicate_count=total_dupes))
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
    seen_base_offers: set[tuple[str, float, str, str]] = set()
    seen_sibling_offers: set[tuple[str, float, str, str]] = set()
    seen_own_offers: set[tuple[str, float, str, str]] = set()
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
    total_suspicious_rejected = 0
    max_pages_fetched = 1
    max_total_available: int | None = None
    all_pagination_complete = True
    collected_extended_designation: str | None = None

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
                    dedupe_key = _offer_dedupe_key(off)
                    if dedupe_key not in seen_base_offers:
                        seen_base_offers.add(dedupe_key)
                        collected_base_offers.append(off)

                for off in getattr(sub_res, "sibling_offers", []):
                    dedupe_key = _offer_dedupe_key(off)
                    if dedupe_key not in seen_sibling_offers:
                        seen_sibling_offers.add(dedupe_key)
                        collected_sibling_offers.append(off)

                for off in sub_res.own_offers:
                    dedupe_key = _offer_dedupe_key(off)
                    if dedupe_key not in seen_own_offers:
                        seen_own_offers.add(dedupe_key)
                        collected_own_offers.append(off)

                if sub_res.active_modifier_fallback and not detected_missing_modifier:
                    detected_missing_modifier = sub_res.active_modifier_fallback
                    detected_missing_source = sub_res.active_modifier_source

        tier_summary[tier_name] = tier_offers_count
        if tier_offers_count > 0 and matched_tier is None:
            matched_tier = tier_name
        instock_exact_count = sum(1 for o in collected_offers if not o.is_sold_out)
        if not exhaustive and instock_exact_count >= 2:
            break

    has_instock_exact = any(not o.is_sold_out for o in collected_offers)
    has_instock_base = any(not o.is_sold_out for o in collected_base_offers)
    has_instock_sibling = any(not o.is_sold_out for o in collected_sibling_offers)

    # Priority 1: Exact Tier 1 matches take precedence when in-stock (or when no lower tier has in-stock offers)
    if collected_offers and (
        has_instock_exact or (not has_instock_base and not has_instock_sibling)
    ):
        final_offers = collected_offers
        active_fallback, active_source = _select_winning_modifier_meta(
            collected_offers, None, "target", floor_price=floor_price
        )
        ambiguity = None
    elif collected_base_offers and (has_instock_base or not has_instock_sibling):
        # Priority 2: When zero in-stock exact matches exist, fallback to Tier 2 base model offers
        final_offers = collected_base_offers
        sel_mod, sel_src = _select_winning_modifier_meta(
            collected_base_offers,
            detected_missing_modifier,
            detected_missing_source,
            floor_price=floor_price,
        )
        active_fallback = sel_mod or "Base Model"
        active_source = sel_src if sel_mod else detected_missing_source
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
    elif collected_sibling_offers:
        # Priority 3: When zero in-stock exact or base matches exist, fallback to Tier 3 sibling sub-model offers
        final_offers = collected_sibling_offers
        sel_mod, sel_src = _select_winning_modifier_meta(
            collected_sibling_offers, None, "market", floor_price=floor_price
        )
        active_fallback = sel_mod
        active_source = sel_src
        ambiguity = None
    else:
        final_offers = []
        active_fallback = None
        active_source = "target"
        ambiguity = None

    final_compat_notice = _select_winning_compatibility_notice(
        final_offers, floor_price=floor_price
    )

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

    if not overall_success:
        discovery_status = DISCOVERY_SEARCH_FAILED
    elif any_failure and not has_viable_external_competitor:
        discovery_status = DISCOVERY_INCOMPLETE
    elif final_offers:
        discovery_status = DISCOVERY_COMPLETE_WITH_OFFERS
    elif not all_pagination_complete:
        discovery_status = DISCOVERY_PAGINATION_INCOMPLETE
    elif total_suspicious_rejected > 0 and not collected_own_offers:
        discovery_status = DISCOVERY_CANDIDATES_REJECTED
    else:
        discovery_status = DISCOVERY_COMPLETE_NO_COMPETITORS

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
        suspicious_rejected_count=total_suspicious_rejected,
        pages_fetched=max_pages_fetched,
        total_available=max_total_available,
        pagination_complete=all_pagination_complete,
        extended_model_designation=collected_extended_designation,
        compatibility_notice=final_compat_notice,
    )


def parse_price_value(price_raw: object) -> float:
    """Parse marketplace price strings (including 'Rs.', 'PKR', colons, commas, and '/-' suffixes) into finite float."""
    if isinstance(price_raw, bool):
        return 0.0
    if isinstance(price_raw, (int, float)):
        val = float(price_raw)
        return val if (math.isfinite(val) and val > 0.0) else 0.0
    s = str(price_raw or "").strip()
    if not s:
        return 0.0
    s_clean = re.sub(r"^(?:RS\.?|PKR)\s*:?\s*", "", s, flags=re.IGNORECASE)
    s_clean = re.sub(r"(?:\s*(?:RS\.?|PKR)\.?|/-+)+$", "", s_clean, flags=re.IGNORECASE)
    s_clean = s_clean.replace(",", "").strip()
    m_num = re.search(r"^\d+(?:\.\d+)?$", s_clean)
    if m_num:
        val = float(m_num.group(0))
        return val if (math.isfinite(val) and val > 0.0) else 0.0
    return 0.0


MAX_SEARCH_PAGES: int = 3

DEFINITIVE_REJECTION_PREFIXES: tuple[str, ...] = (
    "Appliance category collision",
    "AC form-factor collision",
    "Capacity / screen size mismatch",
    "SKU prefix collision",
    "Variant tag collision",
    "Generation series collision",
    "Inverter mode collision",
    "Operating mode collision",
    "Single-letter variant suffix collision",
    "Foreign brand mismatch",
)


def _has_viable_above_floor_offer(offers: list[ScrapedOffer], floor_price: float | None) -> bool:
    """Return True if any active external in-stock offer exceeds floor price."""
    if floor_price is None:
        return False
    min_int = math.ceil(floor_price)
    return any(
        not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name) and o.price > min_int
        for o in offers
    )


def _parse_offers_with_tiers(
    raw_items: list[dict[str, Any]],
    target_model: str,
    brand: str = "",
    target_desc: str = "",
    *,
    definitive_rejection: Callable[[MatchDecision], bool] | None = None,
) -> tuple[
    list[ScrapedOffer],
    list[ScrapedOffer],
    list[ScrapedOffer],
    str | None,
    list[ScrapedOffer],
    int,
    int,
    dict[str, int],
    int,
    str | None,
]:
    """Extract and validate Tier 1, Tier 2, Tier 3, and own-store offers with diagnostics."""
    exact_offers: list[ScrapedOffer] = []
    base_offers: list[ScrapedOffer] = []
    sibling_offers: list[ScrapedOffer] = []
    own_offers: list[ScrapedOffer] = []
    detected_modifier: str | None = None
    extended_designation: str | None = None
    raw_candidate_count: int = len(raw_items)
    rejected_count: int = 0
    rejection_reasons: dict[str, int] = {}
    suspicious_rejected_count: int = 0
    match_target = target_desc.strip() if target_desc and target_desc.strip() else target_model

    for item in raw_items:
        title = str(item.get("title", ""))
        decision = referee_match(match_target, title, brand=brand)
        effective_tier = decision.match_tier
        if effective_tier is None:
            if decision.is_match:
                effective_tier = 1
            elif decision.is_base_match:
                effective_tier = 2

        is_exact = effective_tier == 1
        is_base = effective_tier == 2
        is_sibling = effective_tier == 3

        sold_out = bool(item.get("sold_out", False))
        variant = item.get("variant_detail", {})
        price_str = variant.get("discounted_price") or variant.get("original_price") or "0"
        price = parse_price_value(price_str)

        vendor_obj = item.get("vendor") or {}
        vendor_handle = str(vendor_obj.get("handle") or "").strip()
        vendor = vendor_obj.get("name") or vendor_handle or "Unknown Vendor"
        is_non_comp = is_non_competitor_vendor(str(vendor)) or is_non_competitor_vendor(
            vendor_handle
        )

        if not is_exact and not is_base and not is_sibling:
            rejected_count += 1
            reason_category = decision.reason.split(":")[0].strip()
            rejection_reasons[reason_category] = rejection_reasons.get(reason_category, 0) + 1

            if price > 0 and not sold_out and not is_non_comp:
                is_definitive = any(
                    reason_category.startswith(p) for p in DEFINITIVE_REJECTION_PREFIXES
                )
                if definitive_rejection is not None:
                    is_definitive = definitive_rejection(decision)
                if not is_definitive:
                    title_upper = title.upper()
                    target_brand = brand.strip().upper()
                    brand_ok = not target_brand or target_brand in title_upper
                    if brand_ok:
                        target_clean = match_target.upper()
                        t_digits = re.findall(r"\d{2,}", target_clean)
                        shares_digits = (
                            any(d in title_upper for d in t_digits) if t_digits else False
                        )
                        target_words = set(re.findall(r"[A-Z0-9]+", target_clean))
                        common_stops = {
                            "TON",
                            "INVERTER",
                            "INV",
                            "AC",
                            "SPLIT",
                            "AIR",
                            "CONDITIONER",
                            "SERIES",
                            "WALL",
                            "MOUNT",
                        }
                        sig_words = {
                            w
                            for w in target_words
                            if len(w) >= 3 and w not in common_stops and w != target_brand
                        }
                        shares_series_word = any(w in title_upper for w in sig_words)
                        if shares_digits or shares_series_word:
                            suspicious_rejected_count += 1
            continue

        if price <= 0:
            continue

        item_handle = (
            str(item.get("handle") or item.get("slug") or item.get("id") or "").strip() or None
        )

        cand_var: str | None = None
        if (
            is_base
            and decision.missing_modifier
            and "candidate has variant suffix" in decision.reason.lower()
        ):
            raw_mod = decision.missing_modifier.strip()
            upper_mod = raw_mod.upper()
            if upper_mod.startswith("MARKET VARIANT "):
                cand_var = upper_mod.replace("MARKET VARIANT ", "").strip()
            elif upper_mod.startswith("VARIANT "):
                cand_var = upper_mod.replace("VARIANT ", "").strip()
            else:
                cand_var = upper_mod

        if decision.missing_modifier and "Extended Edition (" in decision.missing_modifier:
            m_ext = re.search(r"Extended Edition \(([^)]+)\)", decision.missing_modifier)
            if m_ext and not extended_designation:
                extended_designation = m_ext.group(1).strip()

        scraped_model_val = decision.candidate_slots.anchor if decision.candidate_slots else None
        color_family_val = (
            decision.candidate_slots.guarded_facets.color_family
            if decision.candidate_slots
            else None
        )

        offer = ScrapedOffer(
            vendor_name=str(vendor),
            price=price,
            is_sold_out=sold_out,
            raw_title=title,
            detected_variant=cand_var,
            missing_modifier=decision.missing_modifier,
            modifier_source=decision.modifier_source,
            product_handle=item_handle,
            scraped_model=scraped_model_val,
            color_family=color_family_val,
            match_tier=effective_tier,
            compatibility_notice=decision.compatibility_notice,
        )
        if is_non_comp:
            own_offers.append(offer)
        elif is_exact:
            exact_offers.append(offer)
        elif is_base:
            base_offers.append(offer)
        elif is_sibling:
            sibling_offers.append(offer)

    if base_offers:
        detected_modifier = _select_winning_modifier(base_offers, None)
    elif exact_offers:
        detected_modifier = _select_winning_modifier(exact_offers, None)
    elif sibling_offers:
        detected_modifier = _select_winning_modifier(sibling_offers, None)

    return (
        exact_offers,
        base_offers,
        sibling_offers,
        detected_modifier,
        own_offers,
        raw_candidate_count,
        rejected_count,
        rejection_reasons,
        suspicious_rejected_count,
        extended_designation,
    )


def _parse_offers_with_diagnostics(
    raw_items: list[dict[str, Any]],
    target_model: str,
    brand: str = "",
    target_desc: str = "",
) -> tuple[
    list[ScrapedOffer],
    list[ScrapedOffer],
    str | None,
    list[ScrapedOffer],
    int,
    int,
    dict[str, int],
    int,
    str | None,
]:
    """Extract and validate offers from raw API items array with structured rejection diagnostics."""
    (
        exact_offers,
        base_offers,
        _,
        detected_modifier,
        own_offers,
        raw_candidate_count,
        rejected_count,
        rejection_reasons,
        suspicious_rejected_count,
        extended_designation,
    ) = _parse_offers_with_tiers(
        raw_items, target_model, brand=brand, target_desc=target_desc
    )
    return (
        exact_offers,
        base_offers,
        detected_modifier,
        own_offers,
        raw_candidate_count,
        rejected_count,
        rejection_reasons,
        suspicious_rejected_count,
        extended_designation,
    )


def _parse_offers_from_raw_items(
    raw_items: list[dict[str, Any]],
    target_model: str,
    brand: str = "",
    target_desc: str = "",
) -> tuple[list[ScrapedOffer], list[ScrapedOffer], str | None, list[ScrapedOffer]]:
    """Extract and validate offers from raw API items array, maintaining 100% backward compatibility."""
    e, b, d, o, _, _, _, _, _ = _parse_offers_with_diagnostics(
        raw_items, target_model, brand=brand, target_desc=target_desc
    )
    return e, b, d, o


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
    cache_key = (
        config.platform_name,
        query.strip().upper(),
        (target_desc.strip() or target_model).upper(),
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
            raw_cached, target_model, brand=brand, target_desc=target_desc
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
                                raw_p, target_model, brand=brand, target_desc=target_desc
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
        o_cached = deduplicate_offers(o_cached)
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
                    raw_items, target_model, brand=brand, target_desc=target_desc
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
                                        raw_next, target_model, brand=brand, target_desc=target_desc
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
                own_offers = deduplicate_offers(own_offers)
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
                if exact_offers or base_offers or sibling_offers or own_offers:
                    _query_cache[cache_key] = result
                    if combined_raw_items:
                        _raw_items_cache[raw_cache_key] = combined_raw_items
                        _raw_items_meta_cache[raw_cache_key] = (total_count, pagination_complete)
                elif raw_items is not None and not raw_items:
                    _query_cache[cache_key] = result
                    _raw_items_cache[raw_cache_key] = []
                    _raw_items_meta_cache[raw_cache_key] = (0, True)

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
