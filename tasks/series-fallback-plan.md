# Model-first series fallback plan — 2026-11-16

1. Reproduce Samsung base-suffix, Midea series retrieval and bad API-tag failures with offline tests.
2. Add a warned capacity-led missing-suffix match, preserving size/family/generation and excluding manufacturer-led washer suffixes.
3. Add one final brand/explicit-series/capacity search, conditional on zero active model matches. Keep normal and series matching caches separate and raw responses reusable.
4. Require positive brand, whole-series and capacity evidence; reuse existing category, mounting, physical capability, polarity and color checks. Never reinterpret a wrong series as a matching product.
5. Test both platforms, own stores, stock, caches, network failures and exact-model priority; verify pricing/range integration and actual live examples.
6. After the bug fix is green, simplify only the new paths and review correctness, readability, architecture, security and performance. Record resolved findings and final checks in the review artifact.

Acceptance: Samsung 55Q7F has a yellow base-model notice; Midea series discovery works only after model discovery fails; no brand/capacity/hardware mixing; genuine no-match retains monopoly policy. Existing staged work is preserved. No deployment, database write or price upload is authorized or needed.

Completed: all six steps. Final review is `series-fallback-review.md`; 33 focused tests and all 807 tests pass, Ruff and strict Mypy pass, and changed executable-line coverage is 96.92%. Both pipeline modes and their temporary exports are verified. Live checks confirm Samsung DigiMall yellow fallback and Midea AlfaMall named-series retrieval.
