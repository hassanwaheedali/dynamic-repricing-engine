# Task Breakdown: Item #28 Matcher Architecture & 5-Case Variant Polish

- [x] **Task 1: Pre-Processing Sanitizer (Noise & Seller Codes) with Capacity Guard**
  - Clean parenthetical payment terms (`0% Markup`, `Installment`, `EMI`, `Down Payment`)
  - Clean trailing seller codes after hyphens/delimiters (`- ET`, `- Telemart`)
  - **Spec & Capacity Guard**: Ensure `- 8 kg`, `- 8.5 KG`, `- 10KG`, `- 1.5 TON`, `- 300L` are NEVER stripped
  - Clean standalone dashes in post-words loop
  - *Acceptance:* `c2` produces `capabilities=set()`, `residuals=[]` with zero fake `ET` capability; `- 8 kg` retains `capacity='8KG'`

- [x] **Task 2: Strict Brand Matching & Dynamic Prefix Initial Verification**
  - Zero-tolerance brand collision against all competing brands
  - Dynamic brand-initial prefix check: `{brand[0]}` (e.g. `D` for Dawlance, `H` for Haier)
  - Reject candidate if prefix initial conflicts with target brand
  - *Acceptance:* Cross-brand candidates rejected immediately with `Brand collision`

- [x] **Task 3: Generic Case B Anchor Extraction**
  - Update `Case B` in `extract_search_query_and_model()` to match `\d{1,6}([A-Za-z]{1,3})?`
  - Canonicalize `DWT 255C` -> `DWT-255-C`, `DW 255C` -> `DW-255-C`
  - *Acceptance:* Prefix `DWT`/`DW` is preserved, anchor becomes `DWT-255-C`

- [x] **Task 4: 5-Case Single-Letter Variant Referee**
  - Implement generic `_extract_stem_single_letter_variant()` using `COLOR_SUFFIX_MAP`
  - Implement 5-case decision logic in `referee_match()`
  - *Acceptance:* All 5 cases (exact, base fallback, variant omission, collision) match expected verdicts

- [x] **Task 5: Unit Tests & Regression Verification**
  - Add `test_dawlance_dwt255_item28_matching_and_5_cases()` in `tests/test_matcher.py`
  - Test `- 8 kg` / `- 8.5 KG` edge cases in unit test
  - Test strict brand rejection (e.g. `PEL` or `Haier` against Dawlance target)
  - Verify `test_deep_freezer_df300_es_matching()` remains passing (ET protection preserved)
  - Run full benchmark tests: Gree, Haier, Dawlance
  - Run `ruff check .`
