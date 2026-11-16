# Architecture consolidation after 6a66118

Implemented on branch `codex/architecture-consolidation`, 2026-11-17. The approved eleven milestones are complete. Earlier task plans and review records are retained.

## Final ownership and interfaces

| Owner | Responsibility |
|---|---|
| `capacity.py` | Supported units/aliases, exact Decimal normalization, formatting, explicit measurement vocabulary; no SKU/category inference |
| `matcher.py` | Model recognition, protected model spans, model-first candidates, canonical series, and the one compatibility referee |
| `series_fallback.py` | Bounded eligibility and query construction; delegates matching without replacing target identity |
| `offer_processing.py` | Parsing, brand evidence, tier classification, stock/identity deduplication, own-store separation, ambiguity, notices and synchronous finalization |
| `digi_discovery.py` | Brandless bounded query policy, branch execution, pagination validation and coverage/audit aggregation |
| `digi_transport.py` | Bounded raw HTTP pages, retries, cache/in-flight work and cancellation |
| `scraper.py` | Existing public scraper entry points and AlfaMall retrieval/outage policy; compatibility aliases delegate to shared processing |
| `models.py`, root `config.py` | Shared transport contract and protocol settings |
| `calculator.py` | Pricing/shipping policy and math; consumes shared numeric/unit normalization |

Dependencies are acyclic: scraper -> discovery -> transport; scraper/discovery -> processing -> matcher/series; series -> matcher; matcher -> capacity/registry. Transport consumes leaf configuration/contracts and the shared query normalizer. Matching and processing contain no HTTP workflows.

Public scraper signatures and CSV/XLSX columns remain unchanged. `MatchDecision` and `ScrapedOffer` add defaulted `match_basis="model"|"series"`. `GuardedFacets.capacity` remains a canonical string. New public shared helpers include `generate_model_first_queries`, `normalize_series_tokens`, `model_identity_parts`, `referee_series_candidate`, and `finalize_offers`.

Matching-policy version is `product-evidence-v7-consolidated`; its existing all-platform checkpoint fingerprint participation invalidates previous completed rows. No database migration is required.

## Completed milestones

| # | Work and primary affected files |
|---|---|
| 1 | Contract, ordered-query/matching/shipping/price baseline, task history: `tasks/plan.md`, `tasks/todo.md`, contract/baseline artifacts, audit script and catalog contract tests |
| 2 | Exact capacity handling: `capacity.py`, matcher extraction/comparison, series normalization and capacity contract tests |
| 3 | Shared safe series matching and explicit basis: matcher, series policy, models, parsing and series tests |
| 4 | Protect structural model spans before measurement removal: matcher and synthetic structural tests |
| 5 | Shared unit vocabulary/numeric parsing in declarative shipping: root config, calculator and shipping-unit tests |
| 6 | Authoritative model-first candidates: matcher, thin Digi planner and ordered-query contracts |
| 7 | Shared parser/finalizer/classifier: processing, scraper, Digi discovery and parser/reporting regressions |
| 8 | Complete-pool stock/identity deduplication, seller handles, prefix consensus and deterministic metadata; both-platform overlap regressions |
| 9 | `PlatformConfig` moved to models; endpoints/headers/Digi limits moved to root configuration; old scraper/discovery import names remain compatible |
| 10 | Removed reverse transport imports and local import workarounds; retained retry details through module logging; fresh-process/dependency tests |
| 11 | Final policy version, differential audit, changed-range formatting, full suite, independent adversarial reviews and this report |

## Correctness and preserved behavior

- Series matching no longer substitutes candidate anchor/base/tag/capacity into the catalog target. Normal model matching runs first; an explicit different SKU cannot enter series-only acceptance.
- Series-only acceptance requires a missing SKU, explicit leading brand, equal complete series, equal verified capacity and positive family evidence. Extra commercial qualifiers, explicit category/mounting/color/feature conflicts and polarity contradictions reject.
- Missing Inverter retains its existing permissive behavior. Existing feature-omission fallback rules remain. Missing catalog color adds a yellow series warning. Exact/base/sibling model results, including active own-store models found in a broad response, outrank series-only evidence.
- Model-dependent feature exemptions cannot be borrowed from an unverified target SKU. Physical lid checks remain in the common path, with explicit conflicts rejected and omissions warned.
- `1T` / `1.0T` normalize equally. `1T` / `1.25T` and `8CFT` / `8.5CFT` differ. Three-digit screens are recognized. Canonical unit tokens are removed from series and fallback-anchor scans.
- Generic structural spans preserve model digits in `DWAF 6321 L` and unseen equivalents while independent measurements survive in source evidence.
- Available duplicates precede sold-out copies; model basis and tier precede representative-warning preferences. Verified seller handles, model/brand identities, colors and variants remain distinct.
- Prefix consensus runs over the complete raw pool. A bare model cannot bridge conflicting explicit prefixes. Query/page retrieval and caches preserve raw evidence; finalization performs the canonical merge. This helper is a complete-pool operation, not a streaming-fold API.
- Digi retains its ordered three-query model budget, separate last-resort series query, required pagination, cache/cancellation and honest COMPLETE/CAPPED/UNKNOWN/INCOMPLETE diagnostics. Alfa outage/viability rules remain separate. Stock, rather than profit-floor viability, still selects the active model tier.
- Pricing formulas, commissions, shipping rate/bracket tables, own-store exclusion and export schema are unchanged. Unit-alias resolution is shared; all 100 audited catalog shipping results are unchanged.

The duplicate Digi stock workaround and dummy asynchronous finalization callback are removed. No separate platform matcher, vendor-specific exception, new dependency or generic rule framework was introduced.

## Verification evidence

- Baseline: 807 tests passed, 26 existing Windows/curl warnings.
- Consolidated suite: **1,087 tests**, including all original tests and 280 new parameterized/catalog/behavior cases. No original test was deleted or skipped.
- Four existing test scenarios/fixtures were deliberately corrected: explicit different-SKU series acceptance, its generic example, its two-mode export fixture, and the former 1-versus-1.25-ton equivalence. The review log explains each approved expectation change. The parser monkeypatch now targets its canonical module; its assertion is unchanged.
- Required gates: full pytest, `ruff check .`, `mypy pricing_engine --strict` (19 files), `git diff --check` and changed-range Ruff formatting. Fresh-process import tests and lower-layer dependency tests are included in the full suite.
- Catalog audit: **400 matching probes over 100 products**, all 100 shipping results unchanged. Existing ordered queries remain identical except item 79's approved numeric-model recovery. Four captured realistic offer/pricing cases remain identical after removing additive default provenance metadata. **Zero unexplained differences** in the audited snapshots.
- Actual mocked pricing/range integration tests exercise both platforms through ingestion, matching, tier selection, pricing and CSV/XLSX, including warning coloring, own stores, checkpoints and learner exclusion.
- New tests derive configurable shipping expectations from active configuration, parameterize brands/model structures/unit aliases, and test arrival-order permutations. Stable identity expectations remain explicit business-contract assertions.

Reproduce the differential evidence:

```powershell
python -m scripts.audit_architecture_contract --output tasks/architecture-consolidation-current.json --compare tasks/architecture-consolidation-baseline.json --report tasks/architecture-consolidation-differences.json
```

Snapshots, structured differences and changed-range formatting checks are stored under `tasks/architecture-consolidation-*.json`. See `tasks/architecture-consolidation-review.md` for actual independent findings and their test-first corrections. Cross-model review was explicitly skipped by the user; isolated same-model subagents were used.

## Limits and git handling

Verification uses offline captured/mocked evidence; no fresh live inventory scan, production upload or database write was performed. Local tests ran on Windows/Python 3.14.6; CI's other Python versions were not locally exercised. The 26 existing curl selector warnings remain.

Repository-wide formatting still reports the same 25 baseline files, and `mypy .` still stops on duplicate discovery of `tests/conftest.py`. Changed ranges are checked separately; unrelated repository-wide cleanup was excluded.

Implementation slices and review corrections are committed separately on the implementation branch. Nothing was pushed. The pre-existing untracked `tests/fixtures/testing_file.csv` remains untouched.

## Complete changed-file inventory

```text
config.py
docs/architecture-consolidation.md
pricing_engine/calculator.py
pricing_engine/capacity.py
pricing_engine/digi_discovery.py
pricing_engine/digi_transport.py
pricing_engine/matcher.py
pricing_engine/models.py
pricing_engine/offer_processing.py
pricing_engine/scraper.py
pricing_engine/series_fallback.py
scripts/audit_architecture_contract.py
tasks/architecture-consolidation-baseline.json
tasks/architecture-consolidation-contract.md
tasks/architecture-consolidation-current.json
tasks/architecture-consolidation-differences.json
tasks/architecture-consolidation-format-check.json
tasks/architecture-consolidation-review.md
tasks/plan.md
tasks/todo.md
tests/test_architecture_contract.py
tests/test_capacity_contract.py
tests/test_digimall_discovery.py
tests/test_import_boundaries.py
tests/test_model_identity_evidence.py
tests/test_offer_processing_contract.py
tests/test_phase2_alfa_discovery.py
tests/test_series_contract.py
tests/test_series_fallback.py
tests/test_shipping_capacity_units.py
tests/test_structural_measurements.py
```
