# Task Breakdown & Checklist (`tasks/todo.md`)

## Task 1: Path Resolution Helper & Format Subfolders (`pricing_engine/exporter.py`)
- [x] Implement `resolve_option_output_dir(input_path: str | Path, option: int | str = 1) -> Path`
- [x] Update `export_results` to create `csv/` and `xlsx/` subfolders inside target directory
- [x] Update `export_winning_5pct_results` to create `csv/` and `xlsx/` subfolders inside target directory
- [x] Ensure `export_range_results` writes to `csv/` and `xlsx/` subfolders inside target directory
- [x] Update existing tests in `tests/test_exporter.py` and `tests/test_exporter_formulas.py` for `csv/` and `xlsx/` paths
- [x] Add unit tests for `resolve_option_output_dir`

## Task 2: Wire `run_pipeline` (Options 1 & 3)
- [x] In `pricing_engine/pipeline.py`, change default `export_dir: str | Path | None = None`
- [x] Resolve `export_dir` using `resolve_option_output_dir(input_path, option=3 if personal_comm_pct > 0 else 1)` when `export_dir is None`
- [x] Update banner path calculations to reflect target option subfolder and `csv/` subfolder

## Task 3: Wire `run_range_pipeline` (Option 2)
- [x] In `pricing_engine/range_pipeline.py`, change default `export_dir: str | Path | None = None`
- [x] Resolve `export_dir` using `resolve_option_output_dir(input_path, option=2)` when `export_dir is None`
- [x] Update banner and finish cards to show resolved `option_2/` paths

## Task 4: Ingestion Safeguards & CLI Updates (`index.py`)
- [x] Ensure `find_input_catalogs` only matches direct files and ignores subfolders in `data/inputs/`
- [x] Update `index.py` CLI help strings and console output

## Task 5: End-to-End Verification
- [x] Run full test suite (`pytest`) to confirm all 355 tests pass
- [x] Run live pipeline on `data/inputs/wm.csv` for Option 1, Option 2, and Option 3
- [x] Confirm resulting directory structure:
  - `data/outputs/wm/option_1/{csv, xlsx}/`
  - `data/outputs/wm/option_2/{csv, xlsx}/`
  - `data/outputs/wm/option_3/{csv, xlsx}/`
