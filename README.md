# Dynamic Repricing Engine

Automated, high-speed dynamic repricing pipeline for Pakistani e-commerce platforms (**AlfaMall** and **DigiMall / Faysal Bank**). It queries direct backend search APIs, cleanly drops variant mismatches and out-of-stock items, and calculates winning psychological prices under strict profit floors.

---

## Key Features

- **Direct Backend Search APIs**: High-speed JSON endpoints with `curl_cffi` (Chrome 120 impersonation) — zero browser/Selenium overhead.
- **Strict Model Matching & Variant Protection**: Prevents cross-variant mispricing (e.g. separates `12AITH21W` from `12AITH21B`, `80-186` from `80-1217`, inverter vs. non-inverter).
- **Intelligent Deduplication & Telemetry**: Collapses vendor spam into single listings while tracking duplicate counts in visual audit badges.
- **Core Logistics Math**: Automatic volumetric weight calculation and courier rate resolution with customizable per-product shipping overrides.
- **Strict Profit Floors**: Guaranteed +Rs. 500 minimum net profit floor across all platforms and commission tiers.
- **DigiMall Two-Tier Bank Switch**:
  - **Tier 1 (Default 10%)**: Competitor $\ge \text{Floor}_{10\%}$ $\rightarrow$ Undercut and win at 10% tier; bank charges 8%, capturing an extra 2% bank spread profit.
  - **Tier 2 (Emergency 8% Switch)**: Competitor below $\text{Floor}_{10\%}$ but $\ge \text{Floor}_{8\%}$ $\rightarrow$ Switch to 8% bank rate, undercut to win.
- **Psychological Price Endings**: Standard retail psychological thresholds (`.999`, `.899`, `.799`, `.499`, `.299`, `.199`, `.099`).
- **Autonomous Pattern Learner**: Dynamic search query generation with optional Supabase cloud registry synchronization.
- **Deterministic CSV Export**: Preserves input row sequencing, pure integer prices (zero `.0` float drift), and ANSI-free risk alerts.

---

## Mathematical Formulas

| Metric | Formula |
| :--- | :--- |
| **Volumetric Weight** | $\frac{\text{Length} \times \text{Width} \times \text{Height}}{5000}$ |
| **Shipping Estimate** | $\text{Volumetric Weight} \times 70.0\text{ PKR}$ |
| **Cost Base** | $\text{Net Price} + \text{Shipping Estimate}$ |
| **Alfa 10% Floor (+Rs. 500)** | $\frac{\text{Cost Base} + 500}{0.90}$ |
| **Digi 10% Floor (+Rs. 500)** | $\frac{\text{Cost Base} + 500}{0.90}$ |
| **Digi 8% Floor (+Rs. 500)** | $\frac{\text{Cost Base} + 500}{0.92}$ |
| **Monopoly Price (0 competitors)** | $\frac{\text{Cost Base} + 4000}{0.90}$ (rounded to psychological ending) |

---

## Architecture Overview

```
Pricing Script/
├── index.py                  # CLI Entrypoint script
├── pyproject.toml            # Project metadata, dependencies, lint & test configurations
├── pricing_engine/
│   ├── calculator.py         # Cost base, shipping, floors, and psychological pricing formulas
│   ├── matcher.py            # Strict model extraction, brand stripping, and candidate filtering
│   ├── scraper.py            # Unified async platform scraper (AlfaMall & DigiMall) with cache guard
│   ├── evaluator.py          # Platform-specific pricing decision engines (Alfa strict 10% & Digi two-tier)
│   ├── pipeline.py           # Concurrency orchestration, terminal cards, and CSV export
│   ├── models.py             # Strongly typed dataclasses & shared domain constants
│   ├── learner.py            # Autonomous regex pattern inference engine
│   ├── registry.py           # In-memory and Supabase pattern registry
│   └── db.py                 # Async Supabase persistence client
└── tests/                    # 137 unit, integration, and simulation test cases
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.11, 3.12, 3.14)
- Git

### Setup
```bash
# Clone the repository
git clone https://github.com/hassanwaheedali/dynamic-repricing-engine.git
cd dynamic-repricing-engine

# Install project and development dependencies
pip install -e ".[dev]"
```

---

## Usage

### Run Default Pipeline
```bash
python index.py
```
By default, reads from `Gree_Uploading_on_DigiMall_and_Price.csv` and outputs to `final_repriced_uploaded_products.csv`.

### Command-Line Arguments
```bash
python index.py --input catalog.csv --output results.csv --concurrency 5
```

| Flag | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| `-i`, `--input` | `FILE` | Input catalog CSV path | `Gree_Uploading_on_DigiMall_and_Price.csv` |
| `-o`, `--output` | `FILE` | Output repriced CSV destination | `final_repriced_uploaded_products.csv` |
| `-c`, `--concurrency` | `INT` | Max concurrent API searches | `3` |
| `-q`, `--quiet` | Flag | Suppress rich terminal audit cards | `False` |

---

## Testing & Quality Gates

Run the complete test suite:
```bash
python -m pytest -v
```

Run static analysis & code style checks:
```bash
python -m ruff check .
```

---

## License

Proprietary & Confidential. Internal e-commerce repricing engine.
