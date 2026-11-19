# Product identity engine — architecture and migration blueprint

**Design for owner review · 19 November 2026 · Python library first.** A repricer and an image application should be able to ask the same question about the same two products and receive the same identity evidence. Each application decides what it can do with that evidence. In particular, a sibling SKU that the repricer may use with a yellow warning can be the wrong product to illustrate.

**Recommended decision.** Build one offline product-identity package in this repository. Parse catalog and marketplace titles independently with the same extractor. Preserve component boundaries and competing interpretations. Compare whole components under explicit, directional compatibility rules. Use catalog and listing data to discover useful query spellings and distinguishing components. Grant an exact match only when the identity evidence supports it. For an underspecified title the correct result can be “which variant?” or “insufficient evidence.” This ability is essential for new product formats.

### How to use this plan

For implementation, start with R0 in §8. Use §§11–15 for file ownership and exit tests, §17 for working-tree regressions, and §18 for mixed seller pools and the handoff checklist. Sections 1–7 describe the design, §9 records policy and §16 governs release. Section 10 maps the owner's 35 original sections, including the historical Book1 tables and API captures.

| Find | Go to |
| --- | --- |
| Why the present design misses listings or accepts a different SKU | §§1–2 and §13 |
| Which file owns tokens, measurements, extraction, comparison and query generation | §§3–5 and §11 |
| How an unfamiliar title becomes a defensible match or an unresolved result | §§4–5 and §12 |
| What happens after the API returns candidates, including yellow warnings and variant choice | §§5–6 and §13 |
| What Argon builds first, the first failing test and how to roll back | §§8 and 14–16 |

## 1. Where the design starts

The owner's [master plan](PRICE_ENGINE_MASTER_ARCHITECTURE_PLAN.md) identifies the right four responsibilities: measurement interpretation, title extraction, query generation and matching. Its Book1 table, fallbacks, test cases and review in §§11, 21–27 and 34 are inputs to this design. Six changes make the split practical for a second application.

| Master-plan proposal | Refinement and reason |
| --- | --- |
| Split four responsibilities inside the pricing application | Put the pure owners in an importable sibling package. Use adapters for marketplace retrieval, pricing and old entry points. A second program can compare two offline titles without importing Rich, pandas, curl, a registry singleton or a repricing pipeline. |
| Select one primary core and peel color, chassis or regional trim by shape | Preserve the entire identifier and its component spans. Classify a split as an interpretation. An observed SKU ending in `S` can denote independent hardware. A long code and a retail suffix list such as `RT/UL/UR` cannot establish equivalence. |
| Accept on a shared core plus a confirming qualifier | Align each distinguishing obligation for that SKU branch. One agreement cannot excuse another contradictory qualifier, or a missing qualifier that distinguishes two known products. Missing and conflicting information get different outcomes. |
| Reduce a title to a primary capacity plus a range flag | Retain all measurement observations with dimension, subject, span and uncertainty. A washer's 8 kg load and its display size can coexist. The shipping adapter retains its existing projection. |
| Pre-extract a single set of slots in the offer loop | Prepare the **entire target**, including alternative model branches, slash-color choices and original text, once per context. Enforce equality between raw and prepared call paths, including warning text. |
| Restore Book1 rows 10, 20 and 98 and use catalog self-match as a release gate | Preserve the owner's verified edits. Keep older spellings as separately labeled regression inputs. Add seller-title pairs, nearest conflicting variants and unseen families. A catalog correction is evidence about that row only. |

### Current evidence and its limits

The inspected working tree is on `codex/smart-targeted-reruns` at `dd05a45`, with local edits. SHA-256 prefixes at inspection: master plan `56b473560eb3`, matcher `40397f1a1066`, capacity `be1729a07557`, Book1 `be13dd60e7e6`. The master plan describes an earlier matcher revision. Its marketplace examples are historical observations. The following probes used the current working source and local Book1. Matched pairs below were supplied directly to the referee.

| Observation | Actual outcome | Consequence for design |
| --- | --- | --- |
| All 100 current Book1 titles compared with themselves and declared brand, then passed to both query generators | 100 Tier 1 self-matches. Digi produced plans for 100 rows with 103 branches. Row 85 produced 48 distinct case-folded Alfa query strings across tiers. These are **generated**, not executed, queries. | Pin valid identities and branch coverage. Evaluate retrieval separately against known returned listing IDs. |
| Row 85, keep the whole Haier title and replace `/X-IK` by `/YB(IK)`, then by `/KB`, then omit it | All three accepted Tier 1. The unmodified title also accepted. Alfa generated `X-IK Conventional Cabinet 24`. | Highest-priority structural regression. A compound qualifier must survive extraction, broad query generation and final comparison. Omission follows the approved base policy; an explicit alternative conflicts. |
| Row 89, Midea Titan target vs seller text `18HRFN1-QC2W-IDU-INV-EZ1-TITAN` with matching brand, tonnage and inverter wording | Referee returned `MODEL_CONFLICT` on the differing single anchors. Bare seller text `Model 18Hrfn1` also conflicted. A different chassis and `QC6` correctly conflicted. Digi's three generated queries all retained the outdoor prefix. | Recover full evidence on each side and generate the observed discriminating core+qualifier projection. Validate the complete unit/package before making an indoor/outdoor designation an exact sellable match. |
| `AB123 ABC 32 in Black LED TV` vs 40 in, same synthetic brand | `FACET_CONFLICT`, 32INCH vs 40INCH. Case-only `QX 255 in/IN White 10 KG` kept QX-255 and 10KG on both sides. | Existing improvements to preserve. Earlier false positives are useful regressions, not current results for these pairs. |
| `2-3 Taps`, `2 - 3 Taps`, `2 / 3 Taps` through `find_capacity(text,"TAP")`; `Icon 2 Taps` vs `Icon 2 Ltr` through the referee | All three exact-capacity reads returned None. Cross-unit pair returned `MODEL_CONFLICT`. Current unit registry already includes litres. | Retain correct rejection while exposing *why* a range differs from an absent value. Avoid repeating the old plan's litre assumption. |
| `Dawlance Classic Series DW-MD 15 20 Ltr Solo Microwave Oven` vs `Dawlance MD 15 20 Ltr Solo Microwave Oven` | Tier 1, no modifier or notice. The current own-store test describes this as exact. The owner's mission requires the yellow omitted-prefix fallback. | Record a deliberate, narrowly specified **policy delta** for this path. Verify true full-model exact and matching prefix controls. Do not silently bless the current implementation or relax every prefix. |
| Current row 20 and row 98 | Row 20 extracted `Icon-2`, series `VCM Bottle`, no primary capacity. Row 98 extracted `WA80CK4240BW`, series `WA4000C`, 8KG. | Keep named models, family prose, series and measurements independent. Do not infer a target color, bottle volume or regional SKU that the owner removed. |

Reproduction entry points are `extract_product_slots`, `referee_match`, `generate_search_patterns`, `generate_digimall_plan` and `find_capacity`. The inspection included six focused pytest modules (402 passing, one Windows curl event-loop warning in the test summary). These checks establish current behavior. No fresh marketplace accuracy or future engine accuracy is inferred.

## 2. Production paths the new package has to serve

| Current owner and call path | Contract to carry forward |
| --- | --- |
| `index.run_pipeline` (imported) → `read_catalog_csv` / `parse_product_input` or prepared products → worker → `pipeline.process_item_async` → `extract_search_query_and_model`, `generate_search_patterns`, `generate_digimall_plan` | Catalog supplies brand and original title. Preserve optional catalog declarations and ordered model/color alternatives. The standalone ingest_catalog API also needs coverage. Pricing, shipping and floor calculation stay in the host. Exercise range mode separately. |
| `matcher.extract_product_slots` → `_evaluate_anchor_compatibility`, `_has_variant_tag_collision`, `_referee_match` → `referee_match` | Anchor, series, suffix, polarity, optional tags, explicit hardware and evidence of omission affect the verdict. Today raw strings and already-prepared slots traverse different branches. |
| `is_strict_model_match(scraped_title, target_model, brand)`, `_keyword_match`, forward/reverse tonnage helpers | Compatibility entry point for existing callers and tests. The main offer parser calls the structured referee. Keep the legacy argument order and Boolean semantics during migration. Independently characterize model-less, keyword, tonnage and T3 behavior. Participation in a compatibility API alone cannot authorize pricing a listing. |
| Ordinary referee for a product with no conventional anchor | Named series, evidence of family, physical and technical compatibility and brand can still identify a product under the existing path. A number from a count is insufficient to create an SKU. Characterize accepted, rejected and ambiguous cases independently of dedicated fallback. |
| `series_fallback.build_series_search` → `referee_series_match` → `referee_series_candidate` | Dedicated last resort requires an explicitly named catalog series, usable capacity and existing eligibility checks. After ordinary matching fails, the dedicated referee requires the catalog brand explicitly at the start of the listing title, no candidate SKU anchor, and agreement on whole series, family, capacity and physical guards. Accepted series fallback carries tier 2, series basis and warning. Current bounded builder's word/digit eligibility is distinct from ordinary Digi query generation. Any widening needs evidence. |
| `scraper.scrape_alfamall` → `_execute_waterfall`; `digi_discovery.discover_digimall` → `_fetch_query` → `DigiDiscoveryContext` | Alfa executes its tiered pattern list. The two-in-stock exact shortcut applies when non-exhaustive. Digi uses per-branch model-first plans, configured budget 3, page size 100 and maximum 3 pages; a string or legacy tier dictionary has different execution semantics. Preserve diagnostics, cancellation and run-scoped sharing. |
| `offer_processing.parse_offers_with_tiers` → `finalize_offers` → `pipeline.process_item_async` / `range_pipeline.process_range_item_async` → evaluator/exporter | A pair verdict, an active pool and a pricing reference are three distinct decisions. Stock, own/official vendor separation, floor-aware winner, selected-offer warnings, coverage, TTY choice and Excel highlighting are host responsibilities. |

Source anchors for implementers: current `matcher.py:1811,2585,2676,3536,3713,4432,4545,5149,6634,6645,6685`, `offer_processing.py:295,545`, `series_fallback.py:18,34,47`, `pipeline.py:1528,1613`, `digi_discovery.py:99,228`, `source_provenance.py:13`. Re-locate by symbol after edits.

## 3. Package boundary and proposed files

```text
product_identity/              # independently importable and packageable
    __init__.py                # small public API and schema version
    types.py                   # immutable inputs, spans, alternatives, decisions
    tokenizer.py               # original offsets, character runs, separators and groups
    measurements.py            # quantities, units, ranges, dimension and source span
    extractor.py               # tokens + observations -> prepared branch identities
    profile.py                 # immutable approved vocabulary, aliases, scoped policy view
    matcher.py                 # component alignment, contradictions, tier and reason
    queries.py                 # ranked evidence projections with branch and source refs
pricing_engine/
    matcher.py, capacity.py    # old import/call contracts delegated to canonical owners
    registry.py, learner.py    # load approved knowledge / propose observations
    series_fallback.py         # last-resort eligibility and discovery coordination
    scraper.py                 # Alfa transport, pagination and execution of query tiers
    digi_discovery.py          # Digi branch scheduling and plan budgets
    digi_transport.py          # retrieval, page cache and request lifecycle
    offer_processing.py        # raw listings -> observations, pool resolution and notices
    pipeline.py, range_pipeline.py   # selection/skip, range, evaluation and presentation
    run_signature.py, source_provenance.py  # dependency accounting across packages
```

The second package name is a design choice. Ship it from the same repository first. Keep four semantic owners from the master plan. The small types, tokenizer and profile modules exist because all four need the same representation. Add a separate catalog-index module only when offline profiling is enabled in phase 6. Existing calculator, config, models, ingestion, evaluator, exporter and publication remain the owners of their existing application contracts.

```mermaid
flowchart LR
    T[Catalog title and declared fields] --> E[Shared extractor]
    E --> P[Prepared target and alternatives]
    P --> Q[Query projections]
    Q --> D[Alfa or Digi adapter]
    D --> R[Raw listing with source metadata]
    R --> E2[Same extractor]
    E2 --> C[Prepared candidate]
    P --> M[Role-aware comparison]
    C --> M
    M --> H[Host resolves offer pools and variant choices]
    H --> O[Pricing or image application]
```

Core dependency direction is `types ← tokenizer / measurements / profile ← extractor`. Both `matcher` and `queries` consume prepared identities. Neither calls the other. The host injects a frozen profile. The package has no network, filesystem synchronization, marketplace singleton, price math or interactive prompts on import or during comparison. Raw page retrieval can be reused for different targets; their verdicts must be independently computed.

## 4. What “extract once” means

A single canonical extractor prepares each distinct **input and context**, not one guessed SKU string. A target is prepared before generating its first query. A candidate is prepared from its own title and its own declared fields. Passing the target brand as a hint may be useful to the old API. It must never manufacture an observation that the listing itself declared that brand.

| Type | Minimum data and invariants |
| --- | --- |
| `ProductText` | Original title, source kind (catalog, merchant listing, other caller), separate declared brand/model/variant fields when actually supplied, provenance of each field. A target in the repricing profile requires a valid catalog brand. |
| `Span` / observation | Original field and half-open character offsets, literal text, normalized value, kind, basis (declared, observed or inferred), branch/group membership. Unicode and whitespace normalization retain a mapping back to original offsets. |
| `PreparedIdentity` | Raw reference, immutable alternatives, whole SKU/compound spans, ordered segments, scoped aliases, explicit series, family, guarded facets, modifiers, unknown material, optional declarations, preparation schema and profile digest. It can represent a complete model-less title. |
| Measurement observation | Exact Decimal or bounds/alternatives, dimension and unit, subject where supported (e.g. load or display), original span, certainty. Serialized amounts are decimal strings. Unknown subject stays unknown. Attachments inside protected model spans stay visible. |
| `Decision` | Directional disposition, tier or absent, basis, matched branch(es), matched/missing/extra/conflicting evidence references and structured notices. Insufficient evidence, invalid input and explicit conflict have distinct outcomes. Rendering uses the host's current warning strings. |
| `QueryCandidate` | Text, branch, source spans, transformation used and priority. Host records executed text, page, coverage, cache source and winning listing ID separately. A proposed or executed query proves nothing about the listing. |

### Extraction algorithm

1. **Tokenize without destroying evidence.** Scan Unicode letters, decimal runs, whitespace, punctuation, quote boundaries and bracket groups. Keep intact forms and offsets. Case folding and reversible presentation changes support lookup. Preserve significant `+`, suffix order, slash and leading zeroes. A regex for recognizing a decimal is appropriate here. A regex assigning “regional trim” from a device-shaped code belongs outside this grammar.
2. **Annotate before consuming.** Mark supplied brand/model fields, explicit model phrases, quantities, units, named series, features, color, polarity, seller and role metadata. Separate seller field is stronger evidence for a trailer than a color word appearing in prose. A clause such as `- ET - Black Color` can contain two different kinds of information. Where ownership is unknown, keep a neutral span; never delete it merely to make two offers agree.
3. **Construct candidate identifier spans.** Start with declared model fields, explicit designation clauses and connected alphanumeric runs. Keep the full compound and its ordered children. A separator can join a qualifier, denote a variant choice or divide quantities. Resolve from attachment, parallel complete alternatives, units and scoped catalog evidence. Preserve unresolved alternatives explicitly. Do not create every possible substring, reorder characters inside a code, or join words across a seller clause.
4. **Assign roles using evidence.** A family prefix, invariant core, distinguishing qualifier, chassis, optional feature and seller designation are different roles. Admit a role from a declared field, an approved scoped mapping, or a supported structural interpretation. The longest or rarest token can nominate a search anchor. It cannot by itself identify the product. A new format can retain a whole opaque model as a first-class identifier and match it exactly.
5. **Resolve overlaps.** Each character span can support one independent identity obligation in a given interpretation. `2 Taps` cannot also count as proof of model `2`. Color written in a model and repeated in prose can corroborate interpretation, but cannot be counted twice as separate SKU confirmations. Preserve typed measurement facts for different dimensions. Contradictory claims within a single interpretation produce ambiguity with both spans attached.
6. **Represent alternatives compactly.** Keep branches tied to the original catalog or listing option. A qualifier in one branch cannot be used to fill a gap in another. Parallel colors can describe a genuine choice. A single price on a multi-variant listing proves variant-specific availability only to the extent allowed by the existing dual-color policy. On a resource bound, return partial/ambiguous preparation with the reason. Silent truncation must never produce an exact decision.
7. **Keep preparation independent of the opponent.** Whether `19HFCS` has an observed terminal `S` is an extraction fact. Whether that `S` can stand for silver in this pairing is a comparison question. This is what permits safe reuse of a prepared listing across many products and tenants with the same approved context.

For each quantity retain its original span, amount or interval, unit, subject (what is being measured), branch and basis (stated or inferred). Bind the whole unit phrase, including a supported multiword unit. A unit-bound number cannot subsequently supply an independent SKU or an inferred capacity. Keep numeric runs inside an explicit identifier intact. Resolve quantity ownership from its clause and enclosing identifier or option; where ownership remains ambiguous, preserve both readings for comparison. The single primary capacity used by a legacy caller is a projection of this record, never the complete input to comparison.

### How the system learns useful patterns from data

Begin with an **optional read-only catalog profile**, compiled per tenant and version. Index declared identifiers, observed spellings, component occurrences and which components distinguish neighboring canonical catalog records. Deduplicate repeated copies of a listing before counting support. Attach source IDs, scope and evidence type to each observation. Existing `InMemoryRegistry` supplies approved category/brand-qualified synonyms and capacity data to the host adapter. The core receives an immutable snapshot. A blank registry still supports structural matching.

For example, if two catalog SKUs share `18HRFN1` and differ on `QC2` / `QC6`, the second component is informative. Generate a high-specificity search such as `18HRFN1-QC2` from observed contiguous components. A seller title with the shared core alone remains eligible only under the established omission rule. If the catalog has only one of the two SKUs, absence of a second row does not turn the short title into an exact identity. A different seller's repetition, a cheap price, a product photograph or a previous matcher acceptance cannot promote an unverified spelling to a manufacturer alias.

Use catalog frequency to rank retrieval projections, with lexicographic priorities and stable tie-breaks. Keep the current exact-first order as the baseline, then prefer a supported discriminating qualifier, then a broad approved projection. Break equal ranks by source order and normalized text. Learn proposed transformations from independently verified pairs or a shared authoritative identifier. Retain counterexamples, review scope (tenant, brand, family and component role), direction, effective version and revocation. Never compute a transitive closure of fallbacks. New evidence can revoke an alias or reduce certainty. Freeze the profile for a run; review changes offline on held-out families before promotion. No product-specific executable exception is required.

### Cold-start example and catalog indexing

Suppose an unfamiliar brand declares model `VX7-P04`. A seller lists `VX7 P04`, another lists `VX7 P40`, and a third lists only `VX7`. The tokenizer preserves the ordered letter/digit runs, including the leading zero in P04. A verified separator-only spelling can align the first pair. P40 has a different literal sequence. The short title carries an unresolved omission unless the applicable profile already permits that role to be omitted. This works with no observations about the brand. If the catalog also declares a distinct `VX7P04` and a separable variant with the same compact spelling, record the spelling collision and require further evidence.

Implementation detail for the offline index: map an observed whole code or ordered component sequence to a **set** of catalog records with source and scope. For each candidate search projection, count distinct catalog identities it selects within the applicable scope. Prefer the most discriminating attested sequence that fits the adapter's remaining budget. Keep exact and branch reservations first. Several copies of the same seller title contribute one observation. If a record lacks a verified canonical identifier, use a record-local reference for retrieval statistics only. Keep ambiguous records separate. A catalog edit can change projection order for another row, so the profile/index digest must participate in targeted reuse wherever the index influences the processing result.

Existing registry calls also need a differential test here. In the current `registry.get_tonnage`, a missing scoped mapping can fall through to a named brand or the first matching code in another brand. Exercise an unknown brand and two brands giving the same numeric code different meanings, in both insertion orders. Use only an applicable scoped mapping or an explicitly approved universal one as identity evidence. Record any deliberate change to legacy tonnage or shipping compatibility separately.

## 5. Comparison algorithm and decision table

**Separate identity proof from corroboration.** Each exact decision must name the source spans that establish identity under its matching mode, any qualifier needed to distinguish a neighboring variant, and the observations that merely corroborate the result. Which role a span plays depends on the target and mode. An intact declared SKU can establish identity. A shared core can establish a family while its qualifier distinguishes a variant. Brand, capacity and color may corroborate a model and can veto it on contradiction. In an approved anchorless mode a particular combination of attributes can be required positive evidence. Repeating a fact adds no independent evidence.

**Paired acceptance test (R4).** Compare the same target with three same-brand listings: verified core and qualifier with little prose; shared core with the decisive qualifier omitted and many agreeing descriptions; shared core with an explicitly opposing qualifier and the same descriptions. Where other required guards are satisfied, expect exact for the first, only an authorized fallback or insufficient evidence for the second, and conflict for the third. Duplicate or reorder the corroborating prose and assert unchanged verdicts. Return the decisive evidence separately from the corroborating spans in all three explanations.

Compare **one coherent pair of alternatives** at a time. Use a map of normalized whole components and their roles to enumerate legal alignments. First attempt whole, scoped model equality. Then try separator-preserving presentation variants, then authorized role-specific aliases/omissions. Independent components may change order when their roles can be aligned. Inside a compound such as `X-IK`, order and grouping remain constraints. Matching one child `IK` in `YB(IK)` provides no agreement between the two compounds.

For each alignment record a relation for every applicable obligation: equal, verified alias, missing in candidate, additional in candidate, contradictory, or unresolved. Brand source precedence is explicit. An explicit leading target brand in the listing title can survive a bad marketplace tag under today's tested contract. A brand-neutral title with explicit foreign metadata cannot be accepted from a shared SKU alone. Reuse the same resolved brand facts for ordinary and dedicated series checks.

A hard contradiction eliminates the alignment. Cover full model core, mutually exclusive compounds, brand, family, color, protected dimensions, physical configuration, inverter polarity and guarded hardware. A recognized sibling *role* is evaluated by its existing sibling rule after shared guards; arbitrary differing suffixes do not qualify. A feature word such as “Smart” in prose may be irrelevant while the same letters attached inside a manufacturer's model are literal evidence. Unknown seller text does not become either a veto or a positive identity fact merely by capitalization.

For repeated or reordered components, construct legal links only between compatible role/value pairs in the same branch. Match complete identical compounds first; where more than one assignment remains, use one-to-one alignment and retain competing assignments that would change the verdict. Reordering whole independent components is legal; splicing a qualifier out of a different option or permuting digits is not. An opaque, terminal identifier difference carries more uncertainty than an explicit equivalent spelling. If a required field cannot be aligned or waived by a named approved policy, the engine cannot emit exact. Store the policy identifier with each waived obligation so an external consumer can explain the difference between exact, base and sibling.

Classify remaining alignments by the strongest **justified** relation. A competing parse assigning the same characters incompatible identities cannot be discarded because the more convenient parse matches. If unambiguous branches independently identify the same variant, merge their witnesses. If distinct viable variants explain the listing and the catalog has not selected one, expose the choices. Require a positive identity witness for every exact result. Price, arrival order and query tier play no part.

| Outcome | Evidence and precedence | Consumer behavior |
| --- | --- | --- |
| Exact, tier 1 | Complete verified identifier or approved complete role alignment, with enough series information for shared numeric stems. All applicable hard guards pass. | Enters exact pool. Existing market-only loose designation can retain exact with a cross-check notice where policy allows. |
| Base, tier 2, target omission | Core agrees, relevant qualifier is absent and existing policy explicitly permits this kind of omission. Examples include an approved omitted edition or suffix. | Retain omitted field and direction; yellow fallback on the selected reference. Separate the owner's intended DW-MD omission from literal full-model equality. |
| Base, tier 2, market addition | Underlying identity supported, and the additional market feature qualifies for the existing compatibility path. | Keep market source, observed variant and existing warning. A contradictory explicit sub-code never enters this pool. |
| Sibling, tier 3 | Recognized sibling editions share the verified base under the current sibling rule, with surviving brand, color, physical and capability guards. | Lower priority than available exact/base. Existing adapter emits `is_match=False`, `is_base_match=False`, `match_tier=3`, `modifier_source="market"` and sibling notice. |
| Ordinary anchorless / keyword | Apply the specific existing positive series/keyword, brand, category and physical evidence contract for the entry point. Distinct SKU evidence or insufficient identity can block acceptance. | Report the actual mode used. Keep the legacy Boolean interface for callers. Do not turn a keyword result into a production exact offer by wiring the Boolean into scraping. |
| Dedicated series fallback | Last-resort query after eligible, healthy model-first discovery found no compatible in-stock model-basis offer, including own store. Require catalog-declared series, explicit leading listing brand, an anchorless candidate, positive family evidence and equal verified capacity. Preserve full-series equality and physical guards. | Map to tier 2 with `match_basis="series"`, original model unverified and explicit notice. It stays behind an active model-basis offer, including sibling; never infer a shared SKU from it. |
| Conflict, insufficient or ambiguous | Contradictory evidence, inadequate positive evidence or incompatible plausible interpretations respectively. | Return structured facts; explicitly incompatible records go out of the pool. Ambiguous identity/coverage can require review. A single poorly specified candidate does not automatically open a CLI choice. |

**Group-level contract.** The host evaluates every returned candidate against its target branch, deduplicates by the existing seller/listing and SKU rules, then chooses the highest eligible in-stock pool. Reuse the established sold-out and own/official store treatment. Do not merge two conflicting explicit prefixes via one unprefixed offer. Carry notices from the selected external reference only. Include a regression for ties, reversed listing order and sub-floor prices. Keep compatibility notice text and the yellow XLSX fill observable.

**Variant choice.** The existing repricing CLI builds `AmbiguousVariantConflict` when the applicable base pool has multiple detected variants. In a TTY it presents the observed choices and Skip; selection filters both marketplace results and updates the output product designation. Headless, skipped or unanswered choice produces `SKIPPED` with no final price. Preserve this trigger. Multiple equivalent sellers, an unchanged checkpoint, or a speculative parsing alternative should not prompt a user. For conflicting Alfa/Digi option sets, capture the existing Alfa-first behavior, test selected-option and no-corresponding-offer cases, and retain marketplace provenance. Any new cross-market choice policy needs its own decision. An API exposes typed choices for its client to render.

**Identity is directional when used for fallback.** Swapping the inputs should preserve a symmetric genuine SKU conflict. It can legitimately change the omitted/additional attribute, source of warning or eligibility for a directional fallback. Never use “A may be repriced against B” to build a global equivalence class.

## 6. Retrieval, coverage and an end-to-end example

### Approved collection rule for incomplete seller titles

When the catalog identifies a compound model, collect compatible seller listings with the same **complete core** even when other declared components are missing. Keep them visible alongside exact offers, with a warning on each incomplete listing identifying the missing components. Apply the existing brand, sellable-unit, physical and variant guards first. Core equality uses whole ordered components including terminal digits. A substring, shared series, or equal capacity cannot establish core equality.

For the catalog target `MSEZ1C-18HRFN1-QC2 TITAN`, assume compatible brand and product-family evidence in these acceptance cases:

| Seller evidence | Collection and display |
| --- | --- |
| Full target identity | Exact, with no omission warning. |
| `18HRFN1-QC2` | Include alongside exact. QC2 is confirmed. Identify chassis designation and series as unstated. |
| `MSEZ1C-18HRFN1` | Include alongside exact. Chassis and core are confirmed. Identify QC2 and series as unstated. |
| `18HRFN1 TITAN` | Include alongside exact. Show “core and series confirmed”; warn that QC2 and chassis are unstated. For otherwise equivalent incomplete listings this has stronger identity evidence than the core alone. |
| `18HRFN1 Go-Easy` or `18HRFN1-QC2 Go-Easy` | Reject for explicit series conflict with the catalog's TITAN series, even when the core and QC2 agree. Apply this to the product's stated series; incidental seller text cannot establish a conflicting series. Pair these negatives with the TITAN and omitted-series controls using the same brand and product family. |
| `18HRFN1` | Include alongside exact. Show “core confirmed”; warn that QC2, chassis and series are unstated. |
| `18HRFN2-QC2 TITAN` or `18HRFN1-QC6 TITAN` | Reject the first for a different core and the second for a different explicitly stated qualifier. Neither may enter the fallback pool. |

Report the literal chassis evidence. Interpret `EZ1` as an alias of `MSEZ1C` only with independently supported scoped equivalence. Preserve a confirmed chassis conflict as a veto. A missing qualifier does not establish a new selectable variant when the target already specifies QC2.

R4 paired control: add only the independently observed complete catalog series to a bare-core listing. The explanation must gain series corroboration and drop the missing-series warning while retaining the missing-QC2 and chassis warnings. Repeating the series words adds no further evidence. An explicit foreign qualifier still rejects. This qualitative distinction leaves price-reference selection to host policy; any numerical probability would require calibration against independently labeled offers.

R4/R7 acceptance: replay a single pool containing an in-stock exact, both qualified and bare-core incomplete offers, a cheaper wrong core and a cheaper wrong qualifier. Assert individually visible warnings for the incomplete offers, exclusion of both conflicts, and no inherited warning on the exact offer. Preserve existing exact-first pricing for this implementation, including when an incomplete offer is cheaper. The owner authorized collecting those sellers together. Changing their pricing precedence would require a separate policy decision. See §18 for the host replay.

Generate source-backed query projections in this order, subject to the current platform contract: full observed identifier, discriminating components together, attested presentation alternatives, then a broader supported base. A named product without an SKU takes its approved descriptive route. Preserve an exact query for each explicit target branch. A shortened retrieval query never edits the prepared target. The host keeps marketplace-specific request scheduling, budget and stop conditions. Deduplicate formatting variants only when the adapter's query semantics permit it.

**Book1 row 85.** Prepare `HPU-24CE03/X-IK` with its intact compound qualifier. Generate the full query first, then supported projections such as `24CE03/X-IK`, `24CE03` and the owner-approved seller spelling in §17.2 within the platform budget. Compare each original listing against the full target. The result `24CE03/X-IK` can enter exact with all guards satisfied. A confirmed core missing the qualifier can enter base with a yellow notice. Explicit `/YB(IK)` and `/KB` conflict. `24 X-IK` lacks the core. This target specifies its variant; sellers omitting the qualifier do not trigger a variant prompt.

**Book1 row 89.** Discover the full model and the corroborated `18HRFN1-QC2` projection. Prepare a listing with reordered components independently, link the core, chassis evidence and qualifier to source spans, then compare. Verified equivalence, compatible sellable unit and corroborated color can justify the intended exact result. A merely similar `EZ1` fragment, a letter-number OCR guess, or the same “Titan” branding cannot resolve unexplained identity material. An explicitly different `QC6` is a veto. A bare core belongs only to the authorized fallback relation. Record which candidate the API actually retrieved before attributing an error to the matcher.

Keep `generated queries → executed queries/pages → raw candidates → parsed candidates → decisions → eligible pool → selected reference` as a trace keyed to the target and listing. Coverage (complete, capped, unknown, incomplete, failed) travels independently of matches. A valid match on a partial page proves an observation; a partial page cannot establish market absence. Preserve actual Digi distinctions (including the current handling of capped/unknown in fallback scheduling) and Alfa exhaustive/non-exhaustive modes during comparison. Raw-page caches need page/cursor, request context and marketplace; classification caches additionally need target, role/mode, profile and implementation. Track the real cursor, not a Boolean “complete” surrogate. Test warm/cold runs on identical recorded pages.

## 7. A stable interface for other software

Proposed interface, shown as a contract sketch. These names do not exist in the current application.

```python
context = IdentityContext.from_snapshot(approved_snapshot)
target = prepare(ProductText.catalog(title=title, brand=brand), context)
queries = propose_queries(target, context)
listing = prepare(ProductText.listing(title=api_title, brand=api_brand), context)
decision = compare(target, listing, context)
```

`compare` is the ordinary entry point. The dedicated call is `compare_series(target, listing, context)`. The discovery adapter may invoke it only on an eligible series search after ordinary matching has failed for that listing. The series entry point independently validates pair-level eligibility and returns its own basis. Include this operation in the decision-cache key. The pair API alone cannot determine market coverage or authorize widening a search.

A Python consumer installs a versioned wheel. A caller with a raw pair can use a convenience wrapper that calls these same functions. External serialization uses a versioned JSON schema, stable enums, Unicode offsets with a documented indexing convention and decimal strings. Require schema/profile compatibility at the boundary. Distinguish malformed requests from valid ambiguous products. Keep compatibility wrappers for `find_capacity(text, unit)`, `generate_search_patterns`, `is_strict_model_match(scraped_title, target_model, brand)` and both referee entry points. Mapping tests assert existing signatures, boolean flags, tier, basis, warnings and sorted pool membership.

For an **image application**, ask for evidence for the exact depicted variant. Supply its asset ID and variant metadata through the host. The same comparison can return an exact result, a yellow commercial fallback, or a choice; the image application can limit asset use to an exact color/model and send the other outcomes for selection. Keep the asset-to-product association independently verified. A matching listing title alone cannot certify the contents of an image.

For **SaaS**, use this library in process first. If a non-Python client needs it, expose a thin authenticated batch comparison endpoint and query-projection endpoint using the same schema and conformance fixtures. Tenant identity comes from authenticated context; authorize profile access server-side. Enforce bounded batch, title and interpretation work, deterministic overload responses, tenant-isolated caches and sanitized evidence logs. Negotiate schema version separately from profile and engine semantics. A browser session, scraper deployment, tenant-specific model training or hosted service is not a prerequisite for the library migration.

## 8. Migration roadmap for Argon

Each slice starts with a failing behavior or compatibility test, adds one independently reviewable capability and leaves the active production path usable. Use the working tree at implementation time and pin its fingerprint first. Keep production active on one implementation during cutover. Shadow replay can run two versions on the same captured input without issuing a second marketplace request. Avoid permanent duplicate parsers.

| ID / dependency | Deliverable and first test | Completion gate and rollback |
| --- | --- | --- |
| R0 · baseline | Build a reviewed corpus from current Book1, original spellings as separate fixtures, selected raw Alfa/Digi responses, owner-verified pairs and surrounding nearest variants. Include title, declared fields, listing ID, source time, tier, notice, policy authority and uncertain labels. Snapshot normalized legacy outputs, queries and evaluated prices separately. | Reproduce rows 85/89, positive controls and DW-MD policy conflict. Capture cold/warm runs and current CI limitations. No catalog or production change to roll back. |
| R1 · R0 | Introduce package contracts and compatibility harness. First test isolated import with no network/DB/UI/pricing dependencies, raw/prepared branch parity and full public-signature inventory. Implement the small types/profile API. | Consumer fixture can round-trip schema and reproduce span references. Keep production on legacy entry points. |
| R2 · R1 | Add reversible tokenizer and canonical measurement owner. First test spaced/glued separators, Unicode quotation, decimal/range/quantity, explicit opposing sizes, bare “in”, SKU-protected digits, litres + tap count and washer + secondary display. Delegate old measurement API. | Demonstrate same positive/negative measurement contracts and unchanged shipping projection on all actual catalog rows. An ambiguous span cannot become an exact endpoint. Defer adapter switch if the differential is unexplained. |
| R3 · R2 | Build extractor for declared SKU, intact opaque codes, compounds, alternatives, branch-local color/polarity, seller clauses and observed role facts. Start with row 85 and foreign synthetic compound twins. Compare raw vs prepared for slash models, colors and uppercase/lowercase. | Every material component points back to source. Preserve unknown spans and both sides of a contradiction. Restore old target preparation adapter on rollback. |
| R4 · R3 | Implement model comparison then directional base and sibling classification from existing referee tests. Cover row 89, `QC2/QC6`, E-Chrome/Chrome, Chrome Pro/Chrome ordering, attached vs loose ECO, literal suffixes vs disabled Smart/WiFi prose, missing color vs opposite color. Encode owner-authorized DW-MD yellow behavior with an explicit directional regression. | Explain each changed verdict against labeled evidence. Whole-code/approved-alias exact, hard veto, yellow omission, extra market notice and sibling contract all survive adapter translation. Keep legacy outputs active while reviewing differences. |
| R5 · R3–4 | Port ordinary anchorless matching, legacy keyword/tonnage/T3 API and dedicated series pair evaluation as three separate tested activities. Exercise explicit foreign candidate model, missing family/capacity, own-only active model, sold-out-only model and unhealthy model discovery. | Capture which entry point can accept each fixture. Distinct basis survives dedup, fallback and warnings. Preserve current query eligibility on migration; a separate policy change must justify relaxing it. |
| R6 · R3–5 | Implement projection generator and optional catalog statistics. First test row 85’s query spans and row 89’s discriminating projection under the existing budgets. Include five-word descriptive titles, independent target branches and identities outside the profile. | Offline replay shows expected ID is reachable per marketplace; log losses and newly reachable wrong variants. Enabling statistics alone cannot upgrade a verdict. Disable ranking/profile amendment as a unit if retrieval regresses. |
| R8 · after R1; prerequisite for R7 | Extend `source_provenance`, `run_signature` and relevant row fingerprint/context to cover the new package and semantic data. Test same package version with changed file contents, changed scoped alias/profile, installed wheel vs checkout, changed UI-only text, mutable registry mid-run, concurrent tenants, and rollback. | Current scanner globs only immediate `pricing_engine/*.py`. Digest full qualified paths and semantic resources in a deterministic manifest, plus selected profile and policy. Verify at run start and before publication. Rollback uses compatible generations only; incompatible explicit targeted runs require existing full-run authorization. |
| R7 · requires R4–R6 and completed R8 | Wire both adapters and range through prepare-once/compare, keeping HTTP and pool ownership where they are. First test exact vs cheaper base, shared raw page across targets, warning provenance, reversed order, ambiguous TTY choice/skip/headless, and stock/own-store isolation. Cover price-less or incomplete evidence through output. | Assert actual selected listing, pool, tier, price reference, yellow reason, risk, row ordering, full CSV and XLSX. Record discovery defects independently of pair matching. Revert adapter routing and its processing version together. |
| R9 · R7–8 | Shadow replay, then split release by verified consumer path (library, Alfa, Digi, range). Package wheel and test from a clean environment outside the source tree. Exercise second application without `pricing_engine`. | Every approved differential accounted for, no unexpected price/commission/coverage/export shifts, release gates below pass. Roll back to the pinned engine/profile and valid snapshot. Preserve historical outputs and receipts. |
| R10 · after cutover | Move surviving callers to canonical owners, keep necessary facades, retire proven-unused duplicate regex/branches only after reference search, public contract tests and replay. External HTTP service is a separate deliverable if needed. | One executable owner per semantic decision. Fresh-process imports and downstream fixtures pass without circular dependencies. Every authorized commit receives separate adversarial review. |

**Implementation order.** R8 may start after R1. Complete its provenance and incompatible-reuse tests before R7 persistent integration begins. Until then, adapter experiments may run only as isolated, non-publishing replays. R9 cutover requires both R8 and R7.

**R0 baseline reconciliation.** The owner's master plan §4 reports 1,383 passing tests. The isolated run in §9 recorded 1,389 passes and 73 warnings. The six-test difference has no established cause. Before implementation edits, pin HEAD plus working source, tests, fixtures and configuration hashes, interpreter/dependency versions and the exact pytest command. In the same isolated payload save pytest collection node IDs, full-suite results, skips and warning summary. Use that run as the common baseline. Compare historical node lists if available; if unavailable, label the historical difference unresolved. The 438-test run in §17 is a focused subset.

## 9. Verification, performance and release decisions

| Layer | Measure or assertion |
| --- | --- |
| Extraction | Assert span, unit/subject, qualifier grouping, multiple observations, explicit alternatives and unknown state. Test idempotence of presentation normalization and raw/prepared equivalence across both matching directions where meaningful. |
| Identity precision | Label exact/base/sibling/series/incompatible/insufficient separately. Count **false exact** and **false commercially eligible** separately; one wrong color priced as base is still a production error. Exercise same-brand neighbors differing by one character, unseen brands/families, full compound vs overlapping child, prefix ambiguity and metadata precedence. |
| Retrieval recall | For each marketplace and budget, count independently verified listing IDs reached / known eligible IDs, with coverage status. Count losses from queries, missing pages, parsing, rejection and wrong pool separately. Never label absence from an incomplete response as a negative example. |
| Generalization | Freeze family-disjoint and seller/source-disjoint holdouts. Add a time-separated capture for new title formats. Group aliases, repeated listing IDs and syndicated copies before splitting. Track both precision and coverage among auto-decided pairs, unresolved rate, false negatives and per-family denominators. Self-match and random foreign-brand negatives alone are too easy. |
| Anti-hardcoding | Rename a synthetic brand, vary SKU length, rearrange *independent* components, move a true qualifier, insert seller noise, reverse meaningful suffix order and negate a facet. Assert the changed or invariant verdict explicitly. New vocabulary needs semantic owner, source, scope and counterexample. |
| End-to-end | Replay identical captured pages through both production adapters, all tiers and fallback. Check selected references, non-selected warning suppression, coverage, rate limits, retryable state, TTY variant handling, headless behavior and complete exports. Verify all 100 current Book1 records and every changed selection manually against listing evidence where available. |
| Cost and determinism | Profile preparation count, candidate comparisons, median/p95 runtime, maximum branches, memory, unique actual requests and cache hits per marketplace on the same hardware and frozen pages. Cache prepared targets once per distinct context, candidates by content and profile. Use explicit operational budgets derived from measurements. Exceeding a budget produces an explainable unresolved result. |
| Packaging and state | AST and fresh-process import boundary tests, installed-wheel smoke test, consumer JSON conformance, cross-tenant isolation, version/profile rotation, interrupted publication and recovery, unchanged-input rerun behavior and rollback compatibility. Distinguish raw-page, prepared-identity, decision and published-result caches. |

**Release gates.** Zero false eligible outcomes on the labeled critical negatives; zero unexplained changes in owner-approved controls, Book1 outputs or warning provenance; every intended retrieval gain must survive downstream pair and offer checks. Publish confusion counts, unresolved cases and class-specific precision/recall with sample sizes. Agree any numerical throughput/latency budget from the measured baseline before cutover. A passing sample establishes behavior on that sample; title text alone sometimes lacks the information needed to distinguish real variants.

**Commands for the implementation checkout.** Run the project's virtual environment, full pytest, focused matcher/capacity/offer/series/discovery/own-store/range/export/state tests, `ruff check .`, `ruff format --check .`, `mypy .`, and `git diff --check`. Compare against actual baseline on the same payload. Run fresh imports and wheel tests in an isolated environment. Use recorded pages for repeats; keep read-only live spot checks timestamped, bounded and separate from deterministic results. Keep real catalogs, outputs, checkpoints and remote registries outside test destinations.

**Historical baseline for this blueprint.** Full pytest on an isolated copy returned **1,389 passed, 73 warnings in 94.85 s**. Focused execution on the checkout returned **402 passed**. These results coexisted with row 85 false positives. Section 17.2 records a later, limited live API check and distinguishes marketplace observations from the owner's identity decision. R0 must pin fresh inputs, responses and baseline results for implementation.

### Why this design and when to revisit it

For this project, deterministic structured comparison is the first production choice because a one-character revision can change which offer sets the price and the owner needs an explainable yellow fallback. Simple token intersections lose role/boundary and conflict information. Learned pair classification is a viable benchmark challenger once labeled local pairs exist. If retrieval misses paraphrased no-model titles after the structured baseline, trial a learned ranker in shadow to propose candidates, measure incremental recall and cost, and send every proposed pair through the same decision policy. Product-matching research evaluates hard negatives and unseen entities explicitly; this motivates the holdouts here, without transferring published accuracy numbers to AlfaMall or DigiMall. [WDC Products benchmark and data](https://webdatacommons.org/largescaleproductcorpus/wdc-products/) · [Ditto reference implementation and candidate-pair workflow](https://github.com/megagonlabs/ditto)

### Decisions that must stay visible

- The owner's verified catalog edits stand. Older full spellings are fixtures for testing historical pairs; any regional equivalence still requires independent evidence of the same sellable product. Keep a verified row-specific match distinct from a general rule about all codes ending in those letters.
- The owner specifies a yellow DW-MD omission fallback, while the current code and test expect exact for the reproduced pair. Mark the approved delta in the compatibility matrix. Do not change other valid prefix equivalences by analogy.
- Keep E-Chrome distinct, respect direction and product family for Chrome/Chrome Pro, preserve literal edition suffixes and current optional-hardware rules. Separate indoor-only, outdoor-only, kit and full appliance listings if evidence identifies different sellable units. If historical target-tier labels rely on unverified bundle or trim identity, retain the example for adjudication before promoting it to exact.
- A reviewer checked the sibling adapter fields, raw vs prepared variants, marketplace brand precedence, scoped registry and package fingerprints against current code. Those checks are reflected above. A separate final-artifact adversarial review remains required before any implementation commit.

### Handoff to the implementation engineer

After owner approval, start at R0 on the actual working tree. Read this blueprint, the master plan and the current handbook. Preserve all user edits. Pin the current source and policy, establish a reviewed corpus, and publish the raw/prepared and old/new comparison matrix. Implement one slice at a time with its red test, green test and counterexamples. Keep raw marketplace evidence and query provenance separate from commercial eligibility. Run the existing application through its real entry points. When a source or fixture conflicts with an owner decision, record the exact divergence and resolve it before cutover. Ship only with an independently reviewed diff, measured verification and a rehearsed rollback.

## 10. Cross-reference to the owner's master plan

The two files serve different readers. The [owner's 35-section plan](PRICE_ENGINE_MASTER_ARCHITECTURE_PLAN.md) records the investigation and original migration proposal. This document specifies the portable replacement, its application boundaries and how to prove each cutover. The following cross-reference identifies the disposition of every original section.

| Original sections | Treatment in this design |
| --- | --- |
| 1 Scope · 2 Baseline · 3 Skills · 4 Evidence | Carry forward the scope and historical evidence. §1 records the inspected working hashes. R0 recaptures the baseline before changing code. Historical measurements and review activity retain their original attribution. |
| 5 Runtime flows · 6 Module matrix · 7 Imports | §§2–3 and 11 trace both production pipelines, the separate ingestion API, the legacy matcher, the new dependency boundary and its compatibility adapters. |
| 8 Decision hierarchy · 9 Discovery | §§5–6 and 13 preserve distinctions between retrieval tiers, pair eligibility, final offer pool and the dedicated series pass. Each uses different evidence. |
| 10 Defects · 11 Catalog inventory · 12 Live evidence · 13 Prior reviews | §§1 and 13 retain the real cases and distinguish reproduced behavior from intended labels. R0 uses the original catalog inventory and historical response examples; §15 describes the fresh evidence required at release. |
| 14 Goals · 15 Package tree · 16 APIs · 17 Dependency direction | §§3, 7, 11–12 put the four semantic responsibilities into a reusable library. Keep old call shapes via explicit host adapters. |
| 18 Extraction · 19 Capacity · 20 Queries · 21 Comparison | §§4–6 and 12 specify the data flow, evidence role, bounded interpretation, query ranking, alignment and abstention. A reusable catalog index is optional and its version participates in reuse. |
| 22 Ambiguity · 23 Fallbacks · 24 Warnings · 25 Compatibility · 26 DRY | §§5–7 and 11–14 preserve direction and provenance across extraction, comparison, presentation, import aliases and stored state. |
| 27 Tests · 28 Performance · 29 Operational safety | §§9, 13, 15–16 define negative controls, paired replay, metrics, resource limits, tenant isolation and release evidence. |
| 30 Migration · 31 Gates · 32 Rollback | §§8 and 14–16 assign dependency order, implementation surfaces, test files, stop conditions and recovery for each slice. |
| 33 Decisions · 34 Adversarial findings · 35 Recommendation | §9 resolves the catalog question and records policy differences. §13 incorporates AR-1 through AR-7. §16 distinguishes design approval, implementation evidence and release approval. |

## 11. File-level implementation specification

The paths under `product_identity/` are proposed. Current repository paths below name the code Argon should trace. Move behavior only after it has a characterization test. These assignments keep a change in unit spelling, external API layout or commercial fallback from requiring edits to several parsers.

### Library files

| Proposed path | Input → output and owner | Evidence of completion |
| --- | --- | --- |
| `product_identity/__init__.py` | Export prepare, compare, compare_series, propose_queries and their public value types. Package import is side-effect free. | Fresh process can import the installed wheel with pricing application, DB, HTTP and UI dependencies absent. |
| `product_identity/types.py` | Define ProductText, span/group references, measurement observation, PreparedIdentity, QueryCandidate, Decision, structured notice and version fields. Keep old mutable ProductSlots outside the portable schema. | Round-trip preserves Unicode spans, zero-padded codes, ordered alternatives, source role, decimal values, ambiguous and missing states. |
| `product_identity/tokenizer.py` | Map original text to runs, nesting, separators and offsets. Supply presentation-normalized lookup keys alongside original slots. Leave semantic interpretation to the extractor. | Reconstruct original slices for a hyphen, slash, quote, bracket, non-ASCII character, plus sign and digit run. Harmless formatting and meaningful changes have separate assertions. |
| `product_identity/measurements.py` | Own unit aliases, exact decimals and range observation; reuse current capacity definitions. Annotate span, unit, dimension and subject if available. | The thin host `find_capacity(text, unit)` still returns its established type. Tests also observe the difference between a missing measure, a range and an exact value. |
| `product_identity/profile.py` | Accept immutable approved meanings and directional eligibility declarations with scope, provenance and version. Return applicable knowledge, explicit conflict or unknown. | Two tenants in one process may give the same token different meanings. Reordering equivalent input data leaves its digest and determinate lookups stable. |
| `product_identity/extractor.py` | Prepare the original input, compatible lookups, branch membership, whole identifiers, qualifiers, measurements, series, guarded features and unassigned spans. It must be callable without a counterpart. | The same seller title with its own metadata produces the same prepared value regardless of which targets are later compared. Raw/prepared branch parity is tested separately. |
| `product_identity/matcher.py` | Compare prepared branch evidence; own guarded contradictions, requirement alignment, named fallback eligibility and notices with references. Expose ordinary and dedicated series comparison. | Each exact, base, sibling, series, conflict and unresolved result has a test for both disposition and decisive evidence. No query generation or offer-price dependency. |
| `product_identity/queries.py` | Generate source-backed query projections and stable order from the prepared target. Mark branch and projection reason. | Reproduce a full-SKU query, a discriminating core+qualifier, an allowed broader model and a descriptive query. A missing qualifier on a query never disappears from the comparison target. |
| `product_identity/catalog_index.py` (R6 only) | Compile the optional scoped retrieval index from catalog records. Return candidate spellings, collisions and discriminating projections, each with provenance. | Turn the index on/off for a frozen target/candidate pair; retrieval order may change, the pair verdict with the same approved policy must agree. |

### Migration from the existing code

| Existing source and symbols | Destination or adapter obligation |
| --- | --- |
| `pricing_engine/matcher.py` — normalize_screen_units, normalize_technical_slashes, expand_cartesian_branches, extract_product_slots, normalize_color | Assign token grouping to tokenizer, quantity interpretation to measurements, branch and facet ownership to extractor. Protect original branch/qualifier evidence before any cleanup. Keep callable compatibility adapters where existing consumers depend on their signatures. |
| Same file — extract_search_query_and_model, _generate_single_branch_patterns, generate_search_patterns, generate_model_first_queries, normalize_search_query | Move query projection semantics to queries. The legacy two-value and tier-dictionary functions translate from the prepared identity and ordered projections. Preserve existing normalized query key semantics per adapter. |
| Same file — _complete_sku_evidence_level, _evaluate_anchor_compatibility, _has_variant_tag_collision, _referee_match, referee_match, referee_series_candidate | Port comparison obligations and reason/basis mapping to the pure matcher. Test its raw-string host wrapper against the prepared API for both single and multi-branch inputs. |
| Same file — is_strict_model_match, _keyword_match, tonnage_matches_title, reverse_tonnage_matches, model_identity_parts | Characterize the legacy Boolean, non-model and dedup-key consumers before moving internals. Preserve argument order and old return types. Prevent a Boolean-only acceptance from entering the commercial pool outside existing production routing. |
| `pricing_engine/capacity.py`, root `config.py`, `pricing_engine/calculator.py` | Capacity becomes a delegating compatibility surface. Root config and calculator keep shipping rules, category brackets and money calculations. Verify identical dimensional/primary-capacity projection where shipping uses these inputs. |
| `pricing_engine/registry.py`, `learner.py`, `db.py` | Registry loads approved facts and constructs the immutable snapshot. Learner records candidate observations using existing provenance; DB handles optional persistence. No DB reads inside core matching and no automatic alias approval from a match. |
| `pricing_engine/series_fallback.py` — build_series_search, has_active_model_offers, referee_series_match | Keep host ownership of authorization to search and suppression by in-stock model offers. Delegate pair evaluation to compare_series. Preserve the stricter leading-brand, no-candidate-anchor and whole-series gates. |
| `pricing_engine/scraper.py`, `digi_discovery.py`, `digi_transport.py`, `async_utils.py` | Keep HTTP, per-market scheduling, retry limits, page evidence, cancellation and in-flight sharing at the boundary. Adapt query inputs per public entry point. Use the same immutable target when a query broadens. |
| `pricing_engine/offer_processing.py`, `models.py` | Convert raw API fields to ProductText without inventing brand. Parse seller, price and stock separately. Adapt Decision to MatchDecision/ScrapedOffer, deduplicate and finalize. ScrapeResult owns coverage, pool conflict and rejection diagnostics. |
| `index.py`, `pricing_engine/ingestion.py`, `pipeline.py`, `range_pipeline.py` | Validate inputs and route workers through preparation. Keep TTY interaction in the CLI/pipeline. Test headless skip, selected variant across marketplaces and each mode's output. Range has a separate loader and an existing title-derived brand path; record its conflict with the owner's explicit-brand rule, cover it with a failing range-input test, and document the intentional behavior change before cutover. |
| `pricing_engine/evaluator.py`, `exporter.py`, `publication.py` | Preserve reference selection, profit floors, commission, warning propagation/formatting, CSV/XLSX schemas, publication receipts and verified-current winner cleanup. Identity can change which eligible offer enters evaluation. Reconcile every resulting price difference against its listing and decision. |
| `pricing_engine/__init__.py`, `source_provenance.py`, `run_signature.py`, `checkpoint.py` | Ensure source and profile fingerprints include every semantic dependency of the external library. Use qualified names to avoid collisions between the two matcher modules. Keep display-only producer dependencies separate where supported. |
| `pricing_engine/run_control.py`, `run_state.py`, `run_lock.py`, `state_io.py` | Reuse validated working/completed generation selection, destination locking, row reconciliation and atomic JSON storage. A row or tenant ID never substitutes for a compatible processing identity. |
| Build metadata and CI | The current root pyproject declares the entire pricing application and its dependencies. Give the identity distribution explicit package inclusion and its own dependency metadata. A reproducible wheel build must include only the library and its declared semantic resources. Test both checkout imports and the installed wheel from an empty working directory. |

## 12. Data contracts and executable decision procedure

### Public operations and failure handling

| Operation | Precondition | Observable return |
| --- | --- | --- |
| prepare(input, context) | Valid source kind, original title, approved snapshot. Catalog brand requirements belong to the active consumer contract. | Immutable identity with zero or more viable interpretations, span references, observations and any preparation limitation. Missing SKU can be a normal descriptive case. |
| propose_queries(target, context) | Target prepared under the same semantic context. | Ordered projections with branch IDs and evidence references. If no allowed projection is available, return an explicit unsearchable result for that path; the host preserves existing per-platform behavior. |
| compare(target, candidate, context) | Both records prepared under compatible schemas and profiles. | Ordinary directional verdict. Pair comparison has no knowledge of cheaper sellers, available stock or discovery health. |
| compare_series(target, candidate, context) | Host has separately qualified a series pass. The pair is still checked for all series requirements. | Series-basis base result with warning, or structured refusal of eligibility with reason. The host alone knows when this invocation is permitted. |
| Legacy entry points | Honor the real positional arguments, public types and defaults in the checkout. | Translate the richer decision to existing booleans, tier, basis, reason and notice. Use compatibility tests for each wrapper, including empty input and exception behavior. |

Invalid input, incompatible preparation context, exhausted interpretation budget and genuinely different SKU are separate results at the external boundary. The first two are caller errors. A budget-limited observation is unresolved and cannot be counted as a definitive marketplace rejection. An external consumer must be able to handle an unknown future reason code conservatively.

A proposed serialized **decision fragment** for row 85 is shown below. References resolve to observations in the two prepared records. Consumers can use the disposition without parsing English text.

```json
{
  "schema_version": 1,
  "basis": "model",
  "disposition": "conflict",
  "tier": null,
  "reason_code": "MODEL_CONFLICT",
  "evidence": [
    {"role": "core", "target": "t.core", "candidate": "c.core", "relation": "equal"},
    {"role": "qualifier", "target": "t.qualifier", "candidate": "c.qualifier", "relation": "contradictory"}
  ],
  "notices": []
}
```

Here `t.qualifier` resolves to the literal `X-IK` and `c.qualifier` to `YB(IK)`. Their original field, offsets and grouped components remain accessible. Local observation references are scoped to a prepared record. They are never persistent identifiers for a catalog product.

### Decision procedure for novel titles

1. Prepare both records independently, retaining whole-code evidence and coexisting parses. An explicit model field and title disagreement creates a conflict to examine; a parser must not use the preferred source to hide it.
2. Determine branch membership before normalization erases a slash or bracket. Compare coherent branch pairs. Work bounds apply to interpretation cost only. Preserve unresolved ambiguity when a bound is reached.
3. Evaluate evidence authority and guarded conflicts first. Identify whether conflicting components represent distinct editions under a recognized sibling rule. Reject incompatible sellable units and any surviving hard conflict.
4. Within each valid interpretation, match intact codes and complete compound qualifiers first. Then consider ordered child runs and approved scoped aliases. Each role needs its own independent witness; a lexical prefix hint, suffix width, common tap count or catalog frequency cannot discharge a missing identity obligation.
5. Build an obligation record for each remaining target requirement and material candidate addition. Resolve it to exact agreement, an explicitly eligible directional waiver, extra feature/advisory, conflict, or unresolved. Store the applicable policy reference with every waiver.
6. Aggregate the surviving interpretations. A determinate exact requires a coherent witness and no unresolved competing interpretation that could point to a different sellable variant. Apply the established base/sibling rules only when their preconditions hold. If evidence is insufficient, carry uncertainty to the host. Do not break an identity tie by cheapest price or first API result.
7. Return pair-level evidence. The host chooses the active in-stock pool, checks discovery/series suppression, and renders any observed variant choice. Recompute the selected reference and its notices from the filtered pool when the user chooses a variant.

At step 3 compare explicit measurements on corresponding subjects and branches before using model-derived estimates. Different stated values for the same guarded subject veto the pair even if the full identifier agrees. Compare an accessory measurement only against the corresponding accessory. An unknown subject cannot silently satisfy a required measurement; an unresolved difference that could change the sellable variant prevents automatic pricing. Keep the independent explicit SKU conflict check even when all measurements agree.

### Controlled vocabulary and alias lifecycle

| Type of fact | Permitted origin and scope | Promotion / revocation check |
| --- | --- | --- |
| Unit, polarity or presentation spelling | Shared measurement/lexical vocabulary with typed meaning | Test literal model segments, bare prepositions and a positive measurement before changing the common grammar. |
| Brand alias, capacity code or documented equipment synonym | Approved scoped registry or authoritative catalog/manufacturer mapping | Include conflicting neighboring families, a foreign brand and reversed registry order. Leave unsupported scope unknown. |
| Seller's reordered title or shortened query spelling | Retrieval evidence from verified listings, with timestamp and source | May affect ranking and retrieval coverage. Only independently verified identity evidence can authorize an equivalence used for exact matching. |
| Candidate designation, tentative alias or fallback observation | Existing learner, seller response or manual review queue | Store observation and counterexamples separately from active policy. Reject circular evidence derived solely from prior matcher acceptance. |
| Policy update affecting acceptance | Owner-approved business decision, with defined direction, affected role and expected warning | Pin a new semantic version/digest, replay known positives and nearest negatives, invalidate applicable persistent reuse and retain a compatible rollback profile. |

### Cache and invalidation contract

| Cache or state | Minimum distinguishing inputs | Failure to simulate |
| --- | --- | --- |
| Raw marketplace page | Marketplace, complete request context within run, normalized query, page/cursor, page size and freshness | Cached prefix of pages reused under a new target; actual next page must still be fetched when required. Protect private request context through the existing safeguards. |
| Prepared record | Original fields including declared brand and input role, profile/scope, parser and schema digest | Same listing text with different declared brand or attached option tags. An incompatible entry must be missed. |
| Pair verdict | Ordered target/candidate identities, model vs dedicated-series operation and applicable policy | Reversed inputs, same title across tenants, approved alias changed, or series-mode verdict leaking into an ordinary request. |
| Catalog query plan | Prepared target, ranking/index digest, adapter policy and budget | Another catalog row introduces a conflicting sibling. Previously broad projections can change priority. |
| Persisted processed result | Existing processing signature plus qualified library code/resources, scoped profile and influential index digest | Mid-run mutation, old working state vs newer completion, or downgrade to an older package. A targeted run cannot silently become a full refresh. |

## 13. Acceptance cases and end-to-end responsibilities

Expected results below are acceptance specifications. Each fixture must state separately whether its basis was an owner decision, an existing test, a reproduced defect or a verified market label. Where an identity is uncertain, preserve that label until independently resolved.

| Case | Positive/control | Nearest adversary or omission | Assertions across stages |
| --- | --- | --- | --- |
| Cabinet compound, Book1 #85 | Intact `24CE03/X-IK` with adequate brand/facets | `/YB(IK)`, `/KB`, omitted qualifier, and `24 X-IK` without core | Preserve attachment; produce a reachable discriminating query. Explicit conflict rejects, allowed omission is base with yellow warning, missing core cannot become exact. |
| Reordered chassis, Book1 #89 | Full catalog model; independently confirmed equivalent seller configuration | `QC6` or a different chassis/kit; bare `18HRFN1` | Separate retrieval miss from referee miss. Retain original core/chassis and qualifier spans. Exact needs the same sellable unit; represent an observed indoor-only designation explicitly. |
| Haier HFS / PRIME | Compatible intact code, explicit or corroborated color | Opposing subordinate `(B)` / `(G)`, uncorroborated suffix, missing required qualifier | Preserve pre-clean slash evidence; a group with an unknown color interpretation stays a literal code. Distinguish missing from conflicting. |
| Glued dispenser model and Samsung trim | Valid separator-only presentation and documented same-variant spelling | Different color, `19HFC` vs unverified `19HFCS`, different model stem, or added unverified regional suffix | The whole identifier survives. An unverified trim may broaden retrieval but cannot authorize exact. Keep Book1 #98 as supplied. |
| Icon / quantity, Book1 #20 | Independently supported named model and compatible dispenser attributes | Same number as litres/watts, range, or conflicting explicit model | Compare dimensions and subjects. The number is never independent proof of a model. Preserve the corrected catalog input. |
| Screen and washer | `32 in` vs `32 Inch` in display context; `QX 255 IN White 10 KG` | 40-inch screen, opposing wash load, quoted SKU or separate display size | Assert actual spans and quantities and stable case handling. Test 100-inch displays and mixed dimensions. |
| Series and styling | Approved series spelling, same verified model and compatible finish | E-Chrome vs Chrome, discrimination by Pro or plus, other explicit SKU | Keep branch-local series, exact/base choice and warning direction across ordinary and last-resort routes. |
| Market notices | Loose seller designation on existing exact-advisory case | Attached conflicting suffix, extra guarded feature, optional vs explicitly negated feature | Role drives verdict and notice. The warning belongs to the selected external reference in terminal/CSV/XLSX. |
| Seller and variant choices | Legitimate final color after seller text; duplicate sellers for one variant | Seller name beginning with a color, competing base variants, no selection, or chosen variant unavailable on one marketplace | Preserve evidence without inventing a color. Exercise TTY selection, headless skip and filtered pool behavior for both platforms. |
| Model-less cases | Verified descriptive target or catalog-declared series with brand/family/capacity | Missing family, foreign brand, partial series, explicit contradictory SKU, only an active own-store model | Exercise legacy keyword, ordinary anchorless and dedicated series entry points separately. Keep model-basis suppression and reasons observable. |
| Prefix omission and siblings | Identical full model; documented allowed omission or sibling | Unrelated prefix carrying same number, wrong color suffix, unselected cheaper sibling | Distinguish exact identity from eligible commercial reference. Verify DW-MD omission produces the owner's yellow-warning outcome. |
| Unknown format | Unseen synthetic brand and an intact, independently declared opaque code | Same code except one digit, leading zero, or unresolved separator collision | Record the conflicting spans or uncertainty. Expose it identically through the Python and serialized boundary. |

The original adversarial review is tracked here explicitly. AR-1 is raw/prepared slash and branch parity (R1/R3). AR-2 is unverified color/trim peeling (R3/R4). AR-3 is shared numeric stem and series sufficiency (R4/R5). AR-4 is compound post-slash atomicity (R3/R4). AR-5 combines subordinate-code provenance and query-baseline compatibility (R3/R6). AR-6 covers three-digit displays and unambiguous units (R2). AR-7 requires model-edition conflicts to be resolved before classifying an extra guarded feature (R4). Keep at least one positive and one opposing control for each.

### Replay six distinct flows

| Path | What a replay must carry end to end |
| --- | --- |
| Ordinary SKU | Original catalog target → prepared compound(s) → query proposal → raw seller observation → same extractor → pair decision → selected in-stock tier and its warning. A broader query cannot relax comparison. |
| Legacy Boolean/keyword | Scraped title + target model in legacy argument order → model/keyword routing → existing tonnage/T3/keyword checks and structured fallback where applicable → Boolean. Record disagreements with the ordinary referee separately. |
| Ordinary anchorless | No conventional anchor → inspect series and positive identifying attributes → run ordinary referee → preserve its accepted, rejected or unresolved result and basis. Presence of this path does not schedule a series-only API query. |
| Dedicated series | Eligible and healthy model-first attempt → absence of compatible active model including own store → explicit bounded series query → ordinary referee first → eligible series comparison → tier 2 with series notice or rejection. |
| AlfaMall | Query tiers → actual deduplicated requests/pages → raw observations → decisions → pool aggregation → variant handling → evaluation/range/output. Replay exhaustive and permitted early-exit paths, page failure and warm-cache continuation. |
| DigiMall | Target branches → budgeted model-first queries → page-level coverage and caching → branch-specific comparison → bounded fallback when eligible → merged pool and coverage. Exercise plan, explicit string and tier-dictionary entry points separately. |

## 14. Implementation work orders and test ownership

Use §8 for dependencies, intended behavior and rollback. The table below names the implementation surface and first executable assertion for each work order. Test filenames in the second column are existing starting points unless explicitly marked proposed. Place new assertions in the closest owner; the plan does not require a separate test file for every row.

| Work order | Source and test ownership | First assertion and evidence to save |
| --- | --- | --- |
| R0 · freeze evidence | `tests/test_architecture_contract.py`, `tests/fixtures/model_identity_regressions.json`, `tests/fixtures/hardware_query_regressions.json`, `scripts/audit_architecture_contract.py` | Replay the unmodified Book1 #85 target and two opposing compound variants, record old verdicts and the contract-required verdict. Save both; a known wrong legacy result is baseline evidence, never the expected target. |
| R1 · API and boundaries | New types, profile, public surface; `tests/test_import_boundaries.py` and proposed `tests/test_identity_api.py` | Import from an isolated consumer and round-trip one opaque identifier, one case with missing SKU and one multi-branch case. Assert ordinary and series operations are distinct. |
| R2 · measurements | New tokenizer/measurements, existing capacity facade; `tests/test_capacity_contract.py`, `tests/test_structural_measurements.py`, `tests/test_shipping_capacity_units.py` | Test exact, absent and range observations independently, then attach multiple quantities to different subjects. Run existing shipping and parser callers before switching the facade. |
| R3 · extraction | New extractor; old extract_product_slots wrapper; `tests/test_hardware_interpretation.py`, `tests/test_model_identity_evidence.py`, `tests/test_matcher.py` | Assert #85's original compound survives intact. Alter a seller clause and reorder independent SKU components. Verify the qualifier, option group, seller and guarded physical facts are still traceable to their own spans. |
| R4 · comparison | New matcher; old referee and compatibility adapters; `tests/test_generic_variants_and_polarity.py`, `tests/test_hardware_advisories.py`, `tests/test_own_store_deduplication.py` | Assert the exact control and reject the conflicting compound under an unseen brand. Add approved directional omissions, supported sibling, excluded tiers and selected notice provenance. Keep policy corrections in separately reviewable changes. |
| R5 · non-model modes | Matcher, series_fallback, keyword adapter; `tests/test_series_fallback.py`, `tests/test_series_contract.py`, `tests/test_matcher.py` | The same candidate cannot enter through the series path with an explicit foreign SKU or absent leading brand. Prove a positive eligible case and two independent ordinary/legacy controls. |
| R6 · retrieval | Queries, optional index, plan adapter; `tests/test_digimall_discovery.py`, `tests/test_architecture_contract.py`, `tests/test_phase2_alfa_discovery.py` | Run both marketplace adapters on captured responses. Assert the known listing ID is reachable through a budgeted, source-backed projection. Reject invented combinations of seller words, numeric stems and qualifiers from independent branches. |
| R8 · provenance before R7 persists results | source_provenance, run_signature, checkpoint; `tests/test_run_signature.py`, `tests/test_run_state.py`, `tests/test_targeted_reruns.py` | Mutate only a library resource, then only a relevant profile or catalog ranking digest. Prove incompatible reuse is refused. Reordering equivalent mappings stays compatible; secrets are absent from persisted state. |
| R7 · host integration | Offer parser, Alfa and Digi orchestration, pipelines; `tests/test_offer_processing_contract.py`, `tests/test_checkpoint_and_ambiguity.py`, `tests/test_range_mode.py`, `tests/test_hardware_output.py` | Pass identical raw pages with stock, own-store and tier differences. Assert selected listing, affected platform, price reference, warning, risk and XLSX highlight. Test reversed arrival order and headless unresolved variants. |
| R9 · distribution and release | Wheel/build metadata, new-package imports, configured CI and `tests/test_publication.py` | Install only the wheel in an empty consumer environment, compare a raw pair, then load the same evidence through the repricer. Prove a fallback reference cannot masquerade as an exact asset identity. Replay full catalog and rollback drill. |
| R10 · retire duplicates | Existing matcher/capacity facades, actual importers, documentation; `tests/test_import_boundaries.py` and whole suite | Search for every retired symbol, run fresh importer tests, and observe one canonical path for the same semantics. Remove a compatibility wrapper only after accounting for supported external callers. |

### Slice checkpoints

- **After R1–R3**, inspect the prepared identity for an unseen title without running either marketplace. An engineer must be able to point to the exact original substring behind every material code and recover all alternate branches.
- **After R4–R5**, the same prepared pair must reproduce the approved outcome through both the package and the legacy adapter. Explain differences caused by explicitly approved policy changes in the test evidence.
- **After R6 and R8**, run shadow retrieval and comparison on frozen input. Existing publication remains authoritative until the applicable R7 path passes its end-to-end checks.
- **After R7–R9**, deployable artifacts comprise a proven wheel, the host adapter, the pinned semantic profile, compatible processing signatures and release evidence. The future SaaS transport can consume this contract independently.
- **After R10**, inspect imports, call sites and profile data for duplicate policies. Compare both marketplace paths again after cleanup since an apparently unused wrapper can still be a public integration surface.

## 15. Book1 evidence collection and repeatable verification

### Evidence record

For each of the 100 original Book1 rows create one catalog record and one marketplace observation per attempted market. A full-catalog replay therefore accounts for **200 row/market combinations**, including both attempted failures and explicitly unverified combinations. Use row number only as a locator inside the pinned catalog copy. Reconciliation across runs follows the application's validated input rules.

| Record | Fields to retain for verification |
| --- | --- |
| Run | UTC observation time, source revision and working digests, catalog SHA-256, engine/profile/index digests, mode, adapter settings, permitted request budgets and whether data is fresh, recorded or synthetic. |
| Target | Row locator, exact title, declared brand and metadata, prepared branches/measurements, expected identity mode, expected policy and source of the expected label. Preserve the three verified Book1 corrections. |
| Discovery | Marketplace, candidate queries in order, actually executed queries, page number, cache status, success/failure, expected vs fetched coverage, raw count and stable listing references when present. |
| Listing and decision | Listing ID or scoped observation reference, raw title, separate declared brand, vendor, stock and relevant specifications. Keep normalized spans, rejected alternatives, pair verdict/tier/basis and reason, modifier direction and warnings. |
| Outcome | Selected eligible listing or reason for no decision, own vs competitor classification, user choice/skip, emitted warning and resulting reference. Record absence, incomplete search, uncertain identity and verified mismatch separately. |
| Adjudication | Independent expected label and why, evidence supporting the same sellable unit, owner-approved exception or uncertainty, discrepancy owner, next test and disposition. Mask credentials and private request headers; preserve only evidence needed to replay the decision. |

### Procedure

1. Pin source, catalog, approved context and existing outputs/checkpoints. Use a temporary checkout or verified payload and isolated writable destinations. Ensure learner/DB state cannot write to a production account during replay.
2. Use the actual worker path and mode that produced the baseline. For personal-commission outputs include the same personal-commission setting; default repricing and market range have different downstream contracts. A fixture script aimed at another catalog is insufficient for this comparison.
3. Capture one permitted marketplace run or replay preserved responses. Feed the same responses and page order to old and new engines. If a planned query is absent from the recording, label it **uncaptured**. Only an actual new response can establish whether that added query retrieves a listing.
4. Compare per-stage records. Classify a difference by the earliest stage where the two traces diverge: query coverage, raw retrieval, parsing, preparation, comparison, eligible pool, variant choice, evaluation or publication.
5. Inspect all 100 rows. For changed or disputed selections inspect the actual listing and technical configuration where available. If inaccessible or ambiguous, leave the identity unverified and exclude it from the denominator of *verified* correctness, while keeping it in the coverage report.
6. Repeat frozen pages with the cache warm and shuffled return order. Separately perform bounded fresh checks on Alfa and Digi for important disputed or newly retrieved cases. Timestamp results and keep live volatility independent from algorithm determinism.
7. Compare catalog order, original columns and S.NO, price and margin calculations, warnings, coverage state, platform-specific exports and workbook formulas. Reproduce any price delta from the selected listing and unchanged evaluator. Confirm input/output/checkpoint fingerprints outside the test destination are preserved.

### Quality commands

Run from the isolated repository payload using the project's virtual environment. If its interpreter resides in the original checkout, point **$py** at that absolute executable while keeping the working directory in the isolated payload.

```powershell
$py = (Resolve-Path '.venv/Scripts/python.exe').Path
& $py -m pytest tests/test_matcher.py tests/test_capacity_contract.py tests/test_structural_measurements.py
& $py -m pytest tests/test_series_contract.py tests/test_series_fallback.py tests/test_offer_processing_contract.py
& $py -m pytest tests/test_architecture_contract.py tests/test_digimall_discovery.py tests/test_phase2_alfa_discovery.py
& $py -m pytest tests/test_checkpoint_and_ambiguity.py tests/test_targeted_reruns.py tests/test_run_signature.py
& $py -m pytest tests/test_hardware_output.py tests/test_range_mode.py tests/test_publication.py
& $py -m pytest -v --durations=10
& $py -m ruff check .
& $py -m ruff format --check .
& $py -m mypy .
git diff --check
```

Also execute the new tests for each slice, fresh-process import parity and installed-wheel conformance. Record exits, versions, actual counts and warnings. Before comparing latency, pin hardware, dataset, warm/cold status, measured operations and API responses. A faster run that skips a branch or page is a coverage regression.

## 16. Release, rollback and engineer handoff

### Decision record at cutover

| Gate | Required artifact | Stop condition |
| --- | --- | --- |
| Identity | Reviewed positive/nearest-negative matrix, false eligible and false exact counts, unresolved cases and dispositions | A critical labeled negative is eligible, a protected explicit conflict disappears, or an exact verdict lacks a witness. |
| Retrieval | Per-market known-ID coverage and actual requests/cost, with healthy, capped, partial and failed runs identified | A previously reachable verified listing disappears without explanation, a query budget is exceeded, or failed retrieval is reported as verified absence. |
| Consumer contract | Golden raw/prepared/legacy comparisons and output replay for repricing, range, optional image consumer and installed wheel | A selected warning leaks from another listing, a pending variant becomes an automatic choice, or the second application requires the pricing stack to match titles. |
| Reuse and recovery | Digest mutation tests, mid-run interruption, concurrent destinations, rollback drill and terminal publication receipts | A stale generation is reusable under different semantics, an unverified winner is cleaned up, or a partial export is represented as complete. |
| Operations | Frozen-corpus performance results, worker/resource limits, tenant separation tests, current CI results and independent review | An unresolved difference materially changes price/identity or an operational failure can silently produce an exact result. Document any known baseline limitation for owner review. |

### Rollback drill

1. Pin the release and previous engine, host adapter, approved profile and resource digests. Exercise the switch on an isolated destination before enabling production writes.
2. Simulate a failed candidate release after some rows were processed and again after partial export publication. Restore the previous compatible engine/profile together. Let the existing generation/provenance checks decide which state can be reused.
3. On incompatible targeted state, surface the established request for explicit full authorization. Preserve the first-run exception and unchanged-input no-prompt behavior. Never silently mix records processed by the two semantics.
4. Republish only through the existing per-file publication/receipt logic, retaining audit history and user-modified or unverified winner files. Verify full row order, chosen references, row count, warnings and actual successful artifact paths.
5. Record the triggering regression, its source/destination evidence and a reproducible test. Resume rollout only after the relevant gate is green and the reviewed change is authorized.

### Approval boundary

The deliverable here is the **architecture and implementation plan**. The current application baseline is recorded in §1/§9. The library, its conformance fixtures, its live recall and its migration gates are future implementation deliverables. In particular, real SKU/kit or regional-trim equivalence needs product evidence; a design decision cannot supply a missing manufacturer fact. The old catalog and live evidence tables remain available in the owner's original file.

**Argon's first actionable deliverable after approval** is R0: a pinned baseline with one paired positive and opposing variant, an ordinary and a dedicated-series control, and a reproducible trace to the existing final selection. Then follow the dependency order in §§8 and 14. At each authorized commit, obtain separate adversarial review of the actual final diff, preserve the owner's data and edits, and publish the verification performed for that slice.

## 17. Cross-catalog stress check and additional cutover gates

These offline probes ran against the existing working matcher, before implementation of this design. Row numbers below are one-based data rows excluding headers. No marketplace request was involved. Seven repository test modules passed **438 tests in 13.78 s**: test_architecture_contract, test_structural_measurements, test_hardware_interpretation, test_model_identity_evidence, test_offer_processing_contract, test_generic_variants_and_polarity and test_series_contract.

| Working input and probe | Observed on the existing path | Additional acceptance requirement |
| --- | --- | --- |
| Book1, all 100 rows; call referee_match(title, title, brand) then lowercase only the candidate | 100 exact self-matches. All 100 retained the same tier and reason code on lowercase candidates. | Run on the actual input CSV as well as the historical JSON baseline; compare notices, basis and variant group in addition to tier and reason. |
| Book1, same 100 comparisons, substitute extract_product_slots(title, brand) for the raw target | Rows **70, 74 and 85** fell from exact to base. Row 70 reported missing variant C, row 74 missing E, row 85 an IK mismatch, each against its own original title. | **R1/R3 blocker for prepare-once.** Exercise all 100 raw/prepared pairs before using the cache. Pin these three exact controls and their opposing variants. Preserve the branch-local source span used by the raw path, then compare both APIs through the offer parser and notice renderer. |
| Gree_AC rows 4 and 5, Haier_Washers rows 2 and 3, Midea_Eco_Series rows 1 and 2, Book1 rows 3 and 89 | Each pair rejected in both directions with MODEL_CONFLICT. Raw self-match controls gave 25/25, 38/38, 2/2 and 100/100 exact respectively. | **R4 hard negatives.** Keep Gree B/W color editions, Haier 90/100 drum models, Midea 12/18 model distinctions and different chassis/QC variants separate even when search relaxes to a shared stem. |
| Dawlance_Products_List, all 270 raw titles used as their own listing titles, with brand supplied only as catalog context | 82 exact and 188 BRAND_CONFLICT. Repeating with independently simulated matching listing metadata yielded 269 exact and one SERIES_CONFLICT. Injected foreign metadata yielded 270 brand conflicts. For rows 2/3, white vs silver, the reason switched from candidate brand “SILVER” to a color collision when correct listing brand was supplied. | **R3/R4 brand provenance.** Track verified foreign brand, missing brand and explicit color conflict separately. Never infer that SILVER is a manufacturer from token position, and never copy the target brand into a listing to clear the gate. Missing brand can remain uncertain. Validate both pair classification and downstream definitive-vs-suspicious rejection counters. |
| Dawlance row 223, identical raw title and correct candidate brand | Even with matching brand, “WD 1051 GD C/S/R/B” compared with itself produced SERIES_CONFLICT, with candidate series “R / B” versus target “R”. | **R3/R5 multi-option control.** Preserve the original grouped alternatives on both sides. A self-comparison must not manufacture a contradictory series. Independently verify the letters' meaning before granting a specific saleable variant, then test a strict subset and a disjoint choice. |
| Midea_Eco_Series row 1, controlled seller strings replacing the bracketed optional declaration with T3, QC0 or QC6 | T3 and QC0 were exact without a notice. Loose QC6 was exact with a market cross-check notice. | Record source role and attachment. Assert loose market designation and attached differing model qualifier separately. Optional target tags must never authorize a different attached SKU qualifier. |
| Four target groups / 11 stored seller offers in tests/fixtures/model_identity_regressions.json | All 11 returned tier 1 on direct comparison, including merchant prose and altered separators. These fixtures include a historical Samsung target with RT. | R0/R4 preserve the fixture's exact source title and expectations separately from current Book1 #98. R7 also checks stock, vendor/own store and selected notice because direct comparison excludes those operations. |
| Synthetic listings “Midea 18HRFN1-QC2 Inverter AC” and “Midea 18HRFN1-QC6 Inverter AC”; distinct external vendors, both priced at 100000 | Bare target “Midea 18HRFN1 Inverter AC” rejected both with FACET_CONFLICT; parse_offers_with_tiers then finalize_offers produced zero offers and no ambiguity object. Explicit QC2 target accepted QC2 only and raised no choice. | **R4/R7 owner-facing variant gate.** For independently verified options of the same selectable base, require a list of observed QC2/QC6 choices, TTY selection and headless skip. Keep the explicit QC2 control and a foreign chassis/kit negative. A conflict that depends on unverified family membership must not be turned into a priceable base offer merely to trigger a prompt. If eligible option evidence is lost before pool finalization, carry selectable alternatives separately from priceable offers until the user chooses; recompare the chosen explicit target before pricing. |

**Reproduction.** Read CSVs with utf-8-sig, preserving original values; use Title in Book1, Name or the whitespace-suffixed Name header in the other inputs. Compare each original title with itself using the row's Brand. For the three prepared-target comparisons use the same original candidate and the same brand. For the brand matrix vary only candidate_brand. For the QC pool use the two literal seller titles above with declared Midea brand, separate vendors and positive original prices. Inspect exact/base/sibling buckets and ambiguity_conflict, not just the Boolean result.

**Test blind spot.** The current test_catalog_self_matches_keep_model_identity reads tasks/architecture-consolidation-baseline.json and permits exact, base or sibling. It cannot detect a regression from exact to base on a current catalog row through the prepared entry point. Keep that historical coverage. Add a separate current-input exact-tier, basis and warning parity test to R1 and a selection-level regression to R7. Treat the current run as evidence of migration risks, not as a measurement of the future library's accuracy.
### 17.1 Owner acceptance cases for omissions and conflicts

Offline checks below use the current raw-title and prepared-target referee entry points. For Book1 rows 49, 85 and 96, keep the full catalog and candidate titles equal except for the indicated edit. These are controlled comparisons, not fresh marketplace responses.

| Target and seller evidence | Observed now | Required at cutover |
| --- | --- | --- |
| Book1 #49, Dawlance 9193LF Avante+ 16 Cu Ft, Sapphire Purple | Exact control passes. Removing only Sapphire Purple still returns Tier 1 without a notice on either entry point. Replacing it with Cloud White returns SERIES_UNCERTAIN; extraction identifies opposing purple and white families. | Retain an otherwise eligible color-omitting offer alongside exact listings. Attach a yellow notice identifying the catalog color and seller omission. Explicit opposing color rejects with the color conflict preserved. Exact color control gets no omission notice. |
| Book1 #96, Haier HSU-13HFN/013WDC(W)-T3 | Changing (W) to (B), removing (W), and leaving the title intact all return Tier 1 without a notice on both paths. | Preserve the parenthesized code attached to the submodel. Same code passes, explicit opposing code rejects, omitted code follows approved incomplete-core handling with a warning. This comparison needs no translation of W or B into color names. |
| Book1 #85, Haier HPU-24CE03/X-IK | Original, /KB substitution and qualifier omission all return Tier 1 raw and Tier 2 prepared. | Both paths must agree: intact compound passes, /KB rejects, and an otherwise eligible omitted qualifier receives its own warning. |
| Dawlance DWMD-15 vs MD15; Haier HWM-91 vs HWS-91 (same brand and appliance prose within each pair) | First pair Tier 1; second MODEL_CONFLICT on both paths. | Preserve supported prefix omission with a notice and reject opposing stated prefixes. Never equate models solely on their numeric portion. |
| Current Book1 #20, Orient VCM Series Icon 2 Top Load Bottle Water Dispenser | Icon 2 Taps accepted; Icon 3 Taps, Icon 2 Ltr, bare 2 Taps and Icon 2 Taps WD-529 rejected on both paths. | Preserve the named identity and explicit competing SKU veto. Tap count alone cannot identify the model. The corrected input declares neither color nor volume. |

R4 checks each decision, omitted role and conflicting span. R7 replays eligible sellers with and without an exact seller in the same Digi result set. Check each listing's notice, the selected reference notice on the card and in exported reason text, and absence of a color warning when the target itself has no color. Retain the original target color wording for display even when the matcher compares normalized colors. Run the same decision controls through Alfa's shared comparison path. These requirements do not decide pricing precedence between exact and incomplete offers.

### 17.2 Marketplace observations and owner-approved item #85 spelling

The two public Digi API queries behaved differently during the live spot check. `24CE03` (digit zero) returned nine rows including EZZI and KiaChahiye. `24CEO3` (letter O) returned five rows covering all four sellers below, including a repeated iShopping row. These are observations from that check. R0 should pin the original titles, returned IDs, page/query and stock/price fields for reproducible replay. Keep the supplied run card as evidence of the historical output. [Digit-zero query](https://digimall-be.faysalbank.com/storefront/search_products?storefront=23&q=24CE03&page=1&limit=18) · [Letter-O query](https://digimall-be.faysalbank.com/storefront/search_products?storefront=23&q=24CEO3&page=1&limit=18)

The owner confirmed that the seller core `HPU-24CEO3` is a misspelling of this catalog's Haier `HPU-24CE03`. Store this directional, whole-core equivalence as approved profile data under §12, with owner provenance and scope. Preserve the original seller title and matched span. The approval covers the core only. No catalog edit, global character substitution or executable Haier exception is authorized.

| Digi seller and observed title evidence | Expected outcome in replay with the supplied card's Rs. 235,898 floor |
| --- | --- |
| Shahid & Sons, `Haier Floor Standing Air Conditioner 2.0 Ton (HPU-24CEO3)`, Rs. 223,000 | Visible compatible base seller. Yellow notice identifies the verified spelling and omitted `/X-IK`. Below floor; excluded as an undercut reference. |
| iShopping Team, same bracketed title, Rs. 224,599 | Same base decision and both notices. Apply existing offer deduplication. Keep this seller distinct from Shahid. Below floor. |
| EZZI TRADERS, `Haier AC 2 Ton Floor Standing HPU-24CE03 \| Free Installation by Haier`, Rs. 255,999 | Visible base seller with only the qualifier-omission warning. With the four observed sellers and the supplied floor, it is the eligible external pricing reference. |
| KiaChahiye PVT LTD, `Haier HPU-24CE03/X-IK 2 Ton Cabinet Air Conditioner`, Rs. 230,900 | Full model match. Display as own store and exclude from external pricing. |

Implementation gates for this decision:

* **R3/R4:** Bare and externally bracketed digit-zero cores produce the same base decision. A bracketed full SKU remains exact. Letter-O core plus `/KB` rejects even with the approved alias. Remove the alias or use an unrelated tenant/model and verify that visual similarity alone cannot authorize pricing. Compare raw and prepared paths.
* **R6/R7:** Retrieve the captured sellers with source-backed projections inside the platform budget. Replay the identical seller payload via exact, alternate and broad queries. Hold target, profile, stock and floor fixed. Tier, warnings and pricing eligibility must remain identical. Record query provenance independently. Check returned listings, displayed sellers, duplicates, selected reference, exported reason and discovery coverage separately. A missing API response is a discovery gap; do not record it as a model rejection.
* **R8:** Fingerprint the approved data with the profile. Revoking or changing its scope invalidates incompatible decisions and checkpoints. A run uses its original frozen profile through publication.

Two adjacent controls prevent broader false matches. Digi returned EZZI's `9193LF Avante+ ... 18CFT` for the Dawlance search. Against the 16 Cu Ft Sapphire Purple target, the explicit capacity conflict rejects even when color is missing. Retain the compatible 16 Cu Ft color-omission control from §17.1. For `HSU-20HFTEX` versus `HSU-20HFT`, no family equivalence was established in this review. Preserve exact-first selection; admit the shorter listing with a yellow notice only if independent scoped evidence establishes the omitted edition. A separately verified different model conflicts; unresolved identity stays outside pricing. [Dawlance query](https://digimall-be.faysalbank.com/storefront/search_products?storefront=23&q=9193LF&page=1&limit=18)

### 17.3 Gallon capacity conflicts in the shared matcher

The owner reported a WooCommerce listing sample for Unigas. A controlled offline comparison using the target `Unigas 50 Gallons Plus` and seller titles differing only in their quantity reproduced Tier 1 for 20, 30 and 50 on both raw and prepared paths. The extracted primary capacities were respectively `1.25T`, `2.5T` and absent. The current capacity module recognizes gallon spellings in its spec-only unit pattern. Recognition during cleanup therefore does not establish a guarded gallon quantity.

* **R2:** Bind the explicit quantity and volume unit before numeric model or implicit tonnage interpretation. Use the shared measurement vocabulary for gallon, gallons and gal. Preserve the original quantity, unit and role. Do not guess US/imperial gallon equivalence or a litre conversion from an unspecified gallon title.
* **R4/R7:** Require the 50-gallon self-match and reject explicit 20/50 and 30/50 capacity conflicts in both directions. Check singular/plural, case, spacing, unseen brands and a range against a single endpoint. Assert that gallon-bound digits cannot also supply inferred AC tonnage. Replay the owner-reported case through the shared offer path with a cheaper opposing capacity and verify its exclusion from the pricing pool. Keep adapter title and price extraction intact. Pin actual seller payloads separately from these controlled title substitutions at R0.

### 17.4 Corpus-wide fault discovery before cutover

The implementation baseline must include all three corpora below. Record their content hashes and one-based data-row locators. Run the existing engine first and preserve disagreements as findings. An old verdict is evidence of behavior, never the oracle for its own replacement.

| Corpus and offline probe on the working matcher | Finding to reproduce at R0 |
| --- | --- |
| Current Book1, first explicit KG, Cu Ft, Ton, litre/Ltr or Inch quantity per title, increase its numeric value by one and keep the model and surrounding text fixed | Of 93 matching titles, 80 produced FACET_CONFLICT and all 13 Ltr edits were accepted. Primary capacity was absent on all 13 originals. Inspect the quantity's subject on each row. The seller's microwave cavity size and a dispenser accessory volume need separate evidence roles. |
| `tests/fixtures/selected_100_stress_products.csv`, all 100 titles across nine categories, using Name and supplied Brands | Raw self-comparison gave 93 exact and seven BRAND_CONFLICT. Raw/prepared tier or reason differed on rows 2, 3 and 53. Of 68 first-quantity edits under the same probe, three were accepted: #57 changed the declared AC capacity from 1.5 to 2.5 Ton with model unchanged, #86 and #87 changed explicit microwave volume from 20 to 21 litres. Pin the originals and counterfactuals. Compare explicit evidence with implicit model-derived values before pruning either. |
| `data/inputs/sample_test_products.csv`, all 55 Name-only rows | Extraction with empty brand produced 54 nonempty anchors. Rows 1 and 2 explicitly declare 14 place settings but primary capacity was absent. Use this file for extraction, span and query tests. Evaluate brand-dependent eligibility only with separately sourced brand evidence. An anchor count alone cannot establish correctness. |

**R0–R4 procedure.** Inventory every unit or facet recognized by cleanup, extraction, retrieval, shipping or matching, including spec-only units and quantities present in the corpora. Assign evidence of its subject and role (identity constraint, ancillary spec, measurement range or unresolved). Trace each annotated span through raw and prepared paths. A protected quantity consumed by cleanup must remain accounted for. Do not promote every spec to an SKU veto. Keep primary and secondary measurements separate. Require a justified disposition for identified but unclassified roles before enabling the affected path.

For each applicable role, generate reproducible pairs from the frozen titles: original, equivalent presentation, omitted field and one changed explicit value. Also compare actual same-brand nearest catalog neighbors. Check both directions where meaningful, preserve significant digits and terminal qualifiers, and label alternative branches and secondary features before assigning expected outcomes. Generate inputs independently of the production parser so its blind spots do not disappear from test selection. Use reviewed annotations for the oracle. Record uncovered roles, skipped rows and the reason. Deduplicate overlapping examples across corpora before computing holdout metrics.

**R6–R9 release gate.** Replay changed and unchanged controls through retrieval, comparison and final offer selection. Include a cheap conflicting seller beside a valid offer to expose mistakes that reach pricing. Compare warnings, selectable variants, commission, selected reference and exported price. Block cutover on a confirmed false eligible offer, an unexplained lost eligible offer, raw/prepared disagreement affecting identity, or unexplained changes to financial output. Report denominators by role and corpus, including labels awaiting evidence. Re-run this matrix with the frozen baseline on subsequent matcher changes.

### 17.5 Design walkthrough against the supplied fixtures

These are worked decisions of the proposed algorithm. They specify intermediate evidence and expected outcomes for the first implementation. Section 17.4 separately records observations of the legacy engine. Modified candidate titles below are controlled examples, not market captures. For Name-only rows the walkthrough tests identity components; full eligibility also requires brand evidence under §5.

| Source and counterexample | Evidence the new algorithm must retain | Consequence |
| --- | --- | --- |
| Stress #57, `1.5 Ton HSU-20-HFTEX(W)`; change only 1.5 to 2.5 | Keep `20` inside the SKU and `(W)` attached. Align the two explicit AC capacities on the same subject. | Reject 1.5 vs 2.5 even when the entire SKU agrees. Moving the unchanged capacity after the SKU preserves the decision. |
| Stress #86, `HMSO-2020B Microwave Oven (20 Liters, Solo, Black)`; stress #87, `HMW-20MWS ... 20Ltr` | The first brackets contain a description, while the second title attaches the unit directly to the amount. Both explicitly describe oven volume. Keep the digits inside each SKU independent. | Changing either stated 20 to 21 conflicts. Changing only unit spacing or a supported litre spelling preserves agreement. This same rule handles storage gallons in §17.3 without a microwave or geyser condition. |
| Sample #1 and #2, different dishwasher models both stating `14 Place Settings` | Bind 14 to the count phrase; retain the two different full model observations. | Equal place count cannot rescue contradictory model codes. Changing 14 to a different explicit place count on the same model conflicts when both refer to dishwasher capacity. |
| Sample #21 and #22, `HDR-TC2C1GB-PK` vs `HDR-TC2C1GR-PK`, both 2 Tap | Preserve the differing embedded letters and shared terminal segment. Keep tap count independent. | Reject the opposed codes without guessing a color meaning for B or R. |
| Sample #23, `HWS 60-50 6 Kg`; stress #4, `DW-9200 CFL … 40–50 Clothes Capacity` | Retain the ordered numeric components of the first model and its separate 6 Kg capacity. The second has a clothes-count interval. | Hyphen handling must preserve both readings in their own context. A seller's single endpoint cannot verify the interval. |
| Sample #5 and #6, `HWM 95-1678` with and without `ES8`, both 9.5 Kg | Both spellings occur in the supplied list. Retain ES8 as observed, along with direction of omission and its evidence scope. | These two rows alone establish neither equivalence nor a known conflicting edition. Require the approved directional rule to price the omission; keep a genuinely unresolved relationship visible. |

Before switching comparison, trace each row from spans through obligations to offer eligibility. Require a source span or approved scoped fact for each deciding step. Add a held-out title with a different brand, code shape and surface spelling for every rule derived here. Use these independent expected decisions to challenge the implementation, including a seller with the lowest price and a contradicted guarded attribute.

## 18. Implementation handoff for seller options, warnings and pricing

### A seller advertises multiple models at once

Use the owner's target `HAIER HMW-20MXP3 SOLO MICROWAVE OVEN` against the seller template `HAIER SOLO MICROWAVE OVEN 20 LITRE Model {model}`. An offline raw-title referee probe gave Tier 1 without a notice for both `HMW-20MXP3` and `HMW-20MXP3/P5/P6`. Both `HMW-20MXP5` and `HMW-20MXP5/P6` returned MODEL_CONFLICT. The stored stress capture contains a single-model P3 title returned for another target. It provides no evidence about stock or pricing for the owner's grouped example.

* R3 retains the original group, its shared stem and the source span for each alternative. R4 records whether the requested P3 is explicitly represented, absent, or indeterminate. Test the same cases with reordered options, a different brand and an unrelated synthetic stem. Keep the entire `/013WDC(W)` qualifier intact in a paired negative control. A slash alone cannot trigger option expansion.
* Run the same grouped listing against three independently prepared targets. P3 and P6 each have an advertised option; P4 is absent. Assert which original span supports each positive, including P6 after the second slash. A fixed P6 target receives no choice prompt. The live Alfa result from Umar Electronics, `HMW-20MXP3 / 20MXP9` at Rs. 16,398, supplies a second shared-stem format. Keep the owner's literal P3/P5/P6 case labeled as a regression example; the API sample verified the P3/P9 listing. Preserve explicit prefix differences such as Digi's `HMN-20MXP6` until independently verified for the relevant model.
* R7 checks what the platform payload actually sells. Replay one response with P3-specific price and stock, one with only a listing-level price, and one with P3 sold out while P5 is available. Keep variant-specific values attached to their own option. With only a group price, report P3 as advertised and its individual price as unverified; pin the existing host pricing outcome in R0. Any proposal to change commercial eligibility for that case needs an owner decision before that behavior ships. A target already fixed to P3 must not prompt the operator to choose P5.

### A mixed pool must survive selection and rendering

The existing `pricing_engine/offer_processing.py::finalize_offers` returns the selected tier in `offers` and retains `base_offers` separately. Rendering only the selected list hides compatible incomplete sellers. Flattening those lists into the evaluator can change the price. Reuse the collected buckets to build the seller display and keep the existing selection path for evaluation. Deduplicate by the existing offer identity rules; preserve the decision and warnings of the actual displayed offer.

| Replay input | Observable assertion |
| --- | --- |
| In-stock exact and cheaper incomplete sellers, plus a still cheaper conflicting SKU | Display the compatible sellers once each. The omission appears only beside its seller. The exact tier supplies the pricing pool. The conflict enters neither display as a match nor pricing. |
| The exact seller is sold out; an eligible incomplete seller remains | Exercise normal fallback selection. Verify the selected seller ID, its original omitted fields, displayed yellow notice, exported reason and price against the existing evaluator. |
| One seller omits both color and qualifier, another omits only color | Render the actual missing fields once per seller. The selected reason contains only the reference seller's omissions. Reversing API arrival order preserves the result under the existing tie rules. |
| A broad query rediscovers a seller already reached by an exact query | Compare against the same prepared target, retain retrieval provenance and verify stable displayed counts and prices. Replay through both marketplaces, including the existing early-stop and partial-discovery cases. Collection applies to returned listings; it does not promise discovery of every seller on the marketplace. |

### First implementation checkpoint

1. **R0:** Freeze a single source and data snapshot. Run the three-corpus discovery procedure in §17.4. Record each §17 and §18 case with target, candidate or captured payload, old outcome, expected outcome, authority and owning slice. Label synthetic seller edits separately from historical HTTP observations. Include both accepted controls and explicit conflicts.
2. **R1–R6:** Add each case at its owning layer before changing that layer. Compare raw and prepared paths, then test the actual retrieval projection and final comparison independently. The core must work offline without an LLM, credentials or a hosted service.
3. **R8 before R7:** Pass signature and incompatible-state tests before permitting persistent reuse. During R7 replay the same captured pages through repricing and range. Compare seller visibility, selected price, warnings, variant prompts and complete exported rows against the authorized outcomes.
4. **R9–R10:** Use §16 release and rollback gates. Keep unresolved product equivalences in the evidence record. Only the affected change is held for adjudication; independent slices can proceed. Require separate adversarial review before each commit.
