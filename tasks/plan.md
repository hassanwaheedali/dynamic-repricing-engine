# Implementation Plan: Centralized Pricing & Commission Configuration (`config.py`)

## Overview
Extract all hardcoded marketplace commissions, personal commission percentages, profit floors, and courier logistics constants from `calculator.py`, `evaluator.py`, `exporter.py`, `pipeline.py`, and `index.py` into a single, human-editable root configuration module (`config.py`). This enables changing AlfaMall and DigiMall bank commissions, personal commission rates (global or per-platform), profit targets, and shipping rates from one place while maintaining 100% backward compatibility with all existing tests and CLI flags.

## RIPER Phase Summary
1. **Research (Complete):** Audited `calculator.py`, `evaluator.py`, `exporter.py`, `pipeline.py`, `models.py`, and `index.py` to catalog every hardcoded pricing constant (`0.90`, `0.92`, `500.0`, `5.0`, `70.0`, `5000.0`, `4000.0`, `1500.0`, `10000.0`, `700`).
2. **Innovate (Complete):** Evaluated 3 approaches:
   - *Approach A:* JSON/YAML config file with runtime file I/O on every call (Rejected: unnecessary I/O overhead in hot loops).
   - *Approach B:* Root `config.py` with top-level human-editable constants + a typed `PricingConfig` helper dataclass (Selected: zero I/O overhead, IDE autocomplete, type-safe, obeys `AGENTS.md` Single Source of Truth).
   - *Approach C:* `.env` environment variables only (Rejected: less discoverable for quick local tuning).
3. **Plan:** Vertical task breakdown below.

## Architecture Decisions
- **Single Source of Truth (`config.py`):** Placed in project root (`D:\Pricing Script\config.py`) for immediate user access, with typed constants and payout rate helpers (`alfa_payout_rate()`, `digi_standard_payout_rate()`, `digi_leverage_payout_rate()`).
- **Per-Platform Personal Commission Support:** `config.py` exposes `DEFAULT_PERSONAL_COMM_PCT = 5.0` as well as platform-specific `ALFA_PERSONAL_COMM_PCT = 5.0` and `DIGI_PERSONAL_COMM_PCT = 5.0`. `CostFloors` tracks both `alfa_personal_comm` and `digi_personal_comm` (keeping `personal_comm` as the primary property/field for backward compatibility).
- **Zero Breaking Changes:** Default values in `config.py` match existing production constants (`10.0%` Alfa, `10.0% / 8.0%` Digi, `5.0%` personal commission, `Rs. 500` company floor, `Rs. 70/kg` courier rate).

## Task List

### Phase 1: Foundation (`config.py` + `models.py` + Unit Tests)
- [ ] **Task 1:** Create root `config.py` with typed constants and `tests/test_config.py` (TDD Red -> Green).
- [ ] **Task 2:** Wire `pricing_engine/calculator.py` and `pricing_engine/models.py` to use `config.py` constants and support per-platform personal commission rates.

### Checkpoint: Foundation
- [ ] `pytest tests/test_config.py tests/test_calculator.py` passes, `ruff check .` clean.

### Phase 2: Core Engine Integration (`evaluator.py`, `pipeline.py`, `exporter.py`, `index.py`)
- [ ] **Task 3:** Wire `pricing_engine/evaluator.py` to read monopoly profit, fallback profit, large-gap profit cap, and payout rates from `config.py`.
- [ ] **Task 4:** Wire `pricing_engine/pipeline.py`, `pricing_engine/exporter.py`, and `index.py` to use `config.py` defaults for personal commission, company floor, and thin-buffer risk alerts.

### Checkpoint: Complete
- [ ] Full test suite (`pytest -q`) and linter (`ruff check .`) pass with 0 errors.

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Mutating `config.py` constants in tests could leak state | Med | Use `unittest.mock.patch` in `tests/test_config.py` when testing custom config overrides |
| Existing 286 tests expect exact default numbers | High | Keep default values in `config.py` identical to current production constants |
