import pytest

from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.models import CostFloors, ScrapedOffer


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


def test_alfa_skip_when_all_sellers_below_floor(sample_floors: CostFloors) -> None:
    # Floor is 80,555. Both sellers are below floor.
    offers = [
        ScrapedOffer(vendor_name="V1", price=79000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="V2", price=80000.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Skip / Unviable"
    assert result.final_price is None
    assert result.real_profit == 0
    assert len(result.dropped) == 2


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
    assert result.final_price == 82899
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
        ScrapedOffer(vendor_name="UpperSellerTight", price=79500.0, is_sold_out=False, raw_title="AC"),
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
        ScrapedOffer(vendor_name="UpperSellerHigh", price=81000.0, is_sold_out=False, raw_title="AC"),
    ]
    result_10 = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers_10)
    assert result_10.status == "Safe Win (10% Tier)"
    assert result_10.effective_comm == "10.00%"
    assert result_10.final_price is not None
    assert result_10.final_price < 81000.0
    assert result_10.final_price >= sample_floors.floor_digi_10
    assert len(result_10.dropped) == 1


def test_digi_skip_when_all_below_8_percent(sample_floors: CostFloors) -> None:
    # 8% floor is 78,804.35. All sellers below 78,000.
    offers = [
        ScrapedOffer(vendor_name="SellerA", price=77000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="SellerB", price=76500.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Skip / Unviable"
    assert result.final_price is None
    assert result.real_profit == 0
    assert result.effective_comm == "8.00%"


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
        ScrapedOffer(vendor_name="YZ international", price=445099.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="Home Cart", price=463549.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="Scroll-N-Shop.pk", price=489999.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)

    # Must win at Default 10% Tier, NOT 8% Emergency Switch!
    assert result.status == "Safe Win (10% Tier)"
    assert result.effective_comm == "10.00%"
    assert result.final_price == 478899
    assert result.real_profit == 10296  # +Rs. 10,296 (~10k sweet spot)
    assert len(result.dropped) == 4
    assert "sweet-spot price Rs. 478,899" in result.reason



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
        ScrapedOffer(vendor_name="iShopping Team", price=162299.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="Tech House", price=165999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="Musab Mall", price=165999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="YZ international", price=166099.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)

    # Tech House (165,999) < 10% floor (168,309), so 10% loses -> Triggers Emergency 8% Switch!
    # Gap is 1,349 PKR (800-1500 range) -> Undercuts by Rs. 200 to 165,799 (.799 psychological ending)
    assert result.status == "Win via 8% Switch"
    assert result.effective_comm == "8.00%"
    assert result.final_price == 165799
    assert result.real_profit == round((165799 * 0.92) - 150978)  # +Rs. 1,557 profit
    assert len(result.dropped) == 1
    assert "emergency 8% bank rate" in result.reason

