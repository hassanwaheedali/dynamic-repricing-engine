# Tasks: Dual-Variant Slash Matching & Scraper Pacing Guard

- [x] **Task 1: Implement `expand_multivariant_titles` in `pricing_engine/matcher.py`**
  - Add color slash regex with hyphen, space, Champagne `[WBSGC]`, and trailing suffixes (`-T3`, ` T3`): `\b([0-9]{2}[A-Z0-9]+?)[-\s]*([WBSGC])\s*/\s*([WBSGC])((?:[-_\s]+[A-Z0-9]+)?)\b`
  - Add identical batch Pular series regex (`14S / 11S`): `\b([0-9]{2}PITH)[-\s]*(14|11)[-\s]*([WBSGC])\s*/\s*(14|11)[-\s]*([WBSGC])\b`
  - Explicitly prohibit single-digit `\d{1}` matching to prevent cross-generation mixing (`ZITH1` vs `ZITH2`) and pipe fractions (`1/2"`)
  - Pass `scraped_title` through `expand_multivariant_titles` before clean string extraction in `is_strict_model_match`
  - Guarantee positive exact match priority (`if base_target in clean_title: return True` executes before any fallback)
  - *Acceptance Criteria:* `GS-12AITH24-W/S`, `GS-12AITH24W/S-T3` expand properly; matches `12AITH24S` and `12AITH24W`; rejects `12AITH24B`; `ZITH1W` and `ZITH2W` remain 100% isolated
  - *Verification:* `pytest tests/test_matcher.py`
  - *Dependencies:* None

- [x] **Task 2: Add Comprehensive Unit Tests in `tests/test_matcher.py`**
  - Test dual color slash matching: `GS-12AITH24W/S` matches `12AITH24S-T3` and `12AITH24W-T3`
  - Test hyphenated syntax: `GS-12AITH24-W/S` and `GS-12AITH24 - W/S` match `12AITH24S-T3`
  - Test trailing suffixes: `GS-12AITH24W/S-T3` and `GS-12AITH24W/S T3` match `12AITH24S-T3`
  - Test extended color `C`: `12AITH24W/C` matches `12AITH24W` and `12AITH24C`
  - Test generation isolation: `GS-12ZITH1W` strictly does NOT match `GS-12ZITH2W`
  - Test color collision guard: `GS-12AITH24W/S` rejects `12AITH24B-T3`
  - Test single-color isolation: pure `GS-12AITH24W` rejects `12AITH24S-T3`
  - *Acceptance Criteria:* All test cases pass 100% green
  - *Verification:* `pytest tests/test_matcher.py`
  - *Dependencies:* Task 1

- [x] **Task 3: Add Scraper Gentle Pacing & Randomized Jitter Timeout Backoff**
  - In `pricing_engine/pipeline.py`, increase task dispatch micro-stagger from `0.2s` to `0.4s`
  - In `pricing_engine/scraper.py`, catch broad timeout errors (`curl: (28)`, `timed out`, `timeout`, `asyncio.TimeoutError`)
  - Apply randomized jitter backoff `random.uniform(3.5, 5.0) + (attempt * 1.5)` to break parallel worker synchronization
  - *Acceptance Criteria:* Rapid consecutive runs do not trigger AlfaMall WAF packet drops or synchronized burst waves
  - *Verification:* `pytest tests/test_pipeline.py`
  - *Dependencies:* None

- [x] **Task 4: Add Integration Test for Item #3 DigiMall Repricing in `tests/test_pipeline.py`**
  - Mock DigiMall scrape response with `GS-12AITH24W/S` at `193,999`
  - Verify engine undercuts to `192,899` (.899 ending via Adaptive Gap Pricing) with `8.00%` rate and `+1,489` profit
  - *Acceptance Criteria:* Confirms Item #3 wins the buy box instead of falling back to Monopoly baseline
  - *Verification:* `pytest tests/test_pipeline.py`
  - *Dependencies:* Task 1 to Task 3

- [x] **Task 5: Quality Gate Run, Live Benchmark & User Approval**
  - Run full test suite: `pytest -v`
  - Run linter: `ruff check .`
  - Run live benchmark: `python index.py`
  - Present changes and verification to user; ask for explicit confirmation before committing to Git!
  - *Acceptance Criteria:* 100% green test suite, zero linter warnings, successful live run
  - *Verification:* `python index.py`
  - *Dependencies:* Task 1 to Task 4

- [x] **Task 6: Pular Multi-Batch Shared Color Slashes & Item #22 Repricing Win**
  - Added `p_batch_shared` regex in `pricing_engine/matcher.py`: `\b([0-9]{2}PITH)[-\s]*((?:\d{2}\s*/\s*)+\d{2})\s*([WBSGC])((?:[-_\s]+[A-Z0-9]+)?)\b`
  - Corrected color collision check to inspect `expanded_title` to prevent Grey from matching White
  - Added unit test `test_strict_model_match_pular_shared_color_batch_slashes` in `tests/test_matcher.py`
  - Added integration test `test_item_22_pular_batch_slash_digimall_reprice_win` in `tests/test_pipeline.py`
  - Verified Item #22 undercuts Tech House (Rs. 247,999) to Rs. 247,799 (+Rs. 1,119 net profit) on DigiMall
  - Preserved 100% isolation of ZITH1 vs ZITH2

