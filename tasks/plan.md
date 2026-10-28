# Implementation Plan: Unified Dynamic Glide Split (80% -> 50%)

## Overview
Upgrade the adaptive pricing Tier 2 algorithm ($2,000 \le \text{Gap} < 10,000$ PKR) from a flat 50% split midpoint to a **Unified Dynamic Glide Split**. 
On smaller gaps (Rs. 2,000 – Rs. 4,000), the merchant retains up to 80% of the surplus margin while offering a compelling customer discount (20%). As the competitor gap widens up to Rs. 10,000, the formula smoothly glides down to 50%, seamlessly transitioning into Tier 1 (~Rs. 10,000 profit cap).

## Architecture Decisions
- **Formula**: $\text{Retention \%} = 0.80 - \left(\frac{\text{Gap} - 2000}{8000}\right) \times 0.30$.
- **Buffer**: $\text{Buffer} = \max(\text{Gap} \times \text{Retention \%},\, 1000.0)$.
- **Strict Monotonicity**: Target ceiling strictly increases with competitor price; zero price cliffs.
- **Dynamic Telemetry**: Strategy reason logs exact dynamic split percentage: `Applied dynamic adaptive split (XX%) to capped winning psychological price...`.

## Task List

### Phase 1: Core Math Engine
- [ ] Task 1.1: Update `calculate_adaptive_target_price()` in `pricing_engine/calculator.py` with Unified Dynamic Glide formula.
- [ ] Task 1.2: Update unit test `test_adaptive_target_tier2_2000_to_10000_gap()` in `tests/test_calculator.py`.

### Phase 2: Evaluator & Strategy Reasons
- [ ] Task 2.1: Update `_evaluate_alfa_core()` in `pricing_engine/evaluator.py` to format dynamic split percentage.
- [ ] Task 2.2: Update `_evaluate_digi_core()` in `pricing_engine/evaluator.py` across Step A, Step B, and Step C.
- [ ] Task 2.3: Update evaluator assertions in `tests/test_evaluator.py`.

### Phase 3: Pipeline & Badging Telemetry
- [ ] Task 3.1: Update `determine_platform_status()` and `build_platform_decision_table()` in `pricing_engine/pipeline.py`.
- [ ] Task 3.2: Update pipeline badging tests in `tests/test_pipeline.py`.

### Phase 4: Quality Gates & Verification
- [ ] Task 4.1: Run `pytest` (must be 100% green, 376+ passing).
- [ ] Task 4.2: Run `ruff check .` (0 errors).
- [ ] Task 4.3: Run `mypy pricing_engine index.py` (0 type issues).
