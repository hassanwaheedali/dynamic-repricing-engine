# AlfaMall & DigiMall Dynamic Repricing Engine — AI Agent Technical Handbook

Automated, high-speed dynamic repricing pipeline for Pakistani e-commerce platforms (**AlfaMall** and **DigiMall / Faysal Bank**). It queries direct backend search APIs, cleans variant mismatches and out-of-stock items, and calculates winning psychological prices under strict profit floors.

---

## 1. System Identity & Mission

- **Target Market**: Pakistani e-commerce retail (Consumer Electronics, Home Appliances, Split ACs, Washing Machines, Refrigerators, LEDs).
- **Core Philosophy**:
  1. **Zero Browser/Selenium Overhead**: Use direct HTTP JSON endpoints via `curl_cffi` (Chrome 120 impersonation) for sub-second responses and zero IP blocking.
  2. **Variant Match Protection**: Strict SKU model extraction. Never allow cross-variant or cross-color mispricing (e.g. `12AITH21W` White must never match `12AITH21B` Black; 8kg washers must never match 10kg washers).
  3. **Guaranteed Profit Floors**: Hard mathematical floor (+Rs. 500 minimum net profit guarantee). Never sell at a loss regardless of competitor price wars.
  4. **Two-Tier Bank Commission Arbitrage**: Leverage DigiMall's special 8% Faysal Bank rate to capture extra profit or win tough competition against competitors paying 10%.
  5. **Deterministic Data Integrity**: Guaranteed Column 1 `S.NO`, pure integer price outputs (zero `.0` float drift), and ANSI-free risk alerts.
  6. **Strict DRY Concept & Generic Dynamic Algorithms (Zero Category & Brand Hardcoding)**:
     - **Zero Static Lists**: Never hardcode category conditionals (`if 'MINI BAR'`), static brand lists (`["DAWLANCE", "GREE", ...]`), or static prefix sets (`(HWM|DWT|DW|WM|...)`) in `matcher.py` or anywhere in the engine.
     - **Dynamic SKU Prefixes**: All SKU prefixes (e.g. `DMB`, `HRF`, `HWM`, `GS`, `PR`, `WF`) must be extracted dynamically via generic regex (`\b([A-Za-z]{2,4})[- ]?{stem_num}`).
     - **Dynamic Initialism Referee**: 2-letter modifier tags (e.g. `SD` vs `Double Door`, `FL` vs `Top Load`) must be matched and collided dynamically via word boundaries and initialisms without static collision dictionaries.
     - **Dynamic Brand-Initial Verification**: Numeric stems must be validated against brand initials dynamically (`{brand[0]}[a-z]{1,3}[- ]?{model}`).
     - **Single Source of Truth**: Data mappings (e.g. AC capacity codes) must be defined once and referenced everywhere.
     - **Strict Ingestion Validation**: Catalogs must provide valid brands; guessing brands from title strings is strictly forbidden.

---

## 2. Core Logistics & Cost Math

### Mathematical Formulas

- **Volumetric Weight**:
  $$\text{Volumetric Weight (KG)} = \frac{\text{Length (cm)} \times \text{Width (cm)} \times \text{Height (cm)}}{5000}$$
- **Courier Shipping Estimate**:
  $$\text{Shipping Estimate (PKR)} = \text{Volumetric Weight} \times 70.0\text{ PKR (Standard Zone Courier Rate)}$$
- **Cost Base**:
  $$\text{Cost Base} = \text{Net Purchase Price} + \text{Shipping Estimate}$$
- **Total Without Profit (0% Margin Breakeven)**:
  - AlfaMall (10% Commission): $\frac{\text{Cost Base}}{0.90}$
  - DigiMall Leverage (8% Commission): $\frac{\text{Cost Base}}{0.92}$
- **Baseline Catalog Calculation**:
  $$\text{Baseline} = \frac{\text{Cost Base} + \text{Profit Target}}{0.90}$$
  *(Profit Target defaults to Rs. 500 if omitted in catalog)*
- **Absolute Hard Profit Floors (+Rs. 500 Net Profit Guarantee)**:
  - $\text{Floor}_{\text{Alfa}} = \frac{\text{Cost Base} + 500}{0.90}$
  - $\text{Floor}_{\text{Digi\_10}} = \frac{\text{Cost Base} + 500}{0.90}$
  - $\text{Floor}_{\text{Digi\_8}} = \frac{\text{Cost Base} + 500}{0.92}$
- **Monopoly Pricing (Zero Competitors in Market)**:
  $$\text{Monopoly Price} = \frac{\text{Cost Base} + 4000}{0.90} \longrightarrow \text{Psychological Threshold}$$

---

## 3. Pricing Decision Logic & Rules

### Strict Winning Condition
$$\text{Floor} \le \text{Our Final Price} < \text{Lowest Viable Competitor}$$
Our price must **always** be strictly lower than the lowest viable competitor to win the buy box.

### Retail Psychological Thresholds
Prices must end strictly in standard retail psychological endings:
- Available endings: `.999`, `.899`, `.799`, `.499`, `.299`, `.199`, `.099`.
- *Example*: If undercut calculation gives `72,877` and floor is `72,500`, final price is snapped to `72,899` or `72,799`.

### Platform Decision Engines

1. **AlfaMall (Strict 10% Commission)**:
   - Discard all scraped offers below $\text{Floor}_{\text{Alfa}}$ (sub-floor loss-makers).
   - If viable competitors exist: Undercut the lowest viable competitor $\ge \text{Floor}_{\text{Alfa}}$.
   - If lowest competitor is excessively inflated above baseline calculation: Apply **Capped Sweet-Spot** rule to protect high sales velocity.
   - If 0 competitors found: Set **Monopoly Price** (+Rs. 4,000 margin with psychological ending).
   - If all competitors are below floor: Fall back safely to $\text{Floor}_{\text{Alfa}}$ or return `NaN` with `SAFE_FALLBACK` alert.

2. **DigiMall (Two-Tier 10% $\rightarrow$ 8% Faysal Bank Switch)**:
   - **Tier 1 (Default 10% Tier)**: If the lowest competitor is $\ge \text{Floor}_{\text{Digi\_10}}$, undercut and win at 10% tier. Bank only charges 8%, capturing an extra 2% bank spread profit. Record `Digi Effective Commision` as `10.00%`.
   - **Tier 2 (Emergency 8% Switch)**: If lowest competitor is below $\text{Floor}_{\text{Digi\_10}}$ but $\ge \text{Floor}_{\text{Digi\_8}}$, switch to 8% bank rate, undercut to win. Record `Digi Effective Commision` as `8.00%`.
   - **Upper Band Undercut**: If lowest competitor is below $\text{Floor}_{\text{Digi\_8}}$, drop them and attempt to undercut the next higher viable competitor at 8%.
   - **Zero Competitors**: Apply Monopoly pricing (+Rs. 4,000 margin).

### Risk Alert Classifications
- `NONE`: Optimal healthy winning price.
- `THIN_BUFFER`: Real net profit is $< \text{Rs. } 700$ (close to floor).
- `SAFE_FALLBACK`: Market is entirely below floor; defaulted safely to floor price.
- `CAPPED_SWEET_SPOT`: Competitor price was artificially inflated; price capped to ensure conversion.
- `SERVER_DOWN`: Upstream platform API timed out or failed (HTTP non-200).

---

## 4. Module Architecture & Code Contracts

```
pricing_engine/
├── calculator.py       # Pure math: volumetric weight, shipping, floors, psychological endings
├── matcher.py          # 4-slot model extraction, brand stripping, negative variant filtering
├── scraper.py          # Async JSON endpoints via curl_cffi, 3-tier waterfall, in-memory cache
├── evaluator.py        # AlfaMall & DigiMall decision logic, sweet-spot capping, profit calculations
├── ingestion.py        # CSV catalog loader, 6-column contract validation, S.NO normalization, pre-flight banner
├── exporter.py         # Timestamped + latest CSV dual export, pure-integer formatting, panel rendering
├── pipeline.py         # Concurrency orchestration, asyncio semaphore, Rich terminal cards, S.NO column guarantee
├── models.py           # Strongly typed dataclasses (ProductInput, PlatformPricingResult, ScrapedOffer, etc.)
├── learner.py          # Autonomous search query pattern extraction engine
├── registry.py         # Regex pattern registry (in-memory + Supabase sync)
└── db.py               # Async Supabase client for pattern registry & price history
```

### Component Details

- **`pricing_engine/ingestion.py`**:
  - Function: `ingest_catalog(file_path: Path, render_banner: bool = True) -> tuple[list[ProductInput], IngestionReport]`
  - Strips whitespace globally across headers and string values.
  - Enforces 6 required columns: `Brand`, `Name`, `Net Price`, `Length`, `Width`, `Height`.
  - Supports optional 7th column: `Profit` (defaults to 500.0).
  - Normalizes `S.NO` from all casings (`S.NO`, `S.No`, `sno`, `Serial No`), handles float drift (`1.0` -> `1`), and auto-generates 1-indexed integers if missing.
  - Ignores custom extra columns silently during validation and preserves them in output.

- **`pricing_engine/exporter.py`**:
  - Function: `export_results(df, source_filename, output_dir="data/outputs", timestamp=None, render_panel=True) -> ExportManifest`
  - Creates two output artifacts:
    - `{stem}_repriced_{YYYYMMDD_HHMMSS}.csv` (permanent audit history).
    - `{stem}_repriced_latest.csv` (always-current upload copy).
  - Sanitizes price columns (`PRICE_INT_COLUMNS`) and `S.NO` using `format_export_price()` and `format_export_sno()` to eliminate `.0` float drift.

- **`pricing_engine/pipeline.py`**:
  - Function: `run_pipeline(input_path, output_path=None, concurrency=3, verbose=True, use_structured_export=False, export_dir=Path("data/outputs"))`
  - Reconstructs `out_record` guaranteeing `S.NO` is Column 1.
  - Binds concurrency via `asyncio.Semaphore(concurrency)`.
  - Renders live Rich execution cards and executive summary tables.

- **`index.py`**:
  - CLI entrypoint. Scans `data/inputs/` for CSVs.
  - Guarded with `sys.stdin.isatty()`: Interactive Rich menu when human terminal is detected; automatic non-blocking selection in headless/cron mode.
  - Flags: `-i / --input`, `-o / --output`, `-b / --batch / -a`, `-c / --concurrency`, `-q / --quiet`.

---

## 5. Input & Output Schema Standards

### Input Catalog Contract (`data/inputs/`)
| Column | Type | Required? | Fallback / Behavior |
| :--- | :--- | :--- | :--- |
| `Brand` | `str` | **Required** | Stripped of whitespace |
| `Name` | `str` | **Required** | Product model extracted from title |
| `Net Price` | `float` | **Required** | Purchase price (commas auto-stripped) |
| `Length` | `float` | **Required** | Box length in cm |
| `Width` | `float` | **Required** | Box width in cm |
| `Height` | `float` | **Required** | Box height in cm |
| `Profit` | `float` | Optional | Defaults to `500.0` if empty or missing |
| `S.NO` / `S.No` | `int/str`| Optional | Auto-generates `1, 2, 3...` if omitted |
| *Custom Cols* | `Any` | Optional | Preserved intact in output CSV |

### Output Catalog Contract (`data/outputs/`)
Standardized output column ordering:
1. `S.NO` (Always Column 1, pure integer or SKU string)
2. Original input columns (`Brand`, `Name`, `Net Price`, `Length`, `Width`, `Height`, `Profit`, any custom tags)
3. Calculated pricing columns:
   - `Shipping Estimate`
   - `Commision` (`10.00%`)
   - `Digi Effective Commision` (`10.00%` or `8.00%`)
   - `Total Without Profit` (Cost base breakeven at effective rate)
   - `Calculation` (Baseline target price)
   - `Minimum Price Alfa`, `Maximum Price Alfa`
   - `Minimum Price Digi`, `Maximum Price Digi`
   - `Final Price Alfa`, `Final Price Digi`
   - `Alfa Real Profit`, `Digi Real Profit`
   - `Alfa Reason`, `Digi Reason`
4. Risk Alert columns (Always final two columns):
   - `Alfa Risk Alert`
   - `Digi Risk Alert`

---

## 6. Scraping & Network Architecture

### Direct JSON Endpoints
- **AlfaMall**:
  `https://be.alfamall.com/storefront/search_products?page=1&q={query}&limit=18&storefront=23&storefront_domain=alfamall.com`
- **DigiMall / Faysal Bank**:
  `https://digimall-be.faysalbank.com/storefront/search_products?storefront=23&q={query}&page=1&limit=18`

### Network Guardrails
- **Client**: `curl_cffi.requests.AsyncSession(impersonate="chrome120")`.
- **Waterfall Strategy**: Tier 1 (Exact clean) $\rightarrow$ Tier 2 (Bare stem) $\rightarrow$ Tier 3 (Permutations). Early exit if Tier 1 yields $\ge 2$ candidates.
- **In-Memory Cache**: Run-scoped `(platform, query)` cache to eliminate duplicate network calls for common models.
- **Out-of-Stock Guard**: Offer dropped immediately if `item.get("sold_out") is True`.

---

## 7. Testing Discipline & Quality Gates

The codebase enforces strict test-driven development:
- **Test Suite**: Located in `tests/` (168 passing tests).
- **Test Fixtures**: Isolated in `tests/fixtures/` (`Gree_Uploading_on_DigiMall_and_Price.csv`, `Haier_Washing_Machines_Uploading_and_Price.csv`, `Stock Holding Report 25-Feb-2026.csv`).
- **Commands**:
  ```bash
  pytest -v               # Run complete test suite (must be 100% green)
  ruff check .            # Linting and style check (must have 0 errors)
  ```
- **Regression Protection**: Every bug fix or edge case must have a corresponding test in `tests/test_pipeline_resilience.py` or the appropriate test module.

---

## 8. Phase 2 Roadmap Blueprint: Supabase History & CLI

When implementing Phase 2, follow these exact requirements:

1. **Database Schema (`scripts/setup_supabase.sql`)**:
   - `repricing_runs`: `id (UUID PK)`, `catalog_name (text)`, `total_items (int)`, `created_at (timestamptz)`.
   - `repricing_results`: `id (UUID PK)`, `run_id (FK)`, `brand (text)`, `model (text)`, `product_name (text)`, `net_price (numeric)`, `shipping (numeric)`, `alfa_price (numeric)`, `digi_price (numeric)`, `alfa_profit (numeric)`, `digi_profit (numeric)`, `alfa_risk (text)`, `digi_risk (text)`, `created_at (timestamptz)`.
   - B-tree indexes on `run_id`, `model`, `brand`, and `created_at`.

2. **Persistence Methods (`pricing_engine/db.py`)**:
   - `create_repricing_run(catalog_name: str, total_items: int) -> str | None`
   - `store_repricing_results(run_id: str, results: list[dict[str, Any]]) -> int`
   - `query_runs_by_date(date_str: str) -> list[dict]`
   - `query_results_by_model(model_pattern: str) -> list[dict]`
   - `query_latest_run() -> dict | None`
   - `query_thin_margin_products(max_profit: float) -> list[dict]`
   - **Offline Resilience**: All DB calls must gracefully return empty/None if credentials are missing or Supabase is unreachable. Never block or crash the CSV repricing pipeline.

3. **CLI History Subcommand (`index.py`)**:
   - Subparser: `python index.py history [--latest | --model <pattern> | --date <YYYY-MM-DD> | --profit-below <amount>]`.
   - If run without flags in an interactive terminal, display an interactive Rich query menu.
   - Render results in styled Rich tables with model, date, prices, profits, and risk alert badges.
