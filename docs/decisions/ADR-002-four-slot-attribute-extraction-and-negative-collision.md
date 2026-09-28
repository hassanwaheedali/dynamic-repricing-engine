# ADR-002: 4-Slot Structural Attribute Extraction and Negative Collision Matching

## Status
Accepted

## Date
2026-09-28

## Context
Matching scraped marketplace titles against catalog targets previously relied on expanding lists of regex rules and hardcoded keywords (`GC`, `GT`, `JT`, `WB`, `GB`). This approach violates the DRY principle and creates severe maintainability problems:
- Brand marketing departments constantly invent new series names (`MAGNA`, `AVANTE`, `FAIRY`, `PULAR`, `ULTRON`, `AIRY`).
- Cosmetic modifiers (`Glass Door`, `Pillow Drum`, `GC`) are not fixed.
- Overly strict keyword whitelists cause false monopolies, while overly permissive regexes cause catastrophic variant collisions (e.g. matching single-tub `80-1217WB` with twin-tub `80-1217GB`, or non-T3 with T3).

## Decision
Replace ad-hoc regex matching with a **4-Slot Structural Attribute Extractor** and a **Negative Collision Referee Matcher**:

### 1. The 4-Slot Extraction Model
Every catalog target and scraped listing is factored into four orthogonal slots:
1. **Anchor Slot (Core Identity)**: The invariant numeric or alphanumeric model run (`120-826S6`, `276EBS`, `12AITH21`, `S80EUX`).
2. **Series Name via Residual Subtraction**:
   - Rather than maintaining an exhaustive series dictionary, the system subtracts known closed-domain sets:
     $$\text{Series} = \text{Clean Title} - (\text{Brand} \cup \text{Category} \cup \text{Specs/Capacities} \cup \text{Root Colors})$$
   - Example: `DAW SPLIT AC MAGNA T3 INVERTER 30 MILKY`
     Subtract `DAW` (Brand), `SPLIT AC` (Category), `INVERTER` (Tech), `T3` (Spec), `30` (Capacity), `MILKY` (Color) $\rightarrow$ Remaining token = **`MAGNA`**.
3. **Guarded Facets (Zero-Tolerance Collision Attributes)**:
   - **T3 / Compressor**: Non-T3 target strictly rejects T3 listings (preventing mispricing a basic unit against a premium tropicalized compressor) and vice-versa.
   - **Capacity / Screen Size**: 12KG vs 10KG, 1.5 Ton vs 1.0 Ton, 50" vs 43".
   - **Hardware Tub/Series Letters**: `WB` vs `GB` (Single vs Twin tub).
   - **Dominant Colors & Family Normalization**:
     - `White Family`: `WHITE`, `MILKY`, `MILKY WHITE`, `PEARL WHITE`, `IVORY` (Suffix Code: `W`)
     - `Black Family`: `BLACK`, `DARK`, `MIDNIGHT`, `PIANO BLACK`, `MATTE BLACK` (Suffix Code: `B`, `D`)
     - `Grey / Silver Family`: `GREY`, `GRAY`, `SILVER`, `METALLIC`, `DARK METALLIC`, `STEEL`, `STAINLESS STEEL`, `S.S`, `TITANIUM`, `GRAPHITE`, `CHROME`, `PLATINUM` (Suffix Code: `S`, `G`)
     - `Red / Maroon Family`: `RED`, `MAROON`, `BURGUNDY`, `RUBY`, `CRIMSON` (Suffix Code: `R`)
     - `Gold / Bronze / Copper Family`: `GOLD`, `ROSE GOLD`, `CHAMPAGNE`, `BRONZE`, `COPPER`, `CLASSIC GOLD`
     - `Brown / Wood Family`: `BROWN`, `CHOCOLATE`, `WOOD`, `WALNUT`, `TEAK`
     - `Blue Family`: `BLUE`, `NAVY`, `ROYAL BLUE`, `SKY BLUE`
     - `Green Family`: `GREEN`, `EMERALD`, `OLIVE`
     - `Purple Family`: `PURPLE`, `VIOLET`, `PINK` (Suffix Code: `P`)
     - Rule: Colors within the same family (e.g. `SILVER` and `DARK METALLIC`, or `WHITE` and `MILKY`) are compatible aliases; cross-family differences (e.g. `WHITE` vs `BLACK`, `RED` vs `SILVER`) trigger hard collision rejection.
4. **Soft Residual Modifiers (Cosmetic Noise & Synonyms)**:
   - Tokens that do not alter physical machine specs (`GC`, `Glass Door`, `Top Load`, `Pillow Drum`).

### 2. The Negative Collision Referee Principle
A candidate offer is evaluated like a human expert:
$$\text{Decision} = \text{Anchor Match} \land \neg(\text{Any Guarded Facet Collision})$$
- If the Core Anchor matches and there are **zero contradictions** in Guarded Facets, the offer is accepted.
- Soft residuals are ignored during matching and passed to the self-learning miner.

## Alternatives Considered

### 1. Manual Keyword Dictionaries (Hardcoding series and cosmetic tags)
- Pros: Simple to write for 5 known models.
- Cons: Violates DRY; completely fragile when new models launch; requires endless code changes.
- Rejected: Unmaintainable for production scale.

### 2. Pure Semantic Embeddings (Vector search via LLM embeddings)
- Pros: Captures semantic synonyms easily.
- Cons: High latency (>50ms per pair), expensive API calls, and notoriously prone to confusing `12AITH21W` with `12AITH21B` (embeddings consider them 99% identical despite being different physical SKUs).
- Rejected: Fails hard-variant isolation requirements.

## Consequences
- Zero dictionaries required for brand series (`MAGNA`, `AVANTE`, `FAIRY` self-extract).
- Hard variants (`WB` vs `GB`, `T3` vs non-T3, `12KG` vs `10KG`) are 100% collision-proof.
- Code is clean, maintainable, and adheres to the DRY principle.
