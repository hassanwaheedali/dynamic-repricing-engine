# Architecture consolidation contract — 2026-11-17

Baseline: 6a66118a70b8aa687f5a395a28a00f5b6147bebf. User authorized implementation; cross-model review explicitly skipped. Fresh-context adversarial review remains required.

## Behavior

- One matcher pipeline owns identity and physical compatibility. Normal exact/base/sibling rules remain model based.
- Series fallback never replaces target identity. Only absent candidate SKU, explicit brand, equal complete normalized series and verified equal capacity qualify. Explicit category, mounting, color, hardware and polarity conflicts reject.
- Missing Inverter remains permitted. Existing feature omission policy remains. Missing catalog color is permitted only with a yellow series warning.
- Equal normalized numeric capacities (1 / 1.0) match; unequal capacities (1 / 1.25, 8 / 8.5) reject. Preserve three-digit screen sizes.
- Protect structural model spans before removing measurements. No brand/model exceptions.
- Preserve DigiMall ordered model-first brandless queries, three-query branch budget, pagination and coverage policy. One separate series query is eligible after healthy model exhaustion. CAPPED/UNKNOWN may widen; FAILED/INCOMPLETE may not.
- Active model matches, including own stores, suppress series widening. A model found in a series response retains model priority.
- Shared deduplication prefers available copies, preserves distinct identities/vendors/colors/variants and own-store separation, and counts duplicates correctly.
- Pricing math, commissions, shipping charges, output columns and public scraper signatures stay compatible. Behavior changes invalidate checkpoints.

## Milestones and verification

1. Persist contract/task list and reproducible query/matching/shipping/pricing baseline.
2. Canonical Decimal capacity definitions; matcher and series consumers; regression tests.
3. Shared legitimate series path, original identity and explicit basis; both-platform tests.
4. Generic model/measurement span protection; synthetic examples and existing suffix guards.
5. Shipping consumes shared units/normalization without changing extraction policy or charges.
6. Public shared model-first query generation; preserve ordered DigiMall snapshots.
7. Shared offer processing/finalization; remove artificial async callback.
8. Stock-aware identity-safe deterministic deduplication; remove Digi-only workaround.
9. Move shared transport contracts/configuration to leaf owners with compatible aliases.
10. Remove reverse transport imports; preserve retries/caching/pagination diagnostics.
11. Policy invalidation, differential evidence, fresh imports, adversarial review, full quality gates.

Every behavior correction is test-first; focus tests per milestone, wider checkpoints after 3/6/10, full suite at completion. Each verified slice is separately committed. Roll back dependent commits in reverse order and recompute checkpoints; do not silently restore unsafe fallback.

Baseline gates: 807 tests pass; Ruff and strict engine mypy pass. Full-repo formatter has 25 existing failures; `mypy .` has duplicate conftest-module discovery. These remain reported limitations, not unrelated cleanup work.
