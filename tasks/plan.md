# Implementation Plan: Consistent Viable Winning & Capping Status Engine

## Overview
Standardize `determine_platform_status()` and `determine_5pct_goal_status()` in `pricing_engine/pipeline.py` according to global enterprise repricing standards. Filtered sub-floor outliers (junk, installments, accessories) are excluded, and undercutting the lowest viable competitor is consistently recognized as a viable market win. Eliminates the word `UNCOMPETITIVE` entirely.

## Architecture Decisions
- **Zero "UNCOMPETITIVE" Labels**: Status remains clean: `CAPPED`, `WIN`, `SOLO`, `FALLBACK`.
- **Viable Win Consistency**: Both capped undercuts (`CAPPED`) and standard undercuts (`WIN`) against viable competitors are consistently recognized as winners.
- **Goal Stability**: When profit >= target profit (Rs. 526), both `CAPPED` and `WIN` earn `WIN + 5% ACHIEVED` and enter the 5% winning export.

## Task List

### Phase 1: Status Engine Refactoring
- [ ] Task 1.1: Refactor `determine_platform_status()` in `pricing_engine/pipeline.py` to consistently return `CAPPED` or `WIN` for viable competitor undercuts.
- [ ] Task 1.2: Verify `determine_5pct_goal_status()` in `pricing_engine/pipeline.py` handles both pure and viable winning badges cleanly without uncompetitive labels.

### Phase 2: Automated Testing
- [ ] Task 2.1: Add unit tests in `tests/test_pipeline.py` for viable competitor undercuts (both capped and uncapped).
- [ ] Task 2.2: Verify `tests/test_personal_commission.py` passes all assertions.

### Phase 3: Quality Gates
- [ ] Task 3.1: Run `pytest -v`.
- [ ] Task 3.2: Run `ruff check .` and `mypy pricing_engine index.py`.
