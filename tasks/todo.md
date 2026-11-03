# Task Checklist: Generic Model Variants, Optional Specifications & Matching Accuracy

- [x] **Phase 1: Baseline Verification & Environment Check**
  - [x] 1.1 Verify git working tree status (`main`, no unintended code changes)
  - [x] 1.2 Run full `pytest -v` baseline suite (`507 passed`) and confirm 100% green pass
  - [x] 1.3 Verify `ruff check .` baseline (`0` errors) and `mypy pricing_engine` baseline (`0` errors)

- [x] **Phase 2: Collateral-Safe Pre-Normalization & Capability Polarity Engine**
  - [x] 2.1 Implement collateral-safe spaced unit binder (`matcher.py`): bind multi-letter units (`WATTS?`, `KGS?`, `RPM`, `LTRS?`) unconditionally, and bind single-letter `W` / `L` *only* when a genuine non-dimension model anchor already exists (never after `-`/`_`/`/`, dynamic 2–4 char SKU prefixes like `DWT 255 W`, hyphenated washer drum capacities like `HWM-150 826 W`, or 5-digit primary stems like `91999 W` / `91060 W`)
  - [x] 2.2 Add pre-Cartesian ERP category slash protection: register `R/F`, `D/F`, `W/M`, `W/D`, `M/O`, `AWM`, `SDA` in `SAFEGUARD_PATTERN` and neutralize in `normalize_technical_slashes()` *before* `expand_cartesian_branches()` and `normalize_color()`
  - [x] 2.3 Implement `AGENTS.md` Rule 1.6 dynamic spaced SKU prefix binding (`PINV 12K` $\rightarrow$ `PINV-12K` without static prefix lists) while keeping unprefixed standalone `12K`/`18K`/`24K` classified as spec/BTU tokens in `is_dimension_or_spec_token()` so downstream SKUs (`GS-12PITH11W`, `HSU-18HFP`) are never hijacked
  - [x] 2.4 Implement Dawlance-scoped isolated `\bX\b` neutralization (`clean_marketplace_noise()` & variant guards in `_extract_stem_single_letter_variant()` / `GENUINE_SUB_SERIES_TOKENS`), protecting numeric dimensions (`24 X 24`) and non-Dawlance brands (`TCL 55" X Series QLED TV`)
  - [x] 2.5 Add `negative_capabilities: set[str]` and `ambiguous_capabilities: set[str]` to `GuardedFacets` in `pricing_engine/matcher.py`
  - [x] 2.6 Implement `CAPABILITY_POLARITY_PATTERN` in `extract_product_slots()` with trailing `(?!\w)` (preserving `ADS+`) and canonical normalization across `extract_product_slots()` and `referee_match()`
  - [x] 2.7 Quarantine `raw_pos & raw_neg` conflicts into `ambiguous_capabilities` (including `Smart` + `Non-Smart` on TVs and co-occurring `WiFi`)
  - [x] 2.8 Implement the 4-Rule Polarity Matrix in `referee_match()`:
    - [x] 2.8.1 **Rule A (Internal Candidate Ambiguity)**: Reject candidate (`match_tier = None`) when `cand.ambiguous_capabilities` is non-empty
    - [x] 2.8.2 **Rule B (Explicit Polarity Contradiction)**: Reject candidate (`match_tier = None`) when `(target.capabilities & cand.negative_capabilities)` or `(target.negative_capabilities & cand.capabilities)` is non-empty
    - [x] 2.8.3 **Rule C (Candidate Extra Spec)**: Accept (`match_tier = 1`) with `ℹ️ [OPTIONAL SPECIFICATION: ...]` when candidate specifies unstated non-negated `T3`
    - [x] 2.8.4 **Rule D (Target Spec Omitted by Candidate)**: Block from Tier 1 and demote to Tier 2 Fallback (`is_match = False, is_base_match = True, match_tier = 2`) with `⚠️ [FALLBACK MODEL: ...]` when `target.capabilities - cand.capabilities` is non-empty
  - [x] 2.9 Unit test pre-normalization collateral guards, `ADS+`, and Rules A–D in `tests/test_generic_variants_and_polarity.py`

- [x] **Phase 3: Item #23 AC-Anchored Subordinate Slash & AC-Only DC Inverter Inference**
  - [x] 3.1 Implement strictly AC-anchored `SUBORDINATE_AC_SLASH_RE` in `extract_search_query_and_model()` (before parenthesis unwrapping of `(GE)`) and in `extract_product_slots()`, leaving non-AC color/tub slashes (`DMB-91060/WB`, `HWM-150-826/WB`) intact
  - [x] 3.2 Add `subordinate_codes: list[str]` to `ProductSlots` in `pricing_engine/matcher.py`
  - [x] 3.3 Implement AC-only `DC` Inverter inference in `extract_product_slots()`: suffixes `/DC`, `/012DC`, `/023DC`, `-DC` set `is_inverter = True` strictly when `_detect_appliance_family() == 'AIR_CONDITIONER'`
  - [x] 3.4 Unit test Item #23 (`HPU-48HE/012DC(GE)-T3`): verify no orphan `GE`, AC `DC` $\rightarrow$ `is_inverter = True`, `Kia Chahiye Pvt Ltd` (`OWN_STORE`) Monopoly pricing (`Rs. 552,999`) untouched, external competitor uncapped psychological undercut (`Rs. 579,899`) + sweet-spot win, and Option [3] floor (`Rs. 548,919`)

- [x] **Phase 4: Item #64 AC SKU Decomposition & Per-Marketplace 3-Tier Waterfall**
  - [x] 4.1 Implement `AC_SKU_DECOMPOSITION_RE` (`2-digit capacity + 3-letter series stem + optional 1–2 char sub-tag`) populating `ProductSlots.base_stem` and `ProductSlots.sub_model_tag` (`18HFPCA` $\rightarrow$ `18HFP` + `CA`, `18HFPE` $\rightarrow$ `18HFP` + `E`, `18HFA` isolated)
  - [x] 4.2 Emit `{BRAND} {base_stem}` / `{base_stem}` (`HAIER 18HFP`, `18HFP`) fallback search queries in `generate_search_patterns()`
  - [x] 4.3 Wire both `_evaluate_anchor_compatibility()` and `_has_variant_tag_collision()` plus `MatchDecision.{match_tier, compatibility_notice}` to classify shared `base_stem` with 100% guarded-facet invariance into Tier 1 / Tier 2 / Tier 3
  - [x] 4.4 Add `match_tier` & `compatibility_notice` to `ScrapedOffer` and `sibling_offers` & `compatibility_notice` to `ScrapeResult` (`models.py`), and update `_parse_offers_with_tiers()` + `_execute_waterfall()` (`scraper.py`) to resolve `Tier 1 > Tier 2 > Tier 3` independently per platform (preserving `_parse_offers_with_diagnostics()` 9-tuple backward compatibility and updating `tests/test_slice3_scraper_diagnostics.py` non-matching pearl prose fixture)
  - [x] 4.5 Wire `evaluate_alfa_pricing()` and `evaluate_digi_pricing()` in `evaluator.py` via `_apply_compatibility_and_fallback_annotations()` so winning `compatibility_notice` values populate `PlatformPricingResult.compatibility_notice` and prepend cleanly to `alfa_reason` / `digi_reason`
  - [x] 4.6 Unit test Item #64 3-tier waterfall (`18HFPCA` $\rightarrow$ `18HFP` $\rightarrow$ `18HFPE`, with `18HFA` rejected)

- [x] **Phase 5: Terminal Presentation, XLSX Soft Yellow Fill, Adversarial Review & 25-Scenario Regression Suite**
  - [x] 5.1 Update `render_audit_card()`, `_format_search_telemetry()`, and `_format_summary_price()` in `pipeline.py` via canonical `has_compatibility_or_fallback_notice()` so `[bold yellow]CROSS-CHECK[/]` triggers on all fallback/compatibility notice markers
  - [x] 5.2 Update `export_excel_workbook()` in `exporter.py` to apply soft yellow `PatternFill("FFF9C4")` on cells/rows containing compatibility/fallback notices while keeping exact CSV/XLSX column schema (**Option A + Soft Yellow Cell Fill**)
  - [x] 5.3 Implement all 25 permanent regression scenarios (`REG-01` to `REG-25`) plus 6 fresh-context adversarial regression tests (`test_adv_01` to `test_adv_06`) in `tests/test_generic_variants_and_polarity.py` (50 focused tests)
  - [x] 5.4 Run full test suite `pytest -v` (`557 passed, 0 failed`)
  - [x] 5.5 Run `ruff check .` (`0` errors) and `mypy pricing_engine tests/test_generic_variants_and_polarity.py` (`0` errors)
