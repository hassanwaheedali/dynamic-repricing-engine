# Tasks Checklist: Enterprise Autonomous Multi-Pattern Repricing Engine

## Previously Completed Sprints
- [x] **v1 Core Matcher (Tasks 1-5)**: Brand-agnostic SKU extraction, token runs, distributive expansion, strict variant match, zero-hardcoded color isolation. (78 tests green)
- [x] **v2 Matcher Gap Fixes (Tasks 6-10)**: Technical slash safeguards (`/DC`, `/KB`, `/YY`, `W/O`), Dawlance name-only fallback, T3 isolation, and numeric hyphenated SKU detection. (84 tests green)
- [x] **Universal Multi-Brand Capacity Mappings (Task 11)**: Universal BTU structure (`09`=0.75T, `12`=1T, `18`=1.5T, `24`=2T, `28`/`30`=2.5T, `36`=3T, `48`=4T) + Dawlance structure (`10`=0.75T, `15`=1T, `20`=1.25T, `30`=1.5T, `45`=2T) + disambiguation. (85 tests green)

---

## Active Roadmap: Enterprise Autonomous Architecture

### Phase 1: Baseline Stabilization & Multi-Catalog Data Integration

- [x] **Task 1.1: Multi-Catalog Dataset Integration**
  - Bring `Haier_Washing_Machines_Uploading_and_Price.csv` and `final_haier_wm_repriced.csv` into the workspace root.
  - Sample representative models from `Stock Holding Report - FINAC - Products - MainSheet.csv` (Refrigerators: `276EBS SILVER`, `306IDB BLACK`, `418IFG1U1 IOT GREY`; Microwave Ovens; Water Dispensers; TVs: `50S80EUX`).
  - *Acceptance Criteria:* Catalog files present and readable by pandas; test fixture verified.
  - *Verification:* `.venv\Scripts\python -c "import pandas as pd; df = pd.read_csv('Haier_Washing_Machines_Uploading_and_Price.csv'); print(f'Loaded {len(df)} Haier products')"`

- [x] **Task 1.2: Restore AlfaMall 50% Midpoint Adaptive Pricing**
  - In `pricing_engine/evaluator.py`:
    - Remove the `if max_profit_cap is not None else None` bypass on AlfaMall.
    - Set default `large_cap_alfa = max_profit_cap if max_profit_cap is not None else 10000.0`.
    - Add explicit audit reason string when Tier 2 50% split midpoint triggers.
  - In `tests/test_evaluator.py`: update expected price in `test_alfa_competitive_win_undercut` to Tier 2 midpoint (`81499`).
  - *Acceptance Criteria:* Large gap items on AlfaMall undercut to 50% split midpoint instead of hugging competitor by only Rs. 100.
  - *Verification:* `.venv\Scripts\pytest tests/test_evaluator.py -v`

- [x] **Task 1.3: Baseline Verification & Test Suite Checkpoint**
  - Run complete project test suite.
  - Run strict linter check.
  - *Acceptance Criteria:* All tests green; 0 linter warnings.
  - *Verification:* `.venv\Scripts\pytest -v` and `.venv\Scripts\ruff check .`

### Checkpoint: Phase 1 Complete
- [x] Catalogs integrated.
- [x] Evaluator 50% adaptive gap bug resolved on AlfaMall.
- [x] 100% tests green.

---

### Phase 2: High-Performance Multi-Pattern Waterfall Scraper

- [ ] **Task 2.1: Multi-Pattern Seed Query Generator (`pricing_engine/matcher.py`)**
  - Implement `generate_search_patterns(canonical_name: str, brand: str = "") -> dict[str, list[str]]`:
    - `tier_1`: Exact clean target SKU (`["120-826S6 GC", "50S80EUX"]`).
    - `tier_2`: Bare alphanumeric stem without cosmetic tags (`["120-826S6", "S80EUX"]`).
    - `tier_3`: Spaced, glued, and prefixed permutations (`["120 826S6", "50 S80EUX", "HWM-120-826S6"]`).
    - Appliance Series queries: `["MAGNA 30", "MAGNA 1.5 TON"]`.
  - Preserve variant codes strictly (e.g. `WB`, `GB` never stripped from query seeds).
  - *Acceptance Criteria:* Returns clean, ordered query tiers for TVs, Washing Machines, ACs, and Refrigerators.
  - *Verification:* `.venv\Scripts\pytest tests/test_matcher.py -k test_generate_search_patterns -v`

- [ ] **Task 2.2: Tiered Early-Exit Waterfall Scraper (`pricing_engine/scraper.py`)**
  - Upgrade `scrape_alfamall` and `scrape_digimall` to accept tiered query patterns.
  - Execute Tier 1 query first; if $\ge 2$ valid candidate offers returned, return immediately without calling Tier 2 or Tier 3.
  - Fallback to Tier 2 and Tier 3 only if $<2$ candidate offers discovered.
  - Integrate run-scoped cache `_query_cache[(platform, query)]` and UTF-8 Windows stdout protection.
  - *Acceptance Criteria:* Early exit stops redundant HTTP requests; deduplicated candidates merged cleanly.
  - *Verification:* `.venv\Scripts\pytest tests/test_scraper.py -v`

- [ ] **Task 2.3: Scraper Unit Tests & Performance Verification**
  - Add mock tests for early-exit waterfall (verify Tier 2 is not called when Tier 1 succeeds).
  - Add tests for fallback when Tier 1 returns 0 offers.
  - *Acceptance Criteria:* Test coverage for waterfall logic exceeds 90%.
  - *Verification:* `.venv\Scripts\pytest tests/test_scraper.py -v`

### Checkpoint: Phase 2 Complete
- [ ] Multi-pattern query generation verified.
- [ ] Tiered early-exit waterfall reduces network overhead by 80%.
- [ ] All scraper tests green.

---

### Phase 3: Token-Based Extraction & Negative-Collision Referee Matcher

- [ ] **Task 3.1: 4-Slot Attribute Extractor with Residual Subtraction (`pricing_engine/matcher.py`)**
  - Implement `extract_product_slots(title: str, brand: str = "") -> ProductSlots`:
    - `anchor`: Primary numeric or alphanumeric SKU run (`120-826S6`, `276EBS`, `DWT-1165`).
    - `series`: Extracted dynamically via CSV Metadata Subtraction (Zero Static Noise Dict):
      $$\text{Series} = \text{Title} - (\text{Brand Metadata} \cup \text{Category Metadata} \cup \text{Specs/Capacities} \cup \text{Colors})$$
      - Sub-series tokens (`PRO`, `+`, `X`, `CLASSIC`, `ELEGANT`) strictly preserved (`CHROME PRO` strictly requires `PRO`, `AVANTE CLASSIC` rejects `AVANTE ELEGANT`).
    - `guarded_facets`:
      - `t3`: True / False / None.
      - `capacity`: Extracted tonnage (`1.5T`), weight (`12KG`), or screen size (`50"`).
      - `tub_series`: Hardware variant codes (`WB` vs `GB`).
      - `color`: 9 normalized color families (White/Milky, Black/Dark, Grey/Silver/Metallic/Steel, Red/Maroon, Gold/Copper/Bronze, Brown/Wood, Blue, Green, Purple/Pink) + Suffix Codes (`W`, `B`, `S`, `G`, `R`, `P`).
    - `residuals`: Extra marketing/cosmetic tokens (`GC`, `Glass Door`, `Pillow Drum`).
  - *Acceptance Criteria:* Correctly factors titles into slots without hardcoded series dictionaries.
  - *Verification:* `.venv\Scripts\pytest tests/test_matcher.py -k test_extract_product_slots -v`

- [ ] **Task 3.2: Negative-Collision Referee Matcher (`pricing_engine/matcher.py`)**
  - Implement `referee_match(target_slots: ProductSlots, candidate_title: str) -> MatchDecision`:
    - Check 1: Anchor Model containment.
    - Check 2: Zero-Tolerance Collision Guards:
      - T3 mismatch (Non-T3 vs T3) $\rightarrow$ REJECT.
      - Capacity mismatch (12KG vs 10KG, 50" vs 43") $\rightarrow$ REJECT.
      - Color mismatch (White vs Black) $\rightarrow$ REJECT.
      - Hardware tub mismatch (`WB` vs `GB`) $\rightarrow$ REJECT.
    - Check 3: If Anchor matches and zero collisions found $\rightarrow$ ACCEPT.
  - Return human-readable decision reason.
  - *Acceptance Criteria:* Accurately matches identical units and strictly rejects variant collisions.
  - *Verification:* `.venv\Scripts\pytest tests/test_matcher.py -k test_referee_match -v`

- [ ] **Task 3.3: Comprehensive Cross-Category Test Suite (`tests/test_matcher.py`)**
  - Add test cases covering:
    - Haier Washing Machines (`120-826S6 GC` matches `120-826S6 Glass Door`; `80-1217WB` rejects `80-1217GB`).
    - Dawlance ACs (`MAGNA T3 30 MILKY` matches `MAGNA 1.5 TON T3` and rejects non-T3).
    - TVs (`50S80EUX` matches `50 S80EUX` and rejects `43S80EUX`).
    - Refrigerators (`276EBS SILVER` matches `276EBS` and rejects `276EPR RED`).
  - *Acceptance Criteria:* 100% of test cases pass with 0 regressions.
  - *Verification:* `.venv\Scripts\pytest tests/test_matcher.py -v`

### Checkpoint: Phase 3 Complete
- [ ] Zero series dictionaries required.
- [ ] Residual subtraction reliably extracts series names.
- [ ] Negative-collision referee guarantees variant safety.

---

### Phase 4: Autonomous Co-Occurrence Mining & Cloud Memory

- [ ] **Task 4.1: Supabase SQL Migration Script (`scripts/setup_supabase.sql`)**
  - Create idempotent SQL table definitions:
    - `capacity_registry`: `(brand, code, tonnage, status, occurrences, confidence)`.
    - `synonym_registry`: `(brand, category, anchor_model, tag, alias, occurrences, status)`.
    - `learning_observations`: Append-only market audit log.
    - Row-Level Security (RLS) policies and indexes.
  - *Acceptance Criteria:* Script runs cleanly in Supabase SQL editor.
  - *Verification:* Code inspection and test schema validation.

- [ ] **Task 4.2: Supabase Client & In-Memory Registry (`pricing_engine/db.py`, `pricing_engine/registry.py`)**
  - Implement async `SupabaseClient` with HTTPS REST API.
  - Implement in-memory cached registry with $<0.01$ms lookups.
  - Implement safe local fallback when offline or unconfigured.
  - *Acceptance Criteria:* Client handles online sync and offline graceful degradation.
  - *Verification:* `.venv\Scripts\pytest tests/test_db.py tests/test_registry.py -v`

- [ ] **Task 4.3: Autonomous Pattern Miner (`pricing_engine/learner.py`)**
  - Ingest residual pairs from accepted matches during scraping sweeps.
  - Enforce the $\ge 3$ distinct seller promotion gate.
  - Conflict quarantine for contradictory signals.
  - *Acceptance Criteria:* Accurately mines co-occurrences without human intervention.
  - *Verification:* `.venv\Scripts\pytest tests/test_learner.py -v`

### Checkpoint: Phase 4 Complete
- [ ] Autonomous knowledge persistence verified.
- [ ] Offline resilience active.

---

### Phase 5: End-to-End Catalog Stress Testing & CI/CD Quality Gates

- [ ] **Task 5.1: Multi-Catalog E2E Pricing Simulation**
  - Run full repricing simulation on:
    - 38 Haier Washing Machines (`Haier_Washing_Machines_Uploading_and_Price.csv`).
    - 42 Gree ACs (`Gree_Uploading_on_DigiMall_and_Price.csv`).
    - 50 sample items from `Stock Holding Report`.
  - Validate output CSVs for integer prices, positive margins, and justified reason strings.
  - *Acceptance Criteria:* 0 false monopolies, 0 variant collisions.
  - *Verification:* `.venv\Scripts\python -m pricing_engine.pipeline` simulation run.

- [ ] **Task 5.2: CI/CD Quality Gates Configuration (`.github/workflows/ci.yml`)**
  - Configure GitHub Actions workflow running:
    - Static analysis: `ruff check .`
    - Test suite with coverage: `pytest --cov=pricing_engine`
  - *Acceptance Criteria:* CI pipeline configured and passing.
  - *Verification:* `.venv\Scripts\ruff check .` and `.venv\Scripts\pytest -v`

- [ ] **Task 5.3: Production Verification & Release Tagging**
  - Ensure all documentation, ADRs, and task lists are 100% up to date.
  - Create release save-point commit following `git-workflow-and-versioning`.
  - *Acceptance Criteria:* Complete project is production-ready, clean, and tested.
  - *Verification:* `git status` clean, all tests green.
