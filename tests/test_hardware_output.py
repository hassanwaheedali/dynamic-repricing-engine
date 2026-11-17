"""Selected exact advisories reuse existing records, rendering and exports."""

from pathlib import Path

import openpyxl
import pandas as pd
import pytest
from rich.console import Console

from pricing_engine import checkpoint, pipeline
from pricing_engine.calculator import calculate_floors
from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.exporter import export_results
from pricing_engine.models import ProductInput, ScrapeResult
from pricing_engine.offer_processing import finalize_offers, parse_offers_with_tiers

TARGET = "Dawlance DWT-1165 Washing Machine"


def _observed_result(designation: str = "") -> ScrapeResult:
    title = f"Dawlance DWT-1165 {designation} Washing Machine"
    parsed = parse_offers_with_tiers(
        [
            {
                "title": title,
                "vendor": {"name": "External Seller"},
                "sold_out": False,
                "variant_detail": {"original_price": "85000"},
            }
        ],
        "DWT-1165",
        "Dawlance",
        TARGET,
    )
    return finalize_offers(
        ScrapeResult(offers=parsed[0], base_offers=parsed[1], sibling_offers=parsed[2]),
        "DWT-1165",
    )


def _product(sno: int) -> ProductInput:
    return ProductInput(
        sno=sno,
        brand="Dawlance",
        name=TARGET,
        length=0,
        width=0,
        height=0,
        net_price=72000,
        profit=500,
        raw_row={"Brand": "Dawlance", "Name": TARGET, "Net Price": 72000},
    )


@pytest.mark.parametrize("platform", ["all", "alfa", "digi"])
def test_actual_exact_advisory_reaches_csv_and_existing_xlsx_yellow_fill(
    tmp_path: Path, platform: str
) -> None:
    floors = calculate_floors(72000)
    records = []
    for sno, designation in [(1, "ECO"), (2, "")]:
        result = _observed_result(designation)
        records.append(
            pipeline.build_output_record(
                _product(sno),
                0,
                floors,
                0,
                evaluate_alfa_pricing(floors, result),
                evaluate_digi_pricing(floors, result),
                platform=platform,
            )
        )
    manifest = export_results(
        pd.DataFrame(records),
        "hardware.csv",
        output_dir=tmp_path,
        render_panel=False,
        platform=platform,
    )
    exported = pd.read_csv(manifest.latest_path, dtype=str, keep_default_na=False)
    assert exported.columns[0] == "S.NO"
    reason_columns = [c for c in exported.columns if c in {"Alfa Reason", "Digi Reason"}]
    assert reason_columns
    for column in reason_columns:
        assert exported.loc[0, column].count("CROSS-CHECK NOTICE") == 1
        assert "'ECO'" in exported.loc[0, column]
        assert "CROSS-CHECK NOTICE" not in exported.loc[1, column]
    xlsx = manifest.latest_xlsx_path
    assert xlsx is not None
    workbook = openpyxl.load_workbook(xlsx)
    sheet = workbook.active
    assert sheet is not None
    headers = {cell.value: cell.column for cell in sheet[1]}
    for column in reason_columns:
        warned = sheet.cell(2, headers[column])
        clean = sheet.cell(3, headers[column])
        assert warned.value == exported.loc[0, column]
        assert warned.fill.fill_type == "solid"
        assert warned.fill.fgColor.rgb == "00FFF9C4"
        assert clean.fill.fill_type != "solid"
    workbook.close()


def test_actual_exact_advisory_uses_existing_card_and_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _observed_result("ECO")
    floors = calculate_floors(72000)
    alfa = evaluate_alfa_pricing(floors, result)
    digi = evaluate_digi_pricing(floors, result)
    console = Console(record=True, width=160, force_terminal=False)
    monkeypatch.setattr(pipeline, "console", console)
    with console.capture() as captured:
        pipeline.render_audit_card(
            _product(1), 0, floors, 0, "DWT-1165", result, result, alfa, digi
        )
    rendered = captured.get()
    assert "CROSS-CHECK" in rendered and "ECO" in rendered
    assert "CROSS-CHECK" in pipeline._format_summary_price(
        alfa.final_price, alfa.min_price, alfa.reason, "NONE"
    )
    assert {offer.match_tier for offer in result.offers} == {1}
    assert result.active_modifier_fallback is None


@pytest.mark.parametrize("platform", ["all", "alfa", "digi"])
def test_existing_fingerprint_invalidates_previous_matcher_policy(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    row = _product(1).raw_row
    current = checkpoint.compute_row_fingerprint(row, platform=platform)
    monkeypatch.setattr(checkpoint, "MATCHER_POLICY_VERSION", "previous-matcher-policy")
    previous = checkpoint.compute_row_fingerprint(row, platform=platform)
    assert current != previous
