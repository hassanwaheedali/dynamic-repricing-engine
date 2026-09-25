# Tasks Checklist: Universal Brand-Agnostic Model Matching Engine

- [x] **Task 1: Brand-Agnostic Model & Search Token Extractor (`pricing_engine/matcher.py`)**
  - Accept optional `brand: str = ""` in `extract_search_query_and_model`.
  - Strip brand names dynamically using catalog metadata.
  - Preserve multi-token SKU codes (`DWT-1165 PL`, `100-316S6 GC`) while cleanly stripping marketing color fluff (`MYSTIC GREY`, `CLOUD WHITE`, `EMERALD GREEN`).
  - *Acceptance Criteria:* Clean SKUs for Dawlance (`DWT-1165 PL`), Haier (`100-1269 S6`), Kenwood (`KCT-1801H`), Homage (`HDG-201S`), Gree (`24AITH21B-T3`).
  - *Verification:* `pytest tests/test_matcher.py` (Passed).

- [x] **Task 2: Universal Structural Token-Run Distributive Expander (`pricing_engine/matcher.py`)**
  - Implemented typed structural run tokenizer (`digits`, `letters`, `punctuation`).
  - Solved missing hyphen in compound suffixes (`GS-24AITH21W-T3/21B-T3` -> `GS-24AITH21W-T3` & `GS-24AITH21B-T3`).
  - Solved dead-code trailing tags by backward and forward propagation of tags (`-T3`, `AAA`, `PRO`).
  - Solved asymmetric-length variants (`15/17G`, `24W/S-T3`, `DWT-1165/1167 PL`).
  - Safeguarded category acronyms (`W/M`, `D/F`, `Heat / Cool`, `12W/8D`).
  - *Verification:* `pytest tests/test_matcher.py` (Passed).

- [x] **Task 3: Universal Strict Model Matcher with Zero Hardcoded Lists (`pricing_engine/matcher.py`)**
  - Replaced hardcoded capacity list `(12, 18, 24...)` with dynamic structural token slot collision check.
  - Replaced hardcoded color list with token slot collision and multi-token canonical containment.
  - Enforced exact canonical containment on expanded listings.
  - *Verification:* `pytest tests/test_matcher.py` (Passed).

- [x] **Task 4: Comprehensive Multi-Brand Test Suite (`tests/test_matcher.py`)**
  - Added unit test for `GS-24AITH21W-T3/21B-T3` matching `24AITH21B-T3` (Electronics World win).
  - Added unit tests for Dawlance, Haier, Kenwood, Homage, Midea from `MainSheet.csv`.
  - Added non-model safeguard tests.
  - *Verification:* 18 tests in `tests/test_matcher.py` 100% green.

- [x] **Task 5: Quality Gate & Validation**
  - Full project test suite: `pytest` (78 tests green).
  - Linter: `ruff check .` (0 errors).
  - Awaiting user review before any Git commit.
