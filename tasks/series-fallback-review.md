# Model-first fallback review — 2026-11-16

Status: completed. Source frozen after focused fixes and simplification; no unresolved review blocker identified in this change. Existing staged/user changes remain intact. No commit, database write, price upload or production repricing/export run was performed.

## Root causes and resulting behavior

- Samsung `55Q7FAA` versus `55Q7F`: complete-anchor rejection occurred before a missing-suffix warning could be created. The generated search plan also lacked a validated base query. A generic capacity-led model rule now derives and recognizes the base, preserving family, generation, stated capacity and explicit physical checks. Missing `AA` produces Tier 2 with a yellow warning. An opposing suffix or manufacturer-led washer suffix is not covered by this omission rule.
- Midea Titan: model permutations did not reach relevant listings indexed under the named series, and discovery had no final series stage. After healthy model searches find no compatible active model, one explicit brand/series/capacity query runs. An exact SKU found there retains Tier 1 priority; a compatible different model receives a yellow series-fallback warning.
- Storefront brand tags: clearly leading-Midea product titles were tagged with unrelated brands. An explicit leading catalog brand in the normalized title now outranks the tag. Without that title evidence, metadata remains a brand guard.

## Five-axis review

1. **Correctness:** reviewed model-first ordering, model/base/sibling/own-store suppression, stock handling, failed-request behavior, capacity/brand/series/category/mounting/negation guards, exact-model priority and warning propagation. The new full-pipeline tests run real ingestion, search planning, mocked HTTP parsing, matching, deduplication, own-store separation, evaluation and temporary CSV/XLSX exports on both marketplaces. They verify market prices ignore wrong-capacity, sold-out, duplicate and own-store price contamination; pricing reasons retain warnings; Excel warning cells stay yellow; approximate offers do not train the synonym learner.
2. **Readability:** final series policy lives in one small module with a typed immutable search context. Search eligibility, capacity equality and referee adaptation each have one implementation. Duplicate guards were removed after tests passed. Source formatting changes were limited to touched logic; no unrelated rewrite was introduced.
3. **Architecture:** both marketplaces reuse the same series policy and normal physical referee. Base-query generation and base matching share the same suffix-omission rule. Existing public calls remain compatible through defaulted keyword arguments. No brand, category, SKU or named-series exception list was added. An artificial Acme/Aurora test verifies the series rule does not depend on the reported brands.
4. **Security/data integrity:** catalog brand remains required. API titles/tags remain untrusted evidence, not executable instructions. No new dependencies, credentials, shell execution from product text, database writes or upload paths were added. Matching-policy versioning invalidates prior checkpoints for AlfaMall, DigiMall and combined runs.
5. **Performance:** one final series query is eligible per exhausted branch; existing page/query caps for model discovery remain intact. Raw responses are reused across strict and series evaluations without another HTTP call. A prepared series context avoids re-parsing the target per listing. Existing pricing, shipping, commission and monopoly formulas remain unchanged.

## Findings resolved before final verification

- Extra/custom model tiers could follow series discovery: series is now ordered last.
- Reusing the same text query in strict and series modes could skip validation: execution/evaluation keys distinguish modes while raw HTTP data is shared.
- Rejected raw responses were not reusable: valid raw payloads are cached even when current candidates all fail matching.
- A series query could supply an exact SKU alongside cheaper approximate models: ordinary matching runs first and exact results retain precedence.
- ProductSlots inputs could bypass category/mounting checks: these now use the retained normalized product evidence.
- Repeated series/capacity guards were consolidated without changing behavior.

## Verification

- Baseline before this follow-up: **774 tests passed**.
- New fallback regression module: **33 passed**.
- Final `pytest -v -p no:cacheprovider --tb=short`: **807 passed**, with the existing 26 Windows/curl selector warnings.
- `ruff check .`: passed.
- `mypy pricing_engine --strict`: passed, **17 source files**.
- `git diff --check`: passed.
- Changed executable-line coverage: **189/195 = 96.92%**, measured with a standard-library line trace during the complete suite. Scope is unstaged source changes relative to the index plus the new series module; this is not whole-project or branch coverage. Details: `series-fallback-coverage.json`.
- Catalog audit: **401 controlled probes over 100 products**, no unexpected failures. All 100 self/cash/marketing cases stay accepted; all 100 foreign-brand cases stay excluded. The only changed decision is the intended Samsung omitted-suffix Tier 2 fallback. Every changed decision was inspected; exact before/after records are in `series-fallback-catalog-audit.json`.

## Live marketplace evidence

Read-only calls used the existing direct HTTP APIs, normal pagination budgets and matching pipeline.

- AlfaMall Midea Titan 1 ton: final named-series search found two external exact-QC2 offers, Rs. 163,599 and Rs. 167,999.
- AlfaMall Midea Titan 1.5 ton: final `Midea Titan 1.5 Ton` search found four external exact-QC2 offers, Rs. 215,599–223,349.
- AlfaMall Samsung: a full `55Q7FAA` listing wins as an exact model; no approximate warning is imposed on that exact offer.
- DigiMall Samsung: three `55Q7F` offers reach evaluation as Tier 2 with the missing-`AA` yellow warning; coverage is COMPLETE.

Recorded retry results are in `series-fallback-live-check.json`. An earlier transient model-query timeout suppressed widening as designed; a successful bounded retry verified the Midea 1.5-ton path. API inventory and availability may change. The catalog audit and automated end-to-end tests are offline controls, not a live scan of all 100 products.

## Explicit boundaries

Series fallback requires an explicitly named catalog series and a verified supported capacity. It does not invent a series from arbitrary prose. Candidate brand must be explicit in the title for this approximate stage. Widening is conditional on healthy exhausted model discovery and cannot substitute for a failed request. Approximate series/model matches remain visibly warned, and cannot prove hardware details absent from both listings. The pre-existing large matcher was not rewritten outside the approved fallback scope.
