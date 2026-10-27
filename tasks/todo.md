# Task Checklist: Own Store & Official Store Telemetry

- [x] **Task 1: Models & Data Contract**
  - [x] Implement `classify_non_competitor_vendor()` in `pricing_engine/models.py`
  - [x] Add `own_offers` field to `ScrapeResult`
  - [x] Add `own_offers` field to `PlatformPricingResult`
  - [x] Unit tests for vendor classification

- [x] **Task 2: Scraper Offer Routing**
  - [x] Route non-competitor items to `own_offers` in `_parse_offers_from_raw_items()` in `pricing_engine/scraper.py`
  - [x] Update `_scrape_platform_single_query()` to deduplicate and store `own_offers`
  - [x] Update `_execute_waterfall()` to aggregate `own_offers` across tiers

- [x] **Task 3: Evaluator Isolation & Reason Annotation**
  - [x] Keep `offers` list strictly competitive (own store never enters `active_offers`)
  - [x] Implement `_annotate_non_competitor_reason()` in `pricing_engine/evaluator.py`
  - [x] Verify Monopoly pricing triggers if own store is sole lister

- [x] **Task 4: Terminal Audit Card Display**
  - [x] Update `_render_platform_offers_to_table()` in `pricing_engine/pipeline.py`
  - [x] Add badge `★ Our Store (Active Listing)` for KiaChahye/Ajmer
  - [x] Add badge `Official Flagship (Excluded)` for Haier Official Store

- [x] **Task 5: Range Mode Check**
  - [x] Ensure `pricing_engine/range_pipeline.py` preserves own store metadata without distorting market min/max

- [x] **Task 6: Verification & Quality Gate**
  - [x] Run `pytest tests/test_evaluator.py`
  - [x] Run `pytest -v` (full 362 test suite)
  - [x] Run `ruff check .`
