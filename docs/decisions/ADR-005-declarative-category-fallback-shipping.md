# ADR-005: Declarative Category-Based Fallback Shipping Architecture

## Status
Accepted

## Date
2026-10-26

## Context
Originally, landed cost calculations strictly required three physical box dimensions (`Length`, `Width`, `Height`) to calculate volumetric weight ($\frac{L \times W \times H}{5000}$) and estimate courier costs at Rs. 70/kg.

However, in real-world retail workflows, merchants frequently ingest raw vendor price lists (e.g. washing machines, LED TVs, refrigerators) that provide only `Brand`, `Title`, and `Net Price`, lacking explicit box dimensions. Without box dimensions, courier shipping defaulted to Rs. 0, creating severe underpricing vulnerabilities where heavy appliances (such as 15kg washing machines or refrigerators) were priced below real landed costs.

Initial attempts to solve this introduced procedural, hardcoded category branches and nested regex conditionals scattered across extraction scripts, violating the engine's strict DRY and generic dynamic design principles.

## Decision
Implement a 100% declarative, data-driven fallback shipping resolution architecture:

1. **Config-Driven Declarative Rules (`pricing_engine/config.py`)**:
   - Establish `FALLBACK_SHIPPING_TABLE` as the single source of truth for category and sub-type shipping rates.
   - Categorize appliances (e.g. `washing_machine`, `refrigerator`, `air_conditioner`, `led_tv`) with explicit capacity-band thresholds (e.g. Twin Tub, Single Tub, Fully Automatic with 8kg, 10kg, 12-15kg tiers).
   - Define canonical keywords and negative boundaries entirely inside data dictionaries, eliminating hardcoded `if/elif` logic.

2. **Generic Resolver (`pricing_engine/calculator.py`)**:
   - Expose `resolve_fallback_shipping(product_name, brand) -> tuple[float, str]`.
   - Perform generic token normalization and capacity stem extraction dynamically.
   - Fall back to declared category base defaults if specific capacity bands are unspecified.

3. **Pipeline & Exporter Integration**:
   - `resolve_shipping_estimate(product)` checks in priority order:
     1. Explicit `Shipping Estimate` from CSV.
     2. Volumetric calculation if `Length`, `Width`, `Height > 0`.
     3. Category-based fallback rate via `resolve_fallback_shipping()`.
   - Terminal audit cards display fallback badges (`[Fallback: Rs. 3,500 (Automatic Washer 10kg)]`).
   - Excel dynamic formulas (`pricing_engine/exporter.py`) preserve fallback constants instead of generating `=ROUNDUP(((0*0*0)/5000)*70, 0)` zeros.

## Alternatives Considered

### 1. Rejection of Catalogs Lacking Dimensions
- Pros: Forces data hygiene onto merchants.
- Cons: Paralyzes rapid daily price updates when suppliers do not provide box measurements.
- Rejected: Unacceptable in high-velocity e-commerce operations.

### 2. Flat Universal Fallback Rate (e.g. Rs. 2,500 for everything)
- Pros: Trivial to implement.
- Cons: Grossly inaccurate. A 32-inch LED TV courier cost is vastly lower than a 15kg twin-tub washing machine. Causes uncompetitive pricing on light goods and losses on heavy goods.
- Rejected: Mathematical accuracy is a core requirement of the engine.

## Consequences
- Catalogs with only `Brand, Title, Net Price` are ingested seamlessly without zero-shipping underpricing risks.
- Adding new categories or adjusting courier rates requires editing only `pricing_engine/config.py` without touching core math or scraping logic.
- 100% backwards compatibility preserved for catalogs with explicit dimensions.
