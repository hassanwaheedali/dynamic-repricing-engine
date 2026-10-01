# Task List: 3-Tier Multi-Pattern Search & Robust Unified Referee Engine

## Phase 1: Exhaustive 3-Tier Pattern Generation & Waterfall Search
- [x] Task 1.1: Remove premature early-exit (`break` on $\ge 2$ offers) in `pricing_engine/scraper.py:_execute_waterfall` to allow all tiers to query and pool.
- [x] Task 1.2: Upgrade `generate_search_patterns()` in `pricing_engine/matcher.py` to decouple glued SKU codes (e.g. `DWT11467ES` -> `DWT-11467`, `11467 ES`, `11467`).
- [x] Task 1.3: Ensure unified deduplication in `scraper.py` by `(vendor_name.lower(), round(price, 2))`.

## Phase 2: Title Normalization & Merchant Noise Cleansing
- [x] Task 2.1: Add marketplace noise cleaner for seller names (`ElectroEase`, `HomeCart`, `ISPK-\d+`, `SNS\d+`, `ET`, `UE\d+`) and promo phrases (`On Installment`, `Free Delivery`, `Special Gift`).
- [x] Task 2.2: Isolate operational descriptors (`Heat & Cool`, `DC Inverter`) so they don't pollute the extracted Series slot.
- [x] Task 2.3: Clean parentheses, brackets, and normalize slashes in `extract_product_slots()` so `(Milky White Textured)` maps cleanly to facets.

## Phase 3: Dynamic Initialisms & Slash-Separated Series Support
- [x] Task 3.1: Support slash-separated series names (`Sprinter / Powercon`) with OR logic in `referee_match()`.
- [x] Task 3.2: Verify and enhance dynamic initialism referee (`SD` $\iff$ `Single Door`, `DD` $\iff$ `Double Door`, `FL` $\iff$ `Front Load`, `TL` $\iff$ `Top Load`).

## Phase 4: Strict Guarded Facets & Color Optionality Enforcement
- [x] Task 4.1: Enforce strict T3 compressor guard in `referee_match()`.
- [x] Task 4.2: Enforce IoT smart appliance guard in `referee_match()` (reject basic model against IoT inverter).
- [x] Task 4.3: Implement Color Optionality Rule: Reject conflicting color families; accept unmentioned color when model matches.
- [x] Task 4.4: Enforce Hardware Tub guard (`WB` vs `GB`).

## Phase 5: Verification & Benchmark Suite
- [x] Task 5.1: Create test suite in `tests/test_dawlance_benchmark.py` covering the 38 benchmark Dawlance models.
- [x] Task 5.2: Run full regression test suite (`pytest`) to ensure 100% green pass.
- [x] Task 5.3: Verify end-to-end pipeline run with rich terminal output and pure integer exports.
