# AlfaMall & DigiMall Dynamic Repricing Engine — AI Agent Technical Handbook

Automated, high-speed dynamic repricing pipeline for Pakistani e-commerce platforms (**AlfaMall** and **DigiMall / Faysal Bank**). It queries direct backend search APIs, cleans variant mismatches and out-of-stock items, and calculates winning psychological prices under strict profit floors.

---

## 0. Mandatory Agent Working Agreement

This section records the owner's engineering and collaboration requirements. Apply it to every task, including work continued by another agent. Current explicit user instructions determine scope; an implementation plan or this handbook is not permission to modify unrelated files.

### Understand the pipeline before changing the algorithm

- Treat `matcher.py` and capacity/model interpretation as financially consequential core logic. A false match can cause incorrect repricing even when the price calculations themselves are correct.
- Inspect the actual current files, staged AND unstaged diffs, callers, configuration, fixtures, and tests. Do not rely solely on conversation summaries, another agent's report, comments, or historical test counts.
- Trace the relevant complete path: ingestion and aliases -> normalization -> model/measurement extraction -> query planning -> discovery -> matching and variant guards -> evaluation -> checkpoint reuse -> output/export. Locate where evidence is introduced, transformed, discarded, or reused.
- Identify the root cause and the owning layer. A failure visible in matching may originate in measurement parsing, query generation, seller cleanup, stale state, or output assembly. Fix its producer rather than adding compensating exceptions downstream.
- Record verified facts, assumptions, unresolved product decisions, and expected behavior separately. Never turn a plausible guess into a business rule.

### Required workflow: Research -> Innovate -> Think -> Plan -> Execute -> Review

| Phase | Required work and evidence |
| --- | --- |
| **Research** | Read-only investigation. Reproduce the failure, trace the pipeline, inspect existing shared logic, and establish representative baseline behavior. Identify both valid matches and dangerous false matches. |
| **Innovate** | Consider viable approaches proportionate to the problem. Prefer extending the canonical algorithm over another parser, branch, or parallel implementation. Explain compatibility and failure-mode tradeoffs. |
| **Think** | Challenge assumptions: what proves product identity, what could be a measurement or prose, what happens with an unfamiliar brand/category, and what information might normalization erase? State invariants before choosing an approach. |
| **Plan** | Present the root cause, proposed unified algorithm, affected boundaries, intended behavior changes, adversarial tests, and validation steps before nontrivial implementation. Honor any user-requested approval gate. Existing approval persists; do not repeatedly ask permission for already-authorized steps. |
| **Execute** | Implement in small coherent increments. Write a failing behavioral regression first for logic changes; verify it fails for the intended reason, then implement the general correction. Preserve the existing worker pipeline and shared contracts. |
| **Review** | Inspect the complete diff and actual outcomes, run relevant and full regression checks, and conduct separate adversarial review before every commit. Reconcile findings against the actual code and evidence, then report remaining limitations honestly. |

Keep concise task notes for substantial work in the repository's existing `tasks/` or `docs/` structure. Do not create a separate document or framework for every trivial operation. Record outcomes, decisions, and reproducible evidence rather than private reasoning transcripts.

### No shortcuts, duplicate policies, or product exception chains

- Never fix a single model, brand, category, seller listing, or failing fixture by introducing an exception that cannot be justified as a general rule. Do not keep patching each new counterexample onto the previous heuristic.
- A regression example is evidence for discovering the defect; it is not the specification of the algorithm. Derive the general rule and test its counterexamples, boundaries, symmetry, and applicability to unseen inputs.
- Search for and reuse the canonical parser, normalizer, unit definitions, alias resolution, configuration, and validator before writing another one. Equivalent representations must not receive different identity or collision decisions in different modules/platforms.
- DRY means one source of semantic truth, not merely moving repeated code into a helper. Do not centralize an incorrect assumption or force contexts with different meanings through a lossy shared regex.
- Do not implement new hardcoded brand/model/prefix dictionaries, category-name conditionals, ad hoc descriptor-removal lists, or arbitrary word-count/digit-count/range limits to make selected examples pass. Every bound needs a demonstrated contract or documented configuration basis; inherited bounds are not automatically correct.
- Legitimate shared unit vocabularies, spelling aliases, typed schema enums, and declarative approved shipping/business tables are data, not automatically forbidden hardcoding. Define them once and reference them. They must not conceal product-specific matching exceptions.
- Hardcode only what is strictly required: shared data tables (units, aliases, enums, approved business tables) defined once in a single source of truth. Decision logic must be structural and general (token runs, digit/letter boundaries, numeric ordering, unit binding, symmetry), never a list of words, brands, models, stores, promo terms, or phrases added to make selected titles pass. Before adding any literal word list or phrase regex, first prove that no existing canonical vocabulary or structural rule can express it; if a new vocabulary is truly unavoidable, define it once with its documented contract, cover it with unseen-input tests, and state it explicitly in the review as new hardcoding.
- Brand/product names in test fixtures or explanatory comments are not executable brand exceptions. Distinguish new hardcoding from inherited hardcoding and structural heuristics when reviewing; show the relevant executable condition and its consequence.
- Do not invent equivalence between a model number and a capacity/count. A unit, nearby word, short prefix, or matching number can nominate evidence but cannot independently prove SKU identity.

### Evidence-preserving identity and normalization

- Preserve explicit brand, full SKU, subordinate model tags, color, capacity, and physical-feature conflicts. Never remove contradictory evidence merely to obtain an accepted match or a cheaper competitor.
- Keep explicit identity evidence, measurements, normal prose, and ambiguous observations distinguishable through the relevant pipeline. Do not silently reinterpret ambiguity as a confirmed match or as confirmed absence of a constraint. Use existing review/rejection contracts where evidence is insufficient.
- Normalization must preserve meaning across harmless casing, whitespace, punctuation, aliases, separator variants, quotation styles, and word order. Do not let `in` versus `IN` change physical capacity merely because one regex branch is case-sensitive.
- Normalize a protected measurement/model span before any cleanup that would destroy its evidence. Verify cleanup ordering, not only individual helper functions. Repeated normalization must not progressively change identity.
- A measurement range is not an exact endpoint. Check spaced/unspaced hyphens and slashes, decimals, thousands separators, attached/separate units, quoted models, and prose prepositions. Reject or retain uncertainty rather than silently selecting a range endpoint.
- A broader fallback query may improve retrieval; it must not weaken the final brand/model/variant referee. Exact queries retain their established priority, and incomplete discovery must not be represented as a confirmed empty market.
- Do not infer missing catalog brands from titles. Do not edit input names, colors, SKU suffixes, fixtures, expected outputs, or source catalogs to hide an algorithmic defect. User-verified catalog corrections are authoritative for that catalog and must not become global equivalence rules.

### Regression tests must challenge the rule

- Include positive and negative cases, unseen synthetic brands/models, cross-brand isolation, opposing colors/capacities, conflicting explicit SKUs, missing evidence, and both matching directions where applicable.
- Exercise combinations rather than only isolated examples: unit before/after color and descriptors, upper/lowercase, spaced ranges, quote styles, numeric boundaries, multiword series, and words that resemble prefixes. Do not exclude a valid input just because it breaks the proposed shortcut.
- Use dynamic synthetic fixtures for general algorithm tests and representative existing catalogs for compatibility. Real product fixtures may document a regression; the implementation must not recognize those fixture names specially.
- Tests must assert observable identity/coverage/output behavior, not merely repeat the implementation's regex or arbitrary cutoff. Do not change expected results solely to turn a failure green; justify each intentional behavior delta.
- Validate input parsing, model extraction, query coverage/order, final match decisions, pricing/commission invariants, and complete CSV/XLSX output where affected. Helper tests alone do not establish end-to-end correctness.
- Report actual commands, results, warnings, and any skipped or blocked checks. Passing selected tests is not proof that the entire catalog is correct. Never claim a full suite, live marketplace check, coverage percentage, or performance result that was not measured for the stated revision/scope.
- Discover the active test/tool configuration; use the project virtual environment. Established checks include pytest, Ruff, and strict Mypy for `pricing_engine` and `index.py`. Historical numbers below are not current verification evidence.

### Separate adversarial review and commit discipline

- Before **every commit**, a separate review sub-agent must inspect the relevant final artifact and contract for correctness, architecture, readability/DRY, security, and performance. Give it an adversarial task, not a request to approve. Do not use a reviewer to rubber-stamp a conclusion.
- The primary agent must personally read the relevant diff and verify substantive findings. A reviewer can be wrong: reproduce findings, distinguish confirmed bugs from policy concerns, and retract claims contradicted by source/history. A test-green result does not override a demonstrated false match.
- Fix actionable issues in the authorized scope and recheck them before committing. If unresolved issues remain, disclose them; do not claim the file is safe or bury the failures under passing-test counts. If a review tool is unavailable, report the missing review rather than claiming equivalent verification.
- Additional external/cross-model review is optional and requires user authorization. Respect a user's decision to skip it; separate sub-agent review remains required.
- Preserve other agents' and the user's staged/unstaged work. Respect file-specific instructions such as “review only,” “do not edit,” and “do not commit matcher.” Never reset, stash, overwrite, or commit excluded work to manufacture a clean tree.
- Stage explicit, reviewed scope; do not use blanket staging when unrelated changes exist. Inspect the staged diff before committing. No engine-code change is implied by a request to update documentation or agent instructions.
- Coordinate or isolate verification when another agent is editing core files. A source-provenance guard firing during edits is not evidence of a pricing bug. An isolated payload check must use complete fixtures and be reported as isolated verification, not a passing live working-tree suite.
- A clean-tree request never authorizes deleting or committing preserved user work. Report intentional remaining changes clearly. Do not push, merge, or deploy merely because a local commit was authorized.

### Owner collaboration and explanations

- Respond in the user's language; Roman Urdu is appropriate when they use it. Keep technical identifiers precise. Explain the concrete problem, why it happens, its consequence, and the general fix in understandable language.
- Lead with verified outcomes. Show a minimal reproducer or file/line evidence for important claims. Explain what changed in each requested file, what is useful, what is unsafe, and what tests do or do not establish.
- Do not blame another agent for assumptions or heuristic fixes you contributed. Acknowledge and correct your own meaningful mistakes plainly.
- Do not add unnecessary confirmations, features, restrictive business policies, or unrelated refactors. Ask only for genuinely missing product intent/authority; continue independent authorized work while waiting.
- For review-only requests, provide findings and recommended correction order without implementing them. When implementation is explicitly requested, carry it through the authorized verification and review steps rather than stopping at advice.

### Re-run and artifact behavior already agreed with the owner

- `S.NO` is optional display numbering, never a persistent product identifier. Row position does not prove identity. Reuse requires validated, compatible, uniquely reconciled input content; do not fabricate identities or modification histories for renamed/ambiguous products.
- Automatic interactive re-run choices apply to meaningful input changes or pending work. Unchanged completed input, including duplicates conservatively requiring processing, must not prompt merely because results cannot be reused. Full refresh remains available; headless unspecified execution defaults to full.
- An explicitly requested targeted run must not silently become an incompatible full run. Preserve the established first-run exception and explicit full authorization behavior.
- Keep working recovery state separate from completed snapshots; validate provenance and dependencies before reuse. Concurrent executions must not mix state or outputs. Preserve current input ordering and complete row coverage.
- Publication is atomic per file, not transactional across all files. Report partial failures and stale optional outputs truthfully. Winner cleanup may touch only verified owned current artifacts, never historical, edited, or unverified files.

The technical descriptions below document existing contracts and history; verify them against current code and the owner's explicit requirements before relying on them. If a substantive conflict exists, report it rather than silently changing business behavior or treating a stale description as a proven implementation fact.

---

## 1. System Identity & Mission

- **Target Market**: Pakistani e-commerce retail (Consumer Electronics, Home Appliances, Split ACs, Washing Machines, Refrigerators, LEDs).
- **Core Philosophy**:
  1. **Zero Browser/Selenium Overhead**: Use direct HTTP JSON endpoints via `curl_cffi` (Chrome 120 impersonation) for sub-second responses and zero IP blocking.
  2. **Variant Match Protection**: Strict SKU model extraction. Never allow cross-variant or cross-color mispricing (e.g. `12AITH21W` White must never match `12AITH21B` Black; 8kg washers must never match 10kg washers).
  3. **Guaranteed Profit Floors**: Hard mathematical floor (+Rs. 500 minimum net profit guarantee). Never sell at a loss regardless of competitor price wars.
  4. **Strictly Fixed Per-Vendor Commissions**: Each vendor strictly applies its own configured percentage (`effective_commission_rate == configured_vendor_commission_rate`; defaults `ALFA_COMMISSION_PCT = 10.0`, `DIGI_COMMISSION_PCT = 8.0`) across every calculation, floor, pipeline, checkpoint, CSV, and XLSX formula. Zero automatic emergency overrides or hidden fallbacks.
  5. **Deterministic Data Integrity**: Guaranteed Column 1 `S.NO`, pure integer price outputs (zero `.0` float drift), and ANSI-free risk alerts.
  6. **Strict DRY Concept & Generic Dynamic Algorithms (Zero Category & Brand Hardcoding)**:
     - **No Product Exception Lists**: Never hardcode category conditionals (`if 'MINI BAR'`), static brand exceptions (`["DAWLANCE", "GREE", ...]`), or static SKU prefix sets (`(HWM|DWT|DW|WM|...)`) in engine algorithms. Shared unit/alias definitions and approved declarative configuration belong in a single source of truth; see section 0.
     - **Dynamic SKU Prefixes**: All SKU prefixes (e.g. `DMB`, `HRF`, `HWM`, `GS`, `PR`, `WF`) must be extracted dynamically via generic regex (`\b([A-Za-z]{2,4})[- ]?{stem_num}`).
     - **Dynamic Initialism Referee**: 2-letter modifier tags (e.g. `SD` vs `Double Door`, `FL` vs `Top Load`) must be matched and collided dynamically via word boundaries and initialisms without static collision dictionaries.
     - **Dynamic Brand-Initial Verification**: Numeric stems must be validated against brand initials dynamically (`{brand[0]}[a-z]{1,3}[- ]?{model}`).
     - **Single Source of Truth**: Data mappings (e.g. AC capacity codes) must be defined once and referenced everywhere.
     - **Strict Ingestion Validation**: Catalogs must provide valid brands; guessing brands from title strings is strictly forbidden.
  7. **No Lazy Shortcuts Under Any Circumstances:**
   - Never write a one-off quick fix or narrow conditional just to satisfy a single failing test case.
   - Every algorithmic change must be designed universally from first principles, verified against the entire catalog logic, and tested for adversarial cross-brand isolation.

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
  - AlfaMall (`ALFA_COMMISSION_PCT`, default `10.0` $\rightarrow$ `0.90` payout): $\frac{\text{Cost Base}}{1 - \text{ALFA\_COMMISSION\_PCT}/100}$
  - DigiMall (`DIGI_COMMISSION_PCT`, default `8.0` $\rightarrow$ `0.92` payout): $\frac{\text{Cost Base}}{1 - \text{DIGI\_COMMISSION\_PCT}/100}$
- **Absolute Hard Profit Floors (+Rs. 500 Net Profit Guarantee)**:
  - $\text{Floor}_{\text{Alfa}} = \frac{\text{Cost Base} + \text{Min Profit}}{1 - \text{ALFA\_COMMISSION\_PCT}/100}$
  - $\text{Floor}_{\text{Digi}} = \frac{\text{Cost Base} + \text{Min Profit}}{1 - \text{DIGI\_COMMISSION\_PCT}/100}$
- **Monopoly Pricing (Zero Competitors in Market)**:
  $$\text{Monopoly Price}_{\text{vendor}} = \frac{\text{Cost Base} + 4000}{1 - \text{Vendor Commission \%}/100} \longrightarrow \text{Psychological Threshold}$$

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

1. **AlfaMall (Strictly Fixed Configured Rate, Default 10%)**:
   - Discard all scraped offers below $\text{Floor}_{\text{Alfa}}$ (sub-floor loss-makers).
   - If viable competitors exist: Undercut the lowest viable competitor $\ge \text{Floor}_{\text{Alfa}}$.
   - If lowest competitor is excessively inflated above baseline calculation: Apply **Capped Sweet-Spot** rule to protect high sales velocity.
   - If 0 competitors found: Set **Monopoly Price** (+Rs. 4,000 margin with psychological ending).
   - If all competitors are below floor: Fall back safely to $\text{Floor}_{\text{Alfa}}$ or return `NaN` with `SAFE_FALLBACK` alert.

2. **DigiMall (Strictly Fixed Configured Rate, Default 8%)**:
   - Strictly uses `DIGI_COMMISSION_PCT` (`get_digi_commission_pct()` / `get_digi_payout_rate()`) across every branch with zero emergency rate switching.
   - Discard all scraped offers $\le \lceil \text{Floor}_{\text{Digi}} \rceil$ (sub-floor loss-makers).
   - If viable competitors exist: Undercut the lowest viable competitor with adaptive psychological pricing and optional sweet-spot capping.
   - If all competitors are below floor: Apply Safe Fallback pricing above $\text{Floor}_{\text{Digi}}$ with `SAFE_FALLBACK` alert.
   - If 0 competitors found (and discovery is complete): Apply Monopoly pricing (+Rs. 4,000 target margin at configured Digi rate).

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
├── calculator.py       # Pure math: volumetric weight, shipping, floors, psychological endings, fallback rates
├── config.py           # Declarative category & capacity fallback shipping tables (single source of truth)
├── matcher.py          # 4-slot model extraction, brand stripping, negative variant filtering
├── scraper.py          # Async JSON endpoints via curl_cffi, 3-tier waterfall, in-memory cache
├── evaluator.py        # AlfaMall & DigiMall decision logic, sweet-spot capping, profit calculations
├── ingestion.py        # CSV catalog loader, 3+1 column validation, collision-free alias normalization, banner
├── exporter.py         # Timestamped + latest CSV/XLSX dual export, pure-integer formatting, panel rendering
├── pipeline.py         # Concurrency orchestration, InOrderCardDispatcher, Rich cards, S.NO column guarantee
├── range_pipeline.py   # Market Range mode pipeline (Alfa/Digi Min/Max discovery)
├── models.py           # Strongly typed dataclasses (ProductInput, PlatformPricingResult, ScrapedOffer, etc.)
├── learner.py          # Autonomous search query pattern extraction engine
├── registry.py         # Regex pattern registry (in-memory + Supabase sync)
└── db.py               # Async Supabase client for pattern registry & price history
```

### Component Details

- **`pricing_engine/ingestion.py`**:
  - Function: `ingest_catalog(file_path: Path, render_banner: bool = True) -> tuple[list[ProductInput], IngestionReport]`
  - Function: `normalize_catalog_columns(columns: list[Any], preserve_name_space: bool = False) -> list[str]`
  - Strips whitespace globally across headers and string values.
  - Enforces 3 core required columns: `Brand`, `Name` (or aliases), `Net Price`. Dimensions (`Length`, `Width`, `Height`) are optional; if omitted, automatically resolved via category fallback shipping.
  - Normalizes common column aliases (`Title`, `Product Name`, `Product Title`, `Model`, `Cost`, `NetPrice`) non-destructively without causing duplicate column collisions in Pandas.
  - Rejects empty, missing, or placeholder product names/brands (`INVALID_NAME_VALUES`, `INVALID_BRAND_VALUES`) at pre-flight with zero silent fallbacks.
  - Supports optional `Profit` (defaults to 500.0).
  - Normalizes `S.NO` from all casings (`S.NO`, `S.No`, `sno`, `Serial No`), handles float drift (`1.0` -> `1`), and auto-generates 1-indexed integers if missing.
  - Auto-detects delimiters (comma vs tab) via `pd.read_csv(sep=None, engine='python')`.

- **`pricing_engine/exporter.py`**:
  - Function: `export_results(df, source_filename, output_dir="data/outputs", timestamp=None, render_panel=True) -> ExportManifest`
  - Creates two output artifacts:
    - `{stem}_repriced_{YYYYMMDD_HHMMSS}.csv` (permanent audit history).
    - `{stem}_repriced_latest.csv` (always-current upload copy).
    - `{stem}_repriced_latest.xlsx` (dynamic Excel workbook with formulas).
  - Sanitizes price columns (`PRICE_INT_COLUMNS`) and `S.NO` using `format_export_price()` and `format_export_sno()` to eliminate `.0` float drift.

- **`pricing_engine/pipeline.py`**:
  - Function: `run_pipeline(input_path, output_path=None, concurrency=3, verbose=True, use_structured_export=False, export_dir=Path("data/outputs"), platform="all", personal_comm_pct=0.0)`
  - Reconstructs `out_record` guaranteeing `S.NO` is Column 1.
  - Binds concurrency via `asyncio.Semaphore(concurrency)`.
  - Employs `InOrderCardDispatcher` for strictly deterministic ascending terminal card rendering (`1 -> 2 -> 3...`) with zero concurrency loss.
  - Renders live Rich execution cards and executive summary tables.

- **`index.py`**:
  - CLI entrypoint. Scans `data/inputs/` for CSVs.
  - Guarded with `sys.stdin.isatty()`: Interactive Rich menu when human terminal is detected; automatic non-blocking selection in headless/cron mode.
  - Flags: `-i / --input`, `-o / --output`, `-b / --batch / -a`, `-c / --concurrency`, `-q / --quiet`, `-r / --range-only`, `-p / --platform`, `-m / --personal-comm`.

---

## 5. Input & Output Schema Standards

### Input Catalog Contract (`data/inputs/`)
| Column | Type | Required? | Fallback / Behavior |
| :--- | :--- | :--- | :--- |
| `Brand` | `str` | **Required** | Valid brand name (empty or placeholder strings rejected) |
| `Name` / `Title` | `str` | **Required** | Model name extracted from title (`Title`, `Product Name`, `Model` aliases accepted) |
| `Net Price` | `float` | **Required** | Purchase price (commas auto-stripped; `Cost`, `NetPrice` aliases accepted) |
| `Length` | `float` | Optional | Box length in cm (if missing, category fallback rate is resolved) |
| `Width` | `float` | Optional | Box width in cm (if missing, category fallback rate is resolved) |
| `Height` | `float` | Optional | Box height in cm (if missing, category fallback rate is resolved) |
| `Profit` | `float` | Optional | Defaults to `500.0` if empty or missing |
| `S.NO` / `S.No` | `int/str`| Optional | Auto-generates `1, 2, 3...` if omitted |
| *Custom Cols* | `Any` | Optional | Preserved intact in output CSV |

### Output Catalog Contract (`data/outputs/`)
Standardized output column ordering:
1. `S.NO` (Always Column 1, pure integer or SKU string)
2. Original input columns (`Brand`, `Name`, `Net Price`, `Length`, `Width`, `Height`, `Profit`, any custom tags)
3. Calculated pricing columns:
   - `Shipping Estimate`
   - `Alfa Commission` (present in unified / `--platform alfa` exports)
   - `Digi Commission` (present in unified / `--platform digi` exports)
   - `Insurance` (present only when product category defines it, anchored right after commission columns)
   - `Total Without Profit (Alfa)` (present in unified / `--platform alfa` exports)
   - `Total Without Profit (Digi)` (present in unified / `--platform digi` exports)
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
- **Test Suite**: Located in `tests/`. Historical counts are not guarantees; discover and run the current suite and report actual results for the current revision.
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

---

## 9. Market Range Mode (`pricing_engine/range_pipeline.py`)

- Entry: `python index.py -r/--range-only` (or mode `[2]` in the interactive prompt, TTY only). Input needs only `Brand` + `Name`.
- Reuses scraper + matcher unchanged (variant protection intact). Scrapes with `floor_price=None` (the waterfall queries every tier, so Max is not understated).
- `evaluate_market_range(offers) -> MarketRange` (evaluator.py) is the single source of truth for min/max over in-stock offers; both platform evaluators use it too.
- Output columns follow section 5, with cost/decision columns blank, plus `Alfa Offers Found` / `Digi Offers Found` between `Maximum Price Digi` and `Final Price Alfa`. Risk alerts: `NONE | NO_OFFERS | SERVER_DOWN`.
- Exports via `export_range_results(...)` to `data/outputs/range/{csv,xlsx}/` (timestamped + latest). XLSX failures never abort the run.
- Tests: `tests/test_range_mode.py`, plus range cases in `tests/test_cli.py`.

---

## 10. In-Order Buffered Terminal Output (`pricing_engine/pipeline.py`)

- **Class**: `InOrderCardDispatcher(lock=render_lock)`
- **Mechanism**:
  - Workers scrape asynchronously in parallel bounded by `asyncio.Semaphore(concurrency=3)`.
  - When worker finishes item `idx`, it buffers a render closure in `_buffer[idx]`.
  - Contiguous ascending sequence `0, 1, 2, 3...` is flushed strictly in order to the terminal.
  - Zero performance slowdown (0.00% throughput regression).
  - Deadlock-free: `skip(idx)` handles worker failures, while `flush()` inside `try...finally` guarantees complete buffer release.
- Tests: `test_in_order_card_dispatcher_sequence` and `test_in_order_card_dispatcher_skip_on_error` in `tests/test_pipeline.py`.

---

## 11. Personal Commission Arbitrage Mode (`-m / --personal-comm`)

- Entry: `python index.py -m <percentage>` (e.g. `-m 5` for 5% personal commission floor).
- In addition to standard platform bank floors, enforces merchant commission floor:
  $$\text{Personal Floor} = \frac{\text{Net Price} \times (1 + \text{comm}\%) + 500 + \text{Shipping}}{1 - \text{platform\_comm}}$$
- Winning items meeting merchant profit floor are highlighted with personal commission profit breakdown.
- Automatically exports winning 5% candidates to `data/outputs/winners_personal_{comm}pct_{timestamp}.csv`.

---

## 12. Declarative Category Fallback Shipping (`pricing_engine/config.py`)

- **Single Source of Truth**: `FALLBACK_SHIPPING_TABLE` in `config.py`.
- **Zero Static Logic**: Eliminates category conditionals in code. Declaratively matches appliance categories and capacity sub-types (e.g. Twin Tub, Single Tub, Automatic Washers: 8kg -> Rs. 2,500/3,000/3,500, 10kg -> Rs. 3,000/3,500, 12-15kg -> Rs. 3,500/4,500).
- Seamlessly resolves landed shipping for catalogs providing only `Brand, Title, Net Price` without box measurements.

