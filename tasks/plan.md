# Implementation Plan: Enterprise Dynamic Catalog I/O & Price History

## Context for Any LLM Agent

This is the **Dynamic Repricing Engine** for Pakistani e-commerce platforms (AlfaMall & DigiMall). It scrapes competitor prices via direct JSON APIs, applies cost math with strict profit floors, and outputs winning psychological prices.

**Current State**: 138 passing tests, 10 modules in `pricing_engine/`, Supabase cloud DB already configured.

**Problem**: Input is hardcoded to one filename, output dumps to project root, and there's no historical record of pricing decisions.

---

## Architecture Decision: What We're Building

Two clean phases:

```
Phase 1: Fix Input/Output Pipeline
Phase 2: Supabase Price History + Terminal Search
```

### Phase 1 Target Architecture

```
BEFORE (Current):
  Root/
    Gree_Uploading_on_DigiMall_and_Price.csv  ← hardcoded in index.py:21
    index.py → pipeline.py → final_repriced_uploaded_products.csv  ← dumped in root

AFTER (Phase 1):
  data/
    inputs/                              ← User drops CSV here
      template.csv                       ← Clean 6+1 column reference
      Gree_AC.csv                        ← Any catalog
      Haier_Washers.csv
    outputs/                             ← All output goes here
      Gree_AC_repriced_20260930_1330.csv  ← Timestamped audit copy
      Gree_AC_repriced_latest.csv         ← Always-current file for upload
```

### Phase 2 Target Architecture

```
AFTER (Phase 2):
  Every pipeline run → auto-stores results in Supabase tables:
    repricing_runs    (run_id, timestamp, catalog, items_count)
    repricing_results (run_id, brand, model, final_price_alfa, final_price_digi, profit, reason)

  Terminal commands:
    python index.py history                        → Interactive Rich menu
    python index.py history --model 12AITH21W      → All runs for this model
    python index.py history --date 2026-09-30      → All results from that day
    python index.py history --profit-below 1000    → Thin-margin products
    python index.py history --latest               → Last run's results
```

---

## Input Template Specification

**Strict 6 required + 1 optional column:**

```csv
Brand,Name,Net Price,Length,Width,Height,Profit
Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92,
Gree,GREE SPLIT AC 18AITH21W-T3,183000,104,39,103,1000
```

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `Brand` | Yes | string | Brand name (Gree, Haier, Dawlance, etc.) |
| `Name` | Yes | string | Full product name including model number |
| `Net Price` | Yes | number | Purchase/wholesale price in PKR (commas allowed: `147,000`) |
| `Length` | Yes | float | Package length in centimeters |
| `Width` | Yes | float | Package width in centimeters |
| `Height` | Yes | float | Package height in centimeters |
| `Profit` | Optional | number | Target profit in PKR. Default: `500.0` if column missing or cell empty |

**Backwards Compatibility**: Legacy CSVs with 18+ columns (like `Gree_Uploading_on_DigiMall_and_Price.csv`) still work — extra columns are silently ignored. The trailing-space `Name ` column is handled by stripping whitespace from all column names on CSV load.

---

## Critical Codebase References

Any implementing agent MUST read these files before writing code:

| File | Why | Key Lines |
|------|-----|-----------|
| [`index.py`](file:///d:/Pricing%20Script/index.py) | Current CLI entrypoint. `DEFAULT_INPUT_CSV` on line 21 must be removed. | L21-57 |
| [`pricing_engine/pipeline.py`](file:///d:/Pricing%20Script/pricing_engine/pipeline.py) | Core pipeline. `run_pipeline()` on L951-1062 is the main function to modify. `parse_product_input()` on L139-173 handles CSV row parsing. `format_export_price()` on L65-82 handles integer formatting. | L139-173, L951-1062 |
| [`pricing_engine/models.py`](file:///d:/Pricing%20Script/pricing_engine/models.py) | `ProductInput` dataclass on L67-78. New ingestion code must produce these. | L67-78 |
| [`pricing_engine/db.py`](file:///d:/Pricing%20Script/pricing_engine/db.py) | `SupabaseClient` class — pattern for Phase 2 DB methods. Uses `curl_cffi.requests.AsyncSession`. | L28-180 |
| [`scripts/setup_supabase.sql`](file:///d:/Pricing%20Script/scripts/setup_supabase.sql) | Existing Supabase schema — Phase 2 new tables go here. | L1-128 |
| [`tests/test_pipeline.py`](file:///d:/Pricing%20Script/tests/test_pipeline.py) | 138 existing tests — ALL must stay green. Tests use `parse_product_input()` directly. | L1-60 |
| [`tests/test_simulation.py`](file:///d:/Pricing%20Script/tests/test_simulation.py) | 3 E2E simulations using real CSV files from root directory. These CSVs must remain accessible. | L1-253 |

---

## Decisions Already Made (Do NOT Revisit)

| Decision | Rationale |
|----------|-----------|
| **Strict 6+1 column template, NO alias resolver** | User confirmed: "bas ek standard template do." Complex alias mapping solves a problem that doesn't exist. |
| **Flat `data/outputs/` directory, NO brand sub-folders** | User manually copies prices into portal CSVs. Nested folders add navigation complexity without benefit. |
| **NO Stock Holding Report ingestion** | User confirmed: "mey shipping, dimensions, model, brand, net price toh donga hi donga." Missing data produces wrong results. |
| **NO Pandera/Great Expectations validation** | Simple pandas column check is sufficient for a 6-column template. |
| **Supabase for history, NOT local SQLite** | User chose Supabase. Client already exists in `db.py`. |
| **Terminal Rich UI for history search, NOT web dashboard** | User chose terminal-first. Supabase data can power frontend later. |
| **`_latest.csv` is file copy, NOT symlink** | Windows compatibility. |

---

## Phase 1: Fix Input/Output Pipeline

### Task 1.1: Create `pricing_engine/ingestion.py` — Clean Template Validator

**What to build**: A module that reads any CSV, strips column whitespace, validates the 6 required columns exist, handles the optional `Profit` column with smart defaults, and returns `list[ProductInput]` + an `IngestionReport`.

**Acceptance Criteria**:
- [ ] Reads CSV with `pd.read_csv(path)`
- [ ] Strips whitespace from all column names (`df.columns = df.columns.str.strip()`)
- [ ] Validates 6 required columns exist: `Brand`, `Name`, `Net Price`, `Length`, `Width`, `Height`
- [ ] If any required column is missing, raises clear `ValueError` naming exactly which columns are missing
- [ ] Handles optional `Profit` column: if column exists, use per-row value (default 500.0 if cell is empty/NaN); if column doesn't exist, use 500.0 for all rows
- [ ] Extra columns (legacy 18-column sheets) are silently ignored — no error
- [ ] Returns `(list[ProductInput], IngestionReport)` where products are ready for pipeline
- [ ] `IngestionReport` is a `@dataclass` with: `source_file: str`, `total_rows: int`, `valid_rows: int`, `profit_source: str` (one of `"column"`, `"default"`)
- [ ] Renders Rich pre-flight banner showing: source file, row count, column validation status, profit source

**Files to create**: `pricing_engine/ingestion.py`, `tests/test_ingestion.py`

**Tests to write**:
- Clean 6-column CSV → all products parsed correctly
- Clean 7-column CSV (with Profit) → profit values used per-row
- Legacy 18-column Gree CSV → works, extra columns ignored
- Legacy 18-column Haier CSV → works, extra columns ignored
- Missing `Net Price` column → clear `ValueError`
- Missing `Brand` column → clear `ValueError`
- Empty CSV (headers only) → returns empty list, report shows 0 rows

**Verification**: `pytest tests/test_ingestion.py` + `pytest` (138 existing green)

---

### Task 1.2: Create `pricing_engine/exporter.py` — Timestamped Output Manager

**What to build**: A module that saves the repriced DataFrame to `data/outputs/` with timestamped naming and a `_latest.csv` copy.

**Acceptance Criteria**:
- [ ] `export_results(df, source_filename) -> ExportManifest`
- [ ] Creates `data/outputs/` directory if it doesn't exist (`Path.mkdir(parents=True, exist_ok=True)`)
- [ ] Saves timestamped file: `data/outputs/{stem}_repriced_{YYYYMMDD_HHMMSS}.csv`
- [ ] Saves latest copy: `data/outputs/{stem}_repriced_latest.csv` (file copy, not symlink)
- [ ] Applies `format_export_price()` to all price columns before saving (reuse from `pipeline.py`)
- [ ] `ExportManifest` is a `@dataclass` with: `timestamped_path: Path`, `latest_path: Path`, `timestamp: str`, `total_rows: int`
- [ ] Renders Rich finish panel showing: output file paths, row count, timestamp

**Files to create**: `pricing_engine/exporter.py`, `tests/test_exporter.py`

**Tests to write**:
- Export creates both timestamped and latest files
- Export creates `data/outputs/` directory automatically
- Timestamp format is `YYYYMMDD_HHMMSS`
- Latest file content matches timestamped file content
- Price columns are formatted as pure integers (no `.0` drift)

**Verification**: `pytest tests/test_exporter.py` + `pytest` (all green)

---

### Task 1.3: Create `data/` Directory Structure & Template

**What to do**:
- [ ] Create `data/inputs/.gitkeep`
- [ ] Create `data/outputs/.gitkeep`
- [ ] Create `data/inputs/template.csv` with header + 2 example rows:
  ```csv
  Brand,Name,Net Price,Length,Width,Height,Profit
  Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92,
  Haier,Haier HW 90-BP12357S8 Front Load Washing Machine,130000,65,56,92,1000
  ```
- [ ] Copy `Gree_Uploading_on_DigiMall_and_Price.csv` to `data/inputs/Gree_AC.csv`
- [ ] Copy `Haier_Washing_Machines_Uploading_and_Price.csv` to `data/inputs/Haier_Washers.csv`
- [ ] Update `.gitignore`: add `data/outputs/*.csv` and `!data/outputs/.gitkeep` and `!data/inputs/template.csv`
- [ ] Keep original root CSV files for existing test compatibility
- [ ] Remove empty legacy `Prices/` directory

---

### Task 1.4: Wire Ingestion + Exporter into `pipeline.py` & `index.py`

**What to modify in `pipeline.py`**:
- [ ] `run_pipeline()` signature becomes: `run_pipeline(input_path, output_path=None, concurrency=3, verbose=True, use_structured_export=False)`
- [ ] When `output_path` is provided → use it directly (legacy behavior, all existing tests pass unchanged)
- [ ] When `output_path` is `None` AND `use_structured_export=True` → use `CatalogExporter` to write to `data/outputs/`
- [ ] `parse_product_input()` note: column stripping (`df.columns = df.columns.str.strip()`) happens strictly at CSV load level in `run_pipeline()` and `ingestion.py`, NOT inside `parse_product_input()`, ensuring 35+ unit tests passing `pd.Series` directly remain 100% green.
- [ ] Return type stays `pd.DataFrame`

**What to modify in `index.py`**:
- [ ] Remove `DEFAULT_INPUT_CSV` constant
- [ ] Remove `DEFAULT_OUTPUT_CSV` constant
- [ ] Change `--input` default from hardcoded filename to `None`
- [ ] Change `--output` default from hardcoded filename to `None`
- [ ] Add `--batch` / `-a` flag: process all CSVs in `data/inputs/`
  - Resilient batch processing: wrap each catalog in `try...except` so an error in one catalog logs a red banner and continues with the remaining catalogs.
- [ ] New logic when no `-i` provided:
  1. Scan `data/inputs/` for `*.csv` files (exclude `template*.csv`)
  2. If 0 found → print error: "No catalog CSVs found in data/inputs/. Place your CSV file there or use -i flag."
  3. If 1 found → auto-select and process
  4. If 2+ found:
     - Check `sys.stdin.isatty()`:
       - If interactive (True) → render Rich picker: `[1] Gree_AC.csv (26 items)` etc. + `[A] Run All`
       - If non-interactive (False / CI / background) → print guidance to provide `-i` or `--batch` flag, or auto-process first catalog.
- [ ] When `-o` not specified → pass `use_structured_export=True` to `run_pipeline()`
- [ ] When `-o` specified → pass `output_path` directly (legacy behavior)

**CRITICAL**: All 138 existing tests must pass. The `-i` / `-o` explicit paths must work identically.

**Verification**: `pytest` (all 138+ tests green), manual test of `python index.py --help`, `python index.py` with files in `data/inputs/`

---

### Phase 1 Checkpoint
- [ ] `pytest` → all existing 138 tests + new ingestion/exporter tests pass
- [ ] `python index.py` with CSVs in `data/inputs/` → shows picker or auto-runs
- [ ] `python index.py -i Gree_Uploading_on_DigiMall_and_Price.csv -o test.csv` → legacy behavior works
- [ ] Output appears in `data/outputs/` with timestamp and latest file
- [ ] `ruff check .` → no lint errors

---

## Phase 2: Supabase Price History & Terminal Search

### Task 2.1: Create Supabase Tables for Price History

**What to add to `scripts/setup_supabase.sql`**:

```sql
-- Repricing Run History: One row per pipeline execution
CREATE TABLE IF NOT EXISTS repricing_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_name VARCHAR(256) NOT NULL,
    total_items INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Repricing Results: One row per product per run
CREATE TABLE IF NOT EXISTS repricing_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES repricing_runs(id),
    brand VARCHAR(64) NOT NULL,
    product_name TEXT NOT NULL,
    model VARCHAR(128) NOT NULL DEFAULT '',
    net_price NUMERIC(12, 2) NOT NULL,
    shipping_estimate NUMERIC(10, 2) NOT NULL,
    cost_base NUMERIC(12, 2) NOT NULL,
    final_price_alfa INT,
    final_price_digi INT,
    alfa_real_profit INT NOT NULL DEFAULT 0,
    digi_real_profit INT NOT NULL DEFAULT 0,
    digi_effective_commission VARCHAR(8) NOT NULL DEFAULT '10.00%',
    alfa_reason TEXT NOT NULL DEFAULT '',
    digi_reason TEXT NOT NULL DEFAULT '',
    alfa_risk_alert VARCHAR(32) NOT NULL DEFAULT 'NONE',
    digi_risk_alert VARCHAR(32) NOT NULL DEFAULT 'NONE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_results_run ON repricing_results (run_id);
CREATE INDEX IF NOT EXISTS idx_results_brand ON repricing_results (brand);
CREATE INDEX IF NOT EXISTS idx_results_model ON repricing_results (model);
CREATE INDEX IF NOT EXISTS idx_results_date ON repricing_results (created_at);
```

**RLS Policies**: Same pattern as existing tables — `service_role` full access, public read-only.

---

### Task 2.2: Add History Storage Methods to `pricing_engine/db.py`

**What to add to `SupabaseClient`**:
- [ ] `async def create_repricing_run(self, catalog_name, total_items) -> str | None` — inserts into `repricing_runs`, returns `run_id`
- [ ] `async def store_repricing_results(self, run_id, results: list[dict]) -> int` — batch inserts into `repricing_results`
- [ ] `async def query_runs_by_date(self, date_str) -> list[dict]` — fetches runs for a date
- [ ] `async def query_results_by_model(self, model_pattern) -> list[dict]` — fetches results matching model
- [ ] `async def query_results_by_run(self, run_id) -> list[dict]` — fetches all results for a run
- [ ] `async def query_latest_run(self) -> dict | None` — fetches most recent run
- [ ] `async def query_thin_margin_products(self, max_profit) -> list[dict]` — fetches products below profit threshold

**Pattern**: Follow existing `fetch_approved_capacities()` and `record_observations_batch()` patterns in `db.py`. All methods must gracefully return empty results if Supabase is not configured.

---

### Task 2.3: Auto-Store Results in Pipeline

**What to modify in `pipeline.py`**:
- [ ] After `out_df.to_csv()`, add async Supabase history sync:
  1. `run_id = await supabase_client.create_repricing_run(catalog_name, len(records))`
  2. Build results list from `records` with `target_model` extracted via `extract_search_query_and_model()`
  3. `await supabase_client.store_repricing_results(run_id, results_batch)`
- [ ] Non-blocking: if Supabase is down, pipeline completes normally — just skip history storage with a warning
- [ ] Show in finish banner: "☁️ Stored {N} results in Supabase price history"

---

### Task 2.4: Add `history` Subcommand to `index.py`

**What to add**:
- [ ] `python index.py history` → Interactive Rich menu:
  ```
  ╭─────────── PRICE HISTORY SEARCH ───────────╮
  │                                              │
  │  [1] Search by Model                        │
  │  [2] Search by Date                         │
  │  [3] Show Latest Run                        │
  │  [4] Show Thin Margin Products              │
  │                                              │
  │  Select option [1-4]:                       │
  ╰──────────────────────────────────────────────╯
  ```
- [ ] `python index.py history --model 12AITH21W` → Rich table showing all runs for this model with dates, prices, profits
- [ ] `python index.py history --date 2026-09-30` → Rich table showing all products repriced that day
- [ ] `python index.py history --latest` → Rich table showing last run's full results
- [ ] `python index.py history --profit-below 1000` → Rich table showing thin-margin products across all runs
- [ ] Each table shows: Date, Brand, Model/Name, Final Price Alfa, Final Price Digi, Alfa Profit, Digi Profit, Risk Alert

**Implementation**: Use `argparse` subcommands (`parser.add_subparsers()`).

---

### Phase 2 Checkpoint
- [ ] `pytest` → all tests pass (existing + new)
- [ ] Pipeline auto-stores results in Supabase on every run
- [ ] `python index.py history --latest` → shows last run's results
- [ ] `python index.py history --model 12AITH21W` → shows price history across runs
- [ ] History queries work even when pipeline hasn't run yet (empty results, no crash)
- [ ] Pipeline runs normally even when Supabase is down (graceful fallback)

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Breaking 138 existing tests | `run_pipeline()` keeps same signature with backwards-compatible optional params. Run `pytest` after EVERY function change. |
| `Name ` trailing whitespace in legacy CSVs | `df.columns = df.columns.str.strip()` applied on CSV load. |
| Test simulation files reference root CSVs | Keep original CSVs in root — do NOT delete them. `data/inputs/` copies are separate. |
| Supabase is down during pipeline run | History sync is wrapped in try/except with graceful skip. Pipeline always completes. |
