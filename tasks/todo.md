# Task Breakdown: Unified Dynamic Glide Split (80% -> 50%)

- [x] **Task 1: Core Math Engine (`pricing_engine/calculator.py`)**
  - Implement dynamic linear interpolation formula for Tier 2: `retention_pct = 0.80 - ((gap - 2000.0) / 8000.0) * 0.30`
  - Update `test_adaptive_target_tier2_2000_to_10000_gap()` in `tests/test_calculator.py`
  - *Acceptance:* Gap 2k -> 80% (buffer 1600), Gap 5k -> 68.75% (buffer 3437.5), Gap 10k -> 50% (buffer 5000)

- [x] **Task 2: Evaluator Dynamic Telemetry (`pricing_engine/evaluator.py`)**
  - In `_evaluate_alfa_core`: compute dynamic `pct_str` and format reason: `Applied dynamic adaptive split ({pct_str}) to capped winning psychological price...`
  - In `_evaluate_digi_core`: apply dynamic `pct_str` across Step A (10% Tier), Step B (Emergency 8% Switch), and Step C (Upper Band 10% & 8%)
  - *Acceptance:* Exact percentage (e.g. 76%, 69%, 58%) rendered in reason string for both platforms

- [x] **Task 3: Pipeline & Badging Consistency (`pricing_engine/pipeline.py`)**
  - Verify `determine_platform_status()` tags `CAPPED (-diff)` on market wins with dynamic adaptive split
  - Verify `build_platform_decision_table()` renders `(CAPPED SWEET-SPOT)` and `(CAPPED SWEET-SPOT (8% RATE))`
  - *Acceptance:* Terminal audit cards display bold yellow `(CAPPED SWEET-SPOT)`

- [x] **Task 4: Automated Testing & Quality Gates**
  - Update existing test assertions in `tests/test_evaluator.py` and `tests/test_pipeline.py`
  - Run `pytest` (100% green, 376 passed)
  - Run `ruff check .` (0 errors)
  - Run `mypy pricing_engine index.py` (0 errors)
