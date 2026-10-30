# Implementation Plan: Dynamic Excel Calculation & Platform-Isolated Exports

## Overview
Decompose implementation of dynamic Excel calculation formula referencing `Commision` column, bulletproof percentage cell formatting, and platform-specific column filtering (`filter_digi_only_columns` alongside existing `filter_alfa_only_columns`, elimination of redundant commission columns in single-platform views, and dual platform exports in `all` mode).

## Architecture Decisions
- **Cell Reference over Hardcoded Constant**: Replace hardcoded `/ 0.90` with dynamic Excel formula `=ROUND((Net + Ship + Profit)/(1 - Commision), 0)`.
- **Numeric Float Storage in Excel**: Store commission values as numeric floats (`0.10` or `0.08`) with `cell.number_format = '0.00%'` so arithmetic operations in Excel evaluate without `#VALUE!` errors.
- **Strict Column Isolation**: Exclude all Alfa columns and `Digi Effective Commision` from Digi-only export; retain single standard `Commision` column representing actual effective rate.
- **Dual Export on All Platforms Mode**: When running `all` mode, produce both the backwards-compatible unified comparison workbook and dedicated platform-isolated workbooks.

## Task Breakdown

### Phase 1: Math & Pipeline Adaptation
- [ ] Task 1.1: Update `calculate_baseline` in `pricing_engine/calculator.py` to support dynamic payout rates (0.90 vs 0.92).
- [ ] Task 1.2: Update `format_output_record` in `pricing_engine/pipeline.py` to populate `Commision` with `digi_res.effective_comm` in Digi mode and calculate baseline using active rate.

### Checkpoint: Math & Pipeline
- [ ] Run `pytest tests/test_personal_commission.py tests/test_platform_selection.py` to ensure core calculations remain green.

### Phase 2: Exporter & Excel Dynamic Formulas
- [ ] Task 2.1: Implement `filter_digi_only_columns` in `pricing_engine/exporter.py` excluding Alfa columns and redundant `Digi Effective Commision`.
- [ ] Task 2.2: Update `export_excel_workbook` in `pricing_engine/exporter.py` to format `Commision` as numeric float percentage and inject dynamic formula `=ROUND((Net + Ship + Profit)/(1 - Commision), 0)`.
- [ ] Task 2.3: Update `export_results`, `export_winning_5pct_results`, and `export_structured_results` in `pricing_engine/exporter.py` to support `platform == "digi"` and dual platform outputs.

### Checkpoint: Exporter & Excel Formulas
- [ ] Run `pytest tests/test_exporter_formulas.py tests/test_exporter.py` to verify formula generation and column filtering.

### Phase 3: Test Suite Expansion & End-to-End Verification
- [ ] Task 3.1: Add unit tests for `filter_digi_only_columns` and Digi-only export in `tests/test_exporter.py`.
- [ ] Task 3.2: Update formula assertions in `tests/test_exporter_formulas.py` for dynamic commission reference.
- [ ] Task 3.3: Run full test suite `pytest -v` (all 392+ tests green) and `ruff check .`.

## Risks and Mitigations
| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| Excel `#VALUE!` on text percentage | High | Write commission as float `0.10`/`0.08` with `0.00%` number format and wrap formula with `IF(ISNUMBER(...))` |
| Breaking backwards compatibility | High | Maintain standard `{stem}_repriced_latest.{csv,xlsx}` unified file in `all` mode alongside platform-isolated files |
| Existing tests expecting `Digi Effective Commision` in combined mode | Medium | Keep `Digi Effective Commision` in unified combined mode, drop only in Digi-isolated export |
