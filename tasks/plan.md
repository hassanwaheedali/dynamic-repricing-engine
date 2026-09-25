# Technical Implementation Plan: Commercial Traffic-Light Risk Alerts & Telemetry

## 1. Executive Summary & Retail Objectives

In Pakistani e-commerce (AlfaMall and DigiMall / Faysal Bank), a dynamic repricing engine must not only compute mathematically optimal prices, but also visually alert management and warehouse operations to **two major commercial risks**:

1. **🔴 Safe Fallback (Market Dumping / Zero Sales Velocity):**
   - When competitors sell below our landed cost floor, the engine avoids a cash loss by listing at Safe Fallback (Floor + Rs. 1,000 margin).
   - *Commercial Reality:* The profit (+Rs. 1,950) is safe, but our price is higher than competitors (e.g. Afzal Corp at Rs. 201,500 vs Us at Rs. 211,999). Sales velocity will be zero.
   - *Visual Alert:* Price highlighted in **RED** (`211,999`) to alert the merchant to negotiate better purchase rates with suppliers.

2. **🔴 Razor-Thin Courier Volumetric Buffer (Profit < Rs. 700):**
   - When real net profit is near the hard floor (+Rs. 502 / +Rs. 512), courier volumetric re-weighing (Rs. 70/KG + packaging bubble wrap / carton bump of 2-3 KG = Rs. 250 - Rs. 350 extra cost) can wipe out the entire profit or turn the sale into a negative cash loss.
   - *Operational Alert:* Profit highlighted in **RED** (`+502`) so warehouse dispatchers ensure precise packaging.

3. **🟡 Emergency 8% Bank Switch (DigiMall):**
   - When 10% standard tier is unviable, the engine switches to the 8% bank rate to win the deal, waiving the 2% bank spread profit.
   - *Visual Alert:* Rate highlighted in **YELLOW** (`8.00%`).

4. **🟢 Optimal Winning & Monopoly:**
   - Normal winning deals with healthy margins ($\ge$ Rs. 700) and legitimate Monopoly wins (+Rs. 4,000) stay clean **GREEN**.

---

## 2. Architecture & Design Principles

### Principle 1: Zero-Width ANSI Formatting (No Table Broken Borders)
- Rich ANSI color tags (`[bold red]...[/]`, `[bold green]...[/]`) have zero terminal display width.
- In `render_summary_table`, cells only change **color**—never append long text tags like `(FALLBACK)` or `(THIN)` inside table cells.
- Numbers remain formatted as fixed-width strings (`{price:10,.0f}`, `{profit:+8,.0f}`). Table borders stay 100% straight and aligned across all 80–120 column terminals.
- A clean, 1-line **Legend** is rendered below the table.

### Principle 2: Complete Platform Asymmetric Decoupling
- AlfaMall and DigiMall evaluate risks independently:
  - **Item #5 Example:**
    - AlfaMall: Price is **RED** (`211,999` - Safe Fallback), Profit is **GREEN** (`+1,950` - Safe).
    - DigiMall: Price is **WHITE** (`205,899` - Winning), Profit is **RED** (`+578` - Thin Buffer).

### Principle 3: Type Safety & Defensive Null Guards (No NoneType Crash)
- If a portal is unreachable or server down, `real_profit` is `None` or `0`.
- Python cannot compare `None < 700` (`TypeError`).
- Explicit null-guard order:
  ```python
  if status == "Server Down / Unreachable" or real_profit is None:
      return "[dim red]   DOWN [/]"
  elif real_profit <= 0:
      return f"[bold white on red]{real_profit:+8,.0f}[/]"
  elif real_profit < 700:
      return f"[bold red]{real_profit:+8,.0f}[/]"
  else:
      return f"[bold green]{real_profit:+8,.0f}[/]"
  ```

### Principle 4: CSV Schema Append & Excel Filter Support
- Two new clean string columns are added at the **very end** of the CSV so existing column indices (0 to 22) are untouched:
  - `Alfa Risk Alert`: `NONE` | `THIN_BUFFER` | `SAFE_FALLBACK` | `SERVER_DOWN`
  - `Digi Risk Alert`: `NONE` | `THIN_BUFFER` | `SAFE_FALLBACK` | `SERVER_DOWN`
- Pure text only in CSV (zero Rich ANSI codes).
- Price columns continue exporting pure integer strings via `format_export_price` (zero `.0` float drift).

### Principle 5: Alert Precedence Hierarchy
If multiple conditions match, priority order is:
1. `SERVER_DOWN` (Highest priority - connection failed)
2. `SAFE_FALLBACK` (Price uncompetitive, sales velocity zero)
3. `THIN_BUFFER` (Profit < Rs. 700, courier packaging risk)
4. `NONE` (Optimal / normal healthy pricing)

---

## 3. Data Contract & Helper Implementations

### Helper: `determine_risk_alert`
```python
def determine_risk_alert(res: PlatformPricingResult) -> str:
    """Determine standardized risk alert code following priority hierarchy."""
    if res.status == "Server Down / Unreachable" or res.final_price is None:
        return "SERVER_DOWN"
    if res.status == "Safe Fallback":
        return "SAFE_FALLBACK"
    if res.real_profit < 700:
        return "THIN_BUFFER"
    return "NONE"
```

### Integrated Schema in `build_output_record`
```python
out_record["Alfa Risk Alert"] = determine_risk_alert(alfa_res)
out_record["Digi Risk Alert"] = determine_risk_alert(digi_res)
```

---

## 4. Phase-wise Implementation Plan

### Phase 1: Risk Alerts Logic & Schema Extension
- In `pricing_engine/pipeline.py`:
  - Implement `determine_risk_alert(res: PlatformPricingResult) -> str`.
  - Update `build_output_record` to include `"Alfa Risk Alert"` and `"Digi Risk Alert"` at the end of the schema.
  - *Files touched:* `pricing_engine/pipeline.py`

### Phase 2: Terminal Audit Card Risk Badging
- In `pricing_engine/pipeline.py`:
  - In `render_audit_card`, display detailed informative badges:
    - Safe Fallback: `[bold red]Rs. 211,999 (SAFE FALLBACK - UNCOMPETITIVE)[/]`
    - Thin Profit: `[bold red]+Rs. 502 (THIN BUFFER - VOLUMETRIC RISK)[/]`
    - Capped Price: `[bold yellow]Rs. 478,999 (CAPPED SWEET-SPOT)[/]`
    - Server Down: `[bold red][SERVER DOWN - RETRY LATER][/]`
  - *Files touched:* `pricing_engine/pipeline.py`

### Phase 3: Summary Table Traffic-Light Formatting & Legend
- In `pricing_engine/pipeline.py`:
  - Implement cell formatting helpers: `format_table_price`, `format_table_profit`, `format_table_rate`.
  - Zero-width character styling preserves 100% straight borders.
  - Print 1-line Rich Legend below summary table.
  - *Files touched:* `pricing_engine/pipeline.py`

### Phase 4: Comprehensive Unit Testing
- In `tests/test_pipeline.py`:
  - Add test for `determine_risk_alert` covering all priority states (`SERVER_DOWN`, `SAFE_FALLBACK`, `THIN_BUFFER`, `NONE`).
  - Add test for `build_output_record` verifying new risk columns exist.
  - Add test verifying CSV export contains clean strings (`THIN_BUFFER`, `NONE`) and zero ANSI codes.
  - Add test verifying `render_summary_table` and `render_audit_card` execute cleanly with mixed risk items.
  - *Files touched:* `tests/test_pipeline.py`

### Phase 5: Live Production Benchmark
- Run `pytest -v` (expect all 65+ unit tests passing).
- Run `ruff check .` (expect 0 errors).
- Execute `python index.py` on all 25 live products and inspect terminal aesthetics and CSV export.

---

## 5. Verification Checklist

- [ ] All 63 existing tests remain 100% green.
- [ ] No `TypeError` when `real_profit` is `None`.
- [ ] Summary table borders remain perfectly aligned without wrapping.
- [ ] CSV columns `Alfa Risk Alert` and `Digi Risk Alert` appear at the end with pure text strings.
- [ ] Price columns contain pure integer strings with zero `.0` float drift.
