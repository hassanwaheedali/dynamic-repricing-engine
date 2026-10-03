# Implementation Plan: Market Range Mode (`--range-only`)

> Status: PLAN ONLY. No code written. Waiting for user approval.
> (Old Phase 1/2 plan stays in `tasks/plan.md`; this is a separate feature.)

## Overview
A second run mode. User gives only `Brand` + `Name` (model list). Engine runs the
same scrape + strict variant matching, then outputs only the **market Min / Max**
for AlfaMall and DigiMall. No floor, no commission math, no final price.
Output = CSV + XLSX in a separate `data/outputs/range/` tree.

## Codebase findings (what already exists)
| Finding | Consequence |
|---|---|
| `evaluate_alfa_pricing` / `evaluate_digi_pricing` already compute `min_p`/`max_p` over **non-sold-out** offers (evaluator.py L71-75, L258-262) | Sold-out rule + min/max logic exists. Extract into one helper (DRY), no new rule. |
| `run_pipeline` reads CSV itself and uses `parse_product_input`; missing L/W/H/Net -> `0.0` | Range mode needs NO ingestion change. Only `Brand` + `Name` are enforced. |
| Output already has `Minimum/Maximum Price Alfa/Digi` + `Alfa Status`/`Digi Status` columns (AGENTS.md is outdated here) | Reuse the same column order. |
| `determine_risk_alert` returns `SERVER_DOWN` whenever `final_price is None` | Cannot reuse in range mode (would flag every row). Need `determine_range_alert`. |
| Scraper `_execute_waterfall` stops after a tier gives >= 2 offers (scraper.py L188-190) | **Max can be understated** (other listings only appear under other queries). Key risk. |
| `floor_price` only triggers page-2 probe | Pass `None` in range mode. `limit=100` already large. |
| `openpyxl` not in `requirements.txt` | New dependency (T4). |
| `pipeline.py` is already 1254 lines | New module `range_pipeline.py`; do not grow pipeline.py. |

## Decisions (from user)
- Input: `Brand`, `Name` only.
- Min = lowest in-stock price any vendor lists (no floor filter).
- Max = highest in-stock price any vendor lists for the same matched model.
- Sold-out offers ignored (same as current rule).
- All existing output columns stay; Final/Profit/Reason columns empty.
- Extra columns allowed (layout below). CSV **and** XLSX. Separate output folder.
- Trigger: `--range-only` flag + interactive mode prompt.

## Output column layout (range mode)
```
S.NO                       <- always col 1
<all input columns>        <- Brand, Name, + any custom cols (preserved)
Shipping Estimate          (empty)
Commision                  (empty)
Digi Effective Commision   (empty)
Total Without Profit       (empty)
Calculation                (empty)
Minimum Price Alfa         <- filled
Maximum Price Alfa         <- filled
Minimum Price Digi         <- filled
Maximum Price Digi         <- filled
Alfa Offers Found          <- NEW (in-stock matched count)
Digi Offers Found          <- NEW
Final Price Alfa           (empty)
Alfa Status                (empty)
Final Price Digi           (empty)
Digi Status                (empty)
Alfa Real Profit           (empty)
Digi Real Profit           (empty)
Alfa Reason                (empty)
Digi Reason                (empty)
Alfa Risk Alert            <- final 2 columns (contract kept)
Digi Risk Alert
```
- Extra columns exist **only in range mode**, between `Maximum Price Digi` and
  `Final Price Alfa`. Normal repricing output contract is untouched.
- Net Price / Length / Width / Height: if absent from input they are not invented.
  If the user supplied them, they are preserved like custom columns.
- Range-mode risk alert: `NONE` | `SERVER_DOWN` | `NO_OFFERS` (healthy search, zero
  in-stock matches; Min/Max empty). `NO_OFFERS` is new.
- Counts make `Min == Max` explainable (1 offer vs. genuinely equal prices).

## Output folders
```
data/outputs/range/
  csv/   {stem}_range_{YYYYMMDD_HHMMSS}.csv   + {stem}_range_latest.csv
  xlsx/  {stem}_range_{YYYYMMDD_HHMMSS}.xlsx  + {stem}_range_latest.xlsx
```
XLSX stores prices as real numbers. CSV keeps pure-integer strings (no `.0`).

## Architecture Decisions
- **Reuse, don't fork**: scraper, matcher, `parse_product_input` unchanged, so
  variant protection (colour / kg / SD vs DD) applies automatically.
- **One helper** `evaluate_market_range(offers) -> MarketRange` used by range mode
  AND both evaluators (removes duplicated min/max code; existing tests guard it).
- **New module** `pricing_engine/range_pipeline.py`.
- Zero hardcoded brands/categories (AGENTS.md rule 6).
- Offline-safe: no Supabase needed; learner buffering skipped in range mode.

## Task List (TDD per task: RED -> GREEN -> REFACTOR)

### Phase 1: Core
- [ ] T1 `MarketRange` + `evaluate_market_range` (+ refactor evaluators to use it)
- [ ] T2 `build_range_record` + `determine_range_alert` (column contract)
### Checkpoint A: `pytest -v` green (168 + new), `ruff check .` clean

### Phase 2: Pipeline + Export
- [ ] T3 `run_range_pipeline` (async, semaphore, deterministic order, Rich summary)
- [ ] T4 `export_range_results` (CSV + XLSX, folders, latest copy, `openpyxl`)
### Checkpoint B: fake-scraper end-to-end test yields CSV+XLSX with right columns

### Phase 3: CLI + Docs
- [ ] T5 `index.py`: `-r/--range-only`, interactive mode prompt (TTY only)
- [ ] T6 Docs (README, AGENTS.md sections 4-5) + live smoke run on 3-5 real models
### Checkpoint C: manual check of Min/Max vs. website for known models

## Risks and Mitigations
| Risk | Impact | Mitigation |
|---|---|---|
| Waterfall early-exit (>=2 offers) understates Max | High | Range mode runs all tiers and merges (`exhaustive=True` param on waterfall, default False). Test with 2-tier fake. More requests, acceptable. |
| Accessory/odd listing distorts Min or Max | Med | Matching already strict. Offer count column + live smoke check. |
| XLSX `latest` locked by Excel on Windows (PermissionError) | Med | Catch, warn, keep timestamped file, do not crash. |
| `openpyxl` missing in user env | Low | Add to requirements/pyproject; clear error, CSV still written. |
| Both malls down for a row | Low | `SERVER_DOWN`, blanks, run continues. |

## Open Questions
1. Folder layout OK (`range/csv`, `range/xlsx`)?
2. Exhaustive tiers in range mode (more requests, correct Max): confirm.
3. `NO_OFFERS` as new alert label OK?
