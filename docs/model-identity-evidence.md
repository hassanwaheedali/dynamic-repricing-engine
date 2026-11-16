# Model identity and marketplace evidence

Implemented on 2026-11-16 to resolve false rejections of DWSI 2322 CX,
Samsung WA80CK4240BWRT, Gree GS-18PITH17G-T3, and DWMM 6001 W.

## Evidence precedence

- Extract structural SKU spans before classifying ambiguous measurements.
  `DWMM - 6001W` is a model; a subsequent independent `600 W` is a measurement.
- Preserve the complete model, its significant suffixes, and explicitly stated
  physical attributes. A secondary family code cannot supply a single-letter
  variant for a different primary model.
- A specific matching SKU tolerates different ordinary descriptions. Numeric
  base stems still require their genuine series/edition identity. Existing
  attached variants, explicit capabilities and negations, capacity differences,
  and fallback tiers retain their guards.
- Generic variant inference is confined to the contiguous model-adjacent code
  sequence. Categories, measurements, prose, and seller delimiters terminate
  that sequence. Unknown words following an already self-contained alphanumeric
  SKU do not establish an extra hardware edition.
- All downstream guards use the normalized product title, including category,
  mounting, color, brand, series, and hardware checks. Removed seller clauses
  and promotional phrases cannot re-enter those checks.
- An explicit leading catalog brand in the normalized title takes precedence
  over a contradictory storefront brand tag. When the title does not establish
  the brand, API metadata remains a rejection guard. Accepted offers retain the
  verified catalog brand for subsequent learning.
- Named colors and independently supplied codes have separate provenance from
  a color inferred from a SKU. The same encoded variant cannot become a color
  mismatch solely because a generic suffix map translates it differently.
  Conflicting named colors and independent opposing codes remain excluded.
- Explicit marketplace brand metadata is checked against the catalog brand.
  It can establish the brand of a title beginning with descriptive prose.
  Without that metadata, brand checks remain conservative; catalog brands are
  never guessed from a title.

## Compatible interface additions

- `ProductSlots.normalized_title` preserves the shared product evidence before
  internal SKU decomposition.
- `GuardedFacets.color_source` distinguishes `none`, `explicit`, `code`, and `sku`.
- `referee_match(..., candidate_brand="")` optionally accepts explicit API brand
  evidence. Existing positional arguments and boolean/tier contracts remain.
- `MatchDecision.reason_code` and `detected_variant` carry machine-readable
  decisions. Display wording does not control rejection classification or
  market-variant ambiguity detection.
- `ScrapedOffer.brand_name` preserves brand evidence for subsequent learning.
- `ScrapeResult.rejected_examples` contains at most five stable examples,
  including title, parsed model, reason code, readable reason, and actual query.
  Digi query audits also retain these examples. Terminal summaries show relevant
  rejection evidence and avoid attributing an aggregate tier count to one query.
- `MATCHER_POLICY_VERSION` participates in every platform's checkpoint
  fingerprint; the existing Digi discovery policy version remains independent.

## Verification and boundaries

The regression JSON contains minimal offline payloads using confirmed public API
titles/prices; local identifiers are used where the diagnostic did not retain the
marketplace ID. Both scraper paths are tested against these payloads. These tests
do not imply that every fixture listing exists on both marketplaces.

The 100-product audit compares against the staged matcher before this change:
100/100 self-matches remain compatible; appending `CASH` or the tested campaign
phrases preserves 100/100 matches; replacing the title brand rejects 100/100.
All 139 changed decisions occur in the marketing probes. See the separate audit
for each changed title and its before/after reason.

The existing monopoly fallback and coverage policy are retained. Price math,
shipping, query/page limits, commission floors, and upload column contracts are
unchanged. No production repricing run or catalog edit is part of this fix.

## Final validation

- `pytest -q`: 769 passed. The existing 26 Windows/curl event-loop warnings remain.
- `ruff check .`: passed.
- `mypy pricing_engine --strict`: passed for all 16 source files.
- `git diff --check`: passed.
- Changed executable-line coverage: 399/441 (90.5%), measured with the standard-library trace hook across the full suite against the staged baseline. This includes existing unstaged changes in the affected modules; it is not whole-project coverage.
- Live AlfaMall checks: DWSI returned all four offers, Samsung returned nine
  distinct offers, and the mincer returned one offer after duplicate aggregation.
- Live DigiMall checks: Samsung returned two exact-model offers; Gree returned
  four external offers and one separate own-store listing using the first planned
  query. The existing three-page scan still reports capped coverage honestly.

Existing staged changes were preserved. No price upload, database write, or
production repricing/export run was performed.

## Model-first fallback follow-up — 2026-11-16

The original full-anchor rejection discarded `55Q7F` before the missing `AA`
suffix could produce a yellow notice. Search planning also lacked a validated
base query. A shared structural rule now requires a capacity-led model with
retained family letters, generation digits and final family letter, matching
explicit capacity, and an omitted trailing alphabetic suffix. It creates a
Tier 2 warning. Opposing suffixes, different sizes/families and manufacturer-led
washer suffixes remain protected. Both marketplaces use this same rule to
generate the base query; no Samsung-specific branch is present.

Named-series discovery is a separate final stage, shared through
`pricing_engine/series_fallback.py`. It requires an explicitly named catalog
series and capacity. After model discovery succeeds without any compatible
in-stock model, including an own-store model, it issues one final query containing
the catalog brand, series and capacity. Failed/incomplete model requests do not
authorize widening. Existing query pagination caps remain unchanged.

The series referee requires an explicit leading catalog brand, the complete
named series as words, and equal verified capacity. It substitutes model
identity only and reuses the normal category, mounting, color, hardware and
negation guards. Different compatible models carry a yellow Tier 2 warning.
An exact SKU discovered through a series query remains Tier 1 and takes
priority. Approximate offers never establish synonym-learning observations.

Strict and series matching have separate evaluation cache keys; the raw HTTP
response is reusable across modes. Every model query tier precedes the series
stage. `product-evidence-v2-series` invalidates old matching checkpoints on all
platforms. Pricing formulas, shipping, commission rules, genuine no-match
monopoly behavior, and marketplace coverage policies remain unchanged.

See `tasks/series-fallback-review.md` for the follow-up review, pipeline tests,
catalog audit and live marketplace evidence. Earlier validation figures above
describe the preceding implementation and are retained as history.
