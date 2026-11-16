"""Shared offer evidence, classification and finalization; no HTTP or pagination."""

import math
import re
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from pricing_engine.matcher import (
    MatchDecision,
    model_identity_parts,
    normalize_model_identity,
    referee_match,
)
from pricing_engine.models import (
    DISCOVERY_CANDIDATES_REJECTED,
    DISCOVERY_COMPLETE_NO_COMPETITORS,
    DISCOVERY_COMPLETE_WITH_OFFERS,
    DISCOVERY_PAGINATION_INCOMPLETE,
    DISCOVERY_SEARCH_FAILED,
    REJECTION_EXAMPLE_LIMIT,
    AmbiguousVariantConflict,
    RejectedCandidate,
    ScrapedOffer,
    ScrapeResult,
    is_non_competitor_vendor,
    resolve_non_competitor_kind,
)
from pricing_engine.series_fallback import (
    build_series_search,
    has_active_model_offers,
    referee_series_match,
)

OfferKey = tuple[str, float, str, str, str]


def offer_dedupe_key(off: ScrapedOffer) -> OfferKey:
    """Build deduplication key, preserving distinct color/variant listings even from the same vendor."""
    v_norm = off.vendor_name.lower().strip()
    if off.vendor_handle:
        v_norm = f"handle::{off.vendor_handle.casefold().strip()}"
    if not v_norm or v_norm == "unknown vendor":
        fallback_id = (off.product_handle or off.raw_title).lower().strip()
        v_norm = f"unknown::{fallback_id}"
    col = (off.color_family or "").lower().strip()
    var = (off.detected_variant or "").lower().strip()
    model = normalize_model_identity(off.scraped_model or "")
    identity = f"{off.brand_name.casefold()}:{model}"
    return (v_norm, round(off.price, 2), col, var, identity)


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
    """Deduplicate a complete evidence pool; retain raw query pools until finalization.

    Prefix consensus needs all observed identities. Do not fold partially merged
    results: an omitted prefix must never bridge two conflicting explicit ones.
    """
    counts: dict[OfferKey, int] = {}
    first_seen: dict[OfferKey, ScrapedOffer] = {}
    # Bare/optional-prefix spellings merge only when this pool has one possible
    # explicit prefix for that core. Conflicting prefixes never bridge via a bare SKU.
    prefixes: dict[tuple[str, float, str, str, str, str], set[str]] = {}
    for off in offers:
        prefix, core = model_identity_parts(off.scraped_model or "", off.brand_name)
        group = (*offer_dedupe_key(off)[:4], off.brand_name.casefold(), core)
        if prefix:
            prefixes.setdefault(group, set()).add(prefix)
    for off in offers:
        key = offer_dedupe_key(off)
        prefix, core = model_identity_parts(off.scraped_model or "", off.brand_name)
        group = (*key[:4], off.brand_name.casefold(), core)
        alternatives = prefixes.get(group, set())
        if core and len(alternatives) == 1:
            prefix = next(iter(alternatives))
        key = (*key[:4], f"{off.brand_name.casefold()}:{prefix}:{core}")
        counts[key] = counts.get(key, 0) + (off.duplicate_count or 1)

        def preference(offer: ScrapedOffer) -> tuple[bool, bool, int, bool, bool, tuple[str, ...]]:
            return (
                offer.is_sold_out,
                offer.match_basis == "series",
                offer.match_tier or 1,
                offer.missing_modifier is not None,
                offer.compatibility_notice is not None,
                (
                    offer.raw_title.casefold(),
                    offer.raw_title,
                    offer.product_handle or "",
                    offer.missing_modifier or "",
                    offer.compatibility_notice or "",
                    offer.modifier_source,
                    offer.scraped_model or "",
                    offer.vendor_name,
                    offer.brand_name,
                ),
            )

        if key not in first_seen or preference(off) < preference(first_seen[key]):
            first_seen[key] = off

    unique_offers: list[ScrapedOffer] = []
    for key, off in first_seen.items():
        total_dupes = counts[key]
        if total_dupes > 1:
            unique_offers.append(replace(off, duplicate_count=total_dupes))
        else:
            unique_offers.append(off)
    return sorted(unique_offers, key=lambda o: (o.is_sold_out, o.price, offer_dedupe_key(o)))


def _own_offer_identity_key(off: ScrapedOffer) -> tuple[str, ...]:
    """Build canonical listing identity key for own-store and official-store offers.

    Prioritizes stable marketplace product handle/ID so repeated appearances of the
    same listing across search tiers/queries collapse into one unique listing, while
    genuine distinct listings (different handles) remain separate.
    """
    v_norm = off.vendor_name.lower().strip()
    kind = resolve_non_competitor_kind(off) or "NON_COMP"
    handle = (off.product_handle or "").lower().strip()
    if handle:
        return ("handle", kind, v_norm, handle)
    norm_title = " ".join(off.raw_title.lower().split())
    col = (off.color_family or "").lower().strip()
    var = (off.detected_variant or "").lower().strip()
    return ("fallback", kind, v_norm, f"{round(off.price, 2):.2f}", norm_title, col, var)


def deduplicate_own_offers(offers: list[ScrapedOffer]) -> list[ScrapedOffer]:
    """Deduplicate own/official store offers by canonical listing identity and tier priority."""
    by_key: dict[tuple[str, ...], ScrapedOffer] = {}
    for off in offers:
        key = _own_offer_identity_key(off)
        clean_off = replace(off, duplicate_count=1) if off.duplicate_count != 1 else off
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = clean_off
            continue
        # Prefer in-stock over sold-out, and exact (Tier 1) over base fallback when stock status is equal
        existing_rank = (
            1 if existing.is_sold_out else 0,
            existing.match_basis == "series",
            existing.match_tier or 1,
            1 if existing.missing_modifier is not None else 0,
        )
        new_rank = (
            1 if clean_off.is_sold_out else 0,
            clean_off.match_basis == "series",
            clean_off.match_tier or 1,
            1 if clean_off.missing_modifier is not None else 0,
        )
        if new_rank < existing_rank:
            by_key[key] = clean_off

    unique = list(by_key.values())
    if not unique:
        return []

    # Per non-competitor vendor kind (OWN_STORE vs OFFICIAL_STORE), if any offer is an exact
    # Tier 1 match (with in-stock priority), discard lower-tier base fallback matches.
    filtered: list[ScrapedOffer] = []
    for kind in ("OWN_STORE", "OFFICIAL_STORE"):
        group = [o for o in unique if (resolve_non_competitor_kind(o) or "OWN_STORE") == kind]
        if not group:
            continue
        has_instock_any = any(not o.is_sold_out for o in group)
        exact_group = [o for o in group if (o.match_tier in (1, None))]
        has_instock_exact = any(not o.is_sold_out for o in exact_group)
        if exact_group and (has_instock_exact or not has_instock_any):
            filtered.extend(exact_group)
        else:
            filtered.extend(group)
    return filtered


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


def _has_viable_above_floor_offer(offers: list[ScrapedOffer], floor_price: float | None) -> bool:
    """Return True if any active external in-stock offer exceeds floor price."""
    if floor_price is None:
        return False
    min_int = math.ceil(floor_price)
    return any(
        not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name) and o.price > min_int
        for o in offers
    )


def _listing_brands(item: dict[str, Any]) -> set[str]:
    """Read explicit API brand metadata without guessing from product prose."""
    raw = item.get("brand") or []
    values = raw if isinstance(raw, list) else [raw]
    names: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            value = value.get("title") or value.get("name") or ""
        if isinstance(value, str) and value.strip():
            names.add(re.sub(r"[^a-z0-9]", "", value.casefold()))
    return names


def parse_offers_with_tiers(
    raw_items: list[dict[str, Any]],
    target_model: str,
    brand: str = "",
    target_desc: str = "",
    *,
    definitive_rejection: Callable[[MatchDecision], bool] | None = None,
    rejected_examples: list[RejectedCandidate] | None = None,
    query: str = "",
    series_fallback: bool = False,
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
    series_search = build_series_search(match_target, brand) if series_fallback else None

    for item in raw_items:
        title = str(item.get("title", ""))
        declared_brands = _listing_brands(item)
        brand_key = re.sub(r"[^a-z0-9]", "", brand.casefold())
        candidate_brand = (
            brand if brand_key in declared_brands else next(iter(sorted(declared_brands)), "")
        )
        decision = referee_match(match_target, title, brand=brand, candidate_brand=candidate_brand)
        if series_search and not (
            decision.is_match or decision.is_base_match or decision.match_tier == 3
        ):
            decision = referee_series_match(series_search, title, brand)
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
            if rejected_examples is not None:
                example = RejectedCandidate(
                    title=title,
                    model=decision.candidate_slots.anchor if decision.candidate_slots else "",
                    reason_code=decision.reason_code,
                    reason=decision.reason,
                    query=query,
                )
                if (
                    len(rejected_examples) < REJECTION_EXAMPLE_LIMIT
                    and example not in rejected_examples
                ):
                    rejected_examples.append(example)

            if price > 0 and not sold_out and not is_non_comp:
                is_definitive = decision.is_definitive_rejection
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

        cand_var = decision.detected_variant if is_base else None

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
            brand_name=brand.strip() or candidate_brand,
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
            match_basis=decision.match_basis,
            compatibility_notice=decision.compatibility_notice,
            vendor_handle=vendor_handle or None,
        )
        if is_non_comp:
            if not is_sibling:
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


def parse_offers_with_diagnostics(
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
    ) = parse_offers_with_tiers(raw_items, target_model, brand=brand, target_desc=target_desc)
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


def parse_offers_from_raw_items(
    raw_items: list[dict[str, Any]],
    target_model: str,
    brand: str = "",
    target_desc: str = "",
) -> tuple[list[ScrapedOffer], list[ScrapedOffer], str | None, list[ScrapedOffer]]:
    """Extract and validate offers from raw API items array, maintaining 100% backward compatibility."""
    e, b, d, o, _, _, _, _, _ = parse_offers_with_diagnostics(
        raw_items, target_model, brand=brand, target_desc=target_desc
    )
    return e, b, d, o


def finalize_offers(
    result: ScrapeResult, target_model: str, floor_price: float | None = None
) -> ScrapeResult:
    """Choose compatible evidence and warnings while preserving retrieval diagnostics."""
    collected_offers = deduplicate_offers(result.offers)
    collected_base_offers = result.base_offers
    collected_sibling_offers = deduplicate_offers(result.sibling_offers)
    collected_own_offers = result.own_offers
    detected_missing_modifier = result.active_modifier_fallback
    detected_missing_source = result.active_modifier_source
    collected_base_offers = deduplicate_offers(collected_base_offers)
    if has_active_model_offers(
        collected_offers, collected_base_offers, collected_sibling_offers, collected_own_offers
    ):
        collected_base_offers = [o for o in collected_base_offers if o.match_basis == "model"]
        collected_own_offers = [o for o in collected_own_offers if o.match_basis == "model"]

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

    collected_own_offers = deduplicate_own_offers(collected_own_offers)

    selected = replace(
        result,
        offers=final_offers,
        base_offers=collected_base_offers,
        sibling_offers=collected_sibling_offers,
        own_offers=collected_own_offers,
        active_modifier_fallback=active_fallback,
        active_modifier_source=active_source,
        ambiguity_conflict=ambiguity,
        compatibility_notice=final_compat_notice,
    )
    return replace(selected, discovery_status=classify_discovery(selected))


def classify_discovery(result: ScrapeResult) -> str:
    """Classify observed evidence after caller-specific transport health decisions."""
    if not result.is_success:
        return DISCOVERY_SEARCH_FAILED
    if result.offers:
        return DISCOVERY_COMPLETE_WITH_OFFERS
    if not result.pagination_complete:
        return DISCOVERY_PAGINATION_INCOMPLETE
    if result.suspicious_rejected_count > 0 and not result.own_offers:
        return DISCOVERY_CANDIDATES_REJECTED
    return DISCOVERY_COMPLETE_NO_COMPETITORS
