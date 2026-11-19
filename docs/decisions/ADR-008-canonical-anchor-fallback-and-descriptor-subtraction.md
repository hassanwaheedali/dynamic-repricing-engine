# ADR-008: Canonical Anchor Fallback, Prefix Hyphenation, and Scoped Descriptor Subtraction

## Status
Accepted

## Date
2026-11-17

## Context
Catalog items and marketplace listings diverge in three recurrent, brand-agnostic formatting patterns:
1. **Spelled vs. Hyphenated Tap Anchors & Prose Inches**: Listings drop the hyphen between a model series name and tap count (`Icon-2` vs. `Icon 2 Taps`), while quotes or English prepositions (`'Icon 2'`, `"2 in Black"`, `2-3 Taps`) can be misread by inline measurement regexes as screen inches (`2INCH`) even though `parse_capacity` (`UNIT_PATTERNS`) still supports explicit inch-quote values (`50"`, `65"`).
2. **Appliance/Listing Descriptors Leaking Into Series**: Words like `Cabinet` (e.g., `Refrigerator Cabinet Water Dispenser`, `Floor Standing Cabinet AC`) and listing noise (`Black color`, `White colour`) leaked into `ProductSlots.series` (`'Cabinet'` vs. `'color'`), causing false `SERIES_UNCERTAIN` rejections when a model code lacked multi-segment evidence. Crucially, adding `CABINET` globally to `NON_SKU_TOKENS` strips historical series-like name-only fallback queries (`extract_search_query_and_model` Step 4, e.g., `X-IK Conventional Cabinet 24` in `tests/test_architecture_contract.py`), so descriptor subtraction scope matters.
3. **Glued Prefix Models & Mid-Number Slicing Divergence**: AlfaMall query generation (`_generate_single_branch_patterns`) did not emit `slots.anchor` (unlike DigiMall's `generate_model_first_queries`) and lacked reverse hyphenation for glued prefix+3+digits models (`YL2037S-B` -> `YL2037S` / `YL-2037S`), while `m_drum_multi` sliced 3/4-digit SKUs mid-number (`YL2037S-B` -> `YL-203-7S-B`, `HRF538` -> `HRF-53-8`).

## Decision
1. **Separate Prose Capacity Extraction From Structured Value Parsing (`pricing_engine/capacity.py`)**:
   - Keep `UNIT_PATTERNS` / `explicit_capacity_pattern` backward-compatible with explicit inch-quote strings (`parse_capacity('50"')`), while removing dead quote branches from `TOKEN_MEASUREMENT_UNIT_PATTERN`.
   - Use `prose_capacity_pattern`, strictly ascending numeric range checks (`is_numeric_range_continuation`, atomic `_MEASUREMENT_RANGE_SPAN_RE`), unambiguous TV/monitor-context bare `"in"` normalization (`normalize_screen_units`, evaluating display context after stripping trailing seller clauses), and stateful left-to-right quote-parity awareness in `pricing_engine/matcher.py`.
2. **Symmetric Tap-Series Model Bridges (`pricing_engine/matcher.py`)**:
   - Share `VALID_TAP_COUNTS` (`1..4`), `_extract_tap_capacity`, and `_is_tap_anchor_wrapper_prefix` across forward and reverse tap bridges so validated form-factor/brand wrapper prefixes (`WD-ICON-2` <-> `Icon 2 Taps`) bridge symmetrically while sub-series prefixes (`PRO-ICON-2`, `MINI-ICON-2`) and out-of-range counts (`Icon 20 Taps`) are rejected.
   - Bridge anchorless candidate tap phrases cleanly via `_anchor_runs_pattern`, `_has_trailing_non_tap_unit`, `_is_numeric_range_lower_bound`, and `_matches_anchor_in_anchorless_title` (supporting spaced, hyphenated, and glued `2Taps`), while rejecting conflicting measurements (`2Ltr`, `2Watt`), numeric ranges (`2.5-3 Taps`, `2 - 3 Taps`), and tap-less candidates in reverse matching.
   - Generate clean DigiMall tap-series queries in `generate_model_first_queries` without arbitrary series-word length cutoffs, `/` leakage, or multi-word glued tokens.
3. **Scoped Descriptor & Color-Trailer Preservation (`pricing_engine/matcher.py`)**:
   - Place `"COLOR"` and `"COLOUR"` in `NON_SKU_TOKENS` (listing color-word noise is never a valid series or search keyword), and filter `_is_product_spec_trailer` color clauses against `_COLOR_CONNECTOR_WORDS` (`{"COLOR", "COLOUR", "FINISH"}`) and `_COLOR_SHADE_MODIFIERS` (with `:`/`/`/`&`/`,` splitting for `Color: White`, `White & Silver`, `Color: White/Grey`) while preserving right-to-left spec tails across preceding seller stop clauses (`- ET - White Color`). Store names containing a color word (`- Red Star`, `- White New`), quoted promo trailers (`- 'Deal 99'`, `- “Store 24”`), and `_PROMO_NUMBER_PREFIX_WORDS` trailers (`- Deal 99`, `- Discount 15`) are stripped while genuine color clauses and `| Model <digits>` trailers remain preserved.
   - Strip `\bCABINET\b` inside `extract_product_slots` series subtraction (alongside `CONVENTIONAL`, `SPLIT`, `AC`, `TOP LOAD`, `FRONT LOAD`) rather than `NON_SKU_TOKENS`, preserving historical name-only fallback query contracts in `extract_search_query_and_model`.
4. **Drum Slicer Scoping & Shared Anchor/Prefix Fallback (`pricing_engine/matcher.py`)**:
   - Require a delimiter or letter+sub-model tail (`\d{3,}|\d{2}[A-Za-z]{2,}`) in `m_drum_multi` and a 50..200 drum-capacity group with `>=6` total digits and a non-zero series start in `m_drum_glued` (zero category conditionals per `AGENTS.md`), so washers (`HW90-BP12357S8`, `HW90BP12357S8`, `HWM150826`, `801217 WB`) and multi-block TV contracts (`UA65DU7000` -> `UA-65-DU7000`, `QA65Q60DAUXMM` -> `QA-65-Q60DAUXMM`) remain intact while 3–5 digit SKUs and 1-digit revision codes (`YL2037S-B`, `HRF538`, `HRF216S6`, `YL203S1`, `GS60F1`, `91060`, `YL80250S`) are never cut mid-number.
   - Share one `slots = extract_product_slots(...)` call at the end of `_generate_single_branch_patterns` to emit color-stripped alphanumeric anchors (`YL2037S` -> `tier_2`), bidirectional hyphen/space variants, and glued `[A-Za-z]{2,4}\d{3,}` prefix hyphenation (`YL-2037S`, `YL 2037S`, `YL-2037S-M`) guarded against hyphen/space-split brand tokens, `NON_SKU_TOKENS`, `CATEGORY_PATTERNS`, and measurement units (`_TOKEN_MEASUREMENT_RE`, covering `GAL`, `KGS`, etc.).

## Alternatives Considered
### 1. Adding `"CABINET"` to Global `NON_SKU_TOKENS`
- **Pros**: One-line change.
- **Cons**: Silently alters `extract_search_query_and_model` Step 4 name-only queries (`X-IK Conventional Cabinet 24` -> `X-IK Conventional 24`), breaking `tests/test_architecture_contract.py` item 85.
- **Rejected**: Stripping `CABINET` inside `extract_product_slots` fixes `series` without mutating name-only search tokens.

### 2. Broadly Stripping Trailing `-B`/`-W` Color Suffixes Inside `extract_tag` or Mutating DigiMall's 3-Query Budget
- **Pros**: Would also replace `'YL2037S B'` with `'YL-2037S'` inside DigiMall's 3-query slot.
- **Cons**: Alters exact-match priority and violates the frozen DigiMall catalog contract (`tasks/architecture-consolidation-baseline.json` / `tests/test_architecture_contract.py` Item #90 requires `['YL2037S-B', 'YL2037S B', 'YL2037S']`), where DigiMall already resolves live `YL-2037S` listings within 1 search.
- **Rejected**: Keeping exact `-B` queries in `tier_1` and emitting `slots.anchor` + hyphenated stems in `tier_2`/`tier_3` fixes AlfaMall retrieval, feeds `YL-2037S` into DigiMall's `tier_2` loop whenever `-B` is absent (`Midea YL2037S`), and preserves both color isolation and the frozen DigiMall contract.

## Consequences
- `Icon 2 Taps` and `Model YL-2037S Black color` resolve deterministically without category or brand hardcoding, while `"- White Color"` / `"| White Colour"` trails remain protected against color collisions.
- `YL2037S-B` queries exact `-B` first (`tier_1`) and falls back to clean `YL2037S` / `YL-2037S` / `YL 2037S` (`tier_2`/`tier_3`), while DigiMall preserves `('YL2037S-B', 'YL2037S B', 'YL2037S')` and inherits `YL-2037S` on glued targets without a color suffix (`Midea YL2037S`).
- Mid-number drum slicing noise (`YL-203-7S-B`, `HRF-53-8`, `HRF-216-S6`, `GS-60-F1`, `YL-80-250S`) is prevented while washer segmentation (`HW-90-BP12357-S8`, `HWM-150-826`, `80-1217`), multi-block TV segmentation (`UA-65-DU7000`, `QA-65-Q60DAUXMM`), and all existing catalog architecture contracts remain intact.
