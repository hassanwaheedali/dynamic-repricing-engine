"""Conservative reconciliation and provenance independent of marketplace policies."""

from __future__ import annotations

from pathlib import Path

import pytest

from pricing_engine.run_state import RunStore, reconcile_rows


def row(name: str, cost: int = 100, **extra: object) -> dict[str, object]:
    return {"Brand": "Synthetic", "Name": name, "Net Price": cost, **extra}


def test_reconciliation_ignores_serials_and_positions() -> None:
    previous = [row("Model-A", **{"S.NO": 1}), row("Model-B", **{"S.NO": 2})]
    current = [row("Model-B", **{"S.NO": 7}), row("Model-A")]
    comparison = reconcile_rows(current, previous, {0, 1})
    assert comparison.reuse == {0: 1, 1: 0}
    assert comparison.to_run == []


def test_changed_columns_are_reported_only_for_unique_brand_name() -> None:
    previous = [row("Model-A", Category="One"), row("Model-B")]
    current = [row("Model-A", 200, Category="Two"), row("Corrected-B")]
    comparison = reconcile_rows(current, previous, {0, 1})
    assert comparison.changed == {0: ["Category", "Net Price"]}
    assert comparison.unmatched == [1]
    assert comparison.previous_only == [1]
    assert comparison.to_run == [0, 1]


def test_duplicates_and_pending_rows_never_reuse() -> None:
    rows = [row("Duplicate"), row("Duplicate"), row("Pending")]
    comparison = reconcile_rows(rows, rows, {0, 1})
    assert comparison.reuse == {}
    assert comparison.uncertain == [0, 1]
    assert comparison.pending == [2]


def test_unknown_column_changes_require_execution() -> None:
    comparison = reconcile_rows([row("A", FutureSetting="on")], [row("A")], {0})
    assert comparison.changed == {0: ["FutureSetting"]}
    assert comparison.to_run == [0]


def test_snapshot_promotion_and_stale_working_selection(tmp_path: Path) -> None:
    source = tmp_path / "catalog.csv"
    source.write_text("input", encoding="utf-8")
    store = RunStore(source, "reprice", tmp_path / "state")
    first = store.begin([row("A")], "compatible", {}, None)
    store.record(first, 0, {"Final Price Alfa": 199}, "")
    stale_working = store.working_path.read_bytes()
    store.promote(first)
    store.working_path.write_bytes(stale_working)
    completed, baseline, issue = store.select("compatible")
    assert completed is not None and baseline == completed
    assert not issue
    assert baseline["run_id"] == first["run_id"]


def test_incompatible_work_cannot_hide_valid_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "catalog.csv"
    source.write_text("input", encoding="utf-8")
    store = RunStore(source, "reprice", tmp_path / "state")
    first = store.begin([row("A")], "current", {}, None)
    store.record(first, 0, {"result": 199}, "")
    store.promote(first)
    store.begin([row("A")], "other", {}, first)
    completed, baseline, issue = store.select("current")
    assert completed is not None and baseline == completed
    assert not issue


def test_incomplete_attempt_retains_snapshot_and_retry_status(tmp_path: Path) -> None:
    source = tmp_path / "catalog.csv"
    source.write_text("input", encoding="utf-8")
    store = RunStore(source, "range", tmp_path / "state")
    state = store.begin([row("A"), row("B")], "sig", {}, None)
    store.record(state, 0, {"result": 100}, "SERVER_DOWN")
    with pytest.raises(ValueError, match="pending"):
        store.promote(state)
    _, recovered, issue = store.select("sig")
    assert not issue and recovered is not None
    assert recovered["pending_indices"] == [0, 1]


def test_corrupt_and_legacy_state_are_not_first_runs(tmp_path: Path) -> None:
    source = tmp_path / "catalog.csv"
    source.write_text("input", encoding="utf-8")
    store = RunStore(source, "reprice", tmp_path / "state")
    store.working_path.parent.mkdir(parents=True)
    store.working_path.write_text("{broken", encoding="utf-8")
    assert store.has_prior_state
    assert store.select("sig")[2]


@pytest.mark.parametrize("damage", ["parent_run_id", "signature", "record", "observation", "row_key"])
def test_malformed_work_cannot_hide_completed_snapshot(tmp_path: Path, damage: str) -> None:
    source = tmp_path / "catalog.csv"
    source.write_text("input")
    store = RunStore(source, "reprice", tmp_path / "state")
    completed = store.begin([row("A")], "sig", {}, None)
    store.record(completed, 0, {"result": 199}, "")
    store.promote(completed)
    working = store.begin([row("A")], "sig", {}, completed)
    store.record(working, 0, {"result": 200}, "")
    if damage in {"parent_run_id", "signature"}:
        working.pop(damage)
    elif damage == "record":
        working["completed_records"]["0"] = []
    elif damage == "observation":
        working["observed_at"].clear()
    else:
        working["completed_records"]["00"] = working["completed_records"].pop("0")
    store.save(working)
    _, selected, issue = store.select("sig")
    assert selected is not None and selected["run_id"] == completed["run_id"]
    assert not issue


def test_select_reports_changed_signature_components(tmp_path: Path) -> None:
    source = tmp_path / "catalog.csv"
    source.write_text("input", encoding="utf-8")
    store = RunStore(source, "reprice", tmp_path / "state")
    state = store.begin([row("A")], "old-sig", {}, None)
    state["signature_components"] = {"source:matcher": "old-hash", "pricing": "same-hash"}
    store.record(state, 0, {"result": 199}, "")
    store.promote(state)

    _, baseline, issue = store.select(
        "new-sig",
        components={"source:matcher": "new-hash", "pricing": "same-hash"},
    )
    assert baseline is None
    assert "changed: source:matcher" in issue
    assert "--rerun full" in issue
