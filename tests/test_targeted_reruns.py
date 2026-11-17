"""Complete pipeline outputs, with deterministic synthetic discovery."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from pricing_engine.models import ScrapeResult
from pricing_engine.pipeline import run_pipeline
from pricing_engine.range_pipeline import run_range_pipeline


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
