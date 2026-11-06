# DigiMall model-first discovery — approved implementation

## Contract

Keep AlfaMall and all financial formulas unchanged. Route normal, personal-commission,
and range DigiMall runs through a separate model-first query planner. Retain original
catalog brand/description for every compatibility decision.

1. Per explicit model branch: extracted model, separator alternative, first distinct
   brandless numeric Tier 2 candidate. At most three queries. Stop fallback only after
   required pages finish and an exact in-stock external offer exists. A page failure
   stops remaining fallback attempts for that branch; another branch still runs.
2. Request 100 items/page. Counts 0–100 require page 1; 101–200 pages 1–2;
   201+ pages 1–3. Above 300 is capped. Unknown counts inspect three pages.
   No brand-drop, viable-offer or floor-based pagination exits.
3. Run-scoped raw-page cache and single-flight map, keyed by platform, endpoint,
   query, page and effective parameters. Request limit equals CLI concurrency.
   Retry each page; release permits during backoff; clean up cancellation.
4. Reuse existing referee, pool precedence and ambiguity handling. Prefer available
   duplicate copies, locally sort active offers, retain lowest five and full pool.
5. Aggregate coverage independently of offers: COMPLETE, CAPPED, UNKNOWN,
   INCOMPLETE, FAILED. Inconsistent/short/repeated pages are incomplete and invalidated.
   Provisional observed prices remain numeric, but cannot qualify as confirmed Digi wins.
   No monopoly when noncomplete and no eligible offers.
6. Preserve coverage/detail in terminal, CSV/XLSX, range and ambiguous rows.
   S.NO first, risk alerts last; preserve existing input columns and integer prices.
7. Version only Digi/all checkpoint fingerprints. Failed/incomplete/unknown rows
   retry on resume; capped rows do not loop automatically.

Explicit string/dictionary calls remain supported. Adaptive production calls pass a
DigiQueryPlan and share one DigiDiscoveryContext per run. Dictionary tiers retain
canonical order and optional legacy exhaustive=False semantics.

## Verification

Write reproductions first, verify each slice, then full pytest and ruff. Strict mypy
checks cover changed engine modules; Black checks new modules/tests. Test exports,
catalogs, checkpoint persistence and coverage data use isolated temporary locations.
Measure request counts, peak concurrency, latency and observed minimum in a controlled
old/new replay. Live API samples are observations, not deterministic timing assertions.

## Limits

COMPLETE means all required pages of the selected query policy, not exhaustive
marketplace discovery. Fallback-only queries can miss alternate-query-only listings.
The three-page cap cannot guarantee a global minimum. No zero-latency-regression promise.

## Implementation order

Planner → page contracts/transport/cache → orchestration/ranking → provisional
pricing → reporting/range → resume → independent review, full tests and benchmark.

No production CSV runs, database migrations, unrelated matcher refactors, staging,
or commits are necessary for this change.

## User-approved reporting/pricing revisions

Successful CAPPED observed wins qualify for winning exports with a coverage note.
Successful CAPPED zero-offer scans use existing monopoly math and a Not Found /
observed SOLO label. Failed/incomplete/unknown discovery and suspicious rejections
still suppress monopoly. Terminal audit is a short summary; raw details stay exported.
Timeout retries remain three increasing-timeout attempts with visible progress.
