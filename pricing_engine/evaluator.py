import math
import re
from dataclasses import replace
from typing import Any

import config
from pricing_engine.calculator import (
    calculate_adaptive_target_price,
    find_winning_psychological_price,
    format_dynamic_retention_pct,
    get_fallback_psychological_price,
    get_monopoly_psychological_price,
)
from pricing_engine.models import (
    DISCOVERY_CANDIDATES_REJECTED,
    DISCOVERY_COMPLETE_NO_COMPETITORS,
    DISCOVERY_COMPLETE_WITH_OFFERS,
    DISCOVERY_INCOMPLETE,
    DISCOVERY_PAGINATION_INCOMPLETE,
    DISCOVERY_SEARCH_FAILED,
    STATUS_CANDIDATES_REJECTED,
    STATUS_INCOMPLETE_DISCOVERY,
    STATUS_SERVER_DOWN,
    CostFloors,
    MarketRange,
    PlatformPricingResult,
    ScrapedOffer,
    ScrapeResult,
    group_offers_by_vendor,
    is_non_competitor_vendor,
    resolve_non_competitor_kind,
)


def __getattr__(name: str) -> Any:
    if name == "MONOPOLY_PROFIT":
        return config.MONOPOLY_PROFIT_PKR
    if name == "FALLBACK_PROFIT":
        return config.FALLBACK_PROFIT_PKR
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def evaluate_market_range(offers: list[ScrapedOffer] | ScrapeResult) -> MarketRange:
    """Compute market min/max over in-stock offers with no floor filtering.

    Sold-out offers are ignored. A failed ScrapeResult yields ``is_down=True`` so callers
    never confuse an unreachable server with an empty market.
    """
    coverage_status = ""
    coverage_detail = ""
    if isinstance(offers, ScrapeResult):
        coverage_status = offers.coverage_status
        coverage_detail = offers.coverage_detail
        if not offers.is_success:
            return MarketRange(
                min_price=None,
                max_price=None,
                offer_count=0,
                is_down=True,
                error_detail=offers.error_detail or "HTTP Server/Network Error",
                coverage_status=coverage_status,
                coverage_detail=coverage_detail,
            )
        offer_list = offers.offers
    else:
        offer_list = list(offers)

    prices = [
        o.price
        for o in offer_list
        if not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
    ]
    if not prices:
        return MarketRange(
            min_price=None,
            max_price=None,
            offer_count=0,
            coverage_status=coverage_status,
            coverage_detail=coverage_detail,
        )
    return MarketRange(
        min_price=min(prices),
        max_price=max(prices),
        offer_count=len(prices),
        coverage_status=coverage_status,
        coverage_detail=coverage_detail,
    )


def format_fallback_descriptions(mod: str, source: str = "target") -> tuple[str, str, str]:
    """Generates (audit_text, reason_prefix, banner_text) for active modifier fallbacks."""
    if mod.startswith("Extended Edition (") or mod.startswith("Extended Designation ("):
        extracted_name = mod.split("(", 1)[1].rstrip(")")
        audit = f"⚠️ COMPATIBILITY NOTICE: Accepted extended designation '{extracted_name}'"
        reason = (
            f"[COMPATIBILITY NOTICE: Accepted legitimate extended model designation '{extracted_name}' — "
            f"verify edition/color alignment]"
        )
        banner = (
            f"[bold yellow]⚠️  COMPATIBILITY NOTICE (DO CROSS-CHECK):[/] Accepted legitimate extended model designation "
            f"[bold cyan]'{extracted_name}'[/] — verify edition/color alignment."
        )
        return audit, reason, banner
    if mod.startswith("Dual-Color"):
        audit = f"⚠️ {mod.upper()} LISTING MATCHED"
        reason = f"[CROSS-CHECK NOTICE: Matched combined {mod} marketplace listing]"
        banner = (
            f"[bold yellow]⚠️  NOTICE (DO CROSS-CHECK):[/] Matched combined [bold cyan]'{mod}'[/] "
            f"marketplace listing."
        )
        return audit, reason, banner
    if " vs " in mod:
        parts = mod.split(" vs ")
        t_part = parts[0].replace("Target ", "").strip("'\" ")
        m_part = parts[1].replace("Market ", "").strip("'\" ")
        audit = f"⚠️ VARIANT MISMATCH: Target '{t_part}' vs Market '{m_part}'"
        reason = (
            f"[FALLBACK MODEL: Target specified '{t_part}', but market listings specified '{m_part}'; "
            f"repriced against base model]"
        )
        banner = (
            f"[bold yellow]⚠️  NOTICE (DO CROSS-CHECK):[/] Target specified [bold cyan]'{t_part}'[/], "
            f"but marketplace listings have [bold cyan]'{m_part}'[/]. "
            f"Repriced against closest verified [bold green]base model[/] listings."
        )
    elif source == "market" or mod.startswith("Market Variant ") or mod.startswith("Market "):
        clean_name = mod.replace("Market Variant ", "").replace("Market ", "").strip("'\" ")
        audit = f"⚠️ MARKET VARIANT '{clean_name}' DETECTED"
        reason = (
            f"[FALLBACK MODEL: Marketplace listings specified '{clean_name}' (omitted in target); "
            f"repriced against base model]"
        )
        banner = (
            f"[bold yellow]⚠️  NOTICE (DO CROSS-CHECK):[/] Marketplace listings specified [bold cyan]'{clean_name}'[/] "
            f"(omitted in target). Repriced against verified [bold green]base model[/] listings."
        )
    else:
        audit = f"⚠️ MODIFIER '{mod}' OMITTED BY MARKET"
        reason = (
            f"[FALLBACK MODEL: Target specified '{mod}', but market listings omitted it; "
            f"repriced against base model]"
        )
        banner = (
            f"[bold yellow]⚠️  NOTICE (DO CROSS-CHECK):[/] Target specified [bold cyan]'{mod}'[/], "
            f"but marketplace listings omitted it. Repriced against verified [bold green]base model[/] listings."
        )
    return audit, reason, banner


def _resolve_active_fallback(
    offers: list[ScrapedOffer] | ScrapeResult,
    ref_offer: ScrapedOffer | None,
) -> tuple[str | None, str]:
    """Resolve (missing_modifier, modifier_source) from the actual reference offer chosen by the evaluator."""
    offer_list = offers.offers if isinstance(offers, ScrapeResult) else list(offers)
    has_per_offer_mod = any(o.missing_modifier is not None for o in offer_list)
    if ref_offer is not None and (ref_offer.missing_modifier is not None or has_per_offer_mod):
        return ref_offer.missing_modifier, ref_offer.modifier_source
    if isinstance(offers, ScrapeResult):
        return offers.active_modifier_fallback, offers.active_modifier_source
    return None, "target"


def _annotate_fallback_reason(
    res: PlatformPricingResult,
    active_fallback: str | None,
    active_source: str = "target",
) -> PlatformPricingResult:
    """Prepend explicit fallback/cross-check notification to pricing reason when modifier differs."""
    if active_fallback and res.status not in (STATUS_SERVER_DOWN, "Monopoly Win"):
        _, reason_prefix, _ = format_fallback_descriptions(active_fallback, source=active_source)
        new_reason = f"{reason_prefix} {res.reason}"
        return replace(res, reason=new_reason)
    return res


def _format_store_offer_fallback_suffix(offers_pool: list[ScrapedOffer]) -> str:
    """Return compact Tier 2 base-fallback label when all offers in pool lack an exact match."""
    if not offers_pool or not all(o.match_tier == 2 and o.missing_modifier for o in offers_pool):
        return ""
    mods = list(dict.fromkeys(str(o.missing_modifier).strip() for o in offers_pool if o.missing_modifier))
    return f" [Base Fallback: {', '.join(mods)}]" if mods else ""


def _format_store_group_tags(offers_group: list[ScrapedOffer]) -> list[str]:
    """Format non-competitor store listings concisely without repeating vendor names."""
    if not offers_group:
        return []
    if len(offers_group) == 1:
        o = offers_group[0]
        status_suffix = " (OUT OF STOCK)" if o.is_sold_out else ""
        fb_suffix = _format_store_offer_fallback_suffix([o])
        return [f"{o.vendor_name}{status_suffix}{fb_suffix} @ Rs. {o.price:,.0f}"]

    tags: list[str] = []
    for v_name, v_offs in group_offers_by_vendor(offers_group):
        if len(v_offs) == 1:
            o = v_offs[0]
            status_suffix = " (OUT OF STOCK)" if o.is_sold_out else ""
            fb_suffix = _format_store_offer_fallback_suffix([o])
            tags.append(f"{v_name}{status_suffix}{fb_suffix} @ Rs. {o.price:,.0f}")
        else:
            active_v_offs = [x for x in v_offs if not x.is_sold_out]
            price_pool = active_v_offs if active_v_offs else v_offs
            min_p = min(x.price for x in price_pool)
            max_p = max(x.price for x in price_pool)
            all_oos = not active_v_offs
            status_suffix = " (OUT OF STOCK)" if all_oos else ""
            fb_suffix = _format_store_offer_fallback_suffix(price_pool)
            price_str = (
                f"Rs. {min_p:,.0f}–{max_p:,.0f}"
                if round(min_p) != round(max_p)
                else f"Rs. {min_p:,.0f}"
            )
            tags.append(
                f"{v_name}{status_suffix}{fb_suffix} ({len(v_offs)} distinct listings: {price_str})"
            )
    return tags


def _annotate_non_competitor_reason(
    res: PlatformPricingResult, own_offers: list[ScrapedOffer]
) -> PlatformPricingResult:
    """Prepend explicit notification to pricing reason when own store or official store is active."""
    if not own_offers or res.status == STATUS_SERVER_DOWN:
        return res

    own_group: list[ScrapedOffer] = []
    official_group: list[ScrapedOffer] = []

    for o in own_offers:
        kind = resolve_non_competitor_kind(o)
        if kind == "OFFICIAL_STORE":
            official_group.append(o)
        else:
            own_group.append(o)

    own_tags = _format_store_group_tags(own_group)
    official_tags = _format_store_group_tags(official_group)

    prefix_parts: list[str] = []
    if own_tags:
        prefix_parts.append(f"[OWN STORE ACTIVE: {', '.join(own_tags)}]")
    if official_tags:
        prefix_parts.append(f"[OFFICIAL STORE: {', '.join(official_tags)}]")

    if prefix_parts:
        combined_prefix = " ".join(prefix_parts)
        new_reason = f"{combined_prefix} {res.reason}"
        return replace(res, reason=new_reason)

    return res


def _apply_compatibility_and_fallback_annotations(
    res: PlatformPricingResult,
    offers: list[ScrapedOffer] | ScrapeResult,
    ref_offer: ScrapedOffer | None,
) -> PlatformPricingResult:
    """Propagate canonical compatibility and fallback notices onto reason and result metadata."""
    suppressed_statuses = (
        STATUS_SERVER_DOWN,
        "Monopoly Win",
        STATUS_INCOMPLETE_DISCOVERY,
        STATUS_CANDIDATES_REJECTED,
    )
    if res.status in suppressed_statuses:
        return replace(res, compatibility_notice=None)

    active_fallback, active_source = _resolve_active_fallback(offers, ref_offer)
    offer_list = offers.offers if isinstance(offers, ScrapeResult) else list(offers)
    has_per_offer_compat = any(o.compatibility_notice is not None for o in offer_list)

    raw_compat_notice: str | None = None
    if ref_offer is not None and (ref_offer.compatibility_notice is not None or has_per_offer_compat):
        raw_compat_notice = ref_offer.compatibility_notice
    elif isinstance(offers, ScrapeResult) and offers.compatibility_notice:
        raw_compat_notice = offers.compatibility_notice
    elif isinstance(offers, ScrapeResult) and offers.extended_model_designation:
        raw_compat_notice = (
            f"Accepted legitimate extended model designation '{offers.extended_model_designation}' "
            f"— verify edition/color alignment"
        )
    elif active_fallback and (
        "Extended Edition (" in active_fallback or "Extended Designation (" in active_fallback
    ):
        extracted = active_fallback.split("(", 1)[1].rstrip(")")
        raw_compat_notice = (
            f"Accepted legitimate extended model designation '{extracted}' "
            f"— verify edition/color alignment"
        )

    if raw_compat_notice and (
        "[OPTIONAL SPECIFICATION:" in raw_compat_notice
        or "[SIBLING SUB-MODEL FALLBACK:" in raw_compat_notice
        or "but market listing is base model" in raw_compat_notice
    ):
        new_reason = (
            f"{raw_compat_notice} {res.reason}"
            if raw_compat_notice not in res.reason
            else res.reason
        )
        return replace(res, reason=new_reason, compatibility_notice=raw_compat_notice)

    res = _annotate_fallback_reason(res, active_fallback, active_source)

    if raw_compat_notice and "Accepted legitimate extended model designation" in raw_compat_notice:
        clean_compat = re.sub(r"^(?:⚠️|ℹ️)\s*", "", raw_compat_notice).strip()
        prefix = (
            raw_compat_notice
            if raw_compat_notice.startswith("[COMPATIBILITY NOTICE:")
            else f"[COMPATIBILITY NOTICE: {clean_compat}]"
        )
        if "[COMPATIBILITY NOTICE:" not in res.reason:
            res = replace(res, reason=f"{prefix} {res.reason}")
        return replace(res, compatibility_notice=raw_compat_notice)

    if raw_compat_notice:
        return replace(res, compatibility_notice=raw_compat_notice)
    return res


def evaluate_alfa_pricing(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float | None = None,
    max_profit_cap: float | None = None,
) -> PlatformPricingResult:
    """Evaluate pricing on AlfaMall strictly under configured ALFA_COMMISSION_PCT."""
    own_offers = offers.own_offers if isinstance(offers, ScrapeResult) else []
    res, ref_offer = _evaluate_platform_core(
        platform_label="AlfaMall",
        cost_floors=cost_floors,
        floor_min=cost_floors.floor_alfa,
        payout_rate=config.get_alfa_payout_rate(),
        comm_str=config.format_commission_pct(config.get_alfa_commission_pct()),
        extra_personal_comm=float(cost_floors.alfa_personal_comm),
        offers=offers,
        monopoly_profit=monopoly_profit,
        max_profit_cap=max_profit_cap,
    )
    res = replace(res, own_offers=own_offers)
    res = _apply_compatibility_and_fallback_annotations(res, offers, ref_offer)
    return _annotate_non_competitor_reason(res, own_offers)


def _format_winning_reason(
    gap: float,
    competitor_name: str,
    competitor_price: float,
    final_price: int,
    profit: int,
    dropped_prefix: str = "",
) -> str:
    """Format an informative winning reason when price is capped below uncapped undercut."""
    has_subfloor = bool(dropped_prefix and "sub-floor" in dropped_prefix.lower())

    if gap >= 10000.0:
        if has_subfloor:
            return (
                f"{dropped_prefix}Competitor {competitor_name} (Rs. {competitor_price:,.0f}) "
                f"price is inflated. Capped price at sweet-spot price Rs. {final_price:,.0f} "
                f"(+Rs. {profit:,} profit) for sales conversion."
            )
        return (
            f"{dropped_prefix}Competitor {competitor_name} (Rs. {competitor_price:,.0f}) "
            f"price is inflated. Capped price at winning sweet-spot price Rs. {final_price:,.0f} "
            f"(+Rs. {profit:,} profit) for sales conversion."
        )
    if gap >= 2000.0:
        pct_str = format_dynamic_retention_pct(gap)
        if has_subfloor:
            return (
                f"{dropped_prefix}Large price gap (Rs. {gap:,.0f}) above floor. Applied dynamic adaptive split ({pct_str}) "
                f"to capped sweet-spot price Rs. {final_price:,.0f} (+Rs. {profit:,} profit) for maximum conversion."
            )
        return (
            f"{dropped_prefix}Large price gap (Rs. {gap:,.0f}) above floor. Applied dynamic adaptive split ({pct_str}) "
            f"to capped winning sweet-spot price Rs. {final_price:,.0f} (+Rs. {profit:,} profit) for maximum conversion."
        )
    if gap >= 1500.0:
        if has_subfloor:
            return (
                f"{dropped_prefix}Applied Tier 3 discount (Rs. 500) below competitor {competitor_name} "
                f"(Rs. {competitor_price:,.0f}) to capped price Rs. {final_price:,.0f} "
                f"(+Rs. {profit:,} profit) to safeguard profit."
            )
        return (
            f"{dropped_prefix}Applied Tier 3 winning discount (Rs. 500) below competitor {competitor_name} "
            f"(Rs. {competitor_price:,.0f}) to winning price Rs. {final_price:,.0f} "
            f"(+Rs. {profit:,} profit) for high sales conversion."
        )
    if gap >= 800.0:
        if has_subfloor:
            return (
                f"{dropped_prefix}Applied Tier 4 discount (Rs. 200) below competitor {competitor_name} "
                f"(Rs. {competitor_price:,.0f}) to capped price Rs. {final_price:,.0f} "
                f"(+Rs. {profit:,} profit) to safeguard profit."
            )
        return (
            f"{dropped_prefix}Applied Tier 4 winning discount (Rs. 200) below competitor {competitor_name} "
            f"(Rs. {competitor_price:,.0f}) to winning price Rs. {final_price:,.0f} "
            f"(+Rs. {profit:,} profit) for high sales conversion."
        )
    if has_subfloor:
        return (
            f"{dropped_prefix}Undercut viable competitor {competitor_name} (Rs. {competitor_price:,.0f}) "
            f"to capped price Rs. {final_price:,.0f} (+Rs. {profit:,} profit)."
        )
    return (
        f"{dropped_prefix}Undercut viable competitor {competitor_name} (Rs. {competitor_price:,.0f}) "
        f"to winning price Rs. {final_price:,.0f} (+Rs. {profit:,} profit)."
    )


def _evaluate_platform_core(
    *,
    platform_label: str,
    cost_floors: CostFloors,
    floor_min: float,
    payout_rate: float,
    comm_str: str,
    extra_personal_comm: float,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float | None = None,
    max_profit_cap: float | None = None,
) -> tuple[PlatformPricingResult, ScrapedOffer | None]:
    """Evaluate pricing for one vendor strictly under its single configured commission rate.

    Rules:
    - If server is unreachable (500/timeout/WAF HTML), return Server Down status (no blind monopoly).
    - Discard out-of-stock and non-competitor offers.
    - If 0 active offers and server is healthy, set Monopoly price (or preserve incomplete discovery).
    - Discard sellers priced <= ceil(floor_min) (unviable loss-makers).
    - If no viable sellers remain, set Safe Fallback Price to ensure catalog upload.
    - Otherwise, strictly undercut the lowest viable competitor with an adaptive psychological price.
    """
    eff_monopoly_profit = (
        config.MONOPOLY_PROFIT_PKR if monopoly_profit is None else monopoly_profit
    )

    if isinstance(offers, ScrapeResult):
        scrape_success = offers.is_success
        error_detail = offers.error_detail
        offer_list = offers.offers
    else:
        scrape_success = True
        error_detail = None
        offer_list = list(offers)

    # Server Down / Unreachable Guard: Never set false Monopoly on network/server error
    if not scrape_success:
        err_msg = error_detail or "HTTP Server/Network Error"
        return (
            PlatformPricingResult(
                min_price=None,
                max_price=None,
                final_price=None,
                real_profit=0,
                status=STATUS_SERVER_DOWN,
                reason=(
                    f"{platform_label} search API unreachable ({err_msg}). "
                    "Skipped to prevent blind mispricing while server is down."
                ),
                dropped=[],
                active_pool=[],
                effective_comm=comm_str,
                discovery_status=DISCOVERY_SEARCH_FAILED,
            ),
            None,
        )

    active_offers = [
        o for o in offer_list if not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
    ]
    valid_prices = sorted(o.price for o in active_offers)

    market = evaluate_market_range(offer_list)
    min_p: float | None = market.min_price
    max_p: float | None = market.max_price

    floor_profit = (floor_min * payout_rate) - cost_floors.cost_base

    disc_status = (
        offers.discovery_status
        if isinstance(offers, ScrapeResult) and offers.discovery_status
        else (DISCOVERY_COMPLETE_WITH_OFFERS if valid_prices else DISCOVERY_COMPLETE_NO_COMPETITORS)
    )

    # Scenario 1: Zero competitors in market -> Monopoly Pricing or Incomplete Discovery Guard
    if not valid_prices:
        if isinstance(offers, ScrapeResult) and offers.discovery_status in (
            DISCOVERY_INCOMPLETE,
            DISCOVERY_SEARCH_FAILED,
            DISCOVERY_PAGINATION_INCOMPLETE,
        ):
            reason_detail = (
                f"{platform_label} search pagination incomplete or query timed out. "
                "Monopoly pricing suppressed to prevent blind mispricing."
            )
            return (
                PlatformPricingResult(
                    min_price=min_p,
                    max_price=max_p,
                    final_price=None,
                    real_profit=0,
                    status=STATUS_INCOMPLETE_DISCOVERY,
                    reason=reason_detail,
                    dropped=[],
                    active_pool=[],
                    effective_comm=comm_str,
                    discovery_status=offers.discovery_status,
                ),
                None,
            )

        if (
            isinstance(offers, ScrapeResult)
            and offers.discovery_status == DISCOVERY_CANDIDATES_REJECTED
        ):
            top_reasons = sorted(
                offers.rejection_reasons.items(), key=lambda x: x[1], reverse=True
            )[:2]
            reasons_summary = (
                ", ".join(f"{count}x {cat}" for cat, count in top_reasons)
                if top_reasons
                else f"{offers.rejected_count} candidates rejected"
            )
            reason_detail = (
                f"Competitor candidates found ({offers.rejected_count} total) but all rejected by referee ({reasons_summary}). "
                "Monopoly pricing suppressed to prevent blind mispricing."
            )
            return (
                PlatformPricingResult(
                    min_price=min_p,
                    max_price=max_p,
                    final_price=None,
                    real_profit=0,
                    status=STATUS_CANDIDATES_REJECTED,
                    reason=reason_detail,
                    dropped=[],
                    active_pool=[],
                    effective_comm=comm_str,
                    discovery_status=DISCOVERY_CANDIDATES_REJECTED,
                ),
                None,
            )

        eff_monopoly = (
            max(eff_monopoly_profit, floor_profit + 1000.0)
            if extra_personal_comm > 0
            else eff_monopoly_profit
        )
        raw_target = (cost_floors.cost_base + eff_monopoly) / payout_rate
        monopoly_p = get_monopoly_psychological_price(raw_target)
        profit = round((monopoly_p * payout_rate) - cost_floors.cost_base)
        return (
            PlatformPricingResult(
                min_price=min_p,
                max_price=max_p,
                final_price=monopoly_p,
                real_profit=profit,
                status="Monopoly Win",
                reason=f"No competitors found in market. Applied Monopoly pricing (+Rs. {eff_monopoly:,.0f} target margin).",
                dropped=[],
                active_pool=[],
                effective_comm=comm_str,
                discovery_status=DISCOVERY_COMPLETE_NO_COMPETITORS,
            ),
            None,
        )

    # Discard loss makers (sellers <= ceil(floor) cannot be profitably undercut by an integer >= floor)
    min_int_floor = math.ceil(floor_min)
    dropped = [o for o in active_offers if o.price <= min_int_floor]
    viable = [o for o in active_offers if o.price > min_int_floor]

    # Scenario 2: All competitors below floor -> Safe Fallback to enable catalog upload
    if not viable:
        lowest_dropped_obj = min(dropped, key=lambda x: x.price)
        lowest_dropped = lowest_dropped_obj.price
        final_fallback_p = get_fallback_psychological_price(
            cost_base=cost_floors.cost_base,
            floor_min=floor_min,
            payout_rate=payout_rate,
            profit_target=config.FALLBACK_PROFIT_PKR + extra_personal_comm,
        )
        profit = round((final_fallback_p * payout_rate) - cost_floors.cost_base)
        return (
            PlatformPricingResult(
                min_price=min_p,
                max_price=max_p,
                final_price=final_fallback_p,
                real_profit=profit,
                status="Safe Fallback",
                reason=(
                    f"All competitors are selling at a loss (< Floor Rs. {round(floor_min):,}, "
                    f"lowest: {lowest_dropped_obj.vendor_name} Rs. {lowest_dropped:,.0f}). Undercut skipped to prevent loss. "
                    f"Listed at Safe Fallback Price Rs. {final_fallback_p:,.0f} (+Rs. {profit:,} profit) to ensure catalog upload."
                ),
                dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
                active_pool=[],
                effective_comm=comm_str,
                discovery_status=disc_status,
            ),
            lowest_dropped_obj,
        )

    # Scenario 3: Undercut lowest viable seller
    sorted_viable = sorted(viable, key=lambda x: x.price)
    lowest_viable = sorted_viable[0]
    large_cap = (
        max_profit_cap
        if max_profit_cap is not None
        else (config.LARGE_GAP_PROFIT_CAP_PKR + extra_personal_comm)
    )
    final_p: int | None = None
    for candidate in sorted_viable:
        target_adaptive = calculate_adaptive_target_price(
            floor_min=floor_min,
            competitor_price=candidate.price,
            cost_base=cost_floors.cost_base,
            payout_rate=payout_rate,
            large_gap_profit_target=large_cap,
        )
        candidate_p = find_winning_psychological_price(
            floor_min, candidate.price, max_ceiling=target_adaptive
        )
        if candidate_p is not None:
            lowest_viable = candidate
            final_p = candidate_p
            break

    if final_p is None:
        return (
            PlatformPricingResult(
                min_price=min_p,
                max_price=max_p,
                final_price=None,
                real_profit=0,
                status="Skip / Unviable",
                reason="Tight competitor margin prevented psychological undercut above floor. Skipped to prevent loss.",
                dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
                active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable],
                effective_comm=comm_str,
                discovery_status=disc_status,
            ),
            lowest_viable,
        )

    profit = round((final_p * payout_rate) - cost_floors.cost_base)
    dropped_prefix = f"Filtered {len(dropped)} sub-floor offer(s). " if dropped else ""
    gap = lowest_viable.price - floor_min
    uncapped_p = find_winning_psychological_price(floor_min, lowest_viable.price)
    if gap < 100.0:
        reason = (
            f"{dropped_prefix}Competitor {lowest_viable.vendor_name} "
            f"(Rs. {lowest_viable.price:,.0f}) gap is tight. Undercut to winning rounded price "
            f"Rs. {final_p:,.0f} with guaranteed +Rs. {profit:,} profit."
        )
    elif uncapped_p is not None and final_p < uncapped_p:
        reason = _format_winning_reason(
            gap=gap,
            competitor_name=lowest_viable.vendor_name,
            competitor_price=lowest_viable.price,
            final_price=final_p,
            profit=profit,
            dropped_prefix=dropped_prefix,
        )
    else:
        reason = (
            f"{dropped_prefix}Undercut viable competitor {lowest_viable.vendor_name} "
            f"(Rs. {lowest_viable.price:,.0f}) to capped price Rs. {final_p:,.0f}."
            if dropped
            else f"Undercut lowest competitor {lowest_viable.vendor_name} (Rs. {lowest_viable.price:,.0f}) to winning price Rs. {final_p:,.0f}."
        )
    return (
        PlatformPricingResult(
            min_price=min_p,
            max_price=max_p,
            final_price=final_p,
            real_profit=profit,
            status="Competitive Win",
            reason=reason,
            dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
            active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable],
            effective_comm=comm_str,
            discovery_status=disc_status,
        ),
        lowest_viable,
    )


def evaluate_digi_pricing(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float | None = None,
    max_profit_cap: float | None = None,
) -> PlatformPricingResult:
    """Evaluate pricing on DigiMall with automatic fallback and own-store reason annotations."""
    from pricing_engine.models import PROVISIONAL_COVERAGES

    if isinstance(offers, ScrapeResult):
        successful_scan = offers.is_success and offers.coverage_status in {"COMPLETE", "CAPPED"}
        eligible = any(not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
                       for o in offers.offers)
        if successful_scan and not eligible:
            # Rejected listings are not competitors under the selected Digi policy.
            offers = replace(offers, discovery_status=DISCOVERY_COMPLETE_NO_COMPETITORS)
        elif offers.coverage_status in PROVISIONAL_COVERAGES:
            offers = replace(offers, discovery_status=DISCOVERY_PAGINATION_INCOMPLETE)
    own_offers = offers.own_offers if isinstance(offers, ScrapeResult) else []
    res, ref_offer = _evaluate_platform_core(
        platform_label="DigiMall",
        cost_floors=cost_floors,
        floor_min=cost_floors.floor_digi,
        payout_rate=config.get_digi_payout_rate(),
        comm_str=config.format_commission_pct(config.get_digi_commission_pct()),
        extra_personal_comm=float(cost_floors.digi_personal_comm),
        offers=offers,
        monopoly_profit=monopoly_profit,
        max_profit_cap=max_profit_cap,
    )
    res = replace(res, own_offers=own_offers)
    res = _apply_compatibility_and_fallback_annotations(res, offers, ref_offer)
    res = _annotate_non_competitor_reason(res, own_offers)
    if isinstance(offers, ScrapeResult) and offers.coverage_status:
        res = replace(
            res, coverage_status=offers.coverage_status, coverage_detail=offers.coverage_detail
        )
        capped_monopoly = offers.coverage_status == "CAPPED" and res.status == "Monopoly Win"
        candidate_review = res.status == STATUS_CANDIDATES_REJECTED
        if offers.coverage_status in PROVISIONAL_COVERAGES and not capped_monopoly and not candidate_review:
            res = replace(
                res,
                status=(
                    "Provisional Price"
                    if res.final_price is not None
                    else STATUS_INCOMPLETE_DISCOVERY
                ),
                reason=f"Provisional observed pricing ({offers.coverage_status}). {res.reason}",
            )
        if offers.coverage_status == "CAPPED":
            if capped_monopoly:
                res = replace(res, status="Monopoly — Observed (3-page scan)",
                              reason="Not found: no compatible in-stock competitors in inspected results. Applied existing monopoly pricing (3-page scan).")
            elif res.final_price is not None:
                res = replace(res, status="Observed Price (3-page scan)",
                              reason=res.reason.replace("Provisional observed pricing (CAPPED).", "Observed pricing within successful 3-page scan (CAPPED)."))
            elif not candidate_review:
                res = replace(res, reason="No compatible in-stock competitor found in inspected results. Scan limit reached; no monopoly price applied.")
        elif offers.coverage_status == "UNKNOWN" and res.final_price is None:
            res = replace(res, reason="Search count unavailable. No compatible in-stock competitor found; no monopoly price applied.")
    return res



