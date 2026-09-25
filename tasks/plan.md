# Universal Brand-Agnostic Model Matching Engine: Architectural Plan (V2 - Structural Token-Run Architecture)

## 1. Executive Summary & Root Cause Confirmation (5 User-Raised Gaps)

A thorough hand-trace analysis confirmed that all 5 issues raised by the user were critical architectural flaws in the previous regex-and-slicing approach:
1. **Issue 1 (Missing Hyphen in Group 3):** Confirmed. In `VARIANT_CLUSTER_PATTERN`, group 3 lacked `-`. In `"GS-24AITH21W-T3/21B-T3"`, the regex failed completely upon encountering the hyphen in `-T3`, returning the listing unexpanded.
2. **Issue 2 (TAG_PATTERN Dead Code):** Confirmed. Trailing tags like `-T3` in `GS-12AITH24W/S-T3` were excluded by the alphanumeric-only group 3, leaving `-T3` outside the match so `TAG_PATTERN` never triggered, attaching `-T3` only to the last token (`GS-12AITH24S-T3`) while leaving `GS-12AITH24W` bare.
3. **Issue 3 (Asymmetric-Length Variants Break Fixed Length Alignment):** Confirmed. In `GS-12AITH24W/S-T3` (3 chars vs 1 char) and `GS-24PITH15/17G` (2 chars vs 3 chars), bidirectional asymmetry cannot be resolved by character slicing. It requires typed structural token runs (`digits`, `letters`, `tags`).
4. **Issue 4 (Zero Hardcoding Violated):** Confirmed. Hardcoded brand prefixes (`GS|GF|GW`), capacities `(12, 18, 24, 36, 48, 60)`, and color words (`BLACK, SILVER...`) violated DRY and failed across the 768-product catalog in `MainSheet.csv` (Dawlance, Haier, Kenwood, Homage, Midea, PEL) which features multi-word compound colors (`MYSTIC GREY`, `CLOUD WHITE`, `EMERALD GREEN`, `BURGUNDY HONEY-COMB`).
5. **Issue 5 (Suffix-Word Truncation in Extractor):** Confirmed. `extract_search_query_and_model("DAW AUTO W/M DWT-1165 PL")` dropped `" PL"` because the regex only captured contiguous hyphens and stopped at spaces, dropping vital variant designations (`PL`, `FLT`, `FLP`, `ES`, `S6`, `S8`).

---

## 2. Updated Architectural Blueprint: Typed Structural Token-Run Engine

### A. Core Mathematical Formalism
Instead of rigid regexes or fixed character-length slicing, model strings and marketplace titles are parsed into ordered tuples of **Structural Runs**:
$$\text{Run} = (\text{Type} \in \{\text{'D' (Digits)}, \text{'L' (Letters)}, \text{'P' (Punctuation)}\}, \text{Value})$$

### B. Three Autonomous Processing Layers
1. **Layer 1: Brand & Fluff Stripper (`extract_search_query_and_model`)**:
   - Dynamically strips the catalog `Brand` name (`Dawlance`, `Haier`, `Kenwood`, `Gree`, `Homage`, `Midea`, `PEL`).
   - Strips category descriptors (`AUTO W/M`, `SPLIT AC`, `CASSETTE`, `FLOOR STANDING`, `M/O`, `D/F`, `R/F`).
   - Captures full multi-token model signatures (`DWT-1165 PL`, `100-316S6 GC`, `HDG-2312B`, `12AITH21W-T3`).
   - Automatically excludes marketing color phrases (`MYSTIC GREY`, `CLOUD WHITE`, `EMERALD GREEN`) without requiring hardcoded color dictionaries.
2. **Layer 2: Structural Token-Run Title Expander (`expand_multivariant_titles`)**:
   - **Safeguard Masking**: Masks category acronyms (`W/M`, `D/F`, `A/C`, `H/C`) and English phrases (`Heat / Cool`, `12W/8D`, `1/2" pipe`).
   - **Direct Parenthetical Expansion**: Expands `STEM (V1/V2...)` directly using `distribute_runs(stem, [V1, V2...])`.
   - **Slash-Cluster Run Alignment**: For tokens containing `/`, separates trailing tags (`-T3`, `AAA`, `PRO`), aligns variant sub-runs against the trailing runs of the model head, factorizes the common stem (`GS-24AITH`, `DWT-`, `HDG-`), and distributes bidirectional asymmetric prefixes/suffixes (`15/17G` -> `15G/17G`, `24W/S` -> `24W/24S`).
3. **Layer 3: Slot-Invariant Strict Matcher (`is_strict_model_match`)**:
   - Enforces exact canonical containment on expanded listings.
   - **Zero-Hardcoded Slot Invariance**: Compares token slots. If the target model has a capacity number (e.g. `24`) in slot 0 before series `AITH`, any title containing a different number (e.g. `12` or `18`) in that exact slot is rejected—without maintaining any capacity lists.
   - **Variant Isolation**: Target variant `B` (Black) requires `B` in the expanded model token; a listing containing only `W` without `B` is rejected.

---

## 3. Vertically Sliced Task Breakdown

### Task 1: Update `pricing_engine/matcher.py` with Structural Token-Run Parser
- Implement `split_runs`, `extract_tag`, `distribute_runs`, `expand_slash_word`, and `expand_multivariant_titles`.
- Update `extract_search_query_and_model` to handle multi-token models (`DWT-1165 PL`) and dynamic brand stripping.
- Update `is_strict_model_match` with zero-hardcoded slot invariance.

### Task 2: Update and Expand `tests/test_matcher.py`
- Add unit tests covering all 5 user issues.
- Add multi-brand test cases from `Stock Holding Report - FINAC - Products - MainSheet.csv` (Dawlance, Haier, Kenwood, Homage, Midea, Gree, PEL).
- Verify 100% test pass on pytest.

### Task 3: Quality Gates & Verification
- Run `pytest -v` across all project tests.
- Run `ruff check .` for 0 linting errors.
