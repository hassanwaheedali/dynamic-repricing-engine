# Research Notes: Universal Dynamic Product Matching & De-duplication Engine

**Date:** 2026-10-01  
**Author:** Software Architect (Data Deduplication & Fuzzy Matching Systems)  
**Methodology:** RIPER Framework — Phase 1 (Research)  
**Subject:** Zero-Dictionary / Pure DRY Dynamic Search Generation, Deduplication, and Negative Collision Matching for Pakistani E-Commerce Platforms (AlfaMall & DigiMall)

---

## 1. Executive Summary & Problem Diagnosis

The current matching system in `pricing_engine/matcher.py` operates using a hybrid of regex patterns and **hardcoded static dictionaries/lists**:
- `COLOR_FAMILIES`: Static dictionary mapping 9 color families to lists of English color words.
- `COLOR_SUFFIX_MAP`: Static mapping of single letters to color families.
- `UNIVERSAL_CAPACITY_TO_TONNAGE` & `DAWLANCE_CAPACITY_TO_TONNAGE`: Static maps of cooling codes to tonnages.
- `BRAND_CAPACITY_SYSTEMS`: Static map of brand prefixes to capacity maps.
- `CATEGORY_PATTERNS`: Massive static regex of hardcoded product categories (`AIR CONDITIONER`, `WASHING MACHINE`, `AIR FRYER`, `MICROWAVE`, etc.).
- `NON_SKU_TOKENS`: Hardcoded stop-word set (`TON`, `KG`, `LTR`, `DOOR`, `AIR`, `WASHER`, etc.).
- `MARKETPLACE_NOISE_RE`: Hardcoded list of seller names (`ELECTROEASE`, `HOMECART`) and promo words (`ON INSTALLMENT`, `0% MARKUP`).
- `GENUINE_SUB_SERIES_TOKENS`: Hardcoded set of sub-series tags (`PRO`, `PLUS`, `MAX`, `ULTRA`).

### The Fundamental Flaw of Static Dictionaries
Static dictionaries represent an **anti-pattern** in dynamic repricing:
1. **Zero Extensibility**: Whenever a new seller (`Daraz`, `Telemart`, `QistBazaar`, `NewSeller99`), a new brand (`Haier`, `TCL`, `Samsung`, `EcoStar`), or a new category (`Dehumidifier`, `Solar Inverter`, `Air Fryer`, `Hand Blender`) enters the market, the code breaks unless an engineer manually updates the static dictionary.
2. **Brittle Collisions**: Hardcoding category words like `HD` (High Definition) causes `24 HD/Z W` to be corrupted into `/Z 24` because `HD` is stripped as a TV category!
3. **Variant Blindness**: When sellers list slash-separated twin models (`TIFG1U1/TIFB1U1` or `25MXP8 / 25MXP9`) or omit manufacturer prefixes (`11lf` instead of `HRF-11LF`, `13hfn` instead of `HSU-13HFN`), static query generators fail to search the correct permutations.

---

## 2. Empirical Failure Analysis of 25 Haier SOLO Products

Through live API queries against AlfaMall and DigiMall, we identified 7 distinct structural failure modes across the 25 Haier products:

| No. | Target Product | Root Cause Failure Mode | Real Marketplace Listing | Why Current Engine Fails |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `11lf` | **Omitted Brand/Category Prefix** | `Haier HRF-11LF Refrigerator` | Catalog gives bare stem `11lf`. Engine only queries `Haier 11lf`, never generating the category prefix `HRF-11LF`. |
| 2 | `13hfn` | **Omitted HVAC Prefix** | `Haier HSU-13HFN 1.0 Ton AC` | Catalog gives bare stem `13hfn`. Engine never generates `HSU-13HFN`. |
| 3 | `Solar hybrid 1.5ton` | **Multi-Word HVAC Descriptive Series** | `Haier Solar Hybrid-III(OW) 1.5 Ton AC` | `1.5ton` mapped to `18`, but query `Haier Solar 18` misses sellers who list `Haier Solar Hybrid 1.5 Ton`. |
| 4 | `Solar hybrid 2ton` | **Multi-Word HVAC Descriptive Series** | `Haier AC 2 Ton Solar Hybrid T3 Plus` | Query `Haier Solar 24` misses sellers listing `Haier Solar Hybrid 2 Ton`. |
| 5 | `24 HD/Z W` | **Category Collision Corruption** | `Haier 2 Ton Inverter AC 24HDZ (White)` | `HD` stripped by `CATEGORY_PATTERNS` (treated as High Definition TV), turning query into `Haier /Z 24`. |
| 6 | `24 HDZ UV` | **Feature Suffix Isolation** | `Haier 2 Ton Inverter 24 HDZ with UV` | `UV` treated as unknown residual; capacity `24` decoupled improperly. |
| 7 | `24 HE/DC` | **Slash False-Alternative Split** | `Haier HBU-24 HE/DC Cassette AC` | Engine treated `HE/DC` as slash series alternative (`HE` OR `DC`), dropping `DC`. |
| 8 | `48 CE/DC` | **Slash False-Alternative Split** | `Haier HPU-48 CEO3 / CE/DC Floor AC` | Engine treated `CE/DC` as `CE` OR `DC`, dropping `DC`. |
| 9 | `48 EDC` | **Form-Factor Prefix Omission** | `Haier HPU-48 EDC Commercial AC` | Engine queried `Haier 48 EDC`, missing commercial form-factor prefix `HPU-`. |
| 10 | `Cassette 18 HE/DC` | **Category + Slash Code** | `Haier 1.5 Ton Cassette HBU-18 HE/DC` | `Cassette` stripped as category; `HE/DC` split; form-factor `HBU-` omitted. |
| 11 | `Cassette 24 HE/DC` | **Category + Slash Code** | `Haier 2 Ton Cassette HBU-24 HE/DC` | Same as above. |
| 12 | `Cassette 48 HE/DC COOL ONLY` | **Operation Descriptor Guard** | `Haier 4 Ton Cassette HPU-48 HE/DC Cool Only` | `COOL ONLY` treated as unmatched extra token, rejecting valid listings. |
| 13 | `Cassette 48 HE/DC H & C` | **Operation Descriptor Guard** | `Haier 4 Ton Cassette HPU-48 HE/DC Heat And Cool` | `H & C` not normalized; failed matching against `Heat and Cool`. |
| 14 | `HRF-418 TIFG1U1/TIFB1U1 (IOT)` | **Cartesian Slash SKU + IoT** | `Haier HRF-418 TIFG1U1 IOT Refrigerator` | Seller lists EITHER `TIFG1U1` OR `TIFB1U1`. Referee required candidate to have BOTH tokens! |
| 15 | `HRF-458 TIFG1U1/TIFB1U1 (IOT)` | **Cartesian Slash SKU + IoT** | `Haier HRF-458 IPGA/IPRA Smart Inverter` | Same Cartesian slash requirement failure. |
| 16 | `HRF-538 TIFG1U1/TIFB1U1 (IOT)` | **Cartesian Slash SKU + IoT** | `Haier HRF-538 IOT Refrigerator` | Same Cartesian slash requirement failure. |
| 17 | `HRF-578 TGGU1 (IOT)` | **IoT Token Asymmetry** | `Haier HRF-578-TGGU1-IOT Inverter` | Trailing `(IOT)` in parentheses was stripped or collided as a sub-series. |
| 18 | `HRF-585SFFGU1` | **Glued Multi-Facet Code** | `Haier Refrigerator HRF-585 SFFGU1` | `585` + `SFFGU1` unspaced, failing token-based set matching. |
| 19 | `HWM-130-688S3` | **Sub-Variant Minor Rejection** | `Haier HWM-130-688S8 / HWM 130-688` | Minor revision `S3` vs `S8` treated as hard rejection despite being the exact same tub/capacity chassis. |
| 20 | `32" D2` | **Punctuation & Quote Entity Leak** | `Haier 32" Smart LED TV D2` | Quote `"` corrupted capacity extraction (`Cap: None`), missing `32INCH`. |
| 21 | `HGL-25MXP8 / 25MXP9` | **Dual Model Slash Alternative** | `Haier Microwave HMW-25MXP9` | Engine only searched `25MXP8`, completely ignoring `25MXP9`! |
| 22 | `HMO-45200` | **Form Factor Acronym Drift** | `Haier Microwave HMN-45200 / HMW-45200` | Catalog wrote `HMO-45200` (Haier Microwave Oven). Real portal listings use `HMN-45200` or `45200`. |
| 23 | `HMO-62 MX80` | **Spaced Compound SKU** | `Haier Solo Microwave HMN-62MX80` | Space between `62` and `MX80` caused split tokens that failed anchor search. |
| 24 | `HAF 50 MB` | **Capacity + Variant Tag Drift** | `Haier HAF-50MB 5L Air Fryer` | Query `Haier HAF` was too broad; missed hyphenated `HAF-50MB`. |
| 25 | `HAF 50 DB` | **Capacity + Variant Tag Drift** | `HAIER HAF 50DB DIGITAL AIR FRYER` | Query `Haier HAF` missed specific `50DB` model. |

---

## 3. Structural Decomposition Analysis: What Is a Product Identity?

Without static dictionaries, what mathematically constitutes a product listing?
Every e-commerce listing in consumer appliances and electronics can be represented as an **Orthogonal 5-Tuple**:

$$\text{Product} = \langle \mathcal{B}, \mathcal{S}_{\text{stem}}, \mathcal{C}_{\text{capacity}}, \mathcal{F}_{\text{facets}}, \mathcal{V}_{\text{variant}} \rangle$$

1. **Brand ($\mathcal{B}$)**: Provided directly by the catalog input contract (`Haier`, `Dawlance`, `Gree`). Zero guessing needed.
2. **Numeric Stem ($\mathcal{S}_{\text{stem}}$)**: The core numeric invariant run ($\ge 2$ digits, e.g. `418`, `538`, `11467`, `130-688`, `45200`, `25`, `30`, `50`).
3. **Prefix / Form Factor ($\mathcal{P}$)**: 2 to 4 letters immediately preceding or glued to the stem (`HRF`, `HWM`, `HSU`, `HBU`, `HPU`, `HMN`, `HAF`, `DWT`, `DMB`).
4. **Capacity ($\mathcal{C}_{\text{capacity}}$)**: Extracted by dynamic unit/number detection (`1.5 Ton`, `13 Kg`, `50 Inch`, `25 Litre`).
5. **Guarded Facets ($\mathcal{F}_{\text{facets}}$)**:
   - **T3**: Compressors rated for high ambient temperature ($52^\circ\text{C}$).
   - **IoT**: Smart connected appliances.
   - **Tub Finish**: `WB` (white/plastic lid) vs `GB` (glass lid).
   - **Door Finish**: `GD` (glass door) vs `INOX` (metallic/stainless).
6. **Variant / Suffix ($\mathcal{V}_{\text{variant}}$)**: Short 1-4 char alpha codes designating cosmetic trims or colors (`TIFG1U1`, `MB`, `DB`, `ES`, `W`, `S`).

---

## 4. Key Takeaways for Innovation Phase

1. **Zero Dictionaries**: Category, color, and noise detection must NOT rely on static Python lists (`["WHITE", "BLACK"]` or `["AIR CONDITIONER", "WASHING MACHINE"]`).
2. **Universal Prefix Extraction**: The prefix must be derived dynamically from `{BrandInitial}[A-Za-z]{1,3}` or word boundaries adjacent to numeric stems.
3. **Cartesian Slash Decomposition**: Any title containing slashes (`/`) in the model token (e.g. `TIFG1U1/TIFB1U1`, `HGL-25MXP8 / 25MXP9`, `Sprinter / Powercon`) must be dynamically factored into an **OR lattice** of search queries and matching candidates.
4. **Information Density & Dynamic Noise Filtration**: Marketplace noise (sellers, installments, promos) occurs predominantly in **trailing positions**, after delimiters (`-`, `|`, `(`, `/`), or as merchant patterns (`[A-Z]{2,4}-\d+`). Filtering them must be algorithmic and positional, not lexical.
