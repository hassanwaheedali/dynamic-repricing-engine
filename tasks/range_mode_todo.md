# Todo: Market Range Mode

Plan: `tasks/range_mode_plan.md`. Each task = RED test first, then minimal code.

## T1 `MarketRange` + `evaluate_market_range` [S]
Files: `models.py`, `evaluator.py`, `tests/test_evaluator.py`
- [ ] min/max over in-stock offers only; sold-out ignored
- [ ] no floor filtering (sub-floor offers count)
- [ ] 0 offers -> min/max `None`, count 0
- [ ] failed `ScrapeResult` -> `is_down=True`
- [ ] `evaluate_alfa/digi_pricing` refactored to use helper; all old tests still green

## T2 `build_range_record` + `determine_range_alert` [S]
Files: `range_pipeline.py`, `tests/test_range_pipeline.py`
- [ ] `S.NO` col 1; input cols preserved; legacy `"Name "` key handled
- [ ] cost/final/profit/reason columns present but empty
- [ ] `Alfa/Digi Offers Found` between `Maximum Price Digi` and `Final Price Alfa`
- [ ] risk alerts last 2 cols: NONE / SERVER_DOWN / NO_OFFERS

## T3 `run_range_pipeline` [M]
Files: `range_pipeline.py`, `tests/test_range_pipeline.py`, `tests/test_scraper.py`
- [ ] input with only Brand+Name works (no Net/L/W/H)
- [ ] missing Brand/Name -> clear error
- [ ] semaphore concurrency, original row order preserved
- [x] waterfall queries every tier (upstream), Max not understated
- [ ] one platform down does not break the row or the run
- [ ] Rich summary table (Model | Alfa Min-Max | Digi Min-Max)

## T4 `export_range_results` [M]
Files: `exporter.py`, `requirements.txt`, `pyproject.toml`, `tests/test_exporter.py`
- [ ] writes `data/outputs/range/csv/` and `/xlsx/` (timestamped + latest)
- [ ] CSV pure integers, no `.0`; XLSX numeric cells
- [ ] locked XLSX -> warning, no crash, timestamped file still saved
- [ ] missing `openpyxl` -> clear message, CSV still written

## Checkpoint B
- [ ] fake-scraper end-to-end: CSV + XLSX columns match plan layout

## T5 CLI [S]
Files: `index.py`, `tests/test_cli.py`
- [ ] `-r/--range-only` runs range mode
- [ ] TTY + no flag -> mode prompt; non-TTY -> normal repricing (unchanged)
- [ ] works with `-i`, `-b`, `-c`, `-q`

## T6 Docs + live check [S]
Files: `README.md`, `AGENTS.md`
- [ ] document mode, columns, folders, new alert
- [ ] live smoke run: 3-5 real models, compare Min/Max with website
- [ ] `pytest -v` 100% green, `ruff check .` 0 errors
