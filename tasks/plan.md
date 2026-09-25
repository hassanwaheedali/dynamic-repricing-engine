# Implementation Plan: Dual-Variant Slash Matching & Scraper Pacing Guard

## 1. Overview
In Pakistani e-commerce platforms (AlfaMall and DigiMall), sellers frequently group color variants within a single title using slash expressions (e.g., `GS-12AITH24W/S` or `GS-12AITH24-W/S`). Currently, punctuation stripping collapses `12AITH24W/S` into `12AITH24WS`, which fails exact substring matching against target `12AITH24S`. Consequently, the engine erroneously declares "0 sellers found", falling back to Monopoly baseline pricing (`Rs. 199,999`) and losing the buy box to competitors selling at `Rs. 193,999`.

This plan implements **Option 1: Virtual Token Slash Expansion** in `matcher.py` focused strictly on **Color Slashes** (`W/S`, `S/W`, `W/B`, `W/G`) and identical batch series (`14S / 11S`). It strictly **rejects** cross-generation mixing (e.g., `ZITH1` vs `ZITH2` remain 100% isolated), eliminates false matching on pipe sizes (`1/2"`), and incorporates gentle scraper pacing with randomized jitter cool-down backoff to eliminate AlfaMall WAF timeouts.

---

## 2. Core Architecture Decisions

### Decision 1: Strict Color Slash Expansion (Exact Model, Different Paint)
Before stripping punctuation in `is_strict_model_match`, the scraped title is passed through `expand_multivariant_titles(title: str) -> str`:

1. **Color Slash Expansion (with Hyphen, Space & Champagne `C` support):**
   - Regex: `r'\b([0-9]{2}[A-Z0-9]+?)[-\s]*([WBSGC])\s*/\s*([WBSGC])((?:[-_\s]+[A-Z0-9]+)?)\b'`
   - Target: The model specification is 100% identical (same capacity, same compressor, same series), only the color finish is slashed.
   - Handles:
     - Standard: `GS-12AITH24W/S` -> `GS-12AITH24W 12AITH24S`
     - Hyphenated: `GS-12AITH24-W/S` -> `GS-12AITH24W 12AITH24S`
     - Spaced: `GS-12AITH24 - W/S` -> `GS-12AITH24W 12AITH24S`
     - Trailing T3: `GS-12AITH24W/S-T3` -> `GS-12AITH24W-T3 12AITH24S-T3`
     - Trailing Space T3: `GS-12AITH24W/S T3` -> `GS-12AITH24W T3 12AITH24S T3`
     - Extended Colors: `18AITH21W/B` (Black), `18PITH11W/G` (Grey), `12AITH24W/C` (Champagne).

2. **Identical Batch Pular Series Slash Expansion:**
   - Regex: `r'\b([0-9]{2}PITH)[-\s]*(14|11)[-\s]*([WBSGC])\s*/\s*(14|11)[-\s]*([WBSGC])\b'`
   - Strictly limited to Pular series batches (`14S / 11S`) where net prices and specs are 100% identical.
   - **STRICT PROHIBITION:** No single-digit `\d{1}` matching (avoids matching `1/2"` copper pipe, and strictly prevents mixing `ZITH1` with `ZITH2`).

### Decision 2: Model & Generation Isolation Invariants
- **Generation Protection:** `GS-12ZITH1W` and `GS-12ZITH2W` are completely different generation models. They will **NEVER** be slashed, expanded, or cross-matched.
- **Rule of Priority:** Positive exact token match (`if base_target in clean_title: return True`) ALWAYS dominates and executes before any negative word penalty.
- **Silver Target (`12AITH24S`):** Matches `12AITH24W/S` because `12AITH24S` is explicitly generated.
- **White Target (`12AITH24W`):** Matches `12AITH24W/S` because `12AITH24W` is explicitly generated.
- **Black Target (`12AITH24B`):** Rejects `12AITH24W/S` because `12AITH24B` is absent.
- **Single-Color Isolation:** Pure `GS-12AITH24W` (without slash) strictly rejects `12AITH24S`.

### Decision 3: Commercial & Profit Impact on Item #3 (`12AITH24S-T3`)
- Real Landed Cost: `Rs. 175,978`
- Digi 8% Floor (+500): `Rs. 191,824`
- Competitors Scraped: Musab Mall (`Rs. 193,999`), Tech House (`Rs. 193,999`), YZ International (`Rs. 194,099`).
- Engine Action: Triggers Emergency 8% Bank Switch. Undercuts `Rs. 193,999` to winning price **`Rs. 193,899`** (.899 ending).
- Guaranteed Profit: `(193,899 * 0.92) - 175,978 = +Rs. 2,409` (far above +Rs. 500 hard floor).

### Decision 4: Scraper Resilience, Pacing & Randomized Jitter Backoff
- In `pricing_engine/pipeline.py`, increase task dispatch micro-stagger from `0.2s` to `0.4s` to smooth burst traffic.
- In `pricing_engine/scraper.py`, catch broad timeout errors (`curl: (28)`, `timed out`, `timeout`, `asyncio.TimeoutError`).
- When a timeout occurs, apply a randomized jitter backoff:
  `backoff = random.uniform(3.5, 5.0) + (attempt * 1.5)`
  This de-synchronizes parallel workers, preventing synchronized retry waves from re-triggering the WAF tarpit.
- Preserve shared `AsyncSession` across pipeline tasks; rely on libcurl's automatic socket teardown for timed-out connections.

---

## 3. Ordered Task List

### Phase 1: Logic & Unit Tests in `matcher.py`
- [ ] **Task 1: Implement `expand_multivariant_titles` in `pricing_engine/matcher.py`**
  - Add color slash regex with hyphen, space, `[WBSGC]`, and trailing suffixes (`-T3`, ` T3`).
  - Add identical batch Pular series regex (`14S / 11S`).
  - Integrate into `is_strict_model_match` before clean title normalization.
  - *Acceptance Criteria:* `GS-12AITH24-W/S`, `GS-12AITH24W/S-T3` expand properly; matches `12AITH24S` and `12AITH24W`; rejects `12AITH24B`; `ZITH1W` and `ZITH2W` remain strictly isolated.
- [ ] **Task 2: Add Comprehensive Unit Tests in `tests/test_matcher.py`**
  - Test dual color slash matching (`12AITH24W/S` with `S`, `W`, `B`).
  - Test hyphenated syntax (`12AITH24-W/S` and `12AITH24 - W/S`).
  - Test trailing suffixes (`-T3` and ` T3`).
  - Test extended color `C`: `12AITH24W/C` matches `12AITH24W` and `12AITH24C`.
  - Test generation isolation: `GS-12ZITH1W` does NOT match `GS-12ZITH2W`.
  - Test color collision guard: `GS-12AITH24W/S` rejects `12AITH24B-T3`.
  - Test single-color isolation: pure `GS-12AITH24W` rejects `12AITH24S-T3`.
  - *Acceptance Criteria:* All matcher tests pass 100% green.

### Phase 2: Scraper Pacing & WAF Tarpit Guard
- [ ] **Task 3: Add Gentle Pacing & Smart Timeout Backoff in `pricing_engine/scraper.py` and `pipeline.py`**
  - In `pipeline.py`, set micro-stagger sleep to `0.4s`.
  - In `scraper.py`, detect `curl: (28)` / timeout exceptions and apply `random.uniform(3.5, 5.0) + (attempt * 1.5)` randomized jitter backoff.
  - *Acceptance Criteria:* Rapid consecutive runs do not trigger AlfaMall WAF packet drops or synchronized burst waves.

### Phase 3: Integration Tests & Production Verification
- [ ] **Task 4: Add Integration Test for Item #3 DigiMall Repricing in `tests/test_pipeline.py`**
  - Simulate DigiMall response containing `GS-12AITH24W/S` at `193,999`.
  - Verify engine undercuts to `193,899` (.899 ending) with `8.00%` rate and `+2,409` profit.
  - *Acceptance Criteria:* Test passes; verifies full end-to-end pricing flow.
- [ ] **Task 5: Quality Gate Run & Live Production Benchmark**
  - Run full test suite: `pytest -v` (expect ~70+ passed).
  - Run linter: `ruff check .` (0 errors).
  - Run live benchmark: `python index.py`.
  - Review changes with user and ask for confirmation before committing to Git!

---

## 4. Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Slash expansion matching unintended words | Medium | Strict regex anchors (`\b` word boundary, specific color letters `[WBSGC]`, 2-digit capacity prefix). |
| Cross-generation model mixing | High | Prohibit single-digit `\d{1}` matching; keep `ZITH1` and `ZITH2` strictly isolated. |
| Selling Silver at White price | Low | Cost Base & Hard Floor (+Rs. 500) always calculate from Silver's own Net Price (`172,000`), guaranteeing profit >= Rs. 500. |
| Negative guard overriding positive match | High | Line 69 positive exact match `if base_target in clean_title: return True` always executes first. |
| Synchronized worker retry burst | Medium | Randomized jitter backoff `random.uniform(3.5, 5.0) + (attempt * 1.5)` breaks worker synchronization. |
