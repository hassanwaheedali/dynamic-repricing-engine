# Task Breakdown & Checklist (`tasks/todo.md`)

## Task 1: Create `config.py` and TDD Test Suite (`tests/test_config.py`)

**Description:** Create the root `config.py` module containing all platform bank commissions, personal commission percentages (default + per-platform Alfa/Digi), profit targets, and shipping constants, backed by a dedicated pytest suite.

**Acceptance criteria:**
- [ ] `config.py` defines `ALFA_COMMISSION_PCT`, `DIGI_STANDARD_COMMISSION_PCT`, `DIGI_LEVERAGE_COMMISSION_PCT`, `DEFAULT_PERSONAL_COMM_PCT`, `ALFA_PERSONAL_COMM_PCT`, `DIGI_PERSONAL_COMM_PCT`, `COMPANY_MIN_PROFIT_PKR`, `MONOPOLY_PROFIT_PKR`, `FALLBACK_PROFIT_PKR`, `LARGE_GAP_PROFIT_CAP_PKR`, `THIN_BUFFER_THRESHOLD_PKR`, `COURIER_RATE_PER_KG`, and `VOLUMETRIC_DIVISOR`.
- [ ] Helper functions compute exact payout multipliers (`1.0 - pct / 100.0`).

**Verification:**
- [ ] Tests pass: `pytest tests/test_config.py -v`
- [ ] Lint clean: `ruff check config.py tests/test_config.py`

**Dependencies:** None

**Files likely touched:**
- `config.py`
- `tests/test_config.py`

**Estimated scope:** Small (2 files)

---

## Task 2: Wire `calculator.py` and `models.py` to `config.py`

**Description:** Connect `calculate_volumetric_weight`, `calculate_shipping_estimate`, `calculate_personal_commission`, `calculate_floors`, and `calculate_baseline` to `config.py` defaults, and support separate Alfa/Digi personal commissions in `CostFloors`.

**Acceptance criteria:**
- [ ] Changing `COURIER_RATE_PER_KG`, `COMPANY_MIN_PROFIT_PKR`, `ALFA_COMMISSION_PCT`, or `DIGI_LEVERAGE_COMMISSION_PCT` in `config` dynamically updates `calculate_floors` and `calculate_shipping_estimate`.
- [ ] `CostFloors` supports `alfa_personal_comm` and `digi_personal_comm` (with `personal_comm` retained).

**Verification:**
- [ ] Tests pass: `pytest tests/test_config.py tests/test_calculator.py -v`
- [ ] Lint clean: `ruff check pricing_engine/calculator.py pricing_engine/models.py`

**Dependencies:** Task 1

**Files likely touched:**
- `pricing_engine/models.py`
- `pricing_engine/calculator.py`
- `tests/test_config.py`

**Estimated scope:** Small (3 files)

---

## Checkpoint: After Tasks 1-2
- [ ] Foundation tests pass (`pytest tests/test_config.py tests/test_calculator.py -v`)
- [ ] `ruff check .` passes

---

## Task 3: Wire `evaluator.py` to `config.py`

**Description:** Update `pricing_engine/evaluator.py` to source `FALLBACK_PROFIT`, `monopoly_profit`, `LARGE_GAP_PROFIT_CAP_PKR`, and platform commission payout rates from `config.py`, and use `cost_floors.alfa_personal_comm` / `cost_floors.digi_personal_comm`.

**Acceptance criteria:**
- [ ] `evaluate_alfa_pricing` and `evaluate_digi_pricing` respect `config.py` settings and platform-specific personal commission floors.

**Verification:**
- [ ] Tests pass: `pytest tests/test_evaluator.py tests/test_config.py -v`
- [ ] Lint clean: `ruff check pricing_engine/evaluator.py`

**Dependencies:** Task 2

**Files likely touched:**
- `pricing_engine/evaluator.py`
- `tests/test_config.py`

**Estimated scope:** Small (2 files)

---

## Task 4: Wire `pipeline.py`, `exporter.py`, and `index.py` to `config.py`

**Description:** Connect `pipeline.py`, `exporter.py`, and `index.py` so CLI `--5pct` / interactive mode `[3]`, Excel formulas, and profit breakdown columns read their default percentages and profit floors from `config.py`.

**Acceptance criteria:**
- [ ] `--5pct` and interactive mode `[3]` use `config.DEFAULT_PERSONAL_COMM_PCT`, `config.ALFA_PERSONAL_COMM_PCT`, and `config.DIGI_PERSONAL_COMM_PCT`.
- [ ] `determine_risk_alert` uses `config.THIN_BUFFER_THRESHOLD_PKR`.
- [ ] Full test suite passes (`pytest -q`).

**Verification:**
- [ ] Tests pass: `pytest -q`
- [ ] Lint clean: `ruff check .`

**Dependencies:** Task 3

**Files likely touched:**
- `pricing_engine/pipeline.py`
- `pricing_engine/exporter.py`
- `index.py`
- `tests/test_config.py`

**Estimated scope:** Medium (4 files)
