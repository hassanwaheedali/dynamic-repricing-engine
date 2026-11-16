"""Tests for category-driven insurance (% on Net + Shipping before commission) — values from config.py."""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd
import pytest

import config
from pricing_engine.calculator import (
    calculate_baseline,
    calculate_cost_base,
    calculate_floors,
    resolve_insurance_pct,
)
from pricing_engine.exporter import export_results
from pricing_engine.models import PlatformPricingResult, ProductInput, ScrapeResult
from pricing_engine.pipeline import (
    console,
    process_product_with_offers,
    render_audit_card,
)


def _categories_with_insurance() -> list[dict[str, Any]]:
    return [
        c
        for c in config.DEFAULT_CATEGORY_SHIPPING["categories"]
        if float(c.get("insurance_pct", 0) or 0) > 0
    ]


def _product(name: str, brand: str = "Samsung", net: float = 100000.0) -> ProductInput:
    return ProductInput(1, brand, name, 0.0, 0.0, 0.0, net, 500.0, {"Name": name})


LED_TITLE = "Samsung UA65DU7000 65 Inch Smart Led TV"
LED_TITLES = [
    LED_TITLE,
    "Haier C43H5FX 43 Inch Full HD Google Smart Led TV",
    'HAIER LED 32" 32K85FX',
]
NON_INSURED_TITLES = [
    "Haier 1.5 Ton Inverter Wall Mounted Split Air Conditioner",
    "Dawlance 9140WB Avante 8 Cu Ft Refrigerator",
    "Kenwood 8 KG Single Tub Semi-Automatic Washing Machine",
    "Dawlance DW-MD4 20 Ltr Solo Microwave Oven",
    "Dawlance DBD-1034 Bottom Load Water Dispenser",
    "Philips Electric Kettle",
]


class TestResolveInsurancePct:
    def test_config_defines_insurance_only_on_led_tv(self) -> None:
        ids = [c["id"] for c in _categories_with_insurance()]
        assert ids == ["led_tv"]

    @pytest.mark.parametrize("title", LED_TITLES)
    def test_led_tv_gets_configured_insurance(self, title: str) -> None:
        led_cat = next(c for c in config.DEFAULT_CATEGORY_SHIPPING["categories"] if c["id"] == "led_tv")
        assert resolve_insurance_pct(title, brand="Samsung") == float(led_cat["insurance_pct"])

    @pytest.mark.parametrize("title", NON_INSURED_TITLES)
    def test_other_categories_get_zero(self, title: str) -> None:
        assert resolve_insurance_pct(title, brand="Dawlance") == 0.0

    def test_dynamic_custom_category_insurance_without_code_changes(self) -> None:
        custom = {
            "categories": [
                {"id": "gadget", "name": "Gadget", "keywords": ["gadget"], "insurance_pct": 1.5},
                {"id": "plain", "name": "Plain", "keywords": ["plain"]},
            ],
            "default": 3000.0,
        }
        assert resolve_insurance_pct("Super Gadget X", config_table=custom) == 1.5
        assert resolve_insurance_pct("Plain Thing", config_table=custom) == 0.0
        assert resolve_insurance_pct("Unmatched", config_table=custom) == 0.0

    def test_changing_config_value_changes_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        table = copy.deepcopy(config.DEFAULT_CATEGORY_SHIPPING)
        for cat in table["categories"]:
            if cat["id"] == "led_tv":
                cat["insurance_pct"] = 4.0
        monkeypatch.setattr(config, "DEFAULT_CATEGORY_SHIPPING", table)
        assert resolve_insurance_pct(LED_TITLE) == 4.0

    def test_invalid_or_negative_value_is_ignored(self) -> None:
        custom = {
            "categories": [
                {"id": "a", "keywords": ["aaa"], "insurance_pct": -3},
                {"id": "b", "keywords": ["bbb"], "insurance_pct": "oops"},
                {"id": "c", "keywords": ["ccc"], "insurance_pct": None},
            ],
        }
        for word in ("aaa", "bbb", "ccc"):
            assert resolve_insurance_pct(word, config_table=custom) == 0.0


class TestCostBaseWithInsurance:
    @pytest.mark.parametrize("ins", [0.0, 2.0, 2.5, 4.0])
    def test_insurance_is_added_on_net_plus_shipping(self, ins: float) -> None:
        assert calculate_cost_base(90000.0, 3000.0, insurance_pct=ins) == pytest.approx(
            93000.0 * (1 + ins / 100), abs=0.01
        )

    def test_default_cost_base_unchanged(self) -> None:
        assert calculate_cost_base(90000.0, 3000.0) == 93000.0


class TestFloorsWithInsurance:
    @pytest.mark.parametrize("ins", [0.0, 2.0, 2.5, 4.0])
    def test_floors_are_computed_on_insurance_inclusive_cost(self, ins: float) -> None:
        cost = calculate_cost_base(90000.0, 3000.0, insurance_pct=ins)
        floors = calculate_floors(cost, insurance_pct=ins)
        min_p = config.COMPANY_MIN_PROFIT_PKR
        assert floors.insurance_pct == ins
        assert floors.cost_base == pytest.approx(93000.0 * (1 + ins / 100), abs=0.01)
        assert floors.zero_margin_10 == pytest.approx(cost / config.get_alfa_payout_rate())
        assert floors.floor_alfa == pytest.approx((cost + min_p) / config.get_alfa_payout_rate())
        assert floors.floor_digi_8 == pytest.approx(
            (cost + min_p) / config.get_digi_leverage_payout_rate()
        )

    def test_default_insurance_is_zero_and_unchanged(self) -> None:
        cost = 72000.0
        assert calculate_floors(cost).insurance_pct == 0.0
        assert calculate_floors(cost).floor_alfa == pytest.approx(
            (cost + config.COMPANY_MIN_PROFIT_PKR) / config.get_alfa_payout_rate()
        )

    def test_user_example_insurance_before_commission(self) -> None:
        # net 90k + delivery 3k -> insurance on that cost -> THEN commission
        ins = 2.5
        cost = calculate_cost_base(90000.0, 3000.0, insurance_pct=ins)
        floors = calculate_floors(cost, insurance_pct=ins)
        expected = (93000.0 * (1 + ins / 100)) / (1 - config.ALFA_COMMISSION_PCT / 100)
        assert floors.zero_margin_10 == pytest.approx(expected, abs=0.01)

    def test_profit_guarantee_holds_at_floor_with_insurance_in_cost(self) -> None:
        ins = 2.5
        cost = calculate_cost_base(90000.0, 3000.0, insurance_pct=ins)
        floors = calculate_floors(cost, insurance_pct=ins)
        profit = floors.floor_alfa * config.get_alfa_payout_rate() - floors.cost_base
        assert profit == pytest.approx(config.COMPANY_MIN_PROFIT_PKR)

    def test_baseline_uses_insurance_inclusive_cost(self) -> None:
        cost = calculate_cost_base(90000.0, 3000.0, insurance_pct=2.5)
        base = calculate_baseline(cost, 500.0)
        assert base == pytest.approx((cost + 500.0) / config.get_alfa_payout_rate())
        assert base > calculate_baseline(93000.0, 500.0)


class TestPipelineInsuranceEndToEnd:
    def test_led_record_prices_include_insurance(self) -> None:
        prod = _product(LED_TITLE)
        rec = process_product_with_offers(prod, ScrapeResult(offers=[]), ScrapeResult(offers=[]))
        ins = resolve_insurance_pct(prod.name, brand=prod.brand)
        cost_ins = (prod.net_price + rec["Shipping Estimate"]) * (1 + ins / 100)
        assert rec["Insurance"] == f"{ins:.2f}%"
        # Total Without Profit = (Net + Shipping + insurance on it) / commission payout
        assert rec["Total Without Profit"] == round(
            cost_ins / config.get_digi_standard_payout_rate()
        )
        # Reported profit is measured against the insurance-inclusive cost
        assert rec["Alfa Real Profit"] == round(
            rec["Final Price Alfa"] * config.get_alfa_payout_rate() - cost_ins
        )
        # Final price never below the insurance-inclusive floor; profit never below guarantee
        floors = calculate_floors(cost_ins, insurance_pct=ins)
        assert rec["Final Price Alfa"] >= floors.floor_alfa
        assert rec["Alfa Real Profit"] >= config.COMPANY_MIN_PROFIT_PKR

    def test_led_final_price_higher_than_without_insurance(self) -> None:
        prod = _product(LED_TITLE)
        with_ins = process_product_with_offers(
            prod, ScrapeResult(offers=[]), ScrapeResult(offers=[])
        )
        ins = resolve_insurance_pct(prod.name)
        plain_cost = prod.net_price + with_ins["Shipping Estimate"]
        floors_no_ins = calculate_floors(plain_cost)
        floors_ins = calculate_floors(
            calculate_cost_base(prod.net_price, with_ins["Shipping Estimate"], insurance_pct=ins),
            insurance_pct=ins,
        )
        assert floors_ins.floor_alfa > floors_no_ins.floor_alfa
        assert with_ins["Final Price Alfa"] >= floors_ins.floor_alfa

    @pytest.mark.parametrize("title", NON_INSURED_TITLES)
    def test_non_led_has_no_insurance_column_or_effect(self, title: str) -> None:
        prod = _product(title, brand="Dawlance")
        rec = process_product_with_offers(prod, ScrapeResult(offers=[]), ScrapeResult(offers=[]))
        assert "Insurance" not in rec
        cost_base = prod.net_price + rec["Shipping Estimate"]
        assert rec["Total Without Profit"] == round(cost_base / config.get_digi_standard_payout_rate())


class TestTerminalShowsInsurance:
    def _render(self, title: str) -> str:
        prod = _product(title)
        ins = resolve_insurance_pct(prod.name, brand=prod.brand)
        cost = calculate_cost_base(prod.net_price, 3500.0, insurance_pct=ins)
        floors = calculate_floors(cost, insurance_pct=ins)
        res = PlatformPricingResult(
            min_price=None,
            max_price=None,
            final_price=122999,
            real_profit=4124,
            status="SUCCESS",
            reason="MONOPOLY",
            effective_comm=f"{config.ALFA_COMMISSION_PCT:.2f}%",
        )
        with console.capture() as cap:
            render_audit_card(
                product=prod,
                shipping=3500.0,
                floors=floors,
                baseline_calc=118857.0,
                target_model="UA65DU7000",
                alfa_offers=[],
                digi_offers=[],
                alfa_res=res,
                digi_res=res,
                is_shipping_fallback=True,
            )
        return cap.get()

    def test_led_card_shows_insurance(self) -> None:
        out = self._render(LED_TITLE)
        ins = resolve_insurance_pct(LED_TITLE)
        assert "Insurance" in out
        assert f"{ins:g}%" in out
        assert f"{(100000.0 + 3500.0) * ins / 100:,.2f}" in out

    def test_non_led_card_has_no_insurance_row(self) -> None:
        out = self._render("Haier 1.5 Ton Inverter Wall Mounted Split Air Conditioner")
        assert "Insurance" not in out


class TestExcelInsurance:
    def test_excel_formulas_reference_insurance_column(self, tmp_path: Path) -> None:
        ins = resolve_insurance_pct(LED_TITLE)
        rows = [
            {
                "S.NO": 1,
                "Brand": "Samsung",
                "Name": LED_TITLE,
                "Net Price": 100000,
                "Profit": 500,
                "Shipping Estimate": 3500,
                "Commision": f"{config.ALFA_COMMISSION_PCT:.2f}%",
                "Digi Effective Commision": f"{config.DIGI_STANDARD_COMMISSION_PCT:.2f}%",
                "Insurance": f"{ins:.2f}%",
                "Total Without Profit": 118286,
                "Calculation": 118857,
                "Final Price Alfa": 122999,
                "Final Price Digi": 122999,
                "Alfa Real Profit": 4124,
                "Digi Real Profit": 4124,
                "Alfa Risk Alert": "NONE",
                "Digi Risk Alert": "NONE",
            },
            {
                "S.NO": 2,
                "Brand": "Haier",
                "Name": "Haier AC 1 Ton",
                "Net Price": 100000,
                "Profit": 500,
                "Shipping Estimate": 3000,
                "Commision": f"{config.ALFA_COMMISSION_PCT:.2f}%",
                "Digi Effective Commision": f"{config.DIGI_STANDARD_COMMISSION_PCT:.2f}%",
                "Insurance": None,
                "Total Without Profit": 114444,
                "Calculation": 115000,
                "Final Price Alfa": 115999,
                "Final Price Digi": 115999,
                "Alfa Real Profit": 1400,
                "Digi Real Profit": 1400,
                "Alfa Risk Alert": "NONE",
                "Digi Risk Alert": "NONE",
            },
        ]
        manifest = export_results(
            df=pd.DataFrame(rows),
            source_filename="ins.csv",
            output_dir=tmp_path,
            timestamp=datetime(2026, 11, 16, 12, 0, 0),
            render_panel=False,
        )
        assert manifest.timestamped_xlsx_path is not None
        wb = openpyxl.load_workbook(manifest.timestamped_xlsx_path)
        ws = wb.active
        assert ws is not None
        cols = [c.value for c in ws[1]]
        ins_letter = openpyxl.utils.get_column_letter(cols.index("Insurance") + 1)
        for col_name in ("Total Without Profit", "Calculation", "Alfa Real Profit", "Digi Real Profit"):
            idx = cols.index(col_name) + 1
            for row in (2, 3):
                formula = str(ws.cell(row=row, column=idx).value)
                assert f"{ins_letter}{row}" in formula, (col_name, row, formula)
        # Insurance cell stored as a decimal fraction, formatted as percent
        assert ws.cell(row=2, column=cols.index("Insurance") + 1).value == pytest.approx(ins / 100)
        assert ws.cell(row=3, column=cols.index("Insurance") + 1).value is None
