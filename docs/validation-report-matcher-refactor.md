# Matcher Refactor — Root Cause Analysis & Validation Report

**Date:** 2026-10-04
**Scope:** `pricing_engine/matcher.py` (full replacement), `pricing_engine/range_pipeline.py`
**Trigger:** `Dawlance 10 KG DWT-1016 INV PR` failing to match, and the base+variant → base
fallback not firing in the range pipeline.

> **Naming note.** There is no module, function, or identifier called `shahid` anywhere in
> this repository (`grep -rni shahid` over `*.py|*.md|*.csv|*.txt` returns nothing). The
> pipeline referred to is **Market Range Mode**, `pricing_engine/range_pipeline.py`, entered
> via `python index.py -r/--range-only`. Everything below about "the range pipeline" means
> that module.

---

## 1. Environment & verification harness

| Check | Command | Result |
| :-- | :-- | :-- |
| Unit suite (baseline, `git stash`) | `pytest` | **257 passed** |
| Unit suite (after fix) | `pytest` | **983 passed** |
| Lint | `ruff check .` | **All checks passed** |
| Types | `mypy pricing_engine/matcher.py pricing_engine/range_pipeline.py` | **0 errors in both files** (6 pre-existing errors remain in `scraper.py` / `exporter.py` / `learner.py`, untouched) |
| Crash sweep | 4,334 real titles × 5 entry points | **0 exceptions** |

**Live API access is not available from this sandbox.** Both endpoints fail at the TLS layer
before any HTTP exchange:

```
https://be.alfamall.com/...            -> SSLError curl:(35) BoringSSL SSL_connect: Connection closed abruptly
https://digimall-be.faysalbank.com/... -> SSLError curl:(35) BoringSSL SSL_connect: Connection closed abruptly
```

So "compare against real API results" was done against the repository's own **recorded live
API capture**, `scripts/live_stress_test_results.json` (916 KB): 10 stress products ×
2 platforms, containing **2,101 raw API items (1,383 unique vendor titles)** together with the
verdict the production matcher returned for each at capture time. That file is real API
output; it is not a fixture I wrote. It is replayed in §4.

---

## 2. Root causes

All four defects are in `matcher.py`. Three of them are independent, and **any one of them
alone** is sufficient to suppress the base+variant → base fallback, which is why the fallback
looked "partially implemented but not functioning".

### RC-1 — A category phrase was being parsed as a product series

`CATEGORY_PATTERNS` (the single vocabulary of "words that are never product identity") had no
entry for `FULLY AUTOMATIC` / `SEMI AUTOMATIC`, and the series-subtraction strip list carried
`TOP LOAD|FRONT LOAD` but not `AUTOMATIC`. Residual subtraction therefore left those words in
the `series` slot:

```
extract_product_slots("Dawlance 10 KG DWT-1016 INV PRIMA Top Load Fully Automatic Washing Machine")
  series = 'PRIMA Fully Automatic'      # should be 'PRIMA'
```

`referee_match` treats the series slot as a **hard, all-tokens requirement**. The vendor's real
listing — verbatim line 21 of `tests/fixtures/selected_100_stress_products.csv` — does not
repeat the words "Fully Automatic":

```
target : Dawlance 10 KG DWT-1016 INV PRIMA Top Load Fully Automatic Washing Machine
listing: Dawlance DWT 1016 INV PRIMA 10 Kg Dark Grey Prima Series DDM Inverter Washing Machine

is_match=False  is_base_match=False
reason="Missing required series tokens for any alternative in 'PRIMA Fully Automatic'"
```

**Cascade:** `is_match=False` **and** `is_base_match=False` means
`scraper._parse_offers_from_raw_items` hits `if not is_exact and not is_base: continue` — the
offer is dropped from *both* buckets. It never reaches the exact list, and it never reaches
the base list, so `_execute_waterfall`'s "Priority 2" fallback branch has nothing to fall back
to. The product degrades to `NO_OFFERS`, and no notice is owed because no fallback occurred.

### RC-2 — The Category-2 modifier scan walked the entire descriptive tail

`extract_product_slots` harvested candidate modifier tokens from **every** word after the
anchor and classified any 2–4 letter word as a guarded hardware capability. On a long vendor
title that reaches past the series name into the prose:

```
"Dawlance DWT 1016 INV PRIMA 10 Kg Dark Grey Prima Series DDM Inverter Washing Machine"
                                            ^^^^^^^^^^^^^ -- DDM harvested as a capability
candidate.guarded_facets.capabilities = {'DDM'}
```

`DDM` is not an upgrade — the stock sheet names this exact machine
`DAW AUTO W/M 1016DDM INV PRIMA` (`tests/fixtures/Stock Holding Report - FINAC - Products -
MainSheet.csv:16`), so `DDM` is part of the vendor's **model designation**. But the referee's
Category-2 rule reads a candidate-only capability as a contradiction:

```
is_match=False  is_base_match=False
reason="Hardware capability mismatch (DDM mismatch): Candidate has extra capability DDM not
        present in target"
```

That branch sets `is_base_match=False` by design, so again the offer is discarded outright.

Verified independently of RC-1 — with `Fully Automatic` removed from the target by hand, the
rejection still fires:

```
target: "Dawlance 10 KG DWT-1016 INV PRIMA Top Load Washing Machine"   -> DDM mismatch
target: "Dawlance 10 KG DWT-1016 INV"                                  -> DDM mismatch
```

### RC-3 — An omitted series was a hard reject, not a base fallback

ADR-002 defines Category-2 semantics as *"exact match if present, fallback if omitted,
collision if extra/different"*. `referee_match` implemented the fallback limb for
`capabilities`, `door_finish` and `is_inverter` — but for the **series** slot it only ever
returned a hard reject. So the "base+variant → base" path never existed for series at all:
that is the precise sense in which the fallback was "partially implemented".

### RC-4 — The range pipeline threw the fallback metadata away

`scraper._execute_waterfall` already does the right thing: it segregates exact from base-model
offers and records `ScrapeResult.active_modifier_fallback`. `pricing_engine/pipeline.py`
(repricing) surfaces it twice — a per-item telemetry line
(`⚠️ MODIFIER '<x>' OMITTED BY MARKET`) and a `NOTICE (DO CROSS-CHECK)` panel.

`range_pipeline.process_range_item_async` passed the `ScrapeResult` straight into
`evaluate_market_range`, which reads only `is_success` and `offers`. The modifier field was
dropped on the floor, and `range_pipeline` imported just two matcher symbols
(`extract_search_query_and_model`, `generate_search_patterns`), so nothing in range mode could
ever print a notice. Range mode also has no `Reason` column to carry it — the terminal is the
only channel available.

Reproduced with a stubbed scraper that explicitly reports a base-model fallback:

```
Alfa: 108,000 - 108,000 (1)  │  Digi: 111,999 - 122,699 (2)
notice present?   False        <-- active_modifier_fallback="INVERTER" was set and ignored
```

---

## 3. What the new implementation does

`matcher.py` was deleted and rewritten (2,691 → 2,445 lines) around one implementation per
concept. The headline change is the referee: 18 hand-written
`if <facet> collides: return MatchDecision(...)` blocks collapsed into a **declarative rule
table** (`_FACET_RULES` / `_POST_FACET_RULES`) driven by a single loop. `MatchDecision(...)`
is now constructed in exactly **2** places (the `_reject` helper and the final accept), down
from 18. Adding a guarded facet is now one row, not one copy-pasted block.

Other duplication removed: safeguard masking (was inlined twice), variant-part parsing
(copy-pasted between `distribute_runs` and `expand_slash_word`), the capacity-stem join regex
(four copies), the unit-suffix regex (three copies), brand-prefix stripping (two copies), the
SaveIN/SVN emitter (two copies), and the tier-emission boilerplate (now `_TierBuilder`).

### Fixes

| ID | Fix |
| :-- | :-- |
| **RC-1** | `_CATEGORY_PHRASES` is now a single tuple compiled once, and includes `FULLY AUTOMATIC`, `SEMI AUTOMATIC`, `AUTOMATIC`, `TOP LOAD`. Category words can no longer reach the `series` slot. |
| **RC-2** | Capability harvesting now stops at the first real word after the anchor. Codes containing a digit (`T3`, `ES8`, `S6`) are unambiguous and are still honoured anywhere; pure-alphabetic codes are guarded only inside the contiguous post-model code run. Separators (`/`, `-`) do not end the run. |
| **RC-3** | `_series_verdict` implements all three Category-2 limbs: covered → pass; **omitted → `is_base_match=True` with `missing_modifier=<series>`**; candidate asserts a different series or sub-series → hard reject. |
| **RC-4** | `range_pipeline` reads `active_modifier_fallback` per platform (`_detect_fallbacks`), marks the live row (`⚠ BASE (INVERTER omitted)`), prints a per-item `CROSS-CHECK` line, and renders a consolidated `RANGED AGAINST BASE MODELS` notice panel. The CSV column contract is unchanged — `S.NO` first, risk alerts last, no new column. |
| **New** | `MatchDecision.tier` / `.usable` give every consumer one vocabulary (`EXACT` / `BASE` / `REJECT`) instead of re-deriving `is_match or is_base_match`. |
| **New** | `extract_search_query_and_model` can no longer return an empty query/model. |

### A fix I deliberately did **not** apply

Gluing a letter prefix onto *any* numeric stem (`DWT 1016` → `DWT-1016`) looks like the obvious
RC-2 companion fix, and I implemented it first. It is wrong: `DMB 4467 SD` is structurally
identical to `DWT 1016 INV`, so the same rule rewrites the minibar SKU to `DMB-4467SD` and
destroys its search patterns (`Dawlance 4467` disappears from tier 1). The prefix merge stays
limited to 1–2 digit capacity codes exactly as before; long stems keep their prefix through
substring containment in the referee. RC-2 alone fixes the reported bug.

---

## 4. Validation

### 4.1 The reported product

| Target / listing | Before | After |
| :-- | :-- | :-- |
| `Dawlance 10 KG DWT-1016 INV PRIMA Top Load Fully Automatic Washing Machine` vs the real listing (fixture line 21) | **REJECT** — `Missing required series tokens … 'PRIMA Fully Automatic'` | **EXACT** — `Accepted: DWT-1016 matched with zero guarded facet collisions` |
| same target vs `Dawlance DWT-1016DDM INV PRIMA 10 KG Washing Machine` | **REJECT** — `DDM mismatch` | **EXACT** |
| same target vs `Dawlance DWT 1016 10 Kg Top Load Washing Machine` (no INV/PRIMA) | REJECT | **BASE**, `missing_modifier='INVERTER'` |
| range pipeline terminal, base fallback present | `notice present? False` | `⚠️ CROSS-CHECK: AlfaMall listings omitted 'INVERTER' → ranged against 1 base model offer` + notice panel |

### 4.2 Replay of 2,101 recorded live-API items (real API titles vs both matchers)

Every recorded vendor title was re-adjudicated by the old and the new matcher against its own
captured target product:

| Verdict change | Count | Assessment |
| :-- | :-- | :-- |
| `REJECT → EXACT` | **30** | Correct. e.g. `Haier HW 105-BD14376PGU1 Front Load Washing Machine` vs `Haier Front Load Fully Automatic Washing Machine 10.5kg (HW 105-BD14376PGU1)` — the identical machine, previously rejected. |
| `REJECT → BASE` | **53** | Correct. Mostly `GREE SPLIT AC 18AITH21B-T3` against listings that omit `T3` — now a base-model fallback *with* a cross-check notice, which is the specified Category-2 behaviour. |
| `EXACT → REJECT` | **0** | — |
| `BASE → REJECT` | **0** | — |

**Zero regressions on real marketplace data; 83 offers recovered.**

Mid-refactor this replay caught two genuine regressions I had introduced, both now fixed and
both covered by a test:

* an *identical* title rejecting (`Haier HRF-216 EBD …` vs itself) because `E-Star` tokenises
  to `E` + `STAR` under a plain `[A-Z0-9]+` scan — series comparison is now
  punctuation-insensitive (`_comparison_words`);
* `TCL 40 Inches Smart | 40S59K` gaining a spurious `IOT` capability, because the original
  set `is_display = True` inside the screen-size branch and my frozen slot context lost that
  mutation.

### 4.3 Whole-corpus differential (4,334 unique titles)

Every product title in `data/inputs/` and `tests/fixtures/` plus every recorded API title:

| Surface | Titles differing | Nature |
| :-- | :-- | :-- |
| `extract_search_query_and_model` | **14 / 4,334** (0.3%) | All intended RC-1 cleanups (`'Fully Automatic DWT-1166-X-ADS'` → `'DWT-1166-X-ADS'`) or the new empty-model guard (`('','')` → a real query). |
| `generate_search_patterns` | **70 / 4,334** (1.6%) | All improvements: the old emitter produced fragments such as `'DF-'`, `'DW'`; these are replaced by real permutations (`'DF 300SD'`, `'DF-300SD'`, `'DF300SD'`). |
| `extract_product_slots` | **780 / 4,334** (18%) | 284 series lose only `AUTOMATIC`/`FULLY`/`TOP LOAD` (RC-1); 518 capability sets lose a distant pure-alphabetic code (RC-2); 35 gain a hyphenated series token now that comparison is punctuation-insensitive. |
| Crashes | **0** | 4,334 × 5 entry points. |

The 518 dropped capabilities were the one change with real downside risk, so it was measured
rather than assumed: variant protection is unchanged because the series slot still carries
`AVANTE`, `PRIMA`, `BD14376`, `LUXE` and `_series_verdict` rejects conflicts there — confirmed
by the 0 `EXACT → REJECT` / 0 `BASE → REJECT` result in §4.2 and by
`test_rc3_contiguous_variant_code_is_still_guarded`.

### 4.4 Tests

| | Count |
| :-- | :-- |
| Baseline suite (unchanged, all still passing) | 257 |
| `tests/test_matcher_fallback.py` — one test per root cause | 20 |
| `tests/test_matcher_corpus_smoke.py` — corpus guards | 706 |
| **Total** | **983 passed** |

---

## 5. Known gaps carried forward

Reported rather than quietly fixed; both pre-date this refactor and are pinned by a
characterisation test so they can only shrink.

1. **42 of 700 corpus titles do not match themselves.** All are non-appliance SKUs — gas
   geysers, garment steamers, pedestal fans, blenders, water purifiers — whose marketing prose
   (`Electric Geyser`, `Touch Panel`, `Evaporative Cooler`) is read as a series name. The
   pre-refactor matcher rejected **57** of the same set, so this is 15 better, not a
   regression. Fixing it properly means a category vocabulary for small domestic appliances,
   which is outside the AlfaMall/DigiMall appliance scope of this change.
   Pinned by `test_self_match_rejects_do_not_grow`.
2. **`SG WATER PURIFIER -` still emits dangling queries** (`'SG -'`, `'-'`). Byte-identical
   output before and after the refactor. Pinned by `test_dangling_search_patterns_do_not_grow`.

---

## 6. Files changed

| File | Change |
| :-- | :-- |
| `pricing_engine/matcher.py` | Replaced. Public API preserved: `extract_search_query_and_model`, `generate_search_patterns`, `extract_product_slots`, `referee_match`, `is_strict_model_match`, `clean_marketplace_noise`, `expand_cartesian_branches`, `expand_multivariant_titles`, `normalize_technical_slashes`, `CATEGORY_1_DIRECT_MATCH_MODIFIERS`, `SAFEGUARD_PATTERN`, `ProductSlots`, `GuardedFacets`, `MatchDecision`. Added: `TIER_EXACT` / `TIER_BASE` / `TIER_REJECT`, `MatchDecision.tier`, `MatchDecision.usable`. |
| `pricing_engine/range_pipeline.py` | `PlatformFallback`, `RangeItemResult`, `_detect_fallbacks`, `_fallback_marker`, `render_range_fallback_notices`; `process_range_item_async` now returns `RangeItemResult`. Output column contract unchanged. |
| `tests/test_matcher_fallback.py` | New — 20 regression tests keyed to RC-1…RC-4. |
| `tests/test_matcher_corpus_smoke.py` | New — corpus crash guard plus the two pinned characterisations. |
| `AGENTS.md` | Range-mode section updated with the cross-check notice. |
