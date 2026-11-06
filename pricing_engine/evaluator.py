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
    classify_non_competitor_vendor,
    is_non_competitor_vendor,
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


def _annotate_non_competitor_reason(
    res: PlatformPricingResult, own_offers: list[ScrapedOffer]
) -> PlatformPricingResult:
    """Prepend explicit notification to pricing reason when own store or official store is active."""
    if not own_offers or res.status == STATUS_SERVER_DOWN:
        return res

    own_tags: list[str] = []
    official_tags: list[str] = []

    for o in own_offers:
        kind = classify_non_competitor_vendor(o.vendor_name)
        status_suffix = " (OUT OF STOCK)" if o.is_sold_out else ""
        tag_str = f"{o.vendor_name}{status_suffix} @ Rs. {o.price:,.0f}"
        if kind == "OFFICIAL_STORE":
            official_tags.append(tag_str)
        else:
            own_tags.append(tag_str)

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
    """Evaluate pricing on AlfaMall with automatic fallback and own-store reason annotations."""
    own_offers = offers.own_offers if isinstance(offers, ScrapeResult) else []
    res, ref_offer = _evaluate_alfa_core(
        cost_floors=cost_floors,
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
    bank_note: str = "",
) -> str:
    """Format an informative winning reason when price is capped below uncapped undercut."""
    has_subfloor = bool(dropped_prefix and "sub-floor" in dropped_prefix.lower())

    if gap >= 10000.0:
        if has_subfloor:
            return (
                f"{dropped_prefix}Competitor {competitor_name} (Rs. {competitor_price:,.0f}) "
                f"price is inflated. Capped price at sweet-spot price Rs. {final_price:,.0f} "
                f"(+Rs. {profit:,} profit{bank_note}) for sales conversion."
            )
        return (
            f"{dropped_prefix}Competitor {competitor_name} (Rs. {competitor_price:,.0f}) "
            f"price is inflated. Capped price at winning sweet-spot price Rs. {final_price:,.0f} "
            f"(+Rs. {profit:,} profit{bank_note}) for sales conversion."
        )
    if gap >= 2000.0:
        pct_str = format_dynamic_retention_pct(gap)
        if has_subfloor:
            return (
                f"{dropped_prefix}Large price gap (Rs. {gap:,.0f}) above floor. Applied dynamic adaptive split ({pct_str}) "
                f"to capped sweet-spot price Rs. {final_price:,.0f} (+Rs. {profit:,} profit{bank_note}) for maximum conversion."
            )
        return (
            f"{dropped_prefix}Large price gap (Rs. {gap:,.0f}) above floor. Applied dynamic adaptive split ({pct_str}) "
            f"to capped winning sweet-spot price Rs. {final_price:,.0f} (+Rs. {profit:,} profit{bank_note}) for maximum conversion."
        )
    if gap >= 1500.0:
        if has_subfloor:
            return (
                f"{dropped_prefix}Applied Tier 3 discount (Rs. 500) below competitor {competitor_name} "
                f"(Rs. {competitor_price:,.0f}) to capped price Rs. {final_price:,.0f} "
                f"(+Rs. {profit:,} profit{bank_note}) to safeguard profit."
            )
        return (
            f"{dropped_prefix}Applied Tier 3 winning discount (Rs. 500) below competitor {competitor_name} "
            f"(Rs. {competitor_price:,.0f}) to winning price Rs. {final_price:,.0f} "
            f"(+Rs. {profit:,} profit{bank_note}) for high sales conversion."
        )
    if gap >= 800.0:
        if has_subfloor:
            return (
                f"{dropped_prefix}Applied Tier 4 discount (Rs. 200) below competitor {competitor_name} "
                f"(Rs. {competitor_price:,.0f}) to capped price Rs. {final_price:,.0f} "
                f"(+Rs. {profit:,} profit{bank_note}) to safeguard profit."
            )
        return (
            f"{dropped_prefix}Applied Tier 4 winning discount (Rs. 200) below competitor {competitor_name} "
            f"(Rs. {competitor_price:,.0f}) to winning price Rs. {final_price:,.0f} "
            f"(+Rs. {profit:,} profit{bank_note}) for high sales conversion."
        )
    if has_subfloor:
        return (
            f"{dropped_prefix}Undercut viable competitor {competitor_name} (Rs. {competitor_price:,.0f}) "
            f"to capped price Rs. {final_price:,.0f} (+Rs. {profit:,} profit{bank_note})."
        )
    return (
        f"{dropped_prefix}Undercut viable competitor {competitor_name} (Rs. {competitor_price:,.0f}) "
        f"to winning price Rs. {final_price:,.0f} (+Rs. {profit:,} profit{bank_note})."
    )


def _evaluate_alfa_core(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float | None = None,
    max_profit_cap: float | None = None,
) -> tuple[PlatformPricingResult, ScrapedOffer | None]:
    """Evaluate pricing on AlfaMall under configured platform commission rules.

    Rules:
    - If server is unreachable (500/timeout/WAF HTML), return Server Down status (no blind monopoly).
    - Discard out-of-stock items.
    - If 0 active offers and server is healthy, set Monopoly price (+Rs. 4,000 margin).
    - Discard sellers priced <= ceil(floor_alfa) (unviable loss-makers).
    - If no viable sellers remain, set Safe Fallback Price (+Rs. 1,500 profit) to ensure upload.
    - Otherwise, strictly undercut lowest viable competitor with psychological price.
    """
    eff_monopoly_profit = (
        config.MONOPOLY_PROFIT_PKR if monopoly_profit is None else monopoly_profit
    )
    alfa_payout = config.get_alfa_payout_rate()
    alfa_comm_str = f"{config.ALFA_COMMISSION_PCT:.2f}%"

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
                    f"AlfaMall search API unreachable ({err_msg}). "
                    "Skipped to prevent blind mispricing while server is down."
                ),
                dropped=[],
                active_pool=[],
                effective_comm=alfa_comm_str,
                discovery_status=DISCOVERY_SEARCH_FAILED,
            ),
            None,
        )

    active_offers = [
        o for o in offer_list if not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
    ]
    valid_prices = sorted([o.price for o in active_offers])

    market = evaluate_market_range(offer_list)
    min_p: float | None = market.min_price
    max_p: float | None = market.max_price

    floor_profit_alfa = (cost_floors.floor_alfa * alfa_payout) - cost_floors.cost_base
    extra_personal_comm_alfa = float(cost_floors.alfa_personal_comm)

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
                "AlfaMall search pagination incomplete or query timed out. "
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
                    effective_comm=alfa_comm_str,
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
                    effective_comm=alfa_comm_str,
                    discovery_status=DISCOVERY_CANDIDATES_REJECTED,
                ),
                None,
            )

        eff_monopoly_alfa = (
            max(eff_monopoly_profit, floor_profit_alfa + 1000.0)
            if extra_personal_comm_alfa > 0
            else eff_monopoly_profit
        )
        raw_target = (cost_floors.cost_base + eff_monopoly_alfa) / alfa_payout
        monopoly_p = get_monopoly_psychological_price(raw_target)
        profit = round((monopoly_p * alfa_payout) - cost_floors.cost_base)
        return (
            PlatformPricingResult(
                min_price=min_p,
                max_price=max_p,
                final_price=monopoly_p,
                real_profit=profit,
                status="Monopoly Win",
                reason=f"No competitors found in market. Applied Monopoly pricing (+Rs. {eff_monopoly_alfa:,.0f} target margin).",
                dropped=[],
                active_pool=[],
                effective_comm=alfa_comm_str,
                discovery_status=DISCOVERY_COMPLETE_NO_COMPETITORS,
            ),
            None,
        )

    # Discard loss makers (sellers <= ceil(floor) cannot be profitably undercut by an integer >= floor)
    min_int_alfa = math.ceil(cost_floors.floor_alfa)
    dropped = [o for o in active_offers if o.price <= min_int_alfa]
    viable = [o for o in active_offers if o.price > min_int_alfa]

    # Scenario 2: All competitors below floor -> Safe Fallback to enable catalog upload
    if not viable:
        lowest_dropped_obj = min(dropped, key=lambda x: x.price)
        lowest_dropped = lowest_dropped_obj.price
        final_fallback_p = get_fallback_psychological_price(
            cost_base=cost_floors.cost_base,
            floor_min=cost_floors.floor_alfa,
            payout_rate=alfa_payout,
            profit_target=config.FALLBACK_PROFIT_PKR + extra_personal_comm_alfa,
        )
        profit = round((final_fallback_p * alfa_payout) - cost_floors.cost_base)
        return (
            PlatformPricingResult(
                min_price=min_p,
                max_price=max_p,
                final_price=final_fallback_p,
                real_profit=profit,
                status="Safe Fallback",
                reason=(
                    f"All competitors are selling at a loss (< Floor Rs. {round(cost_floors.floor_alfa):,}, "
                    f"lowest: {lowest_dropped_obj.vendor_name} Rs. {lowest_dropped:,.0f}). Undercut skipped to prevent loss. "
                    f"Listed at Safe Fallback Price Rs. {final_fallback_p:,.0f} (+Rs. {profit:,} profit) to ensure catalog upload."
                ),
                dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
                active_pool=[],
                effective_comm=alfa_comm_str,
                discovery_status=disc_status,
            ),
            lowest_dropped_obj,
        )

    # Scenario 3: Undercut lowest viable seller
    lowest_viable = min(viable, key=lambda x: x.price)
    large_cap_alfa = (
        max_profit_cap
        if max_profit_cap is not None
        else (config.LARGE_GAP_PROFIT_CAP_PKR + extra_personal_comm_alfa)
    )
    target_adaptive_alfa = calculate_adaptive_target_price(
        floor_min=cost_floors.floor_alfa,
        competitor_price=lowest_viable.price,
        cost_base=cost_floors.cost_base,
        payout_rate=alfa_payout,
        large_gap_profit_target=large_cap_alfa,
    )
    final_p: int | None = find_winning_psychological_price(
        cost_floors.floor_alfa, lowest_viable.price, max_ceiling=target_adaptive_alfa
    )

    if final_p is None:
        # If psychological search couldn't beat lowest, try next higher viable seller
        for higher_viable in sorted(viable, key=lambda x: x.price)[1:]:
            target_adaptive_alfa = calculate_adaptive_target_price(
                floor_min=cost_floors.floor_alfa,
                competitor_price=higher_viable.price,
                cost_base=cost_floors.cost_base,
                payout_rate=alfa_payout,
                large_gap_profit_target=large_cap_alfa,
            )
            final_p = find_winning_psychological_price(
                cost_floors.floor_alfa, higher_viable.price, max_ceiling=target_adaptive_alfa
            )
            if final_p is not None:
                lowest_viable = higher_viable
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
                effective_comm=alfa_comm_str,
                discovery_status=disc_status,
            ),
            lowest_viable,
        )

    profit = round((final_p * alfa_payout) - cost_floors.cost_base)
    dropped_prefix = f"Filtered {len(dropped)} sub-floor offer(s). " if dropped else ""
    uncapped_p = find_winning_psychological_price(cost_floors.floor_alfa, lowest_viable.price)
    if uncapped_p is not None and final_p < uncapped_p:
        gap = lowest_viable.price - cost_floors.floor_alfa
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
            effective_comm=alfa_comm_str,
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
    res, ref_offer = _evaluate_digi_core(
        cost_floors=cost_floors,
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


def _evaluate_digi_core(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float | None = None,
    max_profit_cap: float | None = None,
) -> tuple[PlatformPricingResult, ScrapedOffer | None]:
    """Evaluate pricing on DigiMall with Two-Tier Commission Switch (10% -> 8%)."""
    eff_monopoly_profit = (
        config.MONOPOLY_PROFIT_PKR if monopoly_profit is None else monopoly_profit
    )
    digi_std_payout = config.get_digi_standard_payout_rate()
    digi_lev_payout = config.get_digi_leverage_payout_rate()
    digi_std_comm_str = f"{config.DIGI_STANDARD_COMMISSION_PCT:.2f}%"
    digi_lev_comm_str = f"{config.DIGI_LEVERAGE_COMMISSION_PCT:.2f}%"

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
                    f"DigiMall search API unreachable ({err_msg}). "
                    "Skipped to prevent blind mispricing while server is down."
                ),
                dropped=[],
                active_pool=[],
                effective_comm=digi_lev_comm_str,
                discovery_status=DISCOVERY_SEARCH_FAILED,
            ),
            None,
        )

    active_offers = [
        o for o in offer_list if not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
    ]
    valid_prices = sorted([o.price for o in active_offers])

    market = evaluate_market_range(offer_list)
    min_p: float | None = market.min_price
    max_p: float | None = market.max_price

    floor_profit_digi = (cost_floors.floor_digi_10 * digi_std_payout) - cost_floors.cost_base
    extra_personal_comm_digi = float(cost_floors.digi_personal_comm)

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
                "DigiMall search pagination incomplete or query timed out. "
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
                    effective_comm=digi_lev_comm_str,
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
                    effective_comm=digi_lev_comm_str,
                    discovery_status=DISCOVERY_CANDIDATES_REJECTED,
                ),
                None,
            )

        eff_monopoly_digi = (
            max(eff_monopoly_profit, floor_profit_digi + 1000.0)
            if extra_personal_comm_digi > 0
            else eff_monopoly_profit
        )
        raw_target = (cost_floors.cost_base + eff_monopoly_digi) / digi_std_payout
        monopoly_p = get_monopoly_psychological_price(raw_target)
        profit = round((monopoly_p * digi_lev_payout) - cost_floors.cost_base)
        return (
            PlatformPricingResult(
                min_price=min_p,
                max_price=max_p,
                final_price=monopoly_p,
                real_profit=profit,
                status="Monopoly Win",
                reason=f"No competitors found in market. Applied Monopoly {digi_std_comm_str} baseline pricing and captured extra bank spread profit via {digi_lev_comm_str} Faysal Bank rate.",
                dropped=[],
                active_pool=[],
                effective_comm=digi_std_comm_str,
                discovery_status=DISCOVERY_COMPLETE_NO_COMPETITORS,
            ),
            None,
        )

    lowest_offer = min(active_offers, key=lambda x: x.price)
    large_cap = (
        max_profit_cap
        if max_profit_cap is not None
        else (config.LARGE_GAP_PROFIT_CAP_PKR + extra_personal_comm_digi)
    )
    min_int_digi_10 = math.ceil(cost_floors.floor_digi_10)
    min_int_digi_8 = math.ceil(cost_floors.floor_digi_8)

    # Step A: Check Default 10% Tier
    if lowest_offer.price > min_int_digi_10:
        gap_10 = lowest_offer.price - cost_floors.floor_digi_10
        target_adaptive_10 = calculate_adaptive_target_price(
            floor_min=cost_floors.floor_digi_10,
            competitor_price=lowest_offer.price,
            cost_base=cost_floors.cost_base,
            payout_rate=digi_lev_payout,
            large_gap_profit_target=large_cap,
        )
        final_p_10: int | None = find_winning_psychological_price(
            cost_floors.floor_digi_10, lowest_offer.price, max_ceiling=target_adaptive_10
        )
        if final_p_10 is not None:
            profit = round((final_p_10 * digi_lev_payout) - cost_floors.cost_base)
            uncapped_p = find_winning_psychological_price(
                cost_floors.floor_digi_10, lowest_offer.price
            )
            if uncapped_p is not None and final_p_10 < uncapped_p:
                reason = _format_winning_reason(
                    gap=gap_10,
                    competitor_name=lowest_offer.vendor_name,
                    competitor_price=lowest_offer.price,
                    final_price=final_p_10,
                    profit=profit,
                    bank_note=" on 8% Faysal Bank rate",
                )
            else:
                reason = (
                    f"Lowest competitor {lowest_offer.vendor_name} (Rs. {lowest_offer.price:,.0f}) "
                    f"is above 10% floor. Won at 10% tier with 8% Faysal Bank rate (+Rs. {profit:,} profit incl. 2% bank spread)."
                )
            return (
                PlatformPricingResult(
                    min_price=min_p,
                    max_price=max_p,
                    final_price=final_p_10,
                    real_profit=profit,
                    status="Safe Win (10% Tier)",
                    reason=reason,
                    dropped=[],
                    active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in active_offers],
                    effective_comm=digi_std_comm_str,
                    discovery_status=disc_status,
                ),
                lowest_offer,
            )

    # Step B: Emergency 8% Bank Rate Switch
    if lowest_offer.price > min_int_digi_8:
        gap_8 = lowest_offer.price - cost_floors.floor_digi_8
        target_adaptive_8 = calculate_adaptive_target_price(
            floor_min=cost_floors.floor_digi_8,
            competitor_price=lowest_offer.price,
            cost_base=cost_floors.cost_base,
            payout_rate=digi_lev_payout,
            large_gap_profit_target=large_cap,
        )
        final_p_8: int | None = find_winning_psychological_price(
            cost_floors.floor_digi_8, lowest_offer.price, max_ceiling=target_adaptive_8
        )
        if final_p_8 is not None:
            profit = round((final_p_8 * digi_lev_payout) - cost_floors.cost_base)
            if gap_8 < 100.0:
                reason = (
                    f"Unviable at 10% floor (Rs. {round(cost_floors.floor_digi_10):,}). "
                    f"Triggered emergency 8% Faysal Bank rate. Competitor {lowest_offer.vendor_name} (Rs. {lowest_offer.price:,.0f}) "
                    f"gap is tight. Undercut to winning rounded price Rs. {final_p_8:,.0f} with guaranteed +Rs. {profit:,} profit."
                )
            else:
                uncapped_p = find_winning_psychological_price(
                    cost_floors.floor_digi_8, lowest_offer.price
                )
                if uncapped_p is not None and final_p_8 < uncapped_p:
                    reason = _format_winning_reason(
                        gap=gap_8,
                        competitor_name=lowest_offer.vendor_name,
                        competitor_price=lowest_offer.price,
                        final_price=final_p_8,
                        profit=profit,
                        dropped_prefix="Triggered emergency 8% Faysal Bank rate. ",
                        bank_note=" on 8% Faysal Bank rate",
                    )
                else:
                    reason = (
                        f"Unviable at 10% floor (Rs. {round(cost_floors.floor_digi_10):,}). "
                        f"Triggered emergency 8% Faysal Bank rate to undercut {lowest_offer.vendor_name} (Rs. {lowest_offer.price:,.0f}) "
                        f"to winning price Rs. {final_p_8:,.0f} (+Rs. {profit:,} profit)."
                    )
            return (
                PlatformPricingResult(
                    min_price=min_p,
                    max_price=max_p,
                    final_price=final_p_8,
                    real_profit=profit,
                    status="Win via 8% Switch",
                    reason=reason,
                    dropped=[],
                    active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in active_offers],
                    effective_comm=digi_lev_comm_str,
                    discovery_status=disc_status,
                ),
                lowest_offer,
            )

    # Step C: Lowest seller is <= ceil(8% floor) (unviable loss-maker / sub-integer-floor). Try upper band.
    dropped = [o for o in active_offers if o.price <= min_int_digi_8]
    viable_8 = [o for o in active_offers if o.price > min_int_digi_8]

    if viable_8:
        for lowest_upper in sorted(viable_8, key=lambda x: x.price):
            # Check if lowest upper seller can be won at default 10% tier first
            if lowest_upper.price > min_int_digi_10:
                gap_upper_10 = lowest_upper.price - cost_floors.floor_digi_10
                target_adaptive_10 = calculate_adaptive_target_price(
                    floor_min=cost_floors.floor_digi_10,
                    competitor_price=lowest_upper.price,
                    cost_base=cost_floors.cost_base,
                    payout_rate=digi_lev_payout,
                    large_gap_profit_target=large_cap,
                )
                final_p_10 = find_winning_psychological_price(
                    cost_floors.floor_digi_10, lowest_upper.price, max_ceiling=target_adaptive_10
                )
                if final_p_10 is not None:
                    profit = round((final_p_10 * digi_lev_payout) - cost_floors.cost_base)
                    uncapped_p = find_winning_psychological_price(
                        cost_floors.floor_digi_10, lowest_upper.price
                    )
                    if uncapped_p is not None and final_p_10 < uncapped_p:
                        reason = _format_winning_reason(
                            gap=gap_upper_10,
                            competitor_name=lowest_upper.vendor_name,
                            competitor_price=lowest_upper.price,
                            final_price=final_p_10,
                            profit=profit,
                            dropped_prefix="Filtered sub-floor offers. ",
                            bank_note=" on 8% Faysal Bank rate",
                        )
                    else:
                        reason = (
                            f"Filtered sub-floor offers. Undercut viable competitor {lowest_upper.vendor_name} "
                            f"(Rs. {lowest_upper.price:,.0f}) to capped price Rs. {final_p_10:,.0f} (+Rs. {profit:,} profit on 8% Faysal Bank rate incl. 2% bank spread)."
                        )
                    return (
                        PlatformPricingResult(
                            min_price=min_p,
                            max_price=max_p,
                            final_price=final_p_10,
                            real_profit=profit,
                            status="Safe Win (10% Tier)",
                            reason=reason,
                            dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
                            active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable_8],
                            effective_comm=digi_std_comm_str,
                            discovery_status=disc_status,
                        ),
                        lowest_upper,
                    )

            gap_upper_8 = lowest_upper.price - cost_floors.floor_digi_8
            target_adaptive_8 = calculate_adaptive_target_price(
                floor_min=cost_floors.floor_digi_8,
                competitor_price=lowest_upper.price,
                cost_base=cost_floors.cost_base,
                payout_rate=digi_lev_payout,
                large_gap_profit_target=large_cap,
            )
            final_p_upper = find_winning_psychological_price(
                cost_floors.floor_digi_8, lowest_upper.price, max_ceiling=target_adaptive_8
            )
            if final_p_upper is not None:
                profit = round((final_p_upper * digi_lev_payout) - cost_floors.cost_base)
                if gap_upper_8 < 100.0:
                    reason = (
                        f"Filtered sub-floor offers. Triggered emergency 8% Faysal Bank rate. Competitor {lowest_upper.vendor_name} "
                        f"(Rs. {lowest_upper.price:,.0f}) gap is tight. Undercut to winning rounded price Rs. {final_p_upper:,.0f} "
                        f"with guaranteed +Rs. {profit:,} profit."
                    )
                else:
                    uncapped_p = find_winning_psychological_price(
                        cost_floors.floor_digi_8, lowest_upper.price
                    )
                    if uncapped_p is not None and final_p_upper < uncapped_p:
                        reason = _format_winning_reason(
                            gap=gap_upper_8,
                            competitor_name=lowest_upper.vendor_name,
                            competitor_price=lowest_upper.price,
                            final_price=final_p_upper,
                            profit=profit,
                            dropped_prefix="Filtered sub-floor offers. Triggered emergency 8% Faysal Bank rate. ",
                            bank_note=" on 8% Faysal Bank rate",
                        )
                    else:
                        reason = (
                            f"Filtered sub-floor offers. Triggered emergency 8% Faysal Bank rate to undercut "
                            f"upper competitor {lowest_upper.vendor_name} (Rs. {lowest_upper.price:,.0f}) to capped price Rs. {final_p_upper:,.0f} (+Rs. {profit:,} profit)."
                        )
                return (
                    PlatformPricingResult(
                        min_price=min_p,
                        max_price=max_p,
                        final_price=final_p_upper,
                        real_profit=profit,
                        status="Win via 8% Switch",
                        reason=reason,
                        dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
                        active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable_8],
                        effective_comm=digi_lev_comm_str,
                        discovery_status=disc_status,
                    ),
                    lowest_upper,
                )
            dropped.append(lowest_upper)

    # Step D: All sellers below 8% floor -> Safe Fallback to enable catalog upload
    lowest_dropped_obj = min(dropped, key=lambda x: x.price) if dropped else None
    lowest_str = (
        f", lowest: {lowest_dropped_obj.vendor_name} Rs. {lowest_dropped_obj.price:,.0f}"
        if lowest_dropped_obj
        else ""
    )
    final_fallback_p = get_fallback_psychological_price(
        cost_base=cost_floors.cost_base,
        floor_min=cost_floors.floor_digi_8,
        payout_rate=digi_lev_payout,
        profit_target=config.FALLBACK_PROFIT_PKR + extra_personal_comm_digi,
    )
    profit = round((final_fallback_p * digi_lev_payout) - cost_floors.cost_base)
    return (
        PlatformPricingResult(
            min_price=min_p,
            max_price=max_p,
            final_price=final_fallback_p,
            real_profit=profit,
            status="Safe Fallback",
            reason=(
                f"All competitors are selling at a loss (< Floor Rs. {round(cost_floors.floor_digi_8):,}{lowest_str}). "
                f"Undercut skipped to prevent loss. Listed at Safe Fallback Price Rs. {final_fallback_p:,.0f} (+Rs. {profit:,} profit on {digi_lev_comm_str} Faysal Bank rate) "
                f"to ensure catalog upload."
            ),
            dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
            active_pool=[],
            effective_comm=digi_lev_comm_str,
            discovery_status=disc_status,
        ),
        lowest_dropped_obj,
    )
