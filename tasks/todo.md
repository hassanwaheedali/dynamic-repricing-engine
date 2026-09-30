# Dynamic Repricing Engine — Implementation Todo

## Phase 1: Fix Input/Output Pipeline

### Task 1.1: Create `pricing_engine/ingestion.py`
- [x] Create `pricing_engine/ingestion.py`
- [x] Implement `IngestionReport` dataclass (source_file, total_rows, valid_rows, profit_source)
- [x] Implement `ingest_catalog(csv_path) -> tuple[list[ProductInput], IngestionReport]`
- [x] Strip whitespace from all column names on CSV load
- [x] Validate 6 required columns: Brand, Name, Net Price, Length, Width, Height
- [x] Raise clear `ValueError` if any required column missing (name exactly which)
- [x] Handle optional Profit column (per-row if exists, else default 500.0)
- [x] Ignore extra columns silently (legacy 18-column compatibility)
- [x] Render Rich pre-flight banner (source file, row count, profit source)
- [x] Create `tests/test_ingestion.py`
- [x] Test: clean 6-column CSV parses correctly
- [x] Test: 7-column CSV with Profit uses per-row values
- [x] Test: legacy 18-column Gree CSV works
- [x] Test: legacy 18-column Haier CSV works
- [x] Test: missing Net Price column raises ValueError
- [x] Test: missing Brand column raises ValueError
- [x] Test: empty CSV returns empty list
- [x] Run `pytest` — all 138 existing + new tests green

### Task 1.2: Create `pricing_engine/exporter.py`
- [x] Create `pricing_engine/exporter.py`
- [x] Implement `ExportManifest` dataclass (timestamped_path, latest_path, timestamp, total_rows)
- [x] Implement `export_results(df, source_filename) -> ExportManifest`
- [x] Auto-create `data/outputs/` directory
- [x] Save timestamped file: `{stem}_repriced_{YYYYMMDD_HHMMSS}.csv`
- [x] Save latest copy: `{stem}_repriced_latest.csv`
- [x] Apply `format_export_price()` to price columns
- [x] Render Rich finish panel with output paths
- [x] Create `tests/test_exporter.py`
- [x] Test: both timestamped and latest files created
- [x] Test: data/outputs/ directory auto-created
- [x] Test: timestamp format correct
- [x] Test: latest matches timestamped content
- [x] Test: price columns are pure integers
- [x] Run `pytest` — all tests green

### Task 1.3: Create Data Directory Structure
- [x] Create `data/inputs/.gitkeep`
- [x] Create `data/outputs/.gitkeep`
- [x] Create `data/inputs/template.csv` (6+1 columns, 2 example rows)
- [x] Copy Gree CSV to `data/inputs/Gree_AC.csv`
- [x] Copy Haier CSV to `data/inputs/Haier_Washers.csv`
- [x] Update `.gitignore` (exclude output CSVs, track template and .gitkeep)
- [x] Keep original root CSVs for test compatibility
- [x] Remove empty legacy `Prices/` directory

### Task 1.4: Wire Into Pipeline & CLI
- [ ] Update `run_pipeline()` — add `output_path=None, use_structured_export=False` optional params
- [ ] When output_path provided → legacy behavior (existing tests unchanged)
- [ ] When output_path=None + use_structured_export=True → use CatalogExporter
- [ ] Add `df.columns = df.columns.str.strip()` strictly at CSV load level in run_pipeline
- [ ] Remove `DEFAULT_INPUT_CSV` and `DEFAULT_OUTPUT_CSV` from index.py
- [ ] Change --input default to None
- [ ] Change --output default to None
- [ ] Add --batch / -a flag with per-catalog `try...except` resilient error handling
- [ ] Implement data/inputs/ scanning when no -i provided
- [ ] If 0 CSVs → helpful error message
- [ ] If 1 CSV → auto-select
- [ ] If 2+ CSVs:
  - Check `sys.stdin.isatty()`: interactive Rich picker if True, non-interactive fallback if False
- [ ] When -o not specified → use_structured_export=True
- [ ] When -o specified → pass output_path directly
- [ ] Run `pytest` — all 138+ tests green
- [ ] Test `python index.py --help`
- [ ] Test `python index.py -i Gree_Uploading_on_DigiMall_and_Price.csv -o test.csv` (legacy)
- [ ] Test `python index.py` with CSVs in data/inputs/
- [ ] Run `ruff check .` — no lint errors

### Phase 1 Checkpoint
- [ ] All existing 138 tests + new tests pass
- [ ] `python index.py` with CSVs in data/inputs/ works
- [ ] Legacy -i / -o flags work identically
- [ ] Output in data/outputs/ with timestamp + latest
- [ ] No lint errors
- [ ] Inform User to start Phase 2

---

## Phase 2: Supabase Price History & Terminal Search

### Task 2.1: Create Supabase Tables
- [ ] Add `repricing_runs` table to `scripts/setup_supabase.sql`
- [ ] Add `repricing_results` table to `scripts/setup_supabase.sql`
- [ ] Add indexes on run_id, brand, model, created_at
- [ ] Add RLS policies (service_role full, public read)
- [ ] Run SQL in Supabase dashboard to create tables

### Task 2.2: Add History Methods to `pricing_engine/db.py`
- [ ] `create_repricing_run(catalog_name, total_items) -> str | None`
- [ ] `store_repricing_results(run_id, results) -> int`
- [ ] `query_runs_by_date(date_str) -> list[dict]`
- [ ] `query_results_by_model(model_pattern) -> list[dict]`
- [ ] `query_results_by_run(run_id) -> list[dict]`
- [ ] `query_latest_run() -> dict | None`
- [ ] `query_thin_margin_products(max_profit) -> list[dict]`
- [ ] All methods gracefully return empty if Supabase not configured
- [ ] Create `tests/test_db_history.py` with mocked Supabase responses
- [ ] Run `pytest` — all tests green

### Task 2.3: Auto-Store Results in Pipeline
- [ ] After CSV export in `run_pipeline()`, add Supabase history sync
- [ ] Create run record → get run_id
- [ ] Build results batch from records with model extraction
- [ ] Batch insert results
- [ ] Wrap in try/except — pipeline completes even if Supabase is down
- [ ] Show "Stored N results in Supabase" in finish banner
- [ ] Run `pytest` — all tests green

### Task 2.4: Add `history` Subcommand to `index.py`
- [ ] Add `history` subcommand via argparse subparsers
- [ ] `python index.py history` → Interactive Rich menu (Model / Date / Latest / Profit)
- [ ] `python index.py history --model <pattern>` → Rich table of model price history
- [ ] `python index.py history --date <YYYY-MM-DD>` → Rich table of that day's results
- [ ] `python index.py history --latest` → Rich table of last run
- [ ] `python index.py history --profit-below <amount>` → Rich table of thin-margin products
- [ ] Each table: Date, Brand, Model, Final Price Alfa, Final Price Digi, Profit, Risk Alert
- [ ] Empty results → friendly "No records found" message
- [ ] Supabase not configured → "Price history requires Supabase. See .env.example"
- [ ] Run `pytest` — all tests green
- [ ] Manual test all 4 query modes

### Phase 2 Checkpoint
- [ ] Pipeline auto-stores results in Supabase
- [ ] `python index.py history --latest` works
- [ ] `python index.py history --model 12AITH21W` works
- [ ] `python index.py history --date 2026-09-30` works
- [ ] `python index.py history --profit-below 1000` works
- [ ] Pipeline runs normally when Supabase is down
- [ ] All tests pass
