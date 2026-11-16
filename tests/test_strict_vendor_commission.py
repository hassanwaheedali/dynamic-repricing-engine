"""Comprehensive regression & invariant suite for strictly fixed per-vendor commission policy."""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import openpyxl
import pandas as pd
import pytest
from rich.console import Console

import config
import pricing_engine.pipeline as pipeline_mod
from pricing_engine.calculator import (
    calculate_cost_base,
    calculate_effective_target_profit,
    calculate_floors,
    resolve_insurance_pct,
)
from pricing_engine.checkpoint import COMMISSION_POLICY_VERSION, compute_row_fingerprint
from pricing_engine.evaluator import (
    evaluate_alfa_pricing,
    evaluate_digi_pricing,
)
from pricing_engine.exporter import (
    export_range_results,
    export_results,
    export_winning_5pct_results,
)
from pricing_engine.models import CostFloors, ProductInput, ScrapedOffer, ScrapeResult
from pricing_engine.pipeline import (
    build_output_record,
    create_skipped_platform_result,
    parse_product_input,
    process_product_with_offers,
    render_summary_table,
    run_pipeline,
)
from pricing_engine.range_pipeline import MarketRange, build_range_record


def _make_product(
    *,
    name: str = "Gree 1.5 Ton GS-18PITH11W",
    net_price: float = 140000.0,
    length: float = 100.0,
    width: float = 40.0,
    height: float = 90.0,
    extra_raw: dict[str, Any] | None = None,
) -> ProductInput:
    row: dict[str, Any] = {
        "S.NO": 1,
        "Brand": "Gree",
        "Name": name,
        "Length": length,
        "Width": width,
        "Height": height,
        "Net Price": net_price,
    }
    if extra_raw:
        row.update(extra_raw)
    return parse_product_input(0, pd.Series(row))


def test_digimall_strictly_fixed_8_pct_never_switches_across_scenarios() -> None:
    """REQ-01/REQ-04: DigiMall uses configured 8.00% in every evaluation branch with zero switching."""
    with (
        patch.object(config, "ALFA_COMMISSION_PCT", 10.0),
        patch.object(config, "DIGI_COMMISSION_PCT", 8.0),
        patch.object(config, "COMPANY_MIN_PROFIT_PKR", 500.0),
        patch.object(config, "MONOPOLY_PROFIT_PKR", 4000.0),
        patch.object(config, "FALLBACK_PROFIT_PKR", 500.0),
    ):
        cost_base = 150000.0
        floors = calculate_floors(cost_base=cost_base)
        expected_floor = (cost_base + 500.0) / 0.92
        assert floors.floor_digi == pytest.approx(expected_floor)

        tight_offer = math.ceil(expected_floor) + 40.0
        mid_offer = (cost_base + 500.0) / 0.90 - 500.0
        upper_offer = expected_floor + 3500.0
        capped_offer = expected_floor + 4000.0
        prov_offer = expected_floor + 2500.0

        scenarios: list[tuple[list[ScrapedOffer] | ScrapeResult, str, float | None]] = [
            ([], "Monopoly Win", None),
            (
                [ScrapedOffer("SubSeller", expected_floor - 1500.0, False, "AC")],
                "Safe Fallback",
                None,
            ),
            (
                [ScrapedOffer("TightSeller", tight_offer, False, "AC")],
                "Competitive Win",
                tight_offer,
            ),
            ([ScrapedOffer("MidBandSeller", mid_offer, False, "AC")], "Competitive Win", mid_offer),
            (
                [
                    ScrapedOffer("SubSeller", expected_floor - 2000.0, False, "AC"),
                    ScrapedOffer("UpperSeller", upper_offer, False, "AC"),
                ],
                "Competitive Win",
                upper_offer,
            ),
            (
                ScrapeResult(
                    offers=[ScrapedOffer("CappedSeller", capped_offer, False, "AC")],
                    is_success=True,
                    coverage_status="CAPPED",
                ),
                "Observed Price (3-page scan)",
                capped_offer,
            ),
            (
                ScrapeResult(
                    offers=[ScrapedOffer("ProvSeller", prov_offer, False, "AC")],
                    is_success=True,
                    coverage_status="INCOMPLETE",
                ),
                "Provisional Price",
                prov_offer,
            ),
            (
                ScrapeResult(offers=[], is_success=False, status_code=503, error_detail="503"),
                "Server Down / Unreachable",
                None,
            ),
        ]

        for scenario, expected_status, ceiling in scenarios:
            res = evaluate_digi_pricing(floors, scenario)
            assert res.status == expected_status
            assert res.effective_comm == "8.00%"
            assert "10% Tier" not in res.status
            assert "8% Switch" not in res.status
            assert "emergency" not in res.reason.lower()
            assert "faysal bank rate" not in res.reason.lower()
            assert "spread" not in res.reason.lower()
            if expected_status == "Server Down / Unreachable":
                assert res.final_price is None
            else:
                assert res.final_price is not None
                assert res.final_price >= floors.floor_digi
                assert res.real_profit == round((res.final_price * 0.92) - cost_base)
                if ceiling is not None:
                    assert res.final_price < ceiling


@pytest.mark.parametrize("digi_rate", [2.0, 8.0, 25.0])
def test_alfamall_strictly_fixed_independent_of_digimall(digi_rate: float) -> None:
    """REQ-02: AlfaMall calculations and evaluations remain invariant to DIGI_COMMISSION_PCT."""
    with (
        patch.object(config, "ALFA_COMMISSION_PCT", 10.0),
        patch.object(config, "DIGI_COMMISSION_PCT", digi_rate),
        patch.object(config, "COMPANY_MIN_PROFIT_PKR", 500.0),
        patch.object(config, "MONOPOLY_PROFIT_PKR", 4000.0),
    ):
        floors = calculate_floors(cost_base=100000.0)
        assert floors.zero_margin_alfa == pytest.approx(100000.0 / 0.90)
        assert floors.floor_alfa == pytest.approx(100500.0 / 0.90)

        offers = [ScrapedOffer("Comp1", 116000.0, False, "AC")]
        res_comp = evaluate_alfa_pricing(floors, offers)
        res_mono = evaluate_alfa_pricing(floors, [])
        assert res_comp.effective_comm == "10.00%"
        assert res_mono.effective_comm == "10.00%"
        assert res_comp.final_price == 114499
        assert res_mono.final_price == 115999


@pytest.mark.parametrize(
    ("alfa_pct", "digi_pct"),
    [
        (10.0, 8.0),
        (8.0, 10.0),
        (7.0, 12.0),
        (7.5, 9.5),
        (7.125, 8.375),
        (0.0, 5.0),
    ],
)
def test_parametrized_vendor_rates_end_to_end_csv_and_xlsx(
    tmp_path: Path, alfa_pct: float, digi_pct: float
) -> None:
    """REQ-03/05/06/07: Arbitrary configured rates flow identically through math, evaluator, CSV, and XLSX."""
    alfa_payout = 1.0 - (alfa_pct / 100.0)
    digi_payout = 1.0 - (digi_pct / 100.0)
    exp_alfa_str = config.format_commission_pct(alfa_pct)
    exp_digi_str = config.format_commission_pct(digi_pct)

    with (
        patch.object(config, "ALFA_COMMISSION_PCT", alfa_pct),
        patch.object(config, "DIGI_COMMISSION_PCT", digi_pct),
        patch.object(config, "COMPANY_MIN_PROFIT_PKR", 600.0),
        patch.object(config, "FALLBACK_PROFIT_PKR", 600.0),
    ):
        # Product 1: AC (0% insurance), Product 2: LED TV (category insurance > 0%)
        ac = _make_product(name="Gree 1.5 Ton GS-18PITH11W", net_price=140000.0)
        led = _make_product(
            name="TCL 55 Inch 55P755 UHD Google LED TV",
            net_price=130000.0,
            length=135.0,
            width=15.0,
            height=80.0,
            extra_raw={"S.NO": 2},
        )
        led_ins = resolve_insurance_pct(led.name, brand=led.brand)
        assert led_ins > 0.0

        rec_ac = process_product_with_offers(
            ac,
            [ScrapedOffer("CompA", round((145040.0 + 600.0) / alfa_payout + 3000), False, ac.name)],
            [ScrapedOffer("CompD", round((145040.0 + 600.0) / digi_payout + 3000), False, ac.name)],
            personal_comm_pct=5.0,
        )
        rec_led = process_product_with_offers(led, [], [])

        # Verify independent cost math & explicit schema columns
        for prod, rec, ins in [(ac, rec_ac, 0.0), (led, rec_led, led_ins)]:
            ship = rec["Shipping Estimate"]
            cost_base = (prod.net_price + ship) * (1.0 + ins / 100.0)
            assert rec["Alfa Commission"] == exp_alfa_str
            assert rec["Digi Commission"] == exp_digi_str
            assert rec["Total Without Profit (Alfa)"] == round(cost_base / alfa_payout)
            assert rec["Total Without Profit (Digi)"] == round(cost_base / digi_payout)
            assert rec["Alfa Real Profit"] == round(
                (rec["Final Price Alfa"] * alfa_payout) - cost_base
            )
            assert rec["Digi Real Profit"] == round(
                (rec["Final Price Digi"] * digi_payout) - cost_base
            )
            for forbidden in (
                "Commision",
                "Digi Effective Commision",
                "Total Without Profit",
                "Calculation",
            ):
                assert forbidden not in rec

        # Platform-scoped isolation in build_output_record
        rec_alfa_only = process_product_with_offers(ac, [], [], platform="alfa")
        assert rec_alfa_only["Alfa Commission"] == exp_alfa_str
        assert "Digi Commission" not in rec_alfa_only
        assert "Total Without Profit (Digi)" not in rec_alfa_only

        rec_digi_only = process_product_with_offers(ac, [], [], platform="digi")
        assert rec_digi_only["Digi Commission"] == exp_digi_str
        assert "Alfa Commission" not in rec_digi_only
        assert "Total Without Profit (Alfa)" not in rec_digi_only

        # Export mixed insured + uninsured rows to CSV + XLSX + dedicated single-vendor artifacts
        df = pd.DataFrame([rec_ac, rec_led])
        out_dir = tmp_path / f"exp_{alfa_pct}_{digi_pct}"
        manifest = export_results(
            df=df,
            source_filename="rates_matrix.csv",
            output_dir=out_dir,
            render_panel=False,
            personal_comm_pct=5.0,
        )
        csv_df = pd.read_csv(manifest.latest_path)
        assert list(csv_df["Alfa Commission"]) == [exp_alfa_str, exp_alfa_str]
        assert list(csv_df["Digi Commission"]) == [exp_digi_str, exp_digi_str]
        assert "Insurance" in csv_df.columns
        assert (
            list(csv_df.columns).index("Insurance")
            == list(csv_df.columns).index("Digi Commission") + 1
        )
        assert "Calculation" not in csv_df.columns
        assert "Commision" not in csv_df.columns

        assert manifest.latest_xlsx_path is not None
        wb = openpyxl.load_workbook(manifest.latest_xlsx_path)
        ws = wb.active
        assert ws is not None
        headers = [cell.value for cell in ws[1]]
        col_map = {h: openpyxl.utils.get_column_letter(i + 1) for i, h in enumerate(headers)}
        alfa_c = col_map["Alfa Commission"]
        digi_c = col_map["Digi Commission"]

        exp_alfa_p_str = f"{round(alfa_payout, 6):g}"
        exp_digi_p_str = f"{round(digi_payout, 6):g}"
        for row_num in (2, 3):
            assert ws[f"{alfa_c}{row_num}"].value == pytest.approx(round(alfa_pct / 100.0, 6))
            assert ws[f"{digi_c}{row_num}"].value == pytest.approx(round(digi_pct / 100.0, 6))

            twop_alfa_formula = str(ws[f"{col_map['Total Without Profit (Alfa)']}{row_num}"].value)
            twop_digi_formula = str(ws[f"{col_map['Total Without Profit (Digi)']}{row_num}"].value)
            prof_alfa_formula = str(ws[f"{col_map['Alfa Real Profit']}{row_num}"].value)
            prof_digi_formula = str(ws[f"{col_map['Digi Real Profit']}{row_num}"].value)

            assert f"{alfa_c}{row_num}" in twop_alfa_formula and exp_alfa_p_str in twop_alfa_formula
            assert f"{digi_c}{row_num}" in twop_digi_formula and exp_digi_p_str in twop_digi_formula
            assert f"{alfa_c}{row_num}" in prof_alfa_formula and exp_alfa_p_str in prof_alfa_formula
            assert f"{digi_c}{row_num}" in prof_digi_formula and exp_digi_p_str in prof_digi_formula
            assert f"{digi_c}{row_num}" not in twop_alfa_formula
            assert f"{alfa_c}{row_num}" not in twop_digi_formula

        # Verify dedicated Alfa-only and Digi-only outputs preserve mixed Insurance and isolate vendor cols
        alfa_csv = out_dir / "csv" / "rates_matrix_repriced_alfa_latest.csv"
        alfa_xlsx = out_dir / "xlsx" / "rates_matrix_repriced_alfa_latest.xlsx"
        digi_csv = out_dir / "csv" / "rates_matrix_repriced_digi_latest.csv"
        digi_xlsx = out_dir / "xlsx" / "rates_matrix_repriced_digi_latest.xlsx"
        for p in (alfa_csv, alfa_xlsx, digi_csv, digi_xlsx):
            assert p.is_file(), f"Missing dedicated artifact: {p}"

        alfa_df = pd.read_csv(alfa_csv)
        assert list(alfa_df["Alfa Commission"]) == [exp_alfa_str, exp_alfa_str]
        assert "Digi Commission" not in alfa_df.columns
        assert "Total Without Profit (Digi)" not in alfa_df.columns
        assert "Insurance" in alfa_df.columns
        assert (
            list(alfa_df.columns).index("Insurance")
            == list(alfa_df.columns).index("Alfa Commission") + 1
        )

        digi_df = pd.read_csv(digi_csv)
        assert list(digi_df["Digi Commission"]) == [exp_digi_str, exp_digi_str]
        assert "Alfa Commission" not in digi_df.columns
        assert "Total Without Profit (Alfa)" not in digi_df.columns
        assert "Insurance" in digi_df.columns
        assert (
            list(digi_df.columns).index("Insurance")
            == list(digi_df.columns).index("Digi Commission") + 1
        )

        wb_a = openpyxl.load_workbook(alfa_xlsx)
        ws_a = wb_a.active
        assert ws_a is not None
        h_a = [c.value for c in ws_a[1]]
        m_a = {h: openpyxl.utils.get_column_letter(i + 1) for i, h in enumerate(h_a)}
        assert "Digi Commission" not in m_a
        assert ws_a[f"{m_a['Alfa Commission']}2"].value == pytest.approx(round(alfa_pct / 100.0, 6))
        assert exp_alfa_p_str in str(ws_a[f"{m_a['Total Without Profit (Alfa)']}3"].value)

        wb_d = openpyxl.load_workbook(digi_xlsx)
        ws_d = wb_d.active
        assert ws_d is not None
        h_d = [c.value for c in ws_d[1]]
        m_d = {h: openpyxl.utils.get_column_letter(i + 1) for i, h in enumerate(h_d)}
        assert "Alfa Commission" not in m_d
        assert ws_d[f"{m_d['Digi Commission']}2"].value == pytest.approx(round(digi_pct / 100.0, 6))
        assert exp_digi_p_str in str(ws_d[f"{m_d['Total Without Profit (Digi)']}3"].value)


def test_high_precision_decimal_and_negative_zero_commission_parity(tmp_path: Path) -> None:
    """REQ-03/07: >2-decimal rates retain exact precision in CSV/XLSX and -0.0 normalizes to +0.0."""
    assert config.format_commission_pct(-0.0) == "0.00%"
    with patch.object(config, "ALFA_COMMISSION_PCT", -0.0):
        zero_pct = config.get_alfa_commission_pct()
        assert zero_pct == 0.0
        assert math.copysign(1.0, zero_pct) == 1.0
        assert config.get_alfa_payout_rate() == 1.0

    with pytest.raises(ValueError):
        config.get_vendor_commission_pct(cast(Any, None))

    prod = _make_product(name="Gree 1.5 Ton GS-18PITH11W", net_price=100000.0)
    with (
        patch.object(config, "ALFA_COMMISSION_PCT", 7.125),
        patch.object(config, "DIGI_COMMISSION_PCT", 8.375),
    ):
        rec = process_product_with_offers(prod, [], [])
        assert rec["Alfa Commission"] == "7.125%"
        assert rec["Digi Commission"] == "8.375%"

        manifest = export_results(
            pd.DataFrame([rec]),
            source_filename="precision.csv",
            output_dir=tmp_path / "prec",
            render_panel=False,
        )
        csv_df = pd.read_csv(manifest.latest_path)
        assert csv_df["Alfa Commission"].iloc[0] == "7.125%"
        assert csv_df["Digi Commission"].iloc[0] == "8.375%"

        assert manifest.latest_xlsx_path is not None
        wb = openpyxl.load_workbook(manifest.latest_xlsx_path)
        ws = wb.active
        assert ws is not None
        headers = [c.value for c in ws[1]]
        col_map = {h: openpyxl.utils.get_column_letter(i + 1) for i, h in enumerate(headers)}
        a_col = col_map["Alfa Commission"]
        d_col = col_map["Digi Commission"]

        assert ws[f"{a_col}2"].value == pytest.approx(0.07125, abs=1e-9)
        assert ws[f"{d_col}2"].value == pytest.approx(0.08375, abs=1e-9)
        assert "0.92875" in str(ws[f"{col_map['Total Without Profit (Alfa)']}2"].value)
        assert "0.91625" in str(ws[f"{col_map['Total Without Profit (Digi)']}2"].value)
        assert f"1-{a_col}2" in str(ws[f"{col_map['Alfa Real Profit']}2"].value)
        assert f"1-{d_col}2" in str(ws[f"{col_map['Digi Real Profit']}2"].value)


def test_live_config_mutation_takes_effect_immediately_without_reload() -> None:
    """REQ-03: Sequential in-process config mutations update calculations without stale caches."""
    prod = _make_product(net_price=100000.0, length=50.0, width=50.0, height=60.0)
    results: list[tuple[str, str, int, int]] = []

    for alfa_pct, digi_pct in [(10.0, 8.0), (12.0, 7.5), (9.0, 11.5)]:
        with (
            patch.object(config, "ALFA_COMMISSION_PCT", alfa_pct),
            patch.object(config, "DIGI_COMMISSION_PCT", digi_pct),
        ):
            rec = process_product_with_offers(prod, [], [])
            results.append(
                (
                    rec["Alfa Commission"],
                    rec["Digi Commission"],
                    rec["Total Without Profit (Alfa)"],
                    rec["Total Without Profit (Digi)"],
                )
            )

    assert results[0][0] == "10.00%" and results[0][1] == "8.00%"
    assert results[1][0] == "12.00%" and results[1][1] == "7.50%"
    assert results[2][0] == "9.00%" and results[2][1] == "11.50%"
    assert len({r[2] for r in results}) == 3
    assert len({r[3] for r in results}) == 3


def test_no_competitor_band_or_gap_overrides_configured_commission() -> None:
    """REQ-01/REQ-04: Competitive gap size or band never switches commission percentage."""
    cost_base = 100000.0
    for digi_pct in (10.0, 7.5, 7.125):
        with (
            patch.object(config, "DIGI_COMMISSION_PCT", digi_pct),
            patch.object(config, "COMPANY_MIN_PROFIT_PKR", 500.0),
        ):
            floors = calculate_floors(cost_base)
            floor = floors.floor_digi
            competitor_prices = [
                None,
                floor - 2500.0,
                floor - 500.0,
                math.ceil(floor) + 60.0,
                floor + 1200.0,
                floor + 5000.0,
                floor + 25000.0,
            ]
            for price in competitor_prices:
                offers = [] if price is None else [ScrapedOffer("Seller", price, False, "AC")]
                res = evaluate_digi_pricing(floors, offers)
                assert res.effective_comm == config.format_commission_pct(digi_pct)
                assert res.final_price is not None
                assert res.final_price >= floors.floor_digi


def test_obsolete_symbols_removed_and_legacy_raw_columns_stripped() -> None:
    """REQ-05/REQ-06: Old switching APIs and legacy/generated raw columns are completely eliminated."""
    for removed_cfg in (
        "DIGI_STANDARD_COMMISSION_PCT",
        "DIGI_LEVERAGE_COMMISSION_PCT",
        "get_digi_standard_payout_rate",
        "get_digi_leverage_payout_rate",
    ):
        assert not hasattr(config, removed_cfg)

    field_names = set(CostFloors.__dataclass_fields__.keys())
    for removed_field in (
        "zero_margin_10",
        "zero_margin_8",
        "floor_digi_10",
        "floor_digi_8",
    ):
        assert removed_field not in field_names
    assert {"zero_margin_alfa", "zero_margin_digi", "floor_alfa", "floor_digi"}.issubset(
        field_names
    )

    # Simulate catalog originally loaded with mixed-case legacy, generated, Unnamed, and blank headers
    legacy_prod = _make_product(
        extra_raw={
            "Commision": "10.00%",
            "commision": "9.00%",
            "Digi Effective Commision": "10.00%",
            "DIGI EFFECTIVE COMMISION": "8.00%",
            "Total Without Profit": 99999,
            "total without profit": 77777,
            "Calculation": 88888,
            "calculation": 66666,
            "Insurance": "2.00%",
            "Unnamed: 0": 999,
            "": "blank_junk",
            "CustomTag": "KEEP_ME",
        }
    )
    floors = calculate_floors(calculate_cost_base(legacy_prod.net_price, 5040.0))
    alfa_res = evaluate_alfa_pricing(floors, [])
    digi_res = evaluate_digi_pricing(floors, [])

    rec = build_output_record(
        product=legacy_prod,
        shipping=5040.0,
        floors=floors,
        baseline_calc=0.0,
        alfa_res=alfa_res,
        digi_res=digi_res,
    )
    assert rec["CustomTag"] == "KEEP_ME"
    for forbidden in (
        "Commision",
        "commision",
        "Digi Effective Commision",
        "DIGI EFFECTIVE COMMISION",
        "Total Without Profit",
        "total without profit",
        "Calculation",
        "calculation",
        "Insurance",
        "Unnamed: 0",
        "",
    ):
        assert forbidden not in rec

    rng_rec = build_range_record(legacy_prod, MarketRange(10, 20, 1), MarketRange(10, 20, 1))
    assert rng_rec["CustomTag"] == "KEEP_ME"
    for forbidden in (
        "Commision",
        "commision",
        "Digi Effective Commision",
        "DIGI EFFECTIVE COMMISION",
        "Total Without Profit",
        "total without profit",
        "Calculation",
        "calculation",
        "Insurance",
        "Unnamed: 0",
        "",
    ):
        assert forbidden not in rng_rec


def test_unrelated_pricing_policies_preserved_and_checkpoint_version_bumped() -> None:
    """REQ-08: Profit floors, insurance order, personal commission, and checkpoint version hold."""
    assert COMMISSION_POLICY_VERSION == "fixed-vendor-comm-v2"

    with (
        patch.object(config, "ALFA_COMMISSION_PCT", 10.0),
        patch.object(config, "DIGI_COMMISSION_PCT", 8.0),
        patch.object(config, "COMPANY_MIN_PROFIT_PKR", 500.0),
        patch.object(config, "MONOPOLY_PROFIT_PKR", 4000.0),
    ):
        eff_target = calculate_effective_target_profit(500.0, 5.0)
        assert eff_target == math.ceil(500.0 / (1.0 - config.ALFA_PERSONAL_COMM_PCT / 100.0))

        exp_personal_comm = round((500.0 / (1.0 - config.ALFA_PERSONAL_COMM_PCT / 100.0)) - 500.0)
        cost = calculate_cost_base(100000.0, 2000.0, insurance_pct=2.0)
        assert cost == pytest.approx(102000.0 * 1.02)
        floors = calculate_floors(cost, min_profit=500.0, personal_comm_pct=5.0, insurance_pct=2.0)
        assert floors.alfa_personal_comm == exp_personal_comm
        assert (floors.floor_alfa * 0.90) - cost >= 500.0 + exp_personal_comm - 1e-6
        assert (floors.floor_digi * 0.92) - cost >= 500.0 + exp_personal_comm - 1e-6


@pytest.mark.parametrize(
    "bad_rate",
    [None, -1.0, -0.01, 100.0, 105.0, "bad", float("nan"), float("inf"), True],
)
def test_invalid_commission_fails_fast_and_preserves_vendor_isolation(
    tmp_path: Path, bad_rate: Any
) -> None:
    """REQ-09/REQ-10: Invalid commission fails fast with ValueError without breaking the other vendor."""
    prod = _make_product(net_price=100000.0)

    # 1. Invalid DIGI must break Digi/all paths ONLY, leaving Alfa production callers 100% operational
    with (
        patch.object(config, "ALFA_COMMISSION_PCT", 11.0),
        patch.object(config, "DIGI_COMMISSION_PCT", bad_rate),
    ):
        with pytest.raises(ValueError):
            config.get_digi_commission_pct()
        with pytest.raises(ValueError):
            config.get_digi_payout_rate()
        with pytest.raises(ValueError):
            calculate_floors(103000.0, platform="all")
        with pytest.raises(ValueError):
            calculate_floors(103000.0, platform="digi")

        assert config.get_alfa_commission_pct() == 11.0
        assert config.get_alfa_payout_rate() == pytest.approx(0.89)

        fp_alfa = compute_row_fingerprint(pd.Series(prod.raw_row), platform="alfa")
        assert isinstance(fp_alfa, str) and len(fp_alfa) == 16

        floors_a = calculate_floors(103000.0, platform="alfa")
        assert floors_a.zero_margin_digi == 0.0
        assert floors_a.floor_digi == 0.0
        assert floors_a.floor_alfa == pytest.approx(
            (103000.0 + config.COMPANY_MIN_PROFIT_PKR) / 0.89
        )

        rec_alfa = process_product_with_offers(prod, [], [], platform="alfa")
        assert rec_alfa["Alfa Commission"] == "11.00%"
        assert "Digi Commission" not in rec_alfa

        manifest_a = export_results(
            pd.DataFrame([rec_alfa]),
            source_filename="alfa_iso.csv",
            output_dir=tmp_path / "alfa_iso",
            render_panel=False,
            platform="alfa",
        )
        assert manifest_a.latest_xlsx_path is not None and manifest_a.latest_xlsx_path.is_file()

    # 2. Invalid ALFA must break Alfa/all paths ONLY, leaving Digi production callers 100% operational
    with (
        patch.object(config, "ALFA_COMMISSION_PCT", bad_rate),
        patch.object(config, "DIGI_COMMISSION_PCT", 7.5),
    ):
        with pytest.raises(ValueError):
            config.get_alfa_commission_pct()
        with pytest.raises(ValueError):
            config.get_alfa_payout_rate()
        with pytest.raises(ValueError):
            calculate_floors(103000.0, platform="all")
        with pytest.raises(ValueError):
            calculate_floors(103000.0, platform="alfa")

        assert config.get_digi_commission_pct() == 7.5
        assert config.get_digi_payout_rate() == pytest.approx(0.925)

        fp_digi = compute_row_fingerprint(pd.Series(prod.raw_row), platform="digi")
        assert isinstance(fp_digi, str) and len(fp_digi) == 16

        floors_d = calculate_floors(103000.0, platform="digi")
        assert floors_d.zero_margin_alfa == 0.0
        assert floors_d.floor_alfa == 0.0
        assert floors_d.floor_digi == pytest.approx(
            (103000.0 + config.COMPANY_MIN_PROFIT_PKR) / 0.925
        )

        rec_digi = process_product_with_offers(prod, [], [], platform="digi")
        assert rec_digi["Digi Commission"] == "7.50%"
        assert "Alfa Commission" not in rec_digi

        manifest_d = export_results(
            pd.DataFrame([rec_digi]),
            source_filename="digi_iso.csv",
            output_dir=tmp_path / "digi_iso",
            render_panel=False,
            platform="digi",
        )
        assert manifest_d.latest_xlsx_path is not None and manifest_d.latest_xlsx_path.is_file()


def test_run_pipeline_platform_isolation_with_invalid_inactive_vendor(tmp_path: Path) -> None:
    """REQ-10: End-to-end async run_pipeline succeeds when the inactive vendor's rate is invalid."""
    input_csv = tmp_path / "isolation_catalog.csv"
    pd.DataFrame(
        [
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name": "Gree 1.5 Ton GS-18PITH11W",
                "Length": 100.0,
                "Width": 40.0,
                "Height": 90.0,
                "Net Price": 140000.0,
            }
        ]
    ).to_csv(input_csv, index=False)

    empty_success = ScrapeResult(offers=[], is_success=True, status_code=200)

    # 1. Alfa-only pipeline succeeds while DIGI_COMMISSION_PCT is invalid
    alfa_out = tmp_path / "alfa_only.csv"
    with (
        patch.object(config, "ALFA_COMMISSION_PCT", 11.0),
        patch.object(config, "DIGI_COMMISSION_PCT", "bad_rate"),
        patch(
            "pricing_engine.pipeline.scrape_alfamall",
            new=AsyncMock(return_value=empty_success),
        ) as mock_alfa,
        patch("pricing_engine.pipeline.scrape_digimall", new=AsyncMock()) as mock_digi,
    ):
        df_alfa = asyncio.run(
            run_pipeline(
                input_path=input_csv,
                output_path=alfa_out,
                concurrency=1,
                verbose=False,
                platform="alfa",
                resume=False,
            )
        )
        mock_alfa.assert_awaited_once()
        mock_digi.assert_not_awaited()
        assert list(df_alfa["Alfa Commission"]) == ["11.00%"]
        assert "Digi Commission" not in df_alfa.columns

    # 2. Digi-only pipeline succeeds while ALFA_COMMISSION_PCT is invalid (NaN)
    digi_out = tmp_path / "digi_only.csv"
    with (
        patch.object(config, "ALFA_COMMISSION_PCT", float("nan")),
        patch.object(config, "DIGI_COMMISSION_PCT", 7.5),
        patch("pricing_engine.pipeline.scrape_alfamall", new=AsyncMock()) as mock_alfa2,
        patch(
            "pricing_engine.pipeline.scrape_digimall",
            new=AsyncMock(return_value=empty_success),
        ) as mock_digi2,
    ):
        df_digi = asyncio.run(
            run_pipeline(
                input_path=input_csv,
                output_path=digi_out,
                concurrency=1,
                verbose=False,
                platform="digi",
                resume=False,
            )
        )
        mock_alfa2.assert_not_awaited()
        mock_digi2.assert_awaited_once()
        assert list(df_digi["Digi Commission"]) == ["7.50%"]
        assert "Alfa Commission" not in df_digi.columns


@pytest.mark.parametrize("bad_platform", ["daraz", None, 123])
def test_invalid_platform_fails_fast_everywhere(tmp_path: Path, bad_platform: Any) -> None:
    """REQ-09/10: Unsupported or non-string platform arguments fail fast without side effects."""
    prod = _make_product(net_price=100000.0)
    floors = calculate_floors(103000.0)
    alfa_res = create_skipped_platform_result("AlfaMall")
    digi_res = create_skipped_platform_result("DigiMall")
    sample_df = pd.DataFrame([{"S.NO": 1, "Brand": "Gree", "Name": "AC"}])

    with pytest.raises(ValueError):
        config.normalize_platform(bad_platform, allow_all=True)
    with pytest.raises(ValueError):
        calculate_floors(103000.0, platform=bad_platform)
    with pytest.raises(ValueError):
        compute_row_fingerprint(pd.Series(prod.raw_row), platform=bad_platform)
    with pytest.raises(ValueError):
        build_output_record(
            product=prod,
            shipping=3000.0,
            floors=floors,
            baseline_calc=0.0,
            alfa_res=alfa_res,
            digi_res=digi_res,
            platform=bad_platform,
        )
    with pytest.raises(ValueError):
        process_product_with_offers(prod, [], [], platform=bad_platform)

    dummy_csv = tmp_path / "dummy.csv"
    dummy_csv.write_text("S.NO,Brand,Name,Net Price\n1,Gree,AC,100000\n", encoding="utf-8")
    with pytest.raises(ValueError):
        asyncio.run(run_pipeline(dummy_csv, verbose=False, platform=bad_platform, resume=False))

    out_dir = tmp_path / f"bad_{type(bad_platform).__name__}"
    with pytest.raises(ValueError):
        export_results(
            sample_df,
            source_filename="bad.csv",
            output_dir=out_dir,
            render_panel=False,
            platform=bad_platform,
        )
    assert not out_dir.exists()

    with pytest.raises(ValueError):
        export_winning_5pct_results(
            pd.DataFrame([{"S.NO": 1}]),
            source_filename="bad_win.csv",
            output_dir=out_dir,
            platform=bad_platform,
        )
    assert not out_dir.exists()

    with pytest.raises(ValueError):
        export_range_results(
            sample_df,
            source_filename="bad_rng.csv",
            output_dir=out_dir,
            render_panel=False,
            platform=bad_platform,
        )
    assert not out_dir.exists()


def test_render_summary_table_handles_nan_and_skipped_digi_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REQ-05/07: Terminal summary table never displays 'nan%' or leaks configured Digi rate on skipped rows."""
    rec_console = Console(record=True, width=160, force_terminal=False)
    monkeypatch.setattr(pipeline_mod, "console", rec_console)

    with patch.object(config, "DIGI_COMMISSION_PCT", 8.0):
        records = [
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name": "Gree Active 1.5T",
                "Net Price": 140000,
                "Shipping Estimate": 5000,
                "Final Price Alfa": 162999,
                "Alfa Real Profit": 1700,
                "Alfa Reason": "Competitive win",
                "Alfa Risk Alert": "NONE",
                "Final Price Digi": 159999,
                "Digi Commission": "7.50%",
                "Digi Real Profit": 1999,
                "Digi Reason": "Competitive win",
                "Digi Risk Alert": "NONE",
            },
            {
                "S.NO": 2,
                "Brand": "Gree",
                "Name": "Gree NaN Comm",
                "Net Price": 140000,
                "Shipping Estimate": 5000,
                "Final Price Alfa": 162999,
                "Alfa Real Profit": 1700,
                "Alfa Reason": "Competitive win",
                "Alfa Risk Alert": "NONE",
                "Final Price Digi": None,
                "Digi Commission": float("nan"),
                "Digi Real Profit": None,
                "Digi Reason": "",
                "Digi Risk Alert": "",
            },
            {
                "S.NO": 3,
                "Brand": "Gree",
                "Name": "Gree Skipped Reason",
                "Net Price": 140000,
                "Shipping Estimate": 5000,
                "Final Price Alfa": 162999,
                "Alfa Real Profit": 1700,
                "Alfa Reason": "Competitive win",
                "Alfa Risk Alert": "NONE",
                "Final Price Digi": None,
                "Digi Commission": None,
                "Digi Real Profit": None,
                "Digi Reason": "DigiMall repricing skipped",
                "Digi Status": "SKIPPED",
                "Digi Risk Alert": "",
            },
        ]
        render_summary_table(records)

    rendered = rec_console.export_text()
    assert "7.50%" in rendered
    assert "nan%" not in rendered.lower()
    assert "8.00%" not in rendered
    assert " - " in rendered or "│ -" in rendered
