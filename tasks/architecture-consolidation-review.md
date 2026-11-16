# In-flight adversarial review

Cross-model review was explicitly skipped by the user. Fresh-context subagents reviewed the series boundary and implementation (artifact + contract only).

## Actionable findings and reconciliation

- Model-dependent Glass Door and inherent-T3 exemptions leaked into absent-SKU matching: gated on model basis; regressions cover missing finish and ordinary conflicts.
- Conflict-only category checks did not establish a known family: series preflight now requires positive family evidence on both sides.
- Model matches discovered in own-store series responses must suppress broader external series results: finalization checks all model pools including own stores.
- Early duplicate merging could erase model-basis evidence: representative preference now accounts for basis; overlapping model/series order permutations tested.
- A sold-out model must not beat an available series offer: availability ranks before basis; both arrival orders tested.
- Skipping SKU matching also skipped physical lid checks: lid/physical suffix checks now run in the common pipeline, while SKU-derived inference is disabled for series basis. Clear/Glass conflict and omitted-lid regressions fail against the earlier implementation and pass after correction.

## Approved existing-test corrections

`test_different_model_same_verified_series_is_warned_not_exact` now rejects the explicit different SKU. Synthetic generic-series and full-pipeline export fixtures now omit the candidate SKU when demonstrating valid series fallback. This implements the user's selected stricter policy; separate negative tests retain explicit different-SKU coverage.

The former `test_14k_btu_1_ton_vs_1_25_ton_equivalence` now rejects unequal explicit capacities. This directly implements the user's choice to remove that tolerance; synthetic cross-brand regressions cover the same invariant.

The parser monkeypatch test now patches its canonical `offer_processing.referee_match` owner; its metadata assertion is unchanged. Original scraper parser imports remain delegating compatibility aliases.

## Milestone adjustment

Availability/basis representative preference moved forward from milestone 8 because series priority cannot be correct without it. Milestone 8 still owns distinct identity keys, deterministic ordering and removal of the Digi-only workaround.

## Final independent review and corrections

All following findings were classified valid/actionable and reproduced by failing tests before correction:

- Equivalent spaced/glued manufacturer prefixes inflated counts: use the matcher's structural prefix/core split and complete-pool prefix consensus. Conflicting explicit prefixes never bridge through a bare model.
- Seller display names are not unique identities: honor verified seller handles.
- Nonempty warning metadata and tier could tie by arrival order: preference now orders availability, basis, tier and stable metadata.
- Partial query dedup lost prefix provenance: retain raw external and own-store pools through retrieval/cache and aggregate before finalization. Deduplication requires the complete evidence pool; it is intentionally not a streaming-fold API.
- Same-handle own-store series Tier 2 could shadow an active model Tier 2: preserve raw own evidence until suppression and prefer model basis when own-store duplicates are merged.
- Compact capacity aliases leaked into series text or became a decimal-tail anchor: category cleanup and fallback anchor recognition now consume the shared capacity vocabulary.
- Legacy empty Alfa query strings bypassed finalization after raw-cache separation: preserve the existing single-query retrieval and finalize its result before returning publicly.
- Full regression suite caught old callback result shapes without `sibling_offers`: restored the pre-existing optional-field adapter; existing tests were not altered.

Boundary, implementation, dedup and final-correction reviews were performed by actual isolated subagents. Cross-model review remained skipped by user instruction. All substantiated findings have corresponding tests and corrections; no unresolved finding is accepted as safe by assertion alone.
