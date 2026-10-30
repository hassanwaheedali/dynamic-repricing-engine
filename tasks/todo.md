# Task List: Dynamic Excel Calculation & Platform-Isolated Exports

- [x] **Phase 1: Math & Pipeline Adaptation**
  - [x] Task 1.1: Add optional `payout_rate` parameter to `calculate_baseline` in `pricing_engine/calculator.py`
  - [x] Task 1.2: Update `format_output_record` in `pricing_engine/pipeline.py` to set `Commision` to effective rate and compute baseline accordingly under `platform == "digi"`
  - [x] Task 1.3: Update `run_pipeline` in `pricing_engine/pipeline.py` to route `plat == "digi"` through `filter_digi_only_columns`

- [x] **Checkpoint 1: Core Pipeline Math**
  - [x] Run focused math & platform tests: `pytest -v tests/test_platform_selection.py tests/test_personal_commission.py` (All passed)

- [x] **Phase 2: Exporter & Excel Dynamic Formulas**
  - [x] Task 2.1: Add `filter_digi_only_columns(df)` in `pricing_engine/exporter.py`
  - [x] Task 2.2: Update `export_excel_workbook` in `pricing_engine/exporter.py` for numeric percentage formatting and dynamic `(1 - Commision)` formula
  - [x] Task 2.3: Integrate `filter_digi_only_columns` into `export_results`, `export_winning_5pct_results`, and `export_structured_results`
  - [x] Task 2.4: Implement dual platform exports (`_alfa_latest` and `_digi_latest`) when `platform == "all"`

- [x] **Checkpoint 2: Export & Excel Generation**
  - [x] Run exporter tests: `pytest -v tests/test_exporter.py tests/test_exporter_formulas.py` (All passed)

- [x] **Phase 3: Test Suite & Quality Verification**
  - [x] Task 3.1: Add tests for `filter_digi_only_columns` and `--digi-only` export in `tests/test_exporter.py`
  - [x] Task 3.2: Update assertions in `tests/test_exporter_formulas.py` for dynamic formula
  - [x] Task 3.3: Execute full suite `pytest -v` (396 passed) and `ruff check .` (All checks passed)
