"""Contract assertions independent of the implementation's internal helpers."""

import json
from pathlib import Path

import pytest

from pricing_engine.digi_discovery import generate_digimall_plan
from pricing_engine.matcher import referee_match

BASELINE = Path(__file__).parents[1] / "tasks/architecture-consolidation-baseline.json"
CATALOG = json.loads(BASELINE.read_text(encoding="utf-8"))["catalog"] if BASELINE.exists() else []
HARDWARE_QUERY_FIXTURE = Path(__file__).parent / "fixtures/hardware_query_regressions.json"
HARDWARE_QUERY_CASES = json.loads(HARDWARE_QUERY_FIXTURE.read_text(encoding="utf-8"))["cases"]
HARDWARE_QUERY_DELTAS = {case["item"]: case for case in HARDWARE_QUERY_CASES}


def test_pg_m01_query_deltas_are_limited_to_reviewed_catalog_cases() -> None:
    """The original architecture snapshot stays intact; eight reviewed query changes are explicit."""
    assert len(HARDWARE_QUERY_CASES) == len(HARDWARE_QUERY_DELTAS) == 8
    assert set(HARDWARE_QUERY_DELTAS) == {7, 28, 34, 56, 62, 72, 73, 100}
    catalog_by_item = {case["item"]: case for case in CATALOG}
    for item, delta in HARDWARE_QUERY_DELTAS.items():
        assert delta["title"] == catalog_by_item[item]["title"]
        assert delta["brand"] == catalog_by_item[item]["brand"]
        assert delta["reason"]
        assert delta["queries"] != [
            branch["queries"] for branch in catalog_by_item[item]["digi_plan"]["branches"]
        ]


@pytest.mark.parametrize("case", CATALOG, ids=lambda c: str(c["item"]))
def test_catalog_model_queries_preserve_coverage_and_order(case: dict) -> None:
    """Preserve historical queries except the explicitly reviewed PG-M01 fixture deltas."""
    expected = case["digi_plan"]
    if "error" in expected:
        # The recorded model-loss defect must now produce usable numeric queries.
        corrected = generate_digimall_plan(case["title"], case["brand"])
        assert corrected.branches
        assert all(any(char.isdigit() for char in branch.model) for branch in corrected.branches)
        return
    plan = generate_digimall_plan(case["title"], case["brand"])
    expected_queries = (
        HARDWARE_QUERY_DELTAS[case["item"]]["queries"]
        if case["item"] in HARDWARE_QUERY_DELTAS
        else [branch["queries"] for branch in expected["branches"]]
    )
    assert [list(branch.queries) for branch in plan.branches] == expected_queries


@pytest.mark.parametrize("case", CATALOG, ids=lambda c: str(c["item"]))
def test_catalog_self_matches_keep_model_identity(case: dict) -> None:
    decision = referee_match(case["title"], case["title"], case["brand"])
    assert decision.is_match or decision.is_base_match or decision.match_tier == 3
