# Implementation Plan: Input & Option Grouped Output Structure (with `csv/` & `xlsx/` subfolders)

## Overview
Restructure the dynamic repricing pipeline's output layout to group outputs first by input catalog name beside the input file, then by option subfolder (`option_1/`, `option_2/`, `option_3/`), with dedicated `csv/` and `xlsx/` subfolders inside each option.

## Target Directory Tree
```
data/inputs/
├── wm.csv
└── wm/
    ├── option_1/
    │   ├── csv/
    │   └── xlsx/
    ├── option_2/
    │   ├── csv/
    │   └── xlsx/
    └── option_3/
        ├── csv/
        └── xlsx/
```

## Task List

### Phase 1: Foundation (`pricing_engine/exporter.py`)
- [ ] Implement `resolve_option_output_dir(input_path, option)`
- [ ] Update `export_results` to separate outputs into `csv/` and `xlsx/`
- [ ] Update `export_winning_5pct_results` to separate outputs into `csv/` and `xlsx/`
- [ ] Ensure `export_range_results` outputs to `csv/` and `xlsx/`
- [ ] Update unit tests in `tests/test_exporter.py`

### Phase 2: Pipeline Integration (`pricing_engine/pipeline.py` & `range_pipeline.py`)
- [ ] Wire `run_pipeline` (Option 1 & Option 3) to use `resolve_option_output_dir` when `export_dir is None`
- [ ] Wire `run_range_pipeline` (Option 2) to use `resolve_option_output_dir` when `export_dir is None`

### Phase 3: CLI & Safeguards (`index.py`)
- [ ] Update `index.py` CLI invocation
- [ ] Guard `find_input_catalogs` to ensure subfolders in `data/inputs/` are never re-ingested as catalogs

### Phase 4: Verification & End-to-End Testing
- [ ] Run full test suite (`pytest`)
- [ ] Run live pipeline on `data/inputs/wm.csv` for Option 1, Option 2, and Option 3
- [ ] Verify directory structure and non-overwrite timestamping
