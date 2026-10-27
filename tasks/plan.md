# Implementation Plan: Own Store & Official Store Detection & Telemetry

## Overview
Enable detection of merchant's own store (`KiaChahye`, `Ajmer`) and brand official store (`Haier Official Store`) active listings on AlfaMall and DigiMall. Display hints in terminal audit cards and CSV reason columns with guaranteed mathematical isolation (zero self-undercutting).

## Architecture Decisions
- **Zero Self-Undercut Invariance**: Competitor pool `offers` and metadata pool `own_offers` are strictly segregated at the scraper extraction layer. Evaluator pricing logic only operates on `offers`.
- **Schema Stability**: Zero modifications to CSV column ordering; telemetry is surfaced via Rich Terminal Cards and Reason column annotations (`Alfa Reason`, `Digi Reason`).

## Task List

### Phase 1: Foundation (Models)
- [ ] Task 1.1: Add `classify_non_competitor_vendor()` in `pricing_engine/models.py`
- [ ] Task 1.2: Add `own_offers` to `ScrapeResult` and `PlatformPricingResult` dataclasses

### Phase 2: Scraper Pipeline
- [ ] Task 2.1: Update `_parse_offers_from_raw_items()` in `pricing_engine/scraper.py` to route non-competitors to `own_offers` without dropping
- [ ] Task 2.2: Pass `own_offers` through single query scraper and `_execute_waterfall()`

### Phase 3: Evaluator Decision & Reason Annotation
- [ ] Task 3.1: Add `_annotate_non_competitor_reason()` in `pricing_engine/evaluator.py`
- [ ] Task 3.2: Verify mathematical invariance (monopoly when only own store exists, undercut only genuine competitors)

### Phase 4: UI & Terminal Rendering
- [ ] Task 4.1: Render own store and official store rows in `_render_platform_offers_to_table()` in `pricing_engine/pipeline.py`

### Phase 5: Range Mode & Exporter
- [ ] Task 5.1: Verify range mode compatibility in `pricing_engine/range_pipeline.py`

### Phase 6: Automated Testing & Verification
- [ ] Task 6.1: Add unit tests in `tests/test_evaluator.py` for vendor classification and zero undercutting
- [ ] Task 6.2: Add unit tests in `tests/test_pipeline.py` for terminal card rendering
- [ ] Task 6.3: Run full test suite (`pytest -v`) and linter (`ruff check .`)
