# Tasks: Sweet-Spot Profit Capping with 10% Default Tier Integrity

- [x] **Task 1: Update `pricing_engine/evaluator.py` Sweet-Spot Math**
  - Implemented `calculate_adaptive_target_price` in `pricing_engine/calculator.py`
  - Integrated into `pricing_engine/evaluator.py`
  - Keep commission strictly as `"10.00%"` and status as `"Safe Win (10% Tier)"`
  - Update reason description to clearly state sweet-spot capping for sales volume

- [x] **Task 2: Add TDD Unit Tests in `tests/test_evaluator.py`**
  - Tested Item #1 with Scroll-N-Shop (489,999) prices at `478,899` (+Rs. 10,296 profit)
  - Verified commission remains `"10.00%"`
  - Verified Item #2 remains `"8.00% Emergency Switch"` at `165,899` (+Rs. 1,649 profit)

- [x] **Task 3: Update `tests/test_pipeline.py` & Full Test Suite**
  - Updated pipeline tests with sweet spot target
  - Ran `pytest -v` across all test suites (41/41 passing)
  - Ran `ruff check .` for code cleanliness (All checks passed)

- [x] **Task 4: Terminal Audit Verification**
  - Executed simulation to verify visual card for Item #1 and Item #2
  - Verified Item #1 displays `Target Undercut (10% Viable)`, `10.00% Default Tier`, `Rs. 478,899`, `+Rs. 10,296`

- [x] **Task 5: Complete 5-Tier Dynamic Gap Pricing Ladder**
  - Updated `calculate_adaptive_target_price` in `pricing_engine/calculator.py` with user-defined tiers:
    - Tier 5 (Gap < Rs. 800): Closest Rs. 100 undercut (strict floor guarantee).
    - Tier 4 (Gap Rs. 800 - 1,499): Rs. 200 undercut (visible discount).
    - Tier 3 (Gap Rs. 1,500 - 1,999): Rs. 500 customer discount, min Rs. 1,000 profit buffer.
    - Tier 2 (Gap Rs. 2,000 - 9,999): 50% half average.
    - Tier 1 (Gap >= Rs. 10,000): Option A sweet-spot profit cap (~Rs. 10,000).
  - All 42 unit tests passing (`pytest -v`).
  - Code passes strict linter (`ruff check .`).

