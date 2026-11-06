"""Coverage-aware reporting and resume across the public DigiMall pipeline."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from openpyxl import load_workbook

from pricing_engine.calculator import calculate_floors
from pricing_engine.evaluator import evaluate_digi_pricing
from pricing_engine.models import ProductInput, ScrapedOffer, ScrapeResult
from pricing_engine.pipeline import build_output_record, create_skipped_platform_result


def partial_record(coverage: str = "INCOMPLETE") -> dict:
    product = ProductInput(
        1,
        "Haier",
        "Haier 120-316S6",
        0,
        0,
        0,
        150000,
        500,
        {"Brand": "Haier", "Name": "Haier 120-316S6", "Net Price": 150000},
    )
    floors = calculate_floors(150000)
    result = evaluate_digi_pricing(
        floors,
        ScrapeResult(
            offers=[ScrapedOffer("External", 179999, False, product.name)],
            pagination_complete=False,
            coverage_status=coverage,
            coverage_detail="Page audit detail",
        ),
    )
    return build_output_record(
        product,
        0,
        floors,
        170000,
        create_skipped_platform_result("AlfaMall"),
        result,
        personal_comm_pct=5,
        platform="digi",
    )


def test_output_record_provisional_status_goal_and_column_contract() -> None:
    record = partial_record()
    assert record["Final Price Digi"] is not None
    assert record["Digi Status"] == "PROVISIONAL"
    assert record["Digi 5% Goal"] == "PROVISIONAL"
    assert record["Digi Risk Alert"] == "INCOMPLETE_DISCOVERY"
    assert list(record)[0] == "S.NO"
    assert list(record)[-2:] == ["Alfa Risk Alert", "Digi Risk Alert"]


def test_csv_xlsx_preserve_coverage_numeric_prices_and_exclude_provisional_winners(
    tmp_path: Path,
) -> None:
    from pricing_engine.exporter import export_results, export_winning_5pct_results

    record = partial_record("INCOMPLETE")
    df = pd.DataFrame([record])
    manifest = export_results(
        df, "synthetic_catalog.csv", output_dir=tmp_path, platform="digi", render_panel=False
    )
    csv = pd.read_csv(manifest.latest_path)
    assert csv.iloc[0]["Digi Discovery Coverage"] == "INCOMPLETE"
    assert csv.iloc[0]["Digi Status"] == "PROVISIONAL"
    assert list(csv.columns)[-1] == "Digi Risk Alert"
    assert manifest.latest_xlsx_path is not None
    wb = load_workbook(manifest.latest_xlsx_path)
    ws = wb.active
    headers = {cell.value: cell.column for cell in ws[1]}
    assert ws.cell(2, headers["Digi Discovery Coverage"]).value == "INCOMPLETE"
    assert isinstance(ws.cell(2, headers["Final Price Digi"]).value, int)
    wb.close()
    assert (
        export_winning_5pct_results(
            df, "synthetic_catalog.csv", output_dir=tmp_path, platform="digi"
        )[2]
        == 0
    )
    # Defensive filtering also rejects an externally supplied stale winning goal.
    df["Digi 5% Goal"] = "WIN + 5% ACHIEVED"
    assert (
        export_winning_5pct_results(
            df, "synthetic_catalog.csv", output_dir=tmp_path, platform="digi"
        )[2]
        == 0
    )


def test_terminal_does_not_label_provisional_price_as_winner() -> None:
    from pricing_engine.pipeline import _format_summary_price, determine_platform_status

    record = partial_record()
    assert (
        determine_platform_status(
            record["Final Price Digi"], 179999, record["Digi Reason"], record["Digi Risk Alert"]
        )
        == "PROVISIONAL"
    )
    assert "PROVISIONAL" in _format_summary_price(
        record["Final Price Digi"], 179999, record["Digi Reason"], record["Digi Risk Alert"]
    )


def test_successful_capped_scan_is_an_observed_winner() -> None:
    record = partial_record("CAPPED")
    assert record["Digi Status"].startswith("WIN — OBSERVED")
    assert record["Digi Discovery Coverage"] == "CAPPED"
    assert record["Digi 5% Goal"] == "WIN + 5% ACHIEVED"


def test_observed_winning_price_renders_green() -> None:
    from rich.console import Console

    from pricing_engine.models import PlatformPricingResult
    from pricing_engine.pipeline import build_platform_decision_table

    result = PlatformPricingResult(
        40426,
        40426,
        40299,
        real_profit=575,
        status="Observed Price (3-page scan)",
        coverage_status="CAPPED",
    )
    table = build_platform_decision_table(
        create_skipped_platform_result("AlfaMall"), result, [], []
    )
    segments = list(Console(width=220).render(table))
    assert any(
        "40,299" in segment.text
        and segment.style
        and segment.style.color
        and segment.style.color.name == "green"
        for segment in segments
    )


def test_capped_no_matches_does_not_claim_timeout_or_dump_page_audit() -> None:
    from pricing_engine.digi_discovery import format_digimall_summary

    audit = {
        "query": "model",
        "required_pages": [1, 2, 3],
        "successful_pages": [1, 2, 3],
        "failed_pages": [],
    }
    scrape = ScrapeResult(
        coverage_status="CAPPED",
        pagination_complete=False,
        coverage_detail="RAW DIAGNOSTICS",
        query_audit=[audit] * 3,
    )
    result = evaluate_digi_pricing(calculate_floors(150000), scrape)
    assert result.final_price is not None
    assert "timed out" not in result.reason.lower()
    assert "RAW DIAGNOSTICS" not in result.reason
    assert "Not found" in result.reason
    summary = format_digimall_summary(scrape)
    assert "3 searches" in summary and "9/9 pages" in summary
    assert len(summary) < 130
    assert "required=" not in summary


def test_successful_capped_zero_offer_uses_existing_monopoly_math() -> None:
    floors = calculate_floors(150000)
    baseline = evaluate_digi_pricing(floors, [])
    capped = evaluate_digi_pricing(floors, ScrapeResult(coverage_status="CAPPED", pagination_complete=False))
    assert capped.final_price == baseline.final_price
    assert capped.real_profit == baseline.real_profit
    assert "Monopoly" in capped.status
    assert capped.coverage_status == "CAPPED"
    from pricing_engine.pipeline import determine_platform_status
    assert determine_platform_status(capped.final_price, None, capped.reason, "CAPPED_DISCOVERY").startswith("SOLO — OBSERVED")


def test_successful_capped_rejections_do_not_block_monopoly() -> None:
    capped = evaluate_digi_pricing(calculate_floors(150000), ScrapeResult(
        coverage_status="CAPPED", suspicious_rejected_count=1, rejected_count=1))
    assert capped.final_price is not None


def test_successful_scan_with_only_own_offer_uses_monopoly() -> None:
    result = evaluate_digi_pricing(calculate_floors(150000), ScrapeResult(
        coverage_status="CAPPED", suspicious_rejected_count=1,
        own_offers=[ScrapedOffer("Kia Chahiye", 180000, False, "Haier 120-316S6")]))
    assert result.final_price is not None


@pytest.mark.parametrize("coverage", ["COMPLETE", "CAPPED"])
def test_zero_eligible_offers_uses_monopoly_regardless_of_rejection_reason(coverage: str) -> None:
    from pricing_engine.models import DISCOVERY_CANDIDATES_REJECTED
    scrape = ScrapeResult(coverage_status=coverage, suspicious_rejected_count=18,
        rejected_count=897, discovery_status=DISCOVERY_CANDIDATES_REJECTED,
        rejection_reasons={"Missing required series tokens": 18})
    floors = calculate_floors(35500)
    result = evaluate_digi_pricing(floors, scrape)
    assert result.final_price == evaluate_digi_pricing(floors, []).final_price
    assert "Monopoly" in result.status


def test_observed_solo_summary_keeps_scan_caveat() -> None:
    from pricing_engine.pipeline import _format_summary_price
    assert "3-page scan" in _format_summary_price(171499, None, "Applied monopoly pricing", "CAPPED_DISCOVERY")


def test_discovery_policy_version_only_invalidates_affected_platforms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pricing_engine.checkpoint as checkpoint

    row = {"Brand": "Haier", "Name": "Haier 120-316S6", "Net Price": 150000}
    before = {
        p: checkpoint.compute_row_fingerprint(row, platform=p) for p in ("alfa", "digi", "all")
    }
    monkeypatch.setattr(checkpoint, "DIGI_DISCOVERY_POLICY_VERSION", "next-policy")
    after = {p: checkpoint.compute_row_fingerprint(row, platform=p) for p in before}
    assert before["alfa"] == after["alfa"]
    assert before["digi"] != after["digi"]
    assert before["all"] != after["all"]


def test_incomplete_pipeline_rows_retry_on_resume_and_capped_rows_do_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pricing_engine.checkpoint import load_checkpoint
    from pricing_engine.digi_discovery import DigiQueryPlan
    from pricing_engine.pipeline import run_pipeline

    monkeypatch.setattr(
        "pricing_engine.checkpoint.DEFAULT_CHECKPOINT_DIR", tmp_path / "checkpoints"
    )
    path = tmp_path / "synthetic_catalog.csv"
    path.write_text(
        "Brand,Name,Net Price\nHaier,Haier 120-316S6,150000\nHaier,Haier 120-826S6,150000\n",
        encoding="utf-8",
    )
    offers = [ScrapedOffer("External", 179999, False, "Haier 120-316S6")]
    incomplete = ScrapeResult(
        offers=offers,
        coverage_status="INCOMPLETE",
        coverage_detail="Page 2 failed",
        pagination_complete=False,
    )
    capped = ScrapeResult(
        offers=offers,
        coverage_status="CAPPED",
        coverage_detail="3-page cap",
        pagination_complete=False,
    )
    complete = ScrapeResult(offers=offers, coverage_status="COMPLETE")
    digi = AsyncMock(side_effect=[incomplete, capped, complete])
    db = MagicMock(is_configured=False)
    db.close = AsyncMock()

    async def run() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_digimall", digi),
            patch("pricing_engine.pipeline.SupabaseClient", return_value=db),
        ):
            first = await run_pipeline(
                path,
                output_path=tmp_path / "result.csv",
                verbose=False,
                platform="digi",
                concurrency=1,
            )
            assert first.iloc[0]["Digi Status"] == "PROVISIONAL"
            state = load_checkpoint(path)
            assert state is not None and state.pending_indices == [0]
            await run_pipeline(
                path,
                output_path=tmp_path / "result.csv",
                verbose=False,
                platform="digi",
                concurrency=1,
            )
        assert digi.call_count == 3
        assert isinstance(digi.call_args_list[0].args[1], DigiQueryPlan)
        assert digi.call_args_list[0].kwargs["context"] is digi.call_args_list[1].kwargs["context"]
        assert load_checkpoint(path) is None

    asyncio.run(run())


def test_ambiguous_first_row_retains_digi_coverage_and_final_risk_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pricing_engine.models import AmbiguousVariantConflict
    from pricing_engine.pipeline import run_pipeline

    monkeypatch.setattr(
        "pricing_engine.checkpoint.DEFAULT_CHECKPOINT_DIR", tmp_path / "checkpoints"
    )
    path = tmp_path / "ambiguity.csv"
    path.write_text(
        "Brand,Name,Net Price\nDawlance,DWT 255,50000\nHaier,120-316S6,150000\n", encoding="utf-8"
    )
    ambiguous = ScrapeResult(
        ambiguity_conflict=AmbiguousVariantConflict("DWT 255", ["C", "S"]),
        coverage_status="INCOMPLETE",
        coverage_detail="Page 2 failed",
        pagination_complete=False,
    )
    complete = ScrapeResult(coverage_status="COMPLETE")
    db = MagicMock(is_configured=False)
    db.close = AsyncMock()

    async def run() -> None:
        with (
            patch(
                "pricing_engine.pipeline.scrape_digimall",
                AsyncMock(side_effect=[ambiguous, complete]),
            ),
            patch("pricing_engine.pipeline.SupabaseClient", return_value=db),
            patch("pricing_engine.pipeline.sys.stdin.isatty", return_value=False),
        ):
            result = await run_pipeline(
                path,
                output_path=tmp_path / "result.csv",
                platform="digi",
                verbose=False,
                concurrency=1,
            )
        assert result.iloc[0]["Digi Discovery Coverage"] == "INCOMPLETE"
        assert result.iloc[0]["Digi Discovery Detail"] == "Page 2 failed"
        assert list(result.columns)[-2:] == ["Alfa Risk Alert", "Digi Risk Alert"]

    asyncio.run(run())
