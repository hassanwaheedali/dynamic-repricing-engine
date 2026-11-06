# DigiMall implementation checklist

- [x] Query planner: model-first, distinct fallback queries, branch/brand validation.
- [x] Page contract: count aliases/boundaries, missing totals, cap and inconsistency.
- [x] Transport: bounded parallel pages, retries, raw-page cache and single-flight.
- [x] Orchestration: all required pages, adaptive fallback, explicit-query compatibility.
- [x] Ranking: compatible full pool, available duplicates, sorted lowest-five shortlist.
- [x] Provisional evaluation without financial formula changes.
- [x] Normal/range/personal reporting and ambiguity coverage preservation.
- [x] Policy fingerprint and retryable checkpoint rows.
- [x] Independent adversarial design/core/reporting reviews and regression fixes.
- [x] Coverage, final full suite, lint/type/format verification.
- [x] Controlled performance comparison and final change review.

Cross-model external review skipped at the user's explicit preference; independent
same-model reviewers were used. See digimall-discovery-plan.md for the contract.

Initial implementation verification: 618 tests passed (26 Windows curl event-loop warnings),
97% statement coverage across the two new discovery modules; strict mypy passed for
all nine touched engine modules. Repository ruff and Black checks of the five new
Python files passed. The final post-suite test edit only sorts local imports.

Live read-only checks and controlled replay observations are recorded in
docs/digimall-discovery.md. Production CSVs were not modified. User-created untracked
DigiMall input catalogs were preserved.

Final approved policy v4: successful COMPLETE/CAPPED scans with zero eligible
external offers use existing monopoly pricing regardless of rejection counts.
Matcher acceptance rules and Alfa behavior remain unchanged. Failed/unknown/
incomplete discovery stays guarded. Final suite: 631 passed, 26 Windows curl
warnings; repository lint and strict types for the latest changed modules passed.
