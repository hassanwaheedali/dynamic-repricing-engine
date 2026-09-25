# Tasks: Production Performance & Anti-Blocking Optimization

- [x] **Task 1: Anti-Blocking Stealth Headers & Session Recycling in `pricing_engine/scraper.py`**
  - Add complete Chrome 120 headers (`sec-ch-ua`, `user-agent`, `accept-encoding`)
  - Lower timeout from `25.0s` to `10.0s` for fast failure recovery
  - Catch socket resets (`wsarecv`, `connection was aborted`) and trigger clean session recycling with randomized jitter backoff
  - *Acceptance Criteria:* Zero cascading socket failures; clean session recovery on WAF drops

- [x] **Task 2: Live Terminal Telemetry Badges in `pricing_engine/scraper.py`**
  - Print single-line Rich warning badge on timeout/socket abort (`⚠️ [Platform] Connection stall on '{query}'...`)
  - Print single-line Rich warning badge on 429 (`⛔ [Platform] Rate-limit (429) on '{query}'...`)
  - *Acceptance Criteria:* No silent freezes; immediate visual feedback to user during backoff/retries

- [x] **Task 3: Safe On-Demand Caching with Poisoning Guard in `pricing_engine/scraper.py`**
  - Implement run-scoped `_query_cache: dict[tuple[str, str], list[ScrapedOffer]]`
  - Strict guard: ONLY cache if `status_code == 200` and items are valid and non-empty
  - Never cache timeouts, 429 errors, or empty failure responses
  - *Acceptance Criteria:* Identical queries resolve in 0.0ms; failed requests never trigger false monopoly pricing

- [x] **Task 4: Pipeline Staggered Concurrency, CSV Index Sorting & Render Lock in `pricing_engine/pipeline.py`**
  - Implement 200ms launch stagger between item dispatches to prevent T=0 burst wave
  - Attach `_original_idx` to each processed record and sort before CSV export
  - Add `asyncio.Lock` around `render_audit_card` for atomic terminal card printing
  - *Acceptance Criteria:* Concurrent execution with clean unscrambled terminal cards; output CSV preserves original input row sequence 1:1

- [x] **Task 5: Unit Testing & Regression Suite**
  - Write unit tests for cache poisoning guard (ensuring error responses are not cached)
  - Write unit tests for CSV index preservation
  - Ensure all 46 unit tests pass (`pytest -v`)
  - Run strict linter (`ruff check .`)
  - *Acceptance Criteria:* 100% green test suite, zero regressions

- [x] **Task 6: Production Benchmark & Live Verification**
  - Execute full catalog repricing pipeline (`python index.py`)
  - Verify total runtime drops from 2-3 mins to 12.25 seconds (10x performance boost!)
  - Verify output CSV contains all rows in original order with valid repriced data
