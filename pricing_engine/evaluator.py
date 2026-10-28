from dataclasses import replace

from pricing_engine.calculator import (
    calculate_adaptive_target_price,
    find_winning_psychological_price,
    format_dynamic_retention_pct,
    get_fallback_psychological_price,
    get_monopoly_psychological_price,
)
from pricing_engine.models import (
    STATUS_SERVER_DOWN,
    CostFloors,
    MarketRange,
    PlatformPricingResult,
    ScrapedOffer,
    ScrapeResult,
    classify_non_competitor_vendor,
    is_non_competitor_vendor,
)

MONOPOLY_PROFIT: float = 4000.0
FALLBACK_PROFIT: float = 1500.0


def evaluate_market_range(offers: list[ScrapedOffer] | ScrapeResult) -> MarketRange:
    """Compute market min/max over in-stock offers with no floor filtering.

    Sold-out offers are ignored. A failed ScrapeResult yields ``is_down=True`` so callers
    never confuse an unreachable server with an empty market.
    """
    if isinstance(offers, ScrapeResult):
        if not offers.is_success:
            return MarketRange(
                min_price=None,
                max_price=None,
                offer_count=0,
                is_down=True,
                error_detail=offers.error_detail or "HTTP Server/Network Error",
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
        return MarketRange(min_price=None, max_price=None, offer_count=0)
    return MarketRange(min_price=min(prices), max_price=max(prices), offer_count=len(prices))


def format_fallback_descriptions(mod: str, source: str = "target") -> tuple[str, str, str]:
    """Generates (audit_text, reason_prefix, banner_text) for active modifier fallbacks."""
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


def _annotate_fallback_reason(
    res: PlatformPricingResult, active_fallback: str | None
) -> PlatformPricingResult:
    """Prepend explicit fallback notification to pricing reason when market omitted target modifier."""
    if active_fallback and res.status not in (STATUS_SERVER_DOWN, "Monopoly Win"):
        _, reason_prefix, _ = format_fallback_descriptions(active_fallback)
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


def evaluate_alfa_pricing(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float = MONOPOLY_PROFIT,
    max_profit_cap: float | None = None,
) -> PlatformPricingResult:
    """Evaluate pricing on AlfaMall with automatic fallback and own-store reason annotations."""
    active_fallback = offers.active_modifier_fallback if isinstance(offers, ScrapeResult) else None
    own_offers = offers.own_offers if isinstance(offers, ScrapeResult) else []
    res = _evaluate_alfa_core(
        cost_floors=cost_floors,
        offers=offers,
        monopoly_profit=monopoly_profit,
        max_profit_cap=max_profit_cap,
    )
    res = replace(res, own_offers=own_offers)
    res = _annotate_fallback_reason(res, active_fallback)
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
    monopoly_profit: float = MONOPOLY_PROFIT,
    max_profit_cap: float | None = None,
) -> PlatformPricingResult:
    """Evaluate pricing on AlfaMall under strict 10% commission rules.

    Rules:
    - If server is unreachable (500/timeout/WAF HTML), return Server Down status (no blind monopoly).
    - Discard out-of-stock items.
    - If 0 active offers and server is healthy, set Monopoly price (+Rs. 4,000 margin).
    - Discard sellers priced <= floor_alfa (unviable loss-makers).
    - If no viable sellers remain, set Safe Fallback Price (+Rs. 1,500 profit) to ensure upload.
    - Otherwise, strictly undercut lowest viable competitor with psychological price.

    Args:
        cost_floors: CostFloors object containing cost base and minimum floors.
        offers: List of scraped competitor offerings or ScrapeResult instance.
        monopoly_profit: Profit added when 0 competitors exist.
        max_profit_cap: Optional profit ceiling cap.

    Returns:
        PlatformPricingResult with final decision, prices, and audit log.
    """
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
        return PlatformPricingResult(
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
            effective_comm="10.00%",
        )

    active_offers = [
        o
        for o in offer_list
        if not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
    ]
    valid_prices = sorted([o.price for o in active_offers])

    market = evaluate_market_range(offer_list)
    min_p: float | None = market.min_price
    max_p: float | None = market.max_price

    floor_profit_alfa = (cost_floors.floor_alfa * 0.90) - cost_floors.cost_base
    extra_personal_comm_alfa = (
        float(cost_floors.personal_comm)
    )

    # Scenario 1: Zero competitors in market -> Monopoly Pricing
    if not valid_prices:
        eff_monopoly_alfa = max(monopoly_profit, floor_profit_alfa + 1000.0) if extra_personal_comm_alfa > 0 else monopoly_profit
        raw_target = (cost_floors.cost_base + eff_monopoly_alfa) / 0.90
        monopoly_p = get_monopoly_psychological_price(raw_target)
        profit = round((monopoly_p * 0.90) - cost_floors.cost_base)
        return PlatformPricingResult(
            min_price=min_p,
            max_price=max_p,
            final_price=monopoly_p,
            real_profit=profit,
            status="Monopoly Win",
            reason=f"No competitors found in market. Applied Monopoly pricing (+Rs. {eff_monopoly_alfa:,.0f} target margin).",
            dropped=[],
            active_pool=[],
            effective_comm="10.00%",
        )

    # Discard loss makers (sellers strictly <= floor cannot be profitably undercut)
    dropped = [o for o in active_offers if o.price <= cost_floors.floor_alfa]
    viable = [o for o in active_offers if o.price > cost_floors.floor_alfa]

    # Scenario 2: All competitors below floor -> Safe Fallback to enable catalog upload
    if not viable:
        lowest_dropped_obj = min(dropped, key=lambda x: x.price)
        lowest_dropped = lowest_dropped_obj.price
        final_fallback_p = get_fallback_psychological_price(
            cost_base=cost_floors.cost_base,
            floor_min=cost_floors.floor_alfa,
            payout_rate=0.90,
            profit_target=FALLBACK_PROFIT + extra_personal_comm_alfa,
        )
        profit = round((final_fallback_p * 0.90) - cost_floors.cost_base)
        return PlatformPricingResult(
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
            effective_comm="10.00%",
        )

    # Scenario 3: Undercut lowest viable seller
    lowest_viable = min(viable, key=lambda x: x.price)
    large_cap_alfa = (
        max_profit_cap if max_profit_cap is not None else (10000.0 + extra_personal_comm_alfa)
    )
    target_adaptive_alfa = calculate_adaptive_target_price(
        floor_min=cost_floors.floor_alfa,
        competitor_price=lowest_viable.price,
        cost_base=cost_floors.cost_base,
        payout_rate=0.90,
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
                payout_rate=0.90,
                large_gap_profit_target=large_cap_alfa,
            )
            final_p = find_winning_psychological_price(
                cost_floors.floor_alfa, higher_viable.price, max_ceiling=target_adaptive_alfa
            )
            if final_p is not None:
                lowest_viable = higher_viable
                break

    if final_p is None:
        return PlatformPricingResult(
            min_price=min_p,
            max_price=max_p,
            final_price=None,
            real_profit=0,
            status="Skip / Unviable",
            reason="Tight competitor margin prevented psychological undercut above floor. Skipped to prevent loss.",
            dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
            active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable],
            effective_comm="10.00%",
        )

    profit = round((final_p * 0.90) - cost_floors.cost_base)
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
    return PlatformPricingResult(
        min_price=min_p,
        max_price=max_p,
        final_price=final_p,
        real_profit=profit,
        status="Competitive Win",
        reason=reason,
        dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
        active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable],
        effective_comm="10.00%",
    )


def evaluate_digi_pricing(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float = MONOPOLY_PROFIT,
    max_profit_cap: float | None = None,
) -> PlatformPricingResult:
    """Evaluate pricing on DigiMall with automatic fallback and own-store reason annotations."""
    active_fallback = offers.active_modifier_fallback if isinstance(offers, ScrapeResult) else None
    own_offers = offers.own_offers if isinstance(offers, ScrapeResult) else []
    res = _evaluate_digi_core(
        cost_floors=cost_floors,
        offers=offers,
        monopoly_profit=monopoly_profit,
        max_profit_cap=max_profit_cap,
    )
    res = replace(res, own_offers=own_offers)
    res = _annotate_fallback_reason(res, active_fallback)
    return _annotate_non_competitor_reason(res, own_offers)


def _evaluate_digi_core(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float = MONOPOLY_PROFIT,
    max_profit_cap: float | None = None,
) -> PlatformPricingResult:
    """Evaluate pricing on DigiMall with Two-Tier Commission Switch (10% -> 8%).

    Rules:
    - If server is unreachable (500/timeout/WAF HTML), return Server Down status (no blind monopoly).
    - Default 10% Tier: If lowest competitor > floor_digi_10, undercut at 10% tier.
      Since bank only charges 8%, we capture extra 2% bank spread profit.
    - Emergency 8% Switch: If lowest competitor <= floor_digi_10 but > floor_digi_8,
      trigger 8% bank rate to win the deal.
    - Upper Band: If lowest competitor <= floor_digi_8, drop them and target next
      viable competitor > floor_digi_8.
    - If all competitors <= floor_digi_8, set Safe Fallback Price (+Rs. 1,500 profit) to ensure upload.

    Args:
        cost_floors: CostFloors containing cost base and floors.
        offers: Scraped competitor offerings or ScrapeResult instance.
        monopoly_profit: Profit added when 0 competitors exist.
        max_profit_cap: Optional profit ceiling cap.

    Returns:
        PlatformPricingResult with decision, price, commission used, and audit details.
    """
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
        return PlatformPricingResult(
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
            effective_comm="8.00%",
        )

    active_offers = [
        o
        for o in offer_list
        if not o.is_sold_out and not is_non_competitor_vendor(o.vendor_name)
    ]
    valid_prices = sorted([o.price for o in active_offers])

    market = evaluate_market_range(offer_list)
    min_p: float | None = market.min_price
    max_p: float | None = market.max_price

    floor_profit_digi = (cost_floors.floor_digi_10 * 0.90) - cost_floors.cost_base
    extra_personal_comm_digi = (
        float(cost_floors.personal_comm)
    )

    # Scenario 1: Zero competitors in market -> Monopoly Pricing
    if not valid_prices:
        eff_monopoly_digi = max(monopoly_profit, floor_profit_digi + 1000.0) if extra_personal_comm_digi > 0 else monopoly_profit
        raw_target = (cost_floors.cost_base + eff_monopoly_digi) / 0.90
        monopoly_p = get_monopoly_psychological_price(raw_target)
        profit = round((monopoly_p * 0.92) - cost_floors.cost_base)
        return PlatformPricingResult(
            min_price=min_p,
            max_price=max_p,
            final_price=monopoly_p,
            real_profit=profit,
            status="Monopoly Win",
            reason="No competitors found in market. Applied Monopoly 10% baseline pricing and captured extra 2% bank spread profit via 8% Faysal Bank rate.",
            dropped=[],
            active_pool=[],
            effective_comm="10.00%",
        )

    lowest_offer = min(active_offers, key=lambda x: x.price)
    large_cap = (
        max_profit_cap if max_profit_cap is not None else (10000.0 + extra_personal_comm_digi)
    )

    # Step A: Check Default 10% Tier
    if lowest_offer.price > cost_floors.floor_digi_10:
        gap_10 = lowest_offer.price - cost_floors.floor_digi_10
        target_adaptive_10 = calculate_adaptive_target_price(
            floor_min=cost_floors.floor_digi_10,
            competitor_price=lowest_offer.price,
            cost_base=cost_floors.cost_base,
            payout_rate=0.92,
            large_gap_profit_target=large_cap,
        )
        final_p_10: int | None = find_winning_psychological_price(
            cost_floors.floor_digi_10, lowest_offer.price, max_ceiling=target_adaptive_10
        )
        if final_p_10 is not None:
            profit = round((final_p_10 * 0.92) - cost_floors.cost_base)
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
            return PlatformPricingResult(
                min_price=min_p,
                max_price=max_p,
                final_price=final_p_10,
                real_profit=profit,
                status="Safe Win (10% Tier)",
                reason=reason,
                dropped=[],
                active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in active_offers],
                effective_comm="10.00%",
            )

    # Step B: Emergency 8% Bank Rate Switch
    if lowest_offer.price > cost_floors.floor_digi_8:
        gap_8 = lowest_offer.price - cost_floors.floor_digi_8
        target_adaptive_8 = calculate_adaptive_target_price(
            floor_min=cost_floors.floor_digi_8,
            competitor_price=lowest_offer.price,
            cost_base=cost_floors.cost_base,
            payout_rate=0.92,
            large_gap_profit_target=large_cap,
        )
        final_p_8: int | None = find_winning_psychological_price(
            cost_floors.floor_digi_8, lowest_offer.price, max_ceiling=target_adaptive_8
        )
        if final_p_8 is not None:
            profit = round((final_p_8 * 0.92) - cost_floors.cost_base)
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
            return PlatformPricingResult(
                min_price=min_p,
                max_price=max_p,
                final_price=final_p_8,
                real_profit=profit,
                status="Win via 8% Switch",
                reason=reason,
                dropped=[],
                active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in active_offers],
                effective_comm="8.00%",
            )

    # Step C: Lowest seller is <= 8% floor (unviable loss-maker). Try upper band.
    dropped = [o for o in active_offers if o.price <= cost_floors.floor_digi_8]
    viable_8 = [o for o in active_offers if o.price > cost_floors.floor_digi_8]

    if viable_8:
        for lowest_upper in sorted(viable_8, key=lambda x: x.price):
            # Check if lowest upper seller can be won at default 10% tier first
            if lowest_upper.price > cost_floors.floor_digi_10:
                gap_upper_10 = lowest_upper.price - cost_floors.floor_digi_10
                target_adaptive_10 = calculate_adaptive_target_price(
                    floor_min=cost_floors.floor_digi_10,
                    competitor_price=lowest_upper.price,
                    cost_base=cost_floors.cost_base,
                    payout_rate=0.92,
                    large_gap_profit_target=large_cap,
                )
                final_p_10 = find_winning_psychological_price(
                    cost_floors.floor_digi_10, lowest_upper.price, max_ceiling=target_adaptive_10
                )
                if final_p_10 is not None:
                    profit = round((final_p_10 * 0.92) - cost_floors.cost_base)
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
                    return PlatformPricingResult(
                        min_price=min_p,
                        max_price=max_p,
                        final_price=final_p_10,
                        real_profit=profit,
                        status="Safe Win (10% Tier)",
                        reason=reason,
                        dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
                        active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable_8],
                        effective_comm="10.00%",
                    )

            gap_upper_8 = lowest_upper.price - cost_floors.floor_digi_8
            target_adaptive_8 = calculate_adaptive_target_price(
                floor_min=cost_floors.floor_digi_8,
                competitor_price=lowest_upper.price,
                cost_base=cost_floors.cost_base,
                payout_rate=0.92,
                large_gap_profit_target=large_cap,
            )
            final_p_upper = find_winning_psychological_price(
                cost_floors.floor_digi_8, lowest_upper.price, max_ceiling=target_adaptive_8
            )
            if final_p_upper is not None:
                profit = round((final_p_upper * 0.92) - cost_floors.cost_base)
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
                return PlatformPricingResult(
                    min_price=min_p,
                    max_price=max_p,
                    final_price=final_p_upper,
                    real_profit=profit,
                    status="Win via 8% Switch",
                    reason=reason,
                    dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
                    active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable_8],
                    effective_comm="8.00%",
                )

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
        payout_rate=0.92,
        profit_target=FALLBACK_PROFIT + extra_personal_comm_digi,
    )
    profit = round((final_fallback_p * 0.92) - cost_floors.cost_base)
    return PlatformPricingResult(
        min_price=min_p,
        max_price=max_p,
        final_price=final_fallback_p,
        real_profit=profit,
        status="Safe Fallback",
        reason=(
            f"All competitors are selling at a loss (< Floor Rs. {round(cost_floors.floor_digi_8):,}{lowest_str}). "
            f"Undercut skipped to prevent loss. Listed at Safe Fallback Price Rs. {final_fallback_p:,.0f} (+Rs. {profit:,} profit on 8% Faysal Bank rate) "
            f"to ensure catalog upload."
        ),
        dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
        active_pool=[],
        effective_comm="8.00%",
    )
