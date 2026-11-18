"""Explicit execution choices without network calls or invented row identifiers."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd
import pytest

from pricing_engine.models import ProductInput
from pricing_engine.pipeline import parse_product_input
from pricing_engine.run_control import RunExecution
from pricing_engine.run_signature import build_signatures
from pricing_engine.run_state import RunStore


@pytest.fixture
def catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, ProductInput, RunStore]:
    monkeypatch.setattr("pricing_engine.checkpoint.DEFAULT_CHECKPOINT_DIR", tmp_path / "state")
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    source = tmp_path / "catalog.csv"
    values = {"Brand": "Synthetic", "Name": "ZX-101", "Net Price": 10000}
    pd.DataFrame([values]).to_csv(source, index=False)
    product = parse_product_input(0, pd.Series(values))
    store = RunStore(source, "reprice", tmp_path / "state")
    return source, product, store


def seed(product: ProductInput, store: RunStore, signature: str | None = None) -> None:
    compatible = signature or build_signatures("reprice", "alfa", 0).processing
    state = store.begin([product.raw_row], compatible, {}, None)
    store.record(state, 0, {"S.NO": 1, **product.raw_row, "Final Price Alfa": 19999}, "")
    store.promote(state)


def test_headless_default_is_full_and_explicit_first_targeted_is_allowed(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path,
) -> None:
    source, product, store = catalog
    with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa", rerun="targeted") as owner:
        owner.prepare([product])
        assert owner.comparison.to_run == [0]
    seed(product, store)
    with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa") as owner:
        owner.prepare([product])
        assert owner.cached == {} and owner.comparison.to_run == [0]


@pytest.mark.parametrize("answer", ["1", "2"])
def test_terminal_choice_is_explicit(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, answer: str,
) -> None:
    source, product, store = catalog
    second = parse_product_input(1, pd.Series({"Brand": "Synthetic", "Name": "ZX-202", "Net Price": 20000}))
    compatible = build_signatures("reprice", "alfa", 0).processing
    state = store.begin([product.raw_row, second.raw_row], compatible, {}, None)
    store.record(state, 0, {"S.NO": 1, **product.raw_row, "Final Price Alfa": 19999}, "")
    store.record(state, 1, {"S.NO": 2, **second.raw_row, "Final Price Alfa": 29999}, "")
    store.promote(state)

    modified = parse_product_input(0, pd.Series({**product.raw_row, "Net Price": 12000}))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    answers = iter(["invalid", "", answer])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa") as owner:
        owner.prepare([modified, second])
        assert bool(owner.cached) == (answer == "1")


@pytest.mark.parametrize("eof", [False, True])
def test_terminal_cancellation_does_not_mutate_snapshot(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, eof: bool,
) -> None:
    source, product, store = catalog
    seed(product, store)
    previous = store.snapshot_path.read_bytes()
    modified = parse_product_input(0, pd.Series({**product.raw_row, "Net Price": 12000}))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def cancel(_: str) -> str:
        if eof:
            raise EOFError
        return "q"

    monkeypatch.setattr("builtins.input", cancel)
    with (
        pytest.raises(ValueError),
        RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa") as owner,
    ):
        owner.prepare([modified])
    assert store.snapshot_path.read_bytes() == previous
    assert not store.working_path.exists()


def test_incompatible_target_requires_explicit_terminal_full_choice(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, product, store = catalog
    seed(product, store, signature="outdated")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    answers = iter(["1", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa", rerun="targeted") as owner:
        owner.prepare([product])
        assert owner.cached == {} and owner.comparison.to_run == [0]


def test_legacy_state_is_not_first_run_or_deleted_on_selection(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path,
) -> None:
    source, product, store = catalog
    store.legacy_path.parent.mkdir(parents=True)
    store.legacy_path.write_text('{"old_format":true}')
    with (
        pytest.raises(ValueError, match="--rerun full"),
        RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa", rerun="targeted") as owner,
    ):
        owner.prepare([product])
    assert store.legacy_path.read_text() == '{"old_format":true}'


def test_changed_column_summary_and_current_serials(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    source, product, store = catalog
    seed(product, store)
    modified = parse_product_input(0, pd.Series({**product.raw_row, "Net Price": 12000}))
    with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa", rerun="targeted") as owner:
        owner.prepare([modified])
        assert owner.comparison.changed == {0: ["Net Price"]}
    assert "Net Price" in capsys.readouterr().out


def test_invalid_and_conflicting_execution_choices(catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path) -> None:
    source, _, _ = catalog
    with pytest.raises(ValueError, match="conflicts"):
        RunExecution(source, "range", [tmp_path], platform="alfa", rerun="targeted", resume=False)


def test_tty_without_compatible_baseline_runs_full_without_prompting(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, product, store = catalog
    store.legacy_path.parent.mkdir(parents=True)
    store.legacy_path.write_text('{"old_format":true}', encoding="utf-8")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("unexpected prompt without baseline"))

    with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa") as owner:
        owner.prepare([product])
        assert owner.cached == {}
        assert owner.comparison.to_run == [0]

    seed(product, store, signature="outdated")
    with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa") as owner:
        owner.prepare([product])
        assert owner.cached == {}
        assert owner.comparison.to_run == [0]


def test_tty_unchanged_input_runs_full_without_prompting(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, product, store = catalog
    seed(product, store)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("unexpected prompt when no changes detected"))

    with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa") as owner:
        owner.prepare([product])
        assert owner.cached == {}
        assert owner.comparison.to_run == [0]


def test_candidates_rejected_promotes_to_snapshot(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path,
) -> None:
    source, product, store = catalog

    async def run() -> None:
        with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa") as owner:
            owner.prepare([product])

            async def outcome() -> dict[str, object]:
                return {
                    "S.NO": 1,
                    **product.raw_row,
                    "Alfa Risk Alert": "CANDIDATES_REJECTED",
                    "Alfa Discovery Coverage": "COMPLETE",
                }

            await owner.worker(0, outcome())
            owner.before_publication()
            owner.finish()

    asyncio.run(run())
    assert store.snapshot_path.is_file()
    assert not store.working_path.exists()


def test_unchanged_duplicates_reprocess_without_prompt(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, product, store = catalog
    state = store.begin([product.raw_row, product.raw_row], build_signatures("reprice", "alfa", 0).processing, {}, None)
    for idx in range(2):
        store.record(state, idx, {"S.NO": idx + 1, **product.raw_row}, "")
    store.promote(state)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("unchanged duplicates must not prompt"))
    with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa") as owner:
        owner.prepare([product, product])
        assert owner.cached == {} and owner.comparison.to_run == [0, 1]


def test_incompatible_baseline_announces_changed_components(
    catalog: tuple[Path, ProductInput, RunStore], tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    source, product, store = catalog
    signatures = build_signatures("reprice", "alfa", 0)
    state = store.begin([product.raw_row], signatures.processing, {}, None)
    state["signature_components"] = {**signatures.components, "source:matcher": "old"}
    state["signature"] = "outdated"
    store.record(state, 0, {"S.NO": 1, **product.raw_row, "Final Price Alfa": 19999}, "")
    store.promote(state)

    with RunExecution(source, "reprice", [tmp_path / "out"], platform="alfa") as owner:
        owner.prepare([product])

    out = capsys.readouterr().out
    assert "changed:" in out
    assert "source:matcher" in out
