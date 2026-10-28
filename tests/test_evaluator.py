import pytest

from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.models import CostFloors, ScrapedOffer, ScrapeResult


@pytest.fixture
def sample_floors() -> CostFloors:
    # cost_base = 72,000
    # 10% floor = (72000 + 500) / 0.90 = 80,555.56
    # 8% floor  = (72000 + 500) / 0.92 = 78,804.35
    cost_base = 72000.0
    return CostFloors(
        cost_base=cost_base,
        zero_margin_10=cost_base / 0.90,
        zero_margin_8=cost_base / 0.92,
        floor_alfa=(cost_base + 500.0) / 0.90,
        floor_digi_10=(cost_base + 500.0) / 0.90,
        floor_digi_8=(cost_base + 500.0) / 0.92,
    )


# ==============================================================================
# ALFAMALL TESTS
# ==============================================================================


def test_alfa_monopoly_when_zero_offers(sample_floors: CostFloors) -> None:
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=[])
    assert result.status == "Monopoly Win"
    assert result.final_price is not None
    # Base target = (72000 + 4000) / 0.90 = 84444.44 -> Monopoly price 84499
    assert result.final_price == 84499
    assert result.real_profit >= 4000


def test_alfa_safe_fallback_when_all_sellers_below_floor(sample_floors: CostFloors) -> None:
    # Floor is 80,555. Both sellers are below floor. Must produce Safe Fallback price, NOT None.
    offers = [
        ScrapedOffer(vendor_name="V1", price=79000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="V2", price=80000.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Safe Fallback"
    assert result.final_price is not None
    assert result.final_price >= sample_floors.floor_alfa
    assert result.real_profit >= 1500
    assert len(result.dropped) == 2
    assert "Safe Fallback Price" in result.reason


def test_alfa_competitive_win_undercut(sample_floors: CostFloors) -> None:
    # Floor is 80,555. One loss maker at 79,000, one viable at 83,000.
    offers = [
        ScrapedOffer(vendor_name="LossVendor", price=79000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="ViableVendor", price=83000.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Competitive Win"
    assert result.final_price is not None
    assert result.final_price < 83000.0
    assert result.final_price >= sample_floors.floor_alfa
    assert result.final_price == 82299
    assert "Applied dynamic adaptive split" in result.reason
    assert result.real_profit > 500


def test_alfa_ignores_sold_out_offers(sample_floors: CostFloors) -> None:
    offers = [
        ScrapedOffer(vendor_name="SoldOutCheap", price=75000.0, is_sold_out=True, raw_title="AC"),
    ]
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Monopoly Win"


# ==============================================================================
# DIGIMALL TESTS
# ==============================================================================


def test_digi_monopoly_when_zero_offers(sample_floors: CostFloors) -> None:
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=[])
    assert result.status == "Monopoly Win"
    assert result.effective_comm == "10.00%"
    assert result.final_price == 84499
    # Bank charges 8%, so profit is (84499 * 0.92) - 72000
    assert result.real_profit == round((84499 * 0.92) - 72000)


def test_digi_tier1_safe_win_10_percent(sample_floors: CostFloors) -> None:
    # Lowest offer at 84,000 is above 10% floor (80,555.56)
    offers = [
        ScrapedOffer(vendor_name="Competitor1", price=84000.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Safe Win (10% Tier)"
    assert result.effective_comm == "10.00%"
    assert result.final_price is not None
    assert result.final_price < 84000.0
    assert result.final_price >= sample_floors.floor_digi_10
    # Profit calculated at 0.92 bank rate!
    assert result.real_profit == round((result.final_price * 0.92) - sample_floors.cost_base)


def test_digi_tier2_emergency_8_percent_switch(sample_floors: CostFloors) -> None:
    # 10% floor is 80,555.56. 8% floor is 78,804.35.
    # Competitor is at 79,500 (below 10% floor, but above 8% floor)
    offers = [
        ScrapedOffer(vendor_name="TightSeller", price=79500.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Win via 8% Switch"
    assert result.effective_comm == "8.00%"
    assert result.final_price is not None
    assert result.final_price < 79500.0
    assert result.final_price >= sample_floors.floor_digi_8


def test_digi_upper_band_win_when_lowest_below_8_percent(sample_floors: CostFloors) -> None:
    # 8% floor is 78,804.35, 10% floor is 80,555.55
    # Case 1: Upper seller is between 8% floor and 10% floor (79,500) -> Must switch to 8% to win
    offers_8 = [
        ScrapedOffer(vendor_name="SuicideSeller", price=77000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="UpperSellerTight", price=79500.0, is_sold_out=False, raw_title="AC"
        ),
    ]
    result_8 = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers_8)
    assert result_8.status == "Win via 8% Switch"
    assert result_8.effective_comm == "8.00%"
    assert result_8.final_price is not None
    assert result_8.final_price < 79500.0
    assert result_8.final_price >= sample_floors.floor_digi_8
    assert len(result_8.dropped) == 1

    # Case 2: Upper seller is above 10% floor (81,000) -> Stays on default 10% tier (+2% bank spread profit)
    offers_10 = [
        ScrapedOffer(vendor_name="SuicideSeller", price=77000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="UpperSellerHigh", price=81000.0, is_sold_out=False, raw_title="AC"
        ),
    ]
    result_10 = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers_10)
    assert result_10.status == "Safe Win (10% Tier)"
    assert result_10.effective_comm == "10.00%"
    assert result_10.final_price is not None
    assert result_10.final_price < 81000.0
    assert result_10.final_price >= sample_floors.floor_digi_10
    assert len(result_10.dropped) == 1


def test_digi_safe_fallback_when_all_below_8_percent(sample_floors: CostFloors) -> None:
    # 8% floor is 78,804.35. All sellers below 78,000. Must produce Safe Fallback price, NOT None.
    offers = [
        ScrapedOffer(vendor_name="SellerA", price=77000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="SellerB", price=76500.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Safe Fallback"
    assert result.final_price is not None
    assert result.final_price >= sample_floors.floor_digi_8
    assert result.real_profit >= 1500
    assert result.effective_comm == "8.00%"
    assert "Safe Fallback Price" in result.reason


def test_digi_high_ticket_item1_wins_at_10_percent() -> None:
    # Item #1: Floor Standing AC (Net 415,000, Shipping 15,291 -> Cost Base 430,291)
    # 10% Floor (+500) = (430,291 + 500) / 0.90 = 478,656.67
    # 8% Floor (+500)  = (430,291 + 500) / 0.92 = 468,251.09
    cost_base = 430291.0
    floors = CostFloors(
        cost_base=cost_base,
        zero_margin_10=cost_base / 0.90,
        zero_margin_8=cost_base / 0.92,
        floor_alfa=(cost_base + 500.0) / 0.90,
        floor_digi_10=(cost_base + 500.0) / 0.90,
        floor_digi_8=(cost_base + 500.0) / 0.92,
    )
    offers = [
        ScrapedOffer(vendor_name="Tech House", price=444999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="Musab Mall", price=444999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="YZ international", price=445099.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(vendor_name="Home Cart", price=463549.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="Scroll-N-Shop.pk", price=489999.0, is_sold_out=False, raw_title="AC"
        ),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)

    # Must win at Default 10% Tier, NOT 8% Emergency Switch!
    assert result.status == "Safe Win (10% Tier)"
    assert result.effective_comm == "10.00%"
    assert result.final_price == 478999
    assert result.real_profit == 10388  # +Rs. 10,388 (~10k sweet spot with clean .999)
    assert len(result.dropped) == 4
    assert "sweet-spot price Rs. 478,999" in result.reason


def test_digi_split_ac_item2_triggers_8_percent_emergency_switch() -> None:
    # Item #2: Split AC 12AITH21W-T3 (Net 147,000, Shipping 3,978 -> Cost Base 150,978)
    # 10% Floor (+500) = (150,978 + 500) / 0.90 = 168,308.89
    # 8% Floor (+500)  = (150,978 + 500) / 0.92 = 164,650.00
    cost_base = 150978.0
    floors = CostFloors(
        cost_base=cost_base,
        zero_margin_10=cost_base / 0.90,
        zero_margin_8=cost_base / 0.92,
        floor_alfa=(cost_base + 500.0) / 0.90,
        floor_digi_10=(cost_base + 500.0) / 0.90,
        floor_digi_8=(cost_base + 500.0) / 0.92,
    )
    offers = [
        ScrapedOffer(
            vendor_name="iShopping Team", price=162299.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(vendor_name="Tech House", price=165999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="Musab Mall", price=165999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="YZ international", price=166099.0, is_sold_out=False, raw_title="AC"
        ),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)

    # Tech House (165,999) < 10% floor (168,309), so 10% loses -> Triggers Emergency 8% Switch!
    # Gap is 1,349 PKR (800-1500 range) -> Undercuts by Rs. 200 to 165,799 (.799 psychological ending)
    assert result.status == "Win via 8% Switch"
    assert result.effective_comm == "8.00%"
    assert result.final_price == 165799
    assert result.real_profit == round((165799 * 0.92) - 150978)  # +Rs. 1,557 profit
    assert len(result.dropped) == 1
    assert "emergency 8% Faysal Bank rate" in result.reason


def test_digi_item18_tight_margin_selects_floor_ceil_wins_with_500_profit() -> None:
    # Item #18: Split AC GS-18PITC12W-T3 (Cost Base 158,663)
    # 8% Floor (+500) = (158,663 + 500) / 0.92 = 173,003.26
    # Lowest viable is YZ international at 173,099.0 (Gap = 95.74 PKR)
    cost_base = 158663.0
    floors = CostFloors(
        cost_base=cost_base,
        zero_margin_10=cost_base / 0.90,
        zero_margin_8=cost_base / 0.92,
        floor_alfa=(cost_base + 500.0) / 0.90,
        floor_digi_10=(cost_base + 500.0) / 0.90,
        floor_digi_8=(cost_base + 500.0) / 0.92,
    )
    offers = [
        ScrapedOffer(
            vendor_name="iShopping Team", price=168749.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(
            vendor_name="Electronics World", price=171304.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(vendor_name="Musab Mall", price=171999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="YZ international", price=172099.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(
            vendor_name="YZ international", price=172999.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(
            vendor_name="YZ international", price=173099.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(vendor_name="EZZI TRADERS", price=180549.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)

    # Must NOT skip! Must win at 8% rounded price 173,050 with guaranteed +543 profit
    assert result.status == "Win via 8% Switch"
    assert result.effective_comm == "8.00%"
    assert result.final_price == 173050
    assert result.real_profit == 543
    assert len(result.dropped) == 5
    assert (
        "gap is tight. Undercut to winning rounded price Rs. 173,050 with guaranteed +Rs. 543 profit."
        in result.reason
    )


def test_digi_item17_all_competitors_selling_at_loss_safe_fallback() -> None:
    # Item #17: Cost Base 137,125. 8% Floor (+500) = 149,592.
    # Competitor iShopping Team at 146,849 is selling at a loss.
    cost_base = 137125.0
    floors = CostFloors(
        cost_base=cost_base,
        zero_margin_10=cost_base / 0.90,
        zero_margin_8=cost_base / 0.92,
        floor_alfa=(cost_base + 500.0) / 0.90,
        floor_digi_10=(cost_base + 500.0) / 0.90,
        floor_digi_8=(cost_base + 500.0) / 0.92,
    )
    offers = [
        ScrapedOffer(
            vendor_name="iShopping Team", price=146849.0, is_sold_out=False, raw_title="AC"
        ),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)

    # Must produce Safe Fallback price: 150,999 with profit +1,794
    assert result.status == "Safe Fallback"
    assert result.effective_comm == "8.00%"
    assert result.final_price == 150999
    assert result.real_profit == 1794
    assert len(result.dropped) == 1
    assert (
        "Listed at Safe Fallback Price Rs. 150,999 (+Rs. 1,794 profit on 8% Faysal Bank rate)"
        in result.reason
    )


def test_alfa_server_down_does_not_trigger_false_monopoly(sample_floors: CostFloors) -> None:
    # When remote server crashes with 500, MUST set Server Down / Unreachable, NOT Monopoly!
    scrape_fail = ScrapeResult(
        offers=[],
        is_success=False,
        status_code=500,
        error_detail="HTTP 500 Internal Server Error",
    )
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=scrape_fail)

    assert result.status == "Server Down / Unreachable"
    assert result.final_price is None
    assert result.real_profit == 0
    assert "500" in result.reason
    assert "Skipped to prevent blind mispricing" in result.reason


def test_digi_server_down_does_not_trigger_false_monopoly(sample_floors: CostFloors) -> None:
    # When remote server times out, MUST set Server Down / Unreachable, NOT Monopoly!
    scrape_fail = ScrapeResult(
        offers=[],
        is_success=False,
        status_code=504,
        error_detail="Gateway Timeout after 3 retries",
    )
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=scrape_fail)

    assert result.status == "Server Down / Unreachable"
    assert result.final_price is None
    assert result.real_profit == 0
    assert "Gateway Timeout" in result.reason
    assert "Skipped to prevent blind mispricing" in result.reason


def test_asymmetric_portal_failure_isolated(sample_floors: CostFloors) -> None:
    # AlfaMall succeeds with viable seller, DigiMall fails with 500.
    # Neither should corrupt or block the other!
    alfa_success = ScrapeResult(
        offers=[
            ScrapedOffer(vendor_name="LiveSeller", price=82000.0, is_sold_out=False, raw_title="AC")
        ],
        is_success=True,
    )
    digi_fail = ScrapeResult(
        offers=[],
        is_success=False,
        status_code=500,
        error_detail="WAF 500 Server Error",
    )

    alfa_res = evaluate_alfa_pricing(cost_floors=sample_floors, offers=alfa_success)
    digi_res = evaluate_digi_pricing(cost_floors=sample_floors, offers=digi_fail)

    # Alfa successfully undercuts
    assert alfa_res.final_price is not None
    assert alfa_res.final_price < 82000.0
    assert alfa_res.status == "Competitive Win"

    # Digi cleanly reports Server Down
    assert digi_res.final_price is None
    assert digi_res.status == "Server Down / Unreachable"


def test_is_non_competitor_vendor() -> None:
    from pricing_engine.models import is_non_competitor_vendor

    assert is_non_competitor_vendor("haier-official-store") is True
    assert is_non_competitor_vendor("Haier Official Store") is True
    assert is_non_competitor_vendor("HAIER OFFICIAL STORE") is True
    assert is_non_competitor_vendor("haierofficialstore") is True
    assert is_non_competitor_vendor("KiaChahiye") is True
    assert is_non_competitor_vendor("kia-chahiye") is True
    assert is_non_competitor_vendor("KIA CHAHIYE") is True
    assert is_non_competitor_vendor("Kia Chahiye Pvt Ltd") is True
    assert is_non_competitor_vendor("kia-chahiye-pvt-ltd") is True
    assert is_non_competitor_vendor("KiaChahye") is True
    assert is_non_competitor_vendor("kiachahye") is True
    assert is_non_competitor_vendor("kia chahye") is True
    assert is_non_competitor_vendor("kiachahye.com") is True
    assert is_non_competitor_vendor("Ajmer") is True
    assert is_non_competitor_vendor("Ajmer Electronics") is True
    assert is_non_competitor_vendor("ajmer-electronics") is True
    assert is_non_competitor_vendor("Umar Electronics") is False
    assert is_non_competitor_vendor("Ezzi traders") is False
    assert is_non_competitor_vendor("") is False
    assert is_non_competitor_vendor(None) is False

    from pricing_engine.models import classify_non_competitor_vendor

    assert classify_non_competitor_vendor("KiaChahye") == "OWN_STORE"
    assert classify_non_competitor_vendor("Kia Chahiye Pvt Ltd") == "OWN_STORE"
    assert classify_non_competitor_vendor("kia-chahiye-pvt-ltd") == "OWN_STORE"
    assert classify_non_competitor_vendor("kiachahye.com") == "OWN_STORE"
    assert classify_non_competitor_vendor("Ajmer Electronics") == "OWN_STORE"
    assert classify_non_competitor_vendor("Haier Official Store") == "OFFICIAL_STORE"
    assert classify_non_competitor_vendor("haierofficialstore") == "OFFICIAL_STORE"
    assert classify_non_competitor_vendor("Fahad Electronics") is None
    assert classify_non_competitor_vendor(None) is None


def test_evaluate_market_range_ignores_non_competitor() -> None:
    from pricing_engine.evaluator import evaluate_market_range

    offers = [
        ScrapedOffer(vendor_name="Haier Official Store", price=50000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="Competitor 1", price=65000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="Competitor 2", price=70000.0, is_sold_out=False, raw_title="AC"),
    ]
    rng = evaluate_market_range(offers)
    assert rng.offer_count == 2
    assert rng.min_price == 65000.0
    assert rng.max_price == 70000.0


def test_evaluator_ignores_non_competitor_as_sole_offer(sample_floors: CostFloors) -> None:
    # If the only seller is Haier Official Store, it is NOT considered a competitor -> Monopoly Win!
    offers = [
        ScrapedOffer(vendor_name="Haier Official Store", price=75000.0, is_sold_out=False, raw_title="AC"),
    ]
    alfa_res = evaluate_alfa_pricing(cost_floors=sample_floors, offers=offers)
    assert alfa_res.status == "Monopoly Win"
    assert alfa_res.min_price is None
    digi_res = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers)
    assert digi_res.status == "Monopoly Win"
    assert digi_res.min_price is None


def test_evaluator_own_store_annotation_and_zero_undercut_invariance(sample_floors: CostFloors) -> None:
    # When KiaChahye is the sole seller at 85,000, engine must NOT undercut 85,000!
    # Instead, monopoly pricing is applied and reason includes the [OWN STORE ACTIVE: ...] hint.
    scrape_res = ScrapeResult(
        offers=[],
        own_offers=[
            ScrapedOffer(vendor_name="KiaChahye", price=85000.0, is_sold_out=False, raw_title="AC"),
        ],
    )
    alfa_res = evaluate_alfa_pricing(cost_floors=sample_floors, offers=scrape_res)
    assert alfa_res.status == "Monopoly Win"
    assert alfa_res.final_price == 84499  # Standard monopoly price for sample_floors (Cost Base 72,000 + 4,000 / 0.90 -> 84,444 -> 84,499)
    assert "[OWN STORE ACTIVE: KiaChahye @ Rs. 85,000]" in alfa_res.reason
    assert "Applied Monopoly pricing" in alfa_res.reason
    assert len(alfa_res.own_offers) == 1

    digi_res = evaluate_digi_pricing(cost_floors=sample_floors, offers=scrape_res)
    assert digi_res.status == "Monopoly Win"
    assert "[OWN STORE ACTIVE: KiaChahye @ Rs. 85,000]" in digi_res.reason


def test_evaluator_own_store_with_external_competitor(sample_floors: CostFloors) -> None:
    # Competitor is at 83,000, KiaChahye is at 84,000.
    # Engine must undercut the competitor (83,000 -> 82,899), NOT KiaChahye, and tag both!
    scrape_res = ScrapeResult(
        offers=[
            ScrapedOffer(vendor_name="Fahad Electronics", price=83000.0, is_sold_out=False, raw_title="AC"),
        ],
        own_offers=[
            ScrapedOffer(vendor_name="KiaChahye", price=84000.0, is_sold_out=False, raw_title="AC"),
            ScrapedOffer(vendor_name="Haier Official Store", price=92000.0, is_sold_out=False, raw_title="AC"),
        ],
    )
    alfa_res = evaluate_alfa_pricing(cost_floors=sample_floors, offers=scrape_res)
    assert alfa_res.status == "Competitive Win"
    assert alfa_res.final_price == 82299  # Undercuts Fahad Electronics (83,000) via dynamic split
    assert "[OWN STORE ACTIVE: KiaChahye @ Rs. 84,000]" in alfa_res.reason
    assert "[OFFICIAL STORE: Haier Official Store @ Rs. 92,000]" in alfa_res.reason
    assert any("Fahad Electronics" in s for s in alfa_res.active_pool)


def test_evaluator_own_store_out_of_stock_annotation(sample_floors: CostFloors) -> None:
    scrape_res = ScrapeResult(
        offers=[],
        own_offers=[
            ScrapedOffer(vendor_name="KiaChahye", price=85000.0, is_sold_out=True, raw_title="AC"),
        ],
    )
    alfa_res = evaluate_alfa_pricing(cost_floors=sample_floors, offers=scrape_res)
    assert "[OWN STORE ACTIVE: KiaChahye (OUT OF STOCK) @ Rs. 85,000]" in alfa_res.reason



def test_digi_dynamic_adaptive_split_tier2(sample_floors: CostFloors) -> None:
    # 10% floor is 80,555.56. Competitor is at 85,555 (gap is ~5,000, Tier 2: 2,000 <= Gap < 10,000)
    # Dynamic glide (68.75%) targets ~83,993 -> snaps to psychological 83,899
    offers = [
        ScrapedOffer(vendor_name="CompetitorGap5k", price=85555.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Safe Win (10% Tier)"
    assert result.effective_comm == "10.00%"
    assert result.final_price == 83899
    assert "Applied dynamic adaptive split (69%)" in result.reason
    assert "capped winning sweet-spot price" in result.reason
    assert result.real_profit == round((83899 * 0.92) - sample_floors.cost_base)


def test_digi_step_c_upper_band_10pct_dynamic_split(sample_floors: CostFloors) -> None:
    # Sub-floor competitor at 75,000 (below 8% floor 78,804.35)
    # Upper competitor at 85,555 (Gap above 10% floor is ~5,000 PKR, Tier 2)
    offers = [
        ScrapedOffer(vendor_name="SubFloorSeller", price=75000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="UpperSeller10k", price=85555.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Safe Win (10% Tier)"
    assert result.effective_comm == "10.00%"
    assert result.final_price == 83899
    assert "Filtered sub-floor offers" in result.reason
    assert "Applied dynamic adaptive split (69%)" in result.reason
    assert "capped winning sweet-spot price" in result.reason
    assert any("SubFloorSeller" in d for d in result.dropped)
    assert any("UpperSeller10k" in a for a in result.active_pool)


def test_digi_step_c_upper_band_8pct_dynamic_split() -> None:
    # High-value item: cost_base = 150,000 PKR
    # 10% floor = (150000 + 500) / 0.90 = 167,222.22 PKR
    # 8% floor = (150000 + 500) / 0.92 = 163,586.96 PKR
    floors = CostFloors(
        cost_base=150000.0,
        zero_margin_10=150000.0 / 0.90,
        zero_margin_8=150000.0 / 0.92,
        floor_alfa=(150000.0 + 500.0) / 0.90,
        floor_digi_10=(150000.0 + 500.0) / 0.90,
        floor_digi_8=(150000.0 + 500.0) / 0.92,
    )
    # Sub-floor seller at 160,000 (below 8% floor 163,586.96)
    # Upper seller at 166,500 (below 10% floor 167,222.22, but gap above 8% floor is ~2,913 PKR, Tier 2)
    offers = [
        ScrapedOffer(vendor_name="LossSeller", price=160000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="UpperSeller8pct", price=166500.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)
    assert result.status == "Win via 8% Switch"
    assert result.effective_comm == "8.00%"
    assert result.final_price is not None
    assert result.final_price < 166500.0
    assert result.final_price >= floors.floor_digi_8
    assert "Filtered sub-floor offers" in result.reason
    assert "Triggered emergency 8% Faysal Bank rate" in result.reason
    assert "Applied dynamic adaptive split" in result.reason
    assert "capped winning sweet-spot price" in result.reason
    assert any("LossSeller" in d for d in result.dropped)
    assert any("UpperSeller8pct" in a for a in result.active_pool)


def test_tier3_winning_discount_reason_no_inflated_copy(sample_floors: CostFloors) -> None:
    # Item #3 scenario: Floor is 80,555.56, Competitor is 82,250 (gap = 1,694.44, Tier 3)
    # Tier 3 targets competitor - 500. Snaps to psychological price below ceiling.
    offers = [
        ScrapedOffer(vendor_name="TechHouse", price=82250.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Competitive Win"
    assert "Applied Tier 3 winning discount (Rs. 500) below competitor TechHouse" in result.reason
    assert "price is inflated" not in result.reason
    assert result.final_price == 81499
