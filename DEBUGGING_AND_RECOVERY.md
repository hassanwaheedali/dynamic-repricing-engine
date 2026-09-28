# Debugging & Recovery Documentation: Dynamic Repricing Engine

> **Branch Purpose**: This branch (`debugging-and-recovery`) captures the root-cause analysis, cross-checking findings, and architectural fixes applied to the AlfaMall & DigiMall dynamic repricing engine during the Haier washing machine catalog onboard. It serves as the authoritative blueprint for main branch engineers and upcoming SaaS contributors.

---

## 1. Executive Summary & Context

During live evaluation of Haier washing machines across AlfaMall and DigiMall APIs, two critical issues were reported and diagnosed:

1. **Item #20 (`120-826S6 GC`) - Zero Matches & False Monopoly**:
   - *Symptom*: AlfaMall returned 0 scraped matches despite 9 real active sellers listing the unit.
   - *Root Cause*: The query string contained `GC` (Glass Color). The regex matcher required `GC` strictly. Competitors listed the product as `Haier 120-826S6 Glass Door Fully Automatic Washing Machine` without the two-letter abbreviation `GC`.
   - *Resolution*: Made cosmetic feature tags (`GC`, `GT`, `JT`) optional in `pricing_engine/matcher.py`.

2. **Item #38 (`HWM 80-186`) - Failure to Apply 50% Midpoint Pricing on Large Gap**:
   - *Symptom*: Our 10% floor was Rs. 42,552; viable competitor Home Cart was at Rs. 49,999 (Gap = Rs. 7,447). The engine priced at Rs. 49,899 (hugging the competitor by only -100 PKR).
   - *User Expectation*: When the price gap is large, the engine must apply the **50% split midpoint rule** to maximize customer conversion rather than sitting right next to an inflated competitor.
   - *Root Cause*: `pricing_engine/evaluator.py` had a condition `if max_profit_cap is not None else None` on AlfaMall. Because `max_profit_cap` was `None` by default in the pipeline, `target_adaptive_alfa` was always `None`. The engine silently bypassed the 5-Tier Adaptive Ladder on AlfaMall!
   - *Resolution*: Removed the restrictive check in `pricing_engine/evaluator.py`, aligning AlfaMall with DigiMall to strictly apply the 5-tier dynamic adaptive ladder.

---

## 2. Issue 1: Optional Feature Keywords (`GC`, `GT`, `JT`) vs Strict Variants

### Problem Statement
In Pakistani e-commerce titles, some letters represent **core hardware models** (e.g. `WB` = Washer Box/Single Tub, `E` = Electronic Series), while other suffix tags are **marketing/cosmetic descriptors** (e.g. `GC` = Glass Color / Glass Crystal, `GT` = Glass Top, `JT` = Jet / Top).

When a user searches `120-826S6 GC`:
- If the matcher treats `GC` as mandatory, listings with `120-826S6 Glass Door` get discarded.
- Conversely, if letters like `WB` or `GB` are made optional, single-tub (`HWM 80-1217WB`) and twin-tub models get conflated, causing catastrophic mispricing.

### Architectural Solution in `pricing_engine/matcher.py`
We established a strict distinction between **variant letters** and **optional cosmetic tags**:
- **Optional Tags**: `GC`, `GT`, `JT`
- In `is_strict_model_match()`:
  - If the search target has `GC`, `GT`, or `JT`, strip the tag to form a `core_model` (`120-826S6`).
  - Verify that the scraped title contains the `core_model`.
  - Ensure no colliding model numbers exist (e.g., `100-826S6` or `150-826S6` are rejected).
  - Both listings with `GC` and listings without `GC` match cleanly.
- In `generate_search_queries()`:
  - Multi-pattern query seeds automatically generate search queries with and without `GC`.

### Live Verification
- **Item #20 (`120-826S6 GC`)**:
  - Found **9 verified offers** on AlfaMall (previously 0).
  - Filtered 2 sub-floor loss-makers (< Rs. 83,464).
  - Undercut viable seller Urban Hub (Rs. 83,999) to winning price **Rs. 83,899** with **+Rs. 891** profit.

---

## 3. Issue 2: Large Gap Adaptive 50% Midpoint Pricing on AlfaMall

### Problem Statement
When a competitor is viable but priced significantly above our floor (e.g. Rs. 7,447 higher), simply undercutting them by Rs. 100 leaves our price at an artificially high level. This hurts sales conversion and provides zero compelling value to the bank customer.

The business rule defined in `pricing_engine/calculator.py` specifies:
```
Tier 5 (Gap < Rs. 800)       : Closest Rs. 100 undercut (strict floor guarantee)
Tier 4 (Gap Rs. 800 - 1,499) : Rs. 200 undercut (visible discount)
Tier 3 (Gap Rs. 1,500 - 1,999): Rs. 500 customer discount, min Rs. 1,000 profit buffer
Tier 2 (Gap Rs. 2,000 - 9,999): Proportional 50% split midpoint (min Rs. 1,000 buffer)
Tier 1 (Gap >= Rs. 10,000)   : Sweet-spot profit cap (~Rs. 10,000 target profit)
```

### The Bug in `pricing_engine/evaluator.py`
In `evaluate_alfa_pricing`:
```python
# OLD BUGGY CODE:
target_adaptive_alfa = (
    calculate_adaptive_target_price(
        floor_min=cost_floors.floor_alfa,
        competitor_price=lowest_viable.price,
        cost_base=cost_floors.cost_base,
        payout_rate=0.90,
        large_gap_profit_target=max_profit_cap,
    )
    if max_profit_cap is not None
    else None  # <-- BUG: Evaluated to None on every normal catalog run!
)
```
Because `max_profit_cap` was `None`, `target_adaptive_alfa` evaluated to `None`. The search function `find_winning_psychological_price(floor, competitor, max_ceiling=None)` defaulted to:
$$\text{Winning Price} = \text{Competitor} - 100$$

### The Fix
Aligned AlfaMall with DigiMall:
```python
# NEW FIXED CODE:
large_cap_alfa = max_profit_cap if max_profit_cap is not None else 10000.0
target_adaptive_alfa = calculate_adaptive_target_price(
    floor_min=cost_floors.floor_alfa,
    competitor_price=lowest_viable.price,
    cost_base=cost_floors.cost_base,
    payout_rate=0.90,
    large_gap_profit_target=large_cap_alfa,
)
```

### Live Proof: Item #38 (`HWM 80-186`)
- **Cost Base**: Rs. 37,797
- **Alfa 10% Floor (+500)**: Rs. 42,552
- **Competitor (Home Cart)**: Rs. 49,999
- **Gap**: $49,999 - 42,552 = \text{Rs. } 7,447$ (Tier 2)
- **50% Midpoint Buffer**: $7,447 \times 0.50 = \text{Rs. } 3,723.5$
- **Target Ceiling**: $42,552 + 3,723.5 = \text{Rs. } 46,275.5$
- **Winning Psychological Price**: **Rs. 46,199** *(ends in .199)*
- **Real Net Profit**: **+Rs. 3,782** *(above guaranteed Rs. 500)*
- **Customer Advantage**: Customer saves **Rs. 3,800** off the lowest market competitor!

---

## 4. Modified & Created Files Index

| File Path | Action | Description & Purpose |
| :--- | :--- | :--- |
| `pricing_engine/evaluator.py` | **Modified** | Enabled 5-Tier Adaptive Gap pricing for AlfaMall by removing `if max_profit_cap is not None`. Added 50% split audit reasons. |
| `pricing_engine/matcher.py` | **Modified** | Added optional feature token stripping (`GC`, `GT`, `JT`) and multi-pattern query seeds. Preserved strict model variants (`WB`, `GB`, `E`). Combined nested conditionals for linting. |
| `pricing_engine/scraper.py` | **Modified** | Implemented anti-blocking headers, connection retry backoff, and run-scoped query cache. |
| `pricing_engine/pipeline.py` | **Modified** | Enhanced terminal audit telemetry and deterministic index ordering. |
| `tests/test_matcher.py` | **Modified** | Added unit test `test_optional_feature_tags_gc_gt()`. |
| `tests/test_evaluator.py` | **Modified** | Updated assertion in `test_alfa_competitive_win_undercut` to expect Tier 2 50% midpoint (`81499`). |
| `tests/test_pipeline.py` | **Modified** | Updated Item #17 assertion to expect Tier 4 dynamic undercut (`153799`). |
| `Haier_Washing_Machines_Uploading_and_Price.csv` | **Created** | Clean catalog input with 38 verified products, volumetric shipping calculations, and 4 unpriced models removed. |
| `final_haier_wm_repriced.csv` | **Created** | Full repriced output file with commission breakdown, profit audit, and status reasons. |
| `DEBUGGING_AND_RECOVERY.md` | **Created** | Comprehensive architectural and debugging report for future reference and SaaS scaling. |

---

## 5. Verification & Test Suite Status

- **Unit Tests**: `pytest` run on complete test suite:
  - **81 / 81 Tests Passing (100% Green)**
- **Linter**: `ruff check .`
  - **All checks passed! Zero warnings, zero errors.**
- **Edge-Case Validation**:
  - `HWM 80-1217WB` strictly rejects `HWM 80-1217` and `HWM 80-1217GB`.
  - `120-826S6 GC` matches `120-826S6` without false monopoly.
  - Large gaps trigger 50% conversion midpoints.
  - Tight gaps (< Rs. 800) preserve standard Rs. 100 undercuts.
