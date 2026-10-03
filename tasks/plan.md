# Implementation Plan: 3-Tier Multi-Pattern Search & Robust Unified Referee Engine

## Overview & Executive Summary

Address false monopolies and unmatched "solo" products across brands (especially Dawlance ACs, Refrigerators, Washing Machines, Deep Freezers, and Small Domestic Appliances) by transforming the search and matching architecture into a true **Two-Stage Funnel**:
1. **Stage 1 (Exhaustive 3-Tier Pattern Search & Deduplicated Pooling)**: Remove the premature waterfall early-exit (`break` on $\ge 2$ offers) so all tiered query patterns (exact SKU, bare numeric stem, space/hyphen/prefix permutations, and brand-prefixed variants) execute and merge into an expansive, deduplicated raw candidate pool.
2. **Stage 2 (Unified Centralized Strict Referee)**: Run a robust, noise-resilient referee over the combined candidate pool with clean token normalization (stripping merchant noise, installment text, promo phrases), parenthesis handling, dynamic prefix decoupling (`DWT11467ES` -> `11467`), slash-separated alias tolerance (`Sprinter / Powercon`), and strict guarded facet enforcement (T3, IoT, Capacity, Hardware Tub `WB`/`GB`, Color optionality).

---

## Root Cause Analysis from Empirical Testing (38 Dawlance Products)

Our empirical diagnostic against live AlfaMall & DigiMall APIs on the 38 user-provided Dawlance models revealed:
- **Only 8 of 38 products matched** in the existing implementation, while **30 products became false "solo" (Monopoly priced)**, despite valid listings existing on both portals!
- **Root Cause 1 (Waterfall Premature Exit)**: `scraper.py` terminates query generation as soon as $\ge 2$ offers return for Tier 1, skipping cheaper competitors in Tier 2 and Tier 3 who omitted variant tags or used spaced formats.
- **Root Cause 2 (Noise Pollution in Series Matching)**: Merchant marketing noise (`ElectroEase`, `HomeCart`, `On Installment`, `With Free Delivery`, `Heat & Cool`, `ISPK-0577`) is treated as unmatched "extra series tokens", causing `referee_match` to falsely reject 100% genuine listings (e.g. `Suave+ 30`, `GLACIER 2 Ton FLOOR`).
- **Root Cause 3 (Parenthesis & Punctuation Leakage)**: Punctuation like `(Milky White Textured)` or `Sprinter / Powercon` leaves literal parentheses `(MILKY` or un-split slashes `SPRINTER/POWERCON` in extracted tokens, failing string comparisons.
- **Root Cause 4 (Glued Prefix Extraction)**: Glued catalog SKU codes like `AWM DWT11467ES` or `DW3013AF` fail to decompose into `[Prefix] + [Stem] + [Suffix]` (`DWT` + `11467` + `ES`), searching unindexed strings that return 0 hits.
- **Root Cause 5 (Color Optionality Asymmetry)**: Lack of clear handling when sellers omit the color name on single-color listings versus when sellers list competing color variants (e.g., White target rejecting Silver/Black, but accepting unmentioned color when model matches).

---

## Architectural Decisions

| Decision | Rationale |
| :--- | :--- |
| **Full 3-Tier Query Search (No Early Break)** | Collects all candidate listings from Tier 1 (exact), Tier 2 (bare stem), and Tier 3 (space/prefix permutations) without early exit, ensuring zero hidden competitors are missed. |
| **Comprehensive Merchant & Promo Noise Filtration** | Dynamically strip marketplace junk (merchant signatures, installment terms, warranties, delivery tags, `Heat & Cool`, `DC Inverter`) before computing series token subtraction. |
| **Parenthesis & Punctuation Token Cleaning** | Strip parentheses, brackets, and normalize slashes so `(Milky White Textured)` cleanly maps to `Milky White Textured` color/facets and `Sprinter / Powercon` allows either `Sprinter` or `Powercon`. |
| **Generic Dynamic SKU De-gluing** | Apply generic regex `^([A-Za-z]{2,4})[- ]?(\d+)[- ]?([A-Za-z0-9]*)$` to dynamically break glued codes (e.g. `DWT11467ES` $\to$ Prefix: `DWT`, Stem: `11467`, Suffix: `ES`). |
| **Strict Color Family Collision vs Optional Unmentioned Color** | If target specifies color (e.g. White), reject opposing color families (Silver/Black). If candidate listing does not mention color at all and model matches, accept as unmentioned color. |

---

## Phased Implementation Roadmap

### Phase 1: Exhaustive 3-Tier Pattern Generation & Waterfall Search
- Remove early exit in `pricing_engine/scraper.py` so all tiers query and pool offers.
- Enhance `pricing_engine/matcher.py:generate_search_patterns` to generate glued/de-glued permutations for appliance codes.
- Ensure all queries are collected and deduplicated by `(vendor_name.lower(), round(price, 2))`.

### Phase 2: Title Normalization & Marketing Noise Stripping
- Expand token normalization to strip merchant signatures (`ElectroEase`, `HomeCart`, `ISPK-\d+`, `SNS\d+`, `ET`, `UE\d+`).
- Strip transaction/promo noise (`On Installment`, `Upto \d+ Months`, `0% Markup`, `Free Delivery`, `Special Gift`, `Best Price`).
- Strip common HVAC/appliance operation terms (`Heat & Cool`, `Heat and Cool`, `DC Inverter`) from the Series slot so they don't trigger false "sub-series mismatch".

### Phase 3: Punctuation, Slashes, and Dynamic Initialism Normalization
- Strip parentheses and brackets before slot extraction so `(Milky White Textured)` extracts cleanly.
- Handle slash-separated series names (`Sprinter / Powercon`) by treating them as alternative valid series keywords (OR logic).
- Verify dynamic initialisms (`SD` $\iff$ `Single Door`, `FL` $\iff$ `Front Load`, `TL` $\iff$ `Top Load`).

### Phase 4: Strict Guarded Facets & Color Optionality Enforcement
- Enforce strict T3 compressor guard (T3 target rejects non-T3, non-T3 rejects T3).
- Enforce IoT guard (IoT target rejects non-IoT, non-IoT rejects IoT).
- Enforce Hardware Tub guard (`WB` vs `GB`).
- Enforce Color Family logic: cross-family mismatch rejects; unmentioned color accepted.

### Phase 5: Verification & Benchmark Suite
- Run regression tests on all 38 Dawlance models.
- Run complete test suite (`180+ tests`) ensuring 100% green pass.
- Verify zero float drift and zero ANSI leakage in outputs.
