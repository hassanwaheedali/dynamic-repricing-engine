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

## Milestone adjustment

Availability/basis representative preference moved forward from milestone 8 because series priority cannot be correct without it. Milestone 8 still owns distinct identity keys, deterministic ordering and removal of the Digi-only workaround.
