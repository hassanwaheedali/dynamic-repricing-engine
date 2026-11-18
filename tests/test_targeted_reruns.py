"""Complete pipeline outputs, with deterministic synthetic discovery."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from pricing_engine.models import ScrapeResult
from pricing_engine.pipeline import run_pipeline
from pricing_engine.range_pipeline import run_range_pipeline
from pricing_engine.run_state import RunStore


@pytest.fixture
def discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    monkeypatch.setattr("pricing_engine.checkpoint.DEFAULT_CHECKPOINT_DIR", tmp_path / "state")
    alfa = AsyncMock(return_value=ScrapeResult(offers=[]))
    digi = AsyncMock(return_value=ScrapeResult(offers=[], coverage_status="COMPLETE"))
    for module in ("pipeline", "range_pipeline"):
        monkeypatch.setattr(f"pricing_engine.{module}.scrape_alfamall", alfa)
        monkeypatch.setattr(f"pricing_engine.{module}.scrape_digimall", digi)
    monkeypatch.setattr("pricing_engine.range_pipeline.RANGE_STAGGER_SECONDS", 0)
    database = MagicMock(is_configured=False)
    database.close = AsyncMock()
    monkeypatch.setattr("pricing_engine.pipeline.SupabaseClient", lambda: database)
    original_sleep = asyncio.sleep

    async def no_delay(delay: float, **kwargs: object) -> object:
        return await original_sleep(0, **kwargs)

    monkeypatch.setattr("pricing_engine.pipeline.asyncio.sleep", no_delay)
    return alfa


@pytest.mark.parametrize("range_mode", [False, True])
def test_corrected_name_reorders_and_reuses_complete_results(
    tmp_path: Path, discovery: AsyncMock, range_mode: bool,
) -> None:
    source = tmp_path / "products.csv"
    source.write_text("Brand,Name,Net Price\nSynthetic,ZX-101,10000\nSynthetic,ZX-202,20000\n")

    async def run(choice: str) -> pd.DataFrame:
        if range_mode:
            return await run_range_pipeline(
                source, export_dir=tmp_path / "out", verbose=False, platform="alfa", rerun=choice,
            )
        return await run_pipeline(
            source, output_path=tmp_path / "out.csv", verbose=False, platform="alfa", rerun=choice,
        )

    asyncio.run(run("full"))
    assert discovery.call_count == 2
    source.write_text("Brand,Name,Net Price\nSynthetic,ZX-202,20000\nSynthetic,ZX-103,10000\n")
    targeted = asyncio.run(run("targeted"))
    assert discovery.call_count == 3
    assert targeted["Name"].tolist() == ["ZX-202", "ZX-103"]
    assert targeted["S.NO"].tolist() == [1, 2]
    full = asyncio.run(run("full"))
    pd.testing.assert_frame_equal(targeted, full)


def test_explicit_targeted_incompatibility_never_runs_full(
    tmp_path: Path, discovery: AsyncMock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "products.csv"
    source.write_text("Brand,Name,Net Price\nSynthetic,ZX-101,10000\n")
    kwargs = {"output_path": tmp_path / "out.csv", "verbose": False, "platform": "alfa"}
    asyncio.run(run_pipeline(source, rerun="full", **kwargs))
    monkeypatch.setattr("config.MONOPOLY_PROFIT_PKR", 9999)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(ValueError, match="--rerun full"):
        asyncio.run(run_pipeline(source, rerun="targeted", **kwargs))
    assert discovery.call_count == 1


@pytest.mark.parametrize(("change", "expected_calls"), [
    ("cost", 1), ("multiple", 1), ("add", 1), ("remove", 0),
    ("reorder", 0), ("serials", 0), ("duplicate", 2), ("custom", 2), ("unchanged", 0),
])
def test_targeted_complete_output_equivalent_to_full(
    tmp_path: Path, discovery: AsyncMock, change: str, expected_calls: int,
) -> None:
    source = tmp_path / "products.csv"
    data = [{"Brand": "Synthetic", "Name": f"ZX-{idx}", "Net Price": idx * 100} for idx in (101, 202)]
    pd.DataFrame(data).to_csv(source, index=False)
    kwargs = {"output_path": tmp_path / "out.csv", "verbose": False, "platform": "alfa"}
    asyncio.run(run_pipeline(source, rerun="full", **kwargs))
    discovery.reset_mock()
    if change in {"cost", "multiple"}:
        data[0]["Net Price"] = 9999
        if change == "multiple":
            data[0]["Profit"] = 800
            data[1]["Profit"] = None
            # Column addition conservatively affects both rows.
            expected_calls = 2
    elif change == "add":
        data.append({"Brand": "Synthetic", "Name": "ZX-303", "Net Price": 30300})
    elif change == "remove":
        data.pop(0)
    elif change == "reorder":
        data.reverse()
    elif change == "serials":
        for idx, entry in enumerate(data):
            entry["S.NO"] = 90 - idx
    elif change == "duplicate":
        data.append(dict(data[0]))
    elif change == "custom":
        data[0]["Future Setting"] = "enabled"
        data[1]["Future Setting"] = "disabled"
    pd.DataFrame(data).to_csv(source, index=False)
    targeted = asyncio.run(run_pipeline(source, rerun="targeted", **kwargs))
    assert discovery.call_count == expected_calls
    assert len(targeted) == len(data)
    assert targeted["Name"].tolist() == [entry["Name"] for entry in data]
    full = asyncio.run(run_pipeline(source, rerun="full", **kwargs))
    pd.testing.assert_frame_equal(targeted, full)


def test_interrupted_run_recovers_only_finished_work(tmp_path: Path, discovery: AsyncMock) -> None:
    source = tmp_path / "products.csv"
    source.write_text("Brand,Name,Net Price\nSynthetic,ZX-101,10000\nSynthetic,ZX-202,20000\n")
    store = RunStore(source, "reprice", tmp_path / "state")

    async def scenario() -> None:
        started = asyncio.Event()

        async def interruptible(*args: object, **kwargs: object) -> ScrapeResult:
            if args[2] == "ZX-202":
                started.set()
                await asyncio.Event().wait()
            return ScrapeResult(offers=[])

        discovery.side_effect = interruptible
        task = asyncio.create_task(run_pipeline(source, output_path=tmp_path / "out.csv", platform="alfa", verbose=False, rerun="full"))
        await asyncio.wait_for(started.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        recovered = store._read(store.working_path)
        assert recovered is not None and set(recovered["completed_records"]) == {"0"}
        assert not store.snapshot_path.exists()
        discovery.reset_mock()
        discovery.side_effect = None
        discovery.return_value = ScrapeResult(offers=[])
        result = await run_pipeline(source, output_path=tmp_path / "out.csv", platform="alfa", verbose=False, rerun="targeted")
        assert len(result) == 2 and discovery.call_count == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("range_mode", [False, True])
def test_failed_platform_joins_other_platform_before_return(
    tmp_path: Path, discovery: AsyncMock, monkeypatch: pytest.MonkeyPatch, range_mode: bool,
) -> None:
    source = tmp_path / "products.csv"
    source.write_text("Brand,Name,Net Price\nSynthetic,ZX-101,10000\n")

    async def scenario() -> None:
        started, stopped = asyncio.Event(), asyncio.Event()

        async def blocked(*args: object, **kwargs: object) -> ScrapeResult:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
            return ScrapeResult(offers=[])

        async def failed(*args: object, **kwargs: object) -> ScrapeResult:
            await started.wait()
            raise RuntimeError("synthetic platform failure")

        discovery.side_effect = failed
        module = "range_pipeline" if range_mode else "pipeline"
        monkeypatch.setattr(f"pricing_engine.{module}.scrape_digimall", blocked)
        with pytest.raises(RuntimeError, match="synthetic platform failure"):
            if range_mode:
                await run_range_pipeline(source, export_dir=tmp_path / "out", verbose=False, rerun="full")
            else:
                await run_pipeline(source, output_path=tmp_path / "out.csv", verbose=False, rerun="full")
        assert stopped.is_set()

    asyncio.run(scenario())


def test_required_publication_failure_retains_snapshot_and_reuses_finished_work(
    tmp_path: Path, discovery: AsyncMock,
) -> None:
    source = tmp_path / "products.csv"
    source.write_text("Brand,Name,Net Price\nSynthetic,ZX-101,10000\n")
    output = tmp_path / "out.csv"
    options = {"output_path": output, "verbose": False, "platform": "alfa"}
    asyncio.run(run_pipeline(source, rerun="full", **options))
    store = RunStore(source, "reprice", tmp_path / "state")
    old_snapshot, old_output = store.snapshot_path.read_bytes(), output.read_bytes()
    source.write_text("Brand,Name,Net Price\nSynthetic,ZX-101,11000\n")
    original = Path.replace

    def fail_csv(stage: Path, destination: Path) -> Path:
        if destination == output:
            raise PermissionError("synthetic output lock")
        return original(stage, destination)

    with patch.object(Path, "replace", fail_csv), pytest.raises(PermissionError):
        asyncio.run(run_pipeline(source, rerun="full", **options))
    assert store.snapshot_path.read_bytes() == old_snapshot
    assert output.read_bytes() == old_output
    assert store.working_path.is_file()
    discovery.reset_mock()
    result = asyncio.run(run_pipeline(source, rerun="targeted", **options))
    assert discovery.call_count == 0
    assert result.iloc[0]["Net Price"] == 11000
    assert not store.working_path.exists()
    assert store.snapshot_path.read_bytes() != old_snapshot


def test_legacy_distinct_name_columns_remain_accepted(tmp_path: Path, discovery: AsyncMock) -> None:
    source = tmp_path / "products.csv"
    source.write_text("Brand,Name ,Name,Net Price\nSynthetic,ZX-101,Alternative title,10000\n")
    options = {"output_path": tmp_path / "out.csv", "verbose": False, "platform": "alfa"}
    full = asyncio.run(run_pipeline(source, rerun="full", **options))
    targeted = asyncio.run(run_pipeline(source, rerun="targeted", **options))
    pd.testing.assert_frame_equal(full, targeted)
    assert discovery.call_count == 1


@pytest.mark.parametrize("untracked_headers", [False, True])
def test_dependency_mutation_during_run_cannot_publish_mixed_results(
    tmp_path: Path, discovery: AsyncMock, monkeypatch: pytest.MonkeyPatch,
    untracked_headers: bool,
) -> None:
    import config
    if untracked_headers:
        monkeypatch.setitem(config.ALFAMALL_CONFIG.headers, "Authorization", "private-test-value")
    source = tmp_path / "products.csv"
    source.write_text("Brand,Name,Net Price\nSynthetic,ZX-101,10000\n")

    async def changing(*args: object, **kwargs: object) -> ScrapeResult:
        import config
        monkeypatch.setattr(config, "MONOPOLY_PROFIT_PKR", config.MONOPOLY_PROFIT_PKR + 1)
        return ScrapeResult(offers=[])

    discovery.side_effect = changing
    output = tmp_path / "out.csv"
    with pytest.raises(ValueError, match="dependencies changed"):
        asyncio.run(run_pipeline(source, rerun="full", output_path=output, verbose=False, platform="alfa"))
    assert not output.exists()


def test_untracked_headers_disable_reuse_without_persisting_secrets(
    tmp_path: Path, discovery: AsyncMock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config
    secret = "untracked-sensitive-test-header"
    monkeypatch.setitem(config.ALFAMALL_CONFIG.headers, "Authorization", secret)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    source = tmp_path / "products.csv"
    source.write_text("Brand,Name,Net Price\nSynthetic,ZX-101,10000\n")
    options = {"output_path": tmp_path / "out.csv", "verbose": False, "platform": "alfa"}
    asyncio.run(run_pipeline(source, rerun="full", **options))
    store = RunStore(source, "reprice", tmp_path / "state")
    assert secret not in store.snapshot_path.read_text()
    discovery.reset_mock()
    with pytest.raises(ValueError, match="--rerun full"):
        asyncio.run(run_pipeline(source, rerun="targeted", **options))
    assert discovery.call_count == 0
