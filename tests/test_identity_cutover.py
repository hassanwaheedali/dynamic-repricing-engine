"""Owner-approved identity outcomes at the existing referee boundary.

Real titles come from the November 20 marketplace projections and source CSVs.
The /KB and gallon substitutions are controlled contrasts, not seller captures.
"""

import pytest

from pricing_engine.matcher import MatchDecision, extract_product_slots, referee_match

HAIER = "Haier HPU-24CE03/X-IK 2 Ton Conventional Floor Standing Cabinet Air Conditioner"
MIDEA = "Midea MSEZ1C-18HRFN1-QC2 1.5 Ton Titan Series Inverter Wall Mounted Split Air Conditioner"


def compare(
    title: str, seller: str, brand: str, prepared: bool, metadata_brand: str = ""
) -> MatchDecision:
    target = extract_product_slots(title, brand) if prepared else title
    return referee_match(target, seller, brand, candidate_brand=metadata_brand)


@pytest.mark.parametrize("prepared", [False, True], ids=["raw", "prepared"])
@pytest.mark.parametrize(
    "candidate, expected",
    [
        ("Haier HPU-24CE03/X-IK 2 Ton Cabinet Air Conditioner", 1),
        (
            "Haier HPU-24CE03/YB(IK) 2.0 Ton Floor Standing AC Air Conditioner "
            "(With Kit And Installation) On Installments By Connect Mall",
            None,
        ),
        (HAIER.replace("/X-IK", "/KB"), None),
        ("Haier AC 2 Ton Floor Standing HPU-24CE03 | Free Installation by Haier", 2),
    ],
    ids=["full-model", "opposing-compound", "opposing-kb", "omitted-qualifier"],
)
def test_book1_85_cabinet_qualifier(candidate: str, expected: int | None, prepared: bool) -> None:
    decision = compare(HAIER, candidate, "Haier", prepared)
    assert decision.match_tier == expected, decision.reason
    if expected == 2:
        assert "X-IK" in (decision.compatibility_notice or "").upper()


@pytest.mark.parametrize("prepared", [False, True], ids=["raw", "prepared"])
def test_book1_89_reordered_indoor_listing_lacks_proof_of_exact_package(prepared: bool) -> None:
    # Alfa 200426182507320405, no independent package or chassis equivalence.
    listing = (
        "Midea 1.5 Ton Heat & Cool Inverter Split Ac 18HRFN1-QC2W-IDU-INV-EZ1-TITAN "
        "Low Noise Operation for quiet comfort"
    )
    assert compare(MIDEA, listing, "Midea", prepared, "Motorola").match_tier != 1


@pytest.mark.parametrize("prepared", [False, True], ids=["raw", "prepared"])
def test_book1_89_full_model_remains_exact(prepared: bool) -> None:
    listing = "Midea MSEZ1C-18 HRFN1-QC2 Titan DC Inverter Heat And Cool Split Air Conditioner"
    assert compare(MIDEA, listing, "Midea", prepared).match_tier == 1


@pytest.mark.parametrize("prepared", [False, True], ids=["raw", "prepared"])
@pytest.mark.parametrize("left,right", [(50, 50), (20, 50), (50, 20), (30, 50), (50, 30)])
def test_declared_gallon_volume_guards_commercial_tiers(
    left: int, right: int, prepared: bool
) -> None:
    decision = compare(
        f"Unigas {left} Gallons Plus", f"Unigas {right} Gallons Plus", "Unigas", prepared
    )
    assert decision.match_tier == (1 if left == right else None), decision.reason


@pytest.mark.parametrize("prepared", [False, True], ids=["raw", "prepared"])
def test_finac_stock_red_rejects_black_finish_after_model(prepared: bool) -> None:
    target = "DAW R/F 9149WB AVANTE PEARL RED"
    listing = (
        "Dawlance - Refrigerator - Direct Cool, Non-Inverter, Top Freezer - 9149WB - "
        "Chrome Hairline Black Finish - Dawlance - Official Warranty - (TechElite)"
    )
    assert compare(target, listing, "Dawlance", prepared).match_tier is None
