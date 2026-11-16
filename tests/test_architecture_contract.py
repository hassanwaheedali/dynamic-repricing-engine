"""Contract assertions independent of the implementation's internal helpers."""

import json
from pathlib import Path

import pytest

from pricing_engine.digi_discovery import generate_digimall_plan
from pricing_engine.matcher import referee_match

BASELINE = Path(__file__).parents[1] / "tasks/architecture-consolidation-baseline.json"
CATALOG = json.loads(BASELINE.read_text(encoding="utf-8"))["catalog"] if BASELINE.exists() else []


@pytest.mark.parametrize("case", CATALOG, ids=lambda c: str(c["item"]))
def test_catalog_model_queries_preserve_coverage_and_order(case: dict) -> None:
    """Approved parsing fixes may update the explicit baseline after review."""
    expected = case["digi_plan"]
    if "error" in expected:
        # The recorded model-loss defect must now produce usable numeric queries.
        corrected = generate_digimall_plan(case["title"], case["brand"])
        assert corrected.branches
        assert all(any(char.isdigit() for char in branch.model) for branch in corrected.branches)
        return
    plan = generate_digimall_plan(case["title"], case["brand"])
    assert [list(branch.queries) for branch in plan.branches] == [
        branch["queries"] for branch in expected["branches"]
    ]


@pytest.mark.parametrize("case", CATALOG, ids=lambda c: str(c["item"]))
def test_catalog_self_matches_keep_model_identity(case: dict) -> None:
    decision = referee_match(case["title"], case["title"], case["brand"])
    assert decision.is_match or decision.is_base_match or decision.match_tier == 3
