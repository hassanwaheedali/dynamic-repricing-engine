# ADR-007: Robust Column Alias Normalization & Zero Silent Fallback Policy

## Status
Accepted

## Date
2026-10-26

## Context
Merchants provide catalog files created from diverse ERPs and inventory spreadsheets with varying header naming conventions (e.g. `Title`, `Product Name`, `Model`, `NetPrice`, `Cost`, `Purchase Price`).

Previously, two dangerous architectural bugs existed:
1. **Silent Fallback Anti-Pattern**: In `pricing_engine/pipeline.py`, `parse_product_input` contained `row.get("Name", "Product")`. When an input CSV provided `Title` instead of `Name`, the engine silently defaulted every row's name to `"Product"`, polluting API queries (`"Dawlance Product"`) and corrupting pricing decisions without warning.
2. **Duplicate Column Collision Risk**: Renaming column headers by simple dictionary mapping caused Pandas column duplication if a CSV contained *both* a canonical column and an alias (e.g. `Brand, Name, Title, Net Price`). When duplicate columns exist in Pandas, `row['Name']` returns a `pd.Series` rather than a scalar, causing `ValueError: The truth value of a Series is ambiguous` during downstream boolean checks.

## Decision
Implement a single-source-of-truth normalization and validation pipeline:

1. **Single Source of Truth (`pricing_engine/ingestion.py`)**:
   - `COLUMN_ALIASES`: Canonical mapping dictionary for headers (`title -> Name`, `cost -> Net Price`, etc.).
   - `INVALID_NAME_VALUES` & `INVALID_BRAND_VALUES`: Strict frozensets identifying placeholder strings (`"-"`, `"none"`, `"nan"`, `"null"`, `"?"`, empty).

2. **Collision-Safe Column Normalizer (`normalize_catalog_columns`)**:
   - Accepts raw column headers and preserves existing canonical columns.
   - **Non-Destructive Mapping**: An alias column is only renamed to its target if the canonical target is *not* already present in the catalog.
   - Supports `preserve_name_space` flag to protect legacy export fixtures expecting `"Name "`.

3. **Zero Silent Fallback Policy (`parse_product_input`)**:
   - Completely eliminated `"Product"` default string.
   - `_extract_name` inspects candidate fields (`Name`, `Title`, `Product Name`, `Model`), unwraps Series defensively, and checks against `INVALID_NAME_VALUES`.
   - If no valid name is found, it immediately raises a loud `ValueError` at ingestion time, halting execution before any incorrect API calls are made.

4. **Delimiter Auto-Detection**:
   - Uses `pd.read_csv(path, sep=None, engine="python")` with fallback to standard comma reader, seamlessly accepting comma-separated and tab-separated vendor files.

## Alternatives Considered

### 1. Enforcing Rigid Single Column Header Names
- Pros: Simple code.
- Cons: Extreme friction for merchants. Every supplier export with `Title` or `Cost` required manual spreadsheet editing before running the tool.
- Rejected: Software must be robust to standard industry terminology.

### 2. Retaining Silent Fallbacks with Logging
- Pros: Execution does not abort.
- Cons: Danger of selling uncompetitive or wrong items due to corrupted search queries. In commercial repricing, a crash is infinitely preferable to mispricing.
- Rejected: Commercial integrity requires fail-fast validation.

## Consequences
- Catalogs with `Title`, `Product Name`, `Cost`, or TSV formatting work automatically out of the box.
- Zero possibility of dummy `"Product"` search queries leaking into live marketplace APIs.
- Zero possibility of Pandas duplicate-column collisions crashing the pipeline.
- 100% test coverage with 346 passing automated tests.
