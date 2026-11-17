# PG-M01 Hardware Matching Implementation Report

Date: 17 November 2026. Baseline: `feature/strict-vendor-commission` at `0f81261e6e757950eb421e4ab00dfbb6136b9ffc`.

**Delivery status: completed locally and verified.** Final full offline verification: **1,277 passed, 0 failed, 0 skipped, 0 errors**. The four original iron regression tests pass without edits. The user's clarification removes the incorrectly introduced attached-only restriction: matching separate catalog model codes remain valid evidence. No push, deployment, marketplace request, or database request was made.

## A. Implementation summary

The shared matcher now distinguishes source-attached model components from loose model-adjacent designations. Seller-added loose designations can carry the existing yellow cross-check sentence without becoming hardware capabilities or demoting an otherwise eligible exact match. Catalog-declared separate codes remain comparison constraints, with omissions and conflicting code order protected.

Short hyphenated feature counts cannot supply a model anchor or required series word. Prefix/number formatting no longer manufactures an attached multi-letter suffix from separate source words. WiFi, IOT, Smart and TV OS prose no longer add independent capabilities, contradictions, fallbacks or warnings. Literal SKU components with those spellings remain protected.

The existing notice formatter was centralized and the existing evaluator annotation now includes a selected generic exact advisory in the reason once. Existing terminal and spreadsheet highlighting consume that marker without new renderers or output columns.

## B. Milestones 0–6

| Milestone | Changes and affected functions/files | Executed validation and result | Status / deviation |
|---|---|---|---|
| 0 — Baseline, contracts, protection | Verified branch/HEAD and initial tracked-clean tree; preserved untracked catalogs, checkpoints and investigation documents. Read existing report, matcher, offer processing, evaluator, historical plans and tests. Added expected-behavior tests before fixes. | Archived baseline: **1,128 passed**, Ruff passed, strict package mypy passed. Initial H1 tests reproduced 25 failures; advisory tests reproduced 24 failures. | Complete. Dependency installation initially unavailable; user authorized isolated `.venv`, then existing requirements were installed without changing global Python or dependency files. |
| 1 — Structural interpretation | `extract_search_query_and_model`, `_has_model_anchor`, `_strip_category_measurements`, `_adjacent_model_tags`, `_model_tag_from_source`, `extract_product_slots`, additive `ProductSlots.model_tags`. Source position, attachment and ordering retained; false count anchors and synthetic suffixes removed. | Structural tests pass, including compact/spaced counts, loose ECO/ET/XYQ, genuine suffixes, short-model aliases, spaced/bound/mixed code sequences and later-prose omission controls. | Complete. Independent review exposed order and spelling gaps; failing tests were added before correcting them in canonical extraction. |
| 2 — Connectivity prose | Existing capability scanner no longer recognizes connectivity; shared prose cleanup protects literal model spans. Removed TV OS inference and late connectivity fallback branches. | Disabled forms on both sides, TV OS variants, contradictions and literal prefix/suffix controls pass. | Complete in the shared referee pipeline. Legacy matcher replacement remains out of scope. |
| 3 — SKU evidence and residual feedback | `_complete_sku_evidence_level` uses matching catalog model codes, spaced or attached, and encoded color rather than arbitrary capability sets. Seller-only observations remain outside hardware and required series. Matcher policy advanced once to `product-evidence-v8-model-tag-provenance`. | All four unchanged iron regressions pass, as do generic CX/ET/XYQ separate-code aliases. Candidate-only ECO cannot qualify unrelated series; genuine model, variant, E-Chrome, capacity, color and T3 conflicts remain rejected with extra or shared ECO. | Complete. The user corrected the implementation's attached-only interpretation; it was removed instead of weakening iron tests or adding a product exception. |
| 4 — Existing cross-check flow | `_cross_check_notice` owns the existing sentence; exact advisories use `compatibility_notice`. `_apply_compatibility_and_fallback_annotations` propagates selected generic notices once. | Selected/unselected offers, stock, floor filtering, equivalent duplicates, true base/sibling and retained T3 cases pass. Actual card, summary, CSV and XLSX checks pass; warned reason cells use existing yellow `00FFF9C4`. | Complete. No renderer, selector or schema added. |
| 5 — Matching and price pools | Added six mocked HTTP replays through actual Alfa/Digi scraper entrypoints. Both Mega Flex 15/30 capacities, lower Smart Frequency prices, wrong-capacity exclusion and exact ECO warning reach real evaluation. | All six pass. Existing real-payload, market-range, learning metadata and both-platform iron integrations also pass. | Complete; existing finalizer and pricing math preserved. |
| 6 — Regression protection | Four focused test modules, existing policy-specific expectation updates, exact eight-row query-delta fixture, offline corpus comparison and independent actual-code review. | **335 focused passed**. Final full suite: **1,277 passed / 0 failed / 0 skipped**. Ruff and strict package mypy pass. | Complete. Final independent review found no additional confirmed issue after source-order corrections. |

## C. Root causes corrected

**H1: structural nomination was being used as semantic proof.** A token passing the generic short-code predicate previously entered the hardware capability set. The same set also strengthened SKU evidence. Source normalization joined separate words into apparent suffixes before their origin could be checked. Count tokens could survive tag splitting as a bare number, or their remaining word could enter required series.

The matcher now records a source-observed code with its position and attachment, then orders the observations once by source position. Bound-code and separate-designation views derive from that one sequence. Matching catalog-declared codes remain valid model evidence whether spaced or attached, without being described as independently verified manufacturer facts. A candidate-only observation can receive an advisory only after existing model, series and physical checks pass. A seller-only extra word cannot qualify `_complete_sku_evidence_level`.

Count recognition has one shared structural pattern, used in specification exclusion and category/series cleanup. Post-split model validation requires surviving numeric model evidence. Separate multi-letter suffixes remain separate during query formatting. The pre-existing single-letter/color formatting contract remains.

**H2: connectivity had multiple decision paths.** The polarity scanner, Smart-to-IOT conversion, TV OS inference and late missing/extra checks previously produced inconsistent exact/base/reject outcomes. Those independent criteria are disabled together. Shared cleanup excludes their prose without erasing actual model components. Existing technical spelling normalization is reused when establishing original attachment, including `WI-FI-5432-ES`.

An intermediate attached-only interpretation broke the iron fixtures. The user explicitly rejected that interpretation. The corrected qualification recognizes matching catalog codes and preserves existing descriptive tolerance while all genuine model, series/edition and physical conflict checks continue to run. No CX/ECO-specific exception or new strict suffix policy was introduced.

## D. Before versus after

Actual matching comparisons are saved in [the comparison JSON](evidence/hardware_matching_implementation_comparison.json). A dash means rejection/no match tier.

| Case | Baseline | Current classification / tier | Current observed reason and notice |
|---|---|---|---|
| Mega Flex 30 Smart Frequency | BASE_MATCH / 2; inferred IOT | ACCEPTED / 1 | `Accepted: Mega Flex matched with zero guarded facet collisions`; no connectivity warning. Mega Flex 15 is also covered by both scraper replays. |
| Glacier Pro 45 T3 + 4-Way | FACET_CONFLICT / —; false WAY | ACCEPTED / 1 | `Accepted: Glacier Pro matched with zero guarded facet collisions`; no count warning. |
| Bare DWT-1165 versus seller ECO | FACET_CONFLICT / — | ACCEPTED / 1 | `Accepted: DWT-1165 matched with zero guarded facet collisions`; existing `CROSS-CHECK NOTICE: Market listing includes 'ECO' not specified in target catalog`. No advisory-only missing modifier/base/verified variant. |
| MD 15 versus spaced MD 15 ECO | MODEL_CONFLICT / —; fabricated MD-15ECO | ACCEPTED / 1 | `Accepted: MD-15 matched with zero guarded facet collisions`; same existing ECO advisory. |
| Catalog DWT-1165 ECO versus bare candidate | BASE_MATCH / 2 | BASE_MATCH / 2 | Catalog omission remains a real fallback; `missing_modifier == 'ECO'`. |
| Declared ES versus ES8 | FACET_CONFLICT / — | FACET_CONFLICT / — | `Hardware capability mismatch (ES8 mismatch): Candidate has extra capability ES8 not present in target`. |
| T3 versus T4 | FACET_CONFLICT / — | FACET_CONFLICT / — | `Hardware capability mismatch (T4 mismatch): Candidate has extra capability T4 not present in target`. Existing omission, optional and prose-versus-bound T3 controls also pass. |
| Same TCL model, Smart versus Non-Smart prose | FACET_CONFLICT / — | ACCEPTED / 1 | `Accepted: 32S5400 matched with zero guarded facet collisions`; no Smart warning. |
| Selected exact ECO advisory | Formerly no eligible offer | Exact offer remains tier 1 | Both evaluator reasons contain the existing notice once; CSV contains it once; existing XLSX yellow fill and terminal summary/card show it. An unselected warned offer does not contaminate a clean winner. |
| Existing DWSI 2322 CX iron, descriptive listing | ACCEPTED / 1 | ACCEPTED / 1 | `Accepted: DWSI-2322 matched with zero guarded facet collisions`. Existing separate-code, metadata-brand, duplicate, range and both-platform pricing regressions are preserved. |

Mega Flex raw replay previously selected only Home Cart at **164,499** because Electronics World at **154,255** was demoted. Both now enter the exact pool, ordered 154,255 then 164,499. No pricing mathematics changed.

### Additional CX confirmation before production

A subsequent read-only adversarial confirmation compared baseline and final source using the same target, `Dawlance DWSI 2322 CX Handheld Corded Garment Steam Iron`. All four outcomes below are unchanged from baseline:

| Candidate | Actual final outcome |
|---|---|
| `Dawlance DWSI 2322 CX Steam Iron` | Tier1, ACCEPTED, no compatibility warning |
| `Dawlance DWSI 2322 Steam Iron` | Tier2, BASE_MATCH, existing yellow `FALLBACK MODEL` notice identifying omitted CX |
| `Dawlance DWSI 2322 CY Steam Iron` | Rejected, FACET_CONFLICT; different code is not an omission fallback |
| `Dawlance DWSI 2323 CX Steam Iron` | Rejected, MODEL_CONFLICT; different numeric model cannot be rescued by CX |

No CX-specific production conditional exists. Generic tests also substitute CX, ET and XYQ across spaced/attached forms. Current production file bytes were checked against the final full-suite source copy and matched exactly. This confirmation did not change production code or rerun the unchanged full suite.

## E. Regression evidence

### Executed results

| Check | Actual result |
|---|---|
| Baseline full offline pytest | 1,128 passed, 0 failed/skipped; 52.60 seconds pytest time |
| Final focused matcher/notice/output/scraper/model-identity/polarity modules | 335 passed, 0 failed/skipped/errors; 14.839 seconds |
| Final full offline pytest | **1,277 passed, 0 failed/skipped/errors**; 70.45 seconds |
| `ruff check . --no-cache` | Pass in isolated copy and actual workspace |
| `mypy pricing_engine --strict` | Pass, 19 source files |
| New tests and evidence-script formatting | Five files pass `ruff format --check` |
| Full-tree formatting | Pre-existing 24-file failure reproduced in baseline. New files were formatted; unrelated baseline files were left unchanged. |
| Full-tree `mypy .` | Baseline and current both stop on duplicate module names `conftest` / `tests.conftest`; not claimed green. |
| Dependency files | Unchanged. Existing requirements installed only in the authorized `.venv`. |
| Offline protection | Isolated archive/overlay without `.env`; Python socket and native curl guards active, credentials not loaded, **zero external call attempts** in final full run. Child processes inherited guards. |

Final full logs and JUnit: `scratch/hardware-corrected-source/scratch/hardware-complete-checks/`. Focused JUnit: `scratch/hardware-ordered-codes-focused.xml`. Baseline logs: `scratch/offline-baseline-20261117_150233/source/scratch/baseline-checks/`. Quality comparison: `scratch/hardware-quality-comparison/`. Earlier failing runs remain available as intermediate diagnostic history; they are not the final result.

### Differential results

- All 100 curated catalog self-matches remain Tier1.
- All 500 controlled prose appends now remain Tier1: 100 each for Smart Frequency, WiFi, Without WiFi, 4-Way Air Throw and Premium Performance.
- Exactly 84 append decisions change as intended: 35 Smart demotions, 35 WiFi demotions and 14 count rejections become exact. The other 416 remain exact.
- All 28 retained alias, model, series, physical, polarity, color, capacity, T3, base/sibling and cross-series controls pass.
- Eight query rows change for reviewed source-separation/false-anchor reasons. The historical architecture snapshot is unchanged. `tests/fixtures/hardware_query_regressions.json` records each exact output and rationale; remaining catalog query outputs remain asserted against the historical snapshot.
- Original evidence JSON remains intact. Post-change replay: [hardware_matching_after.json](evidence/hardware_matching_after.json). Same-input diagnostic: `python -B docs/evidence/hardware_matching_offline_probe.py --after`.

### Intermediate failures resolved

An intermediate attached-only implementation broke these existing tests. All four now pass **without changing their assertions**:

1. `test_real_exact_models_survive_descriptive_differences[iron]`
2. `test_brand_evidence_survives_scraping_for_learning`
3. `test_real_payloads_reach_market_range_and_pricing[alfa-iron]`
4. `test_real_payloads_reach_market_range_and_pricing[digi-iron]`

The target is `Dawlance DWSI 2322 CX Handheld Corded Garment Steam Iron`. Candidate examples include `Dawlance Dwsi 2322 CX Steam Iron Fast and efficient ironing` and metadata-branded `Efficient Steam Iron DWSI 2322 CX`. Their matching catalog-declared CX now qualifies the shared numeric SKU independently of source spacing. CX remains model-code evidence rather than being put back into hardware capabilities. The downstream brand metadata, duplicate, range and both-platform pricing cases are restored by that same shared correction.

The initial review challenged shared ECO on both catalog and candidate. Treating every such shared code as invalid introduced a requirement the user had not requested. That finding's attached-only recommendation was withdrawn after the user clarified that valid separate catalog codes must remain supported. The invented test was corrected to assert the actual rule: **candidate-only** ECO cannot turn an unrelated series-uncertain result into qualified identity. Additional tests assert that extra or matching declared ECO cannot override different numeric models, ES/ES8, E-Chrome/Chrome/Chrome Pro, T3/T4, explicit color or capacity conflicts.

The user's clarification supersedes the earlier bound-only sentence in Part I, which has been corrected. No new policy approval is pending and no known acceptance blocker remains. Matching catalog codes preserve existing descriptive tolerance; this does not claim that arbitrary prose differences prove a genuine manufacturer variant. Existing explicit model, edition, series and physical safeguards remain the authority for genuine conflicts.

### Independent review

Actual-code review identified issues in code order, later prose satisfying declared codes, Wi-Fi attachment, literal disabled-prefix preservation, short-model aliases and count series leakage. Reproducing tests were written and corrections applied. Further review after the user's clarification found compound-code extraction recording construction order instead of literal source order, and separate `ES-PL`/`ES_PL` being treated as omissions. The shared extraction now records source position, preserves all-code delimiter sequences and orders them once. Tests cover both correct ordering and rejection of reversed/conflicting codes across spaced, attached and mixed forms.

Review was performed by separate same-model agents, not an external manufacturer expert or a cross-model service. After the latest fixes the independent reviewer reported **“No additional confirmed findings in the revised helpers or shared-code qualification logic.”** The primary agent then ran the final full offline checks on the reviewed source.

## F. Architecture health

The matcher remains the sole interpretation owner. No hardware parser was added to offer processing, scrapers, evaluator or exporters. Ordered tag provenance is a small additive internal structure with a default field, preserving existing `ProductSlots` construction. Public scraper, evaluator, CLI and output schemas remain compatible.

The existing cross-check sentence has one owner. The existing winning-offer notice selector and exact > base > sibling finalizer are unchanged. Existing card, summary and spreadsheet marker detection remain unchanged. Only shared evaluator notice annotation changed; no commission, profit, shipping, floor, psychological price or other financial calculation changed.

No new model-specific or brand-specific exception, category map or hardware ontology was added. Feature counts and attachment handling use generic structure. Disabled connectivity vocabulary is owned by one shared prose pattern. Scope still excludes the legacy Boolean matcher overhaul.

### Phase 2 Architecture Compatibility & Hardware Matching Integration

The separate Phase 2 Starting Plan remains unavailable, as documented in the forensic report. The supplied master audit lacks the promised later parts; the user had authorized proceeding with available evidence. No missing roadmap definitions have been invented.

Existing historical polarity and physical guards remain in their current owners. The AGENTS Supabase-history/CLI Phase 2 work has no dependency on this local correction and was not implemented. Later matching work can consume the additive ordered provenance while retaining existing `MatchDecision`/offer interfaces. PG-M01 has been verified **before** a larger architecture rollout. Reintroducing arbitrary capability-set qualification or an attached-only restriction in a later Phase 2 refactor would recreate the demonstrated defects; duplicating a downstream matcher to compensate would also be inappropriate.

The iron cases now pass under the clarified existing-code contract. No registry, category ontology, separate matcher, historical snapshot rewrite or speculative series redesign was needed.

## G. Residual risks

- **No known immediate acceptance blocker:** final required pytest, Ruff and package mypy checks pass. Full-tree formatting and full-tree mypy have the reproduced pre-existing limitations noted above.
- **H3 unchanged:** no expanded NO/NOT/WITHOUT inverter recognition, target-side symmetric ambiguity or general scalar contradiction rewrite. Existing working inverter controls remain.
- **H4 unchanged:** single-capacity representation, litre recognition and independent tap/volume/quantity problems remain.
- **H5 unchanged:** no new capacity requirement for ordinary anchorless series identity. Existing sufficiency limits remain.
- General numeric-component boundaries, multiple-model ambiguity, Glamour+ fallback, legacy matcher architecture, ownership classification, alias-registry and scraper redesign remain deferred.
- Offline fixtures establish tested behavior, not complete manufacturer specifications or proof of every marketplace title's identity. There is no guarantee against every future input problem.

## H. Delivery inventory and status

Production files modified locally:

- `pricing_engine/matcher.py`
- `pricing_engine/evaluator.py`

Existing tests updated only for reviewed extraction/notice/connectivity policy changes:

- `tests/test_architecture_contract.py`
- `tests/test_audit_remediations.py`
- `tests/test_forensic_regressions.py`
- `tests/test_generic_variants_and_polarity.py`
- `tests/test_haier_benchmark.py`
- `tests/test_matcher.py`
- `tests/test_pipeline_resilience.py`

Added implementation test/fixture files:

- `tests/test_hardware_interpretation.py`
- `tests/test_hardware_advisories.py`
- `tests/test_hardware_output.py`
- `tests/test_hardware_scraper_integration.py`
- `tests/fixtures/hardware_query_regressions.json`

Documentation/evidence delivered or updated in this implementation:

- `docs/HARDWARE_MATCHING_IMPLEMENTATION_REPORT.md`
- `docs/HARDWARE_MATCHING_FORENSIC_AUDIT_AND_FIX_PLAN.md` (user clarification and superseded attached-only wording corrected; historical source findings retained)
- `docs/evidence/hardware_matching_offline_probe.py` (explicit `--after` replay and richer diagnostic output)
- `docs/evidence/hardware_matching_after.json`
- `docs/evidence/hardware_matching_implementation_comparison.json`

The master audit, original baseline evidence, historical plans, original architecture snapshot, user-owned input catalogs and checkpoints were preserved. The focused plan was updated only to reflect implementation authorization and the user's explicit clarification. Tests that write pipeline outputs/checkpoints ran in disposable source copies; focused output tests used temporary paths. Local isolated `.venv` and ignored scratch verification artifacts were created. No user files were deleted and no branch was switched. The user subsequently authorized local commits; no push or deployment occurred.

**Implementation completed locally.** Final result: **1,277 passed, 0 failed, 0 skipped**; Ruff and strict package mypy pass. No remaining implementation blocker. Implementation commit: `ce4d65b`. Supporting documentation/evidence are delivered in a separate local commit. No push or deployment was performed.
