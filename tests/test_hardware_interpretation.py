"""PG-M01: source model evidence, descriptive counts and disabled connectivity."""

import csv
from pathlib import Path

import pytest

from pricing_engine.matcher import (
    extract_product_slots,
    extract_search_query_and_model,
    referee_match,
)


@pytest.mark.parametrize("count", ["4-Way", "3-Speed", "6-Step", "12-Way"])
def test_feature_count_never_supplies_model_or_capability(count: str) -> None:
    target = "Dawlance 2 Ton Inverter Glacier 45 Pro T3 Floor Standing Air Conditioner"
    candidate = (
        "Dawlance 2 Ton Inverter Floor Standing Heat & Cool Air Conditioner (White) | "
        f"Glacier Pro 45 T3 | {count} Air Throw | Gold Fin Coils"
    )
    slots = extract_product_slots(candidate, "Dawlance")
    assert not slots.anchor
    assert slots.guarded_facets.capabilities == {"T3"}
    decision = referee_match(target, candidate, "Dawlance")
    assert decision.match_tier == 1, decision.reason
    assert decision.compatibility_notice is None


@pytest.mark.parametrize("word", ["ECO", "eco", "ET", "XYQ"])
def test_spaced_short_model_never_gains_a_synthetic_attached_suffix(word: str) -> None:
    title = f"Dawlance MD 15 {word} 20 Ltr Microwave Oven"
    _, model = extract_search_query_and_model(title, "Dawlance")
    assert word.upper() not in model.split()[0].upper()
    decision = referee_match("Dawlance MD 15 20 Ltr Microwave Oven", title, "Dawlance")
    assert decision.match_tier == 1, decision.reason
    assert decision.compatibility_notice and word.upper() in decision.compatibility_notice


@pytest.mark.parametrize("separator", [" ", " (", " - "])
def test_loose_designation_is_not_a_verified_hardware_capability(separator: str) -> None:
    ending = ")" if separator == " (" else ""
    slots = extract_product_slots(
        f"Dawlance DWT-1165{separator}ECO{ending} Washing Machine", "Dawlance"
    )
    assert slots.anchor == "DWT-1165"
    assert "ECO" not in slots.guarded_facets.capabilities


@pytest.mark.parametrize("suffix", ["ES", "ES8", "FLP", "XYQ"])
def test_originally_attached_extra_model_component_remains_a_constraint(suffix: str) -> None:
    decision = referee_match(
        "Dawlance DWT-1165 Washing Machine",
        f"Dawlance DWT-1165-{suffix} Washing Machine",
        "Dawlance",
    )
    assert decision.match_tier is None
    assert not decision.is_match and not decision.is_base_match


@pytest.mark.parametrize("code", ["ES", "PL", "FLP", "XYQ"])
def test_catalog_declared_codes_keep_exact_omission_and_conflict_contract(code: str) -> None:
    target = f"Dawlance DWT-1165 {code} Washing Machine"
    same = referee_match(target, target, "Dawlance")
    omitted = referee_match(target, "Dawlance DWT-1165 Washing Machine", "Dawlance")
    conflict = referee_match(target, f"Dawlance DWT-1165 {code}8 Washing Machine", "Dawlance")
    assert same.match_tier == 1
    assert omitted.match_tier == 2
    assert conflict.match_tier is None


@pytest.mark.parametrize("target_join", [" ", "-"])
@pytest.mark.parametrize("candidate_join", [" ", "-"])
def test_conflicting_declared_code_cannot_turn_into_an_advisory(
    target_join: str, candidate_join: str
) -> None:
    decision = referee_match(
        f"Dawlance DWT-1165{target_join}ES Washing Machine",
        f"Dawlance DWT-1165{candidate_join}ES8 Washing Machine",
        "Dawlance",
    )
    assert decision.match_tier is None
    assert not decision.is_base_match


def test_declared_code_order_cannot_be_lost_to_set_comparison() -> None:
    decision = referee_match(
        "Dawlance DWT-1165 ES PL Washing Machine",
        "Dawlance DWT-1165 PL ES Washing Machine",
        "Dawlance",
    )
    assert decision.match_tier is None


@pytest.mark.parametrize("target_join", [" ", "-"])
@pytest.mark.parametrize("candidate_join", [" ", "-"])
def test_compound_model_codes_keep_literal_order_and_attachment(
    target_join: str, candidate_join: str
) -> None:
    target = f"Dawlance DWT-1165{target_join}ES{target_join}PL Washing Machine"
    same = f"Dawlance DWT-1165{candidate_join}ES{candidate_join}PL Washing Machine"
    opposite = f"Dawlance DWT-1165{candidate_join}PL{candidate_join}ES Washing Machine"
    assert referee_match(target, same, "Dawlance").match_tier == 1
    assert referee_match(target, opposite, "Dawlance").match_tier is None
    slots = extract_product_slots(same, "Dawlance")
    assert [tag.code for tag in slots.model_tags] == ["ES", "PL"]
    assert all(tag.attached == (candidate_join == "-") for tag in slots.model_tags)


@pytest.mark.parametrize("separator", ["-", "_"])
def test_separately_written_compound_codes_are_not_reported_as_omitted(separator: str) -> None:
    target = "Dawlance DWT-1165 ES PL Washing Machine"
    same = referee_match(target, f"Dawlance DWT-1165 ES{separator}PL Washing Machine", "Dawlance")
    reversed_codes = referee_match(
        target, f"Dawlance DWT-1165 PL{separator}ES Washing Machine", "Dawlance"
    )
    different_code = referee_match(
        target, f"Dawlance DWT-1165 ES{separator}ES8 Washing Machine", "Dawlance"
    )
    assert same.match_tier == 1, same.reason
    assert same.missing_modifier is None
    assert reversed_codes.match_tier is None
    assert different_code.match_tier is None


def test_declared_code_cannot_be_satisfied_by_later_descriptive_prose() -> None:
    decision = referee_match(
        "Dawlance DWT-1165 ECO Washing Machine",
        "Dawlance DWT-1165 Washing Machine ECO Friendly",
        "Dawlance",
    )
    assert decision.match_tier == 2
    assert decision.missing_modifier == "ECO"


@pytest.mark.parametrize("suffix", ["Wi-Fi", "WI-FI", "WiFi"])
def test_source_attachment_survives_existing_technical_spelling_normalization(suffix: str) -> None:
    decision = referee_match("Acme AX-5432 Appliance", f"Acme AX-5432-{suffix} Appliance", "Acme")
    assert decision.match_tier is None


@pytest.mark.parametrize("prefix", ["IOT", "WIFI", "SMART", "WI-FI"])
def test_disabled_word_in_literal_model_prefix_is_not_removed(prefix: str) -> None:
    target = f"Acme {prefix}-5432 Appliance"
    slots = extract_product_slots(target, "Acme")
    assert prefix.replace("-", "") in slots.anchor.replace("-", "")
    decision = referee_match(target, "Acme AX-5432 Appliance", "Acme")
    assert decision.match_tier is None


def test_technical_prefix_normalization_preserves_later_bound_suffix() -> None:
    decision = referee_match("Acme WI-FI-5432 Appliance", "Acme WI-FI-5432-ES Appliance", "Acme")
    assert decision.match_tier is None


@pytest.mark.parametrize(
    "count", ["4-Way", "3-Speed", "12-Way", "4-Way-Air-Throw", "4 - Way", "4- Way", "4 -Way"]
)
def test_feature_count_is_descriptive_on_both_sides(count: str) -> None:
    plain = "Dawlance 2 Ton Inverter Glacier 45 Pro T3 Floor Standing Air Conditioner"
    observed = plain + " | " + count
    assert not extract_product_slots(observed, "Dawlance").anchor
    for target, candidate in [(plain, observed), (observed, plain)]:
        decision = referee_match(target, candidate, "Dawlance")
        assert decision.match_tier == 1, decision.reason
        assert decision.compatibility_notice is None


@pytest.mark.parametrize("prefix", ["HAF", "AX"])
def test_catalog_declared_short_model_code_matches_originally_glued_code(prefix: str) -> None:
    decision = referee_match(
        f"Acme {prefix} 50 MB Air Fryer", f"Acme {prefix}-50MB Air Fryer", "Acme"
    )
    assert decision.match_tier == 1, decision.reason


@pytest.mark.parametrize("anchor", ["AX-50", "AX 50", "AX-5432", "AX 5432"])
def test_declared_code_order_includes_glued_components(anchor: str) -> None:
    target = f"Acme {anchor} ES PL Air Fryer"
    glued_anchor = anchor.replace(" ", "-")
    correct = referee_match(target, f"Acme {glued_anchor}ES PL Air Fryer", "Acme")
    reversed_codes = referee_match(target, f"Acme {glued_anchor}PL ES Air Fryer", "Acme")
    assert correct.match_tier == 1, correct.reason
    assert reversed_codes.match_tier is None


def test_candidate_only_designation_cannot_bypass_series_uncertainty() -> None:
    # A matching catalog-declared code is valid model evidence. A seller-only
    # addition must not gain that authority or resolve unrelated series prose.
    for designation in ["", " ECO"]:
        decision = referee_match(
            "Acme AX-5432 Premium Appliance",
            f"Acme AX-5432{designation} Chrome Appliance",
            "Acme",
        )
        assert decision.match_tier is None, decision.reason


@pytest.mark.parametrize("code", ["CX", "ET", "XYQ"])
@pytest.mark.parametrize("separator", [" ", "-"])
def test_matching_catalog_code_preserves_descriptive_model_aliases(
    code: str, separator: str
) -> None:
    target = f"Acme AX 5432 {code} Handheld Corded Garment Steam Iron"
    candidate = f"Acme AX-5432{separator}{code} Steam Iron Fast and efficient ironing"
    decision = referee_match(target, candidate, "Acme")
    assert decision.match_tier == 1, decision.reason
    assert decision.compatibility_notice is None


@pytest.mark.parametrize("designation", ["", " ECO"])
@pytest.mark.parametrize(
    "target,candidate",
    [
        ("Acme AX-5432{tag} Refrigerator", "Acme AX-5433{tag} Refrigerator"),
        ("Acme AX-5432 ES{tag} Refrigerator", "Acme AX-5432 ES8{tag} Refrigerator"),
        ("Acme AX-5432{tag} E-Chrome Refrigerator", "Acme AX-5432{tag} Chrome Refrigerator"),
        ("Acme AX-5432{tag} E-Chrome Refrigerator", "Acme AX-5432{tag} Chrome Pro Refrigerator"),
        ("Acme AX-5432{tag} T3 AC", "Acme AX-5432{tag} T4 AC"),
        ("Acme AX-5432{tag} White Refrigerator", "Acme AX-5432{tag} Black Refrigerator"),
        ("Acme AX-5432{tag} 8KG Washing Machine", "Acme AX-5432{tag} 10KG Washing Machine"),
    ],
)
def test_declared_or_extra_words_never_override_genuine_conflicts(
    target: str, candidate: str, designation: str
) -> None:
    for target_tag in ["", designation]:
        decision = referee_match(
            target.format(tag=target_tag), candidate.format(tag=designation), "Acme"
        )
        assert decision.match_tier is None, decision.reason


@pytest.mark.parametrize(
    "prose",
    [
        "Smart Frequency",
        "WiFi",
        "Wi-Fi",
        "IOT",
        "Without WiFi",
        "Non-Smart",
        "WiFi Without WiFi",
        "Smart Non-Smart",
        "Android TV",
        "Google TV",
        "WebOS",
        "Vidaa",
    ],
)
def test_connectivity_prose_has_no_capability_or_advisory_effect(prose: str) -> None:
    target = "Dawlance DWT-1165 Washing Machine"
    # Keep a TV OS description inside the same product's feature clause rather
    # than asking this test to change existing macro-category mismatch policy.
    if "TV" in prose or prose in {"WebOS", "Vidaa"}:
        target = "TCL 32S5400 32 Inch LED TV"
        brand = "TCL"
    else:
        brand = "Dawlance"
    for left, right in [(target, target + " " + prose), (target + " " + prose, target)]:
        decision = referee_match(left, right, brand)
        assert decision.match_tier == 1, decision.reason
        assert decision.compatibility_notice is None
        for slots in (decision.target_slots, decision.candidate_slots):
            assert slots is not None
            facets = slots.guarded_facets
            assert not (
                {"WIFI", "IOT", "SMART"}
                & (
                    facets.capabilities
                    | facets.negative_capabilities
                    | facets.ambiguous_capabilities
                )
            )


@pytest.mark.parametrize("suffix", ["IOT", "SMART", "WIFI"])
def test_disabled_prose_never_erases_a_literal_sku_component(suffix: str) -> None:
    target = f"Acme AX-5432-{suffix} Appliance"
    equal = referee_match(target, target, "Acme")
    different = referee_match(target, "Acme AX-5432-REV Appliance", "Acme")
    assert equal.match_tier == 1, equal.reason
    assert different.match_tier is None


@pytest.mark.parametrize(
    "phrase",
    [" Smart Frequency", " WiFi", " Without WiFi", " | 4-Way Air Throw", " | Premium Performance"],
)
def test_curated_catalog_descriptive_appends_preserve_exact_identity(phrase: str) -> None:
    corpus = Path(__file__).parents[1] / "data/inputs/100_Products/Book1.csv"
    with corpus.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 100
    for row_number, row in enumerate(rows, 1):
        decision = referee_match(row["Title"], row["Title"] + phrase, row["Brand"])
        assert decision.match_tier == 1, (row_number, row["Title"], decision.reason)
        assert decision.compatibility_notice is None
