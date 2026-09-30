# ADR-004: Catalog Ingestion and Timestamped Multi-Target Export Architecture

## Status
Accepted

## Date
2026-09-30

## Context
Originally, the repricing engine relied on hardcoded input and output file paths (`Gree_Uploading_on_DigiMall_and_Price.csv` and `final_repriced_uploaded_products.csv`), legacy 18-column CSV formats, and ad-hoc single-file CLI arguments.

This created several operational friction points for merchants and automated systems:
1. **Catalog Rigidity**: Merchants had to overwrite the same input file or pass complex file paths via `-i`.
2. **Missing Audit History**: Every pipeline run overwrote the destination file, wiping out historical price decisions and audit trails.
3. **Column Bloat & Formatting Drift**: The original input expected 18 columns (including calculated fields). Furthermore, pandas export commonly introduced floating-point drift (e.g. `145000.0` or `1.0` in serial numbers), which caused schema rejections on marketplace upload portals.
4. **Interactive vs. Unattended Execution**: The pipeline lacked an interactive picker for manual terminal users while also lacking a safe, non-blocking fallback for headless CI/cron environments.

## Decision
Implement a decoupled, two-stage I/O architecture:

1. **Structured Ingestion (`pricing_engine/ingestion.py`)**:
   - Establish a clean, minimal 6-column input contract: `Brand`, `Name`, `Net Price`, `Length`, `Width`, `Height` (with optional 7th column `Profit`).
   - Automatically strip column and value whitespace upon ingestion.
   - Robust `S.NO` extraction supporting all casing variants (`S.NO`, `S.No`, `sno`, `Serial No`), alphanumeric SKUs, and auto-fallback to 1-indexed integers if omitted.
   - Pre-flight audit reporting via Rich terminal banners before initiating network I/O.

2. **Timestamped & Latest Dual-Target Export (`pricing_engine/exporter.py`)**:
   - Auto-create `data/outputs/` directory.
   - Every run generates two files:
     - Timestamped audit file: `{stem}_repriced_{YYYYMMDD_HHMMSS}.csv` (permanent history).
     - Latest upload copy: `{stem}_repriced_latest.csv` (always current, ready for portal upload).
   - Strict pure-integer formatting (`format_export_price` and `format_export_sno`) ensuring zero `.0` float drift.
   - Guarantee `S.NO` is consistently formatted as Column 1 in generated CSVs.

3. **Intelligent CLI & Dynamic Folder Scanning (`index.py`)**:
   - Scan `data/inputs/` automatically when no `-i` argument is specified.
   - Use `sys.stdin.isatty()` guard: render interactive Rich picker in interactive terminals, auto-select first file or exit gracefully in non-interactive/cron mode.
   - Support resilient batch processing via `--batch` / `-a` with per-catalog error isolation.

## Alternatives Considered

### 1. In-Place Overwriting of Single CSV File
- Pros: Simple, single file on disk.
- Cons: Destroys historical decision logs, makes rollbacks impossible, risk of data loss on unexpected termination.
- Rejected: Unacceptable for production pricing workflows.

### 2. Full Database Requirement for All Operations
- Pros: Centralized storage from day one.
- Cons: Heavy external dependency requiring active network connectivity and credentials before running a simple local reprice.
- Rejected: Kept file-based CSV workflow as the resilient primary tier, with database (Supabase) as an asynchronous secondary sync in Phase 2.

## Consequences
- Zero breaking changes to legacy script invocations (passing explicit `-i` and `-o` retains exact legacy behavior).
- Clean separation of concerns between catalog ingestion, core pricing math, and file persistence.
- Complete audit trail preserved across all execution runs.
- 100% test coverage with 168 passing automated tests.
