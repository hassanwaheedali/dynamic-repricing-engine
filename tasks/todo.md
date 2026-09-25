# Tasks: Server Down Detection Guard vs. Legitimate Monopoly

- [x] **Task 1: Add `ScrapeResult` Data Contract in `pricing_engine/models.py`**
  - Define `ScrapeResult` dataclass with `offers: list[ScrapedOffer]`, `is_success: bool`, `status_code: int | None`, and `error_detail: str | None`
  - *Acceptance Criteria:* Model imported cleanly across scraper, evaluator, and pipeline; backward-compatible defaults.
  - *Verification:* `pytest tests/test_models.py` or `ruff check .`
  - *Dependencies:* None

- [x] **Task 2: Upgrade Scrapers with WAF HTML Guard & Cache Contract in `pricing_engine/scraper.py`**
  - Return `ScrapeResult(offers=offers, is_success=True, status_code=200)` on valid HTTP 200 responses
  - Catch **Soft 200 OK** (HTML WAF challenge / non-JSON responses) and mark `is_success=False` with error detail
  - Return `ScrapeResult(offers=[], is_success=False, status_code=last_code, error_detail=last_err)` when retries are exhausted (500, 429, socket reset, timeout)
  - Align `_query_cache` type to store `ScrapeResult`; NEVER cache when `is_success is False`
  - *Acceptance Criteria:* Network aborts, 500s, and WAF HTML challenges return explicit `is_success=False` rather than an ambiguous empty list; zero cache type drift
  - *Verification:* `pytest tests/test_scraper.py -v`
  - *Dependencies:* Task 1

- [x] **Task 3: Implement Server Down Guard in `pricing_engine/evaluator.py`**
  - Support `scrape_success: bool = True` and `error_detail: str | None = None` in `evaluate_alfa_pricing` and `evaluate_digi_pricing`
  - When `scrape_success is False`: Return `PlatformPricingResult(final_price=None, real_profit=0, status="Server Down / Unreachable", reason=...)`
  - When `scrape_success is True` and `len(offers) == 0`: Trigger legitimate `Monopoly Win` (+Rs. 4,000 margin)
  - Ensure **Asymmetric Isolation**: AlfaMall and DigiMall evaluations remain 100% decoupled
  - *Acceptance Criteria:* Server failures strictly set `final_price=None` (Skip) and never trigger false Monopoly pricing; failure on one portal never affects the other
  - *Verification:* `pytest tests/test_evaluator.py -v`
  - *Dependencies:* Task 1, Task 2

- [x] **Task 4: Pipeline Integration, Rich Terminal Badges & Integer CSV Formatting in `pricing_engine/pipeline.py`**
  - Unpack `ScrapeResult` in `process_product_with_offers` and pass success flags to evaluators
  - Render distinct `[bold red][SERVER DOWN - RETRY LATER][/]` badge on terminal card when status is `Server Down / Unreachable`
  - Implement `format_export_price` in CSV writer to guarantee pure integer string export (`165000` never `165000.0` or float drift when `None` exists)
  - *Acceptance Criteria:* Output CSV and terminal card clearly inform the merchant that the portal was unreachable; pure integer CSV formatting preserved
  - *Verification:* `pytest tests/test_pipeline.py -v`
  - *Dependencies:* Task 2, Task 3

- [x] **Task 5: Comprehensive Unit Test Suite**
  - Write test for True Monopoly (200 OK + 0 results -> Monopoly Win)
  - Write test for Server Down 500 (HTTP 500 -> Server Down / Unreachable)
  - Write test for Soft 200 OK WAF HTML challenge (HTML body -> Server Down / Unreachable)
  - Write test for Asymmetric Failure (Alfa OK, Digi 500 -> Independent outcomes)
  - Write test for CSV integer formatting with `None` present (zero float drift)
  - *Acceptance Criteria:* Full test suite passes 100% green (`pytest -v`), 0 linter errors (`ruff check .`)
  - *Verification:* `pytest -v && ruff check .`
  - *Dependencies:* Task 1 to Task 4

- [x] **Task 6: Live Production Benchmark Verification**
  - Execute `python index.py` against live catalogs
  - Verify that healthy live products remain completely unaffected (25/25 correctly repriced)
  - *Acceptance Criteria:* Total execution finishes under 7 seconds with zero regressions
  - *Verification:* `python index.py`
  - *Dependencies:* Task 5
