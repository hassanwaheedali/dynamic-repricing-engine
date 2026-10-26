# ⚡ Dynamic Repricing Engine

[![Tests](https://img.shields.io/badge/pytest-168%20passed-brightgreen.svg)](tests/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](pyproject.toml)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](pyproject.toml)
[![Status](https://img.shields.io/badge/status-active%20testing%20phase%20%28WIP%29-orange.svg)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An automated, high-speed, enterprise-grade dynamic repricing pipeline built specifically for Pakistani e-commerce platforms (**AlfaMall** and **DigiMall / Faysal Bank**). It queries direct backend search APIs, cleanly eliminates variant mismatches and out-of-stock items, calculates landed courier shipping from volumetric dimensions, and sets winning psychological prices under guaranteed net profit floors.

> ⚠️ **Project Status: Active Testing Phase (Work In Progress)**  
> **Note:** This project is currently in an **active testing and development phase** and is **not yet a finished, ready-for-market SaaS product**. While the core mathematical algorithms, variant matching, and scrapers are functional and pass 168 rigorous automated tests, the system is actively undergoing stress-testing, database integration, and UI improvements. Always review generated repricing CSVs before uploading to live merchant stores!

---

## 📖 The Story Behind This Project

> *"Hey there! I'm **Hassan Waheed Ali** ([@hassanwaheedali](https://github.com/hassanwaheedali)). While working at **KiaChahiye** ([kiachahiye.pk](https://kiachahiye.pk)), I saw firsthand how painful, exhausting, and risky manual repricing was. 
> 
> Every single morning, our team had to manually look up dozens of products on AlfaMall and DigiMall, check competitor rates, calculate courier charges based on box dimensions, compute bank commission cuts (8% vs. 10%), apply profit margins, and update spreadsheets one by one. It was taking hours of manual labor and was always vulnerable to human calculation errors or underpricing.
> 
> I initially started this as a casual personal project to shift our operations from tedious manual work to 100% automation. But as the engine evolved — with Chrome impersonation, smart variant matching, and multi-tier bank spread math — it became incredibly fast, robust, and accurate. 
> 
> Now, we are expanding this from an internal tool into a **next-level dynamic repricing SaaS engine** for multiple Pakistani and regional e-commerce marketplaces. Contributions, forks, and ideas are warmly welcomed!"*

---

## 🎯 What Does This System Do? (Yeh Kya Karta Hai)

In simple words, you give it your product catalog (like your ACs, Washing Machines, TVs, or Refrigerators), and with one command, it:

1. **Fetches Live Market Prices in Seconds**: Queries official backend JSON search endpoints directly without slow Selenium or headless browser overhead.
2. **Filters Out Junk & Variants**: Drops out-of-stock items and protects against wrong variant collisions (e.g. it strictly refuses to match a White AC `12AITH21W` against a Black AC `12AITH21B` or an 8kg washer against a 10kg washer).
3. **Calculates Real Landed Shipping**: Automatically calculates volumetric weight ($\frac{L \times W \times H}{5000}$) and courier cost per product.
4. **Guarantees Profit (+Rs. 500 Floor)**: Enforces hard mathematical floors so you **never sell at a loss** regardless of competitor price cuts.
5. **DigiMall 2-Tier Bank Switch**:
   - **Tier 1 (10% Tier)**: Undercuts competitors while enjoying extra profit margin from the 8% Faysal Bank agreement.
   - **Tier 2 (8% Emergency Switch)**: If a competitor is aggressive, switches to the 8% bank rate to win the buy box while still keeping your profit intact.
6. **Applies Psychological Pricing**: Rounds all winning prices to standard retail endings (`.999`, `.899`, `.799`, `.499`, `.299`, `.199`, `.099`).
7. **Monopoly Protection**: If you are the only seller with stock, sets an optimal profit price (+Rs. 4,000 margin) rather than leaving money on the table.
8. **Exports Clean, Upload-Ready CSVs**: Saves timestamped audit files and an always-synced `_latest.csv` ready for direct upload to merchant portals.

---

## 🏗️ Architecture Overview

The system is built as a modular async pipeline with clear boundaries:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Dynamic Repricing Engine                         │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
       1. Ingestion (`pricing_engine/ingestion.py`)
       • Scans `data/inputs/` for CSV catalogs
       • Validates 6 core columns + optional Profit
       • Normalizes S.NO, trims whitespace, renders Rich pre-flight banner
                                    │
                                    ▼
       2. Async Scraper (`pricing_engine/scraper.py`)
       • `curl_cffi` (Chrome 120 impersonation, zero IP blocks)
       • Multi-pattern waterfall search (Tier 1 exact -> Tier 2 stem -> Tier 3 permutations)
       • In-memory query cache & concurrency limit (semaphore)
                                    │
                                    ▼
       3. Matcher & Cleaner (`pricing_engine/matcher.py`)
       • Strips brand tokens and marketing fluff
       • 4-slot model extraction (Prefix, Numeric Stem, Suffix, Color/Variant)
       • Drops out-of-stock (`sold_out: true`) and cross-color mismatches
                                    │
                                    ▼
       4. Pricing & Margin Evaluator (`pricing_engine/evaluator.py`)
       • Volumetric shipping estimation: (L × W × H / 5000) × Rs. 70/kg
       • Cost base calculation: Net Price + Shipping
       • AlfaMall: Strict 10% undercutting above hard floor (+Rs. 500)
       • DigiMall: Two-Tier switch (10% standard -> 8% emergency rate)
       • Monopoly pricing (+Rs. 4,000) when zero competitors exist
       • Psychological threshold rounding (.999, .899, etc.)
                                    │
                                    ▼
       5. Exporter (`pricing_engine/exporter.py`)
       • Guaranteed Column 1 `S.NO` sequence
       • Pure integer price formatting (zero `.0` float drift)
       • Timestamped audit file: `data/outputs/{stem}_repriced_{timestamp}.csv`
       • Latest upload file: `data/outputs/{stem}_repriced_latest.csv`
       • Terminal audit cards & executive summary via Rich
```

---

## 📂 Repository File Structure

```
Pricing Script/
├── index.py                     # CLI Entrypoint (Interactive picker, Batch mode, Single file)
├── pyproject.toml               # Project metadata, dependencies, and pytest/ruff config
├── requirements.txt             # Core runtime dependencies
├── data/
│   ├── inputs/                  # Catalogs to reprice
│   │   ├── template.csv         # Clean 6+1 column starting template
│   │   ├── Gree_AC.csv          # Sample catalog
│   │   └── Haier_Washers.csv    # Sample catalog
│   └── outputs/                 # Repriced catalogs
│       ├── {name}_repriced_{timestamp}.csv  # Audit history
│       └── {name}_repriced_latest.csv       # Ready to upload
├── docs/
│   └── decisions/               # Architecture Decision Records (ADRs)
│       ├── ADR-001-multi-pattern-waterfall-candidate-retrieval.md
│       ├── ADR-002-four-slot-attribute-extraction-and-negative-collision.md
│       ├── ADR-003-autonomous-cooccurrence-learning-and-cloud-sync.md
│       └── ADR-004-catalog-ingestion-and-timestamped-export.md
├── pricing_engine/
│   ├── ingestion.py             # CSV catalog validator and pre-flight audit reporter
│   ├── exporter.py              # Timestamped output manager & pure-integer formatter
│   ├── pipeline.py              # Async execution pipeline, concurrency & UI cards
│   ├── calculator.py            # Cost base, shipping, and profit floor formulas
│   ├── matcher.py               # Fuzzy-resistant SKU model extraction & variant protection
│   ├── scraper.py               # Fast async JSON scraper for AlfaMall & DigiMall
│   ├── evaluator.py             # Buy-box winning logic & 2-tier bank commission switch
│   ├── models.py                # Strongly typed dataclasses
│   ├── learner.py               # Autonomous search query pattern learner
│   ├── registry.py              # Pattern registry (in-memory + Supabase)
│   └── db.py                    # Async Supabase persistence client
└── tests/                       # 168 comprehensive unit, simulation & resilience tests
    ├── fixtures/                # Benchmark test datasets
    ├── test_ingestion.py        # Ingestion tests
    ├── test_exporter.py         # Exporter tests
    ├── test_pipeline_resilience.py # S.NO permutations & edge-case tests
    ├── test_cli.py              # CLI interactive & batch mode tests
    └── ...
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/hassanwaheedali/dynamic-repricing-engine.git
cd dynamic-repricing-engine

# Create and activate virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies in editable mode with development tools
pip install -e ".[dev]"
```

### 3. Add Your Products
Drop your catalog CSV file into the `data/inputs/` directory.

You can use the built-in [data/inputs/template.csv](data/inputs/template.csv) as a reference:

```csv
Brand,Name,Net Price,Length,Width,Height,Profit
Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92,
Haier,Haier HW 90-BP12357S8 Front Load Washing Machine,130000,65,56,92,1000
```

| Column | Required? | Description | Example |
|---|---|---|---|
| `Brand` | **Yes** | Manufacturer name | `Gree`, `Haier`, `Dawlance` |
| `Name` | **Yes** | Full product title | `GREE SPLIT AC 12AITH21W-T3` |
| `Net Price` | **Yes** | Wholesale purchase cost in PKR | `147000` |
| `Length` | **Yes** | Box length in cm | `87` |
| `Width` | **Yes** | Box width in cm | `35.5` |
| `Height` | **Yes** | Box height in cm | `92` |
| `Profit` | Optional | Custom profit target in PKR (Default: `500`) | `1000` |
| `S.NO` / `S.No` | Optional | Serial/SKU number (Auto-generated 1, 2... if omitted) | `101`, `SKU-01` |

> Any additional columns (e.g. `Supplier`, `Color`, `Warranty`) are automatically preserved without distortion.

### 4. Run the Engine

#### Option A: Interactive Picker (Easiest)
Just type:
```bash
python index.py
```
If multiple CSV files are present in `data/inputs/`, a rich interactive terminal menu appears letting you choose which catalog to reprice with a single keystroke.

#### Option B: Process All Catalogs in Batch
To reprice all files in `data/inputs/` one after another:
```bash
python index.py --batch
# or
python index.py -a
```

#### Option C: Specific File Run
```bash
python index.py -i data/inputs/Gree_AC.csv
```

#### Option D: Run for AlfaMall Only (or DigiMall Only)
Skip DigiMall scraping to run faster and reprice exclusively for AlfaMall:
```bash
python index.py -i data/inputs/Gree_AC.csv --alfa-only
# or
python index.py -i data/inputs/Gree_AC.csv -p alfa
```
To run for DigiMall only:
```bash
python index.py -i data/inputs/Gree_AC.csv --digi-only
# or
python index.py -i data/inputs/Gree_AC.csv -p digi
```

#### Option E: Background / Cron Mode (Legacy)
```bash
python index.py -i input.csv -o output.csv --concurrency 5 --quiet
```

---

## 📊 Core Pricing Formulas & Math

### 1. Landed Cost Base
$$\text{Volumetric Weight (KG)} = \frac{\text{Length} \times \text{Width} \times \text{Height}}{5000}$$
$$\text{Shipping Estimate (PKR)} = \text{Volumetric Weight} \times 70.0\text{ PKR/KG}$$
$$\text{Cost Base} = \text{Net Price} + \text{Shipping Estimate}$$

### 2. Hard Profit Floors (+Rs. 500 Guarantee)
- **AlfaMall (10% Commission)**:
  $$\text{Floor}_{\text{Alfa}} = \frac{\text{Cost Base} + 500}{0.90}$$
- **DigiMall Standard (10% Tier)**:
  $$\text{Floor}_{\text{Digi\_10}} = \frac{\text{Cost Base} + 500}{0.90}$$
- **DigiMall Emergency (8% Faysal Bank Rate)**:
  $$\text{Floor}_{\text{Digi\_8}} = \frac{\text{Cost Base} + 500}{0.92}$$

### 3. Winning Undercut Rules
- **Winning Condition**: $\text{Floor} \le \text{Our Price} < \text{Lowest Viable Competitor}$.
- **Psychological Rounding**: If undercut yields `72,877` and floor is `72,500`, engine rounds to `72,799` or `72,899`.
- **Monopoly Pricing**: If zero valid competitors exist in the market, pricing sets:
  $$\text{Monopoly Price} = \frac{\text{Cost Base} + 4000}{0.90}$$
  (rounded to psychological ending) to capture optimal margin.

---

## 🧪 Testing & Quality Standards

The engine is engineered under strict **Test-Driven Development (TDD)** discipline:

```bash
# Run all 168 automated tests
pytest

# Run with verbose output
pytest -v

# Run static analysis and linting
ruff check .
```

All 168 tests pass with 100% green status across:
- **Resilience**: Casing variations (`S.NO`, `S.No`, `sno`), alphanumeric serials, NaN fallbacks, and `.0` float drift elimination.
- **Simulation**: Replays historical live catalog benchmarks (Gree, Haier, Stock Holding reports).
- **Calculations**: Verifies mathematical floors, psychological roundings, and shipping cost lookups.
- **CLI & I/O**: Validates folder scanning, tty interactive checks, and batch recovery.

---

## 🗺️ Roadmap: The Journey to a Full SaaS

- [x] **Phase 1: Robust Input/Output & Resilient CLI** (Completed)
  - Dynamic `data/inputs/` ingestion and 6-column clean template.
  - Timestamped + latest copy export with pure integer formatting.
  - Interactive terminal picker + resilient batch processing.
  - Complete test isolation in `tests/fixtures/`.
- [ ] **Phase 2: Supabase Price History & Terminal Search** (In Progress)
  - Historical database storage (`repricing_runs` and `repricing_results`).
  - Terminal history query subcommands (`python index.py history --latest / --model / --date / --profit-below`).
  - Graceful fallback when offline or without credentials.
- [ ] **Phase 3: Multi-Platform Expansion**
  - Adapters for **Daraz PK**, **PriceOye**, **Telemart**, and **iShopping**.
  - Dynamic proxy rotation & captcha telemetry.
- [ ] **Phase 4: Cloud SaaS & Web Dashboard**
  - FastAPI backend with Next.js dashboard.
  - Automated hourly/daily cron repricing workers.
  - Automated stock synchronization and email/SMS alerts when competitors drop below floor.

---

## 🤝 Contributing & Forking

Contributions are what make the open-source community an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**!

1. **Fork the Project**
2. **Create your Feature Branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit your Changes** (`git commit -m 'feat: add some amazing feature'`)
4. **Run Tests & Linting** (`pytest && ruff check .`)
5. **Push to the Branch** (`git push origin feature/AmazingFeature`)
6. **Open a Pull Request**

---

## 👨‍💻 Author & Maintainer

**Hassan Waheed Ali**
- GitHub: [@hassanwaheedali](https://github.com/hassanwaheedali)
- Background: E-Commerce Operations & Automation (built originally at KiaChahiye)

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.


## Market Range Mode (`--range-only`)

Give only a model list (`Brand`, `Name`) and get the market **Min / Max** price on AlfaMall and DigiMall. No cost math, no floors, no final price.

```bash
python index.py -r -i data/inputs/models.csv      # or: --range-only
python index.py                                   # interactive: pick mode [2] Market Range Only
```

- **Min / Max**: lowest / highest in-stock price any vendor lists for the same strictly-matched model (sold-out offers ignored, no profit-floor filter).
- **Full search**: the scraper queries every tier and merges results, so Max is not understated.
- **Columns**: same layout as the repricing output. Cost, Final Price, Profit and Reason columns are blank. Two extra columns, `Alfa Offers Found` / `Digi Offers Found`, sit between `Maximum Price Digi` and `Final Price Alfa`. Risk alerts stay the last two columns: `NONE`, `NO_OFFERS` (empty market) or `SERVER_DOWN`.
- **Output**: `data/outputs/range/csv/` and `data/outputs/range/xlsx/` (`{stem}_range_{timestamp}` + `{stem}_range_latest`). If the latest XLSX is open in Excel, the timestamped copy is still saved and a warning is shown.
- Requires `openpyxl` (in `requirements.txt`).
