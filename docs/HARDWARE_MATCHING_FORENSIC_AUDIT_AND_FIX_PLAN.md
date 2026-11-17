# Hardware Matching Forensic Audit and Focused Correction Plan

**Date:** 17 November 2026, Asia/Karachi. **Status:** investigation complete; implementation subsequently authorized. This audit records the original baseline; current implementation and validation are documented in `HARDWARE_MATCHING_IMPLEMENTATION_REPORT.md`.

**Inspected baseline:** `feature/strict-vendor-commission`, `0f81261e6e757950eb421e4ab00dfbb6136b9ffc` (V). Source references below use this commit unless stated otherwise.

## Final focused plan — updated after user clarification

**Implementation authorized, with the user's clarification below taking precedence.** Reuse or correct the existing logic. Do not introduce a second hardware parser, warning formatter, warning renderer, pool selector, or feature rule engine.

**User clarification, 17 November 2026:** there is no “originally attached suffix only” policy. Preserve valid separate catalog model codes, suffixes and aliases, including `DWSI 2322 CX`. Matching catalog-declared codes can qualify the model whether spaced or attached. Candidate-only loose descriptions cannot invent hardware or override genuine model/variant conflicts. Preserve the existing exact-first and eligible fallback-with-yellow-warning flow; candidate-only ECO remains eligible Tier1 with the existing advisory. Earlier bound-only wording was an implementation interpretation and is withdrawn.

1. Disable active WiFi/IOT/Smart prose checks, including TV Smart/Non-Smart, their inferred capabilities, contradictions, fallbacks and notices. Keep literal manufacturer model/variant components intact.
2. Fix the shared extraction source: feature counts such as 4-Way cannot become model 4/capability WAY; normalization cannot manufacture MD-15ECO from separate MD 15 ECO; candidate-only loose designations cannot become hard hardware constraints or required series.
3. When model identity and remaining safeguards pass, an extra **unverified model-adjacent designation**, such as seller-added ECO, gets the existing yellow CROSS-CHECK NOTICE. Preserve its qualifying exact classification; warning alone does not create Tier2. Ordinary feature-count/marketing prose receives no new designation warning. Disabled connectivity prose receives no warning.
4. Use the existing sentence: `⚠️ [CROSS-CHECK NOTICE: Market listing includes '{designation}' not specified in target catalog]`. Generalize/reuse the existing sentence-building path rather than copying it into another branch. Set `compatibility_notice`; do not set `is_base_match`, `missing_modifier`, or a verified `detected_variant` solely to carry this advisory. If another real omission independently requires fallback, preserve that fallback and its warning.
5. Reuse current winning-offer notice selection, terminal yellow display, reason columns and XLSX highlighting. Correct the existing evaluator annotation helper so a selected exact offer's generic notice reaches its reason once. It currently can retain the notice metadata without adding this generic notice to the exported reason. Preserve current suppressed-status handling and prevent a non-selected seller's warning from leaking into the result.
6. Preserve T3/T4, current inverter matching, every active 1b physical guard, existing commented-out washer cross-architecture guard, model/variant/colour/capacity/alias rules, fixed vendor commissions and exact > base > sibling priority. Bump the existing matching policy version for checkpoint invalidation.
7. Add focused tests and run the full dependency-complete gates before claiming the fix complete. H3 inverter/polarity expansion, H5 missing-capacity sufficiency, H4 quantity redesign and the broader Phase 2 roadmap are separately documented follow-ups, **not part of this final immediate implementation scope**.

This clarification supersedes earlier suggestions that extra ECO should be silently accepted without a notice or that H3/H5 should automatically be bundled into the same approval. The historical reproduction results below remain unchanged.

## Evidence, authorization, and limits

- Read the supplied `PRICE_GENERATOR_MASTER_ARCHITECTURE_AND_SYSTEM_AUDIT.md` completely. The supplied file has 809 lines and ends after PG-H03. Its contents promise Parts 9–16, but those parts, including the full roadmap, are absent.
- A separate Phase 2 Starting Plan was not located. The user explicitly authorized proceeding with the available audit rather than waiting. No separate-plan review or complete milestone assessment is claimed.
- Inspected the older, implemented `tasks/plan.md`, its completed checklist, ADR-002, matching source, shared offer processing, series fallback, capacity/registry knowledge, checkpoint policy linkage, existing tests, and catalog/fixture data.
- The checkout initially showed `main` at `6a66118`; it changed externally during reference-document discovery to V. This investigation did not switch branches. Git comparison confirms matching, capacity, registry, series fallback, and shared offer-processing source has no difference between audit commit A (`f5a8189`) and V. The fixed vendor commission implementation is preserved.
- Loaded installed skills: using-agent-skills, debugging-and-error-recovery, python-pro, doubt-driven-development, code-review-and-quality, test-driven-development, incremental-implementation, documentation-and-adrs, and planning-and-task-breakdown. The exact skill name systematic-debugging is unavailable; debugging-and-error-recovery is the installed equivalent.
- One independent read-only agent challenged the correction. Its findings were checked against source and executable probes. Additional cross-model review was offered and explicitly declined.
- Executed pure Python offline probes through the bundled Python **3.12.14** runtime with `-B`, importing actual repository functions. No marketplace, database, upload, dependency installation, or production pipeline run occurred.
- This runtime lacks pytest, curl_cffi, Rich, Ruff, mypy, and Hypothesis. Consequently, **the full suite and lint/type gates were not rerun here**. The master audit's 1,128 passing tests on V are historical audit evidence, not results of this investigation.
- Catalog inspection covered 22 CSV files under input/fixture directories: 4,503 title observations and 4,169 distinct title/brand pairs, including duplicates, ERP shorthand, incomplete rows, accessories, and non-products. These are data-inventory counts, not validated products or accuracy measurements. Titles and brands came from existing columns, including `Original_Title`, `Brands`, and `Item Name`; no missing brand was guessed.
- Reproducible focused evidence is saved in [the read-only probe](evidence/hardware_matching_offline_probe.py) and [its current-source JSON results](evidence/hardware_matching_baseline.json). Run `python -B docs/evidence/hardware_matching_offline_probe.py` from a dependency-light interpreter. It prints JSON and performs no file/network writes. The 100-row corpus is `data/inputs/100_Products/Book1.csv`, every data row in order, header excluded; SHA-256 `7c2b1103dd4f8ea93655e11f4293678ddf574b8a49bd810ef1c0334309fd5978`. “Curated row N” means this 1-based data-row number. The JSON preserves full titles, extracted slots, reason/tier, controls, mutations that changed classification, and pool outcomes. The broader 22-file inventory is exploratory context rather than an immutable accuracy benchmark.

### User decisions captured during investigation

1. Proceed using the available master audit; prepare the complete future roadmap separately.
2. **Disable matching checks based on WiFi, IoT, and Smart wording, including Smart/Non-Smart TVs.** Their presence, absence, and opposing prose must not cause rejection, fallback, ambiguity, or compatibility warnings.
3. Preserve model, genuine variant, colour, capacity, and other existing technical safeguards. A literal manufacturer SKU component remains significant even if its spelling resembles a disabled prose feature.
4. Replace arbitrary short-word inference with a generic structural algorithm, not an ECO/WAY/ET blacklist or brand/category exceptions.
5. Do not implement production changes until the focused plan is explicitly approved.
6. Reuse the existing yellow warning sentence and existing display/export system for extra unverified seller designations such as ECO. Do not introduce duplicate warning logic. A warning alone must not demote an otherwise exact match to Tier2; genuine fallback decisions remain separate.

These decisions supersede older test assumptions that SMART proves IOT or that Smart/Non-Smart TV prose must reject. They do not authorize removing other hardware guards.

## Part A — Existing Hardware Logic Explained

The engine first cleans seller/payment text and extracts four slots: anchor model, residual series, guarded technical facets, and soft residuals. The referee then combines identity compatibility with a series of rejection and fallback rules. A matching model is necessary in model mode, but it does not override a later hardware rejection.

### Complete reachable control flow

```text
Raw marketplace item + catalog description + supplied brand
  -> offer_processing.parse_offers_with_tiers:295
  -> referee_match:5954 -> _referee_match:4610
       -> branch expansion of target/candidate:4626-4686
       -> extract_product_slots:3329, on each side
          -> separator/seller/parenthesis/slash cleaning
          -> extract_search_query_and_model:1523
          -> anchor + extract_tag:1958
          -> category, quantities, colour and physical facets
          -> capability polarity + short adjacent/glued tags
          -> residual subtraction -> series
       -> explicit series entry checks, if invoked:4690-4726
       -> API brand and candidate internal ambiguity/polarity
       -> brand, bundle, category, mounting, physical facet guards
       -> model/prefix/generation/variant compatibility
       -> series and sub-series compatibility
       -> extra hardware rejection / omitted hardware fallback
       -> capacity and colour guards
       -> exact / base / sibling decision
  -> shared parser partitions exact/base/sibling/owned offers
  -> offer_processing.finalize_offers:545
       -> stock-aware Tier 1 > Tier 2 > Tier 3
  -> source scraper -> pricing or range evaluation
```

Explicit last-resort series matching uses `series_fallback.py:34–69` and `referee_series_candidate:5965`; it delegates to the shared referee, with stricter initial identity checks. Ordinary anchorless named-series matching also exists within normal model mode. It is not equivalent to explicit series fallback.

`pipeline.py:1756–1791` reuses extraction/refereeing for passive learning. Registry synonym methods exist but are not called by the normal matching path; they do not currently decide whether ECO or another token is a real variant.

### Why a correct model still loses

`DWT-1165` is extracted identically from both ECO example titles. `_adjacent_model_tags:3295` accepts the following three-letter word because `is_sku_variant_tag:1418` accepts unexcluded 2–4-letter alphabetic tokens. Distribution at `3831–3844` promotes ECO into `capabilities`. At `5699–5720`, any extra candidate capability outside narrow exceptions is a hard conflict. The equality of the anchor does not bypass that gate.

In contrast, a candidate missing a target capability generally becomes Tier 2 at `5740–5762`, after the other guards pass. Thus the same unproved token rejects in one direction and demotes in the other. Moving ECO after the category stops adjacent extraction and changes the decision to Tier 1. This is a formatting-dependent decision, not evidence of a different manufacturer product.

## Part B — Actual Category Coverage

There are **seven shipping categories** in root `config.py:101`: dispenser, washing machine, microwave, air fryer, air conditioner, refrigerator/freezer, and LED TV. Shipping categories are not manufacturer-identity policies. They must not become a second matching rule engine.

The matcher recognizes ten macro families through `_detect_appliance_family:4547`: TV/display, microwave/oven, dispenser, air fryer, small kitchen, washer, refrigerator, deep freezer, air cooler, and AC. The inventory classified 1,824 distinct title/brand pairs into these families and left 2,345 unclassified. Many unclassified titles are abbreviated ERP names rather than unsupported products. Category columns are not passed as authoritative matching metadata.

| Actual category/subcategory | Current implementation and evidence | Identity/core distinctions to preserve | Descriptive or uncertain evidence; recommended handling |
|---|---|---|---|
| AC: split/wall, floor/cabinet, cassette, portable/window where recognized | Tonnage/code inference; AC decomposition; T3/T4, inverter, mode, mounting, colour; `3488–3600`, `3686–3759`, `4530–4590` | Full SKU/revision, approved base/sibling relation, opposing T3/T4 or inverter, explicit capacity/mounting/mode conflicts | Smart Frequency, air-throw counts and coil/warranty prose cannot invent connectivity/model identity. Keep existing T3 omission/prose-versus-attached policies. |
| Refrigerators: mini-bar, normal/top mount, large/side-by-side/french/multiple door | CFT, tub-like WB/GB codes, colour, door finish/structure, defrost and inverter; `3603–3683`, `5068–5263` | Encoded variant, CFT conflict, stated door finish/structure and defrost/inverter conflicts | Extra ECO/Smart cannot create a variant. Litres are currently lost. WB is interpreted differently in washer context. Do not introduce a new WB dictionary. |
| Freezers: chest/deep, vertical, single/twin door | Shared refrigerator-like facets; ES/EDS/IG can become variant capabilities; existing freezer tests | Actual model/suffix, finish/door, capacity and existing ES/EDS identity contracts | No inference from a token's length alone. Vertical-freezer and ERP D/F family recognition is incomplete. |
| Washers: automatic front/top load, single/twin tub, semi/manual, spinners/dryers | KG plus generic numeric model-to-KG heuristic; WB/GB, load, tub, automation; `3553–3563`, `3603–3677` | Encoded suffix/generation, 8KG/10KG, explicit front/top, single/twin and auto/semi conflicts | ECO is currently over-promoted. Inverter omission already permits matching. Cross-facet washer architecture guard is deliberately commented out at `5166–5208`; do not reactivate it. |
| Microwave/oven: solo, grill, combination/convection; built-in/mini/rotisserie in data | Model/series, global facets; no litre extraction; SOLO/GRILL stripped, convection mostly residual | Manufacturer SKU and existing short-model aliases; explicit quantity contradictions should ultimately be retained | 20L/30L currently accepts. Solo/grill contradiction acceptance is reproduced, but a universal new cooking-mode ontology needs verified category requirements. No invented model-specific specifications. |
| TV/display: LED, QLED, OLED, Full-HD/4K, Android/Google/Smart | INCH; Smart from literal or OS words; display detection is broader than macro family; `3532–3548`, `3733–3760` | Model, size, suffix/generation, explicit colour | User has explicitly removed Smart/Non-Smart as a matching criterion. QLED/OLED prose currently is not a guarded distinction; do not claim this patch adds it. |
| Dispensers: top/bottom load, bottle, refrigerator cabinet, glass door, taps | Tap count only if another capacity was not selected; litre volume omitted; global load/finish/mode helpers also run | Model, finish/colour, existing tap-count conflict behavior | Bottle loading must not become washer architecture. Heating/cooling semantics are not modeled as a dedicated dispenser policy. Independent quantities cannot safely share one scalar forever. |
| Air fryers: manual/XL and digital descriptions in data | Macro-family detection and generic model/facets; no litre/power constraint | Actual suffix/model and explicit existing variants | XL and other short words can be mistaken for hardware; no verified universal XL removal rule is proposed. Volume/power descriptions do not prove distinct SKUs without stronger evidence. |
| Small kitchen: blender, chopper, kettle, juicer, food processor, sandwich maker, toaster, hand/stand mixer, citrus, coffee, grinder/mincer | Some share SMALL_KITCHEN; others are unclassified. Generic code/colour/facets apply | Full model and demonstrated manufacturer variants | No dedicated power, speed or cooking-technology incompatibility rule exists. Do not turn wattage/speed marketing into a model, or claim these categories already have complete guards. |
| Air/room/desert/evaporative coolers | AIR_COOLER family for some spellings; generic facets; no litre tank-volume guard | Model/variant and existing colour/category safeguards | Tank litres and speed counts are observations; not automatic SKU identity. |
| Other actual categories: air curtain, fan, air purifier/water purifier, insect killer, geyser/storage heater, hob/range/built-in oven, hood, hot plate, infrared/induction cooker | Present in category columns; most lack distinct matcher families despite some CATEGORY_PATTERNS support | Model/variant/colour; explicit known constraints only | No fabricated category-specific hardware guarantees. Foot length, litres, wattage and heating methods require context before becoming identity constraints. |
| Garment steamers/irons, personal care/hair straightener/dryer/shaver, accessories/spare parts/WiFi device, soundbar/manual-review items | Present in catalogs/fixtures; often unclassified; iron/mincer real regression fixtures exist | Exact model and preserved code/colour variants | A genuine WiFi accessory must still be identified by its model/product identity. Disabling connectivity prose does not make a WiFi device equivalent to an AC. Non-products/review rows are not matching accuracy evidence. |

**Important distinction:** explicit contradictory source claims can be detected without claiming which manufacturer's specification is correct. No external manufacturer specification was verified during this offline investigation.

## Part C — Complete Hardware Rule Inventory

All references are in `pricing_engine/matcher.py` unless a different module is named. "Early" means the rule can reject before full model compatibility; "late" means a model-compatible result can still reject/demote.

| Mechanism / actual owner | Activated by / evidence and vocabulary | Comparison and consequence | Existing protection/tests |
|---|---|---|---|
| Slot/result types `34–106` | Title-derived capacity, tub/colour/finish/mode/door/load/automation/defrost/inverter; positive/negative/ambiguous sets | Mixed physical and inferred word evidence share authoritative fields; no origin/span roles | model identity, generic polarity suites |
| Optional tags `13–31` | Catalog `[OPT:...]`, `[ALLOW:...]`, `[IGNORE:...]` | Exempt listed extra/missing capability checks; do not establish SKU equality or override polarity conflicts | generic variants/polarity suite |
| Colour vocabulary and inference `126–317` | Nine families, 13 suffix codes; names, parentheses, slash, encoded SKU | Both-known opposing families reject late; inferred shared-SKU colour exception `4121`; missing colour often accepted | model_identity_evidence; own_store_deduplication |
| Capability scanner `330–344` | `NON/NO/WITHOUT/NOT` + T3/T4, UV, ADS/ADS+, WIFI/WI-FI, IOT, SMART | Global recognition; canonical token and polarity | generic_variants_and_polarity |
| AC suffix/decomposition `322–366` | Technical slash code plus two-digit/three-letter stem shape, optional 1–2-letter edition | Subordinate revision capture, AC DC inverter inference, guarded base/sibling relation | generic variants Slices B/C; forensic tests |
| Query/category/spec vocabulary `368–788` | SAFEGUARD_PATTERN, TAG_PATTERN, CATEGORY_PATTERNS; 299 NON_SKU_TOKENS and 15 sub-series words | Keeps/removes tokens before identity; PRO/PLUS/roman editions are series, not ordinary code tags | matcher, structural measurements, polarity suites |
| Plus, units, ERP, seller/marketing normalization `790–1415` | Parenthetical plus/features; W/L protection, SKU prefixes; R/F etc.; seller trailers; measurements/year/resolution/count shapes | Can prevent or manufacture later identity. No proof that every remaining word is a model. Spec/seller trailer tests preserve real claims | audit_remediations; structural_measurements; model_identity_evidence |
| Short-code predicate `1418–1471` | Excludes units/colours/series, then accepts 2–4 alphabetic letters or short alphanumeric forms | Structural candidate predicate is reused as semantic hardware proof; root H1 | matcher and pipeline_resilience; coverage misses ECO |
| Capacity knowledge `1474–1521`, registry `7–26,61–80,151–193` | Registry seeded brand/universal capacity codes | Code-to-ton inference, not proof of capability or aliases; matcher keeps seed-derived copies | registry; capacity_contract; benchmarks |
| Model/query extraction `1523–1955` | Prefix+number joining, following short tokens, first digit-bearing token, name-only series fallback | Query and raw model construction can absorb prose. Spaced MD 15 ECO can become MD-15ECO before facet checks | matcher; model_identity_evidence; architecture_contract |
| Tag splitting `1958–1988` | Slash finish, hyphen suffix, glued alpha tag, single-letter washer suffix, TAG_PATTERN | Preserves or separates real variant and prose using the same predicate. Must retain a valid anchor after splitting | washer/freezer and short-alias regressions |
| Adjacent tags `3283–3326` | Contiguous post-anchor 2–4-letter words, recognized orthogonal tags; stops at category/spec/prose/delimiter | Complete-code heuristic stops alphabetic words >2 only for some anchors; numeric models still admit ECO | model_identity_evidence:41 has CASH/IRON/MEAT but not general ECO case |
| Slot cleaning/anchor `3329–3511` | Raw normalized title, query extraction, prefix/first-digit fallback, tag split | Can select 4-Way then split to bare 4; can select Pular-T3 then leave alphabetic Pular. Not all extracted anchors are verified manufacturer models | generic/model/architecture suites |
| Quantity extraction `3532–3602` | First INCH, else CFT, else KG, else numeric-stem KG heuristic, else AC ton; TAP only if empty | Single scalar; no L path despite capacity.py L support; missing one side skips later comparison | capacity_contract; matcher tap tests |
| Physical facets `3520–3531,3603–3731` | WB/GB; GD/glass door, INOX/stainless/S.S, METAL; SD/DD; TT/ST/twin/single; FA/automatic/semi/manual; FL/TL; no-frost/direct-cool; cool-only/heat-cool; inverter/INV/SAVEIN/SVN/DC | Mostly title-wide, often not gated to a category/subject. Opposing known values generally reject early | audit_remediations; forensic_regressions; generic variants |
| Inverter extraction `3708–3731` | NON-INVERTER/fixed speed/conventional wins; otherwise INVERTER/INV/SAVEIN or encoded clues | NO/NOT/WITHOUT INVERTER not recognized as negative; internal positives/negatives collapse into one boolean | Non-Inverter protection exists; extended negation gap reproduced |
| SMART/connectivity `3743–3767` | SMART->IOT outside display; Google/Android/WebOS/Vidaa -> display SMART; WiFi can remove positive IOT | Unsupported semantic conversion and category-dependent behavior; later user explicitly disables this criterion | pipeline_resilience:656–673; haier_benchmark:156; generic variants:1258 |
| Generic extra-tag distribution `3770–3852` | First split tag, anchor tail, adjacent tags, global glued-stem scan; static dedicated-slot exemptions | Adds remaining tags to caps. A unit suffix can only enter if it passes the predicate; RPM is actually blocked by NON_SKU_TOKENS | pipeline_resilience:678; matcher:1173–1218 |
| Residual/series feedback `3872–4008` | Remove parents/brand/categories/specs/colours/capabilities/residuals; remaining token sets | Word role changes can move a defect from hardware veto to series veto; must fix canonical classification | series_contract; model_identity_evidence |
| SKU qualification `4068–4118` | Complex alphanumeric shape or prefixed numeric model plus any capability/code colour | Arbitrary caps can strengthen identity and change series sufficiency. Verified bound-code evidence is required instead | real listing regressions |
| Early candidate ambiguity/polarity `4749–4790` | Candidate ambiguous set; positive-negative intersections (ADS family handling) | Rejects before model proof. Target ambiguity is not checked. Recognized retained constraints need symmetric handling | generic polarity Rules A/B |
| Brand/bundle/family/mount `4793–5030` | Supplied/API/title brand, dynamic prefix, bundle shapes, macro family, AC form factor | Early conflict; explicit series also requires positive family. No hardware relaxation may bypass these | audit_remediations; series_contract |
| Tub/finish/door/load/tub/automation/defrost/inverter/mode `5033–5263` | Known opposing physical values; finish omission; 5-digit GD omission exception | Early reject; finish can defer Tier2. SD/GT omissions are direct-match policy. Cross-facet washer guard disabled | pipeline_resilience; forensic_regressions |
| Model/variant/generation `4018–4530,5265–5502` | Ordered prefix abbreviation, structured numeric comparisons, attached/delimited suffix, EX edition, colour, omitted capacity-led suffix, single-letter/lid mappings | Core mismatch rejects; permitted omissions defer fallback. Existing literal suffix protections must survive | own_store_deduplication:533–650; matcher; series_contract |
| Series/subseries `5504–5659` | Target tokens, candidate normalized text, complete-SKU evidence, PRO/PLUS/single-letter prefixes | Missing tokens may reject, self-contained SKU can relax prose; E-Chrome and real series distinctions preserved | own_store_deduplication; series_contract |
| Late capabilities `5661–5762` | Extra caps hard reject; T3 inherent-prose exception; connectivity additions sometimes fallback; missing target caps fallback | Exact compatible anchor can be rejected or demoted here. T3 prose versus attached suffix is deliberately different | generic polarity Rules C/D; pipeline_resilience |
| Final quantity/colour/tier `5764–5951` | Both-known capacity, colour; base/subedition comparison; deferred omissions | Capacity/colour veto before returning Tier1/2/3. Omissions cannot bypass a real conflict | forensic, generic, offer-processing suites |
| Explicit series contract `4690–4726,5965–5997`; series_fallback | Explicit brand/family, equal complete series, positive equal capacity, no unverified candidate SKU | Prevents target-SKU substitution; stricter than ordinary series mode | series_contract; series_fallback |
| Legacy public matcher `2271–2606` | Keyword expansion, containment, colour/finish, dynamic initialisms and brand-initial regex | Separate Boolean contract can bypass guards; normal parser does not call it | matcher; master PG-M06 |
| Shared pool/diagnostics, offer_processing `295–487,545–644` | MatchDecision tier, stock, price, seller, deduplication | Chooses one active tier; definitive facet rejection can report complete empty pool without suspicious-review state | offer_processing_contract; scraper diagnostics |

Existing static lists and category/brand branches are documented as current facts, not endorsed as new design. A focused correction must add no new brand/prefix/category exceptions and must not opportunistically rewrite all historical vocabulary.

## Part D — Hardware Overreach Findings

### Reproduced original cases

| Case | Target -> candidate; extracted identity and facts | Gate -> current decision | Competitor consequence |
|---|---|---|---|
| D03a / H2 | `Dawlance 1.5 Ton Inverter Mega Flex 30 Split Air Conditioner` -> `Dawlance 1.5 Ton Mega Flex 30 Smart Frequency AC`. Target anchor empty, series Mega Flex, 1.5T, caps empty; candidate anchor empty, series Mega Flex Frequency, 1.5T, caps IOT | `3744–3750` fabricates IOT; `5723–5738` -> `BASE_MATCH`, Tier2 | Raw replay: Electronics World 154255 in base pool; Home Cart 164499 in exact pool; selected only Home Cart. Correct discounted-price parsing; wrong identity classification. |
| D03b / H1 | `Dawlance 2 Ton Inverter Glacier 45 Pro T3 Floor Standing Air Conditioner` -> title containing `Glacier Pro 45 T3 \| 4-Way Air Throw \| Gold Fin Coils`. Target anchor empty/caps T3/2T; candidate anchor 4/caps T3+WAY/2T | First digit-bearing feature token and `extract_tag` -> bare 4; extra WAY veto -> `FACET_CONFLICT`, no tier | Candidate removed. Pure one-item payload replay finalizes as COMPLETE_NO_COMPETITORS. |
| D03c / H1 | `Dawlance DWT-1165 Washing Machine` -> same plus adjacent ECO. Both anchors DWT-1165; target caps empty, candidate caps ECO | Generic adjacent token -> `FACET_CONFLICT`, no tier | Candidate removed; one-item payload finalizes as COMPLETE_NO_COMPETITORS. |

Both marketplaces use this shared acceptance/finalization path. These are offline replays of reported titles/prices, not fresh observations of current stock or prices. No new financial final-price claim is made.

### Additional manifestations, grouped rather than counted as separate root causes

| Controlled input | Extracted model/capability result | Current result/reason | Interpretation |
|---|---|---|---|
| Reverse ECO case: target includes ECO, candidate omits it | Same DWT-1165; target ECO, candidate none | BASE_MATCH/Tier2, hardware omitted | Reveals catalog-side ambiguity. Proposed compatibility policy deliberately preserves this omission outcome when the catalog presents ECO as a model-adjacent code; it does not claim to prove ECO's manufacturer meaning. |
| Candidate `DWT-1165 (ECO)` | Same anchor; ECO capability | FACET_CONFLICT/no tier | Parentheses do not provide variant provenance. |
| Candidate `DWT-1165 Washing Machine ECO` | Same anchor; ECO is series, no capability | ACCEPTED/Tier1 | Moving the same word changes its authority. |
| Curated microwave row 4: insert ECO after spaced `MD 15` | MD-15 -> MD-15ECO, no caps | MODEL_CONFLICT/no tier | Earlier model joining can fail before the capability veto. |
| Curated rows 7, 8, 31, 44, 54, 56, 99: add adjacent ECO | DWSI-2322, 9106, DBD-1034, DW-297, DWDI-1020, DWT-1471, DWMM-6001 retain core; candidate gains ECO | FACET_CONFLICT/no tier | Same rule affects iron, refrigerator, dispenser, microwave, washer and mincer. Synthetic mutations of real catalog titles. |
| Add Smart Performance to numeric-model microwave, fridge, iron, dispenser or mincer | Same anchor; IOT added | BASE_MATCH/Tier2 | Cross-category connectivity manufacture. |
| Same Samsung 8KG washer + `6 Inch LED Display` | Same WA80CK4240BWRT; capacity becomes 6INCH instead of 8KG | FACET_CONFLICT/no tier, 8KG vs 6INCH | A component display size overwrites the appliance's main capacity. |

### Controlled 100-row experiment

All 100 curated products self-matched as Tier1. Appending five phrases produced 500 probes:

| Appended phrase | Tier1 | Tier2 | Rejected |
|---|---:|---:|---:|
| Smart Frequency | 65 | 35 | 0 |
| WiFi | 65 | 35 | 0 |
| Without WiFi | 100 | 0 | 0 |
| `\| 4-Way Air Throw` | 86 | 0 | 14 |
| `\| Premium Performance` | 100 | 0 | 0 |

These counts show sensitivity to controlled wording and existing SKU heuristics. They are not measured marketplace recall, precision, defect rates, or evidence that every appended claim describes the actual product.

## Part E — Missing Hardware Protections

| Reproduced claim comparison | Model/capabilities/current result | Finding and disposition |
|---|---|---|
| Samsung WA80CK4240BWRT 8KG Inverter -> same `Without Inverter`, `No Inverter`, or `Not Inverter` | Same model, caps empty; both inverter=True; ACCEPTED/Tier1 | **Confirmed H3.** Negation support differs between capability scanner and inverter boolean. Recommend retained-core polarity correction as a separate safety slice. |
| Same Non-Inverter target -> candidate `Inverter Non-Inverter` | Same model; candidate inverter=False, ambiguity empty; ACCEPTED/Tier1 | **Confirmed H3.** First-precedence boolean hides internal contradiction. |
| Haier HSU-18HFP target `T3 Non-T3` -> candidate plain or T3 | Target ambiguous T3 set; target positive empty; candidate same model; ACCEPTED/Tier1 | **Confirmed H3.** Rule A checks candidate only. |
| DW-MD15 20 Ltr -> MD15 30 Ltr | Alias anchors valid, both capacity=None, caps empty; ACCEPTED/Tier1 | **Confirmed H4 / PG-M04.** L exists in capacity.py but is never extracted into matching facets. |
| Samsung 8KG -> same SKU `8KG 10KG` | First 8KG retained; ACCEPTED/Tier1 | **Confirmed H4 / PG-M04.** Multiple same-dimension claims erased. |
| Midea YL2037S, target `3L 2 Taps 1KG` -> candidate `3L 3 Taps 1KG` | Both capacity=1KG, caps empty; ACCEPTED/Tier1 | **Confirmed synthetic H4.** Another quantity hides the genuine tap conflict. No upstream incident claimed. |
| Mega Flex 30/1.5T -> Mega Flex without candidate quantity | Both anchorless; candidate capacity=None; ACCEPTED/Tier1 | **Confirmed H5 / PG-M08.** Ordinary series path does not enforce explicit-series evidence minimum. |
| Same DW-MD15 Solo -> Grill, or same TCL 55C645 QLED -> OLED | Same model; no separate guarded cooking/display technology value; ACCEPTED/Tier1 | **Text-acceptance gap confirmed; manufacturer SKU consequence unverified.** Do not invent universal exclusivity tables. Keep outside immediate PG-M01 correction pending verified technical contracts. |
| DWMM6001 600W -> 1000W | Same model; wattage remains residual; ACCEPTED/Tier1 | **Observation, not automatically a defect.** Rated/peak/marketing power can differ. Identity-changing significance requires evidence. |

Adjacent audit findings were narrowly checked, not reinvestigated as new hardware bugs: numeric component flattening ZN-123-45/ZN-12-345 accepts; multiple HWM models under one scalar price accept; legacy containment differs from normal referee. They remain PG-M03/05/06 and are excluded from this implementation bundle.

## Part F — Root-Cause Map

**Five directly relevant root-cause groups are confirmed.** Multiple symptoms are not five independent ECO/Smart/Glacier bugs.

| Group | Underlying cause | Symptoms / audit relationship | Proposed scope |
|---|---|---|---|
| H1 | Tokens lack role/source/span provenance; length, adjacency and first-digit shape substitute for identity evidence | ECO/WAY, MD15ECO, feature anchor, series feedback and fabricated SKU qualification; PG-M01 | Immediate focused correction |
| H2 | Unproved connectivity semantics plus category/SKU-dependent comparison policy | SMART->IOT, display SMART, extra/missing connectivity demotion; PG-M01 plus user policy change | Immediate focused correction: disable all three prose criteria |
| H3 | Polarity and ambiguity are inconsistent across fields and sides | Without Inverter read positive; contradictory target ignored | Separate retained-core safety slice proposed for approval |
| H4 | One prioritized quantity loses dimension, subject and contradictions | Litres absent; screen overwrites KG; conflicting KG/taps hidden; PG-M04 | Explicitly deferred capacity work; no partial scalar-only litres patch |
| H5 | Identity sufficiency differs by referee entry path | Anchorless ordinary series accepts missing capacity; PG-M08 | Separate small identity-sufficiency slice proposed for approval |

No universal manufacturer hardware ontology was established. Unknown physical significance and incomplete source metadata remain evidence limits, not extra confirmed bugs.

## Part G — Current Versus Recommended Behavior

"Exact" below always requires independent identity and remaining guards; ignoring prose never supplies missing identity.

| Comparison state | Current behavior | Proposed immediate behavior / boundary |
|---|---|---|
| Same catalog manufacturer model, extra standalone unverified prose | May reject as extra cap or alter series | EXACT if other guards pass; extra prose has no identity authority. An unverified model-adjacent designation gets the existing yellow cross-check notice; ordinary descriptive/count prose does not. |
| Same model + Smart Frequency | Some numeric/series targets Tier2, other SKUs exact | EXACT if other evidence passes; no connectivity warning |
| Same model + WiFi/IOT/Smart, omitted or opposing wording, including TVs | Tier1/Tier2/conflict/ambiguity depend on category and shape | Ignore these prose claims consistently, per explicit user decision |
| Different literal model/suffix, even suffix text happens to be IOT | Can differ via hardware/model routes | Preserve MODEL/VARIANT comparison; no global deletion inside SKU spans |
| Same model, remaining explicit technical contradiction | Generally rejects; some negations missed | CONFLICT/REJECT; extend retained inverter negation in H3 slice |
| Same base, catalog-declared different genuine edition | Reject or existing authorized fallback | Preserve existing edition comparison and authorized base/sibling outcomes |
| Catalog declares ES, candidate ES8 | Conflict | CONFLICT; no new ES dictionary |
| Catalog declares ES, candidate omits it | Tier2 | Existing BASE fallback only; do not turn omission into exact equality |
| Bare catalog base, candidate adds an unverified standalone model-adjacent designation, e.g. ECO | Generic hardware rejection | Word alone cannot establish variant; same independently established catalog identity stays exact with the existing CROSS-CHECK NOTICE. Bound model components remain significant. |
| Same model, descriptive feature omitted | Depends on inferred caps/series | Exact when truly descriptive; actual declared/core constraints retain their current policy |
| Extra feature-count phrase | May create anchor/capability | Observation only; cannot strengthen identity or veto by itself |
| Same series without reliable model and missing capacity | Ordinary path may accept | INSUFFICIENT EVIDENCE in proposed H5 slice; never invent an exact SKU |
| Different SKU, same physical capabilities | Usually rejects; known component/multi-model gaps exist | REJECT via existing model guards; adjacent audit defects remain separately tracked |
| No reliable model, superficially similar hardware | Can reach weak series matching | INSUFFICIENT EVIDENCE; retained shared series contract and H5 minimum |
| Approved DW-MD15/MD15 alias with equivalent evidence | Exact | EXACT; preserve short-prefix collision tests |
| E-Chrome vs Chrome/Chrome Pro | Reject | REJECT unchanged |
| Extra optional T3 prose on specific eligible alphanumeric AC model | Tier1 plus optional-spec notice | Preserve this existing narrow policy; attached upgraded SKU-T3 remains different |
| Target T3, candidate omits T3 | Tier2 | Existing BASE fallback unchanged |
| Target T3, candidate T4/Non-T3 | Reject | REJECT unchanged |
| Unknown category-specific claim not already represented | Inconsistent/no dedicated guard | Do not fabricate a new hard constraint; record limitation and seek verified requirements for future work |
| Explicit multiple-model listing under one price | May accept first model | Should ultimately be AMBIGUOUS/REVIEW under PG-M05; not claimed fixed here |
| Internally contradictory retained target/candidate capability sets or inverter claims | Candidate capability ambiguity rejects; target/inverter gaps | AMBIGUOUS/REVIEW in H3. Internal contradictions in other scalar physical facets remain separately tracked limitations; quantity ambiguity belongs to H4. |

### Price-pool consequences

The correction must place the Electronics World Mega Flex offer into the **exact** pool for the right identity reason, then retain Home Cart as another exact competitor. It must not combine genuine fallback and exact pools. The pure shared pool checks passed for exact, base, and sibling precedence.

For the ECO case, reuse the existing sentence template at `matcher.py:5891–5892` (also used by the current exact dual-colour path at `4672–4674`). The final proposed result is **ACCEPTED / Tier1 plus advisory notice**, provided independent identity and all retained guards pass. Reuse `offer_processing._select_winning_compatibility_notice:92` and the current terminal/card/summary/export flow; no separate ECO warning system. Only the selected reference offer supplies the active advisory. A cheaper genuine fallback still cannot override an eligible exact pool.

Rejected ECO and Glacier one-item replays produced zero selected offers and `COMPLETE_NO_COMPETITORS`, not a suspicious-review state, because the generic facet rejection is currently considered definitive. This can supply a false empty-market premise to downstream pricing. No financial formula or monopoly policy change is proposed; correct inclusion at the source removes that premise for these cases.

## Part H — Clean Correction Design

### Immediate PG-M01 correction: one canonical interpretation

1. **Preserve model evidence before cleaning.** Reuse existing normalization/unit protection, but retain raw span boundaries, prefix/core and suffix attachment for selected model evidence. Query construction and slots must consume the same classification. An originally attached component and a token joined by normalization are different evidence: formatting joins may normalize a proved prefix/core boundary, but may not promote a following loose word into an originally attached suffix. In particular, joining spaced `MD 15` never licenses joining its following ECO into `MD-15ECO`. Do not add a second parser in scraper/offer-processing code.
2. **Validate the post-split anchor.** A feature token cannot leave a bare one/two-digit anchor after its descriptive tail is stripped; an alphabetic remainder of a series-plus-T3 badge is not an independent numeric manufacturer model. Continue searching for actual model evidence. If none exists, retain existing named-series identity rather than fabricating an anchor. Short prefixed MD15/Icon2 and approved aliases retain their full structural evidence.
3. **Separate model components from loose words.** Originally attached/glued/delimited suffixes belonging to an established SKU remain model/variant evidence; synthesized attachment never acquires that authority. Existing separate catalog model-code sequences remain comparison constraints under the explicit source-trust policy below. Alphabetic words added only in seller prose cannot become authoritative merely because they are 2–4 letters long or next to a number.
4. **Use an explicit catalog-source policy for separate edition tokens.** For compatibility, treat the separate code sequence in the catalog's selected model expression as declared by the catalog, not as a manufacturer fact discovered by a heuristic. This retains the existing generic code-token boundaries and approved ES/CX/PL-style contracts without a new token list. After a shared base is proved, align those declared tokens with candidate model components in order. A matching declared token remains meaningful alongside extra seller words. If absent, use its existing omission/fallback policy; if a conflicting code occupies its declared position, retain rejection. Candidate-only loose words outside a satisfied declared sequence do not declare a new variant. **Reverse ECO is therefore explicitly Tier2 under this compatibility policy; only candidate-added ECO against the bare DWT-1165 catalog becomes exact.** Changing a catalog-side ambiguous word into non-identifying prose needs an explicit model field or a later catalog correction, not a hidden semantic guess.
5. **Keep descriptive evidence descriptive everywhere.** Do not place it into capabilities, model qualification, required series, or single-letter variant synthesis. `_complete_sku_evidence_level` must require bound/code evidence rather than an arbitrary nonempty capability set. Cleaned spans must not be re-read as raw authority by series/referee helpers.
6. **Disable connectivity prose comprehensively.** Remove WiFi/WI-FI/IOT/SMART from active capability/polarity extraction, display/OS-derived SMART addition, synonym conversion, extra-connectivity fallback, missing-connectivity fallback, ambiguity and warning synthesis. Retain noise cleaning of these words outside protected model spans. Do not delete substrings from actual models. This implements the user's request to disable the checks; avoid leaving duplicated commented implementations.
7. **Retain core decisions and interfaces.** T3/T4, ADS/ADS+, UV, remaining physical facets, colours, prefixes/generations, approved aliases and base/sibling relations remain active. Exact/base/sibling finalization stays unchanged. Increment `MATCHER_POLICY_VERSION` so existing checkpoints cannot reuse old classifications.
8. **Reuse the existing advisory notice path.** Classify extra potential designation tokens once while interpreting the source; carry their observed spelling without promoting them into hardware/variant truth. Where the selected model is otherwise compatible, reuse the existing CROSS-CHECK sentence and `MatchDecision.compatibility_notice`. Keep `is_match=True`, `is_base_match=False`, `match_tier=1`, and leave fallback-only metadata unset for this advisory alone. Genuine independent omissions/conflicts still control their existing decisions. Refactor the existing sentence-building path into one canonical owner if needed; do not add a parallel formatter or copy the same template into a new matching branch.
9. **Correct existing annotation propagation, not pricing.** In `evaluator._apply_compatibility_and_fallback_annotations:255–320`, generic raw compatibility metadata currently need not be prepended to `reason`, while exporter yellow fill reads the reason fields. Make the existing helper propagate the selected advisory once into the platform reason and compatibility metadata, preserving its current suppressed statuses and existing fallback notices. Existing `pipeline.py:1455–1472,1880` display and `exporter.py:365–374` highlighting then consume the same notice. Do not force the advisory through `missing_modifier`, as that can invent fallback semantics.

### Evidence boundary and tradeoff

There is no reliable text-only theorem distinguishing two structurally identical strings such as a loose ECO and a loose unknown manufacturer edition. A universal length/uppercase/entropy rule cannot prove that distinction. The proposed generic contract uses the trusted catalog identity, actual SKU attachment, existing declared code positions and explicit technical constraints; it does not claim to infer manufacturer truth from arbitrary seller words.

Consequently, an unencoded candidate-only edition described solely by an unfamiliar loose word may remain unresolved as a real-world product distinction. Likewise, the source-trust policy preserves a catalog-side model-adjacent code even when its manufacturer meaning is unverified. This deliberate asymmetry protects current catalog variant contracts; it does not resolve every H1 manifestation or promise target-prose invariance. Preventing these underlying catalog/source omissions would require verified model/variant metadata or a separately approved review policy, not another heuristic blacklist. This limitation must remain visible in review and tests.

### Separate follow-ups requiring later authorization

- **H3 retained-core safety:** recognize bounded NON/NO/NOT/WITHOUT inverter claims through one polarity helper, distinguish omitted inverter from explicit negative, and quarantine contradictions in retained capability sets and inverter claims on both target and candidate. Return existing AMBIGUOUS/no-tier for those internal contradictions; keep explicit between-side contradictions as FACET_CONFLICT. Disabled connectivity words do not participate. Internal ambiguity in scalar door/load/tub/finish/operating-mode/defrost fields is outside this slice; their existing between-side conflict guards remain active.
- **H5 identity sufficiency:** require positive equal capacity for anchorless named-series identity in ordinary and explicit-series modes. Reuse the existing exact `Capacity` value type; no target SKU substitution or new fallback relation. Return SERIES_UNCERTAIN/no tier when the ordinary path lacks sufficient capacity evidence.

**Deferred H4:** retain all observed quantities by dimension and subject, detect same-dimension contradiction, and add explicit litre coverage without masking tap/KG/INCH facts. This requires a separate capacity contract; merely placing L earlier in the current scalar priority would break existing dispenser tap checks. It is documented, not silently bundled with PG-M01.

No new runtime dependency, network lookup, cloud registry, category rule engine, catalogue column, public CLI option, export column, or pricing API is required for the immediate correction. Any internal role/provenance field added to ProductSlots must have a default for compatibility and stay private to interpretation; existing public call signatures and MatchDecision reason/tier shapes remain stable. H3/H5 are not automatically authorized with this immediate correction.

## Part I — Exact Implementation Scope and Acceptance

| Slice / existing owner | Required change and expected behavior | Tests / risks / preserved protections |
|---|---|---|
| 0. Evidence contract and regression fixtures | Record approved prose-versus-model rules and user connectivity policy. Add failing tests before code. Preserve current A/V shared baseline. | Known cases, controls and both sources. Existing test counts are not a substitute for new behavior tests. |
| 1. matcher: extract_search_query_and_model, extract_tag, anchor extraction, _adjacent_model_tags, post-code distribution | Share structural evidence classification; reject fabricated count/series anchors; keep loose prose out of model/caps/series authority. Align declared variant sequence; preserve attachment and actual suffixes. | D03b/c; spaced MD15+ECO; before/after/parenthesized/reordered counts; ES/ES8, PL/FLP, suffix/generation and alias negatives. Risk: model/query behavior is coupled; inspect query deltas. |
| 2. matcher: capability scanner/extractor and late comparison branches | Disable all WiFi/IOT/Smart prose criteria, including TV and OS-derived Smart. No connectivity-specific warning or fallback. | D03a, every category, positive/missing/negative/internal/TV forms; literal SKU suffix remains meaningful. Existing contradictory expectations must be rewritten explicitly, not broadly deleted. |
| 3. matcher: _complete_sku_evidence_level, residual/series consumers, MATCHER_POLICY_VERSION | Shared model-code evidence includes valid separate catalog codes and attached components. Candidate-only words cannot qualify a model or re-enter required series. Invalidate prior matching fingerprints. | Preserve DWSI 2322 CX and real fixtures, 100-row differential, E-Chrome, same-family isolation, optional T3 and active legacy contracts. No new attached-only restriction or blanket guard bypass. |
| 4. Existing notice construction and evaluator annotation | Reuse one CROSS-CHECK sentence owner for an eligible extra designation; carry it without making an exact offer a fallback. Correct `_apply_compatibility_and_fallback_annotations` to include that selected generic notice in the reason once. | Exact ECO notice, multiple generic designations, existing true fallback, selected winner only, no duplicate prefixes, terminal/CSV/XLSX marker parity. Reuse existing presentation; no new renderer or schema. |
| Later, not immediate: H3 retained-core polarity | Symmetric ambiguity and bounded inverter negation, only after separate authorization. | Current inverter behavior stays unchanged in the immediate fix. |
| Later, not immediate: H5 ordinary series minimum | Positive equal capacity for anchorless identity, only after separate authorization. | Current fallback eligibility is not broadened or silently tightened in the immediate fix. |
| 5. Tests and documentation around shared consumers | Prove parse -> tier -> final pool -> pricing/range behavior, including advisory propagation, stock and owned cases; update focused evidence documentation. | `offer_processing.py` selection algorithm should not need modification. Scraper adapters, fixed commissions, evaluator mathematics, registry/cloud, output schemas and existing plans remain unchanged. |

Expected implementation is concentrated in matcher and focused tests. A new module or widespread rewrite is not a prerequisite. If implementing the role contract requires changes outside this boundary, stop and explain the concrete dependency before expanding scope.

### Required regression scenarios and independent oracle

The oracle consists of explicitly asserted fixture identities/variants, literal source model components, existing approved relations, explicit retained physical contradictions, and the user's disabled-connectivity policy. Current extracted sequences are not independent proof of manufacturer truth. The catalog-code source-trust policy is a declared compatibility rule, tested separately from manufacturer-equivalence claims. Do not use current engine output as the desired truth.

1. Original D03a/b/c, 1T and 1.5T Mega Flex, Glacier ordering/count variants; record full extracted evidence and reason/tier.
2. Structural prose: 2–4-letter additions, mixed case, punctuation, parentheses, before/after model, seller clauses, numbered features, hyphenated counts and irrelevant numbers. Verify source-side prose cannot move into series, variants or SKU-strength evidence.
3. All ten recognized families plus actual unclassified-category representatives; manufacturer-model positives and different-model negatives. Corpus cases are clearly separated from synthetic mutations.
4. All disabled feature forms: WiFi/WI-FI, IOT, Smart, Non-Smart, No/Not/Without, target/candidate reversed, mixed words, Android/Google/WebOS/Vidaa; TV included. Their prose changes alone must leave matching tier/reason class unchanged.
5. Literal suffix/edition protection: bound versus loose tokens; PL/FLP, ES/ES8, EDS, numeric revision/generation, EX extension, approved AC base/sibling, existing colour/lid variants. Different actual model components cannot become exact because the prose criterion was disabled.
6. Negative controls: T3/T4 and Non-T3, ADS+/Non-ADS+, UV polarity, explicit non-inverter, capacity, colour, mounting, defrost, finish, load/tub/automation, E-Chrome/Chrome/Pro, short-prefix and numeric boundary guards, DW-MD15/MD15.
7. Future H3/H5 suites are specified separately and are not criteria claiming those defects fixed by the immediate correction. Preserve current inverter omission/opposition and series guard regressions now.
8. Pool integration on **both** Alfa and Digi: exact+base+sibling, each absent in turn, sold-out exact, duplicates, own stores, cheaper corrected exact offer, unaffected true base fallback. Assert specific vendors/prices and tier membership, not only match count.
9. Price/range integration: corrected same-identity listings are included; fake empty market no longer results from PG-M01; existing formula/rate invariants and active-pool priority remain intact. Do not change financial policy to make a new expected price pass.
10. Resume: matching policy version changes fingerprints on Alfa, Digi and all-platform modes; no checkpoint deletion required. Real fixtures, typed ProductSlots callers, series callers and passive learning remain compatible.
11. Advisory notices: bare DWT-1165 catalog versus seller DWT-1165 ECO yields the existing CROSS-CHECK sentence and remains Tier1 if all other guards pass. Assert no advisory-only `missing_modifier`/base flag/verified variant; generic extra designations use the same template, no ECO-specific conditional. Counts such as 4-Way and disabled WiFi/IOT/Smart prose produce no such advisory. Preserve existing true fallback notices.
12. Warning selection/output: a selected warned exact offer carries the notice into both metadata and reason exactly once, and existing marker/highlight functions recognize it. A non-selected warned offer cannot contaminate a clean selected offer; verify both arrival orders, platforms, independently triggered T3 notices, and duplicate offer handling. Do not create or select a fallback pool merely to obtain yellow text.

Use parametrized/metamorphic tests without requiring a new property-testing dependency: harmless prose addition/reordering preserves proved identity; genuine conflicting evidence never strengthens acceptance; a real suffix survives normalization; equivalent raw payloads produce equal decisions; adding an unrelated model cannot be used as positive identity evidence. The known general multi-model flaw remains a separately tracked expected gap, not a claimed passing property of this slice.

### Validation commands after authorized implementation

Run focused pytest modules for matching, model identity, polarity, series, own stores and offer-processing contracts, then the complete offline suite. Run `ruff check .` and `mypy pricing_engine --strict`. Preserve fixed-vendor commission tests. Document repository-wide format/mypy failures separately rather than claiming narrowed checks satisfy every CI gate.

Use a dependency-complete isolated runtime and mocks/network blocking. The audit warns that bare pipeline tests in a credentialed checkout can initialize database state or default checkpoints. No dependency installation or broad test run occurred in this investigation. After each successful change-dependent check, do not repeat it without a new reason.

### Checks actually performed in this investigation

- 28 explicit current-behavior matching controls: **28 passed** (aliases, short/numeric boundaries, E-Chrome, T3/T4/polarity/omission/prose, inverter conflict/omission, KG, colour, ES/ES8, door/finish/load/tub/automation/defrost, mount/mode, base/sibling/cross-series, ADS+ polarity).
- 100 curated catalog self-matches: **100 Tier1**.
- 500 controlled append probes: outcomes tabulated in Part D.
- Shared finalizer precedence assertions: **3 passed**, exact then base then sibling.
- Raw-payload Mega Flex price-pool replay and ECO/Glacier rejection/empty-pool replay reproduced.
- Additional pure probes reproduced H3/H4/H5 and preserved approved alias/prefix behavior. These are diagnostics against unchanged code, not tests of an implemented correction.

## Part J — Independent Adversarial Challenge

| Challenge | Review result and correction to recommendation |
|---|---|
| Just remove SMART->IOT and caps.add | **Rejected as incomplete.** Count anchors are fabricated earlier; a word can migrate into series. Canonical role classification must precede both. |
| Delete all short-code handling | **Rejected.** Loses ES/ES8, EDS, real suffixes, optional T3 and approved fallback behavior. Keep bound and catalog-declared model components. |
| Ignore all facets after equal anchor | **Rejected.** Capacity, colour, T3, defrost, mounting and explicit retained contradictions remain vetoes. |
| An arbitrary cap can qualify a numeric SKU | **Actionable source coupling.** Restrict qualification to bound/code provenance; no invented confidence bonus from an extra word. |
| Global glued-stem scanner necessarily makes 1400RPM a capability | **Not confirmed by execution.** Both 1400RPM and 1400 RPM remained non-capability and Tier1 because RPM is already excluded by NON_SKU_TOKENS. Do not count this reviewer suspicion as a reproduced defect. Still test measured suffixes generally. |
| Disable connectivity but accidentally erase literal manufacturer suffix | **Actionable risk.** Protect model spans before prose cleaning; compare literal components regardless of their word spelling. |
| Treat every missing feature as false | **Rejected.** Omission is unknown; preserve existing authorized fallback and omitted-Inverter behavior. |
| Generic text structure can prove every loose word's manufacturer meaning | **Rejected assumption.** State the information limit. No entropy, capitalization or length rule can resolve every unknown real-world edition. |
| “Catalog-declared” silently means manufacturer-verified, or generated joining creates an attached SKU suffix | **Rejected assumption.** Declare the source-trust policy and reverse-ECO Tier2 outcome explicitly; preserve original versus synthesized attachment. Existing separate catalog codes are compatibility constraints, not newly verified manufacturer facts. |
| H3 implicitly promises to fix every scalar-facet contradiction | **Scope narrowed.** This slice covers retained capability sets and inverter polarity only. Other scalar internal ambiguity remains documented rather than authorizing a broad rewrite. |
| Precise counts lack reproducible inputs | **Corrected.** Saved the probe, complete 100-row selection/hash, detailed current-source JSON and exact invocation alongside this report. |
| Simplify by merging exact/base pools | **Rejected.** Fix identity classification; keep stock-aware tier priority. |
| Reuse the yellow sentence by routing every extra designation through the current Tier2 branch | **Rejected.** The sentence/display are reusable; the branch's fallback decision is not. Keep advisory metadata independent from tier and real variant proof, and correct existing annotation propagation so reason-based exports show the selected advisory. |
| Add litres to scalar capacity and call all hardware safe | **Rejected.** Would mask taps/other dimensions; H4 requires a separate dimension/subject contract. |

The independent review was performed by a separate agent using the same model family, not an external manufacturer expert or a cross-model service. Its claims were reconciled, not treated as automatic sign-off. No independent approval of unimplemented production changes is claimed.

## Phase 2 Architecture Compatibility & Hardware Matching Integration

### Reference availability and original objectives

The separate requested Phase 2 Starting Plan is unavailable. The supplied master audit has no Parts 9–16, so a complete proposed architecture/implementation sequence cannot be extracted from it. The user explicitly authorized continuing and preparing that complete future plan later.

Three different uses of "Phase 2" must remain distinct:

1. **AGENTS section 8:** Supabase repricing history plus CLI queries, offline-resilient persistence. It contains no hardware-matching correction and is not a dependency for this fix.
2. **Older tasks/plan.md section 10, already implemented:** pre-normalization, polarity sets, Rules A–D; followed by AC slash/DC, three-tier selection, notices/output. Its header/checklist marks this completed. Reimplementing it would duplicate existing work.
3. **Master audit future dependencies:** PG-M01 explicitly names M01/M11 evidence contract before M12 hardware correction. PG-M04/08, M13 alias/fallback, M20 extraction and M21 retrieval are related references. Their complete missing milestone definitions cannot be invented.

The older plan's objectives were safe W/L binding, ERP slash isolation, scoped existing X behavior, dynamic spaced prefixes, polarity/ambiguity, AC subordinate codes, and per-marketplace exact/base/sibling selection. These are architectural context, not authorization to redo their implementation or restore obsolete financial policy.

### Compatibility and conflict ledger

| Proposed/historical decision | Current source | Master audit discovery | Resolution and approval |
|---|---|---|---|
| Polarity Rule A rejects internally contradictory candidate capabilities | Implemented, candidate side only | PG-M01 warns untyped prose is not truth | Keep for retained proven technical constraints; H3 extends symmetric ambiguity. Connectivity ambiguity intentionally disabled by current user policy. Implementation approval still required. |
| Rule B rejects opposing capability polarity | Implemented for enumerated scanner, not consistent inverter field | Master requires real technical contradictions remain protected | Preserve retained hardware contradictions; disable WiFi/IOT/Smart contradictions per explicit user choice. No broad contradiction bypass. |
| Rule C allows extra T3 specification | Current code restricts to eligible alphanumeric AC prose; attached upgraded SKU suffix still rejects | Audit says preserve real T3/core distinctions | Keep current tested narrow behavior. Do not broaden old specification pseudocode into all extra hardware. |
| Rule D demotes omitted target capabilities | Implemented for general inferred set | PG-M01 shows false caps create false demotion | Run only on retained technical/declared variant evidence. No missing connectivity fallback. |
| Generic short adjacent code -> capability | Implemented with several exemptions | ECO/WAY become false identity | Replace provenance rule once at extraction; do not add a second downstream referee or token blacklist. Approval changes ET-only extra-hardware expectation. |
| SMART belongs to capability scanner; non-display SMART maps IOT | Implemented; TV OS names add SMART | PG-M01 confirms overreach | Current user now requests a broader change than audit's "explicit connectivity remains meaningful": all three prose criteria inactive, including TV. This conflict is explicitly resolved by latest user instruction. |
| Safe unit/prefix/ERP normalization | Working regressions exist | Audit identifies evidence-role gaps, not permission for wholesale normalization replacement | Reuse and preserve; change only classification dependencies needed by PG-M01. |
| AC slash/DC capture and same-base editions | Implemented and tested | Audit regards existing architecture as useful | Preserve. Do not rewrite AC matching/decomposition or regain old orphan GE bug. |
| Per-source exact > base > sibling | Centralized in offer_processing, not old scraper-local owner described in plan | D03a shows a wrong input classification, not wrong pool precedence | Leave finalizer algorithm unchanged; correct which tier the listing belongs to. |
| Existing yellow CROSS-CHECK NOTICE and presentation | Sentence already exists in matcher; exact dual-colour path also supports it; selected-offer notice metadata reaches terminal, but generic exact metadata need not be added to the exported reason | No new warning architecture is needed | Reuse/correct current sentence and annotation owners. Extra eligible designation is advisory, not an automatic Tier2 decision. Use existing summary/CSV/XLSX markers and highlighting; no duplicate formatter/renderer. |
| Alias and variant safety | DW-MD, E-Chrome, generation/colour guards active | Audit says preserve fixes; full alias governance later | Keep current behavior; no new alias registry or Glamour+ fallback in this scope. |
| Fixed-vendor commissions | V already applies configured vendor rates | PG-P01 says this is fixed on V | Preserve V and replacement AGENTS instructions. Do not import obsolete 10%/8% switching from older plans/docs. |
| Full typed evidence architecture suggested by audit | Existing dataclasses lack provenance; full later architecture section missing | PG-M01 needs fact roles; audit explicitly discourages rewrite | Introduce only minimum internal provenance needed by current matcher, compatible with later evidence contracts. No universal hardware ontology. |
| H4 quantities and H5 sufficiency | Scalar omissions/path divergence persist | PG-M04 and PG-M08 track them separately | H5 small predicate slice proposed separately; H4 dimension/subject redesign deferred. No claim PG-M01 alone fixes all technical evidence. |

### Recommended sequencing and dependencies

**Implement the focused correction before broader Phase 2 work, as the hardware milestone itself, after a small local evidence-contract step.** In audit terminology: preserve V baseline -> define the necessary M01/M11 interpretation contract -> implement/review M12 correction -> then plan the remaining roadmap. Do not wait for history storage, scraper rebuilds, global ontology, M13 qualifier fallback, or financial-policy refactoring.

H3 and H5 are separately reviewable future safety slices and are not bundled into the immediate correction. Passing the immediate regression suite must not be described as fixing them. H4 remains a separately approved capacity milestone. Later M13 fallback work must consume the corrected interpretation rather than replicate it. Later M20 source evidence should enrich the same roles rather than introduce a second hardware parser. The existing notice flow is reused during M12 rather than deferred to or duplicated by a separate presentation milestone.

This is compatible with the known dependency references, **not confirmation of an unavailable complete Phase 2 plan**. The later roadmap must cite and supersede this report where needed; do not overwrite approved historical plans or repeat the completed consolidation.

## Part K — User Decisions and Approval Gate

### Decisions already resolved

- WiFi/IOT/Smart prose matching, including TV Smart/Non-Smart and contradictory connectivity wording, is disabled in the proposed behavior.
- Generic structural evidence replaces word-specific exceptions; no new brand/category/prefix blacklist.
- Fixed vendor commission, financial policies, source adapters, store ownership, export schemas, genuine variant/colour guards and tier priority are preserved.
- Complete separate Phase 2 plan review is deferred by explicit user instruction; external cross-model review declined.
- Extra unverified model-adjacent designations such as ECO use the existing yellow CROSS-CHECK sentence; advisory alone does not change an eligible exact tier. No duplicate matching or warning logic is permitted.
- H3/H5 changes require later separate authorization. Current T3, inverter and active 1b behavior is preserved in this immediate scope.

### Approval requested

Approve only the **final immediate PG-M01 correction at the start of this report and in H/I**, including reuse/correction of the existing yellow advisory flow. H3 polarity/inverter expansion, H5 capacity sufficiency, H4 quantity redesign, new cooking/display technology policies, general numeric/multi-model/legacy repairs, PLUS fallback, and the broader Phase 2 roadmap remain outside that implementation authorization.

Approval also acknowledges these explicit behavior changes and limits: old WiFi/IOT/Smart assertions are superseded; an unverified candidate-only loose token cannot constitute a hardware veto; eligible extra model-adjacent designations instead use the existing yellow advisory without a tier change. Existing tests that assert arbitrary extra ET is hardware need an evidence-based expectation rather than preservation of the bug. Originally attached manufacturer components and existing catalog-declared separate-code contracts remain protected. Catalog-side ECO omission remains Tier2 under the stated source-trust policy; this package does not claim to infer which ambiguous catalog words the manufacturer intended as identity.

**Stop point:** This document records a recommended correction, not an implementation. No production code, configuration, catalogs, tests, existing plans, commission logic, commit, merge, push, or deployment was changed by this investigation. New files are limited to this report and its documentation-owned offline probe/JSON evidence.

### Roman Urdu / simple English answers

1. **Abhi kya check hota hai?** Model ke ilawa capacity, colour, edition, T3, inverter, finish, door/load/tub, mode aur inferred short-word capabilities check hoti hain. Kuch checks model pass hone ke baad bhi reject kar dete hain.
2. **Categories mein farq?** AC mein tonnage/mounting/DC/T3, TV mein inches/Smart, washer mein KG/load/tub, fridge mein CFT/defrost/finish; bohat si doosri categories par generic rules lagte hain. Coverage har category mein complete nahi.
3. **Unnecessary rejection/demotion?** ECO/WAY ko hardware banana, count ko model banana, Smart ko IOT banana, aur component screen size ko main capacity banana reproduce hua.
4. **Important checks?** Actual model/suffix/revision, genuine edition, colour, capacity, T3/T4 aur retained explicit technical contradictions. WiFi/IOT/Smart wording aapki instruction par inactive hogi.
5. **Kitne root causes?** Paanch groups: token roles, connectivity inference/policy, polarity gaps, quantity representation, aur identity-evidence minimum. Teen reported examples ko teen unrelated patches nahi banaya.
6. **Confirmed vs suspected?** Reported failures aur H3/H4/H5 local probes se confirmed hain. Manufacturer ki har marketing technology ka meaning verify nahi hua; RPM suspicion execute karke confirm nahi hui.
7. **Minimum changes?** Shared matcher interpretation aur tests; model-bound evidence ko loose prose se alag karna, connectivity gates disable, existing yellow sentence/notice flow reuse aur reason propagation sahi karna, policy version bump. H3/H5 later separate authorization; broad architecture rewrite nahi.
8. **Risk?** Genuine spaced suffix ko prose samajhna ya prose ko required series banana. Is liye declared/bound variants, aliases aur complete catalog differential regressions zaroori hain. Unknown loose words ka real-world meaning text se hamesha prove nahi hota.
9. **Tests?** Original three cases, 100-row differential/metamorphic cases, all real category groups, retained negative controls, both platform pool integration, stock/owned behavior, and full dependency-complete pytest/lint/type gates before completion.
10. **Recommendation?** Identity ko actual model evidence se decide karo; seller ke extra chhote lafz se hardware invent mat karo. ECO jaisi extra designation par existing yellow CROSS-CHECK NOTICE dikhao; sirf warning ki wajah se Tier2 mat banao. WiFi/IOT/Smart criteria disable karo, genuine model/variant/colour/core constraints preserve karo. Existing logic reuse/sahi karo, duplicate system nahi. Pehle focused plan ki approval, phir implementation.
