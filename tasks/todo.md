# Tasks: Commercial Traffic-Light Risk Alerts & Telemetry

- [x] **Task 1: Add `determine_risk_alert` & Extend Output Schema in `pricing_engine/pipeline.py`**
  - Implement `determine_risk_alert(res: PlatformPricingResult) -> str` supporting priority order: `SERVER_DOWN` -> `SAFE_FALLBACK` -> `THIN_BUFFER` -> `NONE`
  - Append `"Alfa Risk Alert"` and `"Digi Risk Alert"` to `build_output_record` at the end of the schema
  - *Acceptance Criteria:* Risk alert strings cleanly populated without fragile string parsing; backward compatibility preserved
  - *Verification:* `pytest tests/test_pipeline.py`
  - *Dependencies:* None

- [x] **Task 2: Update Audit Card with Detailed Risk Badges in `pricing_engine/pipeline.py`**
  - In `render_audit_card`, display detailed visual markers:
    - Safe Fallback: `[bold red]Rs. 211,999 (SAFE FALLBACK - UNCOMPETITIVE)[/]`
    - Thin Profit (< 700): `[bold red]+Rs. 502 (THIN BUFFER - VOLUMETRIC RISK)[/]`
    - Capped Price: `[bold yellow]Rs. 478,999 (CAPPED SWEET-SPOT)[/]`
    - Server Down: `[bold red][SERVER DOWN - RETRY LATER][/]`
  - *Acceptance Criteria:* Full audit cards clearly inform merchants about courier weight and uncompetitive price risks
  - *Verification:* `pytest tests/test_pipeline.py`
  - *Dependencies:* Task 1

- [x] **Task 3: Implement Zero-Width Cell Styling & Legend in `render_summary_table`**
  - In `pricing_engine/pipeline.py`, implement cell formatters:
    - `format_table_price`: Red for Safe Fallback, White for normal win, dim red for DOWN
    - `format_table_profit`: Null-safe! `None` -> `DOWN`, `<= 0` -> `[bold white on red]`, `< 700` -> `[bold red]`, `>= 700` -> `[bold green]`
    - `format_table_rate`: Yellow for `8.00%` switch, dim white for `10.00%`
  - Print 1-line Rich Legend below the table:
    `🔴 RED: Safe Fallback (Market Dumping) / Thin Profit (< Rs. 700) | 🟡 YELLOW: 8% Bank Switch | 🟢 GREEN: Healthy Win (≥ Rs. 700)`
  - *Acceptance Criteria:* Terminal table borders remain 100% straight and aligned without text wrapping
  - *Verification:* `pytest tests/test_pipeline.py`
  - *Dependencies:* Task 1, Task 2

- [x] **Task 4: Add Unit Test Suite in `tests/test_pipeline.py`**
  - Test `determine_risk_alert` with all 4 states (`SERVER_DOWN`, `SAFE_FALLBACK`, `THIN_BUFFER`, `NONE`)
  - Test `build_output_record` verifies `Alfa Risk Alert` and `Digi Risk Alert` columns
  - Test CSV export verifies pure integer prices (no `.0`), clean risk alert text, and zero Rich/ANSI tags in CSV file
  - Test `render_summary_table` and `render_audit_card` execute cleanly with mixed risk inputs without raising `TypeError`
  - *Acceptance Criteria:* Full test suite passes 100% green (`pytest -v`), 0 linter errors (`ruff check .`)
  - *Verification:* `pytest -v && ruff check .`
  - *Dependencies:* Task 1 to Task 3

- [x] **Task 5: Live Production Benchmark Verification**
  - Execute `python index.py` on all 25 live Gree AC catalog items
  - Visually inspect terminal cards and executive summary table for clean alignment and proper color assignment
  - Inspect output CSV file to ensure clean risk alert columns and zero float drift
  - *Acceptance Criteria:* Full execution completes under 7 seconds with zero regressions
  - *Verification:* `python index.py`
  - *Dependencies:* Task 4

