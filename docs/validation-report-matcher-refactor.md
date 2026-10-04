# Matcher Refactor — Root Cause Analysis & Validation Report

**Date:** 2026-10-04
**Scope:** `pricing_engine/matcher.py` (full replacement), `pricing_engine/range_pipeline.py`,
`scripts/corpus_harness.py`, `tests/test_matcher_fallback.py`, `tests/test_matcher_corpus_smoke.py`
**Trigger:** `Dawlance 10 KG DWT-1016 INV PR` failing to match, and the base+variant → base
fallback not firing in the range pipeline.

> **Naming note.** There is no module, function, or identifier called `shahid` anywhere in this
> repository. The pipeline referred to is **Market Range Mode**, `pricing_engine/range_pipeline.py`,
> entered via `python index.py -r/--range-only`.

---

## 1. Results

| Check | Result |
| :-- | :-- |
| `pytest` | **257 → 12,275 passed** |
| `ruff check .` | **All checks passed** |
| `mypy pricing_engine/matcher.py pricing_engine/range_pipeline.py` | **0 errors** in both (repo total 8 → **6**; the 2 removed were in the old matcher) |
| Corpus crash sweep — 2,997 titles × 6 entry points | **0 exceptions** |
| Corpus self-match — every product vs its own title | **173 failures → 0** |
| Corpus search-query / model-code empties | **0** |
| Corpus dangling queries (`''`, `'SG -'`) | **2 → 0** |
| Category phrase leaking into the `series` slot | **0** |
| Replay of 1,736 recorded live-API items, old vs new matcher | **0 downgrades**, 43 recoveries |

**Live API access is unavailable from this sandbox** — both endpoints fail at the TLS layer
before any HTTP exchange:

```
https://be.alfamall.com/...            -> SSLError curl:(35) BoringSSL SSL_connect: Connection closed abruptly
https://digimall-be.faysalbank.com/... -> SSLError curl:(35) BoringSSL SSL_connect: Connection closed abruptly
```

So API comparison uses the repository's own recorded capture,
`scripts/live_stress_test_results.json` (916 KB): 10 stress products × 2 platforms, 1,736 unique
raw vendor titles with the verdict the production pipeline returned for each.

---

## 2. What the corpus sweep actually covered

`scripts/corpus_harness.py` reads **every string column of all 12 input/fixture CSVs**:

| File | Unique titles |
| :-- | :-- |
| `tests/fixtures/test product list.csv` | 1,352 |
| `tests/fixtures/Stock Holding Report - FINAC - Products - MainSheet.csv` | 743 |
| `data/inputs/Dawlance_Products_List.csv` | 268 |
| `data/inputs/sample_test_products.csv` | 262 |
| `data/inputs/Haier_Products_List.csv` | 212 |
| `tests/fixtures/selected_100_stress_products.csv` | 99 |
| `tests/fixtures/Haier_Washing_Machines_Uploading_and_Price.csv` | 36 |
| `tests/fixtures/Gree_Uploading_on_DigiMall_and_Price.csv` | 25 |
| **Total unique** | **2,997** (51 distinct brands) |

Two harness bugs had to be fixed before this meant anything:

1. **Column 0 is usually not the title.** `data/inputs/Haier_Products_List.csv` starts
   `S.No,Brand,Name`; `Stock Holding Report …csv` starts `Item Name,Brand,Warehouse,Category`.
   A first-column-only sweep fed the matcher brand names (`Dawlance`) and category words
   (`Washing Machine`) and silently skipped the real titles. The harness now resolves
   `Name` / `Item Name` by header and pairs each with that row's own `Brand` column.
2. **Sampling hid the problem.** An earlier 700-title sample reported 42 self-match failures.
   The full corpus has **173**. The sample also missed every `ELite`, `NASGAS`, `Hanco` and
   `Super Asia` failure. Nothing in this report is sampled any more.

---

## 3. Root causes

### RC-1 — A category phrase was parsed as a product series

`CATEGORY_PATTERNS` had no entry for `FULLY AUTOMATIC` / `SEMI AUTOMATIC`, so residual
subtraction left them in the `series` slot:

```
extract_product_slots("Dawlance 10 KG DWT-1016 INV PRIMA Top Load Fully Automatic Washing Machine")
  series = 'PRIMA Fully Automatic'      # should be 'PRIMA'
```

The referee treats `series` as an all-tokens **hard** requirement, and the real listing
(`tests/fixtures/selected_100_stress_products.csv:21`) does not repeat those words:

```
is_match=False  is_base_match=False
reason="Missing required series tokens for any alternative in 'PRIMA Fully Automatic'"
```

**Cascade:** `is_base_match=False` means `scraper._parse_offers_from_raw_items` hits
`if not is_exact and not is_base: continue` — the offer leaves *both* buckets, so
`_execute_waterfall`'s Priority-2 fallback has nothing to fall back to. The product degrades
to `NO_OFFERS` and no notice is owed because no fallback occurred.

### RC-2 — The Category-2 modifier scan walked the whole descriptive tail

Any 2–4 letter word after the anchor became a guarded hardware capability, so a vendor's
fuller SKU suffix was read as an upgrade:

```
"Dawlance DWT 1016 INV PRIMA 10 Kg Dark Grey Prima Series DDM Inverter Washing Machine"
candidate.guarded_facets.capabilities = {'DDM'}
reason="Hardware capability mismatch (DDM mismatch): Candidate has extra capability DDM"
```

`DDM` is part of the model designation — the stock sheet names this machine
`DAW AUTO W/M 1016DDM INV PRIMA` (`Stock Holding Report …csv:16`).

### RC-3 — An omitted series was a hard reject, not a base fallback

ADR-002 defines Category-2 as *exact if present, fallback if omitted, collision if different*.
The fallback limb existed for `capabilities`, `door_finish` and `is_inverter` but never for
`series`. That is the precise sense in which the fallback was "partially implemented".

### RC-4 — The range pipeline threw the fallback metadata away

`scraper._execute_waterfall` correctly segregates exact from base-model offers and records
`ScrapeResult.active_modifier_fallback`; `pipeline.py` prints it twice. But
`range_pipeline.process_range_item_async` passed the result straight to `evaluate_market_range`,
which reads only `is_success` and `offers`. Reproduced:

```
Alfa: 108,000 - 108,000 (1)  │  Digi: 111,999 - 122,699 (2)
notice present?   False        <-- active_modifier_fallback="INVERTER" set and ignored
```

### RC-5 — A digit list was expanded as two independent variant axes

Found by the corpus sweep. `expand_cartesian_branches` regex-matched the first two `X/Y` pairs
and took their cartesian product. For an adjacent run the "middle" is just `/`, so:

```
GS-24PITH15/16/17/18G-T3   ->  "GS-24PITH15/17"   and   "16/18G-T3"
```

Those are **model codes that exist on no marketplace**. The product could not be searched and
could not match itself. Now:

```
GS-24PITH15/16/17/18G-T3   ->  GS-24PITH15G-T3, GS-24PITH16G-T3, GS-24PITH17G-T3, GS-24PITH18G-T3
```

### RC-6 — A multi-variant anchor rejected its own branches

`referee_match` expands the candidate into branches first, so the candidate presents as
`HSU-13HFS(G)` while the target keeps `HSU-13HFS/013WDC(G)`. Three separate rules then fired
against the product's own listing:

* `_anchor_tag_collision` read the differing trailing runs as `Variant tag collision:
  HSU13HFS013WDCG vs HSU13HFSG`;
* the numeric-count heuristic compared `['13','013']` with `['13']` and failed;
* `_series_verdict` was handed `series='13HFS / 013WDC'` — fragments of the anchor itself.

Fixed with `_is_branch_form` (prefix-of-target + suffix-of-target, no vocabulary), a
branch short-circuit before the numeric heuristic, `_anchor_branches`, and dropping
anchor-derived tokens from the series requirement.

### RC-7 — Greek homoglyphs turned a capacity unit into a series

The corpus contains exactly three non-ASCII homoglyphs, all Greek capitals typed through a
keyboard-layout slip:

```
U+03A4 GREEK CAPITAL LETTER TAU      x6
U+039F GREEK CAPITAL LETTER OMICRON  x6
U+039D GREEK CAPITAL LETTER NU       x5
```

So `ECOSTAR SPLIT 1.5 ΤΟΝ 18DU01GC` carried `series='ΤΟΝ'` — a Greek string that no `[A-Z0-9]+`
scan can ever match. Folded at the character level in `clean_marketplace_noise`; the title now
parses as `capacity='1.5T'`, `series=''`.

### RC-8 — A series could be uncoverable for two structural reasons

* **Truncation.** `clean_marketplace_noise` cuts a title at a long dash, so
  `ELite EAF-05 Air Fryer – 4.5L Low-Fat …` became `ELite EAF-05 Air Fryer` and lost its own
  series before comparison. The raw title is now re-tested.
* **Partial codes.** `MSEZ2D-24HRFN1` is a *prefix* of the longer hyphenated
  `MSEZ2D-24HRFN1-QCOW-B`, and a whole-token squash can never produce it. Coverage now uses
  bounded n-grams (`_comparison_ngrams`, span ≤ 3) — bounded on purpose, because unbounded
  substring matching would let a series like `PRO` match inside `PROCESSOR`.

The two sets are kept separate: n-grams drive *coverage* only, never the sub-series set
arithmetic, where extra compounds invent collisions that do not exist. Wiring them together
produced **682 regressions** and was reverted.

### RC-9 — Marketing prose reached the `series` slot through three routes

* Standalone category nouns (`Freezer`, `Signature Freezer`, `Deluxe Juicer Grinder 600W`)
  were absent from `_CATEGORY_PHRASES`, which only covered them in compounds. Extended.
* `extract_product_slots` flattened `|` and `—` to **spaces** instead of cutting, so
  `DW-9200 WFL—Extra Large … | Powerful Washing | Built-in Buzzer` yielded
  `series='Extra Large Powerful Washing Buzzer'`.
* Cutting naively broke the opposite case: `GREE AIR CONDITIONER INVERTER 1.5 TON | 18AITH21W`
  puts the **model code after the pipe**. Trimming is now conditional — the prose is dropped
  only once the extracted model no longer appears in what remains, and the model token is
  re-attached when it lived in the dropped segment.

### RC-10 — Dangling search queries

Noise stripping could leave a bare separator, emitting `'SG -'` and `'-'` as real queries.
`_sane_query` now trims and drops empties at the single point where tiers are assembled.

---

## 4. What the new implementation looks like

`matcher.py` deleted and rewritten around one implementation per concept. The referee's 18
hand-written `if <facet> collides: return MatchDecision(...)` blocks became a declarative rule
table (`_FACET_RULES` / `_POST_FACET_RULES`) driven by one loop; `MatchDecision(...)` is
constructed in exactly **2** places, down from 18. Also de-duplicated: safeguard masking,
variant-part parsing, capacity-stem join, unit suffix, brand-prefix strip, SaveIN/SVN emission
and tier emission (`_TierBuilder`).

Added `MatchDecision.tier` (`EXACT | BASE | REJECT`) and `.usable` so consumers stop
re-deriving `is_match or is_base_match`.

**One fix deliberately not applied:** gluing a letter prefix onto any numeric stem
(`DWT 1016` → `DWT-1016`). `DMB 4467 SD` is structurally identical, so the same rule rewrites
the minibar SKU to `DMB-4467SD` and drops `Dawlance 4467` from tier 1. RC-2 alone fixes the bug.

---

## 5. Validation

### 5.1 The reported product

| Case | Before | After |
| :-- | :-- | :-- |
| `Dawlance 10 KG DWT-1016 INV PRIMA Top Load Fully Automatic Washing Machine` vs the real listing | **REJECT** — `Missing required series tokens … 'PRIMA Fully Automatic'` | **EXACT** |
| same target vs `Dawlance DWT-1016DDM INV PRIMA 10 KG Washing Machine` | **REJECT** — `DDM mismatch` | **EXACT** |
| same target vs `Dawlance DWT 1016 10 Kg Top Load Washing Machine` (no INV/PRIMA) | REJECT | **BASE**, `missing_modifier='INVERTER'` |
| range pipeline terminal, base fallback present | `notice present? False` | `⚠️ CROSS-CHECK: AlfaMall listings omitted 'INVERTER' → ranged against 1 base model offer` + notice panel |

### 5.2 Whole corpus — 2,997 unique titles, 51 brands

| Metric | Old matcher | New matcher |
| :-- | :-- | :-- |
| Crashes across 6 entry points | — | **0** |
| Titles that reject **themselves** | 173 | **0** |
| Empty search query / model code | — | **0** |
| Dangling queries (`''`, `'SG -'`) | 2 | **0** |
| Category phrase in `series` | present | **0** |

Old → new self-match verdict changes: `REJECT → EXACT` **229**, `REJECT → BASE` **33**,
`EXACT → BASE` **1**. No title moved *to* REJECT.

The single `EXACT → BASE` is `HDR-TC2C1 GB/GR/GS`, a genuine three-way variant list. BASE is
the correct, *safe* answer: still usable, still priced, now carrying a cross-check notice.

### 5.3 Replay of 1,736 recorded live-API items

Every recorded vendor title re-adjudicated by both matchers against its captured target:

```
recorded | old matcher | new matcher | count
  REJECT    REJECT        REJECT       1235
  REJECT    BASE          BASE          170
  EXACT     BASE          BASE          116
  EXACT     REJECT        REJECT         78
  EXACT     EXACT         EXACT          70
  REJECT    REJECT        BASE           22   <-- recovered as base-model fallback
  REJECT    REJECT        EXACT          21   <-- recovered as exact
  EXACT     REJECT        BASE           15
  EXACT     REJECT        EXACT           7
  REJECT    EXACT         EXACT           2

old and new agree on 1671/1736 (96.3%)
downgrades old->new: 0
```

**43 recovered offers, 0 regressions.** Recoveries are e.g.
`GREE AC 1.5 TON Inverter Split Air Conditioner Airy Plus 18AITH21B…` and
`Haier Top Load Fully Automatic Washing Machine HWM 150-826s6` — identical machines the old
matcher rejected.

**A caution about the recorded labels.** 78 items are labelled `matched` in the capture but
rejected by *both* matchers. Those labels came from the pipeline's end-to-end path, not from
`referee_match`, so the bucket is not a valid oracle for this function. The apples-to-apples
comparison is the `old matcher` column, and there the two implementations agree 96.3% of the
time with zero downgrades.

### 5.4 Tests

| | Count |
| :-- | :-- |
| Baseline suite (unchanged) | 257 |
| `tests/test_matcher_fallback.py` — one test per root cause | 20 |
| `tests/test_matcher_corpus_smoke.py` — corpus guards + named regressions | 11,998 |
| **Total** | **12,275 passed** |

---

## 6. Regressions found and fixed during this work

Reported because each one was a real defect I introduced, caught only by the corpus sweep:

| Defect | How it was caught | Fix |
| :-- | :-- | :-- |
| Renamed local `m` left a dangling reference; crashed on `<prefix> <capacity> <series>` titles | 8 unit failures; the differential harness had swallowed it as a "delta" | Completed the rename; added a permanent no-crash sweep |
| `E-Star` tokenised to `E`+`STAR`, so an identical title rejected itself | live-API replay | `_comparison_words` adds the whole-token form |
| `TCL 40 Inches Smart` gained a phantom `IOT` capability | live-API replay | `is_display` recomputed from `_SCREEN_RE` |
| `Low-Fat` series rejected its own title (dash truncation) | full-corpus sweep, 1 `EXACT → REJECT` | raw-title re-test in `_series_verdict` |
| n-grams wired into sub-series arithmetic | full-corpus sweep, **682** `EXACT → REJECT` | split coverage from set arithmetic |
| Prose stripping cut a model code that sat after a pipe | live-API replay, 1 `EXACT → REJECT` | conditional trim that re-attaches the model token |

---

## 7. Known gaps carried forward

1. **The `series` slot still absorbs non-series prose for some small-appliance titles**
   (`WestPoint Deluxe Sandwich Toaster`, `Deluxe 1000W`, `DAW` on 156 rows). These no longer
   cause incorrect rejections — every corpus title matches itself, and there are no downgrades
   on live data — but the slot is noisier than it should be. Cleaning it properly means a
   category vocabulary for small domestic appliances, which is outside the AlfaMall/DigiMall
   appliance scope of this change.
2. **`HDR-TC2C1 GB/GR/GS`** and similar three-plus-way variant lists resolve to BASE rather
   than EXACT. Safe (usable + cross-check notice); branch equivalence is implemented for the
   2-way case.
3. **Pre-existing `mypy` errors remain** in `scraper.py` (3), `exporter.py` (2) and
   `learner.py` (1). Untouched by this change; the old matcher's 2 were fixed.

---

## 8. Files changed

| File | Change |
| :-- | :-- |
| `pricing_engine/matcher.py` | Replaced. Public API preserved; added `TIER_*`, `MatchDecision.tier`, `.usable`. |
| `pricing_engine/range_pipeline.py` | `PlatformFallback`, `RangeItemResult`, `_detect_fallbacks`, `_fallback_marker`, `render_range_fallback_notices`. CSV column contract unchanged. |
| `scripts/corpus_harness.py` | New. Reads every column of all 12 CSVs; resolves `Name`/`Item Name` by header. |
| `tests/test_matcher_fallback.py` | New — 20 regression tests keyed to RC-1…RC-4. |
| `tests/test_matcher_corpus_smoke.py` | New — 2,997-title corpus guards plus named regressions for RC-5…RC-10. |
| `AGENTS.md` | Range-mode cross-check notice; test count. |
