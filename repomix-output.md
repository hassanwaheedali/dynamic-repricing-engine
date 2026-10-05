This file is a merged representation of the entire codebase, combined into a single document by Repomix.

# File Summary

## Purpose
This file contains a packed representation of the entire repository's contents.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Files are sorted by Git change count (files with more changes are at the bottom)

# Directory Structure
````
.github/
  workflows/
    ci.yml
data/
  inputs/
    .gitkeep
    Dawlance_Products_List.csv
    Gree_AC.csv
    Haier_Products_List.csv
    Haier_Washers.csv
    template.csv
  outputs/
    .gitkeep
docs/
  decisions/
    ADR-001-multi-pattern-waterfall-candidate-retrieval.md
    ADR-002-four-slot-attribute-extraction-and-negative-collision.md
    ADR-003-autonomous-cooccurrence-learning-and-cloud-sync.md
    ADR-004-catalog-ingestion-and-timestamped-export.md
pricing_engine/
  __init__.py
  calculator.py
  db.py
  evaluator.py
  exporter.py
  ingestion.py
  learner.py
  matcher.py
  models.py
  pipeline.py
  registry.py
  scraper.py
scripts/
  select_100_stress_products.py
  setup_supabase.sql
  test_audit_pilot.py
  test_supabase_connection.py
tasks/
  approaches.md
  haier-universal-matching-plan.md
  plan.md
  research-notes.md
  todo.md
tests/
  fixtures/
    Gree_Uploading_on_DigiMall_and_Price.csv
    Haier_Washing_Machines_Uploading_and_Price.csv
    selected_100_stress_products.csv
    Stock Holding Report - FINAC - Products - MainSheet.csv
    test product list.csv
  test_calculator.py
  test_cli.py
  test_dawlance_benchmark.py
  test_db.py
  test_evaluator.py
  test_exporter.py
  test_fixtures.py
  test_haier_benchmark.py
  test_ingestion.py
  test_learner.py
  test_matcher.py
  test_pipeline_resilience.py
  test_pipeline.py
  test_registry.py
  test_scraper.py
  test_simulation.py
.env.example
.gitignore
AGENTS.md
index.py
pyproject.toml
README.md
requirements.txt
````

# Files

## File: scripts/select_100_stress_products.py
````python
import pandas as pd
import re

df = pd.read_csv(r"tests\fixtures\test product list.csv")

def get_category(name):
    u = name.upper()
    # 1. Specific small appliances / blenders / juicers
    if any(k in u for k in ["JUICER", "BLENDER", "CHOPPER", "TOASTER", "KETTLE", "FOOD PROCESSOR", "CITRUS", "HAND BLENDER", "MIXER"]):
        return "SMALL_APPLIANCES"
    # 2. Air Fryer
    if any(k in u for k in ["AIR FRYER", "AIRFRYER", "AIR-FRYER"]):
        return "AIR_FRYER"
    # 3. Microwave Oven (check before washing machine so Dawlance MWO / DW- oven doesn't get confused)
    if any(k in u for k in ["MICROWAVE", " MWO ", "MWO-", "MWO ", "OVEN", "HMO-", "HMO ", "BAKING"]):
        return "MICROWAVE_OVEN"
    if re.search(r"\bDW-(?:MD\d+|\d{3}|GSS|CHZP|AF|HZP)\b", u) and ("MICROWAVE" in u or "OVEN" in u or "GRILL" in u or "SOLO" in u or "LITRE" in u):
        return "MICROWAVE_OVEN"
    # 4. Water Dispenser
    if any(k in u for k in ["DISPENSER", "WATER DISPENSER", "HWD", "WD "]):
        return "WATER_DISPENSER"
    # 5. LED TV
    if any(k in u for k in ["LED TV", "SMART TV", "ANDROID TV", "GOOGLE TV", "QLED", "OLED", "UHD TV", "4K TV", "TELEVISION"]) or re.search(r"\b\d{2}[\"']?\s*(?:LED|SMART|4K|UHD|TV)\b", u):
        return "LED_TV"
    # 6. Deep Freezer
    if any(k in u for k in ["DEEP FREEZER", "CHEST FREEZER", "HDF-", "HDF ", "DF-", "FREEZER"]) and "REFRIGERATOR" not in u:
        return "DEEP_FREEZER"
    # 7. Washing Machine
    if any(k in u for k in ["WASHING MACHINE", "WASHER", "W/M", "HWM", "DWT", "TWIN TUB", "TOP LOAD", "FRONT LOAD", "SPINNER DRYER", "SINGLE TUB"]):
        return "WASHING_MACHINE"
    # 8. Air Conditioner (avoid matching 'capacity' or 'automatic' with raw 'AC')
    if any(k in u for k in ["AIR CONDITIONER", "SPLIT", "PULAR", "FAIRY", "HEAT & COOL", "HEAT AND COOL", "COOL ONLY"]) or re.search(r"\bAC\b", u) or re.search(r"\b\d(?:\.\d)?\s*TON\b", u) or re.search(r"\b(?:GS|HSU|ES|PINV)[- ]\d+", u):
        return "AIR_CONDITIONER"
    # 9. Refrigerator
    if any(k in u for k in ["REFRIGERATOR", "FRIDGE", "HRF", "REF", "CU FT", "CU.FT", "CFT", "DIRECT COOL", "DOUBLE DOOR", "SINGLE DOOR"]):
        return "REFRIGERATOR"
    return "SMALL_APPLIANCES"

def score_suspicion(row):
    name = str(row["Name"]).upper()
    score = 0
    # Modifiers
    if any(k in name for k in ["T3", "ES", "UV", "WIFI", "IOT", "SD", "GD", "GLASS DOOR", "INOX", "STAINLESS", "IAPA", "IFGA", "IPPA", "IDPA", "TIFG", "TIFB", "S6", "S8", "WB", "GB", "GC", "LVS"]):
        score += 4
    if any(c in name for c in ["/", "(", ")", "+"]):
        score += 3
    if any(k in name for k in ["NON-INVERTER", "FIXED SPEED", "FIX SPEED", "COOL ONLY", "HEAT & COOL", "HEAT AND COOL"]):
        score += 2
    if re.search(r"\b\d{2,3}[-_]\d{3,}", name) or re.search(r"\b[A-Z]{2,4}[-_ ]\d+", name):
        score += 2
    if re.search(r"\b(?:15|20|24|30|32|40|43|50|55|65|75)\s+[A-Za-z]+", name):
        score += 2
    return score

df["category"] = df["Name"].apply(get_category)
df["score"] = df.apply(score_suspicion, axis=1)

# Drop exact duplicate titles
df = df.drop_duplicates(subset=["Name"]).copy()

# Sort within each category by score descending
df = df.sort_values(by=["category", "score"], ascending=[True, False])

# Target quotas for the 100 products
quotas = {
    "WASHING_MACHINE": 22,
    "REFRIGERATOR": 20,
    "AIR_CONDITIONER": 22,
    "DEEP_FREEZER": 10,
    "WATER_DISPENSER": 10,
    "MICROWAVE_OVEN": 6,
    "LED_TV": 6,
    "AIR_FRYER": 2,
    "SMALL_APPLIANCES": 2,
}

selected_dfs = []
for cat, quota in quotas.items():
    cat_df = df[df["category"] == cat].head(quota)
    selected_dfs.append(cat_df)

final_df = pd.concat(selected_dfs).reset_index(drop=True)
print(f"Total Selected Products: {len(final_df)}")
print(final_df["category"].value_counts())

# Save selection to scratch directory for testing
out_path = "tests/fixtures/selected_100_stress_products.csv"
final_df.to_csv(out_path, index=False)
print(f"Saved to: {out_path}")
````

## File: scripts/test_audit_pilot.py
````python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import pandas as pd
from curl_cffi.requests import AsyncSession
from rich.console import Console
from rich.table import Table

from pricing_engine.matcher import extract_search_query_and_model, generate_search_patterns, referee_match
from pricing_engine.scraper import scrape_alfamall, scrape_digimall, _raw_items_cache

console = Console()

async def main():
    df = pd.read_csv("tests/fixtures/selected_100_stress_products.csv")
    sample = df.head(5)
    
    async with AsyncSession(impersonate="chrome120") as session:
        for idx, row in sample.iterrows():
            name = row["Name"]
            brand = row["Brands"]
            cat = row["category"]
            
            clean_q, target_model = extract_search_query_and_model(name, brand=brand)
            patterns = generate_search_patterns(name, brand=brand)
            
            console.print(f"\n[bold cyan]Product #{idx+1}:[/] {name}")
            console.print(f"  Brand: {brand} | Cat: {cat} | Target Model: [bold yellow]{target_model}[/]")
            console.print(f"  Tier 1 Query: {patterns.get('tier_1', [])}")
            
            alfa_res = await scrape_alfamall(session, patterns, target_model, brand=brand)
            digi_res = await scrape_digimall(session, patterns, target_model, brand=brand)
            
            console.print(f"  [#2c4699]AlfaMall:[/] Status={alfa_res.status_code}, Exact={len(alfa_res.offers)}, Base={len(alfa_res.base_offers)}, Fallback={alfa_res.active_modifier_fallback}, Executed={alfa_res.executed_queries}")
            if alfa_res.offers:
                for o in alfa_res.offers[:2]:
                    console.print(f"    - Exact: Rs. {o.price:,.0f} | {o.raw_title[:60]}")
            if alfa_res.base_offers:
                for o in alfa_res.base_offers[:2]:
                    console.print(f"    - Base: Rs. {o.price:,.0f} | {o.raw_title[:60]}")
                    
            console.print(f"  [#229693]DigiMall:[/] Status={digi_res.status_code}, Exact={len(digi_res.offers)}, Base={len(digi_res.base_offers)}, Fallback={digi_res.active_modifier_fallback}, Executed={digi_res.executed_queries}")
            if digi_res.offers:
                for o in digi_res.offers[:2]:
                    console.print(f"    - Exact: Rs. {o.price:,.0f} | {o.raw_title[:60]}")
            if digi_res.base_offers:
                for o in digi_res.base_offers[:2]:
                    console.print(f"    - Base: Rs. {o.price:,.0f} | {o.raw_title[:60]}")

if __name__ == "__main__":
    asyncio.run(main())
````

## File: tests/fixtures/selected_100_stress_products.csv
````
Name,Brands,category,score
Dawlance DWT-1166 X ADS+—9KG Top Load Automatic Washing Machine | Auto Dose Series | Energy Saving,DAWLANCE,WASHING_MACHINE,9
Dawlance 12KG Top Load DWT-270 C LVS+ Automatic Washing Machine,DAWLANCE,WASHING_MACHINE,9
Dawlance DWT-260 C LVS+—9KG Top Load Automatic Washing Machine | Low Voltage Series | Triple Waterfall,DAWLANCE,WASHING_MACHINE,9
Dawlance DW-9200 CFL—Extra Large Single Tub Washer | 40–50 Clothes Capacity | Powerful & Reliable,DAWLANCE,WASHING_MACHINE,8
Haier HWM 150B-699S8 15 KG Top Load Inverter Automatic Washing Machine,HAIER,WASHING_MACHINE,8
Dawlance DWT 9060 EZ Platinum 9 Kg Dark Grey Extreme+ Dryer Non-Inverter Washing Machine,DAWLANCE,WASHING_MACHINE,7
HAIER Model HWM 120-316S6 12KG AUTOMATIC TOP LOAD WASHING MACHINE,HAIER,WASHING_MACHINE,6
Dawlance DWT-14470 ES—12KG Top Load Automatic Washing Machine | Triple Waterfall | Energy Saving,DAWLANCE,WASHING_MACHINE,6
Dawlance DWT-11467 ES—10KG Top Load Fully Automatic Washing Machine | Triple Waterfall | EZ Wash,DAWLANCE,WASHING_MACHINE,6
Dawlance DS-9000—12KG Single Tub Spinner Dryer | Stainless Steel Drum | Fast & Efficient Drying,DAWLANCE,WASHING_MACHINE,6
Dawlance 12KG DW-9100-G Single Tub Glass Door Washing Machine,DAWLANCE,WASHING_MACHINE,6
Haier HW-90-BP14959S8 Automatic Washing Machine—9KG | BLDC Motor | Steam & Hygiene Care,HAIER,WASHING_MACHINE,6
Haier HWM 150-316S6 15KG Automatic Top Load Washing Machine – Starry Silver,HAIER,WASHING_MACHINE,6
Haier 10KG HWM 100-826S6 Top Load Fully Automatic Washing Machine,HAIER,WASHING_MACHINE,6
Dawlance DW 255 ES Top Load Automatic Washing Machine,DAWLANCE,WASHING_MACHINE,6
Dawlance DW6570 GB 8 Kg Twin Tub Semi Automatic Washing Machine,DAWLANCE,WASHING_MACHINE,6
Haier HWM 100-316 HS8 10 KG Top Load Automatic Washing Machine,HAIER,WASHING_MACHINE,6
Haier HWM 130B-699S8 13 KG Top Load Inverter Automatic Washing Machine,HAIER,WASHING_MACHINE,6
Haier HWM150-688S8 15 KG Top Load Automatic Washing Machine,HAIER,WASHING_MACHINE,6
Dawlance DWT 1016 INV PRIMA 10 Kg Dark Grey Prima Series DDM Inverter Washing Machine,DAWLANCE,WASHING_MACHINE,6
Dawlance DWF 8200 X INV Front Load Washing Machine-8KG | Steam Care | A+++ Energy Rating,DAWLANCE,WASHING_MACHINE,5
Dawlance DW-7500 TWIN TUB GLASS LID BLACK/GREY Washing Machine,DAWLANCE,WASHING_MACHINE,5
Haier HRF-438 IAPA+ 15 Cu Ft Purple Digital Inverter Refrigerator,HAIER,REFRIGERATOR,11
Haier HRF-418 IAPA+ 15 Cu Ft Purple Digital Inverter Refrigerator,HAIER,REFRIGERATOR,11
Haier HRF-538 IAPA+ 20 Cu Ft Purple Digital Inverter Refrigerator,HAIER,REFRIGERATOR,11
Haier HRF-368 IAPA+ 13 Cu Ft Purple Digital Inverter Refrigerator,HAIER,REFRIGERATOR,9
Haier HRF-398 IAPA+ 14 Cu Ft Purple Digital Inverter Refrigerator,HAIER,REFRIGERATOR,9
Haier HRF-458 IAPA+ 16 Cu Ft Purple Digital Inverter Refrigerator,HAIER,REFRIGERATOR,9
Dawlance 9106-SD 6 Cu Ft Metallic Grey Non-Inverter Mini Refrigerator,DAWLANCE,REFRIGERATOR,8
HAIER HRF-538 IFGA 20 Cu Ft Green Digital Inverter Refrigerator,HAIER,REFRIGERATOR,8
Dawlance DSD 4890 Silver Single Door Non-Inverter Refrigerator,DAWLANCE,REFRIGERATOR,8
Haier HRF-398 IFGA 15 Cu Ft Green Digital Inverter Refrigerator,HAIER,REFRIGERATOR,8
Haier HRF-418 TIFGU1 15 Cu Ft Grey Twin Inverter IOT Refrigerator,HAIER,REFRIGERATOR,8
Haier HRF-538 TIFGU1 20 Cu Ft Silver Grey Twin Inverter IOT Refrigerator,HAIER,REFRIGERATOR,8
Haier HRF-538 TIFBU1 20 Cu Ft Black Twin Inverter IOT Refrigerator,HAIER,REFRIGERATOR,8
Haier HRF-418 IPPA 15 Cu Ft Purple Smart Inverter Refrigerator,HAIER,REFRIGERATOR,8
Haier HRF-538 IPPA 20 Cu Ft Purple Smart Inverter Refrigerator,HAIER,REFRIGERATOR,8
Haier HRF-578 TGGU1 IOT 20 Cu Ft Champagne Gold T-Door Smart IoT Twin Inverter Refrigerator,HAIER,REFRIGERATOR,8
Haier HRF-578 TSG 20 Cu Ft Silver Inox T-Door Twin Inverter Refrigerator,HAIER,REFRIGERATOR,8
Dawlance 9173-WB-Avante+ 12 Cu Ft Cloud White Inverter Double Door Refrigerator,DAWLANCE,REFRIGERATOR,7
Dawlance 9169WB 11 Cu Ft Avante+ Sapphire Purple Double Door Refrigerator,DAWLANCE,REFRIGERATOR,7
Dawlance 9193LF 16 Cu Ft Avante+ IoT Silky Red Inverter Double Door Refrigerator,DAWLANCE,REFRIGERATOR,7
Haier 1 Ton HSU-13HFAB/W/G-T3 PRO DC Inverter Heat & Cool Air Conditioner,HAIER,AIR_CONDITIONER,11
Gree 1 Ton Pular Series GS-12PITH14S Heat & Cool Inverter Split Air Conditioner (Turbo),GREE,AIR_CONDITIONER,11
Gree 2 Ton Pular Series GS-24PITH15/16/17/18G-T3 Inverter Heat And Cool Split Air Conditioner,GREE,AIR_CONDITIONER,11
Gree 2 Ton Zeno Series GS-24ZITH1/2–T3 Inverter Heat And Cool Split Air Conditioner-White,GREE,AIR_CONDITIONER,11
Haier 1 Ton HSU-13HFS/W/G-T3 Pro Inverter Heat & Cool Split Air Conditioner,HAIER,AIR_CONDITIONER,11
EcoStar 1.5 Ton Duke Series ES-18DU02WG SA+ Inverter Heat & Cool Split Air Conditioner,EcoStar,AIR_CONDITIONER,11
HAIER 1.5 TON HSU-20HJUV(G)-T3 INVERTER HEAT & COOL AIR CONDITIONER,HAIER,AIR_CONDITIONER,11
HAIER 1.5 TON HSU-19HFS/W/G-T3 INVERTER HEAT & COOL AIR CONDITIONER,HAIER,AIR_CONDITIONER,11
HAIER 2 TON HSU-24HFAB(W) T3 INVERTER HEAT & COOL SPLIT AIR CONDITIONER,HAIER,AIR_CONDITIONER,11
Gree 1 Ton Fairy Series GS-12FITH1/S/W Inverter Heat & Cool Split Air Conditioner,GREE,AIR_CONDITIONER,11
Gree 2 Ton Pular Series GS-24PITH11S/14S Inverter Heat & Cool Air Conditioner,GREE,AIR_CONDITIONER,11
EcoStar 0.75 Ton Emperor Series ES-10EMC1WS Inverter Cool Only Split Air Conditioner,EcoStar,AIR_CONDITIONER,10
Dawlance 1.5 Ton Mega T3 Pro 30 Inverter Heat & Cool Split Air Conditioners,DAWLANCE,AIR_CONDITIONER,10
Haier 1.5 Ton HSU-18-HFT(W) T3 Inverter Air Conditioner,HAIER,AIR_CONDITIONER,9
Haier 1.5 Ton HSU-20-HFTEX(W) T3 Inverter Air Conditioner,HAIER,AIR_CONDITIONER,9
PEL 1 Ton PINV 12K Turbo Ultimate T3 (H&C) Inverter Air Conditioner,PEL,AIR_CONDITIONER,9
PEL 1.5 Ton PINV-18K JUMBO DC Prime Wifi T3 Inerter (H&C) Air Conditioner,PEL,AIR_CONDITIONER,9
PEL 1 Ton PINV-12K Jumbo Prime+ T3 (Wifi) Inverter Split Air Conditioner,PEL,AIR_CONDITIONER,9
Haier 1.5 Ton HSU-19 HFAB T3 Pro Inverter Air Conditioner (Grey),HAIER,AIR_CONDITIONER,9
Haier 2 Ton HSU-24HFAB(G)-T3 Inverter Split Air Conditioner,HAIER,AIR_CONDITIONER,9
Midea 1.5 Ton Breezeless (E) MSCB1CU-18HRFN8 DC Inverter Heat & Cool Split Air Conditioner,Midea,AIR_CONDITIONER,9
TCL 2 Ton 24 SVN-AI-CO-31G/S Inverter Cool Only Split Air Conditioner,TCL,AIR_CONDITIONER,9
Dawlance DF-200 Energy Saver Glass Door Chest Deep Freezer (Champagne),DAWLANCE,DEEP_FREEZER,9
Haier HDF-285INV (10 CF) Inverter Single Door Chest Deep Freezer,HAIER,DEEP_FREEZER,9
Dawlance 15 Cubic Feet CF-91997 Signature LVS Double Door Inverter Deep Freezer- Champagne,DAWLANCE,DEEP_FREEZER,8
Dawlance VF-1035 GD 12 Cu Ft Burgundy Honey-Comb Glass Door Non-Inverter Vertical Deep Freezer,DAWLANCE,DEEP_FREEZER,8
Dawlance CONVERTIBLE CF-91997 LVS 4-in-1 Twin Door Deep Freezer,DAWLANCE,DEEP_FREEZER,6
Dawlance DF-400 SD Inverter Single Door Deep Freezer,DAWLANCE,DEEP_FREEZER,6
Dawlance CONVERTIBLE CF-91997 LVS Twin Door Deep Freezer,DAWLANCE,DEEP_FREEZER,6
Dawlance DF-200 SD Inverter White Deep Freezer,DAWLANCE,DEEP_FREEZER,6
Dawlance DF-200P STUCCO PCM Chest Deep Freezer,DAWLANCE,DEEP_FREEZER,6
DAWLANCE DF-300P STUCCO PCM NON INVERTER CHEST DEEP FREEZER,DAWLANCE,DEEP_FREEZER,6
DAWLANCE WD-1051 HC WHITE HC Series (Hot & Cool) Water Dispenser - 2 Taps,DAWLANCE,WATER_DISPENSER,9
ORIENT Crystal 3 Taps (Smoke Purple) Crystal Glass Door Water Dispenser - 3 Taps,ORIENT,WATER_DISPENSER,7
PEL PCWD 525 Curved Glass Door Water Dispenser,PEL,WATER_DISPENSER,6
Dawlance Water Dispenser WD-1051 Silver – Hot & Cold with Glass Door and Refrigerator,DAWLANCE,WATER_DISPENSER,6
PEL 525 Curved Glass Door 3 Taps with Refrigerator Water Dispenser,PEL,WATER_DISPENSER,6
Dawlance DBD-1035 Glass Door Water Dispenser,DAWLANCE,WATER_DISPENSER,6
Dawlance DBD-1034 EZ Glass Door Water Dispenser,DAWLANCE,WATER_DISPENSER,6
WestPoint WF-1401 3.2L 500W Deluxe Water Dispenser,WestPoint Pakistan,WATER_DISPENSER,6
ORIENT DMZ1-2054-MP-IS-0265 Velvet Glass Door Water Dispenser - 3 Taps,ORIENT,WATER_DISPENSER,6
PEL PWD-316 Premier Premier Series Water Dispenser - 3 Taps,PEL,WATER_DISPENSER,6
WestPoint WF-825 20 L 1270 W Microwave Oven with Grill,WestPoint Pakistan,MICROWAVE_OVEN,8
"Homage HMSO-2020B Microwave Oven (20 Liters, Solo, Black)",Homage,MICROWAVE_OVEN,7
Haier Model HMW-20MWS Solo Series Microwave Oven 20Ltr,HAIER,MICROWAVE_OVEN,6
WestPoint WF-2800RK 1500 Watts Rotisserie Oven with Kebab Grill,WestPoint Pakistan,MICROWAVE_OVEN,6
WestPoint WF-830DG Deluxe 1050W Microwave Oven With Grill,WestPoint Pakistan,MICROWAVE_OVEN,6
WestPoint WF-2310RK 1500 Watts Rotisserie Oven with Kebab Grill,WestPoint Pakistan,MICROWAVE_OVEN,6
TCL 55 Inches 55P79K 4K UHD Google QLED TV,TCL,LED_TV,8
Haier 50 Inch 4K QLED Smart Google TV 50S80EUX,HAIER,LED_TV,8
Haier 32 Inch Smart QLED Google TV 32S80EFX,HAIER,LED_TV,8
Haier 55 Inch Smart 4K QLED Google TV 55S80EUX,HAIER,LED_TV,8
Haier 43 Inch 43S80EUX Smart Google 4K QLED TV,HAIER,LED_TV,8
TCL 32 Inch QLED Smart TV 32S59K (2026) Full HD Google TV,TCL,LED_TV,7
Philips HD9270/90 6.2L XL Essential Rapid Air Fryer,Philips,AIR_FRYER,7
WestPoint WF-4257 Deluxe 6.5L 1700W Rapid Air Fryer,WestPoint Pakistan,AIR_FRYER,6
WestPoint WF-9225 80 g Professional Dry/Wet Grinder,WestPoint Pakistan,SMALL_APPLIANCES,9
ELite Commercial Blender Pro Mix ECJB-200 – 1400W Powerful Professional Blender (3.0L Capacity),ELite,SMALL_APPLIANCES,9
````

## File: .github/workflows/ci.yml
````yaml
name: CI Quality Gates

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  quality-gates:
    name: Lint, Format & Multi-Catalog Tests (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - name: Checkout Code Repository
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: "Quality Gate 1: Code Style & Static Linter (Ruff)"
        run: ruff check .

      - name: "Quality Gate 2: Code Formatting Verification (Ruff)"
        run: ruff format --check .

      - name: "Quality Gate 3: Comprehensive Multi-Catalog Test Suite"
        run: pytest -v --durations=10

      - name: "Quality Gate 4: Multi-Catalog Benchmark & Simulation Gates"
        run: pytest tests/test_fixtures.py tests/test_simulation.py -v
````

## File: data/inputs/.gitkeep
````
# Keep directory in git
````

## File: data/inputs/Dawlance_Products_List.csv
````
S.No,Brand,Name,Net Price,Length,Width,Height
1,Dawlance,DMB 4467 SD MINI BAR,"34,000",52,55,90
2,Dawlance,9101 white,"39,000",52,55,90
3,Dawlance,9101 silver,"39,600",52,55,90
4,Dawlance,4890,"39,800",52,55,90
5,Dawlance,9106 white,"43,200",54,56,105
6,Dawlance,9106 Silver,"43,700",54,56,105
7,Dawlance,9060 INVERTER INOX,"273,000",76,85,188
8,Dawlance,9060 INVERTER GD,"288,000",76,85,188
9,Dawlance,DSS-9055 GD,"228,000",78,98,188
10,Dawlance,DSS9055 INOX,"212,000",78,98,188
11,Dawlance,DTM 7650 GD IOT,"172,000",76,85,188
12,Dawlance,DTM 7650 INOX,"162,000",76,85,188
13,Dawlance,7950 GD,"245,500",76,85,188
14,Dawlance,7950 INOX,"221,000",76,85,188
15,Dawlance,8365 INOX,"225,000",76,85,188
16,Dawlance,DMD 7951 INV GD,"211,000",76,85,188
17,Dawlance,DMD 7951 INV INOX,"189,000",76,85,188
18,Dawlance,DFD 900 GD INVERTER,"222,000",76,85,188
19,Dawlance,9140 WB LVS FH,"53,000",60,56,145
20,Dawlance,9149 WB LVS,"57,500",60,56,145
21,Dawlance,9160 WB LVS FH,"64,800",64,60,155
22,Dawlance,9169 WB LVS FH,"70,000",64,60,155
23,Dawlance,9173 WB Chrome FH,"72,000",68,64,165
24,Dawlance,9178 WB Chrome FH,"76,800",68,64,165
25,Dawlance,9191 WB Chrome FH,"81,500",72,68,175
26,Dawlance,9193 WB Chrome FH,"90,000",72,68,175
27,Dawlance,91999 WB Chrome FH,"96,500",75,72,185
28,Dawlance,9140 WB AVANTE GD,"58,000",60,56,145
29,Dawlance,9149 WB AVANTE GD,"63,000",60,56,145
30,Dawlance,9160 WB AVANTE GD,"68,500",64,60,155
31,Dawlance,9169 WB AVANTE GD,"74,500",64,60,155
32,Dawlance,9173 WB Avante GD,"79,800",68,64,165
33,Dawlance,9178 WB Avante GD,"85,000",68,64,165
34,Dawlance,9191 WB Avante GD,"90,000",72,68,175
35,Dawlance,9193 WB Avante GD,"96,000",72,68,175
36,Dawlance,91999 WB Avante GD,"108,000",75,72,185
37,Dawlance,9173 ACCE GD,"77,000",68,64,165
38,Dawlance,9178 ACCE GD,"81,500",68,64,165
39,Dawlance,9191 ACCE GD,"86,700",72,68,175
40,Dawlance,9193 ACCE GD,"92,800",72,68,175
41,Dawlance,91999 ACCE,"100,000",75,72,185
42,Dawlance,9160 WB Avante+ GD INV,"72,000",64,60,155
43,Dawlance,9160 WB Avante+ GD INV WHITE,"77,500",64,60,155
44,Dawlance,9169 WB Avante+ GD INV,"78,500",64,60,155
45,Dawlance,9169 WB Avante+ GD INV WHITE,"82,000",64,60,155
46,Dawlance,9173 WB Avante+ GD INV,"84,500",68,64,165
47,Dawlance,9173 WB Avante+ GD INV WHITE,"85,300",68,64,165
48,Dawlance,9178 WB Avante+ GD INV,"92,600",68,64,165
49,Dawlance,9178 WB Avante+ GD INV (WHITE),"92,600",68,64,165
50,Dawlance,9191 WB Avante+ GD INV,"96,300",72,68,175
51,Dawlance,9191 WB Avante+ GD INV (WHITE),"99,000",72,68,175
52,Dawlance,9193 WB Avante+ GD INV,"101,500",72,68,175
53,Dawlance,9193 WB Avante+ GD INV(WHITE),"104,500",72,68,175
54,Dawlance,91999 WB Avante+ GD INV,"113,000",75,72,185
55,Dawlance,91999 WB Avante+ GD INV(WHITE),"116,000",75,72,185
56,Dawlance,9173 ACCE PRO,"81,700",68,64,165
57,Dawlance,9178 ACCE PRO,"86,200",68,64,165
58,Dawlance,9191 ACCE PRO,"91,800",72,68,175
59,Dawlance,9193 ACCE PRO,"97,300",72,68,175
60,Dawlance,91999 ACCE PRO,"105,000",75,72,185
61,Dawlance,9173 GRAZE PLUS,"90,000",68,64,165
62,Dawlance,9178 GRAZE PLUS,"95,300",68,64,165
63,Dawlance,9191 GRAZE PLUS,"99,900",72,68,175
64,Dawlance,9193 GLAZE PLUS,"107,000",72,68,175
65,Dawlance,91999 GLAZE PLUS,"118,000",75,72,185
66,Dawlance,9160 ICEMAX,"69,500",64,60,155
67,Dawlance,9169 ICEMAX,"73,500",64,60,155
68,Dawlance,9173 ICEMAX,"79,000",68,64,165
69,Dawlance,9178 ICEMAX,"84,000",68,64,165
70,Dawlance,9140 CHROME PRO INVERTER,"57,000",60,56,145
71,Dawlance,9149 CHROME PRO INVERTER,"64,000",60,56,145
72,Dawlance,9160 WB Chrome PRO,"71,200",64,60,155
73,Dawlance,9169 WB Chrome PRO,"72,500",64,60,155
74,Dawlance,9173 WB Chrome PRO,"76,700",68,64,165
75,Dawlance,9178 WB Chrome PRO,"81,200",68,64,165
76,Dawlance,9191 WB Chrome PRO,"85,800",72,68,175
77,Dawlance,9193 WB Chrome PRO,"94,000",72,68,175
78,Dawlance,91999 WB Chrome PRO,"107,000",75,72,185
79,Dawlance,DW9193 IOT RED,"110,000",72,68,175
80,Dawlance,DW9193 IOT BLACK,"110,000",72,68,175
81,Dawlance,DW91999 IOT BLACK,"120,000",75,72,185
82,Dawlance,DW91999 IOT RED,"120,000",75,72,185
83,Dawlance,9140 WB E CHROME FH,"50,000",60,56,145
84,Dawlance,9149 WB E CHROME FH,"56,500",60,56,145
85,Dawlance,9173 WB E Chrome FH,"70,500",68,64,165
86,Dawlance,9178 WB E Chrome FH,"75,500",68,64,165
87,Dawlance,9173 DIGITALPRO,"85,000",68,64,165
88,Dawlance,9178 DIGITALPRO,"89,000",68,64,165
89,Dawlance,9191 DIGITALPRO,"94,400",72,68,175
90,Dawlance,9193 DIGITALPRO,"101,000",72,68,175
91,Dawlance,91999 DIGITALPRO,"110,000",75,72,185
92,Dawlance,DF-200 ES,"62,000",62,85,88
93,Dawlance,DF-200 GD,"65,200",62,85,88
94,Dawlance,DF-200SD INVERTER GREY,"67,000",62,85,88
95,Dawlance,DF-300 ES,"66,500",65,115,88
96,Dawlance,DF-300SD INVERTER,"72,000",65,115,88
97,Dawlance,DF-300SD INVERTER GREY,"72,000",65,115,88
98,Dawlance,DF-400 ES,"71,500",70,135,88
99,Dawlance,DF-400 INVERTER,"77,500",70,135,88
100,Dawlance,DF-400SD INVERTER GREY,"77,500",70,135,88
101,Dawlance,DF-400 EDS,"74,500",70,135,88
102,Dawlance,DF-400 COMMERCIAL,"91,000",70,135,88
103,Dawlance,DF-500 DD,"90,000",75,160,90
104,Dawlance,DF-500SD INVERTER GREY,"98,500",75,160,90
105,Dawlance,91997-H LVS,"86,000",68,125,90
106,Dawlance,91997-H LVS CONVERTABLE,"94,500",68,125,90
107,Dawlance,91997-H SIGNATURE INVERTER,"92,000",68,125,90
108,Dawlance,91998-H LVS,"88,000",68,125,90
109,Dawlance,91998-H SIGNATURE INVERTER,"96,500",68,125,90
110,Dawlance,91998-H SIGNATURE INVERTER GD,"106,000",68,125,90
111,Dawlance,91998-H CONVERTABLE,"97,000",68,125,90
112,Dawlance,VF-1035WB GD,"92,000",66,62,155
113,Dawlance,VF 1035WB GD EMERALD GREEN,"98,500",66,62,155
114,Dawlance,VF 1035WB GD AVANTE + LUXE BROWN,"98,500",66,62,155
115,Dawlance,VF 1035WB GD AVANTE + CLOUD WHITE,"99,500",66,62,155
116,Dawlance,VF-1045 CVT NO-FROST,"215,000",72,68,178
117,Dawlance,DW 6000,"17,000",52,52,88
118,Dawlance,DW 6010,"16,800",52,52,88
119,Dawlance,DW 6050,"17,700",52,52,88
120,Dawlance,DW 6080 CB,"17,300",52,52,88
121,Dawlance,DW 6100 White,"21,500",52,84,96
122,Dawlance,DW 6100 C,"22,500",52,84,96
123,Dawlance,DW 7200 W,"20,500",52,84,96
124,Dawlance,DW 7200 C,"22,000",52,84,96
125,Dawlance,DW 9000C,"37,300",52,84,96
126,Dawlance,DW 9000WM,"24,300",52,84,96
127,Dawlance,DW 9100 C,"28,000",52,84,96
128,Dawlance,DW 9100 G,"30,000",52,84,96
129,Dawlance,DW-9200WFL,"27,500",52,84,96
130,Dawlance,DW-9200CFL,"28,000",52,84,96
131,Dawlance,DW-6550W,"33,000",52,84,96
132,Dawlance,DW-6550G,"36,000",52,84,96
133,Dawlance,DW-6550C,"34,000",52,84,96
134,Dawlance,DW-7500C,"38,000",55,92,102
135,Dawlance,DW-7500 G,"39,600",55,92,102
136,Dawlance,DW-10500C,"44,000",55,92,102
137,Dawlance,DW-10600 CFL,"45,000",55,92,102
138,Dawlance,DW-10600 WFL,"43,000",55,92,102
139,Dawlance,DW 6580 CFL,"34,500",52,84,96
140,Dawlance,DW 6580 WFL,"32,000",52,84,96
141,Dawlance,DW-8550 CFL,"35,300",55,92,102
142,Dawlance,DW-8550 WFL,"36,000",55,92,102
143,Dawlance,DW-6570,"27,600",52,84,96
144,Dawlance,DWT 260 LVS+C/S,"66,000",62,64,102
145,Dawlance,DWT 260ES,"66,000",62,64,102
146,Dawlance,DWT 270 LVS+ C,"76,000",68,70,108
147,Dawlance,DWT 270 LVS+ S,"76,000",68,70,108
148,Dawlance,DWT 9540,"59,500",62,64,102
149,Dawlance,DWT 9560,"61,000",62,64,102
150,Dawlance,AWM DWT11467ES,"59,000",62,64,102
151,Dawlance,AWM DWT 1165 PL,"69,000",68,70,108
152,Dawlance,AWM DWT 1166,"78,000",68,70,108
153,Dawlance,AWM DWT 1167 FLP,"64,000",68,70,108
154,Dawlance,AWM DWT 11671 FLT,"69,500",68,70,108
155,Dawlance,AWM DWT 1470 PL,"79,000",68,70,108
156,Dawlance,AWM DWT 1471 FLP,"73,500",68,70,108
157,Dawlance,AWM DWT 14711 FLT,"81,500",68,70,108
158,Dawlance,AWM DWT 14470 ES,"78,000",68,70,108
159,Dawlance,AWM DWT 1775 PL,"115,000",72,74,112
160,Dawlance,DWT 1006,"71,000",62,64,102
161,Dawlance,DWT 1016 INVERTER,"84,000",62,64,102
162,Dawlance,DWT 1776 FLT,"115,000",72,74,112
163,Dawlance,DWT 1580 INV,"111,000",72,74,112
164,Dawlance,DWT 255ES,"50,000",66,66,88
165,Dawlance,DWT 7310 INV,"114,000",65,60,120
166,Dawlance,AWM DWF 7200 X INV,"127,500",66,66,88
167,Dawlance,AWM DWF 8200 X INV,"145,500",66,66,88
168,Dawlance,DW-9060EZ,"50,000",62,64,102
169,Dawlance,DWF 85-1214 MG INV FRONT LOAD,"123,500",66,66,88
170,Dawlance,DWF 95-1215 MG INV FRONT LOAD,"128,500",66,66,88
171,Dawlance,DWF 105-1215 MG INV FRONT LOAD,"131,000",66,66,88
172,Dawlance,DWT 107-1414 MG INV FRONT LOAD DRYER,"144,000",66,66,88
173,Dawlance,DW 90100 W Washer,"21,899",58,58,96
174,Dawlance,DW 10115 Washer Black Opaque Lid,"21,853",58,58,96
175,Dawlance,DW 14150 WASHER BLACK OPAQUE LID,"28,277",58,58,96
176,Dawlance,DW 14145 C WASHER CLEAR LID,"28,933",58,58,96
177,Dawlance,DW 10095 GB Twin Tub Black Lid,"28,652",55,92,102
178,Dawlance,MD-4 WHITE,"14,500",48,38,30
179,Dawlance,MD-4 BLACK,"15,000",48,38,30
180,Dawlance,MD-7,"14,700",48,38,30
181,Dawlance,DW MD-10,"14,600",48,38,30
182,Dawlance,DW MD-15,"13,800",48,38,30
183,Dawlance,DW MD-20 INV,"15,000",48,38,30
184,Dawlance,DW210S PRO BLACK,"15,500",48,38,30
185,Dawlance,DW210S WHITE,"15,000",48,38,30
186,Dawlance,DW390S,"20,500",54,44,34
187,Dawlance,DW388,"22,000",54,44,34
188,Dawlance,DW2205,"14,800",48,38,30
189,Dawlance,DW-295,"16,800",54,44,34
190,Dawlance,DW-297 GSS,"20,000",54,44,34
191,Dawlance,DW-374/374 IR CIRCUIT,"23,500",54,44,34
192,Dawlance,DW-393 GSS,"27,800",54,44,34
193,Dawlance,DW-132 S,"28,400",54,44,34
194,Dawlance,DW-128G,"30,800",54,44,34
195,Dawlance,DW-395 HCG,"25,300",54,44,34
196,Dawlance,DW-133 RG,"29,000",54,44,34
197,Dawlance,DW-133 G,"32,500",54,44,34
198,Dawlance,DW-131 HP,"33,500",54,44,34
199,Dawlance,DW-136G,"32,000",54,44,34
200,Dawlance,DW-115 CHZP,"36,000",60,50,40
201,Dawlance,DW-162HZP,"42,500",60,50,40
202,Dawlance,DW-550 AF,"44,000",60,50,40
203,Dawlance,DW-560 AF,"52,000",60,50,40
204,Dawlance,DW-142,"39,500",60,50,40
205,Dawlance,DW-530 AF,"39,500",60,50,40
206,Dawlance,DW-393G,"26,000",54,44,34
207,Dawlance,DW-330DS,"26,800",54,44,34
208,Dawlance,DW-525AF,"39,500",60,50,40
209,Dawlance,DW-299DS,"22,500",54,44,34
210,Dawlance,DW2113C MINI MICRO,"15,000",48,38,30
211,Dawlance,DWOT 4215,"35,000",60,50,40
212,Dawlance,DWOT 2515,"22,000",60,50,40
213,Dawlance,DWOT2515CR,"24,000",60,50,40
214,Dawlance,DW3013AF AIRFRYER,"29,500",60,50,40
215,Dawlance,DW251G,"21,000",54,44,34
216,Dawlance,DW25BG,"22,000",54,44,34
217,Dawlance,DDW 868 CT B,"78,500",66,66,88
218,Dawlance,DDW 1471 I INVERTER,"162,500",66,66,88
219,Dawlance,DDW 1470 GB INVERTER,"176,500",66,66,88
220,Dawlance,DDW 149525 INVERTER,"148,000",66,66,88
221,Dawlance,WD 1060 FP WITHOUT REF,"32,000",40,38,108
222,Dawlance,WD 1060 C/S/G,"38,000",40,38,108
223,Dawlance,WD 1051 GD C/S/R/B,"39,500",40,38,108
224,Dawlance,WD 1051 GD WHITE,"41,000",40,38,108
225,Dawlance,WD 1035 GD BOTTOM LOAD,"45,600",40,38,108
226,Dawlance,WD 1034 GD BOTTOM LOAD,"40,600",40,38,108
227,Dawlance,WD 1051 HC,"33,500",40,38,108
228,Dawlance,WD 1051 CN,"33,200",88,38,60
229,Dawlance,15 Infinity Pro Fix Speed,"87,000",98,40,66
230,Dawlance,30 Infinity Pro Fix Speed,"107,000",88,38,60
231,Dawlance,15 Inspire,"97,000",88,38,60
232,Dawlance,15 Sprinter / Powercon,"98,000",88,38,60
233,Dawlance,15 Sprinter / Powercon T3,"106,000",98,40,66
234,Dawlance,30 Sprinter / Powercon,"116,000",98,40,66
235,Dawlance,30 Sprinter / Powercon T3,"127,000",88,38,60
236,Dawlance,15 Aura,"104,000",98,40,66
237,Dawlance,30 Aura,"134,000",88,38,60
238,Dawlance,15 Mega Flex,"109,000",98,40,66
239,Dawlance,30 Mega Flex,"141,000",98,40,66
240,Dawlance,30 Mega T3 Pro,"150,000",88,38,60
241,Dawlance,15 Elegance X,"104,000",88,38,60
242,Dawlance,15 Elegance PRO,"109,000",98,40,66
243,Dawlance,30 Elegance X,"136,000",88,38,60
244,Dawlance,15 Econo,"103,000",98,40,66
245,Dawlance,30 Econo,"133,000",88,38,60
246,Dawlance,15 Frost Pro,"91,000",98,40,66
247,Dawlance,20 Frost,"96,000",98,40,66
248,Dawlance,30 Frost,"110,000",98,40,66
249,Dawlance,30 Frost Pro,"111,000",98,40,66
250,Dawlance,30 Chrome Copper,"129,000",110,44,78
251,Dawlance,Chrome + 45,"193,000",98,40,66
252,Dawlance,Hyper T30 (White),"150,000",98,40,66
253,Dawlance,30 Suave+ (Silver),"131,000",98,40,66
254,Dawlance,30 MAGNA INV R-32 (White Textured),"148,000",98,40,66
255,Dawlance,30 Magna T3 INV (Milky White Textured),"149,500",98,40,66
256,Dawlance,30 MAGNA INV R-32 (White),"146,000",98,40,66
257,Dawlance,30 Excel,"136,000",98,40,66
258,Dawlance,30 Avante (White),"143,000",98,40,66
259,Dawlance,30 Prima PurSense,"168,000",65,50,198
260,Dawlance,45 GALLANT FLOOR,"281,000",65,50,198
261,Dawlance,45 GLAMOUR FLOOR,"273,000",110,44,78
262,Dawlance,GLACIER 2 Ton FLOOR,"241,000",106,14,66
263,Dawlance,"43"" E3A","58,000",80,13,51
264,Dawlance,"32"" E22 Smart","46,500",106,14,66
265,Dawlance,"43"" E22 Smart","69,500",122,15,76
266,Dawlance,"50"" G3A Pro","96,000",134,16,84
267,Dawlance,"55"" G3A Pro","113,500",80,13,51
268,Dawlance,"32"" KORE","41,000",98,14,62
269,Dawlance,"40"" KORE","55,000",98,14,62
270,Dawlance,"43"" KORE","63,000",106,14,66
````

## File: data/inputs/Gree_AC.csv
````
S.NO,Brand,Name ,Length,Width,Height,Shipping Estimate,Commision,Net Price,Total Without Profit,Minimum Price Alfa,Maximum Price Alfa,Minimum Price Digi,Maximum Price Digi,Profit,Calculation,Final Price Alfa,Final Price Digi
1,Gree,GREE FLOOR STANDING 36TFIH AA+,127,43,200,15291,,"415,000",430291,,,,,,430291,,
2,Gree,GREE SPLIT AC 12AITH21W-T3,87,35.5,92,3978,,"147,000",150978,,,,,,150978,,
3,Gree,GREE SPLIT AC 12AITH24S-T3,87,35.5,92,3978,,"172,000",175978,,,,,,175978,,
4,Gree,GREE SPLIT AC 18AITH21B-T3,104,39,103,5849,,"183,000",188849,,,,,,188849,,
5,Gree,GREE SPLIT AC 18AITH21W-T3,104,39,103,5849,,"183,000",188849,,,,,,188849,,
6,Gree,GREE SPLIT AC 18AITH24S-T3,104,39,103,5849,,"226,000",231849,,,,,,231849,,
7,Gree,GREE SPLIT AC 18PITH11G AAA,103,38.5,102,5663,,"143,000",148663,,,,,,148663,,
8,Gree,GREE SPLIT AC 18PITH11W AAA,103,38.5,102,5663,,"140,000",145663,,,,,,145663,,
9,Gree,GREE SPLIT AC 24AITH21B-T3,108,43,114,7412,,"236,000",243412,,,,,,243412,,
10,Gree,GREE SPLIT AC 24AITH21W-T3,108,43,114,7412,,"236,000",243412,,,,,,243412,,
11,Gree,GREE SPLIT AC 24PITH11S SILVER,106,42,110,6856,,"212,000",218856,,,,,,218856,,
12,Gree,GREE SPLIT AC 24PITH14S SILVER,106,42,110,6856,,"212,000",218856,,,,,,218856,,
13,Gree,GREE SPLIT AC GS-12PITH15G-T3,87,35.5,92,3978,,"131,500",135478,,,,,,135478,,
14,Gree,GREE SPLIT AC GS-12PITH15W-T3,87,35.5,92,3978,,"129,000",132978,,,,,,132978,,
15,Gree,GREE SPLIT AC GS-12PITH17G-T3,87,35.5,92,3978,,"131,500",135478,,,,,,135478,,
16,Gree,GREE SPLIT AC GS-12PITH17W-T3,87,35.5,92,3978,,"129,000",132978,,,,,,132978,,
17,Gree,GREE SPLIT AC GS-12ZITH2W-T3,88,36,93,4125,,"133,000",137125,,,,,,137125,,
18,Gree,GREE SPLIT AC GS-18PITC12W-T3,103,38.5,102,5663,,"153,000",158663,,,,,,158663,,
19,Gree,GREE SPLIT AC GS-18PITH15G-T3,103,38.5,102,5663,,"158,000",163663,,,,,,163663,,
20,Gree,GREE SPLIT AC GS-18PITH17G-T3,103,38.5,102,5663,,"158,000",163663,,,,,,163663,,
21,Gree,GREE SPLIT AC GS-18ZITH2W-T3,104,39,103,5849,,"164,000",169849,,,,,,169849,,
22,Gree,GREE SPLIT AC GS-24PITH15G-T3,106,42,110,6856,,"220,000",226856,,,,,,226856,,
23,Gree,GREE SPLIT AC GS-24PITH15W-T3,106,42,110,6856,,"219,000",225856,,,,,,225856,,
24,Gree,GREE SPLIT AC GS-24PITH17G-T3,106,42,110,6856,,"220,000",226856,,,,,,226856,,
25,Gree,GREE SPLIT AC GS-24ZITH1W-T3,107,42.5,112,7130,,"222,000",229130,,,,,,229130,,
````

## File: data/inputs/Haier_Products_List.csv
````
S.No,Brand,Name,Net Price,Length,Width,Height
1,Haier,12cf,"80,000",88,38,60
2,Haier,18cf,"100,000",98,40,66
3,Haier,24cf,"144,000",110,44,78
4,Haier,11lf,"82,000",88,38,60
5,Haier,13lf,"87,000",88,38,60
6,Haier,19lf,"110,000",98,40,66
7,Haier,13hfc,"97,000",88,38,60
8,Haier,19hfc,"116,000",98,40,66
9,Haier,24hfc,"172,000",110,44,78
10,Haier,14hft ow,"115,000",88,38,60
11,Haier,14hft dg,"119,000",88,38,60
12,Haier,20hft ow,"151,000",98,40,66
13,Haier,20hft dg,"156,000",98,40,66
14,Haier,13hfab white,"106,000",88,38,60
15,Haier,13hfab grey,"109,000",88,38,60
16,Haier,19hfab white,"137,000",98,40,66
17,Haier,19hfab grey,"142,000",98,40,66
18,Haier,24hfab white,"184,000",110,44,78
19,Haier,24hfab grey,"186,000",110,44,78
20,Haier,13hfs white,"105,000",88,38,60
21,Haier,13hfs s g,"108,000",88,38,60
22,Haier,19hfs w,"135,500",98,40,66
23,Haier,19hfs s g,"141,000",98,40,66
24,Haier,13hfn,"103,000",88,38,60
25,Haier,19hfn,"133,000",98,40,66
26,Haier,Solar hybrid 1.5ton,"162,000",98,40,66
27,Haier,Solar hybrid 2ton,"187,000",110,44,78
28,Haier,20hj,"203,000",98,40,66
29,Haier,20hjuv,"182,000",98,40,66
30,Haier,24 CEO3 / H03,"200,000",65,50,195
31,Haier,24 HD/Z W,"265,000",65,50,195
32,Haier,24 HDZ UV,"268,000",65,50,195
33,Haier,24 HE/DC,"250,000",65,50,195
34,Haier,48 CEO3,"370,000",75,55,205
35,Haier,48 CE/DC,"451,500",75,55,205
36,Haier,48 EDC,"486,000",75,55,205
37,Haier,Cassette 18 HE/DC,"272,500",95,95,45
38,Haier,Cassette 24 HE/DC,"400,000",95,95,45
39,Haier,Cassette 48 HE/DC COOL ONLY,"543,000",105,105,55
40,Haier,Cassette 48 HE/DC H & C,"588,000",105,105,55
41,Haier,HR-66 B,"29,224",50,48,55
42,Haier,HR-136 B,"41,344",54,56,105
43,Haier,HRF-186 EBS/EBD,"43,820",62,58,145
44,Haier,HRF-216 EBS/EBD,"53,390",62,58,145
45,Haier,HRF 216 EPR/EPB,"56,833",62,58,145
46,Haier,HRF-246 EBS/EBD,"57,694",62,58,145
47,Haier,HRF 246 EPR/EPB,"62,096",62,58,145
48,Haier,HRF-276 EBS/EBD,"62,095",65,62,155
49,Haier,HRF 276 EPR/EPB,"66,400",65,62,155
50,Haier,HRF-316 EPR/EPB,"74,247",65,62,155
51,Haier,HRF-346 EPR/EPB,"77,691",68,65,168
52,Haier,HRF-368 EPR/EPB,"94,841",68,65,168
53,Haier,HRF-398 EPR/EPB,"99,636",68,65,168
54,Haier,HRF-438 EPR/EPB,"104,814",74,70,178
55,Haier,HRF-538 EPR/EPG,"110,568",74,70,178
56,Haier,HRF-246 IPRA/IPGA/IPPA,"65,532",62,58,145
57,Haier,HRF-276 IPRA/IPGA/IPPA,"69,837",65,62,155
58,Haier,HRF-316 IPRA/IPGA/IPPA,"77,684",65,62,155
59,Haier,HRF-346 IPRA/IPGA/IPPA,"81,128",68,65,168
60,Haier,HRF-418 IPRA/IPGA/IPPA,"90,697",74,70,178
61,Haier,HRF-458 IPRA/IPGA/IPPA,"95,386",74,70,178
62,Haier,HRF-538 IPRA/IPGA/IPPA,"104,094",74,70,178
63,Haier,HRF-316 IDGA/IDRGA,"81,124",65,62,155
64,Haier,HRF-346 IDGA/IDRGA,"84,665",68,65,168
65,Haier,HRF-418 IDGA/IDRGA,"95,096",74,70,178
66,Haier,HRF-458 IDGA/IDRGA,"99,785",74,70,178
67,Haier,HRF-538 IDGA/IDRGA,"107,632",74,70,178
68,Haier,HRF-316 IAPA+/IARA,"81,119",65,62,155
69,Haier,HRF-346 IAPA+/IARA,"84,660",68,65,168
70,Haier,HRF-368 IAPA+/IARA,"85,675",68,65,168
71,Haier,HRF-398 IAPA+/IARA,"106,332",68,65,168
72,Haier,HRF-418 IAPA+/IARA,"95,089",74,70,178
73,Haier,HRF-438 IAPA+/IARA,"111,509",74,70,178
74,Haier,HRF-458 IAPA+/IARA,"99,777",74,70,178
75,Haier,HRF-538 IAPA+/IARA,"107,624",74,70,178
76,Haier,HRF-316 IFGA/IFRA,"83,792",65,62,155
77,Haier,HRF-346 IFGA/IFRA,"87,236",68,65,168
78,Haier,HRF-368 IFGA/IFRA,"89,964",68,65,168
79,Haier,HRF-398 IFGA/IFRA,"110,161",68,65,168
80,Haier,HRF-418 IFGA/IFRA/IFPA,"99,996",74,70,178
81,Haier,HRF-438 IFGA/IFRA/IFPA,"92,635",74,70,178
82,Haier,HRF-458 IFGA/IFRA/IFPA,"104,683",74,70,178
83,Haier,HRF-538 IFGA/IFRA/IFPA,"112,626",74,70,178
84,Haier,HRF-418 TIFG1U1/TIFB1U1 (IOT),"104,298",74,70,178
85,Haier,HRF-458 TIFG1U1/TIFB1U1 (IOT),"109,084",74,70,178
86,Haier,HRF-538 TIFG1U1/TIFB1U1 (IOT),"115,207",74,70,178
87,Haier,HRF-488 IFFB,"215,771",78,96,190
88,Haier,HRF-518 IFFB,"223,281",78,96,190
89,Haier,HRF-518 WIFFBGU1,"228,913",78,96,190
90,Haier,HRF-622 IBS,"207,407",78,96,190
91,Haier,HRF-622 ICG,"217,784",78,96,190
92,Haier,HRF-622 IBG,"220,308",78,96,190
93,Haier,HRF-578 TSG,"181,270",78,96,190
94,Haier,HRF-578 TBG,"181,269",78,96,190
95,Haier,HRF-578 TBGU1 (IOT),"188,281",78,96,190
96,Haier,HRF-578 TGGU1 (IOT),"188,280",78,96,190
97,Haier,HRF-678 TGG,"323,119",78,96,190
98,Haier,HRF-585SFFGU1,"338,155",78,96,190
99,Haier,HWM 60-50,"17,000",54,54,92
100,Haier,HWM-80-60,"18,500",54,54,92
101,Haier,HWM 80-1217 E,"18,000",54,54,92
102,Haier,HWM 80-1217 W,"19,500",54,54,92
103,Haier,HWM-120-35,"24,000",54,54,92
104,Haier,HWM-130-1217 E,"24,000",54,54,92
105,Haier,HWM-130-1217 WB,"25,000",54,54,92
106,Haier,HWM-130-1217 GB,"25,000",54,54,92
107,Haier,HWM-75 AS,"24,500",54,86,98
108,Haier,HWM-80 CS,"26,000",54,86,98
109,Haier,HWM 100-196 E,"30,000",54,86,98
110,Haier,HWM 100-196 G,"31,500",54,86,98
111,Haier,HWM 100-1217,"30,500",54,86,98
112,Haier,HWM-120 AS GREY,"42,500",54,86,98
113,Haier,HWM-120 AS MG,"42,500",54,86,98
114,Haier,HWM 80-186,"32,000",54,86,98
115,Haier,HWM 110-186,"34,500",54,86,98
116,Haier,HWM 100-1169,"31,500",54,86,98
117,Haier,HWM 85-1269,"49,000",62,62,102
118,Haier,HWM 100-1269 (NEW),"51,000",62,62,102
119,Haier,HWM 90-1708,"58,000",62,62,102
120,Haier,HWM 90-826 E,"52,500",62,62,102
121,Haier,HWM 100-826,"57,000",62,62,102
122,Haier,HWM 95-1678 ES8/JT,"66,000",62,62,102
123,Haier,HWM 100-1678 E,"65,000",62,62,102
124,Haier,HWM-110-688 (NEW),"64,000",66,66,106
125,Haier,HWM-110-B688S8,"70,000",66,66,106
126,Haier,HWM-120-826 GT/GC,"69,000",66,66,106
127,Haier,HWM 120-1678 ES8,"78,000",66,66,106
128,Haier,HWM 120-1678 ES9,"74,000",66,66,106
129,Haier,HWM-120-B1678,"89,000",66,66,106
130,Haier,HWM-130-688S3,"77,000",66,66,106
131,Haier,HWM-150-826 GT,"76,000",72,72,112
132,Haier,HWM 150-688S8,"84,000",72,72,112
133,Haier,HWM 150-B1678 ES8,"82,500",72,72,112
134,Haier,HWM 150-1678 ES8,"83,000",72,72,112
135,Haier,HWM 150-B1978,"147,000",72,72,112
136,Haier,HWM 150-B2578 S8 (NEW),"101,000",72,72,112
137,Haier,HWM-200-BD2178 S8,"190,000",72,72,112
138,Haier,100-316 S6,"60,500",62,62,102
139,Haier,100-316 HS8 (NEW),"63,000",62,62,102
140,Haier,120-316 S6,"72,500",66,66,106
141,Haier,150-316 S6,"80,000",72,72,112
142,Haier,HWM-130-B699,"87,000",66,66,106
143,Haier,HWM-150-B699,"96,000",72,72,112
144,Haier,HW-80 BP12929 S3 / S6,"135,000",67,67,89
145,Haier,HW-100 AR,"210,000",67,67,89
146,Haier,HW-90-BP12357 S8 (NEW),"130,000",67,67,89
147,Haier,HW-100-BP12357 S8 (NEW),"140,000",67,67,89
148,Haier,HW-120-BP12357 S8 (NEW),"153,000",67,67,89
149,Haier,HWD-120-BP12357 S8 (NEW),"179,000",67,67,89
150,Haier,105 BD14376 PG,"170,000",67,67,89
151,Haier,HDF-230,"61,000",62,88,88
152,Haier,HDF-285,"73,000",65,112,88
153,Haier,HDF-320,"68,500",65,112,88
154,Haier,HDF-345 SD,"77,500",70,140,88
155,Haier,HDF-385,"86,000",70,140,88
156,Haier,HDF-405 SD,"88,500",70,140,88
157,Haier,HDF-465,"96,500",70,140,88
158,Haier,HDF-535,"105,500",75,165,90
159,Haier,HDF-545,"115,000",75,165,90
160,Haier,HDF 175 INV / IG,"57,000",62,88,88
161,Haier,HDF 230 INV,"61,000",62,88,88
162,Haier,HDF 245 INV / IG,"72,500",65,112,88
163,Haier,HDF-285 INV / IG,"76,000",65,112,88
164,Haier,HDF 320 INV,"70,500",65,112,88
165,Haier,HDF-345 IG,"82,000",70,140,88
166,Haier,HDF-385 INV / IG,"89,500",70,140,88
167,Haier,HDF-405 INV / IG,"95,000",70,140,88
168,Haier,HDF-465 INV,"97,500",70,140,88
169,Haier,HDF-535 INV,"108,500",75,165,90
170,Haier,HDF-545 INV,"122,500",75,165,90
171,Haier,"32"" D2","35,500",80,13,51
172,Haier,"40"" K800 / K66","57,500",98,14,62
173,Haier,"32"" K85","45,500",80,13,51
174,Haier,"40"" K85","61,000",98,14,62
175,Haier,"43"" K85 FX","70,000",106,14,66
176,Haier,"50"" K85","96,000",122,15,76
177,Haier,"55"" K85 FX","108,000",134,16,84
178,Haier,"65"" K85 FX","175,000",158,18,96
179,Haier,"75"" K85","228,000",180,20,110
180,Haier,"50"" S800 Q-LED PRO","113,000",122,15,76
181,Haier,"55"" S800 Q-LED PRO","134,500",134,16,84
182,Haier,"65"" S800 Q-LED PRO","194,000",158,18,96
183,Haier,"85"" S800 Q-LED PRO","425,000",205,24,125
184,Haier,"85"" S800 Q-LED","440,000",205,24,125
185,Haier,"55"" S900","188,500",134,16,84
186,Haier,"55"" M80","157,000",134,16,84
187,Haier,"65"" M80","220,000",158,18,96
188,Haier,"75"" M80","300,000",180,20,110
189,Haier,"85"" M80","480,000",205,24,125
190,Haier,"65"" M90 4K","240,000",158,18,96
191,Haier,"75"" M90 4K","330,000",180,20,110
192,Haier,"32"" S80","45,500",80,13,51
193,Haier,"43"" S80 UX","79,500",106,14,66
194,Haier,"50"" S80","99,000",122,15,76
195,Haier,"55"" S80 / S81","114,000",134,16,84
196,Haier,"65"" S80","172,000",158,18,96
197,Haier,"75"" S80","251,000",180,20,110
198,Haier,"98"" S90","730,000",235,28,145
199,Haier,HMW-20 MBS/MWS,"14,000",48,38,30
200,Haier,HMN 20 MXP3/MXP5/MXP6,"13,000",48,38,30
201,Haier,HMW-20 MPS/MPB,"13,500",48,38,30
202,Haier,HMW-26 MBH SOLO (Silver),"24,000",54,44,34
203,Haier,HMW-26 MBH SOLO (Black),"23,000",54,44,34
204,Haier,HGL-25MXP8 / 25MXP9,"22,000",54,44,34
205,Haier,HMW-20 MX11/MX12,"15,000",48,38,30
206,Haier,HMW-20 DSS Digital,"17,500",48,38,30
207,Haier,HMW-20 MHES,"16,500",48,38,30
208,Haier,HMW-20 DGS GRILL,"20,000",48,38,30
209,Haier,HGL-23200,"27,000",54,44,34
210,Haier,HGL-28100,"30,000",54,44,34
211,Haier,HGL-30100,"40,500",60,52,42
212,Haier,HMN-32100 EGB,"32,000",60,52,42
213,Haier,HMN-32300,"33,000",60,52,42
214,Haier,HMO-45200,"39,500",60,52,42
215,Haier,HMO-62 MX80,"46,000",60,52,42
216,Haier,HMW-30AFR / AFS,"47,000",60,52,42
217,Haier,HAF 50 MB,"16,000",38,34,36
218,Haier,HAF 50 DB,"18,500",38,34,36
219,Haier,HDR-TC2C1 GB/GR/GS,"40,000",40,38,108
````

## File: data/inputs/Haier_Washers.csv
````
S.NO,Brand,Name ,Length,Width,Height,Shipping Estimate,Commision,Net Price,Total Without Profit,Minimum Price Alfa,Maximum Price Alfa,Minimum Price Digi,Maximum Price Digi,Profit,Calculation,Final Price Alfa,Final Price Digi
1,Haier,Haier HW 105-BD14376PGU1 Front Load Washing Machine,65.0,57.0,92.0,4772,,"170,000",174772,,,,,,174772,,
2,Haier,Haier HW 90-BP12357S8 Front Load Washing Machine,65.0,56.0,92.0,4688,,"130,000",134688,,,,,,134688,,
3,Haier,Haier HW 100-BP12357S8 Front Load Washing Machine,65.0,59.0,92.0,4939,,"140,000",144939,,,,,,144939,,
4,Haier,Haier HW 120-BP12357S8 Front Load Washing Machine,65.0,62.0,92.0,5191,,"153,000",158191,,,,,,158191,,
5,Haier,Haier 100-316 HS8 Automatic Washing Machine,62.4,63.4,101.0,5594,,"63,000",68594,,,,,,68594,,
6,Haier,Haier 130-688S8 Automatic Washing Machine,66.0,66.0,105.0,6403,,"77,000",83403,,,,,,83403,,
7,Haier,Haier 110-688S8 Automatic Washing Machine,64.0,65.0,103.0,5999,,"64,000",69999,,,,,,69999,,
8,Haier,Haier 90-826E Automatic Washing Machine,61.0,62.0,98.0,5189,,"52,500",57689,,,,,,57689,,
9,Haier,Haier HWM-150-B699S8 Automatic Washing Machine,68.0,68.0,108.0,6991,,"96,000",102991,,,,,,102991,,
10,Haier,Haier 150-688S8 Automatic Washing Machine,68.0,68.0,108.0,6991,,"84,000",90991,,,,,,90991,,
11,Haier,Haier HWM-130-B699S8 Automatic Washing Machine,66.0,66.0,105.0,6403,,"87,000",93403,,,,,,93403,,
12,Haier,Haier 100-316S6 Automatic Washing Machine,62.4,63.4,101.0,5594,,"60,500",66094,,,,,,66094,,
13,Haier,Haier 120-316S6 Automatic Washing Machine,66.0,66.0,105.0,6403,,"72,500",78903,,,,,,78903,,
14,Haier,Haier 150-826S6 GC Automatic Washing Machine,68.0,65.0,98.0,6064,,"76,000",82064,,,,,,82064,,
15,Haier,Haier HWM 100-1269 Automatic Washing Machine,62.0,63.0,102.0,5578,,"51,000",56578,,,,,,56578,,
16,Haier,Haier 150-316S6 Automatic Washing Machine,68.0,68.0,108.0,6991,,"80,000",86991,,,,,,86991,,
17,Haier,Haier 110-B688S8 Automatic Washing Machine,64.0,65.0,103.0,5999,,"70,000",75999,,,,,,75999,,
18,Haier,Haier 100-826S6 Automatic Washing Machine,63.0,63.0,98.0,5445,,"57,000",62445,,,,,,62445,,
19,Haier,Haier HWM 95-1678 ES8 Automatic Washing Machine,61.0,62.0,100.0,5295,,"66,000",71295,,,,,,71295,,
20,Haier,Haier 120-826S6 GC Automatic Washing Machine,65.0,63.0,98.0,5618,,"69,000",74618,,,,,,74618,,
21,Haier,Haier HWM 120-826 Automatic Washing Machine,65.0,63.0,98.0,5618,,"69,000",74618,,,,,,74618,,
22,Haier,Haier HWM 95-1678 E Automatic Washing Machine,61.0,62.0,100.0,5295,,"66,000",71295,,,,,,71295,,
23,Haier,Haier HWM 60-50 Single Tub Washing Machine,49.0,51.0,89.0,3114,,"17,000",20114,,,,,,20114,,
24,Haier,Haier HWM-120-35 Single Tub Washing Machine,56.0,60.0,115.0,5410,,"24,000",29410,,,,,,29410,,
25,Haier,Haier HWM-80-CS Twin Tub Semi-Automatic Washing Machine,82.0,50.0,102.0,5855,,"26,000",31855,,,,,,31855,,
26,Haier,Haier HWM 80-60 Single Tub Washer Washing Machine,52.0,55.0,100.0,4004,,"18,500",22504,,,,,,22504,,
27,Haier,Haier HWM 60-50 Single Tub Washing Machine,49.0,51.0,89.0,3114,,"17,000",20114,,,,,,20114,,
28,Haier,Haier HWM 80-60 Single Tub Washer Washing Machine,52.0,54.0,95.0,3735,,"18,500",22235,,,,,,22235,,
29,Haier,Haier HWM 130-1217 WB Single Tub Washing Machine,56.0,58.0,115.0,5229,,"25,000",30229,,,,,,30229,,
30,Haier,Haier HWM 130-1217 GB Single Tub Washing Machine,56.0,58.0,115.0,5229,,"25,000",30229,,,,,,30229,,
31,Haier,Haier HWM 130-1217 E Single Tub Washing Machine,56.0,58.0,115.0,5229,,"24,000",29229,,,,,,29229,,
32,Haier,Haier 8 Kg Single Tub HWM 80-1217WB Washer Washing Machine,52.0,55.0,100.0,4004,,"19,500",23504,,,,,,23504,,
33,Haier,Haier 7.5 Kg HWM 75-AS Twin Tub Semi-Automatic Washing Machine,82.0,50.0,97.0,5568,,"24,500",30068,,,,,,30068,,
34,Haier,Haier HWM 100-196S 10 Kg Twin Tub Washing Machine,82.0,50.0,102.0,5855,,"31,500",37355,,,,,,37355,,
35,Haier,Haier 10 KG HWM 100-1217-WB Twin Tub Semi Automatic Washing Machine,92.0,56.0,106.0,7646,,"30,500",38146,,,,,,38146,,
36,Haier,Haier 10 KG HWM-100-196G Twin Tub Semi Automatic Washing Machine,82.0,50.0,102.0,5855,,"31,500",37355,,,,,,37355,,
37,Haier,Haier 10 Kg HWM-100-196E Twin Tub Semi-Automatic Washing Machine,82.0,50.0,102.0,5855,,"30,000",35855,,,,,,35855,,
38,Haier,Haier HWM 80-186 Twin Tub Washing Machine,82.0,50.0,101.0,5797,,"32,000",37797,,,,,,37797,,
````

## File: data/inputs/template.csv
````
Brand,Name,Net Price,Length,Width,Height,Profit
Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92,
Haier,Haier HW 90-BP12357S8 Front Load Washing Machine,130000,65,56,92,1000
````

## File: data/outputs/.gitkeep
````
# Keep directory in git
````

## File: docs/decisions/ADR-001-multi-pattern-waterfall-candidate-retrieval.md
````markdown
# ADR-001: Multi-Pattern Candidate Retrieval with Tiered Early-Exit Waterfall

## Status
Accepted

## Date
2026-09-28

## Context
Marketplace search APIs (AlfaMall and DigiMall / Faysal Bank) have heterogeneous and unstandardized search indexing:
- Sellers frequently alter spacing, hyphens, and prefixes (e.g. `120-826S6` vs `120 826S6` vs `HWM120-826S6`).
- TV models mix screen sizes with series codes (e.g. `50S80EUX` vs `50 S80EUX` vs `S80EUX`).
- Appliance models append optional marketing descriptors (`120-826S6 GC` vs `120-826S6 Glass Door`).

Searching with a single rigid string causes high false-negative rates (e.g. Item #20 returned 0 offers despite 9 active sellers). Conversely, blindly querying 4–5 variations simultaneously for all 768 products would quadruple API traffic (~3,500 HTTP requests), triggering WAF rate-limiting, socket exhaustion, and slow pipeline execution.

## Decision
Implement a **Multi-Pattern Candidate Retrieval Engine** powered by a **Tiered Early-Exit Waterfall**:

1. **Pattern Matrix Generation**:
   - `Tier 1 (Exact Clean)`: The canonical target SKU with spaces normalized (`120-826S6 GC`, `50S80EUX`).
   - `Tier 2 (Bare Alphanumeric Stem)`: Prefix and cosmetic tokens stripped (`120-826S6`, `S80EUX`).
   - `Tier 3 (Permutated Stem)`: Glued/spaced/hyphenated variations (`120 826S6`, `50 S80EUX`, `HWM-120-826S6`).

2. **Waterfall Early-Exit Execution**:
   - Query **Tier 1** first.
   - If Tier 1 returns $\ge 2$ valid candidate offers, **terminate search immediately** (saving 75–80% network I/O).
   - Only if Tier 1 returns $<2$ candidates, cascade sequentially to **Tier 2**, and finally **Tier 3**.
   - Merge candidates into a deduplicated `CandidatePool` keyed by `(vendor_name.lower(), price, raw_title.lower())`.

3. **In-Memory Cache & Concurrency**:
   - Query responses cached in a run-scoped memory dictionary `_query_cache[(platform, query)]`.
   - Concurrency bounded via `asyncio.Semaphore(3)` with 0.1s micro-staggering to prevent Cloudflare/WAF throttling.

## Alternatives Considered

### 1. Single Strict Search Query
- Pros: Minimal network calls (1 request per platform).
- Cons: High false-negative rate and false monopolies due to vendor spelling variance.
- Rejected: Directly caused the Item #20 bug (9 sellers lost).

### 2. Full Parallel Broadcast (Query all 5 patterns simultaneously for every item)
- Pros: Simple code, maximum candidate recall in one step.
- Cons: 4x–5x network load, high risk of WAF bans, significant latency overhead for the 80% of items that match on the first query.
- Rejected: Unsustainable at 768-product catalog scale.

## Consequences
- 80%+ of products resolve on Tier 1 in $<300$ms.
- 0 false monopolies caused by trivial hyphen or space differences.
- Network footprint remains bounded and WAF-safe.
````

## File: docs/decisions/ADR-002-four-slot-attribute-extraction-and-negative-collision.md
````markdown
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
````

## File: docs/decisions/ADR-003-autonomous-cooccurrence-learning-and-cloud-sync.md
````markdown
# ADR-003: Autonomous Co-Occurrence Learning, Confidence Gates, and Cloud Sync

## Status
Accepted

## Date
2026-09-28

## Context
When marketplace sellers use informal or natural language synonyms (e.g. using `Glass Door` instead of `GC`), the system must recognize this equivalence dynamically. Hardcoding synonyms in Python code requires developer intervention for every new market phrasing. However, blindly auto-approving any co-occurring phrase risks poisoning the matching engine with seller typos or erroneous listings.

## Decision
Implement a **Statistical Co-Occurrence Miner** with a strict **Multi-Seller Confirmation Gate** and cloud persistence via Supabase:

### 1. Passive Title Observation
During standard pricing sweeps, every accepted candidate's residual tokens are paired with the target's residual tokens:
$$\text{Observation} = (\text{Brand}, \text{AnchorModel}, \text{TargetResidual}, \text{CandidateResidual})$$

### 2. Multi-Seller Confirmation Gate ($\ge 3$ Distinct Vendors)
- **Candidate State**: An observed synonym or mapping is held as `CANDIDATE` if observed $<3$ times.
- **Approved State**: An equivalence is automatically promoted to `APPROVED` only when $\ge 3$ distinct, verified seller listings confirm the exact same mapping with zero contradictory signals.
- **Conflict Quarantine**: If two listings provide contradictory mappings for the same anchor (e.g. one seller associates `GC` with `Glass Cover` and another with `Grey Color`), the token is immediately quarantined with `status = 'CONFLICT'` and flagged for audit.

### 3. Cloud Synchronization & Zero-Latency Caching
- **Supabase Cloud PostgreSQL**: Serves as the durable, append-only source of truth (`capacity_registry` and `learning_observations`).
- **In-Memory Local Mirror**: The approved registry is pre-loaded at startup into an in-memory dictionary, ensuring zero-latency ($<0.01$ms) lookups during high-speed repricing loops.
- **Graceful Offline Fallback**: If Supabase credentials are missing or the network drops, the engine falls back to local memory without halting or crashing the pricing sweep.

## Alternatives Considered

### 1. Instant Auto-Approval on First Sight
- Pros: Immediate learning.
- Cons: A single seller typo or fraudulent listing permanently pollutes the database.
- Rejected: Unsafe for production financial calculations.

### 2. Manual Human Review for All Discovered Terms
- Pros: 100% human-verified.
- Cons: High operational burden, defeats the purpose of autonomous repricing.
- Rejected: Doesn't scale.

## Consequences
- The repricing engine gets smarter with every catalog run without code changes.
- Multi-seller confirmation prevents hallucinations and seller typos from corrupting matches.
- Full auditability via append-only observation logs in Supabase.
````

## File: docs/decisions/ADR-004-catalog-ingestion-and-timestamped-export.md
````markdown
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
````

## File: pricing_engine/__init__.py
````python
"""AlfaMall & DigiMall Dynamic Repricing Automation Engine."""

__version__ = "1.0.0"
````

## File: pricing_engine/learner.py
````python
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

INVALID_METRIC_UNITS: set[str] = {
    "KG",
    "TON",
    "ΤΟN",
    "LTR",
    "LITRE",
    "INCH",
    "FT",
    "FEET",
    "MM",
    "CM",
    "GM",
}


def is_valid_residual_token(token: str) -> bool:
    """Validate that a token is a legitimate cosmetic/feature modifier and not a number or metric.

    Enforces Reviewer Guard 2:
    - Digits are strictly forbidden (numbers belong to anchors, capacities, or specs).
    - Minimum length >= 2 to reject single-letter noise.
    - Standard metric unit tokens are explicitly rejected.
    """
    clean = token.strip("-_., \"'")
    if len(clean) < 2:
        return False

    # Residuals can NEVER contain numbers (prevents anchor and metric leakage)
    if any(char.isdigit() for char in clean):
        return False

    return clean.upper() not in INVALID_METRIC_UNITS


def normalize_merchant_name(name: str) -> str:
    """Normalize vendor name into an invariant lowercase alphanumeric ID.

    Enforces Reviewer Guard 3:
    Prevents Sybil attacks and duplicate listings from acting as multiple distinct vendors.
    """
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def is_valid_synonym_candidate(target_res: str, cand_res: str) -> bool:
    """Evaluate if a target/candidate residual pair represents a viable synonym candidate.

    Enforces Reviewer Guard 6:
    - Symmetric Non-Empty Guard: Both sides must be non-empty and valid tokens.
    - Ratio Guard: Prevents mapping a 1-token acronym to 4+ words of marketing fluff.
    """
    if not is_valid_residual_token(target_res) or not is_valid_residual_token(cand_res):
        return False

    t_words = target_res.split()
    c_words = cand_res.split()

    return not (len(c_words) > 3 * len(t_words) or len(t_words) > 3 * len(c_words))


class AutonomousLearner:
    """Autonomous market observation accumulator and consensus promotion miner.

    Adheres to ADR-003 and Reviewer Guards 1, 2, 3, 4, 6:
    - In-Memory Observation Buffer (prevents N+1 REST API flooding).
    - Category-bounded polysemy isolation.
    - Sybil-resistant distinct merchant consensus gate (>= 3 distinct normalized vendors).
    """

    def __init__(self) -> None:
        self._buffer: list[dict[str, Any]] = []

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

    def clear_buffer(self) -> None:
        self._buffer.clear()

    def buffer_observation(
        self,
        brand: str,
        category: str,
        anchor_model: str,
        target_residual: str,
        candidate_residual: str,
        vendor_name: str,
        raw_title: str,
    ) -> bool:
        """Validate and append an observed market difference to the in-memory batch buffer.

        Returns:
            True if observation was valid and buffered, False otherwise.
        """
        # Reviewer Guard 1: Category MUST NOT be empty
        clean_category = category.strip().upper()
        if not clean_category:
            return False

        clean_brand = brand.strip().upper()
        if not clean_brand:
            return False

        # Reviewer Guards 2 & 6: Validate tokens and symmetric ratio
        if not is_valid_synonym_candidate(target_residual, candidate_residual):
            return False

        # Reviewer Guard 3: Normalize merchant for Sybil defense
        norm_merchant = normalize_merchant_name(vendor_name)
        if not norm_merchant:
            return False

        observation = {
            "brand": clean_brand,
            "category": clean_category,
            "anchor_model": anchor_model.strip().upper(),
            "target_residual": target_residual.strip().upper(),
            "candidate_residual": candidate_residual.strip().upper(),
            "vendor_name": vendor_name.strip(),
            "normalized_merchant": norm_merchant,
            "raw_title": raw_title.strip(),
        }
        self._buffer.append(observation)
        return True

    async def flush_observations(self, client: Any) -> int:
        """Bulk flush all buffered observations to Supabase in a single batch POST.

        Enforces Reviewer Guard 4 (N+1 REST flooding prevention).
        """
        if not self._buffer or not client:
            return 0

        to_flush = list(self._buffer)
        try:
            recorded = await client.record_observations_batch(to_flush)
            self.clear_buffer()
            return recorded
        except Exception as exc:
            logger.warning("Flush observations failed gracefully: %s", exc)
            return 0

    @staticmethod
    def count_distinct_merchants(observations: list[dict[str, Any]]) -> int:
        """Count unique normalized merchants from an observation collection."""
        merchants: set[str] = set()
        for obs in observations:
            norm = obs.get("normalized_merchant")
            if not norm and obs.get("vendor_name"):
                norm = normalize_merchant_name(obs["vendor_name"])
            if norm:
                merchants.add(norm)
        return len(merchants)

    @staticmethod
    def is_consensus_reached(distinct_merchants: int, threshold: int = 3) -> bool:
        """Determine if observation has achieved multi-seller promotion consensus."""
        return distinct_merchants >= threshold
````

## File: tasks/approaches.md
````markdown
# Innovation Analysis: Universal Dynamic Product Matching Approaches

**Date:** 2026-10-01  
**Author:** Software Architect (Data Deduplication & Fuzzy Matching Systems)  
**Methodology:** RIPER Framework — Phase 2 (Innovate)  
**Subject:** 3 Viable Architectural Approaches for Zero-Dictionary Dynamic Search & Matching

---

## Comparative Matrix of Architectural Approaches

| Dimension | Approach 1: Structural Slot Grammar (Pure Regex Morphological) | Approach 2: Information-Theoretic Entropy & Dynamic Frequency Alignment | Approach 3: Dual-Stage Funnel: Cartesian Search Permutator + Negative-Collision Referee (Recommended) |
| :--- | :--- | :--- | :--- |
| **Dictionary Dependency** | **Zero** | **Zero** | **Zero** |
| **Search Breath (Stage 1)** | High | Moderate | **Maximum (Google-Style Cartesian Latticing)** |
| **Deduplication Robustness (Stage 2)** | High | Moderate | **Strict (Composite Vendor + Price + URL/Title Fingerprint)** |
| **Attribute Handling Logic (Stage 3)** | Strict Slot Grammar | Continuous Entropy Distance | **3-Tier Intelligent Asymmetry (Contradiction, Optionality, Target Omission)** |
| **Handling of Slashes (`/`)** | Partial | Heuristic | **Full Cartesian Lattice Expansion** |
| **Handling of Omitted Prefixes (`11lf`, `13hfn`)** | Static Regex Rules | Character Entropy Clustering | **Dynamic Brand-Initial Prefix Synthesis (`{B[0]}[A-Z]{1,3}-{Stem}`)** |
| **Latency & Performance** | Sub-millisecond | 5-15 ms (entropy calculations) | **Sub-millisecond (Pure Vectorized String Topology)** |
| **Test Suite Compatibility** | Requires rewriting tests | High regression risk | **100% Compatible with Existing 189 Passing Tests** |

---

## Detailed Evaluation of Approaches

### Approach 1: Structural Slot Grammar (Pure Regex Morphological)
* **How It Works**:
  Breaks any product string into a strict sequence of grammar tokens:
  `[BRAND] [PREFIX]? [STEM_NUMBER] [SUFFIX]? [CAPACITY_UNITS]? [DELIMITER_NOISE]?`
  Eliminates dictionaries by classifying tokens strictly by character types:
  - Digits with adjacent letters = SKU model.
  - Numbers followed by unit symbols (`"`, `Ton`, `Kg`, `L`) = Capacity.
  - Letters following a hyphen = Variant suffix.
* **Limitations**:
  Real marketplace titles frequently violate grammar (e.g. `Haier 1.5 Ton Solar Hybrid T3 Plus-By Electronics World`). Rigid grammatical slotting can misclassify `Solar Hybrid` as brand or noise.

---

### Approach 2: Information-Theoretic Entropy & Dynamic Frequency Alignment
* **How It Works**:
  Calculates token informativeness based on character diversity and rarity:
  $$\mathcal{H}(token) = -\sum_{c \in token} p(c) \log_2 p(c)$$
  - High entropy tokens (`TIFG1U1`, `11467`, `688S3`, `MXP9`, `45200`) are guaranteed product identifiers.
  - Low entropy tokens (`ac`, `on`, `the`, `with`, `free`, `all`) are dynamically treated as stop-words without maintaining a dictionary list.
* **Limitations**:
  Short high-priority model tokens (like `D2` in `32" D2` or `MB` in `HAF 50 MB`) have low character entropy and could be falsely categorized as noise.

---

### Approach 3: Dual-Stage Funnel: Cartesian Search Permutator + Negative-Collision Referee (RECOMMENDED)

Approach 3 synthesizes Google-style search recall with mathematically guaranteed negative-collision verification. It completely eradicates all hardcoded word lists and dictionaries.

#### Stage 1: Dynamic Multi-Pattern Search Generation (Google-Style Cartesian Lattice)
1. **Dynamic Model Extraction (Zero Brand/Category Lists)**:
   - Identify the **Core Numeric Stem ($S$)**: Any contiguous run of digits ($\ge 2$ digits, e.g. `418`, `538`, `11467`, `13`, `24`, `48`).
   - Extract **Dynamic Form Prefix ($P$)**: Check for 2-4 letter alpha runs immediately preceding or hyphenated with $S$.
   - **Dynamic Brand-Initial Synthesis**: If catalog gives a bare model without prefix (e.g. `11lf` or `13hfn`), synthesize the brand's standard form-factor prefixes:
     $$\mathcal{P}_{\text{synth}} = \{ \text{Brand}[0] + \text{Char} \mid \text{Char} \in \{\text{'RF'}, \text{'WM'}, \text{'SU'}, \text{'BU'}, \text{'PU'}, \text{'MO'}, \text{'AF'}\} \}$$
     e.g. for Haier: `HRF-11LF`, `HSU-13HFN`, `HWM-130`, `HAF-50`.
   - **Cartesian Slash Latticing**:
     If a model token or title contains slashes (e.g. `HRF-418 TIFG1U1/TIFB1U1` or `HGL-25MXP8 / 25MXP9` or `Sprinter / Powercon`):
     Factor the title into independent Cartesian branches:
     - Branch A: `HRF-418 TIFG1U1`
     - Branch B: `HRF-418 TIFB1U1`
     Each branch independently generates Tier 1, Tier 2, and Tier 3 query patterns.

2. **Tiered Query Breadth**:
   - **Tier 1 (Exact & Prefixed)**: Brand + Prefix + Stem + Suffix, Brand + Stem.
   - **Tier 2 (Bare Stem & Model Codes)**: Prefix + Stem, Bare Stem, Alternative Slash Models.
   - **Tier 3 (Permutations & Capacities)**: Stem with units (`24 2 Ton`, `18 1.5 Ton`, `32 Inch`), space-separated, hyphen-separated.

#### Stage 2: Deduplication Engine
- Composite Unique Key:
  $$\text{Key} = \left\langle \text{normalize}(\text{vendor\_name}),\; \text{round}(\text{price}, 2),\; \text{hash}(\text{normalized\_url} \lor \text{title\_fingerprint}) \right\rangle$$
- Eliminates duplicate listings returned across multiple tiers and search query hits before matching.

#### Stage 3: Intelligent Negative-Collision Attribute Referee
The referee evaluates candidates using **Asymmetric Attribute Logic (Zero Word Dictionaries)**:

1. **The Contradiction Rule (Negative Collision)**:
   $$\text{If } \text{Attr}_{\text{target}} \neq \emptyset \land \text{Attr}_{\text{cand}} \neq \emptyset \land \text{Attr}_{\text{target}} \neq \text{Attr}_{\text{cand}} \implies \mathbf{REJECT}$$
   - Example: Target has Capacity `2.0 Ton`, Candidate has `1.5 Ton` $\to$ **REJECT**.
   - Example: Target has Tub Finish `GB`, Candidate has `WB` $\to$ **REJECT**.
   - Example: Target has Color `White`, Candidate has `Silver` $\to$ **REJECT**.
   - Example: Target has Model Number `418`, Candidate has `458` $\to$ **REJECT**.

2. **The Optionality Rule (Candidate Omission)**:
   $$\text{If } \text{Attr}_{\text{target}} \neq \emptyset \land \text{Attr}_{\text{cand}} = \emptyset \implies \mathbf{ACCEPT}$$
   - Example: Target specifies Color `(Milky White)` or Revision `S3`, but Candidate simply lists `Haier Refrigerator HRF-418` without mentioning any color $\to$ **ACCEPT** (seller omitted non-mandatory marketing descriptor).

3. **The Specification Absence Rule (Target Omission)**:
   $$\text{If } \text{Attr}_{\text{target}} = \emptyset \land \text{Attr}_{\text{cand}} \neq \emptyset \implies \mathbf{ACCEPT}$$
   - Example: Target does not specify operational mode (e.g. `Cassette 18 HE/DC`), but Candidate lists `Heat and Cool` or `DC Inverter` $\to$ **ACCEPT** (candidate has extra descriptive attributes that do not collide with target).

4. **Hard Security Guards (T3, IoT, Inverter)**:
   - Target contains `IOT` $\implies$ Candidate must NOT explicitly say non-smart.
   - Target contains `T3` $\implies$ Candidate must NOT be standard T1 compressor.

---

## Conclusion & Recommendation

**Approach 3** is selected for implementation. It completely satisfies the user's requirement:
- **No hardcoded lists or dictionaries to maintain**.
- **Handles all 25 Haier failure cases** and existing Dawlance/Gree benchmarks.
- **Strict mathematical guarantee against false positive and false negative repricing**.
````

## File: tasks/haier-universal-matching-plan.md
````markdown
# Architecture Specification & Implementation Plan: Universal Zero-Dictionary Dynamic Search & Matching Engine

**Document:** `tasks/haier-universal-matching-plan.md`  
**Date:** 2026-10-01  
**Author:** Software Architect (Data Deduplication & Fuzzy Matching Systems)  
**Methodology:** RIPER Framework — Phase 3 (Plan)  
**Governing Standard:** `AGENTS.md` (Strict DRY, Zero Hardcoded Dictionaries, Deterministic Data Integrity)

---

## 1. Executive Summary & Architectural Vision

The mission of this architecture is to transition the repricing engine from **fragile static dictionaries** (`COLOR_FAMILIES`, `CATEGORY_PATTERNS`, `NON_SKU_TOKENS`, `MARKETPLACE_NOISE_RE`, `GENUINE_SUB_SERIES_TOKENS`) to a **Universal Dynamic Matching Algorithm** inspired by Google Search Engine query lattices and deterministic morphological analysis.

### Core Architectural Guarantee
1. **Zero Dictionaries / Pure DRY**: No hardcoded lists of brands, categories, seller names, colors, or stop-words. When a new brand, seller, or product category appears, the engine must handle it dynamically using character morphology, token entropy, and grammatical structure.
2. **Two-Stage Funnel**:
   - **Stage 1 (Google-Style Cartesian Search Generator)**: Exhaustive query breadth across Tier 1 (exact/prefixed), Tier 2 (bare stem/model code), and Tier 3 (permutations/capacities).
   - **Stage 2 (Deduplication Engine)**: Robust deduplication of search results across all queries into a clean candidate pool.
   - **Stage 3 (Unified Intelligent Model Referee)**: Multi-attribute asymmetric comparison with zero false monopolies and strict negative-collision protection.

---

## 2. Comprehensive Gap & Issue Analysis of Previous Implementation

Empirical diagnostic against live storefront APIs (AlfaMall & DigiMall) identified **6 fundamental design gaps** in `tasks/plan.md` and `matcher.py`:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CURRENT MATCHER ANTI-PATTERNS                         │
├──────────────────────────────┬──────────────────────────────┬───────────────┤
│ Anti-Pattern                 │ Example Failure Mode         │ Consequence   │
├──────────────────────────────┼──────────────────────────────┼───────────────┤
│ 1. Static Category Regex     │ '24 HD/Z W' has 'HD'         │ Mangled into  │
│    (CATEGORY_PATTERNS)       │ stripped as 'HD TV'          │ 'Haier /Z 24' │
│                              │                              │ (0 hits)      │
├──────────────────────────────┼──────────────────────────────┼───────────────┤
│ 2. False Slash Splitting     │ '24 HE/DC' split into        │ Searched 'HE' │
│    on Technical Codes        │ alternative series 'HE', 'DC'│ and 'DC', lost│
│                              │                              │ 'HE/DC' code  │
├──────────────────────────────┼──────────────────────────────┼───────────────┤
│ 3. Slash Alternative Dropping│ 'HGL-25MXP8 / 25MXP9'        │ Searched only │
│    in Multi-Model Catalog    │ dropped '/ 25MXP9'           │ 25MXP8, missed│
│                              │                              │ 25MXP9 portal │
├──────────────────────────────┼──────────────────────────────┼───────────────┤
│ 4. Omitted Form-Factor       │ '11lf' refrigerator searched │ Missed portal │
│    Prefixes in Bare Stems    │ as 'Haier 11lf'              │ listings named│
│                              │                              │ 'HRF-11LF'    │
├──────────────────────────────┼──────────────────────────────┼───────────────┤
│ 5. Rigid Tonnage Conversion  │ 'Solar hybrid 1.5ton' turned │ Real sellers  │
│    vs Marketplace Wording    │ into 'Haier Solar 18'        │ write 'Solar  │
│                              │                              │ Hybrid 1.5'   │
├──────────────────────────────┼──────────────────────────────┼───────────────┤
│ 6. Noise Cleaner Blinding    │ 'Cassette 48 HE/DC COOL ONLY'│ 'COOL ONLY'   │
│    Operational Disparities   │ stripped 'COOL ONLY' as noise│ matched 'Heat │
│                              │                              │ & Cool' AC    │
└──────────────────────────────┴──────────────────────────────┴───────────────┘
```

---

## 3. The 3-Stage Universal Architecture (Zero Dictionaries)

```mermaid
graph TD
    A["Catalog Title: e.g. '24 HD/Z W' or 'HRF-418 TIFG1U1/TIFB1U1 (IOT)'"] --> B["Stage 1: Dynamic Morphological Decomposer"]
    B --> B1["Extract Numeric Stem: '24' / '418'"]
    B --> B2["Extract Prefix/Form Factor: 'HRF' / '{Brand[0]}*'"]
    B --> B3["Detect Slashes: Alternative (OR) vs Technical Compound"]
    
    B --> C["Stage 1.2: Google-Style Cartesian Query Generator"]
    C --> C1["Tier 1: Canonical, Prefixed, Hyphenated & Compound"]
    C --> C2["Tier 2: Bare Model Stems & Alternative Slash Codes"]
    C --> C3["Tier 3: Spaced Permutations & Unit Variations"]
    
    C --> D["Network: Async API Querying across AlfaMall & DigiMall"]
    D --> E["Stage 2: Deterministic Deduplication Engine"]
    E --> E1["Composite Key: (Vendor, Price, Hash(Title/URL))"]
    E --> E2["Preserve Duplicate Counts for Telemetry"]
    
    E2 --> F["Stage 3: Intelligent Asymmetric Model Referee"]
    F --> G{"Model Code / Numeric Stem Match?"}
    G -- "No" --> REJ1["REJECT (Anchor Mismatch)"]
    G -- "Yes" --> H{"Guarded Facet Collision?<br/>(Capacity, T3, Finish WB/GB)"}
    H -- "Yes" --> REJ2["REJECT (Facet Collision)"]
    H -- "No" --> I{"Attribute Asymmetry Matrix"}
    I -- "Contradiction (White vs Silver)" --> REJ3["REJECT (Attribute Collision)"]
    I -- "Vendor Omission (Target specifies, Candidate omits)" --> ACC1["ACCEPT (Optionality)"]
    I -- "Target Omission (Candidate adds non-conflicting info)" --> ACC2["ACCEPT (Descriptive Add-on)"]
    ACC1 --> WIN["Calculated Winning Repriced Output"]
    ACC2 --> WIN
```

---

## 4. Stage 1: Google-Search-Engine-Style Multi-Pattern Generator

### 4.1. Morphological Entity Extraction (Zero Category Lists)
Instead of matching titles against a static list of 100 categories, token types are identified by **character syntax and positional entropy**:

1. **Numeric Stem ($\mathcal{S}_{\text{stem}}$)**:
   - Contiguous integer runs ($\ge 2$ digits, e.g. `418`, `538`, `11467`, `45200`, `18`, `24`, `48`).
   - Compound numeric models: `130-688`, `62 MX80`.
2. **Dynamic Prefix ($\mathcal{P}$)**:
   - 2 to 4 letters preceding or hyphenated to the numeric stem: `\b([A-Za-z]{2,4})[- ]?{stem}\b`.
   - Examples: `HRF` in `HRF-418`, `HWM` in `HWM-130`, `DWT` in `DWT-11467`, `HAF` in `HAF 50 MB`.
3. **Dynamic Brand-Initial Prefix Synthesis**:
   - If catalog provides a bare stem without prefix (e.g. `11lf`, `13hfn`, `48 EDC`, `45200`), search engines synthesize brand-initial queries:
     $$\mathcal{Q}_{\text{brand}} = \text{Brand} + \text{" "} + \text{Stem}$$
     $$\mathcal{Q}_{\text{prefix}} = \text{Brand}[0] + \text{"*"} + \text{Stem} \quad (\text{e.g. } \text{H*11LF}, \text{H*13HFN})$$
4. **Slash Classification (Alternative vs Technical Compound)**:
   $$\text{Classification} = \begin{cases} 
   \text{Technical Compound} & \text{if suffix after } / \in \{\text{'DC'}, \text{'AC'}, \text{'Z'}, \text{'KB'}\} \lor \text{len} \le 2 \\
   \text{Alternative (OR Branch)} & \text{if both sides are alphanumeric models or series names}
   \end{cases}$$
   - `24 HE/DC` $\longrightarrow$ Technical Compound: `HE/DC`, `HEDC`, `HE-DC`.
   - `24 HD/Z W` $\longrightarrow$ Technical Compound: `24HDZ`, `24 HDZ`, `24 HD/Z`.
   - `HRF-418 TIFG1U1/TIFB1U1` $\longrightarrow$ Cartesian OR Branches:
     - Branch 1: `HRF-418 TIFG1U1`
     - Branch 2: `HRF-418 TIFB1U1`
   - `HGL-25MXP8 / 25MXP9` $\longrightarrow$ Cartesian OR Branches:
     - Branch 1: `HGL-25MXP8` / `25MXP8`
     - Branch 2: `HGL-25MXP9` / `25MXP9`

### 4.2. Universal 3-Tier Query Hierarchy

| Tier | Purpose | Generated Formats | Example (`Cassette 18 HE/DC`) | Example (`HRF-418 TIFG1U1/TIFB1U1`) |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (Exact & Canonical)** | Highest precision hits; exact portal titles | `Brand + Full Model`, `Brand + Hyphenated SKU` | `Haier Cassette 18`, `Haier 18 HE/DC` | `Haier HRF-418 TIFG1U1`, `Haier HRF-418 TIFB1U1` |
| **Tier 2 (Bare Stems & Model Codes)** | Resilient against sellers omitting brand or form words | `Bare Stem`, `Model Code without Brand`, `Branch Alternatives` | `Cassette 18`, `18 HE/DC`, `HBU-18` | `HRF-418`, `418 TIFG1U1`, `418 TIFB1U1` |
| **Tier 3 (Permutations & Capacities)** | Catches space/hyphen drift, glued codes, unit synonyms | `Glued`, `Spaced`, `Capacity conversions` (`1.5 Ton`, `5L`, `32 Inch`) | `Haier 1.5 Ton Cassette`, `Haier HBU 18` | `HRF 418`, `HRF418`, `Haier 418` |

---

## 5. Stage 2: Deduplication Engine

When querying multiple tiers and Cartesian branches, duplicate listings naturally return. The deduplication engine guarantees pure unique offers:

### Composite Unique Key
$$\text{Dedupe Key} = \left\langle \text{lower}(\text{strip}(\text{vendor\_name})),\; \text{round}(\text{price}, 2),\; \mathcal{H}(\text{raw\_title}) \right\rangle$$

- **Vendor Normalization**: Strips whitespace, case-folded.
- **Price Precision**: Rounded to 2 decimal places to absorb floating-point differences.
- **Title Fingerprint $\mathcal{H}$**: Normalized alphanumeric token hash, stripping variable session tokens or query IDs.
- **Duplicate Counting**: Preserved in `ScrapedOffer.duplicate_count` to record competitor stock density and marketplace presence in audit logs.

---

## 6. Stage 3: Intelligent Asymmetric Model Referee (Zero Dictionaries)

The referee decides whether a candidate listing is the identical commercial product using **Asymmetric Attribute Rules**:

### 6.1. The 3 Asymmetric Attribute Laws

```
                 Target Has Attribute?
                      ┌─────────┬─────────┐
                      │   YES   │   NO    │
  Candidate     ┌─────┼─────────┼─────────┤
  Has           │ YES │ Law 1   │ Law 3   │
  Attribute?    ├─────┼─────────┼─────────┤
                │ NO  │ Law 2   │   N/A   │
                └─────┴─────────┴─────────┘
```

#### Law 1: The Contradiction Law (Both Specify $\implies$ Strict Precision Match)
$$\text{Attr}_{\text{target}} \neq \emptyset \land \text{Attr}_{\text{cand}} \neq \emptyset \implies (\text{Attr}_{\text{target}} = \text{Attr}_{\text{cand}} \lor \mathbf{REJECT})$$
- Target: `Cassette 48 HE/DC COOL ONLY` vs Candidate: `Heat and Cool` $\implies$ **REJECT**.
- Target: `30 Magna T3` vs Candidate: `15 Magna T3` $\implies$ **REJECT** (Capacity mismatch).
- Target: `DW 10095 GB` vs Candidate: `DW 10095 WB` $\implies$ **REJECT** (Hardware tub mismatch).
- Target: `White` vs Candidate: `Silver` or `Black` $\implies$ **REJECT** (Color collision).

#### Law 2: The Optionality Law (Target Specifies, Candidate Omits $\implies$ ACCEPT)
$$\text{Attr}_{\text{target}} \neq \emptyset \land \text{Attr}_{\text{cand}} = \emptyset \implies \mathbf{ACCEPT}$$
- Target: `30 Magna T3 INV (Milky White Textured)`.
- Candidate: `Dawlance Magna 30 T3 Inverter AC` (no color mentioned).
- Verdict: **ACCEPT**. Pakistani marketplace sellers frequently omit cosmetic colors on single-color model runs. Rejecting this creates a false monopoly.

#### Law 3: The Target Omission Law (Target Omits, Candidate Adds $\implies$ ACCEPT)
$$\text{Attr}_{\text{target}} = \emptyset \land \text{Attr}_{\text{cand}} \neq \emptyset \implies \mathbf{ACCEPT}$$
- Target: `Cassette 18 HE/DC`.
- Candidate: `Haier 1.5 Ton 4 Way Cassette Type Inverter Air Conditioner HBU-18 HE/DC | Free Installation By Haier`.
- Verdict: **ACCEPT**. The candidate includes extra descriptive details (`4 Way`, `Type Inverter`, `Free Installation`) that do not contradict any target attribute.

### 6.2. Algorithmic Marketplace Noise Stripping (Zero Seller Dictionaries)
Instead of maintaining a static dictionary of seller names (`ELECTROEASE`, `HOMECART`), noise is eliminated via **syntactic boundaries**:
1. **Delimiter-Separated Trailer Stripping**:
   `re.sub(r"\s*[-|/]\s*(?:By\s+)?[A-Z][A-Za-z0-9\s]{2,}$", "", text)` strips trailing merchant signatures.
2. **Promotional Clause Stripping**:
   Matches transactional phrasing structurally:
   - Installments: `\b\d+%\s*Markup\b`, `\b(?:On\s+)?Installments?\b`, `\bUpto\s+\d+\s+Months\b`.
   - Warranties: `\b(?:\d+\s+Years?\s+)?(?:Official|Brand|Company)?\s*Warranty\b`.
   - Shipping: `\bFree\s+(?:Home\s+)?Delivery\b`, `\bFree\s+Installation\b`.
   - Stock IDs: `\b[A-Za-z]{2,5}[-_]?\d+\b` (e.g. `SNS29`, `UE010`, `ISPK-0577`).

---

## 7. Product-by-Product Verification Matrix (All 25 Haier SOLO Models)

Every failure case from the previous code is solved deterministically by the dynamic algorithm:

| # | Catalog Model | Root Cause in Old Code | Dynamic Algorithm Solution | Live API Outcome |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `11lf` | Bare stem without prefix | Synthesize `Haier 11lf`, `Haier 11 LF`, bare `11lf`. Referee matches dynamic `H` initial with `HRF-11LF`. | Matches `HRF-11LF` |
| 2 | `13hfn` | Bare stem without prefix | Generates `Haier 13hfn`, `HSU-13HFN`. Matches `HSU-13HFN(W)-T3`. | Matches `HSU-13HFN` |
| 3 | `Solar hybrid 1.5ton` | Mutilated to `Solar 18` | Generates `Haier Solar Hybrid 1.5`, `Haier Solar Hybrid 1.5 Ton`. Law 2 accepts extra portal tags. | Matches `Solar Hybrid-III(OW) 1.5 Ton` |
| 4 | `Solar hybrid 2ton` | Mutilated to `Solar 24` | Generates `Haier Solar Hybrid 2`, `Haier Solar Hybrid 2 Ton`. Law 2 accepts extra portal tags. | Matches `Solar Hybrid AC 2 TON T3` |
| 5 | `24 HD/Z W` | `HD` stripped by `CATEGORY_PATTERNS` | Eliminated category dictionary. Normalizes `/Z` to `HDZ`. Generates `Haier 24 HDZ`, `Haier 24 HD/Z`. | Matches `Haier 24HDZ (White)` |
| 6 | `24 HDZ UV` | `UV` dropped; stem decoupled | Keeps model code `24 HDZ` intact with `UV` modifier. Generates `Haier 24 HDZ UV`, `Haier 24 HDZ`. | Matches `24 HDZ with UV` |
| 7 | `24 HE/DC` | Split into `HE` OR `DC` | Recognizes `/DC` as technical rating, not alternative. Generates `Haier 24 HE/DC`, `Haier 24 HEDC`. | Matches `HBU-24 HE/DC` |
| 8 | `48 CE/DC` | Split into `CE` OR `DC` | Recognizes `/DC` as technical rating. Generates `Haier 48 CE/DC`, `HPU-48 CE/DC`. | Matches `HPU-48 CE/DC` |
| 9 | `48 EDC` | Missing commercial prefix | Generates `Haier 48 EDC`, `Haier EDC 48`. Referee matches `HPU-48 EDC`. | Matches `HPU-48 EDC` |
| 10 | `Cassette 18 HE/DC` | `Cassette` stripped; `HE/DC` split | Keeps `Cassette` & `18 HE/DC`. Generates `Haier Cassette 18`, `Haier 18 HE/DC`. | Matches `HBU-18 HE/DC` |
| 11 | `Cassette 24 HE/DC` | `Cassette` stripped; `HE/DC` split | Generates `Haier Cassette 24`, `Haier 24 HE/DC`. Matches `HBU-24 HE/DC`. | Matches `HBU-24 HE/DC` |
| 12 | `Cassette 48 HE/DC COOL ONLY` | `COOL ONLY` stripped as noise | Preserves operational facet `COOL ONLY`. Law 1 strictly rejects `Heat and Cool`. | Matches `HPU-48 HE/DC Cool Only` |
| 13 | `Cassette 48 HE/DC H & C` | `H & C` not normalized | Normalizes `H & C` $\iff$ `Heat and Cool`. Matches Heat & Cool, rejects Cool Only. | Matches `HPU-48 HE/DC Heat And Cool` |
| 14 | `HRF-418 TIFG1U1/TIFB1U1 (IOT)` | Required BOTH slash variants | Expands into Cartesian OR branches (`TIFG1U1` OR `TIFB1U1`). Matches either variant. | Matches `HRF-418 TIFG1U1 IOT` |
| 15 | `HRF-458 TIFG1U1/TIFB1U1 (IOT)` | Required BOTH slash variants | Expands into Cartesian OR branches. Matches either variant. | Matches `HRF-458 TIFG1U1 / TIFB1U1` |
| 16 | `HRF-538 TIFG1U1/TIFB1U1 (IOT)` | Required BOTH slash variants | Expands into Cartesian OR branches. Matches either variant. | Matches `HRF-538 TIFG1U1 IOT` |
| 17 | `HRF-578 TGGU1 (IOT)` | Parentheses `(IOT)` collided | Preserves `IOT` guarded facet; normalizes model anchor `HRF-578 TGGU1`. | Matches `HRF-578-TGGU1-IOT` |
| 18 | `HRF-585SFFGU1` | Glued stem + suffix | Dynamic de-gluing parses `585` stem and `SFFGU1` suffix. Generates spaced & glued queries. | Matches `HRF-585 SFFGU1` |
| 19 | `HWM-130-688S3` | Compound stem `130-688` split | Preserves compound numeric stem `130-688`. Matches chassis. | Matches `HWM-130-688S3` |
| 20 | `32" D2` | Quotes corrupted capacity | Strips quotes cleanly; extracts screen size `32` and model `D2`. Generates `Haier 32 D2`. | Matches `Haier 32" Smart LED D2` |
| 21 | `HGL-25MXP8 / 25MXP9` | Dropped `/ 25MXP9` | Expands Cartesian OR branches (`25MXP8` OR `25MXP9`). Searches both models independently. | Matches `HMW-25MXP9` & `25MXP8` |
| 22 | `HMO-45200` | Drift between `HMO` and `HMN` | Generates bare stem `Haier 45200` alongside `HMO-45200`. Catches `HMN-45200` listings. | Matches `HMN-45200` & `HMO 45200` |
| 23 | `HMO-62 MX80` | Spaced compound code split | Normalizes compound code `62MX80` and `62 MX80`. Generates both queries. | Matches `HMN-62MX80` |
| 24 | `HAF 50 MB` | Missed hyphenated query | Generates hyphenated `Haier HAF-50MB` + bare `50MB`. Matches manual air fryer. | Matches `HAF-50MB` |
| 25 | `HAF 50 DB` | Missed hyphenated query | Generates hyphenated `Haier HAF-50DB` + bare `50DB`. Matches digital air fryer. | Matches `HAF-50DB` |

---

## 8. Measurable Success Criteria & Quality Gates

To confirm complete fulfillment of the goal, the system must pass the following verifiable gates:

1. **Gate 1: Existing Test Suite Integrity**:
   - Complete `pytest -v` run must pass with **100% green** (all 189+ tests passing).
2. **Gate 2: Haier Benchmark Coverage**:
   - New dedicated benchmark suite `tests/test_haier_benchmark.py` verifying model extraction, pattern generation, deduplication, and referee decisions for all 25 Haier products.
3. **Gate 3: Zero Hardcoded Dictionaries**:
   - `pricing_engine/matcher.py` contains zero static dictionaries or lists of categories, seller names, or brand prefixes.
4. **Gate 4: Deterministic Data Integrity**:
   - Column 1 `S.NO` guaranteed.
   - Zero `.0` float drift on prices.
   - Clean ANSI-free risk alerts.

---

## 9. Phased Execution Roadmap

- **Step 1**: Refactor `pricing_engine/matcher.py`:
  - Implement dynamic morphological decomposer and Cartesian slash expander.
  - Implement technical compound slash classifier (`HE/DC`, `HD/Z`).
  - Implement structural noise stripper (zero seller dictionary).
  - Implement 3 Asymmetric Attribute Laws in `referee_match`.
- **Step 2**: Update `pricing_engine/scraper.py`:
  - Enhance composite deduplication key with duplicate counting.
  - Align raw items cache to support all Cartesian branches.
- **Step 3**: Create `tests/test_haier_benchmark.py`:
  - Add comprehensive test cases for all 25 Haier benchmark products.
- **Step 4**: Run full verification suite (`pytest -v`, `ruff check .`).
- **Step 5**: Review output artifacts and document final report.
````

## File: tasks/research-notes.md
````markdown
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
````

## File: tests/fixtures/Gree_Uploading_on_DigiMall_and_Price.csv
````
S.NO,Brand,Name ,Length,Width,Height,Shipping Estimate,Commision,Net Price,Total Without Profit,Minimum Price Alfa,Maximum Price Alfa,Minimum Price Digi,Maximum Price Digi,Profit,Calculation,Final Price Alfa,Final Price Digi
1,Gree,GREE FLOOR STANDING 36TFIH AA+,127,43,200,15291,,"415,000",430291,,,,,,430291,,
2,Gree,GREE SPLIT AC 12AITH21W-T3,87,35.5,92,3978,,"147,000",150978,,,,,,150978,,
3,Gree,GREE SPLIT AC 12AITH24S-T3,87,35.5,92,3978,,"172,000",175978,,,,,,175978,,
4,Gree,GREE SPLIT AC 18AITH21B-T3,104,39,103,5849,,"183,000",188849,,,,,,188849,,
5,Gree,GREE SPLIT AC 18AITH21W-T3,104,39,103,5849,,"183,000",188849,,,,,,188849,,
6,Gree,GREE SPLIT AC 18AITH24S-T3,104,39,103,5849,,"226,000",231849,,,,,,231849,,
7,Gree,GREE SPLIT AC 18PITH11G AAA,103,38.5,102,5663,,"143,000",148663,,,,,,148663,,
8,Gree,GREE SPLIT AC 18PITH11W AAA,103,38.5,102,5663,,"140,000",145663,,,,,,145663,,
9,Gree,GREE SPLIT AC 24AITH21B-T3,108,43,114,7412,,"236,000",243412,,,,,,243412,,
10,Gree,GREE SPLIT AC 24AITH21W-T3,108,43,114,7412,,"236,000",243412,,,,,,243412,,
11,Gree,GREE SPLIT AC 24PITH11S SILVER,106,42,110,6856,,"212,000",218856,,,,,,218856,,
12,Gree,GREE SPLIT AC 24PITH14S SILVER,106,42,110,6856,,"212,000",218856,,,,,,218856,,
13,Gree,GREE SPLIT AC GS-12PITH15G-T3,87,35.5,92,3978,,"131,500",135478,,,,,,135478,,
14,Gree,GREE SPLIT AC GS-12PITH15W-T3,87,35.5,92,3978,,"129,000",132978,,,,,,132978,,
15,Gree,GREE SPLIT AC GS-12PITH17G-T3,87,35.5,92,3978,,"131,500",135478,,,,,,135478,,
16,Gree,GREE SPLIT AC GS-12PITH17W-T3,87,35.5,92,3978,,"129,000",132978,,,,,,132978,,
17,Gree,GREE SPLIT AC GS-12ZITH2W-T3,88,36,93,4125,,"133,000",137125,,,,,,137125,,
18,Gree,GREE SPLIT AC GS-18PITC12W-T3,103,38.5,102,5663,,"153,000",158663,,,,,,158663,,
19,Gree,GREE SPLIT AC GS-18PITH15G-T3,103,38.5,102,5663,,"158,000",163663,,,,,,163663,,
20,Gree,GREE SPLIT AC GS-18PITH17G-T3,103,38.5,102,5663,,"158,000",163663,,,,,,163663,,
21,Gree,GREE SPLIT AC GS-18ZITH2W-T3,104,39,103,5849,,"164,000",169849,,,,,,169849,,
22,Gree,GREE SPLIT AC GS-24PITH15G-T3,106,42,110,6856,,"220,000",226856,,,,,,226856,,
23,Gree,GREE SPLIT AC GS-24PITH15W-T3,106,42,110,6856,,"219,000",225856,,,,,,225856,,
24,Gree,GREE SPLIT AC GS-24PITH17G-T3,106,42,110,6856,,"220,000",226856,,,,,,226856,,
25,Gree,GREE SPLIT AC GS-24ZITH1W-T3,107,42.5,112,7130,,"222,000",229130,,,,,,229130,,
````

## File: tests/fixtures/Haier_Washing_Machines_Uploading_and_Price.csv
````
S.NO,Brand,Name ,Length,Width,Height,Shipping Estimate,Commision,Net Price,Total Without Profit,Minimum Price Alfa,Maximum Price Alfa,Minimum Price Digi,Maximum Price Digi,Profit,Calculation,Final Price Alfa,Final Price Digi
1,Haier,Haier HW 105-BD14376PGU1 Front Load Washing Machine,65.0,57.0,92.0,4772,,"170,000",174772,,,,,,174772,,
2,Haier,Haier HW 90-BP12357S8 Front Load Washing Machine,65.0,56.0,92.0,4688,,"130,000",134688,,,,,,134688,,
3,Haier,Haier HW 100-BP12357S8 Front Load Washing Machine,65.0,59.0,92.0,4939,,"140,000",144939,,,,,,144939,,
4,Haier,Haier HW 120-BP12357S8 Front Load Washing Machine,65.0,62.0,92.0,5191,,"153,000",158191,,,,,,158191,,
5,Haier,Haier 100-316 HS8 Automatic Washing Machine,62.4,63.4,101.0,5594,,"63,000",68594,,,,,,68594,,
6,Haier,Haier 130-688S8 Automatic Washing Machine,66.0,66.0,105.0,6403,,"77,000",83403,,,,,,83403,,
7,Haier,Haier 110-688S8 Automatic Washing Machine,64.0,65.0,103.0,5999,,"64,000",69999,,,,,,69999,,
8,Haier,Haier 90-826E Automatic Washing Machine,61.0,62.0,98.0,5189,,"52,500",57689,,,,,,57689,,
9,Haier,Haier HWM-150-B699S8 Automatic Washing Machine,68.0,68.0,108.0,6991,,"96,000",102991,,,,,,102991,,
10,Haier,Haier 150-688S8 Automatic Washing Machine,68.0,68.0,108.0,6991,,"84,000",90991,,,,,,90991,,
11,Haier,Haier HWM-130-B699S8 Automatic Washing Machine,66.0,66.0,105.0,6403,,"87,000",93403,,,,,,93403,,
12,Haier,Haier 100-316S6 Automatic Washing Machine,62.4,63.4,101.0,5594,,"60,500",66094,,,,,,66094,,
13,Haier,Haier 120-316S6 Automatic Washing Machine,66.0,66.0,105.0,6403,,"72,500",78903,,,,,,78903,,
14,Haier,Haier 150-826S6 GC Automatic Washing Machine,68.0,65.0,98.0,6064,,"76,000",82064,,,,,,82064,,
15,Haier,Haier HWM 100-1269 Automatic Washing Machine,62.0,63.0,102.0,5578,,"51,000",56578,,,,,,56578,,
16,Haier,Haier 150-316S6 Automatic Washing Machine,68.0,68.0,108.0,6991,,"80,000",86991,,,,,,86991,,
17,Haier,Haier 110-B688S8 Automatic Washing Machine,64.0,65.0,103.0,5999,,"70,000",75999,,,,,,75999,,
18,Haier,Haier 100-826S6 Automatic Washing Machine,63.0,63.0,98.0,5445,,"57,000",62445,,,,,,62445,,
19,Haier,Haier HWM 95-1678 ES8 Automatic Washing Machine,61.0,62.0,100.0,5295,,"66,000",71295,,,,,,71295,,
20,Haier,Haier 120-826S6 GC Automatic Washing Machine,65.0,63.0,98.0,5618,,"69,000",74618,,,,,,74618,,
21,Haier,Haier HWM 120-826 Automatic Washing Machine,65.0,63.0,98.0,5618,,"69,000",74618,,,,,,74618,,
22,Haier,Haier HWM 95-1678 E Automatic Washing Machine,61.0,62.0,100.0,5295,,"66,000",71295,,,,,,71295,,
23,Haier,Haier HWM 60-50 Single Tub Washing Machine,49.0,51.0,89.0,3114,,"17,000",20114,,,,,,20114,,
24,Haier,Haier HWM-120-35 Single Tub Washing Machine,56.0,60.0,115.0,5410,,"24,000",29410,,,,,,29410,,
25,Haier,Haier HWM-80-CS Twin Tub Semi-Automatic Washing Machine,82.0,50.0,102.0,5855,,"26,000",31855,,,,,,31855,,
26,Haier,Haier HWM 80-60 Single Tub Washer Washing Machine,52.0,55.0,100.0,4004,,"18,500",22504,,,,,,22504,,
27,Haier,Haier HWM 60-50 Single Tub Washing Machine,49.0,51.0,89.0,3114,,"17,000",20114,,,,,,20114,,
28,Haier,Haier HWM 80-60 Single Tub Washer Washing Machine,52.0,54.0,95.0,3735,,"18,500",22235,,,,,,22235,,
29,Haier,Haier HWM 130-1217 WB Single Tub Washing Machine,56.0,58.0,115.0,5229,,"25,000",30229,,,,,,30229,,
30,Haier,Haier HWM 130-1217 GB Single Tub Washing Machine,56.0,58.0,115.0,5229,,"25,000",30229,,,,,,30229,,
31,Haier,Haier HWM 130-1217 E Single Tub Washing Machine,56.0,58.0,115.0,5229,,"24,000",29229,,,,,,29229,,
32,Haier,Haier 8 Kg Single Tub HWM 80-1217WB Washer Washing Machine,52.0,55.0,100.0,4004,,"19,500",23504,,,,,,23504,,
33,Haier,Haier 7.5 Kg HWM 75-AS Twin Tub Semi-Automatic Washing Machine,82.0,50.0,97.0,5568,,"24,500",30068,,,,,,30068,,
34,Haier,Haier HWM 100-196S 10 Kg Twin Tub Washing Machine,82.0,50.0,102.0,5855,,"31,500",37355,,,,,,37355,,
35,Haier,Haier 10 KG HWM 100-1217-WB Twin Tub Semi Automatic Washing Machine,92.0,56.0,106.0,7646,,"30,500",38146,,,,,,38146,,
36,Haier,Haier 10 KG HWM-100-196G Twin Tub Semi Automatic Washing Machine,82.0,50.0,102.0,5855,,"31,500",37355,,,,,,37355,,
37,Haier,Haier 10 Kg HWM-100-196E Twin Tub Semi-Automatic Washing Machine,82.0,50.0,102.0,5855,,"30,000",35855,,,,,,35855,,
38,Haier,Haier HWM 80-186 Twin Tub Washing Machine,82.0,50.0,101.0,5797,,"32,000",37797,,,,,,37797,,
````

## File: tests/fixtures/Stock Holding Report - FINAC - Products - MainSheet.csv
````
Item Name,Brand,Warehouse,Category,Qty,Net Price,KiaChahye Website Price,Alfa uploaded?,Faysal  uploaded?
ACSON AIR CURTAIN 3FT,ACSON,SEA-BREEZE,AIR CURTAIN,1,,,,
ANEX INSECT KILLER 1088,ANEX,HASHMI SHOP,INSECT KILLER,1,,,,
BLACK & DECKER JUG KETTLE,BLACK & DECKER,HASHOO,KETTLE,1,,,,
CHOWKI,LOCAL,HASHMI SHOP,CHOWKI,1,,,,
DAIKIN SPLIT AC 2.0TON NORMAL FTV60AXV1,DAIKIN,HASHMI SHOP,SPLIT AC,1,,,,
DAW AUTO W/M DWT-1165 PL,Dawlance,HASHOO,AWM,26,"74,500",82000,,
DAW AUTO W/M DWT-11671 FLT,Dawlance,HASHOO,AWM,21,"75,500",82000,,
DAW AUTO W/M DWT-9560,Dawlance,HASHOO,AWM,16,"66,500",73999,,
DAW AUTO W/M DWT-1471 FLP,Dawlance,HASHMI SHOP,AWM,12,"79,500",86999,,
DAW AUTO W/M 255 CLEAR LID WHITE,Dawlance,HASHOO,AWM,7,"50,000",60000,,
DAW AUTO W/M DWT-1006 MYSTIC GREY,Dawlance,HASHOO,AWM,7,"77,000",85000,,
DAW AUTO W/M DWT-14470 ES,Dawlance,HASHOO,AWM,7,"84,500",90000,,
DAW AUTO W/M DWT-1470 PL,Dawlance,HASHOO,AWM,7,"85,000",92000,,
DAW AUTO W/M DWT-9060 EZ,Dawlance,HASHOO,AWM,7,"57,500","59,999",,
DAW AUTO W/M 1016DDM INV PRIMA,Dawlance,HASHOO,AWM,6,"90,000","94,999",,
DAW AUTO W/M 260C LVS + CHAMPAGNE,Dawlance,Dastagir,AWM,4,"71,500",84000,,
DAW AUTO W/M DWT-1167 FLP,Dawlance,HASHOO,AWM,4,"69,000",76000,,
DAW AUTO W/M DWT-9060 EZ (SILVER),Dawlance,HASHMI SHOP,AWM,3,"57,500",64000,,
DAW AUTO W/M 255 ES,Dawlance,HASHOO,AWM,2,"53,000",62000,,
DAW AUTO W/M 260 ES,Dawlance,Dastagir,AWM,2,,,,
DAW AUTO W/M 260S LVS + SILVER,Dawlance,HASHOO,AWM,2,70500,"74,999",,
DAW AUTO W/M 270C LVS +,Dawlance,HASHOO,AWM,2,"81,500",88999,,
DAW AUTO W/M DWT-1580 INV C GLOW,Dawlance,HASHOO,AWM,2,"116,000",124999,,
DAW AUTO W/M DWT-1775 PL,Dawlance,HASHMI SHOP,AWM,2,"122,000",129999,,
DAW AUTO W/M 270 ES,Dawlance,Dastagir,AWM,1,,,,
DAW AUTO W/M 270S LVS +,Dawlance,HASHOO,AWM,1,80500,"84,999",,
DAW AUTO W/M DWT-1166 X ADS+,Dawlance,Dastagir,AWM,1,"83,500",92999,,
DAW AUTO W/M DWT-14711 FLT,Dawlance,HASHMI SHOP,AWM,1,"87,500",94500,,
DAW AUTO W/M FRONT LOAD 8200 X INV,Dawlance,HASHMI SHOP,FRONT LOAD AWM,1,,,,
DAW BUILT-IN OVEN GAS+ELECTRIC 21810S,Dawlance,HASHOO,BUILT-IN OVEN,1,n/a,,,
DAW D/F 200 ES,Dawlance,Dastagir,D/F,5,"65,000",,,
DAW D/F 300 ES,Dawlance,Dastagir,D/F,1,"67,500",,,
DAW D/F 400 SD EDS WHITE,Dawlance,Dastagir,D/F,1,"75,000",,,
DAW D/F 400 SD INVERTER GREY,Dawlance,SEA-BREEZE,D/F,1,"79,000",,,
DAW D/F 500 DD,Dawlance,Dastagir,D/F,3,"91,000",,,
DAW D/F 500 DD INVERTER WHITE,Dawlance,Dastagir,D/F,2,"97,500",,,
DAW D/F 91997 LVS CONVERTIBLE,Dawlance,SEA-BREEZE,D/F,1,"86,000",,,
DAW D/F 91997-H SIGNATURE INVERTER,Dawlance,HASHOO,D/F,1,"93,000",,,
DAW D/F 91998 INVERTER GREY,Dawlance,Dastagir,D/F,2,"97,000",,,
DAW D/F 91998-H GD INVERTER WICKER,Dawlance,Dastagir,D/F,4,"108,500",,,
DAW D/F 91998-H SIGNATURE ARC WHITE,Dawlance,Dastagir,D/F,4,"90,000",,,
DAW D/F VF-1035 GD AVANTE + CLOUD WHITE,Dawlance,Dastagir,VERTICAL FREEZER,2,,,,
DAW D/F VF-1035 GD AVANTE + EMERALD GREEN,Dawlance,Dastagir,VERTICAL FREEZER,1,,,,
DAW D/F VF-1035 GD BURGUNDY HONEY-COMB,Dawlance,Dastagir,VERTICAL FREEZER,19,93000,102000,,
DAW DISHWASHER AUTO INV DDW-1451 TRADING,Dawlance,Dastagir,DISHWASHER,1,n/a,,,
DAW DISHWASHER AUTO INV DDW-14952 S INV,Dawlance,HASHOO,DISHWASHER,1,,,,
DAW DISHWASHER DDW-1250 SILVER MANUAL,Dawlance,HASHOO,DISHWASHER,1,n/a,,,
DAW DISHWASHER DDW-1470 GB INV,Dawlance,HASHOO,DISHWASHER,2,,,,
DAW DISHWASHER DDW-1485G INVERTER,Dawlance,Dastagir,DISHWASHER,1,n/a,,,
DAW FLOOR STANDING GLACIER PRO T3 INVERTER 45,Dawlance,Dastagir,FLOOR STANDING,1,,,,
DAW FLOOR STANDING GLAMOUR INVERTER 45,Dawlance,Dastagir,FLOOR STANDING,4,,,,
DAW FLOOR STANDING GLAMOUR+ INVERTER 45,Dawlance,DILPASAND,FLOOR STANDING,4,,,,
DAW HOOD DCB 7530 B,Dawlance,HASHOO,HOOD,3,,,,
DAW HOOD DCT 7310 S A SERIES,Dawlance,HASHOO,HOOD,2,,,,
DAW HOOD DCT 9030 S,Dawlance,HASHOO,HOOD,4,,,,
"DAW LED 40"" KORE GOOGLE TV",Dawlance,HASHOO,LED,2,,,,
"DAW LED 43"" 43E22 2K SMART TV",Dawlance,HASHOO,LED,30,"69,500",110000,,
"DAW LED 50"" CANVAS X SERIES 4K UHD SMART TV",Dawlance,HASHOO,LED,1,,,,
"DAW LED 50"" 50G3A PRO 4K UHD",Dawlance,HASHOO,LED,13,"96,000",80000,,
"DAW LED 55"" APOLLO 144HZ QLED GOOGLE",Dawlance,HASHOO,LED,7,not provided,,,
"DAW LED 65"" APOLLO 144HZ QLED GOOGLE",Dawlance,HASHOO,LED,2,,,,
DAW M/O 115CHZP,Dawlance,HASHMI SHOP,M/O,8,"38,000",,,
DAW M/O 128G,Dawlance,HASHOO,M/O,13,"33,000",,,
DAW M/O 131HP,Dawlance,HASHOO,M/O,1,"35,500",,,
DAW M/O 133 RG,Dawlance,HASHOO,M/O,9,"35,000",,,
DAW M/O 136G,Dawlance,HASHOO,M/O,5,"34,000",,,
DAW M/O 142HZP,Dawlance,HASHOO,M/O,7,"41,500",,,
DAW M/O 210S,Dawlance,HASHOO,M/O,1,"16,500",,TRUE,
DAW M/O 220S,Dawlance,HASHOO,M/O,5,"16,500",,,
DAW M/O 295,Dawlance,HASHOO,M/O,15,"18,500",,,
DAW M/O 297 GSS,Dawlance,HASHMI SHOP,M/O,12,"22,000",,,
DAW M/O 299 DS,Dawlance,HASHOO,M/O,8,"24,000",,,
DAW M/O 374,Dawlance,HASHMI SHOP,M/O,17,"25,500",,,
DAW M/O 393 G,Dawlance,HASHOO,M/O,9,"28,500",,,
DAW M/O 395 HCG,Dawlance,HASHOO,M/O,1,"27,500",,,
DAW M/O 525 AF,Dawlance,HASHOO,M/O,18,"40,000",,,
DAW M/O 530 AF,Dawlance,HASHOO,M/O,1,"41,500",,,
DAW M/O 550AF,Dawlance,HASHOO,M/O,29,"46,000",,,
DAW M/O DBMO 25 BG SERIES,Dawlance,HASHOO,BUILT-IN M/OVEN,1,n/a,,TRUE,
DAW M/O DBMO 25 IG SERIES,Dawlance,HASHMI SHOP,BUILT-IN M/OVEN,11,n/a,,,
DAW M/O MD10,Dawlance,HASHMI SHOP,M/O,1,"16,000",,,
DAW M/O MD15,Dawlance,HASHOO,M/O,47,"15,000",,,
DAW M/O MD4,Dawlance,HASHOO,M/O,5,"16,500",,,
DAW M/O MD7,Dawlance,HASHOO,M/O,2,"16,000",,,
DAW MINI OVEN DWMO-4520 CR,Dawlance,HASHOO,MINI OVEN,3,n/a,,,
DAW MINI OVEN DWMO-5222 CR,Dawlance,HASHOO,MINI OVEN,3,n/a,,,
DAW OVEN TOASTER DWMO-2113 C,Dawlance,HASHMI SHOP,OVEN TOASTER,1,n/a,,,
DAW OVEN TOASTER DWOT-2515,Dawlance,HASHOO,OVEN TOASTER,9,n/a,,,
DAW R/F 4467 MINIBAR,Dawlance,HASHMI SHOP,REFRIGERATOR,9,,,,
DAW R/F 4890SD SILVER,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F 9101 SD METALLIC GREY,Dawlance,Dastagir,REFRIGERATOR,8,,,,
DAW R/F 9101 SD R ND (WHITE),Dawlance,HASHMI SHOP,REFRIGERATOR,10,,,,
DAW R/F 9106 SD R ND (WHITE),Dawlance,Dastagir,REFRIGERATOR,10,,,TRUE,
DAW R/F 9140WB AVANTE PEARL BURGUNDY,Dawlance,Dastagir,REFRIGERATOR,15,,,,
DAW R/F 9140WB AVANTE PEARL RED,Dawlance,Dastagir,REFRIGERATOR,9,,,,
DAW R/F 9140WB CHROME PRO INVERTER,Dawlance,HASHMI SHOP,REFRIGERATOR,1,,,,
DAW R/F 9140WB E-CHROME HAIRLINE GOLDEN,Dawlance,Dastagir,REFRIGERATOR,4,,,,
DAW R/F 9140WB E-CHROME METALLIC GREY,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F 9149WB AVANTE PEARL BURGUNDY,Dawlance,Dastagir,REFRIGERATOR,9,,,,
DAW R/F 9149WB AVANTE PEARL RED,Dawlance,HASHMI SHOP,REFRIGERATOR,4,,,,
DAW R/F 9149WB CHROME HAIRLINE BLACK,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9149WB CHROME PEARL COPPER,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9149WB E-CHROME HAIRLINE GOLDEN,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9160LF AVANTE + CLOUD WHITE,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F 9160LF AVANTE PEARL BURGUNDY,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9160LF CHROME PRO HAIRLINE SILVER,Dawlance,Dastagir,REFRIGERATOR,6,,,,
DAW R/F 9160LF ICEMAX MIDNIGHT BLUE,Dawlance,Dastagir,REFRIGERATOR,5,,,,
DAW R/F 9160LF ICEMAX MIST GREEN,Dawlance,Dastagir,REFRIGERATOR,6,,,,
DAW R/F 9169LF AVANTE + CLOUD WHITE,Dawlance,Dastagir,REFRIGERATOR,4,,,,
DAW R/F 9169WB AVANTE PEARL RED,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F 9169WB CHROME HAIRLINE BLACK,Dawlance,Dastagir,REFRIGERATOR,10,,,,
DAW R/F 9169WB CHROME PEARL COPPER,Dawlance,Dastagir,REFRIGERATOR,14,,,,
DAW R/F 9169WB CHROME PRO HAIRLINE SILVER,Dawlance,Dastagir,REFRIGERATOR,13,,,,
DAW R/F 9169WB ICEMAX MIST GREEN,Dawlance,Dastagir,REFRIGERATOR,3,,,,
DAW R/F 9173 AVANTE+ RUBY RED,Dawlance,Dastagir,REFRIGERATOR,4,,,,
DAW R/F 9173 GRAZE+ GEM BLACK,Dawlance,Dastagir,REFRIGERATOR,7,,,,
DAW R/F 9173LF ACCE PRO MEADOW GREEN,Dawlance,Dastagir,REFRIGERATOR,9,,,,
DAW R/F 9173WB AVANTE + CLOUD WHITE,Dawlance,HASHMI SHOP,REFRIGERATOR,3,,,,
DAW R/F 9173WB AVANTE DIAMOND RED,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9173WB AVANTE+ MIDNIGHT GREEN,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9173WB AVANTE+ PLATINUM SILVER,Dawlance,Dastagir,REFRIGERATOR,7,,,TRUE,
DAW R/F 9173WB CHROME PEARL COPPER,Dawlance,Dastagir,REFRIGERATOR,26,,,,
DAW R/F 9173WB CHROME+HAIRLINE GOLDEN,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9173WB DIGITAL PRO MAGNETIC GREEN,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9173WB DIGITAL PRO MAGNETIC RED,Dawlance,Dastagir,REFRIGERATOR,22,,,,
DAW R/F 9173WB E-CHROME HAIRLINE GOLDEN,Dawlance,Dastagir,REFRIGERATOR,8,,,,
DAW R/F 9173WB E-CHROME METALLIC GREY,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9173WB ICEMAX MIST GREEN,Dawlance,DILPASAND,REFRIGERATOR,6,,,,
DAW R/F 9178 GRAZE+ GEM BLACK,Dawlance,HASHMI SHOP,REFRIGERATOR,3,,,,
DAW R/F 9178LF ACCE CORAL RED,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F 9178LF ACCE PRO CRIMSON RED,Dawlance,Dastagir,REFRIGERATOR,3,,,,
DAW R/F 9178LF ACCE PRO MEADOW GREEN,Dawlance,Dastagir,REFRIGERATOR,8,,,,
DAW R/F 9178LF AVANTE+ SAPPHIRE PURPLE,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F 9178LF AVANTE+ RUBY RED,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9178LF CHROME HAIRLINE BLACK,Dawlance,Dastagir,REFRIGERATOR,7,,,,
DAW R/F 9178LF CHROME PEARL COPPER,Dawlance,Dastagir,REFRIGERATOR,8,,,,
DAW R/F 9178LF DIGITAL PRO MAGNETIC GREEN,Dawlance,DILPASAND,REFRIGERATOR,7,,,,
DAW R/F 9178LF DIGITAL PRO MAGNETIC RED,Dawlance,Dastagir,REFRIGERATOR,13,,,,
DAW R/F 9178LF E-CHROME HAIRLINE GOLDEN,Dawlance,Dastagir,REFRIGERATOR,13,,,,
DAW R/F 9178LF ICEMAX MIDNIGHT BLUE,Dawlance,HASHMI SHOP,REFRIGERATOR,1,,,,
DAW R/F 9178LF ICEMAX MIST GREEN,Dawlance,Dastagir,REFRIGERATOR,5,,,,
DAW R/F 9178LF M-CHROME METALLIC SILVER,Dawlance,Dastagir,REFRIGERATOR,7,,,,
DAW R/F 9178WB AVANTE DIAMOND RED,Dawlance,Dastagir,REFRIGERATOR,6,,,,
DAW R/F 9178WB AVANTE+ LUXE BROWN,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9191 ACCE CORAL RED,Dawlance,Dastagir,REFRIGERATOR,9,,,,
DAW R/F 9191LF ACCE PRO CRIMSON RED,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9191LF ACCE PRO MEADOW GREEN,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F 9191WB AVANTE DIAMOND PURPLE,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9191WB AVANTE+ EMERALD GREEN,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9191WB AVANTE+ LUXE BROWN,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9191WB AVANTE+ PLATINUM SILVER,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F 9191WB CHROME HAIRLINE BLACK,Dawlance,HASHMI SHOP,REFRIGERATOR,1,,,,
DAW R/F 9193 AVANTE+ IOT SILKY BLACK,Dawlance,HASHMI SHOP,REFRIGERATOR,2,,,,
DAW R/F 9193 AVANTE+ IOT SILKY RED,Dawlance,Dastagir,REFRIGERATOR,7,,,,
DAW R/F 9193LF ACCE CORAL RED,Dawlance,Dastagir,REFRIGERATOR,8,,,,
DAW R/F 9193LF ACCE PRO CRIMSON RED,Dawlance,Dastagir,REFRIGERATOR,5,,,,
DAW R/F 9193LF ACCE PRO MEADOW GREEN,Dawlance,Dastagir,REFRIGERATOR,3,,,,
DAW R/F 9193LF AVANTE + CLOUD WHITE,Dawlance,HASHMI SHOP,REFRIGERATOR,12,,,,
DAW R/F 9193LF AVANTE DIAMOND PURPLE,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9193LF AVANTE+ MIDNIGHT GREEN,Dawlance,Dastagir,REFRIGERATOR,3,,,,
DAW R/F 9193LF CHROME HAIRLINE BLACK,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 9193LF CHROME PEARL COPPER,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F 9193LF DIGITAL PRO MAGNETIC GREEN,Dawlance,Dastagir,R/F,16,,,,
DAW R/F 9193LF DIGITAL PRO MAGNETIC RED,Dawlance,Dastagir,REFRIGERATOR,12,,,,
DAW R/F 91996 GD BURGUNDY,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 91999 ACCE PRO MEADOWN GREEN,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 91999 AVANTE+ CLOUD WHITE NEW,Dawlance,Dastagir,REFRIGERATOR,7,,,,
DAW R/F 91999 CHROME PEARL COPPER,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F 91999 DIGITAL PRO MAGNETIC RED,Dawlance,Dastagir,REFRIGERATOR,4,,,,
DAW R/F DFD-900 GD (INV) HONEYCOMB,Dawlance,HASHMI SHOP,REFRIGERATOR,4,,,,
DAW R/F DMD-7950 GD INVERTER,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F DMD-7951 INV GD,Dawlance,Dastagir,REFRIGERATOR,1,,,,
DAW R/F DMD-7951 INV INOX,Dawlance,Dastagir,REFRIGERATOR,3,,,,
DAW R/F DMD-9060 INV GD,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F DMD-9060 INV INOX,Dawlance,Dastagir,REFRIGERATOR,2,,,,
DAW R/F DTM-7650 GD INVERTER IOT,Dawlance,HASHMI SHOP,REFRIGERATOR,2,,,,
DAW R/F DTM-8365 INVERTER INOX,Dawlance,Dastagir,REFRIGERATOR,4,,,,
DAW SDA AIR FRYER DWAF-3374 B,Dawlance,HASHMI SHOP,AIR FRYER,1,,,,
DAW SDA AIR FRYER DWAF-6321 L,Dawlance,HASHOO,AIR FRYER,31,21000,24999,,
DAW SDA AIR FRYER DWAF-6322 D,Dawlance,HASHMI SHOP,AIR FRYER,35,22000,29000,,
DAW SDA CITRUS PRESS DWCJ 80301,Dawlance,HASHMI SHOP,CITRUS,1,,,,
DAW SDA COFFER MAKER DWCM-5304 X VOLTAS,Dawlance,HASHMI SHOP,COFFE MAKER,3,,,,
DAW SDA ELECTRIC HOT PLATE DWHP-3021W,Dawlance,HASHOO,HOT PLATE,1,,,,
DAW SDA GARMENT STEAMER DWGS-2316,Dawlance,HASHMI SHOP,GARMENT STEAMER,11,,,,
DAW SDA HAIR STRAIGHTNER DWHS-7034-,Dawlance,HASHMI SHOP,HAIR STRAIGHTNER /,2,,,,
DAW SDA HAND/BLENDER DWHB-475W,Dawlance,HASHMI SHOP,BLENDER,19,,,,
DAW SDA HAND/BLENDER DWHB-81762,Dawlance,HASHOO,BLENDER,2,,,,
DAW SDA HARD FRUIT JUICER DWHJ-8002 I,Dawlance,HASHOO,JUICER,28,,,,
DAW SDA HARD FRUIT JUICER DWJ-4002,Dawlance,HASHOO,JUICER,1,,,,
DAW SDA IRON DWDI 1020 BLACK,Dawlance,HASHOO,IRON,1,,,,
DAW SDA IRON DWDI 1020 WHITE,Dawlance,HASHOO,IRON,13,,,,
DAW SDA STEAM IRON DWSI 2322 CX,Dawlance,HASHOO,IRON,57,,,,
DAW SDA STEAM IRON DWSI-2217 T PURPLEMM,Dawlance,HASHOO,IRON,1,,,,
DAW SDA TABLE BLENDER DWTB-620 1,Dawlance,HASHOO,BLENDER,4,,,,
DAW SPINNER DS-6000,Dawlance,HASHMI SHOP,SPINNER,7,"18,000",20999,,
DAW SPINNER DS-6010 C,Dawlance,Dastagir,SPINNER,8,"18,000",21500,,
DAW SPINNER DS-6050,Dawlance,Dastagir,SPINNER,1,,,,
DAW SPINNER DS-6080 CB,Dawlance,Dastagir,SPINNER,1,,,,
DAW SPLIT AC AEROMAX INVERTER 15,Dawlance,Dastagir,SPLIT AC,30,,,,
DAW SPLIT AC AEROMAX INVERTER 30,Dawlance,Dastagir,SPLIT AC,1,,,,
DAW SPLIT AC ATMOS COOL INVERTER 30,Dawlance,Dastagir,SPLIT AC,1,,,,
DAW SPLIT AC AVANTE INVERTER 30 (CLASSIC,Dawlance,Dastagir,SPLIT AC,6,,,,
DAW SPLIT AC AVANTE INVERTER 30 (ELEGANT,Dawlance,Dastagir,SPLIT AC,1,,,,
DAW SPLIT AC AVANTE INVERTER 30 DESIGNER,Dawlance,Dastagir,SPLIT AC,2,,,,
DAW SPLIT AC CHROME + INVERTER 45 (COPPER,Dawlance,Dastagir,SPLIT AC,3,,,,
DAW SPLIT AC CHROME INVERTER 30 WHITE,Dawlance,Dastagir,SPLIT AC,1,,,,
DAW SPLIT AC CHROME PRO INVERTER 30,Dawlance,Dastagir,SPLIT AC,5,,,,
DAW SPLIT AC CRUISE PRO 45,Dawlance,Dastagir,SPLIT AC,1,,,,
DAW SPLIT AC DUAL PRO T3 INVERTER 15,Dawlance,Dastagir,SPLIT AC,4,,,,
DAW SPLIT AC ECONO+ X INVERTER 15,Dawlance,Dastagir,SPLIT AC,16,,,,
DAW SPLIT AC ECONO+ X INVERTER 30,Dawlance,Dastagir,SPLIT AC,13,,,,
DAW SPLIT AC ELEGANCE PRO INVERTER 15,Dawlance,Dastagir,SPLIT AC,10,,,,
DAW SPLIT AC ELEGANCE X INVERTER 15,Dawlance,Dastagir,SPLIT AC,19,,,,
DAW SPLIT AC ENERCON X INVERTER 15,Dawlance,Dastagir,SPLIT AC,55,,,,
DAW SPLIT AC ENERCON X INVERTER 30,Dawlance,Dastagir,SPLIT AC,39,,,,
DAW SPLIT AC FROST INVERTER 20 (COOL ONLY),Dawlance,Dastagir,SPLIT AC,13,,,,
DAW SPLIT AC FROST INVERTER 30 (COOL ONLY),Dawlance,Dastagir,SPLIT AC,34,,,,
DAW SPLIT AC HYPER T3 INVERTER 30,Dawlance,Dastagir,SPLIT AC,1,,,,
DAW SPLIT AC INFINITY PRO 15,Dawlance,Dastagir,SPLIT AC,20,,,,
DAW SPLIT AC INFINITY PRO 30,Dawlance,Dastagir,SPLIT AC,29,,,,
DAW SPLIT AC MAGNA T3 INVERTER 30 MILKY,Dawlance,Dastagir,SPLIT AC,1,,,,
DAW SPLIT AC MEGA FLEX INVERTER 15,Dawlance,Dastagir,SPLIT AC,50,,,,
DAW SPLIT AC MEGA T+ 10,Dawlance,HASHOO,SPLIT AC,45,,,,
DAW SPLIT AC MEGA T3 PRO INVERTER 30,Dawlance,Dastagir,SPLIT AC,14,,,,
DAW SPLIT AC POWERCON 30,Dawlance,Dastagir,SPLIT AC,2,,,,
DAW SPLIT AC POWERCON T3 X INV 15,Dawlance,Dastagir,SPLIT AC,12,,,,
DAW SPLIT AC POWERCON T3 X INV 30,Dawlance,Dastagir,SPLIT AC,1,,,,
DAW SPLIT AC PRIMA PURSENSE INVERTER 30,Dawlance,Dastagir,SPLIT AC,16,,,,
DAW SPLIT AC SPRINTER 30,Dawlance,Dastagir,SPLIT AC,5,,,,
DAW SPLIT AC SPRINTER T3 X INVERTER 15,Dawlance,Dastagir,SPLIT AC,5,,,,
DAW SPLIT AC SPRINTER T3 X INVERTER 30,Dawlance,Dastagir,SPLIT AC,1,,,,
DAW SPLIT AC SUAVE + 30 INVERTER SILVER,Dawlance,Dastagir,SPLIT AC,2,,,,
DAW W/D 1051 CLOUD WHITE,Dawlance,HASHOO,W/D,1,,,,
DAW W/D 1051 CN GREY,Dawlance,HASHOO,W/D,10,"33,000",37500,,
DAW W/D 1051 GD NOIR RED,Dawlance,HASHOO,W/D,1,,,,
DAW W/D 1051 GD SILVER,Dawlance,HASHOO,W/D,5,"40,000",42999,,
DAW W/D 1060 W/O REF WHITE,Dawlance,HASHOO,W/D,17,"34,500",37500,,
DAW W/D 1060 WBR SILVER,Dawlance,HASHOO,W/D,1,,,,
DAW W/D 1060 WGR CHAMPAGNE,Dawlance,HASHOO,W/D,1,,,,
DAW W/D DBD-1034 BOTTOM LOAD,Dawlance,HASHOO,W/D,31,"40,500",44999,,
DAW W/D DBD-1035 GD,Dawlance,HASHOO,W/D,1,,,,
DAW W/M 6580 CB FL,Dawlance,HASHOO,W/M,45,34000,42000,,
DAW W/M 9200 WFL,Dawlance,HASHOO,W/M,12,29500,36999,,
DAW W/M 6550 W,Dawlance,HASHOO,W/M,11,34000,39000,,
DAW W/M 7500 C,Dawlance,HASHOO,W/M,8,40500,47000,,
DAW W/M 6100 W WHITE,Dawlance,Dastagir,W/M,4,23000,26999,,
DAW W/M 6100 C,Dawlance,Dastagir,W/M,3,,,,
DAW W/M 6570,Dawlance,HASHOO,W/M,2,,,,
DAW W/M 7200 W FL,Dawlance,HASHMI SHOP,W/M,20,22000,27999,,
DAW W/M 6580 W FL,Dawlance,Dastagir,W/M,2,,,,
DAW W/M 9100 C,Dawlance,HASHOO,W/M,2,,,,
DAW W/M 10500 C,Dawlance,HASHMI SHOP,W/M,1,,,,
DAW W/M 7500 G,Dawlance,HASHOO,W/M,1,,,,
DAW W/M 9200 CFL,Dawlance,Dastagir,W/M,1,,,,
Dawlance REF 9106 SD METALLIC GREY,Dawlance,Dastagir,REFRIGERATOR,20,,,,
ECOSTAR SPLIT 1.5TON 18EM02WS,ECOSTAR,HASHOO,SPLIT AC,39,,,,
ECOSTAR SPLIT 1TON 12EM02WS,ECOSTAR,HASHOO,SPLIT AC,11,,,,
ECOSTAR SPLIT 1TON 12PR02WT3,ECOSTAR,HASHMI SHOP,SPLIT AC,1,,,,
ECOSTAR SPLIT 1TON ES-12AR01WT3,ECOSTAR,HASHOO,SPLIT AC,9,,,,
ECOSTAR SPLIT 2TON 24DU01BC,ECOSTAR,DILPASAND,SPLIT AC,3,,,,
ECOSTAR SPLIT 2TON 24DU01WG,ECOSTAR,HASHMI SHOP,SPLIT AC,2,,,,
ECOSTAR SPLIT 2TON 24EM01WS SA+,ECOSTAR,HASHMI SHOP,SPLIT AC,1,,,,
ECOSTAR AUTO W/M EW-9502 DC,ECOSTAR,HASHOO,AWM,7,,,,
ECOSTAR FLOOR STANDING EF-24GLO2S,ECOSTAR,HASHOO,FLOOR STANDING,3,,,,
ECOSTAR FLOOR STANDING EF-48IB01W,ECOSTAR,HASHOO,FLOOR STANDING,3,,,,
ECOSTAR SPINNER EW-S1001GW,ECOSTAR,HASHOO,SPINNER,1,,,,
ECOSTAR SPLIT 0.75TON ES-10EMC1WS,ECOSTAR,HASHOO,SPLIT AC,13,,,,
ECOSTAR SPLIT 1.5 ΤΟΝ 18DU01GC,ECOSTAR,HASHOO,SPLIT AC,1,,,,
ECOSTAR SPLIT 1.5TON 18DU02BC,ECOSTAR,DILPASAND,SPLIT AC,1,,,,
ECOSTAR SPLIT 1.5TON 18EMC1WS,ECOSTAR,HASHOO,SPLIT AC,15,,,,
ECOSTAR SPLIT 1.5TON ES-18AR01WT3,ECOSTAR,HASHOO,SPLIT AC,43,,,,
ECOSTAR SPLIT 1TON 12DU01BC,ECOSTAR,HASHOO,SPLIT AC,6,,,,
ECOSTAR SPLIT 1TON 12DU01GC,ECOSTAR,HASHOO,SPLIT AC,9,,,,
ECOSTAR SPLIT 1TON 12DU01WG SA+,ECOSTAR,HASHMI SHOP,SPLIT AC,1,,,,
ECOSTAR SPLIT 1TON 12DU02WG,ECOSTAR,HASHOO,SPLIT AC,37,,,,
ECOSTAR SPLIT 1TON 12EM01WS SA+,ECOSTAR,HASHOO,SPLIT AC,8,,,,
ECOSTAR SPLIT 2TON 24DU01GC,ECOSTAR,DILPASAND,SPLIT AC,2,,,,
ECOSTAR SPLIT 2TON ES-24AR01WT3,ECOSTAR,DILPASAND,SPLIT AC,5,,,,
ECOSTAR SPLIT AC 1 ΤΟN 12NV01WT3,ECOSTAR,HASHOO,SPLIT AC,10,,,,
ECOSTAR SPLIT AC 1 TON 24NV01WT3,ECOSTAR,HASHOO,SPLIT AC,2,,,,
ECOSTAR SPLIT AC 1 TON ES-12NV02WT3,ECOSTAR,HASHOO,SPLIT AC,4,,,,
ECOSTAR SPLIT AC 1.5 ΤΟΝ 18NV01WT3,ECOSTAR,HASHOO,SPLIT AC,49,,,,
ECOSTAR SPLIT AC 1.5 ΤΟΝ 18NV02WT3,ECOSTAR,HASHOO,SPLIT AC,9,,,,
ECOSTAR SPLIT AC 1.5TON 18AR02W,ECOSTAR,HASHOO,SPLIT AC,9,,,,
ECOSTAR W/D 300,ECOSTAR,HASHOO,W/D,4,,,,
ECOSTAR W/D 300F,ECOSTAR,HASHOO,W/D,5,,,,
ECOSTAR W/D 351FB,ECOSTAR,HASHOO,W/D,2,,,,
ECOSTAR W/D 450F,ECOSTAR,HASHOO,W/D,10,,,,
ECOSTAR WIFI USB PR02WT3,ECOSTAR,HASHMI SHOP,WIFI DEVICE,1,,,,
ELITE AIR COOLER EAC-99A,ELITE,HASHMI SHOP,AIR COOLER,1,,,,
FLOWER M/O N36GGBD,FLOWER,HASHOO,M/O,1,,,,
GABA NATIONAL CHOPPER GN-5024-21,GABA NATIONAL,HASHOO,CHOPPER,6,,,,
GABA NATIONAL HOT PLATE GN-261/21,GABA NATIONAL,HASHOO,HOT PLATE,5,,,,
GABA NATIONAL INFRARED COOKER GN145-,GABA NATIONAL,HASHMI SHOP,INFRARED COOKER,1,,,,
GABA NATIONAL R/F 165 GD RED,GABA NATIONAL,HASHOO,R/F,2,,,,
GABA NATIONAL R/F 183 S.S,GABA NATIONAL,HASHOO,R/F,1,,,,
GABA NATIONAL R/F 184 S.S,GABA NATIONAL,HASHMI SHOP,R/F,1,,,,
GABA NATIONAL R/F 185 GD CHAMPAGNE,GABA NATIONAL,HASHOO,R/F,1,,,,
GABA NATIONAL R/F 185 GD RED,GABA NATIONAL,HASHOO,R/F,1,,,,
GABA NATIONAL R/F 187 GD GOLDEN,GABA NATIONAL,HASHOO,R/F,1,,,,
GABA NATIONAL R/F 187 GD RED FLOWER,GABA NATIONAL,HASHOO,R/F,1,,,,
GABA NATIONAL R/F 2509 GD PURPLE,GABA NATIONAL,HASHMI SHOP,R/F,2,,,,
GABA NATIONAL SANDWITCH MAKER GNE-396/20,GABA NATIONAL,HASHMI SHOP,S/MAKER,1,,,,
GABA NATIONAL SPINNER GND-1606/23,GABA NATIONAL,HASHMI SHOP,SPINNER,2,,,,
GABA NATIONAL STEAM IRON GN-203 DLX,GABA NATIONAL,HASHMI SHOP,STEAM IRON,10,,,,
GABA NATIONAL TABLE TOP W/DISPENSER GND-0319,GABA NATIONAL,HASHOO,W/D,3,,,,
GABA NATIONAL W/D 2100,GABA NATIONAL,HASHMI SHOP,W/D,1,,,,
GABA NATIONAL W/D GND-0919,GABA NATIONAL,HASHOO,W/D,13,,,,
GABA NATIONAL W/M 1208 STD,GABA NATIONAL,HASHOO,W/M,1,,,,
GABA NATIONAL W/M 92020,GABA NATIONAL,HASHOO,W/M,14,,,,
GABA NATIONAL W/M 93020 GD,GABA NATIONAL,HASHOO,W/M,11,,,,
GABA NATIONAL W/M 94023 BLUE,GABA NATIONAL,HASHOO,W/M,21,,,,
GABA NATIONAL W/M 95023 TWIN TUB,GABA NATIONAL,HASHOO,W/M,8,,,,
GREE FLOOR STANDING 36TFIH AA+,GREE,HASHOO,FLOOR STANDING,4,,,,
GREE SPLIT AC 12AITH21W-T3,GREE,HASHMI SHOP,SPLIT AC,9,,,,
GREE SPLIT AC 12AITH24S-T3,GREE,HASHOO,SPLIT AC,21,,,,
GREE SPLIT AC 12CM12,GREE,HASHOO,SPLIT AC,1,,,,
GREE SPLIT AC 12FITH1S SILVER WIFI,GREE,HASHOO,SPLIT AC,1,,,,
GREE SPLIT AC 12FITH6G GREY AAA,GREE,HASHMI SHOP,SPLIT AC,1,,,,
GREE SPLIT AC 12FITH6S SILVER AAA,GREE,SEA-BREEZE,SPLIT AC,1,,,,
GREE SPLIT AC 12FITHW WHITE WIFI,GREE,HASHOO,SPLIT AC,2,,,,
GREE SPLIT AC 12PITH11G AAA,GREE,HASHOO,SPLIT AC,1,,,,
GREE SPLIT AC 12PITH11W AAA,GREE,HASHOO,SPLIT AC,1,,,,
GREE SPLIT AC 12PITH21B-T3,GREE,HASHOO,SPLIT AC,1,,,,
GREE SPLIT AC 18AITH21B-T3,GREE,HASHMI SHOP,SPLIT AC,51,,,,
GREE SPLIT AC 18AITH21W-T3,GREE,HASHOO,SPLIT AC,3,,,,
GREE SPLIT AC 18AITH24S-T3,GREE,HASHOO,SPLIT AC,6,,,,
GREE SPLIT AC 18PITH11G AAA,GREE,HASHOO,SPLIT AC,8,,,,
GREE SPLIT AC 18PITH11W AAA,GREE,HASHOO,SPLIT AC,40,,,,
GREE SPLIT AC 24AITH21B-T3,GREE,HASHOO,SPLIT AC,3,,,,
GREE SPLIT AC 24AITH21W-T3,GREE,HASHOO,SPLIT AC,4,,,,
GREE SPLIT AC 24CITH13W WHITE,GREE,HASHOO,SPLIT AC,1,,,,
GREE SPLIT AC 24PITH11G AAA+,GREE,HASHOO,SPLIT AC,1,,,,
GREE SPLIT AC 24PITH11S SILVER,GREE,HASHOO,SPLIT AC,6,,,,
GREE SPLIT AC 24PITH14S SILVER,GREE,SEA-BREEZE,SPLIT AC,5,,,,
GREE SPLIT AC GS-12PITH15G-T3,GREE,HASHOO,SPLIT AC,9,,,,
GREE SPLIT AC GS-12PITH15W-T3,GREE,HASHOO,SPLIT AC,6,,,,
GREE SPLIT AC GS-12PITH17G-T3,GREE,HASHOO,SPLIT AC,7,,,,
GREE SPLIT AC GS-12PITH17W-T3,GREE,HASHOO,SPLIT AC,6,,,,
GREE SPLIT AC GS-12ZITH2W-T3,GREE,DILPASAND,SPLIT AC,9,,,,
GREE SPLIT AC GS-18PITC12W-T3,GREE,HASHOO,SPLIT AC,7,,,,
GREE SPLIT AC GS-18PITH15G-T3,GREE,HASHOO,SPLIT AC,5,,,,
GREE SPLIT AC GS-18PITH15W-T3,GREE,HASHOO,SPLIT AC,1,,,,
GREE SPLIT AC GS-18PITH17G-T3,GREE,HASHOO,SPLIT AC,7,,,,
GREE SPLIT AC GS-18ZITH1W-T3,GREE,HASHOO,SPLIT AC,2,,,,
GREE SPLIT AC GS-18ZITH2W-T3,GREE,HASHOO,SPLIT AC,17,,,,
GREE SPLIT AC GS-24PITH15G-T3,GREE,DILPASAND,SPLIT AC,5,,,,
GREE SPLIT AC GS-24PITH15W-T3,GREE,HASHMI SHOP,SPLIT AC,7,,,,
GREE SPLIT AC GS-24PITH17G-T3,GREE,DILPASAND,SPLIT AC,5,,,,
GREE SPLIT AC GS-24PITH17W-T3,GREE,HASHOO,SPLIT AC,1,,,,
GREE SPLIT AC GS-24ZITH1W-T3,GREE,HASHOO,SPLIT AC,4,,,,
GREE W/D GW-JL500FC,GREE,HASHOO,W/D,3,,,,
GREE W/D GW-JL500FS,GREE,HASHOO,W/D,1,,,,
HAIER AUTO W/M 100-1269 S6,HAIER,HASHOO,AWM,11,,,,
HAIER AUTO W/M 100-316S6 GC,HAIER,HASHOO,AWM,5,,,,
HAIER AUTO W/M 100-826 S6,HAIER,HASHOO,AWM,11,,,,
HAIER AUTO W/M 110-688S8 BLACK -,HAIER,HASHOO,AUTOMATIC W/M/HAIER,20,,,,
HAIER AUTO W/M 110-B688S8 BLACK,HAIER,HASHOO,AWM,4,,,,
HAIER AUTO W/M 120-316S6 GT,HAIER,HASHOO,AWM,3,,,,
HAIER AUTO W/M 120-826,HAIER,HASHOO,AWM,9,,,,
HAIER AUTO W/M 120-826GT GREY,HAIER,HASHMI SHOP,AWM,1,,,,
HAIER AUTO W/M 130-688S8 BLACK,HAIER,HASHOO,AWM,3,,,,
HAIER AUTO W/M 130-B699 S8,HAIER,HASHOO,AWM,3,,,,
HAIER AUTO W/M 150-316S6 GT,HAIER,HASHMI SHOP,AWM,2,,,,
HAIER AUTO W/M 150-688S8 BLACK,HAIER,HASHOO,AWM,1,,,,
HAIER AUTO W/M 150-826,HAIER,HASHOO,AWM,5,,,,
HAIER AUTO W/M 85-1269S6,HAIER,HASHOO,AWM,1,,,,
HAIER AUTO W/M 85-1708,HAIER,HASHMI SHOP,AWM,1,,,,
HAIER AUTO W/M 90-1789,HAIER,HASHMI SHOP,AWM,1,,,,
HAIER AUTO W/M 90-826E,HAIER,HASHOO,AWM,10,,,,
HAIER AUTO W/M 95-1678,HAIER,HASHMI SHOP,AWM,1,,,,
HAIER AUTO W/M 95-1678 ES8,HAIER,HASHOO,AWM,1,,,,
HAIER CASSETTE 1.5TON INVERTER 18HE/DC,HAIER,HASHOO,CASSETTE,3,,,,
HAIER CASSETTE 2TON INVERTER 24HE013DC(QB),HAIER,HASHOO,CASSETTE,5,,,,
HAIER CASSETTE 2TON NORMAL 24CE03/KB-01,HAIER,SEA-BREEZE,CASSETTE,1,,,,
HAIER CASSETTE 4TON INVERTER HBU-48E/DC,HAIER,HASHOO,CASSETTE,3,,,,
HAIER D/F 285,HAIER,SEA-BREEZE,D/F,4,,,,
HAIER D/F 285 INVERTER,HAIER,SEA-BREEZE,D/F,2,,,,
HAIER D/F 285IG INVERTER GREY,HAIER,SEA-BREEZE,D/F,3,,,,
HAIER D/F 405 INVERTER,HAIER,SEA-BREEZE,D/F,2,,,,
HAIER D/F 405IG INVERTER GREY,HAIER,SEA-BREEZE,D/F,1,,,,
HAIER D/F 465 INVERTER,HAIER,SEA-BREEZE,D/F,7,,,,
HAIER D/F 535 INVERTER WHITE,HAIER,SEA-BREEZE,D/F,2,,,,
HAIER D/F 545,HAIER,SEA-BREEZE,D/F,2,,,,
HAIER D/F 545 INVERTER,HAIER,SEA-BREEZE,D/F,2,,,,
HAIER D/F HDF-385,HAIER,SEA-BREEZE,D/F,1,,,,
HAIER FLOOR 4TON INVERTER HBU-48HE/T3DC-012GE,HAIER,HASHOO,FLOOR STANDING,4,,,,
HAIER FLOOR STANDING 24CE03(IK),HAIER,HASHOO,FLOOR STANDING,15,,,,
HAIER FLOOR STANDING 24HDZCA(W) INVERTOR,HAIER,HASHOO,SPLIT AC,11,,,,
HAIER FLOOR STANDING 2TON INVERTER 24HE012WSDC(X-IK)-T3,HAIER,HASHOO,FLOOR STANDING,14,,,,
HAIER FLOOR STANDING 48CE/DC INVERTER,HAIER,HASHOO,FLOOR STANDING,3,,,,
HAIER FLOOR STANDING 48CE03 R410,HAIER,HASHOO,FLOOR STANDING,9,,,,
HAIER FRONT LOAD W/M 100-BP12357S8 10KG,HAIER,HASHOO,FRONT LOAD AWM,1,,,,
HAIER FRONT LOAD W/M 105-BD14376PGU1 GRAY,HAIER,HASHOO,FRONT LOAD AWM,2,,,,
HAIER FRONT LOAD W/M 120-BP12357S8 12KG,HAIER,HASHOO,FRONT LOAD AWM,2,,,,
HAIER FRONT LOAD W/M 80-BP12929 S3,HAIER,HASHOO,FRONT LOAD AWM,2,,,,
HAIER FRONT LOAD W/M 90-BP12357S8 SILVER,HAIER,HASHOO,FRONT LOAD AWM,5,,,,
"HAIER LED 32"" 32K85FX",HAIER,HASHOO,LED,21,,,,
"HAIER LED 32"" 32S80EFX",HAIER,HASHOO,LED,17,,,,
"HAIER LED 40"" 40K85FFX",HAIER,HASHOO,LED,9,,,,
"HAIER LED 43"" 43K85FX",HAIER,HASHOO,LED,8,,,,
"HAIER LED 43"" 43S80EUX",HAIER,HASHOO,LED,29,,,,
"HAIER LED 50"" 50K800UX",HAIER,HASHOO,LED,1,,,,
"HAIER LED 50"" 50K85FUX",HAIER,HASHOO,LED,5,,,,
"HAIER LED 50"" 50S80EUX",HAIER,HASHOO,LED,28,,,,
"HAIER LED 55"" 55P7UX",HAIER,HASHOO,LED,2,,,,
"HAIER LED 55"" 55K85FUX",HAIER,HASHOO,LED,5,,,,
"HAIER LED 55"" 55M80FUX",HAIER,HASHOO,LED,2,,,,
"HAIER LED 55"" 55S800UX PRO",HAIER,HASHOO,LED,4,,,,
"HAIER LED 55"" 55S80EUX",HAIER,HASHOO,LED,4,,,,
"HAIER LED 65"" 65S800UX PRO",HAIER,HASHOO,LED,3,,,,
"HAIER LED 75"" 75S80EUX Q LED GOOGLE TV",HAIER,HASHOO,LED,3,,,,
HAIER M/O 20MXP3,HAIER,HASHOO,M/O,2,,,,
HAIER M/O 20MXP6,HAIER,HASHOO,M/O,2,,,,
HAIER M/O 25MXP9,HAIER,HASHOO,M/O,2,,,,
HAIER M/O 28100DG BLACK,HAIER,HASHOO,M/O,4,,,,
HAIER M/O 30AFR WITH AIR FRYER,HAIER,HASHMI SHOP,M/O,8,,,,
HAIER M/O 30AFS,HAIER,HASHOO,M/O,1,,,,
HAIER M/O 32300S SILVER,HAIER,HASHOO,M/O,1,,,,
HAIER M/O 62MX80,HAIER,HASHOO,M/O,2,,,,
HAIER M/O HGL-30100 BLACK,HAIER,HASHOO,M/O,3,,,,
HAIER M/O HMW-20DGS SILVER,HAIER,HASHOO,M/O,3,,,,
HAIER M/O HMW-20DSS SILVER,HAIER,HASHMI SHOP,M/O,1,,,,
HAIER M/O HMW-20MWS WHITE,HAIER,HASHOO,M/O,1,,,,
HAIER M/O HMW-23200DG SILVER GRAY,HAIER,HASHMI SHOP,M/O,4,,,,
HAIER M/O HMW-26MGH,HAIER,HASHOO,M/O,4,,,,
HAIER R/F 186EBD DARK METTALIC,HAIER,SEA-BREEZE,REFRIGERATOR,10,,,,
HAIER R/F 216EBD DARK METTALIC,HAIER,SEA-BREEZE,REFRIGERATOR,22,,,,
HAIER R/F 216EBS SILVER,HAIER,HASHMI SHOP,REFRIGERATOR,1,,,,
HAIER R/F 246EBS SILVER,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 246EPC CHOCLATE,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 246EPR RED,HAIER,HASHMI SHOP,REFRIGERATOR,2,,,,
HAIER R/F 246IPGA GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,5,,,,
HAIER R/F 246IPP PURPLE,HAIER,SEA-BREEZE,REFRIGERATOR,5,,,,
HAIER R/F 246IPRA RED,HAIER,HASHMI SHOP,REFRIGERATOR,5,,,,
HAIER R/F 276EBD DARK METTALIC,HAIER,HASHMI SHOP,REFRIGERATOR,18,,,,
HAIER R/F 276EBS SILVER,HAIER,SEA-BREEZE,REFRIGERATOR,18,,,,
HAIER R/F 276EPR RED,HAIER,SEA-BREEZE,REFRIGERATOR,38,,,,
HAIER R/F 276IPGA GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,6,,,,
HAIER R/F 306IDB BLACK,HAIER,HASHOO,REFRIGERATOR,1,,,,
HAIER R/F 306IDR RED,HAIER,HASHOO,REFRIGERATOR,2,,,,
HAIER R/F 306IFPA PURPLE,HAIER,HASHOO,REFRIGERATOR,1,,,,
HAIER R/F 316IAPA,HAIER,SEA-BREEZE,REFRIGERATOR,2,,,,
HAIER R/F 316IFGA GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 316IFRA RED,HAIER,SEA-BREEZE,REFRIGERATOR,3,,,,
HAIER R/F 316IPGA GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,5,,,,
HAIER R/F 316IPP PURPLE,HAIER,SEA-BREEZE,REFRIGERATOR,6,,,,
HAIER R/F 316IPRA RED,HAIER,SEA-BREEZE,REFRIGERATOR,4,,,,
HAIER R/F 336EBD DARK METTALIC,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 336IDB BLACK,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 336IDR RED,HAIER,HASHMI SHOP,REFRIGERATOR,1,,,,
HAIER R/F 346EPR RED,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 346IFRA RED,HAIER,SEA-BREEZE,REFRIGERATOR,2,,,,
HAIER R/F 346IPGA GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 346IPRA RED,HAIER,SEA-BREEZE,REFRIGERATOR,3,,,,
HAIER R/F 368IBSA SILVER,HAIER,HASHMI SHOP,REFRIGERATOR,1,,,,
HAIER R/F 368IDB BLACK,HAIER,HASHMI SHOP,REFRIGERATOR,1,,,,
HAIER R/F 368IFGA GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 368IFRA RED,HAIER,SEA-BREEZE,REFRIGERATOR,3,,,,
HAIER R/F 398IFGA GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 398IFPA PURPLE,HAIER,HASHOO,REFRIGERATOR,1,,,,
HAIER R/F 418IFB1U1 IOT BLACK,HAIER,SEA-BREEZE,REFRIGERATOR,4,,,,
HAIER R/F 418IFG GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 418IFG1U1 IOT GREY,HAIER,SEA-BREEZE,REFRIGERATOR,4,,,,
HAIER R/F 418IFP PURPLE,HAIER,SEA-BREEZE,REFRIGERATOR,3,,,,
HAIER R/F 418IFRA RED,HAIER,SEA-BREEZE,REFRIGERATOR,3,,,,
HAIER R/F 438IDR RED,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 438TPR,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 458IFB1U1 IOT BLACK,HAIER,SEA-BREEZE,REFRIGERATOR,5,,,,
HAIER R/F 458IFG GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,2,,,,
HAIER R/F 458IFP PURPLE,HAIER,SEA-BREEZE,REFRIGERATOR,8,,,,
HAIER R/F 458IFR RED,HAIER,SEA-BREEZE,REFRIGERATOR,5,,,,
HAIER R/F 488IFFB BLACK,HAIER,SEA-BREEZE,REFRIGERATOR,4,,,,
HAIER R/F 518IFFB BLACK,HAIER,SEA-BREEZE,REFRIGERATOR,3,,,,
HAIER R/F 518WIFFBGU1 IOT BLACK,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 538EPG GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 538IDR RED,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 538IFG GREEN,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 538IFPA PURPLE,HAIER,SEA-BREEZE,REFRIGERATOR,5,,,,
HAIER R/F 538IFRA RED,HAIER,SEA-BREEZE,REFRIGERATOR,2,,,,
HAIER R/F 538IPP PURPLE,HAIER,SEA-BREEZE,REFRIGERATOR,7,,,,
HAIER R/F 538IPR RED,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 578TBGU1,HAIER,SEA-BREEZE,REFRIGERATOR,19,,,,
HAIER R/F 578TGGU1,HAIER,SEA-BREEZE,REFRIGERATOR,4,,,,
HAIER R/F 578TSG,HAIER,SEA-BREEZE,REFRIGERATOR,3,,,,
HAIER R/F 622IBS INVERTER SBS,HAIER,SEA-BREEZE,REFRIGERATOR,3,,,,
HAIER R/F 622ICG INVERTER SBS,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER R/F 678TGG INVERTER SBS,HAIER,SEA-BREEZE,REFRIGERATOR,2,,,,
HAIER R/F HR-66B BLACK,HAIER,SEA-BREEZE,REFRIGERATOR,1,,,,
HAIER SDA AIR FRYER HAF50DB DIGITAL,HAIER,HASHOO,AIR FRYER,10,,,,
HAIER SDA AIR FRYER HAF50MB,HAIER,HASHOO,AIR FRYER,9,,,,
HAIER SPINNER 60-50,HAIER,HASHMI SHOP,SPINNER,12,,,,
HAIER SPINNER 80-60,HAIER,HASHOO,SPINNER,19,,,,
HAIER SPLIT AC 12CF,HAIER,Dastagir,SPLIT AC,101,,,,
HAIER SPLIT AC 12LF,HAIER,HASHOO,SPLIT AC,1,,,,
HAIER SPLIT AC 12SNS OUTDOOR/18SNS INDOOR -,HAIER,HASHOO,SPLIT AC/HAIER,1,,,,
HAIER SPLIT AC 13HFAB T3 INVERTER GREY,HAIER,HASHOO,SPLIT AC,7,,,,
HAIER SPLIT AC 13HFC WHITE,HAIER,HASHOO,SPLIT AC,5,,,,
HAIER SPLIT AC 13HFN (W) WHITE,HAIER,HASHOO,SPLIT AC,3,,,,
HAIER SPLIT AC 13HFS (G) GOLDEN,HAIER,HASHOO,SPLIT AC,4,,,,
HAIER SPLIT AC 13HFS (S) SILVER,HAIER,HASHOO,SPLIT AC,3,,,,
HAIER SPLIT AC 13LF PRIME,HAIER,HASHOO,SPLIT AC,41,,,,
HAIER SPLIT AC 14HFTEX T3 (DG) GRAY,HAIER,HASHOO,SPLIT AC,1,,,,
HAIER SPLIT AC 14HFTEX T3 (OW) WHITE,HAIER,HASHOO,SPLIT AC,7,,,,
HAIER SPLIT AC 18CF,HAIER,HASHOO,SPLIT AC,11,,,,
HAIER SPLIT AC 18HFM WHITE,HAIER,HASHOO,SPLIT AC,2,,,,
HAIER SPLIT AC 18HFP CHAMPAGNE,HAIER,HASHOO,SPLIT AC,1,,,,
HAIER SPLIT AC 18HFTC WHITE,HAIER,HASHOO,SPLIT AC,1,,,,
HAIER SPLIT AC 18HJ GOLDEN,HAIER,HASHOO,SPLIT AC,8,,,,
HAIER SPLIT AC 19HFC WHITE,HAIER,HASHOO,SPLIT AC,17,,,,
HAIER SPLIT AC 19HFS (G) GOLDEN,HAIER,HASHOO,SPLIT AC,6,,,,
HAIER SPLIT AC 19LF,HAIER,HASHOO,SPLIT AC,20,,,,
HAIER SPLIT AC 20HFTEX T3 (DG) GRAY,HAIER,HASHOO,SPLIT AC,4,,,,
HAIER SPLIT AC 20HFTEX T3 (OW) WHITE,HAIER,HASHOO,SPLIT AC,6,,,,
HAIER SPLIT AC 20HJUV GOLDEN,HAIER,HASHOO,SPLIT AC,5,,,,
HAIER SPLIT AC 24CF,HAIER,HASHMI SHOP,SPLIT AC,6,,,,
HAIER SPLIT AC 24HFAB(GREY) T3 INVERTER,HAIER,HASHOO,SPLIT AC,3,,,,
HAIER SPLIT AC SOLAR HYBRID (IV) (OW) T3 PLUS,HAIER,HASHOO,SPLIT AC,5,,,,
HAIER SPLIT AC SOLAR HYBRID 1.5TON (IV) (OW) T3 PLUS,HAIER,Dastagir,SPLIT AC,10,,,,
HAIER SPLIT AC SOLAR HYBRID SOLAR PANEL,HAIER,HASHMI SHOP,SPLIT AC,2,,,,
HAIER W/D HDR-TC2C1GB (BLACK),HAIER,HASHOO,W/D,8,,,,
HAIER W/D HDR-TC2C1GR (RED),HAIER,HASHOO,W/D,8,,,,
HAIER W/D HWD-206WR,HAIER,HASHMI SHOP,W/D,1,,,,
HAIER W/M 100-1217,HAIER,HASHOO,W/M,3,,,,
HAIER W/M 100-196E,HAIER,HASHOO,W/M,4,,,,
HAIER W/M 100-196G,HAIER,HASHOO,W/M,4,,,,
HAIER W/M 100-196S WB,HAIER,HASHOO,W/M,5,,,,
HAIER W/M 100BS,HAIER,HASHMI SHOP,WM/,1,,,,
HAIER W/M 120-35,HAIER,Dastagir,W/M,32,,,,
HAIER W/M 120AS,HAIER,Dastagir,W/M,2,,,,
HAIER W/M 120AS (MG),HAIER,HASHOO,W/M,2,,,,
HAIER W/M 130-1217 E,HAIER,HASHOO,WM/,13,,,,
HAIER W/M 130-1217 GB,HAIER,HASHOO,W/M,4,,,,
HAIER W/M 130-1217 WB,HAIER,HASHOO,W/M,5,,,,
HAIER W/M 75AS,HAIER,HASHOO,W/M,5,,,,
HAIER W/M 80-1217 E,HAIER,HASHOO,W/M,17,,,,
HAIER W/M 80-1217 WB,HAIER,HASHMI SHOP,W/M,14,,,,
HAIER W/M 80-186 W,HAIER,SEA-BREEZE,W/M,1,,,,
HAIER W/M 80-60,HAIER,Dastagir,WM/,1,,,,
HAIER W/M 80CS WHITE,HAIER,HASHOO,W/M,1,,,,
HOMAGE M/O HDG-201S,HOMAGE,HASHOO,M/O,13,,,,
HOMAGE M/O HDSO-203S,HOMAGE,HASHOO,M/O,1,,,,
HOMAGE M/O HMSO-2020B,HOMAGE,HASHOO,M/O,20,,,,
HOMAGE M/OVEN HDG-2312B,HOMAGE,HASHOO,M/O,5,,,,
HOMAGE M/OVEN HDG-2313B,HOMAGE,HASHOO,M/O,6,,,,
HOMAGE M/OVEN HDG-282,HOMAGE,HASHOO,M/O,11,,,,
HOMAGE M/OVEN HDG-342S,HOMAGE,HASHOO,M/O,6,,,,
HOMAGE M/OVEN HDG-451S,HOMAGE,HASHOO,M/O,16,,,,
HOMAGE M/OVEN HMSO-2019B,HOMAGE,HASHOO,M/O,23,,,,
HOMAGE R/F 47222 VCM GHL NEW STAR SERIES (220-,HOMAGE,HASHOO,REFRIGERATOR,4,,,,
HOMAGE R/F 47332 GD GNG NEW CRYSTAL SERIES,HOMAGE,HASHOO,REFRIGERATOR,2,,,,
HOMAGE R/F 47332 GD MRG NEW CRYSTAL SERIES,HOMAGE,DILPASAND,REFRIGERATOR,5,,,,
HOMAGE R/F 47332 VCM GHL NEW STAR SERIES (280-,HOMAGE,HASHOO,REFRIGERATOR,3,,,,
HOMAGE R/F 47442 GD MIG INVERTER CRYSTAL,HOMAGE,HASHOO,REFRIGERATOR,14,,,,
HOMAGE R/F 47442 GD MRG NEW CRYSTAL SERIES,HOMAGE,DILPASAND,REFRIGERATOR,5,,,,
HOMAGE R/F 47442 VCM GHL NEW STAR SERIES (320-,HOMAGE,HASHOO,REFRIGERATOR,3,,,,
HOMAGE R/F 47452 TECH INVERTER R-310 BKG,HOMAGE,HASHOO,REFRIGERATOR,2,,,,
HOMAGE R/F 47452 TECH INVERTER R-310 MRG,HOMAGE,HASHOO,REFRIGERATOR,2,,,,
HOMAGE R/F 47552 CRYSTAL INV PURPLE ARROW (R-400),HOMAGE,HASHOO,REFRIGERATOR,5,,,,
HOMAGE R/F 47552 GD MIG INVERTER CRYSTAL,HOMAGE,HASHOO,REFRIGERATOR,3,,,,
HOMAGE R/F 47552 GD MRG NEW CRYSTAL SERIES,HOMAGE,HASHOO,REFRIGERATOR,5,,,,
HOMAGE R/F 47552 VCM GHL NEW STAR SERIES (400-,HOMAGE,DILPASAND,REFRIGERATOR,5,,,,
HOMAGE R/F 47562 TECH INVERTER R-410 BKG,HOMAGE,HASHOO,REFRIGERATOR,2,,,,
HOMAGE R/F 47662 CRYSTAL INV PURPLE ARROW (R-480),HOMAGE,HASHOO,REFRIGERATOR,6,,,,
HOMAGE R/F 47662 GD GNG NEW CRYSTAL SERIES,HOMAGE,HASHOO,REFRIGERATOR,3,,,,
HOMAGE R/F 47662 GD MIG INVERTER CRYSTAL,HOMAGE,HASHOO,REFRIGERATOR,5,,,,
HOMAGE R/F 47662 GD MRG NEW CRYSTAL SERIES,HOMAGE,HASHOO,REFRIGERATOR,4,,,,
HOMAGE R/F 47662 VCM GHL NEW STAR SERIES (400-,HOMAGE,HASHOO,REFRIGERATOR,2,,,,
HOMAGE R/F 47672 TECH INVERTER R-450 BKG,HOMAGE,HASHOO,REFRIGERATOR,2,,,,
HOMAGE R/F 47672 TECH INVERTER R-450 MRG,HOMAGE,HASHOO,REFRIGERATOR,3,,,,
HOMAGE R/F 47782 TECH INVERTER R-550 BKG,HOMAGE,HASHOO,REFRIGERATOR,1,,,,
HOMAGE R/F 47782 TECH INVERTER R-550 MRG,HOMAGE,HASHOO,REFRIGERATOR,4,,,,
HOMAGE R/F HRF-1051F,HOMAGE,HASHOO,REFRIGERATOR,6,,,,
HOMAGE SDA AIR FRYER HAF-4LMB0,HOMAGE,HASHOO,AIR FRYER,4,,,,
HOMAGE SDA AIR FRYER HAF-5LDB0,HOMAGE,HASHOO,AIR FRYER,3,,,,
HOMAGE SDA AIR PURIFIER HAP-251DWB,HOMAGE,HASHOO,AIR PURIFIER,4,,,,
HOMAGE SDA AIR PURIFIER HAP-403DWB,HOMAGE,HASHOO,AIR PURIFIER,2,,,,
HOMAGE SDA CHOPPER HCH-401A0,HOMAGE,HASHMI SHOP,CHOPPER,28,,,,
HOMAGE SDA CITRUS JUICER HCJ-090A0,HOMAGE,HASHOO,CITRUS,12,,,,
HOMAGE SDA ELECTRIC KETTLE HKT-1817SSB0,HOMAGE,HASHOO,KETTLE,5,,,,
HOMAGE SDA FOOD PROCESSOR HFP-711A0,HOMAGE,HASHOO,FOOD PROCESSOR,1,,,,
HOMAGE SDA GARMENT STEAMER HGS-1121WE-,HOMAGE,HASHOO,GARMENT STEAMER/HOMAGE,22,,,,
HOMAGE SDA GARMENT STEAMER HGS-1151BE-,HOMAGE,HASHOO,GARMENT STEAMER/HOMAGE,22,,,,
HOMAGE SDA GARMENT STEAMER HGS-2202WE -,HOMAGE,HASHOO,GARMENT STEAMER/HOMAGE,1,,,,
HOMAGE SDA HAND MIXER HHM-302A0,HOMAGE,HASHOO,HAND MIXER,5,,,,
HOMAGE SDA IRON HDI-1201D0 DRY IRON,HOMAGE,HASHOO,IRON,49,,,,
HOMAGE SDA IRON HDI-1202D0 DRY IRON,HOMAGE,HASHOO,IRON,39,,,,
HOMAGE SDA POWER JUICER 4IN1 HPJ-504A0,HOMAGE,HASHOO,JUICER,8,,,,
HOMAGE SDA SANDWICH MAKER 3IN1 HSM-70300-,HOMAGE,HASHOO,SANDWICH MAKER / HOMAGE,4,,,,
HOMAGE SDA SANDWICH MAKER HSM-70200 -,HOMAGE,HASHMI SHOP,SANDWICH MAKER/HOMAGE,4,,,,
HOMAGE SPLIT AC 1212S SMART CRYSTAL,HOMAGE,HASHOO,SPLIT AC,23,,,,
HOMAGE SPLIT AC 1213S E-GRANDE,HOMAGE,HASHOO,SPLIT AC,107,,,,
HOMAGE SPLIT AC 1220S SMART COOL,HOMAGE,HASHOO,SPLIT AC,12,,,,
HOMAGE SPLIT AC 1221S CLASSIC,HOMAGE,HASHOO,SPLIT AC,65,,,,
HOMAGE SPLIT AC 1222S ELEMENT ULTRA,HOMAGE,HASHOO,SPLIT AC,13,,,,
HOMAGE SPLIT AC 12C01S PRESTIGE,HOMAGE,HASHOO,SPLIT AC,9,,,,
HOMAGE SPLIT AC 1813S E-GRANDE,HOMAGE,HASHOO,SPLIT AC,1,,,,
HOMAGE SPLIT AC 1820S E-SMART,HOMAGE,HASHOO,SPLIT AC,20,,,,
HOMAGE SPLIT AC 1821S CLASSIC,HOMAGE,SEA-BREEZE,SPLIT AC,79,,,,
HOMAGE SPLIT AC 18C01S PRESTIGE,HOMAGE,HASHOO,SPLIT AC,7,,,,
HOMAGE SPLIT AC 2413S E-GRANDE,HOMAGE,HASHOO,SPLIT AC,1,,,,
HOMAGE SPLIT AC 2421S CLASSIC,HOMAGE,HASHOO,SPLIT AC,17,,,,
HOMAGE SPLIT AC HGS-18D01S GRANDE,HOMAGE,HASHOO,SPLIT AC,6,,,,
HOMAGE STAND MIXER HKM-103A0,HOMAGE,HASHOO,STAND MIXER,1,,,,
HOMAGE TABLE BLENDER HTB-603A0,HOMAGE,HASHOO,BLENDER,5,,,,
HOMAGE VERTICAL FREEZER HVF-2601V,HOMAGE,HASHOO,VERTICAL FREEZER,6,,,,
HOMAGE W/DISPENSER 49320 BLACK TABLE TOP,HOMAGE,HASHOO,W/D,10,,,,
HOMAGE W/DISPENSER 49331 BLACK W/O R/F,HOMAGE,HASHOO,W/D,7,,,,
HOMAGE W/DISPENSER 49332 BLACK WITH REF,HOMAGE,HASHOO,W/D,18,,,,
HOMAGE W/DISPENSER 49432 BLG WITH R/F,HOMAGE,HASHOO,W/D,10,,,,
HOMAGE W/DISPENSER 49432 GLG LEAF 3WT WITH REF,HOMAGE,HASHOO,W/D,20,,,,
HOMAGE W/DISPENSER 49432 MLG LEAF 3WT WITH REF,HOMAGE,HASHOO,W/D,10,,,,
HOMAGE W/DISPENSER 49432 MRG WITH R/F,HAIER,HASHOO,W/D,14,,,,
HOMAGE W/M 49112SAG GD BLUE BUBBLES,HOMAGE,HASHOO,W/M,15,,,,
HOMAGE W/M HW-49102 GLASS PEARL BLACK ECO SERIES,HOMAGE,HASHOO,W/M,1,,,,
HOMAGE W/M HW-49112 GLASS PEARL BLACK ECO SERIES,HOMAGE,HASHOO,W/M,1,,,,
HOMAGE W/M HW-49112 GLASS PEARL GREEN ECO SERIES,HOMAGE,HASHOO,W/M,2,,,,
HOMAGE W/M HW-49112 GLASS-GRAY DIAMOND,HOMAGE,HASHOO,W/M,6,,,,
HOMAGE W/M HW-49112 PLASTIC-GRAY,HOMAGE,Dastagir,W/M,5,,,,
KENWOOD AUTO W/M 10005FAF-DG,KENWOOD,HASHOO,AWM,1,,,,
KENWOOD AUTO W/M 7003FAT-DG,KENWOOD,HASHOO,AWM,1,,,,
KENWOOD AUTO W/M 8005FAF-DG,KENWOOD,HASHOO,AWM,2,,,,
KENWOOD CASSETTE 1.5TON NORMAL KCT-1801H,KENWOOD,HASHOO,CASSETTE,5,,,,
KENWOOD CASSETTE 2TON INVERTER KCT-2402,KENWOOD,HASHOO,CASSETTE,1,,,,
KENWOOD CASSETTE 4TON NORMAL KCT-4801H,KENWOOD,HASHOO,CASSETTE,3,,,,
KENWOOD FLOOR STANDING 2446F E-BREEZE,KENWOOD,HASHOO,FLOOR STANDING,10,,,,
KENWOOD FLOOR STANDING 2452FHI SUPERIA,KENWOOD,HASHOO,FLOOR STANDING,10,,,,
KENWOOD FLOOR STANDING 2TON 2441F IMPERIAL,KENWOOD,HASHOO,FLOOR STANDING,1,,,,
KENWOOD FLOOR STANDING 4TON 4851FH E-FREEDOM,KENWOOD,HASHOO,FLOOR STANDING,6,,,,
KENWOOD R/F 220GD PERSONA BKG (22257),KENWOOD,HASHOO,REFRIGERATOR,5,,,,
KENWOOD R/F 220GD PERSONA MRG (22257),KENWOOD,HASHOO,REFRIGERATOR,5,,,,
KENWOOD R/F 220VCM PBG CLASSIC (22257),KENWOOD,HASHOO,REFRIGERATOR,4,,,,
KENWOOD R/F 220VCM PGY CLASSIC (22257),KENWOOD,HASHOO,REFRIGERATOR,7,,,,
KENWOOD R/F 24557 SMART INVERTER R-310 BKG,KENWOOD,HASHOO,REFRIGERATOR,3,,,,
KENWOOD R/F 24557 SMART INVERTER R-310 MRG,KENWOOD,HASHOO,REFRIGERATOR,3,,,,
KENWOOD R/F 25657 SMART INVERTER R-410 BKG,KENWOOD,HASHOO,REFRIGERATOR,1,,,,
KENWOOD R/F 25657 SMART INVERTER R-410 MRG,KENWOOD,DILPASAND,R/F,1,,,,
KENWOOD R/F 26757 SMART INVERTER R-450 BKG,KENWOOD,HASHOO,REFRIGERATOR,1,,,,
KENWOOD R/F 26757 SMART INVERTER R-450 MRG,KENWOOD,HASHOO,REFRIGERATOR,12,,,,
KENWOOD R/F 280GD BKG PERSONA (23357),KENWOOD,HASHOO,REFRIGERATOR,4,,,,
KENWOOD R/F 280GD MAROON INVERTECH (23357),KENWOOD,HASHOO,REFRIGERATOR,17,,,,
KENWOOD R/F 280GD MIRROR INVERTECH (23357),KENWOOD,HASHOO,REFRIGERATOR,6,,,,
KENWOOD R/F 280GD MRG PERSONA (23357),KENWOOD,HASHOO,REFRIGERATOR,3,,,,
KENWOOD R/F 280VCM GTX INVERTECH (23357),KENWOOD,HASHOO,REFRIGERATOR,5,,,,
KENWOOD R/F 280VCM PBG CLASSIC (23357),KENWOOD,HASHOO,REFRIGERATOR,7,,,,
KENWOOD R/F 280VCM PGY CLASSIC PLUS (23357),KENWOOD,HASHOO,REFRIGERATOR,5,,,,
KENWOOD R/F 320GD BKG PERSONA (24457),KENWOOD,HASHOO,REFRIGERATOR,11,,,,
KENWOOD R/F 320GD MAROON INVERTECH (24457),KENWOOD,HASHOO,REFRIGERATOR,10,,,,
KENWOOD R/F 320GD MIRROR INVERTECH (24457),KENWOOD,HASHOO,REFRIGERATOR,7,,,,
KENWOOD R/F 320GD MRG PERSONA (24457),KENWOOD,HASHOO,REFRIGERATOR,10,,,,
KENWOOD R/F 400GD BKG PERSONA (25557),KENWOOD,HASHOO,REFRIGERATOR,3,,,,
KENWOOD R/F 400GD MAROON INVERTECH (25557),KENWOOD,HASHOO,REFRIGERATOR,6,,,,
KENWOOD R/F 400GD MIRROR INVERTECH (25557),KENWOOD,HASHOO,REFRIGERATOR,1,,,,
KENWOOD R/F 400GD MRG PERSONA (25557),KENWOOD,HASHOO,REFRIGERATOR,4,,,,
KENWOOD R/F 400VCM GTX INVERTECH (25557),KENWOOD,DILPASAND,REFRIGERATOR,2,,,,
KENWOOD R/F 400VCM PBG CLASSIC (25557),KENWOOD,HASHOO,REFRIGERATOR,5,,,,
KENWOOD R/F 400VCM PGY NEW CLASSIC PLUS (25557),KENWOOD,HASHOO,REFRIGERATOR,3,,,,
KENWOOD R/F 480GD BKG PERSONA PLUS (26657),KENWOOD,HASHOO,REFRIGERATOR,3,,,,
KENWOOD R/F 480GD MAROON INVERTECH (26657),KENWOOD,HASHOO,REFRIGERATOR,16,,,,
KENWOOD R/F 480GD MIRROR INVERTECH (26657),KENWOOD,HASHOO,REFRIGERATOR,3,,,,
KENWOOD R/F 480GD MRG PERSONA (26657),KENWOOD,HASHOO,REFRIGERATOR,4,,,,
KENWOOD R/F 480VCM GTX INVERTECH (26657),KENWOOD,HASHMI SHOP,REFRIGERATOR,2,,,,
KENWOOD R/F 480VCM PEARL BLUE INVERTECH (26657),KENWOOD,HASHOO,REFRIGERATOR,10,,,,
KENWOOD R/F 480VCM PGY NEW CLASSIC PLUS (26657),KENWOOD,HASHOO,REFRIGERATOR,1,,,,
KENWOOD SPINNER KWS-1050S,KENWOOD,HASHOO,SPINNER,31,,,,
KENWOOD SPLIT AC 1235S E-ECO PLUS GREY 75%,KENWOOD,SEA-BREEZE,SPLIT AC,1,,,,
KENWOOD SPLIT AC 1266S E-SMART OYNX,KENWOOD,HASHOO,SPLIT AC,30,,,,
KENWOOD SPLIT AC 12B01S LUXURY PLUS,KENWOOD,HASHOO,SPLIT AC,22,,,,
KENWOOD SPLIT AC 12B02S LUXURY PRO,KENWOOD,HASHOO,SPLIT AC,18,,,,
KENWOOD SPLIT AC 12B03SS LUXURY ULTRA,KENWOOD,HASHOO,SPLIT AC,16,,,,
KENWOOD SPLIT AC 12C01S GLORY PRO,KENWOOD,HASHOO,SPLIT AC,15,,,,
KENWOOD SPLIT AC 12C03S GLORY PLUS,KENWOOD,HASHOO,SPLIT AC,58,,,,
KENWOOD SPLIT AC 1839S E-SUPREME 60%,KENWOOD,SEA-BREEZE,SPLIT AC,1,,,,
KENWOOD SPLIT AC 1862S E-SUPREME PRO,KENWOOD,HASHMI SHOP,SPLIT AC,1,,,,
KENWOOD SPLIT AC 1863S E-SLEEK PRO,KENWOOD,HASHOO,SPLIT AC,1,,,,
KENWOOD SPLIT AC 1866S E-SMART OYNX,KENWOOD,HASHOO,SPLIT AC,63,,,,
KENWOOD SPLIT AC 1867S COMFORT PRO,KENWOOD,SEA-BREEZE,SPLIT AC,2,,,,
KENWOOD SPLIT AC 1872S E-SMART PURA,KENWOOD,HASHOO,SPLIT AC,60,,,,
KENWOOD SPLIT AC 1876S E-NOVA PRO,KENWOOD,HASHOO,SPLIT AC,45,,,,
KENWOOD SPLIT AC 18B01S LUXURY PLUS,KENWOOD,HASHOO,SPLIT AC,19,,,,
KENWOOD SPLIT AC 18B02S LUXURY PRO,KENWOOD,HASHOO,SPLIT AC,59,,,,
KENWOOD SPLIT AC 18B03SS LUXURY ULTRA,KENWOOD,HASHOO,SPLIT AC,4,,,,
KENWOOD SPLIT AC 18C01S GLORY PRO,KENWOOD,HASHOO,SPLIT AC,35,,,,
KENWOOD SPLIT AC 18C03S GLORY PLUS,KENWOOD,HASHOO,SPLIT AC,48,,,,
KENWOOD SPLIT AC 2434S E-PRIME PLUS 60%,KENWOOD,SEA-BREEZE,SPLIT AC,1,,,,
KENWOOD SPLIT AC 2465S ECO ULTRA,KENWOOD,HASHOO,SPLIT AC,6,,,,
KENWOOD SPLIT AC 2470S E-LUXURY PRO,KENWOOD,HASHOO,SPLIT AC,57,,,,
KENWOOD SPLIT AC 24B02S LUXURY PRO,KENWOOD,HASHOO,SPLIT AC,7,,,,
KENWOOD SPLIT AC 24C02S GLORY PRO,KENWOOD,HASHOO,SPLIT AC,18,,,,
KENWOOD STEAM IRON STP01,KENWOOD,HASHOO,IRON,20,,,,
KENWOOD W/M KWM-1010SA,KENWOOD,HASHOO,W/M,1,,,,
KENWOOD W/M KWM-1015SA,KENWOOD,HASHOO,W/M,1,,,,
KENWOOD W/M KWM-1016SA,KENWOOD,HASHOO,W/M,2,,,,
KENWOOD W/M KWM-211059 SAG BLACK FLOWER,KENWOOD,HASHMI SHOP,W/M,1,,,,
KENWOOD W/M KWM-21159 SAG ROSE PINK OPAL,KENWOOD,HASHOO,W/M,3,,,,
KENWOOD W/M KWM-231159 SAG BLACK FLOWER,KENWOOD,HASHOO,W/M,20,,,,
KENWOOD W/M KWM-899,KENWOOD,HASHMI SHOP,W/M,3,,,,
L.G AUTO W/M FRONT LOAD 7KG -,LG,HASHMI SHOP,AUTOMATIC W/M/LG,1,,,,
MIDEA CASSETTE 2TON INVERTER MCD1-24HRDN1,MIDEA,SEA-BREEZE,CASSETTE,3,,,,
MIDEA CASSETTE 2TON NORMAL MCD1-24HRN1 H&C,MIDEA,SEA-BREEZE,CASSETTE,1,,,,
MIDEA DISHWAHSER WQP12-5201F INVERTER BLACK 13SETS,MIDEA,HASHOO,DISHWASHER,2,,,,
MIDEA FLOOR STANDING INVERTER MFM-48HRDN1,MIDEA,SEA-BREEZE,FLOOR STANDING,2,,,,
MIDEA FLOOR STANDING MFPA-24HRDN1 SQUARE,MIDEA,SEA-BREEZE,FLOOR STANDING,4,,,,
MIDEA FLOOR STANDING MFTPA-24CRN1 COOL,MIDEA,SEA-BREEZE,FLOOR STANDING,12,,,,
MIDEA FRONT LOAD W/M MF200-D120-G 12W/8D KG GREY,MIDEA,HASHOO,FRONT LOAD AWM,4,,,,
MIDEA FRONT LOAD W/M MF200-MFL120 12KG,MIDEA,HASHOO,FRONT LOAD AWM,4,,,,
MIDEA FRONT LOAD W/M MF200-MFL90 9KG,MIDEA,HASHOO,FRONT LOAD AWM,5,,,,
MIDEA FRONT LOAD W/M MF200-W120-G 12KG GREY,MIDEA,HASHOO,FRONT LOAD AWM,3,,,,
MIDEA FRONT LOAD W/M MF200-W90-G 9KG GREY,MIDEA,HASHOO,FRONT LOAD AWM,3,,,,
MIDEA FRONT LOAD W/M MF200W90/W,MIDEA,HASHOO,FRONT LOAD AWM,1,,,,
MIDEA M/O 20L BLACK MM720C2MV,MIDEA,HASHOO,M/O,10,,,,
MIDEA M/O 25L BLACK AG9P022VB,MIDEA,HASHOO,M/O,3,,,,
MIDEA SPLIT 1 TON INVERTER 12HRDN1 AG2 FIGHTING,MIDEA,SEA-BREEZE,SPLIT AC,13,,,,
MIDEA SPLIT 1 TON INVERTER 12HRFN1,MIDEA,SEA-BREEZE,SPLIT AC,1,,,,
MIDEA SPLIT 1 TON INVERTER BREEZELESS 12HRFN8,MIDEA,SEA-BREEZE,SPLIT AC,30,,,,
MIDEA SPLIT 1 TON INVERTER MSEZ1B-12HRFN1 TITAN,MIDEA,SEA-BREEZE,SPLIT AC,54,,,,
MIDEA SPLIT 1.5 TON INVERTER 18HRFN1,MIDEA,SEA-BREEZE,SPLIT AC,27,,,,
MIDEA SPLIT 1.5 TON INVERTER BREEZELESS 18HRFN8,MIDEA,SEA-BREEZE,SPLIT AC,21,,,,
MIDEA SPLIT 1.5 ΤΟΝ NORMAL 18CRN1,MIDEA,SEA-BREEZE,SPLIT AC,22,,,,
MIDEA SPLIT 2 TON INVERTER 24HRDN1 AG2 ECO,MIDEA,SEA-BREEZE,SPLIT AC,5,,,,
MIDEA SPLIT 2 TON INVERTER BREEZELESS 24HRFN8,MIDEA,SEA-BREEZE,SPLIT AC,5,,,,
MIDEA SPLIT 2 TON INVERTER MSEZ1D-24HRFN1 EXTREME PLUS,MIDEA,SEA-BREEZE,SPLIT AC,9,,,,
MIDEA SPLIT AC 2.0TON 24CRN1,MIDEA,SEA-BREEZE,SPLIT AC,29,,,,
MIDEA SPLIT AC MSAG2C-18HRDN1-QC2 AG2 FIGHTING,MIDEA,SEA-BREEZE,SPLIT AC,17,,,,
MIDEA SPLIT AC MSEF1B-12HRFN1-QC6 GO EASY,MIDEA,SEA-BREEZE,SPLIT AC,58,,,,
MIDEA SPLIT AC MSEZ1C-18HRFN1-QC2 TITAN,MIDEA,SEA-BREEZE,SPLIT AC,68,,,,
MIDEA SPLIT AC MSEZ2B-12HRFN1-QC6 EXTREME PLUS,MIDEA,SEA-BREEZE,SPLIT AC,11,,,,
MIDEA SPLIT AC MSEZ2B-12HRFN1-QC6-B EXTREME PLUS GREY,MIDEA,SEA-BREEZE,SPLIT AC,29,,,,
MIDEA SPLIT AC MSEZ2C-18HRFN1-QC6 EXTREME PLUS,MIDEA,SEA-BREEZE,SPLIT AC,15,,,,
MIDEA SPLIT AC MSEZ2C-18HRFN1-QC6-B EXTREME PLUS GREY,MIDEA,SEA-BREEZE,SPLIT AC,43,,,,
MIDEA SPLIT AC MSEZ2D-24HRFN1-QCOW-B EXTREME PLUS GREY,MIDEA,SEA-BREEZE,SPLIT AC,7,,,,
MIDEA W/D YL2036S (BOTTOM LOAD),MIDEA,HASHOO,W/D,9,,,,
MIDEA W/D YL2037S-B (TOP LOAD),MIDEA,HASHOO,W/D,46,,,,
MIDEA WATER HEATER 50L STORAGE D50-20FN,MIDEA,HASHOO,GEYSER,3,,,,
MIDEA WATER HEATER STORAGE D100-20EFG,MIDEA,HASHOO,GEYSER,2,,,,
MIDEA WATER HEATER STORAGE D30-20EFG,MIDEA,HASHOO,GEYSER,29,,,,
MIDEA WATER HEATER STORAGE D50-20EFG,MIDEA,HASHOO,GEYSER,10,,,,
MITSUBISHI SPLIT 1.5TON INVERTER HJ50VA,MITSUBISHI,SEA-BREEZE,SPLIT AC,1,,,,
MOULINEX BLENDER 3IN1 LM242025,MOULINEX,HASHMI SHOP,3 IN 1,1,,,,
"OKTRA LED 40"" SMART K569S",OKTRA LED,HASHOO,LED,1,,,,
ORIENT R/F 330 ICE GALAXY SILVER,ORINET,HASHOO,REFRIGERATOR,1,,,,
PANASONIC IRON 22AWT,PANASONIC,HASHMI SHOP,IRON,5,,,,
PANASONIC SPLIT 1.5 ΤΟΝ INVERTER 18XKF-9,PANASONIC,Dastagir,SPLIT AC,3,,,,
PEL M/OVEN 23 SLD SILVER LINE DIGITAL BLACK,PEL,HASHMI SHOP,M/O,1,,,,
PEL M/OVEN PM0-26 DESIRE BLACK,PEL,HASHMI SHOP,M/O,1,,,,
PEL R/F 1400 LIFE CHARCOAL GREY,PEL,HASHMI SHOP,REFRIGERATOR,1,,,,
PEL SPLIT AC 1.5TON INVERTER ACE,PEL,HASHMI SHOP,SPLIT AC,1,,,,
PEL W/D 425 FLAT GD CHOCOLATE PRISM (CP),PEL,HASHMI SHOP,W/D,1,,,,
PEL W/D 425 FLAT GD PURPLE BLAZE (PB),PEL,HASHMI SHOP,W/D,1,,,,
PEL W/D 525 GD CURVED PURPLE BLAZE,PEL,HASHMI SHOP,W/D,1,,,,
PEL W/D 525 GD CURVED RED BLAZE,PEL,HASHMI SHOP,W/D,1,,,,
PHILIPS AIR FRYER 9270,PHILIPS,HASHMI SHOP,AIR FRYER,6,,,,
SAMSUNG AUTO W/M WA10CK4545BY GREY,SAMSUNG,HASHMI SHOP,AWM,1,,,,
SAMSUNG AUTO W/M WA90F5S2,SAMSUNG,HASHMI SHOP,AWM,1,,,,
SG WASHER,SG,Dastagir,W/M,2,,,,
SG WATER PURIFIER -,SG,HASHOO,UNKNOWN/UNKNOWN,1,,,,
SUPER ASIA ELECTRIC WATER HEATER SEH-16,SUPER ASIA,HASHMI SHOP,GEYSER,1,,,,
"TCL LED 50"" 50C6K",TCL,HASHMI SHOP,LED,1,,,,
TOSHIBA AUTO W/M 1000GM,TOSHIBA,Dastagir,AWM,1,,,,
TOSHIBA AUTO W/M AWF-820,TOSHIBA,Dastagir,AWM,1,,,,
UCOOL AIR CURTAIN 3FEET UCA-315Y,UCOOL,HASHOO,AIR CURTAIN,15,,,,
UCOOL AIR CURTAIN 4FEET UCA-415Y,UCOOL,HASHMI SHOP,AIR CURTAIN,6,,,,
UCOOL AIR CURTAIN 5FEET UCA-515Y,UCOOL,HASHOO,AIR CURTAIN,5,,,,
UCOOL AIR CURTAIN 6FEET UCA-615Y,UCOOL,HASHOO,AIR CURTAIN,16,,,,
WESTPOINT AIR COOLAR WF1301-,WESTPOINT,HASHMI SHOP,AIR COOLER,1,,,,
WESTPOINT AIR FRYER WF-5254,WESTPOINT,HASHMI SHOP,AIR FRYER,1,,,,
WESTPOINT INDUCTION COOKER WF-146,WESTPOINT,HASHMI SHOP,INDUCTION COOKER,1,,,,
WESTPOINT R/F 205,WESTPOINT,HASHOO,REFRIGERATOR,1,,,,
````

## File: tests/fixtures/test product list.csv
````
Name,Brands
Haier HR-66B 2.5 Cu Ft Black Single Door Non-Inverter Refrigerator,HAIER
Haier HRF-316 IAPA 11 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-346 IAPA 12 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-438 IAPA+ 15 Cu Ft Purple Digital Inverter Refrigerator,HAIER
HAIER 8.5KG HWM85-1269S6 AUTOMATIC TOP LOAD WASHING MACHINE,HAIER
Haier Model HWM100-316S6 Fully Automatic Top Load Washing Machine,HAIER
HAIER Model HWM 120-316S6 12KG AUTOMATIC TOP LOAD WASHING MACHINE,HAIER
Haier HRF-186EBS 6 Cu Ft Silver E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-216EBS 8 Cu Ft Silver E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-246EBD 9 Cu Ft Dark Metallic E-Star Non-Inverter Refrigerator,HAIER
Haier HWS 60-50 Spin Dryer – Electric Clothes Spinner Machine | Fast Drying Laundry Solution | Portable & Energy Efficient,HAIER
"Haier HWM 80-1217 Top Load Washing Machine – 8kg Semi Automatic Washer | Powerful Cleaning, Durable & Energy Saving Home Appliance",HAIER
Haier 7.5 KG Twin Tub HWM-75-AS Washing Machine,HAIER
HAIER 20 LITRE SOLO HMW-20MXP3 MICROWAVE OVEN WITH AIRPODS,HAIER
"Haier HMW-20MPB 20L Microwave Oven – Solo & Grill Microwave | Defrost, Reheat, Quick Cooking, Compact Kitchen Oven",HAIER
Haier HMW-20MBS Solo Microwave Oven | 20-litre capacity,HAIER
Haier Model HMW-20MWS Solo Series Microwave Oven 20Ltr,HAIER
PEL PCWD 525 Curved Glass Door Water Dispenser,PEL
WestPoint WF-6807 Deluxe Ceramic Coating Plate Hair Straightener,WestPoint Pakistan
WestPoint WF-6810 Professional Ceramic Coating Plate Hair Straightening Brush,WestPoint Pakistan
WestPoint WF-6613 Professional Cordless Freedom Hair Clipper,WestPoint Pakistan
WestPoint WF-6813 Professional LED Charge Indicator Hair Clipper,WestPoint Pakistan
WestPoint WF-6217 Deluxe Overheat Protection Hair Dryer,WestPoint Pakistan
WestPoint WF-6362 Deluxe IPX7 Water Resistant Epilator,WestPoint Pakistan
WestPoint WF-1156 Deluxe Fast Heat Up Garment Steamer,WestPoint Pakistan
WestPoint WF-614 Deluxe Pure Warm Vapor Facial Steamer,WestPoint Pakistan
WestPoint WF-3166 Deluxe 40cm Non-Stick Pizza Pan,WestPoint Pakistan
WestPoint WF-1253 300ml Deluxe Handy Garment Steamer,WestPoint Pakistan
WestPoint WF-3870 Deluxe Magic Herbal Spa Foot Massager,WestPoint Pakistan
WestPoint WF-1846 Professional 4 in 1 1000W 1.5L Food Processor,WestPoint Pakistan
WestPoint WF-4257 Deluxe 6.5L 1700W Rapid Air Fryer,WestPoint Pakistan
"WestPoint WF-408 Cordless Kettle – Fast Boiling, Modern Convenience",WestPoint Pakistan
WestPoint WF-4360 5 kg Kitchen Scale,WestPoint Pakistan
WestPoint WF-672 1000 Watts Dry Iron,WestPoint Pakistan
WestPoint WF-2020 2200 Watts Steam Iron,WestPoint Pakistan
WestPoint WF-332 350 Watts Blender & Grinder,WestPoint Pakistan
WestPoint WF-2023 1.8 Liters Coffee Maker,WestPoint Pakistan
WestPoint WF-9228 500ml Deluxe Dry & Wet Grinder,WestPoint Pakistan
WestPoint WF-8818 1000 Watts Robo Max Kitchen Chef 5 in 1 Food Processor,WestPoint Pakistan
WestPoint WF-4201 Hand Blender 3-in-1,WestPoint Pakistan
WestPoint WF-2800RK 1500 Watts Rotisserie Oven with Kebab Grill,WestPoint Pakistan
WestPoint WF-142 2000 Watts Ceramic Cooker,WestPoint Pakistan
WestPoint WF-251 188 mm Professional Hot Plate,WestPoint Pakistan
WestPoint WF-7108 Insect Killer,WestPoint Pakistan
WestPoint WF-1097W Professional 2.0L Stainless Steel Bowl Chopper,WestPoint Pakistan
WestPoint WF-5350 Professional 15-Cup 900W Rice Cooker,WestPoint Pakistan
WestPoint WF-3669 Deluxe High Suction Vacuum Cleaner,WestPoint Pakistan
WestPoint WF-830DG Deluxe 1050W Microwave Oven With Grill,WestPoint Pakistan
WestPoint WF-5147 Deluxe Electric Fan Heater,WestPoint Pakistan
WestPoint WF-2564 Professional 4 Slice 1400W Pop Up Toaster,WestPoint Pakistan
WestPoint WF-04 Deluxe Manual Quick Chopper,WestPoint Pakistan
WestPoint WF-07 Deluxe Hand Press Kitchen Slicer,WestPoint Pakistan
WestPoint WP-6316 Professional 16 Liter Commercial Electric Kettle,WestPoint Pakistan
WestPoint WF-6808 Deluxe Ceramic Coating Plate Hair Straightener,WestPoint Pakistan
WestPoint WF-6713 Professional Cordless Freedom Hair Clipper,WestPoint Pakistan
WestPoint WF-6203 Deluxe Overheat Protection Hair Dryer,WestPoint Pakistan
WestPoint WF-1353 Professional Handy Garment Steamer,WestPoint Pakistan
WestPoint WF-1833 Deluxe 3 in 1 750W 1.0L Food Processor,WestPoint Pakistan
WestPoint WF-2405 Deluxe 750W Stainless Steel Spinner Juicer,WestPoint Pakistan
WestPoint WF-4256 Deluxe 8L 1500W Glass Window Air Fryer,WestPoint Pakistan
WestPoint WF-5259 25L Deluxe Air Fryer With Rotisserie Oven,WestPoint Pakistan
"WestPoint Cordless Kettle WF-409 – Fast Boiling, Sleek Design",
WestPoint WF-6174 2 Liters Cordless Kettle,WestPoint Pakistan
WestPoint WF-772 1000 Watts Deluxe Dry Iron,WestPoint Pakistan
WestPoint WF-2063 2200 Watts Steam Iron,WestPoint Pakistan
WestPoint WF-333 Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-367 Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-9225 80 g Professional Dry/Wet Grinder,WestPoint Pakistan
WestPoint WF-2024 1.5 Liters Coffee Maker,WestPoint Pakistan
WestPoint WF-2805 1750ml Kitchen Chef,WestPoint Pakistan
WestPoint WF-9901 400 Watts Deluxe Hand Mixer,WestPoint Pakistan
WestPoint WF-4626 5 Liters Stand Mixer,WestPoint Pakistan
WestPoint WF-2310RK 1500 Watts Rotisserie Oven with Kebab Grill,WestPoint Pakistan
WestPoint WF-252 188 mm Professional Dual Hot Plate,WestPoint Pakistan
WestPoint WF-6514T 12 inch Roti Maker,WestPoint Pakistan
WestPoint WF-6093 Sandwich Toaster 3 in 1,WestPoint Pakistan
WestPoint WF-6193 Sandwich Toaster 3 in 1,WestPoint Pakistan
WestPoint WF-7110 Deluxe 2x10W UV Tube Insect Killer,WestPoint Pakistan
WestPoint WF-1099 Professional 800W 5L Stainless Steel Bowl Chopper,WestPoint Pakistan
WestPoint WF-498 Professional 800W Kitchen Robot Food Processor,WestPoint Pakistan
WestPoint WF-6809 Professional Floating Ceramic Coating Plate Hair Straightener,WestPoint Pakistan
WestPoint WF-6913 Professional Low Noise Type-C Hair Clipper,WestPoint Pakistan
WestPoint WF-6270 Deluxe Overheat Protection Hair Dryer,WestPoint Pakistan
WestPoint WF-1834 Deluxe 4 in 1 750W 1.0L Food Processor,WestPoint Pakistan
WestPoint WF-4258 Deluxe Dual Basket 9L 2200W Air Fryer,WestPoint Pakistan
WestPoint WF-5258 22 Liters Professional Power Air Fryer Oven,WestPoint Pakistan
WestPoint Cordless Kettle WF-578,WestPoint Pakistan
WestPoint WF-2451 1200 Watts Dry Iron,WestPoint Pakistan
WestPoint WF-342 1.5 Liters Deluxe Blender and Grinder,WestPoint Pakistan
WestPoint WF-2025 1.2 Liters Professional Coffee Maker,WestPoint Pakistan
WestPoint WF-4800RKC 2200 Watts Convection Rotisserie Oven with Kebab Grill,WestPoint Pakistan
WestPoint WF-6293 Sandwich Toaster 3 in 1,WestPoint Pakistan
WestPoint WF-960 Deluxe 25L Drum Steel Shell Vacuum Cleaner,WestPoint Pakistan
WestPoint WF-6280 Professional 2200W Heavy Duty Hair Dryer,WestPoint Pakistan
WestPoint WF-1155 Deluxe Adjustable Supporting Tubes Garment Steamer,WestPoint Pakistan
WestPoint WF-1154 Deluxe Adjustable Supporting Tubes Garment Steamer,WestPoint Pakistan
WestPoint WF-5160 Deluxe 500W Stainless Steel Filter Juicer,WestPoint Pakistan
WestPoint WF-1186 Deluxe 750W Stainless Steel Spinner Juicer,WestPoint Pakistan
WestPoint WF-5254 6 Liters Air Fryer,WestPoint Pakistan
WestPoint WF-6178C 4.2 Liters Deluxe Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-7005 250 kg Bath Scale,WestPoint Pakistan
WestPoint WF-9914 700ml Hand Blender,WestPoint Pakistan
WestPoint WF-2610RK 1500 Watts Deluxe Convection Rotisserie Oven with Kebab Grill,WestPoint Pakistan
WestPoint WF-691 Sandwich Maker,WestPoint Pakistan
WestPoint WF-1098 Professional 600W Food Processor Chopper,WestPoint Pakistan
WestPoint WF-3050 Deluxe Meat Grinder With Vegetable Cutter,WestPoint Pakistan
WestPoint WF-442 Deluxe 4 in 1 Kitchen Chef Food Processor,WestPoint Pakistan
WestPoint WF-231 Deluxe Magic Broom Handheld Vacuum Cleaner,WestPoint Pakistan
WestPoint WF-841DG Deluxe Digital Microwave Oven With Grill,WestPoint Pakistan
WestPoint WF-5307 Deluxe 1000W Electric Sun Heater,WestPoint Pakistan
WestPoint WF-2532 Professional 2 Slice 860W Pop Up Toaster,WestPoint Pakistan
WestPoint WF-6259 Deluxe Overheat Protection Hair Dryer,WestPoint Pakistan
WestPoint WF-343 1.5 Liters Deluxe Blender and Grinder,WestPoint Pakistan
WestPoint WF-8817 3.5 Liters Food Processor RoboMax,WestPoint Pakistan
WestPoint WP-6320 Professional 20 Liter Commercial Electric Kettle,WestPoint Pakistan
WestPoint WF-7115 20 W Deluxe Insect Killer,WestPoint Pakistan
WestPoint WF-103 Deluxe 21L Drum Steel Shell Vacuum Cleaner,WestPoint Pakistan
WestPoint WF-6260 Deluxe 1600W Foldable Hair Dryer,WestPoint Pakistan
WestPoint WF-7201GL Deluxe 500W Glass Jar Juicer Blender,WestPoint Pakistan
WestPoint WF-5257 Deluxe 6.5L 1700W LCD Display Air Fryer,WestPoint Pakistan
WestPoint WF-90B 1000 Watts Dry Iron,WestPoint Pakistan
Dawlance 8Kg Top Load DW-255 C Fully Automatic Washing Machine,DAWLANCE
Dawlance DTM-7650 Inverter Refrigerator,DAWLANCE
Dawlance 1.25 TON Frost X 20 Cool only Inverter Air Conditioner,DAWLANCE
Dawlance MWO DW-MD 15 SOLO WHITE Heating Microwave Oven,DAWLANCE
Orient 1 Ton Everest -12G Split Air Conditioner,ORIENT
Dawlance 1.5 Ton Frost 30 DC Inverter Cool Only Split Air Conditioner,DAWLANCE
Haier 12Kg HWM-120-35FF Single Tub Washing Machine,HAIER
Orient Water Dispencer OWD-529 Icon,ORIENT
Dawlance 9101 SD Mini Refrigerator,DAWLANCE
Dawlance REF-9140WB 8 Cu Ft Grey Double Door Refrigerator,DAWLANCE
"Haier HWM 130-1217 12kg Top Load Washing Machine – Manual Control Washer | Big Capacity, Strong Performance, Home Use",HAIER
Orient OWD-531 3 Taps Water Dispenser,ORIENT
Super Asia GEH-720AI Auto Ignition Gas Geyser – Heavy Gauge 20 Gallons | Super Asia Geyser | Gas Geyser | Geyser,Super Asia
Super Asia GEH-725AI Auto Ignition Gas Geyser – 25 Gallons Capacity | Super Asia Geyser | Gas Geyser | Geyser,Super Asia
Super Asia GEH-730AI Auto Ignition Gas Geyser – Heavy Gauge | 30 Gallons Capacity | Super Asia Geyser | Gas Geyser | Geyser,Super Asia
Super Asia GEH-735AI Auto Ignition Gas Geyser – Heavy Gauge | 35 Gallons Capacity | Super Asia Geyser | Gas Geyser | Geyser,Super Asia
Super Asia GEH-755AI Auto Ignition Gas Geyser – Heavy Gauge | 55 Gallons Capacity | Super Asia Geyser | Gas Geyser | Geyser,Super Asia
Super Asia EH-630 Electric Water Heater – 37 Liters | 2000W Fast Heating & Rust-Proof Body | Energy Efficient Water Heater | Electric Geyser,Super Asia
"Super Asia EH-640 Electric Geyser – 44 Liters | 2000W Fast Heating, Rust-Proof Tank & Energy Efficient Water Heater | Electric Geyser",Super Asia
"Super Asia EH-650 Electric Geyser – 52 Liters | 2000W Fast Heating, Rust-Proof Tank & Energy Efficient Water Heater | Electric Geyser",Super Asia
"Super Asia EH-660 Electric Geyser – 59 Liters | 2000W Fast Heating, Rust-Proof Tank & Energy Efficient Water Heater | Electric Geyser",Super Asia
"Super Asia EH-670 Electric Geyser – 65 Liters | 2000W Fast Heating, Rust-Proof Tank & Energy Efficient Water Heater | Electric Geyser",Super Asia
"Super Asia SEH-11 Electric Water Heater – 11 Liters | Safe, Durable & Energy Efficient Electric Geyser | Electric Geyser",Super Asia
"Super Asia SEH-16 Electric Water Heater – 16 Liters | Safe, Durable & Energy Efficient Electric Geyser | Electric Geyser",Super Asia
Nasgas Electric Geyser NEG-30 – Best 30 Liter Energy Efficient Electric Water Heater for Home Use,NASGAS
Nasgas Electric Geyser NEG-40 – High Capacity 40 Liter Energy Efficient Electric Water Heater for Home Use,NASGAS
Nasgas Electric Geyser NEG-50 – Premium 50 Liter Energy Efficient Electric Water Heater for Home and Bathroom,NASGAS
Nasgas Electric Geyser NEG-60 – High Capacity 60 Liter Energy Efficient Electric Water Heater for Home and Bathroom,NASGAS
Nasgas Semi Instant Electric Geyser SEM-100 – 100 Liter High Capacity Fast Heating Energy Efficient Water Heater for Home and Bathroom,NASGAS
NasGas 25 Liter Semi Instant Electric Geyser SEM-250 – Fast Heating Energy Efficient Water Heater for Home Use,NASGAS
Nasgas Gas Geyser DG-55 Super Dlx Auto – High Efficiency Automatic Gas Water Heater for Home and Bathroom,NASGAS
Nasgas Instant Gas Geyser DG-09 Dlx (Executive) – Fast Heating High Efficiency Gas Water Heater for Home and Bathroom,NASGAS
Nasgas Instant Gas Geyser DG-07 Dlx (Executive) – Fast Heating High Efficiency Gas Water Heater for Home and Bathroom,NASGAS
NasGas 20 Liter Semi-Instant Electric Geyser SEM-200 – Fast Heating Energy Efficient Water Heater for Home and Bathroom,NASGAS
"Nasgas Electric Geyser NEG-80 – Instant Heating, Energy Efficient Electric Water Heater""",NASGAS
Nasgas E+G Geyser 15 Gallon (DEG-15) Super Deluxe – Electric + Gas Hybrid Water Heater,NASGAS
"Nasgas Semi Instant Electric Geyser SEM-150 – Fast Heating, Energy Efficient Water Heater",NASGAS
"Nasgas Electric & Gas Geyser 35 Gallon (DEG-35) – Hybrid Water Heater, Energy Efficient & Fast Heating",NASGAS
"NasGas 10 Liter Semi Instant Electric Geyser SEM-101 – Fast Heating, Compact & Energy Efficient Water Heater",NASGAS
Hotline 50 Gallon Water Heater Geyser (10x10) – Dual Electric + Gas High-Capacity Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 30 Gallon Water Heater Geyser (14x14) – Dual Electric + Gas High-Efficiency Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 30 Gallon Water Heater Geyser (10x14) – High-Capacity Electric + Gas Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 20 Gallon Water Heater Geyser (14x16) – Electric + Gas High-Efficiency Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 30 Gallon Water Heater Geyser (10x10) – Dual Electric + Gas High-Capacity Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 15 Gallon Water Heater Geyser (14x16) – Electric + Gas Compact Home Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 30 Gallon Water Heater Geyser (14x16) – Dual Electric + Gas High-Capacity Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 20 Gallon Water Heater Geyser (10x10) – Electric + Gas Compact Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 20 Gallon Water Heater Geyser (14x14) – Electric + Gas Efficient Home Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 15 Gallon Water Heater Geyser (14x14) – Electric + Gas Compact Home Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 20 Gallon Water Heater Geyser (10x14) – Electric + Gas Efficient Home Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Hotline 15 Gallon Water Heater Geyser (10x10) – Electric + Gas Compact Home Geyser | Hotline Geyser | Gas + Electric Geyser | Geyser,Hotline
Midea 100 Liters Fast Electric Storage Geyser D100-20FN – High-Capacity Water Heater | Energy Efficient Electric Geyser | Electric Geyser,Midea
Midea 50 Liters Fast Electric Storage Geyser D50-20FN – Compact High-Efficiency Water Heater | Electric Geyser,Midea
Midea 30 Liters Fast Electric Storage Geyser D30-20FN – Compact High-Efficiency Water Heater | Electric Geyser,Midea
Boss K.E SIE 15CL Supreme Electric Water Heater – Compact High-Performance Geyser | Energy Efficient Electric Geyser | Electric Geyser,Boss
Boss K.E SIE 25CL Supreme Steel Electric Geyser – 25L High-Performance Water Heater | Energy Efficient Electric Geyser | Electric Geyser,Boss
Boss K.E SIE 30CL SS Elite ELCB Electric Geyser – 30L High-Capacity Stainless Steel Water Heater | Energy Efficient Electric Geyser | Electric Geyser,Boss
Hanco 20-GL 20 Gallon Hybrid Electric + Gas Storage Geyser (14x16),Hanco
Canon Electric Geyser | EWT-50 Water Heater | 50L Electric Geyser | Fast Heating Geyser | Rust-Proof Water Heater | Energy Efficient Electric Geyser | Canon Water Heater,
Hanco 710 7 Litre Instant Water Heater – Dual Ignition Gas Geyser,Hanco
Beetro Electric Geyser | FFE-15 Water Heater | 15L Electric Geyser | Fast Heating Geyser | Energy Efficient Water Heater | Quick Heating Electric Geyser | Beetro Water Heater Pakistan,
Hanco 30-GL 30 Gallon Hybrid Electric + Gas Storage Geyser (14×16),Hanco
WestPoint WF-271 188 mm Electric Hot Plate,WestPoint Pakistan
Hanco 7G2 – 7 Liters Instant Gas Water Heater | Dual Ignition | Imported | LPG / NG,Hanco
WestPoint WF-292 2000 Watts Professional Electric Hot Plate,WestPoint Pakistan
Hanco 30-GL – 30 Gallon Hybrid Electric + Gas Storage Geyser | 10×10 Heavy Duty Tank,Hanco
WestPoint WF-291 2000 Watts Electric Hot Plate,WestPoint Pakistan
Hanco 20-GL – 20 Gallon Hybrid Electric + Gas Storage Geyser | 10×10 Heavy Duty Tank,Hanco
Hanco 1010-B – 10 Liters Instant Gas Water Heater | Dual Ignition | Imported | LPG / NG,Hanco
WestPoint WF-262 2500 Watts Double Electric Hot Plate,WestPoint Pakistan
Hanco 7G3 – 7 Liters Instant Gas Water Heater | Dual Ignition | Imported | LPG / NG,Hanco
Hanco – Semi Instant Electric Water Heater | 80 Litres Smart Electric Geyser,Hanco
Boss KE-SIE-10 CL Supreme Steel Electric Water Heater – 10 Liter | Energy Efficient Electric Geyser | Electric Geyser,Boss
Hanco – Semi Instant Electric Water Heater | 50 Litres Smart Electric Geyser,Hanco
Hanco – Semi Instant Electric Water Heater Solar Compatible | 40 Litres Smart Electric Geyser,Hanco
Hanco – Semi Instant Electric Water Heater | 60 Litres Smart Electric Geyser,Hanco
Dawlance DWHP-3021 B Electric Hot Plate – Energy Efficient Hot Plate | Double Burner Cooking Plate,DAWLANCE
Dawlance DWHP-3021 W Electric Hot Plate – Energy Efficient Hot Plate | Double Burner Cooking Plate,DAWLANCE
WestPoint WF-281 188 mm Electric Hot Plate,WestPoint Pakistan
Kenwood IFC-01.000BK Ceramic Hot Plate – Energy Efficient Hot Plate | Infrared Cooking Plate,Kenwood
Anex AG-2062 Single Burner Electric Hot Plate,Anex
Anex AG-2061 Single Burner Electric Hot Plate,Anex
WestPoint WF-143 3.5 cm Induction Cooker,WestPoint Pakistan
Hanco 40L Semi Instant Electric Water Heater – Smart Geyser with Energy Saving & Temperature Control,Hanco
Nasgas Water Dispenser NWD-190 Hot & Cold with Refrigerator Cabinet – Energy Efficient,NASGAS
"Dawlance Water Dispenser WD-1051 Cloud White – Hot, Cold & Normal with Refrigerator",DAWLANCE
Hanco 60 Liters Semi Instant Electric Water Heater – Solar Compatible,Hanco
Hanco 50L Semi Instant Electric Water Heater – Solar Compatible Smart Geyser,Hanco
Hanco Fast Electric Water Heater 10 Liter – Instant Hot Water Geyser,Hanco
Hanco 710G 7 Litre Instant Gas Water Heater – Dual Ignition,Hanco
Hanco Fast Electric Water Heater 15 Liter – Semi Instant Electric Geyser,Hanco
Dawlance Water Dispenser WD-1051 Silver – Hot & Cold with Glass Door and Refrigerator,DAWLANCE
SG Electric Water Geyser – SGEG-14G (50 Liters) | Energy Efficient Electric Water Heater,SG
EcoStar Water Dispenser WD-300 – Hot & Cold Water Dispenser with 16 Liters Refrigerator Cabinet,EcoStar
SG Electric Water Geyser — SGEG-12G (40 Liters),SG
SG Electric Water Geyser – SGEG-16G (60 Liters),SG
"SG 14×16 30G Hybrid Electric + Gas Storage Geyser , Energy Efficient",SG
SG 10X10 30G Electric + Gas Hybrid Storage Geyser – Energy Efficient Plus,SG
"SG 10L Instant Electric Geyser — Hybrid Technology, Energy Efficient Plus",SG
SG 10X10 30G Steel Electric + Gas Hybrid Storage Geyser – Energy Efficient,SG
SG 12X16 30G Electric + Gas Hybrid Storage Geyser – Energy Efficient,SG
ELite ETO-12L Oven Toaster — 12 Liter Compact Electric Toaster Oven (800W),ELite
"ELite ETO-221R Oven Toaster – 22 Liters, 1500W (Black)",ELite
"ELite ETO-32R Oven Toaster – Compact, Powerful and Versatile",ELite
ELite Commercial Blender Pro Mix ECJB-200 – 1400W Powerful Professional Blender (3.0L Capacity),ELite
ELite EAF-008 Ultra Air Fryer – 4.5L Digital Touch Panel with Rapid Air Circulation,ELite
ELite EAF-05 Air Fryer – 4.5L Low-Fat Digital Air Fryer with High-Speed Air Circulation,ELite
ELite EAF-001 Air Fryer – 7L Touch Screen Digital Air Fryer with Air Crisp Technology,ELite
ELite SS-29 Garment Steamer – 2200W Electric Steamer with 3L Water Tank,ELite
ELite SS-39 Steam Iron – 2200W High-Power Iron with 3L Water Tank and Adjustable Rod,ELite
ELite EGS-500 Vertical Garment Steamer – 1.5L Large Tank with 1800W Power,ELite
ELite EWK-16B Electric Kettle – Fast Boiling 16L Kettle with Cool Touch Handle,ELite
ELite EWK-20B Electric Tea Kettle – 20L Commercial Stainless Steel Kettle with Rapid Boil & Keep-Warm Function,ELite
ELite EWK-30D Electric Tea Kettle – 30L Commercial Stainless Steel Kettle with Keep-Warm & Overheat Protection,ELite
ELite Metal Table Fan Copper ETF-30M,ELite
ELite Velocity Fan EVF-08 — Turbo Force Air Circulator,ELite
ELite Velocity Fan – EVF-20,ELite
ELite EBF-42 Bladeless Fan — 42” Remote Control Cooling Fan,ELite
"Elite Tower Fan ETF-001 — Powerful, Slim & Energy Efficient",ELite
ELite ETF-002 Tower Fan 38″ Black — Remote Control,ELite
ELite ETF-003 Evaporative Cooler Tower Fan 42” – 60W,ELite
ELite EWD-10 Water Dispenser with Refrigerator – Hot & Cold Water Dispenser 520W,ELite
ELite EWD-178T Tabletop Water Dispenser – 4.1L Silver Hot & Cold Water Dispenser,ELite
ELite EIK-16L Jasmine Insect Killer – 8 LED UV-A Flying Insect Trap 6W,ELite
ELite EIK-16 Insect Killer – 16W UV-A  Flying Insect Trap 3000V,ELite
ELite EIK-30 Insect Killer – 30W UV-A Flying Insect Trap 1600–1800V,ELite
ELite EQH-80Y4 Quartz Heater – 800W with Temperature Control,ELite
ELite EFH-804 Fan Heater – 2000W Adjustable Thermostat Compact,ELite
ELite EFH-901 Fan Heater – White Portable 2000W,ELite
ELite EVC-220 Vacuum Cleaner – High-Efficiency Low-Noise Electric Cleaner,ELite
ELite Anti-Allergy UVC Mite Vacuum Cleaner,ELite
ELite Deerma Mini Juice Blender – 400mL Portable Wireless Personal Blender,ELite
Elite Deerma DEM-ZQ600 Multi-Function Steam Cleaner,ELite
ELite Deerma JS-100 Wireless Portable Food Processor Mini Blender,ELite
ELite Deerma DEM-F325 Ultrasonic Air Humidifier – 5L Water Tank,ELite
ELite Deerma F500 Ultrasonic Humidifier & Manual Air Purifier – 5L Tank,ELite
"ELite ETO-354R Toaster Oven – 38 Liter, 1500W, Adjustable Thermostat & Timer",ELite
"ELite ETO-453R Oven Toaster - 45 Liter, 1800W, Timer & Adjustable Thermostat",ELite
"ELite ETO-653R Oven Toaster – 65L, 2200W, Thermostat Control, 120-Min Timer",ELite
"ELite Garment Steamer SS19 — 1750W, 3L Tank, Adjustable Rod, Powerful Wrinkle Removal",ELite
ELite EGS-400 Garment Steamer — Powerful Wrinkle Remover,ELite
ELITE Handheld Garment Steamer – EGS-300,ELite
ELite EEM-010 Espresso Coffee Machine – 850W | 15-Bar Pump,ELite
"ELite EEM-020 Fully Automatic Espresso Machine — Cappuccino, Latte Maker",ELite
ELite Pedestal Fan EPF-16A – 16-Inch Powerful Cooling Fan with Remote & Timer,ELite
"ELite EPF-18 Pedestal Fan — 18-Inch, 5 Blades, Remote Control, Powerful Home & Office Cooling",ELite
Elite EAC-70 – Evaporative Air Cooler – 70L Tank – Remote & Touch Control,ELite
"ELite Evaporative Air Cooler EAC-30 — 28L Tank, Remote Control",ELite
"ELite EAC-50 Evaporative Air Cooler — 12L Tank, Honeycomb Cooling, Remote Control",ELite
"ELite EAC-99A – Evaporative Air Cooler | Powerful Cooling, Large Tank, Low Power Consumption",ELite
ELite EIK-35S Insect Killer | Indoor UV-A Mosquito & Flying Insect Trap,ELite
ELite EIK-40 Insect Killer 41W | Indoor UV-A Mosquito & Flying Insect Trap,ELite
ELite Halogen Heater EHH-12 | Energy Efficient Portable Heater for Home & Office,ELite
"ELite Deerma Spray Mop TB-500 – 350L Water Tank, 360° Rotating Floor Cleaning Mop",ELite
ELite Deerma DEM-CS50M Mini Portable Dehumidifier — Home Air Dryer & Humidity Absorber,ELite
ELite Deerma DX-700 Vacuum Cleaner — Powerful Lightweight 2-in-1 Handheld & Stick Vacuum,ELite
ELite Deerma DX700S 2-in-1 Vertical Handheld Vacuum Cleaner – Powerful Lightweight Corded Vacuum,ELite
"ELite Deerma Electric Kettle DEM-SH30W – 1.7L, 2200W, Glass Body, Auto Safety Protection",ELite
ELite Deerma DEM-HS007 Foldable Garment Steamer — Portable Travel Wrinkle Remover,ELite
"ELite Deerma Ultrasonic Humidifier F-600 – 5L Cool Mist, 360° Rotatable Nozzle",ELite
"ELite Sun Heater ESH-L13 – Portable 2-Heat Setting, 1000W Energy-Saving",ELite
ELite Sun Heater ESH-L08 – 1000W Halogen Heater with Oscillation & Safety Features,ELite
"ELite Digital 3-in-1 Air Purifier EAP-911 – HEPA, Charcoal & UV-C Filter, 22 Inch Tower, Black",ELite
"ELite Digital Smart 3-in-1 Air Purifier EAP-922 – White, HEPA, Pet Dander & Dust Mite Filter",ELite
"ELite Aroma Air Purifier EAP-606 – Botanical Extracts, Bacteria & Virus Removal, 80m² Coverage",ELite
Dawlance DW-6580 WFL Twin Tub Washing Machine-8KG | Energy Efficient | Deep Waterfall Wash,DAWLANCE
Dawlance DW 6100-C Single Washing Machine-8KG | Durable Plastic Drum | Energy Efficient,DAWLANCE
Dawlance DWF 8200 X INV Front Load Washing Machine-8KG | Steam Care | A+++ Energy Rating,DAWLANCE
Dawlance DWT-9560 Top Load Washing Machine-8.5 KG | EZ Wash | Air Dry | Hygienic Cleaning,DAWLANCE
Dawlance DWT-9540 Top Load Washing Machine-8.5 KG | Eco Wash | Triple Waterfall,DAWLANCE
Dawlance DWT-9060 EZ-Fully Automatic Washing Machine | 9 KG | Triple Waterfall | Diamond Drum,DAWLANCE
Dawlance DWT-14470 ES—12KG Top Load Automatic Washing Machine | Triple Waterfall | Energy Saving,DAWLANCE
Dawlance DWT-14711 FLT—12KG Top Load Automatic Washing Machine | Touch Panel | EZ Wash,DAWLANCE
Dawlance DWT-1471 FLP—12KG Top Load Automatic Washing Machine | Powerful | Durable | Energy Efficient,DAWLANCE
Dawlance 14KG Top Load DW-1470PL Fully Automatic Washing Machine,DAWLANCE
Dawlance DWT-1166 X ADS+—9KG Top Load Automatic Washing Machine | Auto Dose Series | Energy Saving,DAWLANCE
Dawlance 1775 PL—17KG Fully Automatic Top Load Washing Machine | E-Care Series | Energy Saving,DAWLANCE
Dawlance DWT-11671 FLT—11KG Top Load Automatic Washing Machine | Hand Care Technology | EZ Wash,DAWLANCE
Dawlance DWT-11467 ES—10KG Top Load Fully Automatic Washing Machine | Triple Waterfall | EZ Wash,DAWLANCE
Dawlance DWT-1167 FLP—10KG Top Load Automatic Washing Machine | EZ Wash | Energy Saving,DAWLANCE
Dawlance 11Kg Top Load DW-1165PL Fully Automatic Washing Machine,DAWLANCE
Dawlance DS-6010—6KG Spinner Dryer | Blue Transparent Lid | Efficient & Quick Drying,DAWLANCE
Dawlance DW-9200 WFL—Extra Large Single Tub Washer | Powerful Washing | Built-in Buzzer,DAWLANCE
Dawlance DW-9200 CFL—Extra Large Single Tub Washer | 40–50 Clothes Capacity | Powerful & Reliable,DAWLANCE
Dawlance DW-8550 CB FL—7.5KG Twin Tub Washing Machine,DAWLANCE
Dawlance DW-10600—10KG Twin Tub Washing Machine | Deep Waterfall Wash | Powerful & Durable,DAWLANCE
Dawlance DW-6100 W - 6KG Single Tub Washing Machine | Deep Waterfall Wash | Energy Efficient,DAWLANCE
Dawlance 12KG Top Load DWT-270 C LVS+ Automatic Washing Machine,DAWLANCE
Dawlance DWT-260 C LVS+—9KG Top Load Automatic Washing Machine | Low Voltage Series | Triple Waterfall,DAWLANCE
Dawlance 8KG Twin Tub DW-6550-G Glass Lid Washing Machine,DAWLANCE
Dawlance DW-6550 C—8KG Twin Tub Washing Machine | Glass Lid | Deep Waterfall Wash,DAWLANCE
Dawlance DS-9000—12KG Single Tub Spinner Dryer | Stainless Steel Drum | Fast & Efficient Drying,DAWLANCE
Dawlance DW-10500—10–12KG Twin Tub Washing Machine | Deep Waterfall Wash | Wash & Spin,DAWLANCE
Dawlance DW-7500 TWIN TUB GLASS LID BLACK/GREY Washing Machine,DAWLANCE
Dawlance DS-6000—5KG Single Tub Spin Dryer | Quick & Efficient Drying,DAWLANCE
Dawlance 12KG DW-9100-G Single Tub Glass Door Washing Machine,DAWLANCE
Haier HS150-B1978S9—15KG Automatic Top Load Washing Machine | Touch Display | Quick Wash & Child Lock,HAIER
Haier HW-90-BP14959S8 Automatic Washing Machine—9KG | BLDC Motor | Steam & Hygiene Care,HAIER
EcoStar 9.5KG Fully Automatic Washing Machine EW-F9502 DC | Soft Press Technology | LED Display | 12 Programs | Energy Efficient Washer,EcoStar
Haier 10kg Twin Tub HTW100-196E Semi Automatic Washing Machine,HAIER
Haier 10kg Twin Tub HWM 100-1217 Semi Automatic Washing Machine,HAIER
Haier 12kg Twin Tub HWM 120AS Semi Automatic Washing Machine,HAIER
Haier 8kg Twin Tub HTW 80-186 Semi Automatic Washing Machine,HAIER
Haier 10kg Twin Tub HTW 110-186 Semi Automatic Washing Machine,HAIER
Haier HTW 100-1169 10kg Twin Tub Semi Automatic Washing Machine,HAIER
Haier 1 Ton HSU-12CF Non-Inverter Cool Only Split Air Conditioner,HAIER
Haier 1.5 ton HSU-18-CFT Non-Inverter Cool Only Split Air Conditioner,HAIER
Haier 2 Ton HSU-24-CF Non-Inverter Air Conditioner,HAIER
Haier 1 Ton HSU-13-LF Flexis Inverter Air Conditioner,HAIER
Haier 1.5 Ton HSU-19-LF Flexis Inverter Air Conditioner,HAIER
Haier 1.5 ton 19-RFP Wifi Split Inverter Heat & Cool  Air Conditioner,HAIER
Haier 1 Ton HSU-13HFCS Triple Inverter Heat & Cool Split Air Conditioner,HAIER
Haier 1 Ton HSU-13HFAB/W/G-T3 PRO DC Inverter Heat & Cool Air Conditioner,HAIER
HAIER 1.25 TON HSU-14HFTEX-OW T3 PLUS INVERTER AIR CONDITIONER,HAIER
Haier 1.5 Ton HSU-18-HFT(W) T3 Inverter Air Conditioner,HAIER
Haier 1.5 Ton HSU-20-HFTEX(W) T3 Inverter Air Conditioner,HAIER
HAIER 1 TON HSU-13HFP/G/S PEARL PRO INVERTER AIR CONDITIONER,HAIER
Haier 1.5 Ton HSU-18-HFP Pearl Inverter Air Conditioner,HAIER
Haier 2 Ton HSU-24HFCD Split Inverter Air Conditioner,HAIER
Dawlance 20 Litre DW-MD10 Fast Heating Microwave Oven,DAWLANCE
"TCL 32S51K 32"" QLED Smart TV (2026) – Full HD Android LED TV with Netflix & YouTube",TCL
"TCL 40S51K 40"" QLED Smart TV (2026) – Full HD Android LED TV with Netflix & YouTube",TCL
"TCL 43S51K 43"" QLED Smart TV (2026) – Full HD Android LED TV with Netflix & YouTube",TCL
Dawlance 385Ltr 91998 Signature Inverter Glass Door Champagne Twin Door Deep Freezer,DAWLANCE
Dawlance 91997 Signature Inverter Twin Door Deep Freezer– White,DAWLANCE
Dawlance 15 Cubic Feet CF-91997 Signature LVS Double Door Inverter Deep Freezer- Champagne,DAWLANCE
Gree 1 Ton Charmo Series GS-12CM11 Split Air Conditioner,GREE
TCL 50S51K 50″ QLED Smart TV (2026) – Full HD Android LED TV with Netflix & YouTube,TCL
Gree 1.5 Ton Charmo Series GS-18CM11 Split Air Conditioner,GREE
Gree 2 Ton Charmo Series GS-24CM11 Split Air Conditioner,GREE
TCL 32 Inch QLED Smart TV 32S59K (2026) Full HD Google TV,TCL
TCL 40 Inch QLED Smart TV 40S59K (2026) Full HD Google TV,TCL
Gree 1 Ton Pular Series  GS-12PIT10W Cool Only Air Conditioner,GREE
TCL 43 Inch QLED Smart TV 43S59K (2026) Full HD Google TV,TCL
GREE 1 TON PULAR SERIES GS-12PITH11W INVERTER HEAT & COOL SPLIT AIR CONDITIONER,GREE
TCL 50 Inch QLED Smart TV 50S59K (2026) Full HD Google TV,TCL
GREE 1 TON PULAR SERIES GS-12PITH11S INVERTER SPLIT AIR CONDITIONER,GREE
TCL 55 Inch 55P6K 4K UHD Smart Google LED TV,TCL
Gree 1 Ton Pular Series GS-12PITH14S Heat & Cool Inverter Split Air Conditioner (Turbo),GREE
TCL 65 Inch 65P6K 4K UHD Smart Google LED TV,TCL
Gree 1 Ton Pular T3 Series GS-12PITH15W DC Inverter Split Air Conditioner,GREE
TCL 50 Inch 50C6KS Premium 4K QD-Mini LED Smart TV,TCL
Gree 1 Ton Pular T3 Series GS-12PITH15G DC Inverter Split Air Conditioner,GREE
GREE 1 TON AIRY PLUS GS-12AITH21W-T3 DC INVERTER HEAT & COOL SPLIT AIR CONDITIONER,GREE
"TCL 55 Inch QD-Mini LED 4K Smart Google TV 55C6KS (Dolby Vision, Dolby Atmos, 2025 Premium)",TCL
GREE 1 TON AIRY PLUS GS-12AITH21B-T3 DC INVERTER AIR CONDITIONER,GREE
Gree 1 Ton Airy GS-12AITH23W-T3 Inverter Split Air Conditioner,GREE
GREE 1 TON ZENO GS-12ZITH1W T3 INVERTER SPLIT AIR CONDITIONER,GREE
GREE 1 TON ZENO GS-12ZITH2W T3 INVERTER SPLIT AIR CONDITIONER,GREE
Gree 1.5 Ton GS-18PITH10W DC Inverter Only Cool Air Conditioner,GREE
Gree 1.5 Ton Pular Series GS-18PITH11W Inverter Heat and Cool Split Air Conditioner,GREE
Gree 1.5 Ton Pular Series GS-18PITH11G Inverter Heat and Cool Split Air Conditioner,GREE
Gree 1.5 Ton Pular Series GS-18PITH15W-T3 WiFi Enabled Inverter Heat and Cool Split Air Conditioner,GREE
Gree 1.5 Ton Pular Series GS-18PITH15G-T3 WiFi Enabled Inverter Heat and Cool Split Air Conditioner,GREE
Gree 1.5 Ton Zeno Series GS-18ZITH1W-T3 WiFi Enabled Inverter Heat and Cool Split Air Conditioner,GREE
Gree 1.5 Ton Zeno Series GS-18ZITH2W-T3 WiFi Enabled Inverter Heat and Cool Split Air Conditioner,GREE
Gree 2 Ton Pular Series GS-24PIT10W Cool Only Air Conditioner,GREE
Gree 2 Ton Pular Series GS-24PITH11W Inverter Heat And Cool Split Air Conditioner,GREE
Gree 2 Ton Pular Series GS-24PITH11G Inverter Heat And Cool Split Air Conditioner,GREE
Gree 2 Ton Pular Series GS-24PITH15/16/17/18G-T3 Inverter Heat And Cool Split Air Conditioner,GREE
Gree 2 Ton Zeno Series GS-24ZITH1/2–T3 Inverter Heat And Cool Split Air Conditioner-White,GREE
Gree 2.25 Ton Airy Series GS-26AITH23W-T3 Inverter Split Air Conditioner,GREE
Gree 2 Ton T Fresh GF-24TFIH-T3 Inverter Floor Standing Air Conditioner,GREE
GREE 2 TON GF-24ISH DC INVERTER FLOOR STANDING AIR CONDITIONER,GREE
GREE 2 TON VALUE TIME SERIES GF-24VTIH-T3 INVERTER FLOOR STANDING AIR CONDITIONER,GREE
GREE 3 TON GF-36TFIH-T3 INVERTER FLOOR STANDING AIR CONDITIONER,GREE
GREE 4 TON T-FRESH SERIES GF-48TF FLOOR STANDING AIR CONDITIONER,GREE
GREE 4 TON T-FRESH SERIES GF-48TFIH INVERTER FLOOR STANDING AIR CONDITIONER,GREE
EcoStar 1 Ton Duke Series ES-12DU01WG Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 1 Ton Duke Series ES-12DU01GC Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 0.75 Ton Emperor Series ES-10EMC1WS Inverter Cool Only Split Air Conditioner,EcoStar
EcoStar 1 Ton Emperor Series ES-12EM01WS Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 1 Ton Emperor Series ES-12EMC1WS Cool Only Split Air Conditioner,EcoStar
EcoStar 1 Ton Ario Series ES-12AR01W-T3 Inverter Split Air Conditioner,EcoStar
EcoStar 1 Ton Novo Series ES-12NV01WT3 Inverter Split Air Conditioner,EcoStar
EcoStar 1 Ton Prince Series ES-12PR02WT3 Inverter Heat & Cool Split Air Conditioner,EcoStar
Ecostar 1.5 Ton Duke Series ES-18DU01 Inverter Heat & Cool Split Air Conditioner,EcoStar
Ecostar 1.5 Ton Duke Series ES-18DU01GC Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 1.5 Ton Emperor Series ES-18EM01WS Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 1.5 Ton Emperor Series ES-18EMC1WS Cool Only Split Air Conditioner,EcoStar
EcoStar 1.5 Ton Ario Series ES-18AR01WT3 Inverter Split Air Conditioner,EcoStar
EcoStar 1.5 Ton Novo Series ES-18NV01WT3 Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 1.5 Ton Ario MAX Series ES-18AR02WT3 Inverter Heat & Cool Split Air Conditioner,EcoStar
Ecostar 1.5 Ton Novo MAX Series ES-18NV02WT3 Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 1.5 Ton Prince Series ES-18PR02WT3 Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 2 Ton Duke Series ES-24DU01WG Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 2 Ton Duke Series ES-24DU01GC Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 2 Ton Emperor Series ES-24EM01WS Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 2 Ton Ario Series ES-24AR01WT3 Inverter Split Air Conditioner,EcoStar
Ecostar 2 Ton Novo Series ES-24NV01WT3 Inverter Heat & Cool Split Air Conditioner,EcoStar
Midea 1 Ton Eco Series T3 Tropical Pro inverter Heat and Cool Air Conditioner,Midea
Midea 1.5 Ton Eco Series T3 Tropical Pro Heat and Cool Air Conditioner,Midea
Dawlance 1 Ton Frost Pro X 15 DC Inverter Cool Only Split Air Conditioner,DAWLANCE
Haier 1.5-Ton HSU-19LF-SUPREME(W) DC Inverter Air Conditioner,HAIER
Haier 1-Ton HSU-13LF-SUPREME(W) DC Inverter Air Conditioner,HAIER
Dawlance 1 Ton Powercon X 15 T3 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1 Ton Sprinter X 15 T3 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Powercon X 30 T3 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Orient 1 Ton LUNAR-12G eComfort Grace Black DC Inverter Air Conditioner,ORIENT
Orient 1.5 Ton LUNAR-18G eComfort Grace Black DC Inverter Air Conditioner,ORIENT
Orient 2 Ton LUNAR-24G eComfort Grace Black DC Inverter Air Conditioner,ORIENT
Orient 1 Ton Mega-12G DC T3 Inverter Heat & Cool Air Conditioner,ORIENT
Orient 1.5 Ton Ulron Series eComfort Mega-18G DC T3 Inverter Heat & Cool Air Conditione,ORIENT
Orient 2 Ton AK-24G Floor Standing Inverter Air Conditioner,ORIENT
ORIENT 1.5 TON FB-18X AUX INVERTER IMPRINT WHITE AIR CONDITIONER,ORIENT
Midea 1 Ton MSAFB-12CRN1-R410 Split Non Inverter Air Conditioner,Midea
Midea 1.5 Ton MSAFC-18RN1-R410 Split Non Inverter Air Conditioner,Midea
Midea 2 Ton MSAFD-24RN1 Split Non Inverter Air Conditioner,Midea
Dawlance 91998 LVS Convertible Twin Door Deep Freezer,DAWLANCE
Dawlance CONVERTIBLE CF-91997 LVS 4-in-1 Twin Door Deep Freezer,DAWLANCE
Dawlance 91998 Signature LVS White Twin Door Deep Freezer,DAWLANCE
Dawlance 500 DD Twin Door Deep Freezer,DAWLANCE
Dawlance DF-400 SD Inverter Single Door Deep Freezer,DAWLANCE
Dawlance DF 400 Commercial White Single Door Deep Freezer,DAWLANCE
Dawlance 91997 Signature Inverter Champagne Twin Door Deep Freezer,DAWLANCE
Dawlance 91998 Signature Inverter Grey Twin Door Freezer,DAWLANCE
Dawlance 91998 Signature LVS Champagne Twin Door Deep Freezer,DAWLANCE
Dawlance CONVERTIBLE CF-91997 LVS Twin Door Deep Freezer,DAWLANCE
Dawlance 400-EDS Chest Deep Freezer,DAWLANCE
Dawlance 10 Cubic Ft Single Door Non Inverter DF-300W Deep Freezer,DAWLANCE
Dawlance DF-200P D Solar (ARC-P1 White) Deep Freezer,DAWLANCE
Dawlance DF-200 SD Inverter White Deep Freezer,DAWLANCE
Haier 1 Ton HSU-13LF Inverter Air Conditioner,HAIER
Dawlance DF-200P STUCCO PCM Chest Deep Freezer,DAWLANCE
Dawlance 400P Chest Deep Freezer,DAWLANCE
PEL 1 Ton Cool Breeze Inverter Cool Only Air Conditioner,PEL
DAWLANCE DF-300P STUCCO PCM NON INVERTER CHEST DEEP FREEZER,DAWLANCE
Dawlance DF-200 Energy Saver Glass Door Chest Deep Freezer (Champagne),DAWLANCE
Haier HDF-385IG Inverter Grey Twin Cabinet Chest Deep Freezer,HAIER
Haier HDF-405IG Inverter Grey Chest Deep Freezer,HAIER
KENWOOD 1.5 TON KES-1867S ECOMFORT PRO INVERTER AIR CONDITIONER,Kenwood
DAWLANCE 0.75 TON MEGA T+10 DC INVERTER AIR CONDITIONER,DAWLANCE
Haier 0.75 Ton HSU-10LF Flexis Inverter Air Conditioner,HAIER
Dawlance 1 Ton Infinity Pro 15 Non-Inverter Cool Only Split Air Conditioner,DAWLANCE
SUPERASIA ECM-3500 PLUS DC SMART COOL AIR COOLER,Super Asia
SUPERASIA ECM-4600 AUTO AC/DC INVERTER EASY COOL AIR COOLER,Super Asia
WestPoint WF-1304 Deluxe Evaporative Room Air Cooler,WestPoint Pakistan
Haier HDF-175IG 175L Inverter Chest Deep Freezer,HAIER
SUPERASIA ECM-6500 PLUS FAST COOL AIR COOLER,Super Asia
Haier HDF-385INV 385L Inverter Twin Cabinet Chest Deep Freezer,HAIER
Boss ECM-6500-IB Ice Box Air Cooler,Boss
GFC Room GF-6600 Deluxe AC/DC Inverter Room Air Cooler,GFC
GFC GF-6700 AC Touch Inverter Room Air Cooler,GFC
Haier 285L Inverter Chest Freezer HDF-285INV Double Door Deep Freezer,HAIER
Royal RAC-4700 Room Air Cooler,Royal Fans
Royal RAC-4700 AC Inverter Room Air Cooler,Royal Fans
Haier HRF-438 IFGA 16 Cu Ft Green Glass Door Digital Inverter Refrigerator,HAIER
Kenwood 1 Ton E-Smart Pura KES-1272S Inverter Heat & Cool Air Conditioner,Kenwood
Dawlance 1.5 Ton Frost Pro X 30 DC Inverter Cool Only Split Air Conditioner,DAWLANCE
Kenwood 1.5 Ton E-Luxury Plus KEL-1871S Inverter Heat & Cool Air Conditioner,Kenwood
Kenwood 1 Ton E-Luxury Pro KEL-1270S Inverter Air Conditioner,Kenwood
TCL 1 TON SAVE IN SERIES TAC-12SVN-AI-11 DC INVERTER ARI CONDITIONER,TCL
PEL 1 Ton PINV 12K Turbo Ultimate T3 (H&C) Inverter Air Conditioner,PEL
PEL 1.5 Ton On FIT White Inverter (H&C) Air Conditioner,PEL
PEL 1.5 Ton PINV-18K JUMBO DC Prime Wifi T3 Inerter (H&C) Air Conditioner,PEL
PEL 1.5 Ton PINV-18K Aero Extend Inverter (H&C) Air Conditioner,PEL
PEL 1 Ton PINV-12K Jumbo Prime+ T3 (Wifi) Inverter Split Air Conditioner,PEL
TCL 1.5 Ton SaveIN AI-21 AC R32 Inverter Air Conditioner,TCL
TCL 1.5 Ton SaveIN AI-41 Black Design R32 Inverter Air Conditioner,TCL
TCL 1.5 Ton SaveIN-EX-31W Inverter R32 Air Conditioner,TCL
TCL 2 TON Elite-HEA TAC-24HEA INVERTER AIR CONDITIONER,TCL
PEL 2 Ton PAC-24K Majestic 4D T3 Air Conditioner,PEL
Gree 1.5 Ton Pular Series GS-18PITH14S Inverter Heat & Cool Air Conditioner,GREE
PEL 1 Ton 12K PINV Fit Graphite (H&C) Inverter Air Conditioner,PEL
Midea 2 Ton MSCB1DU-24HRFN8-QRD1GW Breezeless E Series DC Inverter R32 T3 Air Conditioner,Midea
PEL 1.5 TON ATOM 18K ATOM-W INVERTER AIR CONDITIONER,PEL
Dawlance 1 Ton Cruise Plus DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Chillex DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton EnerCon X 30 T3 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1 Ton Chillex DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Haier 1 Ton HSU-13HFS/W/G-T3 Pro Inverter Heat & Cool Split Air Conditioner,HAIER
PEL 2 Ton 24K Supreme Inverter Floor Standing  Air Conditioner,PEL
PEL 2 Ton 24K Bold+ Inverter Floor Standing Cabinet Air Conditioner,PEL
Dawlance 1.5 Ton Cruise Plus DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Haier 1.5 Ton HSU-19HFC Triple Inverter Heat & Cool Split Air Conditioner,HAIER
Dawlance 1.5 Ton Infinity Pro 30 Non-Inverter Cool Only Split Air Conditioner,DAWLANCE
Haier 1.5 Ton HSU-19 HFAB T3 Pro Inverter Air Conditioner (Grey),HAIER
Haier 1.5 Ton HSU-18HFTCD T3 Inverter Air Conditioner,HAIER
EcoStar 1.5 Ton Duke Series ES-18DU01WG Inverter Heat & Cool Split Air Conditioner,EcoStar
TCL 1 Ton 12-E Cool DC Inverter Split Air Conditioner,TCL
Kenwood 1 Ton KEA-1250 Split Air Conditioner,Kenwood
Pel 1 Ton PAC-12k Majestic ES2-4D Split Air Conditioner,PEL
Dawlance 1 Ton Enercon X 15 T3 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1 Ton Aeromax-15 Inverter Heat and Cool Split Air Conditioner,DAWLANCE
Dawlance 1 Ton Aura X 15 DC Inverter Heat & Cool Air Conditioner,DAWLANCE
Dawlance 9191 Avante Non-Inverter Refrigerator,DAWLANCE
Dawlance 9191 Avante Inverter Refrigerator,DAWLANCE
Dawlance 1.25 Ton 20 Chrome Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1 Ton Elegance-X 15 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Kenwood 1 Ton E-Serene KES-1273S Heat & Cool Air Conditioner,Kenwood
PEL PDF-130 13 CFT Arctic Inverter Single Door Deep Freezer,PEL
Haier HDF-545DD (19 CF) Double Door Deep Freezer,HAIER
Haier HDF-230 (8 CF) Inverter Double Door Deep Freezer,HAIER
Haier HDF-285INV (10 CF) Inverter Single Door Chest Deep Freezer,HAIER
Kenwood 1 Ton Glory Pro KGP-12C01S DC Inverter Split Air Conditioner,Kenwood
Haier 8-kg HWM-80CS Semi Automatic Twin Tub Washing Machine,HAIER
MIDEA 1 TON MSEZ2B-12HRFN1 T3 XTREME PLUS INVERTER AIR CONDITIONER,Midea
PEL PDFT 70-155 15 CFT Arctic Pro Twin Door Deep Freezer,PEL
Dawlance MWO DW-MD7 20L Microwave Oven,DAWLANCE
Dawlance MWO DW-295 20L Heating Microwave Oven,DAWLANCE
Dawlance MWO DW-297-GSS Grilling Microwave Oven,DAWLANCE
Dawlance MWO DW-220 S 20L SOLO Heating Microwave Oven,DAWLANCE
Dawlance MWO DW-210 S PRO 20L Heating Microwave Oven,DAWLANCE
Dawlance MWO DW-MD4 WHITE 20L Heating Microwave Oven,DAWLANCE
Dawlance MWO DW-MD-4 BLACK 20L Heating Microwave Oven,DAWLANCE
Dawlance MWO MD-20 INV 20L Heating Microwave Oven,DAWLANCE
Dawlance MWO DW-374 23L Heating Microwave Ovenx (CHAMPAGNE),DAWLANCE
Dawlance DW-393 GSS 23L Grilling Microwave Oven,DAWLANCE
Dawlance DW-388 23L Heating Microwave Oven,DAWLANCE
Dawlance MWO DW-115-CHZP 25L Baking Microwave Oven,DAWLANCE
Dawlance 1.5 Ton DAC-Hyper T3 Inverter Silver Split Air Conditioner,DAWLANCE
Orient 2 Ton 24X Divine (Pristine) Inverter Split Air Conditioner,ORIENT
Kenwood 1.5 Ton KES-1866S E-Smart OYNX Inverter Air Conditioner,Kenwood
Gree 1.5 TON Airy Pro GS-18AITH24S Inverter Heat & Cool Split Air Conditioner,GREE
Midea 1.5 Ton MSAGC-18HRFN Xtreme Full DC Inverter Heat & Cool Air Conditioner,Midea
Anex AG-146 1000W Deluxe Hand Blender,Anex
Panasonic MX-SS1 Hand Blender,Panasonic
WestPoint WF-7501GL Deluxe 500W Glass Jar Juicer Blender,WestPoint Pakistan
Philips HR-2141 Daily Collection Blender,Philips
Anex AG-176-GL 600W 3 in 1 Juicer Blender Grinder,Anex
TCL 55 Inches 55P79K 4K UHD Google QLED TV,TCL
Haier 50 inch H50S81EUX QLED Google TV,HAIER
Dawlance 1 Ton Mega Flex Inverter Split Air Conditioner,DAWLANCE
Dawlance 1 Ton Econo Plus X 15 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1 Ton Elegance Pro 15 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Mega T3 Pro 30 Inverter Heat & Cool Split Air Conditioners,DAWLANCE
Dawlance 1.5 Ton Sprinter X 30 T3 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Aeromax 30 Inverter Heat and Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Prima PurSense 30 Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Econo Plus X 30 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Infinity Pro 30 Inverter Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Mega Flex 30 Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Magna T3 30 Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Avante 30-T3 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Chrome Pro 30 Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Suave+ 30 Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 2 Ton Chrome+ 45 Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 2 Ton Dual Pro 45 T3 Inverter Split Air Conditioner,DAWLANCE
EcoStar 1 Ton Duke Series ES-12DU02WG Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 1 Ton Duke Series ES-12DU01BC Inverter Heat & Cool Split Air Conditioner,EcoStar
Dawlance DF-500DD 15 CFT Inverter Double Door Deep Freezer,DAWLANCE
Haier HDF-405I Inverter Single Door Deep Freezer,HAIER
Haier HDF-545INV Inverter Double Door Deep Freezer,HAIER
PEL PDF70-100 APF 10 CFT Arctic Pro Inverter Single Door Deep Freezer,PEL
EcoStar 1 Ton Emperor Series ES-12EM02WS Heat & Cool Split Air Conditioner,EcoStar
Ecostar 1 Ton Novo MAX Series ES-12NV02WT3 Inverter Heat & Cool Split Air Conditioner,EcoStar
EcoStar 1.5 Ton Duke Series ES-18DU02WG SA+ Inverter Heat & Cool Split Air Conditioner,EcoStar
Haier 1.5 Ton HSU-19LF-PRIME(W) DC Inverter Air Conditioner,HAIER
Haier 1.5 Ton HSU-18HJ(G) Inverter Heat & Cool Split Air Conditioner,
HAIER 1.5 TON HSU-20HJUV(G)-T3 INVERTER HEAT & COOL AIR CONDITIONER,HAIER
Haier 1.5 Ton HSU-19HFMCE Inverter Heat & Cool Split Air Conditioner,HAIER
HAIER 1.5 TON HSU-19HFS/W/G-T3 INVERTER HEAT & COOL AIR CONDITIONER,HAIER
Haier 1.5 Ton HSU-18HFMCE Inverter Heat & Cool Split Air Conditioner,HAIER
HAIER 2 TON HSU-24HFAB(W) T3 INVERTER HEAT & COOL SPLIT AIR CONDITIONER,HAIER
Haier 2 Ton HSU-24CF Cool Only Split Air Conditioner,HAIER
Gree 1 Ton Airy Pro GS-12AITH24S-T3 Inverter Heat & Cool Split Air Conditioner,GREE
Gree 1 Ton Pular T3 Series GS-12PITC12W-T3 Cool Only Split Air Conditioner,GREE
Gree 1 Ton Airy Pro GS-12AITH24W-T3 Inverter Heat & Cool Split Air Conditioner,GREE
Oreint 1.25 Ton Snow 14C T3 Chrome Inverter Cool Only Split Air Conditioner,ORIENT
Oreint 1.25 Ton Ice 14C T3 Gold White Inverter Cool Only Split Air Conditioner,ORIENT
Gree 1 Ton Fairy Series GS-12FITH1/S/W Inverter Heat & Cool Split Air Conditioner,GREE
Gree 1.5 Ton Airy Plus Series GS-18AITH21B-T3 Inverter Heat and Cool Split Air Conditioner,GREE
Gree 1.5 Ton Airy Plus Series GS-18AITH21W-T3 Inverter Heat & Cool Split Air Conditioner,GREE
Gree 1.5 Ton Airy Plus Series GS-18AITH24W-T3 Inverter Heat & Cool Split Air Conditioner,GREE
Gree 1.5 Ton Pular T3 Series GS-18PITC12W-T3 Cool Only Split Air Conditioner,GREE
Gree 1.5 Ton Pular T3 Series GS-18PITH17W-T3 Inverter Heat & Cool Split Air Conditioner,GREE
Gree 2 Ton Pular Series GS-24PITH11S/14S Inverter Heat & Cool Air Conditioner,GREE
Gree 2 Ton Airy Pro Series GS-24AITH24S-T3 Inverter Heat & Cool Split Air Conditioner,GREE
Gree 2 Ton Airy Plus Series GS-24AITH21B-T3 Inverter Heat & Cool Split Air conditioner,GREE
Gree 2 Ton Airy Pro Series GS-24AITH24W-T3 Inverter Heat & Cool Split Air Conditioner,GREE
Gree 2 Ton Fairy Series GS-24FITH1C Inverter Heat & Cool Split Air Conditioner,GREE
Gree 2 Ton Pular Series GS-24PITH10W Inverter Cool Only Split Air Conditioner,GREE
Homage 1 Ton Grande HES-1213-T3 Non Inverter Split Air Conditioner,Homage
Homage 1 Ton Classic HCS-1221S Inverter Split Air Conditioner,Homage
Homage 1 Ton Smart Crystal HSC-1212S-T3 Inverter Split Air Conditioner,Homage
Homage 1 Ton Element Ultra HES-1222S-T3 Inverter Split Air Conditioner,Homage
Homage 1 Ton Smart Cool HSC-1220S Inverter Heat & Cool Split Air Conditioner,Homage
Homage 1 Ton Prestige HPS-12C01S-T3 Inverter Split Air Conditioner,Homage
Homage 1.5 Ton Classic HCS-1821S Inverter Split Air Conditioner,Homage
Homage 1.5 Ton  Smart Cool HSC-1820S-T3 Inverter Heat & Cool Split Air Conditioner,Homage
Homage 1.5 Ton Pristige HPS-18C01S-T3 Inverter Split Air Conditioner,Homage
Homage 2 Ton Classic HCS-2421S-T3 Inverter Split Air Conditioner,Homage
KENWOOD 1 TON GLORY PLUS KGP-12C03S-T3 INVERTER SPLIT AIR CONDITIONER,Kenwood
Kenwood 1 Ton E-Smart Onyx KES-1266S Inverter Split Air Conditioner,Kenwood
Kenwood 1.5 Ton Luxury Ultra KLU-18B03S-T3 Inverter Split Air conditioner,Kenwood
Kenwood 1.5 Ton E-Nova Pro KEN-1876S Non Inverter Only Cool Split Air Conditioner,Kenwood
Kenwood 1.5 Ton Glory Pro KGP-18C01S-T3 Inverter Split Air Conditioner,Kenwood
Kenwood 1.5 Ton E-Smart Pura KES-1872S Inverter Split Air Conditioner,Kenwood
KENWOOD 1.5 TON LUXURY PRO KLP-18B02S-T3 INVERTER AIR CONDITIONER,Kenwood
KENWOOD 1.5 TON GLORY PLUS KGP-18C03S-T3 INVERTER SPLIT AIR CONDITIONER,Kenwood
Kenwood 2 Ton E-Luxury Pro KEL-2470S-T3 Inverter Split Air Conditioner,Kenwood
Dawlance DS 6080 Cosmic Blue Spinner Dryer,DAWLANCE
HAIER 11KG HWM110-688S8 AUTOMATIC TOP LOAD WASHING MACHINE,HAIER
Haier HWM150-826S6 15KG Automatic Top Load Washing Machine,HAIER
Haier HWM90-826E 9KG Automatic Top Load Washing Machine,HAIER
Haier HWM130-688S8 13KG Automatic Top Load Washing Machine,HAIER
Super Asia 12Kg SA-812 Inverter Topload Automatic Washing Machine,Super Asia
Super Asia SA-280 Grand Wash 10KG Semi Automatic Twin Tub Washing Machine,Super Asia
Super Asia SA-241 Smart Wash 7KG Twin Tub Washing Machine,Super Asia
Haier HAF50MB Black 5L Air Fryer,HAIER
Haier 5Litre Black HAF-50DB Digital Air Fryer,HAIER
WestPoint WF-5255 Deluxe 6L 1500W Retro Style Air Fryer,WestPoint Pakistan
Dawlance 5.5 Litre AirFryer DWAF 6322 D XL,DAWLANCE
Dawlance Air Fryer DWAF-6321 L (5.5 Liters),DAWLANCE
Anex AG-2025 8 Liter Digital LED Deluxe Air Fryer,Anex
Anex AG-2015 8 Liter Deluxe Air Fryer,Anex
Anex AG-2020 1700W Deluxe Air Fryer,Anex
Anex AG-2125 8 Litre Deluxe Air Fryer,Anex
PEL-215 Pearl Hot & Cold Water Dispenser (Without Refrigerator Compartment),PEL
PEL PMO-20W 20L Classic Solo Microwave Oven,PEL
Haier Candy CSU-13HF 1.0 Ton DC Inverter Heat & Cool Air Conditioner,HAIER
Dawlance DW-9193LF 16 Cu Ft Chrome Hairline Black Double Door Refrigerator,DAWLANCE
Dawlance DW-91999 20 Cu Ft Coral Red Double Door Refrigerator,DAWLANCE
PEL PEL-1400-SD 135 Liters Mini Refrigerator,PEL
PEL 315 Smart Hot & Cold Water Dispenser with Refrigerator,PEL
Gree 1 Ton Pular T3 Series GS-12PITH17W-T3 Inverter Heat & Cool Air Conditioner,GREE
Gree 1.5 Ton Pular T3 Series GS-18PITH17G-T3 Inverter Heat & Cool Air Conditioner,GREE
Haier 2 Ton HSU-24HFAB(G)-T3 Inverter Split Air Conditioner,HAIER
Haier 4 Ton HPU-48CE03-(R410a) Non Inverter Cool Only Floor Standing Air Conditioner,HAIER
Haier 50 Inch 4K QLED Smart Google TV 50S80EUX,HAIER
Kenwood 1.5 Ton KCT-1801H Non-Inverter Ceiling Cassette Air Conditioner,Kenwood
Kenwood 2 Ton KCT-2401H Non Inverter Ceiling Cassette Air Conditioner,Kenwood
Haier 32 Inch Smart QLED Google TV 32S80EFX,HAIER
Haier 32 Inch Google LED TV H32K85FX,HAIER
Haier 43 Inch Smart Google LED TV H43K85FX,HAIER
Haier 40 Inch Smart Google LED TV 40K85FFX,HAIER
Haier 55 Inch Smart 4K QLED Google TV 55S80EUX,HAIER
Dawlance 43 Inch Smart 2K Google LED TV 43E22,DAWLANCE
Dawlance 50 Inch Pro 4K Ultra HD Smart Android TV |G3A,DAWLANCE
Haier 2.0 Ton Ceiling Cassette Inverter Air Conditioner HBU-24HE/DC,HAIER
Dawlance 9173LF-Acce-Pro 12 Cu Ft Crimson Red Inverter Double Door Refrigerator,DAWLANCE
Dawlance 9173-WB-Avante+ 12 Cu Ft Cloud White Inverter Double Door Refrigerator,DAWLANCE
Dawlance 9193LF-Digital-Pro 16 Cu Ft Magnetic Green Inverter Double Door Refrigerator,DAWLANCE
Haier HRF-578TBG 505 Liters Black Glass Inverter Refrigerator,HAIER
Midea 1.5 Ton 18HRDN1-QC2-AG2-T3 Fighting Series Inverter Air Conditioner,Midea
Dawlance 50 Inch Smart 4K Ultra HD Google LED TV |50G22,DAWLANCE
Dawlance 43 Inch 43G3A 4K Ultra HD Smart LED TV,DAWLANCE
Haier 43 Inch 43S80EUX Smart Google 4K QLED TV,HAIER
Dawlance 1.5 Ton Aura X 30 DC Inverter Heat & Cool Air Conditioner,DAWLANCE
Dawlance 40 Inch 40KORE Smart Full HD Google LED TV,DAWLANCE
Dawlance 1.5 Ton Elegance-X 30 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 1.5 Ton Elegance Pro 30 DC Inverter Heat & Cool Split Air Conditioner,DAWLANCE
Dawlance 32 Inch 32KORE Smart HD Google LED TV Android TV,DAWLANCE
Gree 2 Ton Pular T3 Series GS-24PITH15W DC Inverter Heat & Cool Split Air Conditioner,GREE
Haier HRF-276EPB 10 Cu Ft Black Glass E-Star Non-Inverter Refrigerator,HAIER
Midea 1.5 Ton Titan MSEZ1C-18HRFN1-T3 DC Inverter Heat & Cool Split Air Conditioner,Midea
Midea 1.5 Ton Xtreme Plus MSEZ2C-18HRFN1-T3 DC Inverter Heat & Cool Split Air Conditioner,Midea
Midea 1.5 Ton Breezeless (E) MSCB1CU-18HRFN8 DC Inverter Heat & Cool Split Air Conditioner,Midea
Kenwood 1.5 Ton KES-1866S-T3 eSmart Onyx Full DC Inverter Heat & Cool Split Air Conditioner,Kenwood
Kenwood 1 Ton KEE-1245S E-Eco Plus DC Inverter Heat & Cool Split Air Conditioner,Kenwood
TCL 1.5 Ton 18T5 Voxin-13 Full DC Inverter Heat & Cool Split Air Conditioner,TCL
TCL 1.5 Ton 18T3 PRO 2-T3 DC Inverter Heat & Cool Split Air Conditioner,TCL
EcoStar 1.5 Ton Crown Series ES-18CRO1W DC Inverter Heat & Cool Split Air Conditioner,EcoStar
Haier 40 Inch 40K85EFX Full HD Smart Google LED TV,HAIER
Haier HRF-368 IFRA 14 Cu Ft Red Glass Door Digital Inverter Refrigerator,HAIER
Dawlance 9169WB 11 Cu Ft Avante+ Sapphire Purple Double Door Refrigerator,DAWLANCE
PEL PRLP-2000 168 Liters Non-Inverter Top Mount Refrigerator,PEL
PEL 2350-Prinvo 240 Liters Maroon Blaze Inverter Refrigerator,PEL
Super Asia 54G with 3 Taps Water Dispenser,Super Asia
PEL 6370-Digitron-Ultra 310 Liters Red Blaze Inverter Refrigerator,PEL
PEL 1.5 Ton 18K Fit DC Inverter Split Air Conditioner White,PEL
Haier 23L HMW-23200 Digital Grill Microwave Oven,HAIER
Haier 2.0 Ton HSCF-24HNR1 Cassette Inverter Heat & Cool Air Conditioner,HAIER
PEL 525 Curved Glass Door 3 Taps with Refrigerator Water Dispenser,PEL
Dawlance 9106-SD 6 Cu Ft Metallic Grey Non-Inverter Mini Refrigerator,DAWLANCE
Homage HMSO-2019B-20 Liters Solo Microwave Oven – Black,Homage
Midea 1.0 Ton MSEZ1B-12HRFN1-Titan Full DC Inverter Heat & Cool Air Conditioner,Midea
Homage Handheld Garment Steamer HGS-1121WE – 1200W,Homage
Homage Handheld Garment Steamer |HGS-1151BE –1500W with LCD Display,Homage
Kenwood 12B02S Luxury Pro WiFi Inverter Air Conditioner (T3 Compressor),Kenwood
Dawlance WD-1060 WGR Champagne Top Load Water Dispenser with Refrigerator,DAWLANCE
Dawlance Hand Blender DWHB-475W – 500W Copper Motor,DAWLANCE
"Homage HMSO-2020B Microwave Oven (20 Liters, Solo, Black)",Homage
"Kenwood STP01 Steam Iron (1100W, Non-Stick Soleplate)",Kenwood
Dawlance DW-7200 W FL 6-KG Single Tub Washer Washing Machine – White,DAWLANCE
EcoStar 1.5 Ton 18DUO2BC DC Inverter Heat & Cool Split Air Conditioner,EcoStar
"Dawlance MWO DW 525 AF Air Fryer Microwave Oven (25 Liters, 4-in-1)",DAWLANCE
Kenwood 2.0 Ton KES-2452FHI Superia Smart Floor Standing Inverter Heat & Cool Air Conditioner,Kenwood
Midea 1.5 Ton Titan MSE1C-18HRFN1-QC2 Inverter Heat & Cool Split Air Conditioner,Midea
Dawlance 28L DW-128 G Grill Microwave Oven,DAWLANCE
Midea 1 Ton Breezeless MSCB1BU-12HRFN8 Inverter Heat & Cool Split Air Conditioner,Midea
Kenwood KRF-26657 18 Cu Ft Maroon Inverter Refrigerator,Kenwood
Dawlance 9173WB 12 Cu Ft Coral Red Refrigerator,DAWLANCE
Kenwood 10KG KWS-1050S Spin Dryer Washing Machine,Kenwood
Dawlance 9178LF 14 Cu Ft Red Inverter Refrigerator,DAWLANCE
Dawlance 9149WB 9 Cu Ft Grey Refrigerator,DAWLANCE
Haier 1.25 Ton Plus Series HSU-14HFTEX-G-T3 Plus Inverter Heat & Cool Split Air Conditioner,HAIER
Kenwood KRF-23357 11 Cu Ft Maroon Inverter Double Door Refrigerator,Kenwood
Dawlance 9178 LF 14 Cu Ft E-Chrome Hairline Golden Refrigerator,DAWLANCE
Gaba National GNW-95023 Twin Tub Baby Washing Machine – Blue / Pink,Gaba National
Homage HDG-451S 45L Grill Microwave Oven,Homage
Dawlance DW-136-G 20L Grill Microwave Oven,DAWLANCE
Homage HDG-282B 28L Grill Microwave Oven,Homage
Haier HWM 150-316S6 15KG Automatic Top Load Washing Machine – Starry Silver,HAIER
TCL 1 Ton 12 SVN-AI-CO-31G/S Inverter Cool Only Split Air Conditioner,TCL
TCL 1.5 Ton 18 SVN-AI-CO-31G/S Inverter Cool Only Split Air Conditioner,TCL
TCL 2 Ton 24 SVN-AI-CO-31G/S Inverter Cool Only Split Air Conditioner,TCL
Haier HRF-458 IPGA 16 Cu Ft Green Smart Inverter Refrigerator,HAIER
Dawlance 9140-WB-AVANTE 8 Cu Ft Non-Inverter Refrigerator,DAWLANCE
Dawlance 9178-LF-M 14 Cu Ft Chrome Non-Inverter Refrigerator,DAWLANCE
Homage 47442-GD-MIG 13 Cu Ft Inverter Refrigerator,Homage
Haier 16 Cu Ft HDF-465 Inverter Deep Freezer,HAIER
Haier 10KG HWM 100-826S6 Top Load Fully Automatic Washing Machine,HAIER
Homage Table Top HWD-49320 Water Dispenser (Black),Homage
Homage 28L HDG-282 Grill Microwave Oven,Homage
Kenwood KRF-26757-GD 17 Cu Ft Red Smart Inverter Refrigerator,Kenwood
Kenwood KRF-26657-GD-MIRROR 18 Cu Ft Inverter Refrigerator,Kenwood
Kenwood KRF-26657-VCM 18 Cu Ft Pearl Blue Inverter Refrigerator,Kenwood
Homage 20L HDG-201S Grill Microwave,Homage
Dawlance 23L 393G Heating Microwave Oven,DAWLANCE
Dawlance 20L 210S Solo White Microwave Oven,DAWLANCE
Dawlance 7.6L DWAF-3374 B Air Fryer,DAWLANCE
Midea 50L D50-20EFG Smart Wifi Geyser,Midea
Homage 9KG HW-49102 Washing Machine Pearl Black Ecosense,Homage
Haier HW80-BP12929S3 8KG Front Load Automatic Washing Machine – Star Grey,HAIER
Homage HPJ-504A0 4-in-1 Power Juicer Blender Grinder & Chopper – 500W,Homage
Haier 30L HMW-30AFR Air Fryer Microwave Oven,HAIER
Dawlance 9193LF 16 Cu Ft Avante+ Cloud White Refrigerator,DAWLANCE
HAIER HRF-538 IFGA 20 Cu Ft Green Digital Inverter Refrigerator,HAIER
HAIER HRF-538 IFRA 20 Cu Ft Red Digital Inverter Refrigerator,HAIER
Dawlance 9160LF 10 Cu Ft Silver Refrigerator,DAWLANCE
Dawlance 9169WB 11 Cu Ft Silver Refrigerator,DAWLANCE
Dawlance 9173WB 12 Cu Ft Ruby Red Refrigerator,DAWLANCE
Haier 20L HMW-20DGS Grill Microwave,HAIER
Haier 30L HGL-30100 Convection Oven,HAIER
Haier 62L HMN-62MX80 Solo Microwave,HAIER
Dawlance 30L DW-131 HP Sync Smart Microwave,DAWLANCE
Dawlance 30L DW-530 AF Air Fryer Microwave Owen,DAWLANCE
Homage HVF-2601V Vertical Freezer,Homage
Homage HCJ-090A0 85W Stainless Steel Citrus Juicer,Homage
Dawlance DBMO 25 BG Series Built-In Microwave Oven with Grill – 25 Liters,DAWLANCE
Kenwood 2 Ton Luxury Pro 24B02S-T3 Inverter Split Air Conditioner,Kenwood
Kenwood 24C02S 2 Ton Glory Ultra Inverter Split Air Conditioner,Kenwood
TCL TAC-T5 18T5-SMT-S 1.5 Ton Smart Inverter Split Air Conditioner,TCL
TCL TAC-24T5-SMT-S 2 Ton Smart Inverter Split Air Conditioner,TCL
Dawlance DW-299 DS 23L Heating Microwave Oven,DAWLANCE
Dawlance DW-162 HZP 62L Heating Microwave Oven,DAWLANCE
Dawlance DW-133 RG 30L Grilling Microwave Oven,DAWLANCE
Kenwood 1 Ton Luxury Ultra KLU-12B03S DC Inverter Heat & Cool Split Air Conditioner,Kenwood
Midea 2 Ton Xtreme Eco 24HRDN1-T3 DC Inverter Heat & Cool Split Air Conditioner,Midea
Midea 2 Ton Xtreme Plus MSEZ2C-24HRFN1 DC Inverter Heat & Cool Split Air Conditioner,Midea
Haier HRF-246 IPGA 9 Cu Ft Green Smart Inverter Refrigerator,HAIER
Dawlance 9173WB 12 Cu Ft Platinum Silver Inverter Refrigerator,DAWLANCE
Dawlance 9178LF 14 Cu Ft Sapphire Purple Inverter Refrigerator,DAWLANCE
Dawlance DBD-1035 Glass Door Water Dispenser,DAWLANCE
Gree 1.5 Ton Pular GS-18PIT10W DC Inverter Split Air Conditioner,GREE
Gree 2 Ton Pular 24PITH14S-T3 DC Inverter Heat & Cool Split Air Conditioner,GREE
Homage 1200W HDI-1201 Lightweight Dry Iron,Homage
Dawlance 1750W DWSI-2322-CX Ceramic Steam Iron,DAWLANCE
Homage 1200W HDI-1202D0 Premium Heavy Duty Iron,Homage
Dawlance DBD-1034 EZ Glass Door Water Dispenser,DAWLANCE
Midea Top Load YL-2037S-B Premium Water Dispenser White/Black,Midea
Dawlance DWHJ-8002 600W Premium Hard Fruit Juicer,DAWLANCE
Midea 30L D30-20EFG Premium Electric Geyser,Midea
Homage HCH-401A0 400W Premium Food Chopper,Homage
"Midea 1 Ton 12HRDN1 AG2 Fighting Inverter Split Air Conditioner - Heat & Cool, T3 Compressor",Midea
"Midea 1.5 Ton 18HRDN1 AG2 Fighting Inverter Split Air Conditioner - Heat & Cool, T3 Compressor",Midea
Haier HRF-216EPR 8 Cu Ft Red Glass E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-246EPB 9 Cu Ft Black Glass E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-246EPR 9 Cu Ft Red Glass E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-276EBS 10 Cu Ft Silver E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-276 IPGA 10 Cu Ft Green Smart Inverter Refrigerator,HAIER
Haier HRF-316 IPRA 11 Cu Ft Red Smart Inverter Refrigerator,HAIER
Haier HRF-346EPR 12 Cu Ft Red Glass E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-438 IFPA 16 Cu Ft Purple Glass Door Digital Inverter Refrigerator,HAIER
Haier HRF-316 IPGA 11 Cu Ft Green Smart Inverter Refrigerator,HAIER
Dawlance 9106-SD 6 Cu Ft White Mini Refrigerator,DAWLANCE
Dawlance 9149WB 9 Cu Ft Golden Refrigerator,DAWLANCE
Dawlance 9169WB 11 Cu Ft Chrome Hairline Black Double Door Non Inverter Refrigerator,DAWLANCE
Gree GW-JL500FC Three Tap Water Dispenser with Refrigerator Cabinet,GREE
Dawlance 9193LF 16 Cu Ft Avante+ IoT Silky Red Inverter Double Door Refrigerator,DAWLANCE
Haier HMW-30AFS 30L Convection Microwave Oven with Air Fryer,HAIER
Haier HWM 80-60 Semi-Automatic Single Tub Washing Machine – 8 KG,HAIER
Dawlance 9178LF-ACCE 14 Cu Ft Coral Red Non-Inverter Double Door Refrigerator,DAWLANCE
Dawlance 9178LF 14 Cu Ft Avante Diamond Red Non Inverter Double Door Refrigerator,DAWLANCE
Dawlance 9178LF 14 Cu Ft Avante+ Cloud White Inverter Double Door Refrigerator,DAWLANCE
Haier HRF-418 IPRA 15 Cu Ft Red Smart Inverter Refrigerator,HAIER
Dawlance 45 FS Glamour Inverter Floor Standing Heat & Cool Air Conditioner,DAWLANCE
Dawlance DSD 4890 Silver Single Door Non-Inverter Refrigerator,DAWLANCE
Dawlance 9173 12 Cu Ft Graze+ Gem Black Glass Door Inverter Refrigerator,DAWLANCE
Dawlance 9149WB 9 Cu Ft Avante Pearl Red Double Door Non Inverter Refrigerator,DAWLANCE
Homage HKT-817SSB0 1.8 Litre Stainless Steel Electric Kettle,Homage
Homage HSM-702C0 2 Slice Non-Stick Sandwich Maker,Homage
Homage HHM-302A0 300W 5 Speed Hand Mixer,Homage
Homage HTB-603A0 600W 1.5 Litre Table Blender,Homage
Gaba National GN-5024-21 500W Electric Food Chopper,Gaba National
Gaba National GNW-92020 2.5 Kg Single Tub Baby Washing Machine,Gaba National
Gaba National GN-261/21 1500W Single Burner Electric Hot Plate,Gaba National
Gaba National GND-0319 Table Top Hot and Cold Water Dispenser,Gaba National
Philips HD9270/90 6.2L XL Essential Rapid Air Fryer,Philips
Dawlance DWT 1006 Mystic Grey Top Load Washing Machine,DAWLANCE
Dawlance DW 255 ES Top Load Automatic Washing Machine,DAWLANCE
Dawlance DW6570 GB 8 Kg Twin Tub Semi Automatic Washing Machine,DAWLANCE
WestPoint WF-1153 300ml Deluxe 1500 W Handy Portable Garment Steamer,WestPoint Pakistan
WestPoint WF-1157 1350ml 1580W Deluxe Garment Steamer,WestPoint Pakistan
WestPoint WF-1159 2.2L Professional 2600W 2 in 1 Commercial Garment Steamer,WestPoint Pakistan
WestPoint WF-5252 350 W Deluxe Egg Boiler,WestPoint Pakistan
WestPoint WF-714 Countertop Mineral Water Purifier,WestPoint Pakistan
WestPoint WF-1102 2.5 l 50W Deluxe Air Purifier,WestPoint Pakistan
WestPoint WF-1201 300 ml Quiet 25 W Ultrasonic Room Humidifier,WestPoint Pakistan
WestPoint WF-1205 Deluxe 25 W Ultrasonic Room Humidifier,WestPoint Pakistan
WestPoint WF-1206 5.3L Deluxe 28 W Ultrasonic Room Humidifier,WestPoint Pakistan
WestPoint WF-1845 Professional 1000W Juicer Blender 4 in 1,WestPoint Pakistan
WestPoint WF-2409 1000ml Deluxe 750 W Glass Juicer Blender 3 in 1,WestPoint Pakistan
WestPoint WF-8813 750W Deluxe Juicer,WestPoint Pakistan
WestPoint WF-8823 750W Deluxe Juicer,WestPoint Pakistan
WestPoint WF-8814 Deluxe 750W Juicer Blender 4 in 1,WestPoint Pakistan
WestPoint WF-8824 Deluxe 750W Juicer Blender 4 in 1,WestPoint Pakistan
WestPoint WF-5161 500 W Deluxe Juicer,WestPoint Pakistan
WestPoint WF-5164 1.2L Professional 1000W Deluxe Juicer,WestPoint Pakistan
WestPoint WF-5165 Professional 200W Slow Juicer,WestPoint Pakistan
WestPoint WF-4259 9L 2200W Deluxe Air Fryer,WestPoint Pakistan
WestPoint WF-5253 6 liter 1900 W Deluxe Air Fryer,WestPoint Pakistan
WestPoint WF-5256 6 l 1900 W Deluxe Air Fryer,WestPoint Pakistan
WestPoint WF-7259 9.0L 2200W Deluxe Air Fryer Double Heater,WestPoint Pakistan
WestPoint WF-410 1 Liter Deluxe 2200W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-411 1 Liter Deluxe 2200W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-3117 1850 W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-3118 1850 W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-3119 6.5 L Deluxe 1700 W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-8266 1.7 Liter Deluxe 2200W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-8267 Deluxe 2200 W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-8269 1.7 Liter Deluxe 2200W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-8270 Professional 2200 W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-6171 2 Liter Deluxe 2200 W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-6172 1.8 Liter Deluxe 2200 W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-6173 1.8 Liter Deluxe 2200 W Cordless Electric Kettle,WestPoint Pakistan
WestPoint WF-6175 1.8 Liter Deluxe 1000 W Multi-Function Electric Kettle,WestPoint Pakistan
WestPoint WF-6275 1.8 Liter Deluxe 1000 W Multi-Function Electric Kettle,WestPoint Pakistan
WestPoint WF-7006 180 KG Digital Bathroom Scale,WestPoint Pakistan
WestPoint WF-7007 180 kg Deluxe Digital Bathroom Scale,WestPoint Pakistan
WestPoint WF-7008 180 kg Deluxe Digital Bathroom Scale,WestPoint Pakistan
WestPoint WF-7009 180 kg Deluxe Digital Bathroom Scale,WestPoint Pakistan
WestPoint WF-8605 136 kg Deluxe Bathroom Weight Scale,WestPoint Pakistan
WestPoint WF-8607 180 kg Deluxe Bathroom Weight Scale,WestPoint Pakistan
WestPoint WF-7010 180 kg Deluxe Digital Bathroom Scale,WestPoint Pakistan
WestPoint WF-78B Deluxe 1000 W Heavyweight Dry Iron,WestPoint Pakistan
WestPoint WF-80B Deluxe 1000 W Heavyweight Dry Iron,WestPoint Pakistan
WestPoint WF-81B Deluxe 1000 W Heavyweight Dry Iron,WestPoint Pakistan
WestPoint WF-84B Deluxe 1000 W Heavyweight Dry Iron,WestPoint Pakistan
WestPoint WF-85B Deluxe 1000W Heavyweight Dry Iron,WestPoint Pakistan
WestPoint WF-86B Deluxe 1200 W Heavyweight Dry Iron,WestPoint Pakistan
WestPoint WF-2386 Deluxe 1200 W Heavyweight Dry Iron,WestPoint Pakistan
WestPoint WF-2432 Deluxe 1200 W Heavyweight Dry Iron,WestPoint Pakistan
WestPoint WF-2430 1200 W Deluxe Dry Iron,WestPoint Pakistan
WestPoint WF-2431 1200 W Deluxe Dry Iron,WestPoint Pakistan
WestPoint WF-2064 180ml 2000 W Deluxe Garment Steam Iron,WestPoint Pakistan
WestPoint WF-2065 180ml 2000 W Deluxe Garment Steam Iron,WestPoint Pakistan
WestPoint WF-718 Deluxe 350 W Blender & Dry Mill 2 in 1,WestPoint Pakistan
WestPoint WF-7181 Deluxe 350 W Blender & Dry Mill 2 in 1,WestPoint Pakistan
WestPoint WF-738 1.5L Deluxe 1 W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-7381 1.5L Deluxe 1 W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-929 Deluxe 350 W Blender & Dry Mill 2 in 1,WestPoint Pakistan
WestPoint WF-9291 Deluxe 1 W Blender & Dry Mill 2 in 1,WestPoint Pakistan
WestPoint WF-949 350 W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-9491 350 W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-301 Deluxe 450 W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-302 Deluxe 450 W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-303 Deluxe 450 W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-304 Deluxe 450 W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-307 Deluxe 450 W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-308 Deluxe 450 W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-3321 Deluxe 350W Blender & Dry Mill 2 in 1,WestPoint Pakistan
WestPoint WF-3331 Deluxe 350W Blender & Grinder 3 in 1,WestPoint Pakistan
WestPoint WF-372 1.5L Professional 800 W Blender & Dry Mill 2 in 1,WestPoint Pakistan
WestPoint WF-373 1.5L Professional 800 W Electric Coffee Grinder,WestPoint Pakistan
WestPoint WF-448 3000mL Commercial 1500W Deluxe Blender,WestPoint Pakistan
WestPoint WF-449 Deluxe 1500W Nutri Smoothy Blender,WestPoint Pakistan
WestPoint WF-364 1.5 Liter 800 W Blender & Dry Mill 2 in 1,WestPoint Pakistan
WestPoint WF-9224 Commercial 220 W Electric Coffee Grinder,WestPoint Pakistan
WestPoint WF-2803 1750 ml Professional 600 W Food Processor 9 in 1,WestPoint Pakistan
WestPoint WF-2804 1750 ml Professional 450 W Food Processor 9 in 1,WestPoint Pakistan
WestPoint WF-3804 1750 ml Professional 450 W Food Processor 9 in 1,WestPoint Pakistan
WestPoint WF-1844 1.5 L Professional 600 W Juicer Blender 3 in 1,WestPoint Pakistan
WestPoint WF-1847 1.2L Professional 1000W Deluxe Food Processor,WestPoint Pakistan
WestPoint WF-1860 Food Processor Unbreakable Jug,WestPoint Pakistan
WestPoint WF-4805 1750 ml 450 W Food Processor Unbreakable Jug,WestPoint Pakistan
WestPoint WF-4806 1500 ml Professional 450 W Food Processor Unbreakable Jug,WestPoint Pakistan
WestPoint WF-5805 1750 ml Deluxe 450 W Food Processor Unbreakable Jug,WestPoint Pakistan
WestPoint WF-5806 1500 ml Professional 450 W Food Processor Unbreakable Jug,WestPoint Pakistan
WestPoint WF-7805 1750 ml 450 W Food Processor Unbreakable Jug,WestPoint Pakistan
WestPoint WF-7806 1750 ml 450 W Food Processor Unbreakable Jug,WestPoint Pakistan
WestPoint WF-8815 Professional 700 W Deluxe Food Processor,WestPoint Pakistan
WestPoint WF-8819 1100 W RoboMax Food Processor,WestPoint Pakistan
WestPoint WF-9301 400 W Deluxe Hand Mixer,WestPoint Pakistan
WestPoint WF-9401 200W Deluxe Hand Mixer,WestPoint Pakistan
WestPoint WF-9501 Deluxe 250 W Stainless Steel Hand Mixer,WestPoint Pakistan
WestPoint WF-9601 Turbo 200 W Stainless Steel Hand Mixer,WestPoint Pakistan
WestPoint WF-9701 400 W Deluxe Hand Mixer,WestPoint Pakistan
WestPoint WF-9802 400 W Deluxe Hand Mixer,WestPoint Pakistan
WestPoint WF-9806 Deluxe 500 W Stainless Steel Hand Mixer,WestPoint Pakistan
WestPoint WF-9807 Deluxe 500 W Stainless Steel Hand Mixer,WestPoint Pakistan
WestPoint WF-9915 700ml Deluxe 800 W Hand Blender 2 in 1,WestPoint Pakistan
WestPoint WF-9916 700ml Deluxe 1000 W Hand Blender Set 3 in 1,WestPoint Pakistan
WestPoint WF-9801 Deluxe 400 W Stainless Steel Hand Mixer,WestPoint Pakistan
WestPoint WF-9805 Deluxe 400 W Stainless Steel Hand Mixer,WestPoint Pakistan
WestPoint WF-9814 1000ml 600 W Deluxe Hand Blender,WestPoint Pakistan
WestPoint WF-9815 1000ml 600 W Deluxe Hand Blender,WestPoint Pakistan
WestPoint WF-9816 1000ml 600 W Deluxe Hand Blender,WestPoint Pakistan
WestPoint WF-9826 4L 500W Deluxe Stand Mixer,WestPoint Pakistan
WestPoint WF-9827 4L 500W Deluxe Stand Mixer,WestPoint Pakistan
WestPoint WF-9934 1000W Deluxe Hand Blender,WestPoint Pakistan
WestPoint WF-9935 Deluxe 1000W Hand Blender 2 in 1,WestPoint Pakistan
WestPoint WF-9936 1000W Deluxe Hand Mixer,WestPoint Pakistan
WestPoint WF-9714 800ml Professional 600 W Deluxe Hand Blender,WestPoint Pakistan
WestPoint WF-9715 800ml Professional 600 W Stainless Steel Hand Mixer,WestPoint Pakistan
WestPoint WF-9214 700ml 600 W Deluxe Hand Blender,WestPoint Pakistan
WestPoint WF-9215 700ml Deluxe 600 W Stainless Steel Hand Mixer,WestPoint Pakistan
WestPoint WF-9216 700ml Deluxe 600 W Hand Blender Set 3 in 1,WestPoint Pakistan
WestPoint WF-4616 4.3L 1000W Deluxe Stand Mixer,WestPoint Pakistan
WestPoint WF-4627B 1.0L Deluxe 1500W Professional Stand Mixer,WestPoint Pakistan
WestPoint WF-3616 5 Liter 500W Deluxe Dough Maker,WestPoint Pakistan
WestPoint WF-4636 7.0L 1500W Professional Stand Mixer,WestPoint Pakistan
WestPoint WF-4646 7.0L 1500W Professional Stand Mixer,WestPoint Pakistan
WestPoint WF-4711 Deluxe 1800 W Convection Rotisserie Oven,WestPoint Pakistan
WestPoint WF-7500 Professional 2200 W Convection Rotisserie Oven,WestPoint Pakistan
WestPoint WF-5500 Professional 1800W Convection Rotisserie Oven,WestPoint Pakistan
WestPoint WF-4500 Professional 1800 W Convection Rotisserie Oven,WestPoint Pakistan
WestPoint WF-6300 Professional 2200 W Convection Rotisserie Oven,WestPoint Pakistan
WestPoint WF-545 1 Liter 40 W Citrus Juicer,WestPoint Pakistan
WestPoint WF-550 1.5 Liter 40 W Citrus Juicer,WestPoint Pakistan
WestPoint WF-553 Deluxe 80 W Citrus Juicer,WestPoint Pakistan
WestPoint WF-546 600ml 25 W Citrus Juicer,WestPoint Pakistan
WestPoint WF-554 Deluxe 85 W Citrus Juicer,WestPoint Pakistan
WestPoint WF-636 700 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-637 700 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-638 700 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-639 Deluxe 700 WATTS Sandwich Toaster,WestPoint Pakistan
WestPoint WF-640 800 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-643 750 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-671 800 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-6696 750 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-6697 1000 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-6686 800 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-6393 Deluxe 1000W Sandwich Toaster 3 in 1,WestPoint Pakistan
WestPoint WF-152 Professional 2000 W Induction Cooker,WestPoint Pakistan
WestPoint WF-7112 15 W Deluxe Insect Killer,WestPoint Pakistan
WestPoint WF-5112 15 W Deluxe Insect Killer,WestPoint Pakistan
WestPoint WF-5115 Deluxe Insect Killer,WestPoint Pakistan
WestPoint WF-1090 Professional 800 W Deluxe Electric Chopper,WestPoint Pakistan
WestPoint WF-496C Deluxe 500 W Chopper & Vegetable Cutter,WestPoint Pakistan
WestPoint WF-497C 1500 W Chopper & Vegetable Cutter,WestPoint Pakistan
WestPoint WF-4981 Professional 800 W Deluxe Blender,WestPoint Pakistan
WestPoint WF-441 550 W Deluxe Blender,WestPoint Pakistan
WestPoint WF-443 550 W Deluxe Blender,WestPoint Pakistan
WestPoint WF-445 Professional 800 W Deluxe Blender,WestPoint Pakistan
WestPoint WF-393 2 Liter 900 W Deluxe Food Processor,WestPoint Pakistan
WestPoint WF-501 1200ML Deluxe 600 W Kitchen Robot Food Processor,WestPoint Pakistan
WestPoint WF-502 Deluxe 700 W Kitchen Robot Food Processor,WestPoint Pakistan
WestPoint WF-503 1.8L Deluxe 800 W Kitchen Robot Food Processor,WestPoint Pakistan
WestPoint WF-504 1200ML Deluxe 500 W Kitchen Robot Food Processor,WestPoint Pakistan
WestPoint WF-505 Professional 800 W Kitchen Robot Food Processor,WestPoint Pakistan
WestPoint WF-506 Deluxe 800 W Kitchen Robot Food Processor,WestPoint Pakistan
WestPoint WF-495C 500 W Chopper & Vegetable Cutter,WestPoint Pakistan
WestPoint WF-3469 25 Liter Professional 2200W Drum Vacuum Cleaner,WestPoint Pakistan
WestPoint WF-3569 25 Liter Professional 2200W Drum Vacuum Cleaner,WestPoint Pakistan
WestPoint WF-822 1270 W Deluxe Microwave Oven,WestPoint Pakistan
WestPoint WF-823 1270 W Deluxe Microwave Oven,WestPoint Pakistan
WestPoint WF-824 Professional 1270W Deluxe Microwave Oven,WestPoint Pakistan
WestPoint WF-825 20 L 1270 W Microwave Oven with Grill,WestPoint Pakistan
WestPoint WF-832 1250 W Deluxe Appliance,WestPoint Pakistan
WestPoint WF-851 1450 W Deluxe Appliance,WestPoint Pakistan
WestPoint WF-853 Professional 1450W Deluxe Appliance,WestPoint Pakistan
WestPoint WF-4307 1000W Deluxe Tower Heater,WestPoint Pakistan
WestPoint WF-6307 1000W Deluxe Tower Heater,WestPoint Pakistan
WestPoint WF-1401 3.2L 500W Deluxe Water Dispenser,WestPoint Pakistan
WestPoint WF-1546 Deluxe 70W Ultra Quiet Tower Fan,WestPoint Pakistan
WestPoint WF-2538 860 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-2542 860 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-2561 1050 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-2589 Professional 870 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-2528 1400 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-2563 1400 W Deluxe Sandwich Toaster,WestPoint Pakistan
WestPoint WF-F05 Manual Potato Fries Cutter,WestPoint Pakistan
WestPoint WF-F10 Deluxe Quick Manual Chopper,WestPoint Pakistan
WestPoint WF-6330 30 Liter 1600W Commercial Electric Water Boiler,WestPoint Pakistan
WestPoint WF-209 Deluxe 150W Baby Bottle Warmer,WestPoint Pakistan
WestPoint WF-210 Deluxe 400W Dual Baby Bottle Warmer,WestPoint Pakistan
WestPoint WF-329 Deluxe 500W Baby Bottle Sterilizer,WestPoint Pakistan
WestPoint WF-330 Deluxe 500W Baby Bottle Sterilizer,WestPoint Pakistan
WestPoint WF-2540 870 W Deluxe Sandwich Toaster,WestPoint Pakistan
Haier HTW-100-196G 10 KG Twin Tub Semi Automatic Washing Machine,HAIER
Haier HWM100-1269S6 10 KG Top Load Automatic Washing Machine,HAIER
Haier HWM 85-826 8.5 KG Top Load Automatic Washing Machine,HAIER
Haier HWM 90-1708 9 KG Top Load Automatic Washing Machine,HAIER
Haier HWM 100-316 HS8 10 KG Top Load Automatic Washing Machine,HAIER
Haier HWM 120-826 12 KG Top Load Automatic Washing Machine,HAIER
Haier HWM 130B-699S8 13 KG Top Load Inverter Automatic Washing Machine,HAIER
Haier HWM150-688S8 15 KG Top Load Automatic Washing Machine,HAIER
Haier HWM 150B-699S8 15 KG Top Load Inverter Automatic Washing Machine,HAIER
Haier HW90-BP12357S8 9 KG Front Load Inverter Automatic Washing Machine,HAIER
Haier HW100-BP12357S8 10 KG Front Load Inverter Automatic Washing Machine,HAIER
Haier HW120-BP12357S8 12 KG Front Load Inverter Automatic Washing Machine,HAIER
Haier HW 105-BD14376PGU1 10.5 KG Front Load Automatic Washing Machine,HAIER
Haier HD 100-AR376PGU1 10 KG Front Load Automatic Washing Machine,HAIER
Dawlance DW-6580 CFL 6.5 KG Twin Tub Semi Automatic Washing Machine,DAWLANCE
Dawlance DWT-1580 C-Glow 15 KG Top Load Inverter Automatic Washing Machine,DAWLANCE
Dawlance DWT 1776 FLT C Glow 17 KG Top Load Automatic Washing Machine,DAWLANCE
Dawlance DWF 7310 INV 6.5 KG Front Load Inverter Automatic Washing Machine,DAWLANCE
"TCL 43"" S5400 Full HD Micro Dimming Smart Led TV",TCL
"TCL 55"" P6L 4K UHD Direct LED Smart Led TV",TCL
"TCL 65"" P6L 4K UHD Direct LED Smart TV",TCL
"TCL 75"" P6L 4K UHD Direct LED Smart Led TV",TCL
"TCL 43"" P79L 4K UHD QLED Smart Led TV",TCL
"TCL 50"" P79L 4K UHD QLED Smart Led TV",TCL
"TCL 55"" P79L 4K UHD QLED Smart Led TV",TCL
"TCL 65"" P79L 4K UHD QLED Smart Led TV",TCL
"TCL 75"" P79L 4K UHD QLED Smart Led TV",TCL
"TCL 85"" P79L 4K UHD QLED Smart Led TV",TCL
"TCL 43"" T6D 4K UHD QLED Smart Led TV",TCL
"TCL 50"" T6D 4K UHD QLED Smart Led TV",TCL
"TCL 55"" T6D 4K UHD QLED Smart Led TV",TCL
"TCL 65"" T6D 4K UHD QLED Smart Led TV",TCL
"TCL 75"" T6D 4K UHD QLED Smart Led TV",TCL
"TCL 55"" P8L 4K UHD QD-Mini LED Smart Led TV",TCL
"TCL 65"" P8L 4K UHD QD-Mini LED Smart Led TV",TCL
"TCL 75"" P8L 4K UHD QD-Mini LED Smart Led TV",TCL
"TCL 85"" P8L 4K UHD QD-Mini LED Smart Led TV",TCL
"TCL 98"" P8L 4K UHD QD-Mini LED Smart Led TV",TCL
"TCL 50"" C6K 4K UHD QLED Pro Smart Led TV",TCL
"TCL 55"" C6K 4K UHD QLED Pro Smart Led TV",TCL
"TCL 65"" C6K 4K UHD QLED Pro Smart Led TV",TCL
"TCL 75"" C6K 4K UHD QLED Pro Smart Led TV",TCL
"TCL 85"" C6K 4K UHD QLED Pro Smart Led TV",TCL
"TCL 98"" C6K 4K UHD QLED Pro Smart Led TV",TCL
"TCL 65"" C7L 4K UHD QD-Mini LED Smart TV",TCL
"TCL 75"" C7L 4K UHD QD-Mini LED Smart Led TV",TCL
"TCL 85"" C7L 4K UHD QD-Mini LED Smart Led TV",TCL
"TCL 98"" C7L 4K UHD QD-Mini LED Smart Led TV",TCL
"TCL 55"" A400 PRO NXTFRAME Art Lifestyle 4K UHD QLED Pro Smart Led TV",TCL
"TCL 65"" A400 PRO NXTFRAME Art Lifestyle 4K UHD QLED Pro Smart Led TV",TCL
"TCL 75"" A400 PRO NXTFRAME Art Lifestyle 4K UHD QLED Pro Smart Led TV",TCL
"TCL 43"" T6C Mid-Range QLED 4K Smart Led TV",TCL
"TCL 85"" C7K Premium QD-Mini LED Smart Led TV",TCL
"TCL 65"" C645 Mid-Range QLED Smart Led TV",TCL
"TCL 65"" C835 Premium Mini LED Smart Led TV",TCL
"TCL 75"" C655 QLED Pro 4K Smart Led TV",TCL
"Haier 32"" H32S80GFX Full HD Smart LED Google TV",HAIER
"Haier 65"" H65S80EUX 4K UHD Smart LED Google TV",HAIER
"Haier 75"" H75S80EUX 4K UHD Smart LED Google TV",HAIER
"Haier 98"" H98S90EUX 4K UHD Smart LED Google TV",HAIER
"Haier 55"" H55S900UX 4K UHD Smart LED Google TV",HAIER
Anex AG-01 Deluxe Handy Pull Chopper,Anex
Anex AG-04 Handy Potato Cutter,Anex
Anex AG-08 Manual Multi Wonder (5 BLADES),Anex
Anex AG-10 Handy Chopper with 10 Functions,Anex
Anex AG-11 Handy 3L Pull Chopper - 2200W,Anex
Anex AG-12 Deluxe Handy Food Processor - 300W,Anex
Anex AG-15 Deluxe Manual Vegetable Slicer,Anex
Anex AG-17 Deluxe Vegetable & Food Slicer,Anex
Anex AG-390 Deluxe Egg Beater - 250W,Anex
Anex AG-392 Deluxe Hand Mixer - 250W,Anex
Anex AG-398 Deluxe Hand Mixer & Blender - 300W,Anex
Anex AG-399 Deluxe Hand Mixer - 250W,Anex
Anex AG-121 Deluxe Hand Blender - 300W,Anex
Anex AG-122 Deluxe Hand Blender - 600W,Anex
Anex AG-126 Deluxe Hand Blender with Beater (New) - 300W,Anex
Anex AG-128 Deluxe Hand Blender - 800W,Anex
Anex AG-129 Deluxe Hand Blender with Beater - 800W,Anex
Anex AG-130 Deluxe Hand Blender and Beater and Chopper - 800W,Anex
Anex AG-140 Deluxe Hand Blender and Beater and Chopper - 300W,Anex
Anex AG-141 Deluxe Hand Blender With Titanium Blade - 500W,Anex
Anex AG-142 Deluxe Hand Blender with Beater - 500W,Anex
Anex AG-143 Deluxe Hand Blender with Beater & Chopper - 500W,Anex
Anex AG-145 Deluxe Hand Blender With Titanium Blade - 1000W,Anex
Anex AG-144 Deluxe Hand Blender With Milk Frother - 1000W,Anex
Anex AG-644 Deluxe Grinder (Wet & Dry) - 380W,Anex
Anex AG-645 Deluxe Grinder (Wet & Dry) - 380W,Anex
Anex AG-646 Deluxe Grinder - 380W,Anex
Anex AG-647 Deluxe Grinder (Wet & Dry) - 250W,Anex
Anex AG-650 Deluxe Grinder - 200W,Anex
Anex AG-648 Deluxe Grinder (Stainless Steel) - 250W,Anex
Anex AG-649 Deluxe 2 in 1 Grinder (Wet & Dry) - 250W,Anex
Anex AG-690UB Deluxe Unbreakable 2 in 1 Blender - 300W,Anex
Anex AG-695UB Deluxe Unbreakable 3 in 1 Blender - 300W,Anex
Anex AG-697UB Deluxe Unbreakable 2 in 1 Blender - 300W,Anex
Anex AG-699UB Deluxe Unbreakable 3 in 1 Blender - 300W,Anex
Anex AG-6043 Deluxe 2 in 1 Blender and Grinder - 300W,Anex
Anex AG-6044 Deluxe 3 in 1 Blender and Grinder - 300W,Anex
Anex AG-6045 Deluxe 2 in 1 1.5L Blender and Grinder - 600W,Anex
Anex AG-6046 Deluxe 3 in 1 Blender and Grinder - 600W,Anex
Anex AG-6130 Deluxe 2 in 1 1.5L Stainless Steel Body Glass Jug & Grinder - 600W,Anex
Anex AG-6133 Deluxe 3 in 1 1.5L Stainless Steel Body Stainless Steel Jug & Grinder - 600W,Anex
Anex AG-6134UB Deluxe 2 in 1 1.5L Jug & Grinder - 500W,Anex
Anex AG-6135UB Deluxe 3 in 1 1.5L Jug & Grinder - 500W,Anex
Anex AG-6136 Deluxe 2 in 1 1.5L Blender and Grinder - 500W,Anex
Anex AG-6137 Deluxe 3 in 1 Blender and Grinder - 500W,Anex
Anex AG-6138 Deluxe 2 in 1 1.5L Stainless Steel Jug & Grinder - 600W,Anex
Anex AG-6139 Deluxe 3 in 1 1.5L Stainless Steel Jug & Grinder - 600W,Anex
Anex AG-3043 4L Food Chopper - 400W,Anex
Anex AG-3048 Deluxe Big Chopper with Vegetable Cutter - 500W,Anex
Anex AG-3049SS Big Chopper with Vegetable Cutter,Anex
Anex AG-3052 7 in 1 2L Big Chopper - 700W,Anex
Anex AG-3054 Digital 7 in 1 2L Big Chopper - 700W,Anex
Anex AG-3055 Deluxe Chopper with Glass Bowl - 300W,Anex
Anex AG-3058 Deluxe Super Big Chopper with Extra Bowl (w) - 500W,Anex
Anex AG-3059 Deluxe Big Chopper with Extra Bowl (b) - 500W,Anex
Anex AG-1041 Food Processor,Anex
Anex AG-1141 Kitchen Chef - 500W,Anex
Anex AG-2048 Super Meat Grinder (Mincer) - 1200W,Anex
Anex AG-2049 Super Meat Grinder & Vegetable Cutter - 1200W,Anex
Anex AG-3060 Deluxe Meat Grinder - 1200W,Anex
Anex AG-2142 Deluxe Electric BBQ Grill - 2000W,Anex
Anex AG-2146UB Deluxe Kitchen Robot - 800W,Anex
Anex AG-2146EX Deluxe 1.25L Kitchen Robot - 380W,Anex
Anex AG-2150 Deluxe Kitchen Robot - 450W,Anex
Anex AG-3140 Deluxe 1.2L Chopper with Vegetable Cutter - 500W,Anex
Anex AG-3141 Deluxe Chopper with Vegetable Cutter - 800W,Anex
Anex AG-3142 Deluxe 1.2L Chopper with Vegetable Cutter - 500W,Anex
Anex AG-3143 1.2L Chopper with Vegetable Cutter - 800W,Anex
Anex AG-3144 Deluxe 1.2L Chopper with Vegetable Cutter - 800W,Anex
Anex AG-3145 Deluxe Chopper Blender with Vegetable Cutter - 800W,Anex
Anex AG-3146 Deluxe Chopper Blender with Vegetable Cutter,Anex
Anex AG-3147 9 in 1 2L Big Chopper - 700W,Anex
Anex AG-3148 Digital 9 in 1 Big Chopper - 700W,Anex
Anex AG-3150 Deluxe Kitchen Robot - 700W,Anex
Anex AG-3151 Deluxe Kitchen Robot - 700W,Anex
Anex AG-3152 Deluxe 2.5L Kitchen Robot - 900W,Anex
Anex AG-3153 Deluxe Kitchen Robot Titanium Blade - 450W,Anex
Anex AG-3156 Food Processor - 1100W,Anex
Anex AG-3157 Food Processor With Juicer - 1100W,Anex
Anex AG-3159 Deluxe 1.8L Kitchen Robot - 1200W,Anex
Anex AG-3004 Deluxe 2 Slice Toaster - 930W,Anex
Anex AG-3005 Deluxe 4 Slice Toaster Full Stainless Steel - 1550W,Anex
Anex AG-3006 Deluxe 2 Slice Toaster - 870W,Anex
Anex AG-3007 Deluxe 4 Slice Toaster Stainless Steel+Plastic - 1550W,Anex
Anex AG-3008 Deluxe 2 Slice Toaster - 1050W,Anex
Anex AG-3009 Deluxe 4 Slice Toaster - 2300W,Anex
Anex AG-3017 Deluxe 2 Slice Toaster Cool Touch - 870W,Anex
Anex AG-3018 Deluxe 2 Slice Toaster - 870W,Anex
Anex AG-3019 Deluxe 2 Slice Toaster - 870W,Anex
Anex AG-1035 Deluxe Sandwich White/Black - 750W,Anex
Anex AG-1037C Deluxe Sandwich Maker - 750W,Anex
Anex AG-2040 Deluxe Sandwich Maker - 750W,Anex
Anex AG-2045 Deluxe Sandwich Maker - 750W,Anex
Anex AG-2046 Deluxe Sandwich Maker,Anex
Anex AG-2047 Deluxe 3 in 1 Sandwich Maker,Anex
Anex AG-2036 Deluxe Sandwich Maker - 900W,Anex
Anex AG-1039C Deluxe Sandwich and Waffle and Grill - 750W,Anex
Anex AG-2039C Deluxe 3 in 1 Sandwich Maker - 750W,Anex
Anex AG-2131 Deluxe Sandwich Maker - 750W,Anex
Anex AG-2132 Deluxe Sandwich Maker - 1000W,Anex
Anex AG-2137 Deluxe Sandwich Maker - 1400W,Anex
Anex AG-2138 Deluxe 3 in 1 Sandwich and Waffle and Grill - 750W,Anex
Anex AG-2139 Deluxe 3 in 1 Sandwich and Waffle and Grill - 750W,Anex
Anex AG-3130 Deluxe Sandwich Maker - 750W,Anex
Anex AG-76 Deluxe Juicer - 600W,Anex
Anex AG-77 Deluxe Juicer - 600W,Anex
Anex AG-78 Deluxe Juicer - 600W,Anex
Anex AG-89 Deluxe 1.5L Juicer - 800W,Anex
Anex AG-90 3.2L Juicer - 600W,Anex
Anex AG-91 Deluxe Juicer Stainless Steel Body - 600W,Anex
Anex AG-92 Deluxe 1.5L Juicer Stainless Steel Body - 500W,Anex
Anex AG-95 Deluxe Digital Single Juicer With Panel - 600W,Anex
Anex AG-175GL Deluxe Juicer Blender Grinder - 600W,Anex
Anex AG-177GL Deluxe Juicer. Blender and Grinder - 600W,Anex
Anex AG-178GL Deluxe Juicer and Blender and Grinder - 600W,Anex
Anex AG-179GL Deluxe Juicer and Blender and Grinder - 600W,Anex
Anex AG-182GL Deluxe Juicer and Blender and Grinder,Anex
Anex AG-180GL Deluxe Juicer and Blender and Grinder - 600W,Anex
Anex AG-181 Deluxe Juicer and Blender and Grinder Stainless Steel - 600W,Anex
Anex AG-184GL Deluxe Juicer and Blender and Grinder and Chopp - 700W,Anex
Anex AG-188GL Deluxe Juicer and Blender and Grinder and Wet Gr - 800W,Anex
Anex AG-189 Deluxe Juicer and Blender and Grinder - 600W,Anex
Anex AG-190 Deluxe 3 in 1 Juicer and Blender and Grinder - 600W,Anex
Anex AG-191 Deluxe 4 in 1 Juicer and Blender. Grinder - 600W,Anex
Anex AG-192 Deluxe 1.5L Juicer and Blender and Grinder - 500W,Anex
Anex AG-195 Deluxe Digital Juicer Blender Grinder - 600W,Anex
Anex AG-2012 Deluxe 2.5L Deep Fryer - 1800W,Anex
Anex AG-2014 2.5L Deep Fryer - 1800W,Anex
Anex AG-2016 Deluxe 6.5L Air Fryer - 1600W,Anex
Anex AG-2017 Deluxe 8L Air Fryer - 1800W,Anex
Anex AG-2019 Deluxe Air Fryer - 1400W,Anex
Anex AG-2022 4L Multi Cooker - 1350W,Anex
Anex AG-2188 8L Multi Pressure Cooker - 1000W,Anex
Anex AG-2024 Deluxe Digital 8L Air Fryer Up & Down Elements - 1800W,Anex
Anex AG-2121 Deluxe Air Fryer With Oven - 1200W,Anex
Anex AG-2123 Deluxe Air Fryer With Oven Rotessori - 1200W,Anex
Anex AG-2126 Deluxe Digital 8L Air Fryer Up & Down Elements - 2200W,Anex
Anex AG-2029 Deluxe Roti Maker - 1200W,Anex
Anex AG-2030 Deluxe Roti Maker - 1200W,Anex
Anex AG-2021 Deluxe 1.8L Rice Cooker - 900W,Anex
Anex AG-2023 Deluxe 2.2L Rice Cooker With Steamer - 900W,Anex
Anex AG-2127 Deluxe 5L Dough Maker - 500W,Anex
Anex AG-2093 Deluxe 2 in 1 4.5L Vacuum Cleaner - 1500W,Anex
Anex AG-2097 Deluxe 2 in 1 Vacuum Cleaner - 1500W,Anex
Anex AG-2098 Deluxe 2 in 1 Vacuum Cleaner - 1500W,Anex
Anex AG-2099 Deluxe 3 in 1 Vacuum Cleaner - 1500W,Anex
Anex AG-2199 Deluxe 2 in 1 Vacuum Cleaner - 1600W,Anex
Anex AG-5014 Deluxe Ceramic Fan Heater - 2000W,Anex
Anex AG-5015 Deluxe Ceramic Fan Heater - 2000W,Anex
Anex AG-5016 Ceramic Fan Heater - 2000W,Anex
Anex AG-5017 Ceramic Fan Heater with Remote - 2000W,Anex
Anex AG-3039 Deluxe Sun Heater - 1000W,Anex
Anex AG-9086 3L Fan Air Cooler with Remote Control,Anex
Anex AG-9087 Deluxe Tower Fan Air Cooler,Anex
Anex AG-2154 Deluxe 0.85L Citrus Juicer,Anex
Anex AG-2054 Deluxe Citrus Juicer (40 W),Anex
Anex AG-2055 Deluxe Citrus Juicer (40 W),Anex
Anex AG-2058 Deluxe Citrus Juicer,Anex
Anex AG-2158 Deluxe Citrus Juicer - 160W,Anex
Anex AG-2074 Deluxe Dry Iron - 1300W,Anex
Anex AG-2078 Deluxe Dry Iron With Spray - 1300W,Anex
Anex AG-1072 Deluxe Dry Iron - 1000W,Anex
Anex AG-662 Deluxe Middle Weight Iron - 1000W,Anex
Anex AG-1076B Deluxe 6L Dry Iron - 1000W,Anex
Anex AG-1079B Deluxe 6L Dry Iron - 1000W,Anex
Anex AG-2079B Deluxe 6L Dry Iron - 1000W,Anex
Anex AG-2179B Deluxe 346L Dry Iron - 1000W,Anex
Anex AG-1022 Deluxe Steam Iron - 2200W,Anex
Anex AG-1027 Deluxe Steam Iron - 2200W,Anex
Anex AG-1028EX Deluxe Steam Iron,Anex
Anex AG-1030 Deluxe Steam Iron - 2400W,Anex
Anex AG-1018 Deluxe Handy Garment Steamer - 2100W,Anex
Anex AG-1019 Deluxe Handy Garment Steamer - 1900W,Anex
Anex AG-1020 Deluxe 2.1L Garment Steamer - 2000W,Anex
Anex AG-1120 1.8L Garment Steamer - 2100W,Anex
Anex AG-1121 2.2L Garment Steamer - 2000W,Anex
Anex AG-1122 3L Garment Steamer - 2200W,Anex
Anex AG-7003 Deluxe Hair Dryer - 1600W,Anex
Anex AG-7004 Deluxe Hair Dryer,Anex
Anex AG-7005 Deluxe Hair Dryer - 1600W,Anex
Anex AG-7006 Deluxe Hair Dryer - 1300W,Anex
Anex AG-7007 Hair Dryer With Ionic - 2200W,Anex
Anex AG-7008 Deluxe Hair Dryer - 1600W,Anex
Anex AG-7025 Deluxe Hair Dryer - 2000W,Anex
Anex AG-7026 Deluxe Hair Dryer with Diffuser - 2000W,Anex
Anex AG-7028 Deluxe Hair Dryer With Ionic - 2200W,Anex
Anex AG-7029 Deluxe Hair Dryer With Ionic - 2600W,Anex
Anex AG-7030 Hair Dryer With Ionic - 2000W,Anex
Anex AG-7031 Deluxe Hair Straightener,Anex
Anex AG-7034 Hair Straightener,Anex
Anex AG-7035 Deluxe Hair Straightener Heat Controller,Anex
Anex AG-7037 Deluxe Hair Straightener,Anex
Anex AG-7038 Deluxe Hair Straightener & Curler,Anex
Anex AG-7039 Deluxe Hair Straightener,Anex
Anex AG-7040 Deluxe 2 in 1 Hair Straightener & Curler,Anex
Anex AG-7041 Deluxe Hair Straightener,Anex
Anex AG-7042 Deluxe Curl & Straight Styler,Anex
Anex AG-7139 Hair Straightener With Ionic Fund,Anex
Anex AG-7018 Facial Steamer,Anex
Anex AG-7023 Foot Massager + Heater - 345W,Anex
Anex AG-7045 Deluxe Epilator - 1600W,Anex
Anex AG-7061 Deluxe Trimmer,Anex
Anex AG-7062 Deluxe Trimmer,Anex
Anex AG-7063 Trimmer,Anex
Anex AG-7064 Trimmer,Anex
Anex AG-7065 Deluxe Trimmer,Anex
Anex AG-7066 Deluxe Trimmer,Anex
Anex AG-7067 4L Trimmer,Anex
Anex AG-7068 Deluxe Hair Trimmer and Nose Trimmer and Sha,Anex
Anex AG-308 Deluxe Hair Curler,Anex
Anex AG-8024 Manual Bath Scale,Anex
Anex AG-8025 Manual Bath Scale,Anex
Anex AG-8026 Digital 400L Bath Scale,Anex
Anex AG-8027 Digital Bath Scale,Anex
Anex AG-1064 Deluxe 100L Oven Toaster - 1380W,Anex
Anex AG-1065 Deluxe Oven Toaster with Bar BQ Grill - 1380W,Anex
Anex AG-1070 Deluxe Oven Toaster with Bar BQ Grill - 1500W,Anex
Anex AG-3067 Deluxe Oven Toaster Bar BQ Grill - 1600W,Anex
Anex AG-3069TT Convection Oven with Bar BQ - 1600W,Anex
Anex AG-2070 Deluxe Convection Oven BBQ Grill Rot - 2000W,Anex
Anex AG-3070 Deluxe 100L Convection Oven BBQ Grill Rot - 2000W,Anex
Anex AG-3071 Deluxe Oven Toaster BBQ Grill,Anex
Anex AG-3072 Deluxe Convection Oven BBQ Grill Rot - 2000W,Anex
Anex AG-3073 Deluxe 100L Convection Oven BBQ With Gril - 2000W,Anex
Anex AG-3075 Deluxe Digital Oven With Fan & BBQ G - 1600W,Anex
Anex AG-3079 Deluxe 100L Oven Toaster BBQ With Grill - 2200W,Anex
Anex AG-3080 Deluxe Digital Oven With Fan & BBQ G - 2200W,Anex
Anex AG-9028 Deluxe Microwave Oven (Manual) - 700W,Anex
Anex AG-9029 Microwave Oven - 900W,Anex
Anex AG-9031 Deluxe Digital Microwave Oven - 900W,Anex
Anex AG-9039 Deluxe Digital Microwave With Oven - 900W,Anex
Anex AG-1086 Deluxe Insect Killer 2X8W,Anex
Anex AG-1087 Insect Killer 2X10W,Anex
Anex AG-1088 Insect Killer 2X15W,Anex
Anex AG-1089 Deluxe Insect Killer 2X20W,Anex
Anex AG-3084 Deluxe Insect Killer 2X8W,Anex
Anex AG-3085 Deluxe Insect Killer 2X10W,Anex
Anex AG-3086 Deluxe Insect Killer 2X15W,Anex
Anex AG-3088 Deluxe Insect Killer 2X20W,Anex
Anex AG-3091 Deluxe Insect Killer 2X8W,Anex
Anex AG-3092 Deluxe Insect Killer 2X10W,Anex
Anex AG-3093 Deluxe Insect Killer 2X15W,Anex
Anex AG-3094 Deluxe Insect Killer 2X20W,Anex
Anex AG-3095 Deluxe Insect Killer 2X8W,Anex
Anex AG-3096 Deluxe Insect Killer 2X10W,Anex
Anex AG-3097 Deluxe Insect Killer 2X15W,Anex
Anex AG-3098 Deluxe Insect Killer 2X20W,Anex
Anex AG-4027 Deluxe 1.7L Concealed Element Kettle - 2000W,Anex
Anex AG-4032 Deluxe 1L Concealed Element Kettle - 1200W,Anex
Anex AG-4033 Deluxe 1.7L Concealed Element Kettle - 2200W,Anex
Anex AG-4042 Deluxe 1.7L Plastic Body Kettle - 2200W,Anex
Anex AG-4046 Deluxe 1.7L Steel Body Kettle - 2200W,Anex
Anex AG-4047 Deluxe 1.7L Steel Body Kettle - 2200W,Anex
Anex AG-4048 Deluxe 1.7L Steel Body Kettle - 2150W,Anex
Anex AG-4051 Deluxe 1L Steel Body Kettle - 2200W,Anex
Anex AG-4052 Deluxe Travel Steel Body Kettle - 1350W,Anex
Anex AG-4053 Deluxe 1L Steel Body Kettle - 1350W,Anex
Anex AG-4054 Deluxe 1.6L Multi Purpose Kettle - 600W,Anex
Anex AG-4055 Deluxe 1.75L Plastic Body Kettle - 2150W,Anex
Anex AG-4056 Deluxe 1.7L Steel Body Kettle - 1500W,Anex
Anex AG-4057 Deluxe 1.7L Steel Body Concealed Element Kettle - 1700W,Anex
Anex AG-4058 Deluxe 1.7L Concealed Element Kettle - 1500W,Anex
Anex AG-4060 Deluxe 0.8L Plastic Body Kettle - 1000W,Anex
Anex AG-4061 Deluxe 1.2L Plastic Body Kettle - 1350W,Anex
Anex AG-4062 Deluxe 1.8L Steel Body Kettle - 1500W,Anex
Anex AG-4064 Deluxe 1.8L Steel Body Kettle - 1500W,Anex
Anex AG-4065 Deluxe 1.7L Plastic Body Concealed Element Kettle - 2200W,Anex
Anex AG-4066 Deluxe 1.5L Steel & Glass Body Kettle - 1350W,Anex
Anex AG-4067 Deluxe 1.7L Plastic Body Kettle - 2200W,Anex
Anex AG-4070 Deluxe 1.7L Steel Body Concealed Element Kettle - 2200W,Anex
Anex AG-4071 Deluxe 1.75L Steel Body Kettle - 2200W,Anex
Anex AG-4072 Deluxe 1.75L Steel Body Kettle - 2200W,Anex
Anex AG-801 Deluxe Coffee Maker - 550W,Anex
Anex AG-802 Deluxe Coffee Maker - 600W,Anex
Anex AG-803 Deluxe 1L Coffee Maker - 800W,Anex
Anex AG-811 Deluxe 1.25L Coffee Maker - 1080W,Anex
Anex AG-825 Deluxe 1.6L Coffee Maker - 850W,Anex
Anex AG-826 Deluxe Coffee Maker - 850W,Anex
Anex AG-830 Deluxe 1.8L Coffee Maker - 850W,Anex
Anex AG-819 Deluxe 5L Stand Mixer Stainless Steel Bowl - 1200W,Anex
Anex AG-834 Deluxe 5L Stand Mixer Stainless Steel Bowl - 1200W,Anex
Anex AG-820 Deluxe 7L Stand Mixer Stainless Steel Bowl - 1500W,Anex
Anex AG-821 Deluxe Egg Beater - 300W,Anex
Anex AG-822 Deluxe 3.5L Stand Egg Beater - 300W,Anex
Anex AG-823 Digital Egg Beater - 300W,Anex
Anex AG-732 Deluxe Baby Bottle Warmer - 150W,Anex
Anex AG-733EX Deluxe Baby Bottle Warmer - 250W,Anex
Anex AG-736 Deluxe Sterlizer - 500W,Anex
Anex AG-737 Deluxe Sterlizer - 500W,Anex
Anex AG-775 Deluxe Egg Boiler - 410W,Anex
Anex AG-2166 Deluxe Hot Plate With Timer - 2200W,Anex
Anex AG-2167 Deluxe Digital Hot plate Single - 2000W,Anex
Anex AG-2168 Deluxe Infrared Cooker - 2000W,Anex
Anex AG-2174 Deluxe Induction Cooker - 2000W,Anex
Anex AG-3061 Deluxe Hot plate Stainless Steel Single - 1500W,Anex
Anex AG-3062 Deluxe Hot plate Stainless Steel Double - 2500W,Anex
Anex AG-3063 Deluxe Pizza Pan / Cooking Pan - 1200W,Anex
ORIENT Crystal 3 Taps (Smoke Purple) Crystal Glass Door Water Dispenser - 3 Taps,ORIENT
Orient Marvel 3 Taps Marvel Red Glass Door Water Dispenser - 3 Taps,ORIENT
ORIENT DMZ1-2054-MP-IS-0265 Velvet Glass Door Water Dispenser - 3 Taps,ORIENT
PEL PWD-115 Classic Table-Top Water Dispenser - 2 Taps,PEL
PEL PWD-316 Premier Premier Series Water Dispenser - 3 Taps,PEL
PEL PWD-3TAB 425 Straight Glass Door Water Dispenser - 3 Taps,PEL
PEL PWD-425 FLAT Flat Glass Door Water Dispenser - 2 Taps,PEL
Homage HWD-49320 Table Top Series Water Dispenser - 2 Taps,Homage
Homage HWD-49331P Non-Fridge Floor Series Water Dispenser - 3 Taps,Homage
Homage HWD-49332P Fridge Cabinet Water Dispenser - 3 Taps,Homage
HAIER HDR-TC2C1GB-PK Black Glass Mirror Series Water Dispenser - 2 Taps,HAIER
DAWLANCE WD-1051 CN GREY (Cool & Normal) Water Dispenser - 2 Taps,DAWLANCE
DAWLANCE WD-1051 HC WHITE HC Series (Hot & Cool) Water Dispenser - 2 Taps,DAWLANCE
DAWLANCE WD-1060 WHITE W Non-Fridge Series Water Dispenser - 2 Taps,DAWLANCE
Haier HRF-186 EBD 6 Cu Ft Metallic Grey E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-216 EBD 8 Cu Ft Metallic Grey E-Star Non-Inverter Refrigerator,HAIER
HAIER HR-136 B 4 Cu Ft Black Single Door Non-Inverter Refrigerator,HAIER
HAIER HRF-216 EPB 8 Cu Ft Black Glass E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-246 EBS 9 Cu Ft Silver E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-276 EPR 10 Cu Ft Red Glass E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-316 EPB 11 Cu Ft Black Glass E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-316 EPR 11 Cu Ft Red Glass E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-346 EPB 12 Cu Ft Black Glass E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-368 EPB 13 Cu Ft Black Wave Glass E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-368 EPR 13 Cu Ft Red Wave Glass E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-398 EPB 14 Cu Ft Black Wave Glass E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-398 EPR 14 Cu Ft Red Wave Glass E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-438 EPB 15 Cu Ft Black Wave Glass E-Star Non-Inverter Refrigerator,HAIER
HAIER HRF-438 EPR 15 Cu Ft Red Wave Glass E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-368 IFGA 14 Cu Ft Green Glass Door Digital Inverter Refrigerator,HAIER
Haier HRF-316 IFGA 11 Cu Ft Green Digital Inverter Refrigerator,HAIER
Haier HRF-316 IFPA 11 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-316 IFRA 11 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-346 IFGA 12 Cu Ft Green Digital Inverter Refrigerator,HAIER
Haier HRF-346 IFPA 12 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-346 IFRA 12 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-368 IFPA 14 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-398 IFGA 15 Cu Ft Green Digital Inverter Refrigerator,HAIER
Haier HRF-398 IFPA 15 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-398 IFRA 15 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-438 IFRA 16 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-418 IFGA 14 Cu Ft Green Digital Inverter Refrigerator,HAIER
Haier HRF-418 IFPA 14 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-418 IFRA 14 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-458 IFGA 16 Cu Ft Green Digital Inverter Refrigerator,HAIER
Haier HRF-458 IFPA 16 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-458 IFRA 16 Cu Ft Red Digital Inverter Refrigerator,HAIER
HAIER HRF-538 IFPA 20 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-438 IBSA 18 Cu Ft Silver Digital Inverter Refrigerator,HAIER
Haier HRF-418 TIFGU1 15 Cu Ft Grey Twin Inverter IOT Refrigerator,HAIER
Haier HRF-458 TIFBU1 16 Cu Ft Black Twin Inverter IOT Refrigerator,HAIER
Haier HRF-458 TIFGU1 16 Cu Ft Silver Grey Twin Inverter IOT Refrigerator,HAIER
Haier HRF-538 TIFGU1 20 Cu Ft Silver Grey Twin Inverter IOT Refrigerator,HAIER
Haier HRF-538 TIFBU1 20 Cu Ft Black Twin Inverter IOT Refrigerator,HAIER
Haier HRF-316 IARA 11 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-346 IARA 12 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-438 IARA+ 15 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-368 IARA+ 13 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-368 IAPA+ 13 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-398 IARA+ 14 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-398 IAPA+ 14 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-418 IARA+ 15 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-418 IAPA+ 15 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-458 IARA+ 16 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-458 IAPA+ 16 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-538 IARA+ 20 Cu Ft Red Digital Inverter Refrigerator,HAIER
Haier HRF-538 IAPA+ 20 Cu Ft Purple Digital Inverter Refrigerator,HAIER
Haier HRF-538 EPR 20 Cu Ft Red E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-538 EPG 20 Cu Ft Green E-Star Non-Inverter Refrigerator,HAIER
Haier HRF-246 IPRA 9 Cu Ft Red Smart Inverter Refrigerator,HAIER
Haier HRF-246 IPPA 9 Cu Ft Purple Smart Inverter Refrigerator,HAIER
Haier HRF-276 IPRA 10 Cu Ft Red Smart Inverter Refrigerator,HAIER
Haier HRF-276 IPPA 10 Cu Ft Purple Smart Inverter Refrigerator,HAIER
Haier HRF-316 IPPA 11 Cu Ft Purple Smart Inverter Refrigerator,HAIER
Haier HRF-346 IPGA 12 Cu Ft Green Smart Inverter Refrigerator,HAIER
Haier HRF-346 IPRA 12 Cu Ft Red Smart Inverter Refrigerator,HAIER
Haier HRF-346 IPPA 12 Cu Ft Purple Smart Inverter Refrigerator,HAIER
Haier HRF-418 IPGA 15 Cu Ft Green Smart Inverter Refrigerator,HAIER
Haier HRF-418 IPPA 15 Cu Ft Purple Smart Inverter Refrigerator,HAIER
Haier HRF-458 IPRA 16 Cu Ft Red Smart Inverter Refrigerator,HAIER
Haier HRF-458 IPPA 16 Cu Ft Purple Smart Inverter Refrigerator,HAIER
Haier HRF-538 IPGA 20 Cu Ft Green Smart Inverter Refrigerator,HAIER
Haier HRF-538 IPRA 20 Cu Ft Red Smart Inverter Refrigerator,HAIER
Haier HRF-538 IPPA 20 Cu Ft Purple Smart Inverter Refrigerator,HAIER
Haier HRF-578 TGGU1 IOT 20 Cu Ft Champagne Gold T-Door Smart IoT Twin Inverter Refrigerator,HAIER
Haier HRF-622 IBS 22 Cu Ft Black Inox Side by Side Twin Inverter Refrigerator,HAIER
Haier HRF-622 ICG 22 Cu Ft Chocolate Glass Side by Side Twin Inverter Refrigerator,HAIER
Haier HRF-622 IBG 22 Cu Ft Black Mirror Side by Side Twin Inverter Refrigerator,HAIER
Haier HRF-678 TGG 24 Cu Ft Golden Glass T-Door Twin Inverter Refrigerator,HAIER
Haier HRF-578 TSG 20 Cu Ft Silver Inox T-Door Twin Inverter Refrigerator,HAIER
Haier HRF-578 TBG 20 Cu Ft Black Glass T-Door Twin Inverter Refrigerator,HAIER
Haier HRF-488 IFFB 17 Cu Ft Black Mirror No Frost Twin Inverter Refrigerator,HAIER
Haier HRF-518 IFFB 18 Cu Ft Black Mirror No Frost Twin Inverter Refrigerator,HAIER
Haier HRF-518 WIFFBGU1 18 Cu Ft Black Mirror No Frost Smart IoT Twin Inverter Refrigerator,HAIER
Anex AG-6143 Deluxe Blender Grinder - 550W,Anex
Anex AG-6144 Deluxe Blender Grinder - 550W,Anex
Anex AG-193 Deluxe Juicer Blender - 500W,Anex
Anex AG-2186 Deluxe Pressure Cooker - 1000W,Anex
Anex AG-2111 Deluxe Air Fryer - 1600W,Anex
Anex AG-2112 Deluxe Air Fryer - 2500W,Anex
Anex AG-7043 Deluxe Ceramic Hair Straightener - 230°C,Anex
Anex AG-7046 Deluxe 2-in-1 Epilator - USB Rechargeable,Anex
Anex AG-2160 Single Deluxe Hotplate - 1500W,Anex
Anex AG-2163 Double Deluxe Hotplate - 2500W,Anex
Anex AG-5053 16 Inch Deluxe Stand Fan,Anex
Anex AG-5054 16 Inch Deluxe Remote Stand Fan,Anex
Anex AG-5058 Deluxe Stand Fan - 18 Inch,Anex
Haier HRF-276EBD 10 Cu Ft Golden E-Star 1HIT Non-Inverter Refrigerator,HAIER
Dawlance DWT 9060 EZ Platinum 9 Kg Dark Grey Extreme+ Dryer Non-Inverter Washing Machine,DAWLANCE
Dawlance DWT 1016 INV PRIMA 10 Kg Dark Grey Prima Series DDM Inverter Washing Machine,DAWLANCE
Dawlance DW 7500 C 10 Kg White Twin Tub Clear Lid Non-Inverter Washing Machine,DAWLANCE
Dawlance DW 6550 W 8 Kg White Twin Tub White Lid Non-Inverter Washing Machine,DAWLANCE
Dawlance VF-1035 GD 12 Cu Ft Burgundy Honey-Comb Glass Door Non-Inverter Vertical Deep Freezer,DAWLANCE
Haier Home Deal Four in One,HAIER
Dawlance Home Deal Four in One,DAWLANCE
Dawlance DWMO 5222 CR 55 Liters Convection Oven Toaster,DAWLANCE
Dawlance DW-142 HZP 42 Liters Silver Grilling Microwave Oven,DAWLANCE
Dawlance DW-550 AF 30 Liters Black Air Fryer Microwave Oven,DAWLANCE
Dawlance DW-MD-4-N 20 Liters Black Solo Heating Microwave Oven,DAWLANCE
Dawlance DW-MD4 20 Liters White Solo Heating Microwave Oven,DAWLANCE
Dawlance DBMO-25 IG 25 Liters Built-in Grilling Microwave Oven,DAWLANCE
Dawlance DW-390 S 23 Liters Jet Black Solo Heating Microwave Oven,DAWLANCE
Dawlance DW-395 HCG 25 Liters Grilling Microwave Oven,DAWLANCE
````

## File: tests/test_cli.py
````python
"""Unit and integration tests for index.py CLI and catalog picker."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from index import (
    find_input_catalogs,
    interactive_catalog_picker,
    main,
    parse_args,
)


def test_find_input_catalogs(tmp_path: Path) -> None:
    (tmp_path / "Gree_AC.csv").write_text("dummy", encoding="utf-8")
    (tmp_path / "Haier_Washers.csv").write_text("dummy", encoding="utf-8")
    (tmp_path / "template.csv").write_text("dummy", encoding="utf-8")
    (tmp_path / "template_reference.csv").write_text("dummy", encoding="utf-8")
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("dummy", encoding="utf-8")

    catalogs = find_input_catalogs(tmp_path)

    assert len(catalogs) == 2
    names = [c.name for c in catalogs]
    assert "Gree_AC.csv" in names
    assert "Haier_Washers.csv" in names
    assert "template.csv" not in names


def test_interactive_catalog_picker_selection(tmp_path: Path) -> None:
    cat1 = tmp_path / "cat1.csv"
    cat2 = tmp_path / "cat2.csv"
    catalogs = [cat1, cat2]

    # Select single item "1"
    with patch("builtins.input", return_value="1"):
        res = interactive_catalog_picker(catalogs)
        assert res == [cat1]

    # Select all "A"
    with patch("builtins.input", return_value="A"):
        res = interactive_catalog_picker(catalogs)
        assert res == catalogs

    # Quit "Q"
    with patch("builtins.input", return_value="q"):
        res = interactive_catalog_picker(catalogs)
        assert res is None

    # Invalid input
    with patch("builtins.input", return_value="99"):
        res = interactive_catalog_picker(catalogs)
        assert res is None


def test_parse_args_defaults() -> None:
    with patch("sys.argv", ["index.py"]):
        args = parse_args()
        assert args.input is None
        assert args.output is None
        assert args.batch is False
        assert args.concurrency == 3
        assert args.quiet is False


def test_parse_args_explicit() -> None:
    with patch(
        "sys.argv",
        [
            "index.py",
            "-i",
            "custom_input.csv",
            "-o",
            "custom_output.csv",
            "-c",
            "5",
            "-q",
        ],
    ):
        args = parse_args()
        assert str(args.input) == "custom_input.csv"
        assert str(args.output) == "custom_output.csv"
        assert args.concurrency == 5
        assert args.quiet is True


def test_main_with_explicit_missing_file() -> None:
    with patch("sys.argv", ["index.py", "-i", "definitely_non_existent_file.csv"]):
        code = asyncio.run(main())
        assert code == 1


def test_main_with_explicit_valid_file(tmp_path: Path) -> None:
    test_csv = tmp_path / "test.csv"
    test_csv.write_text("Brand,Name,Net Price\n", encoding="utf-8")

    with (
        patch("sys.argv", ["index.py", "-i", str(test_csv)]),
        patch("index.run_pipeline", new_callable=AsyncMock) as mock_pipe,
    ):
        code = asyncio.run(main())
        assert code == 0
        mock_pipe.assert_called_once()
````

## File: tests/test_dawlance_benchmark.py
````python
"""Regression and benchmark test suite for Dawlance multi-tier search and strict referee matching.

Validates:
1. Dynamic Decomposer & Pattern Generator for leading capacity (e.g. 15 Infinity Pro -> Dawlance Infinity 15).
2. Dynamic Slash-Separated Series OR-Matching (e.g. 30 Sprinter / Powercon T3).
3. Marketplace Noise Purification (stripping sellers, installments, operational terms).
4. Strict Guarded Facets (Capacity 30 vs 15 block, T3 isolation, Tub WB vs GB isolation).
5. Color Optionality Rule (Conflicting color rejected, omitted color accepted).
"""


from pricing_engine.matcher import (
    clean_marketplace_noise,
    extract_search_query_and_model,
    generate_search_patterns,
    referee_match,
)


def test_leading_capacity_query_extraction_no_digit_repetition() -> None:
    """Ensure leading capacity codes do not repeat digits (e.g. no 'Dawlance 15 15')."""
    query, model = extract_search_query_and_model("15 Infinity Pro Fix Speed", brand="Dawlance")
    assert query == "Dawlance Infinity 15"
    assert "Infinity" in model
    assert "15" in model

    query30, model30 = extract_search_query_and_model("30 Infinity Pro Fix Speed", brand="Dawlance")
    assert query30 == "Dawlance Infinity 30"
    assert "Infinity" in model30
    assert "30" in model30


def test_slash_series_pattern_generation() -> None:
    """Ensure slash-separated series generates multi-tier queries for both alternatives."""
    patterns = generate_search_patterns("30 Sprinter / Powercon T3", brand="Dawlance")
    t1 = patterns["tier_1"]
    t2 = patterns["tier_2"]
    t3 = patterns["tier_3"]

    # Tier 1 should cover both Sprinter and Powercon with capacity 30
    assert any("Sprinter" in q and "30" in q for q in t1)
    assert any("Powercon" in q and "30" in q for q in t1)

    # Tier 2 should cover bare series names
    assert any("Sprinter" in q for q in t2)
    assert any("Powercon" in q for q in t2)

    # Tier 3 should cover 1.5 TON conversion
    assert any("1.5 TON" in q for q in t3)


def test_slash_series_referee_or_matching() -> None:
    """Ensure candidate matching either alternative in slash series is accepted."""
    target = "30 Sprinter / Powercon T3"

    # Match Sprinter alternative
    cand_sprinter = "Dawlance Sprinter 30 T3 Inverter 1.5 Ton AC - ElectroEase"
    dec_s = referee_match(target, cand_sprinter, brand="Dawlance")
    assert dec_s.is_match is True

    # Match Powercon alternative
    cand_powercon = "Dawlance Powercon 30 T3 Inverter 1.5 Ton AC"
    dec_p = referee_match(target, cand_powercon, brand="Dawlance")
    assert dec_p.is_match is True

    # Reject non-T3
    cand_non_t3 = "Dawlance Sprinter 30 Inverter 1.5 Ton AC - ElectroEase"
    dec_non_t3 = referee_match(target, cand_non_t3, brand="Dawlance")
    assert dec_non_t3.is_match is False
    assert "T3 mismatch" in dec_non_t3.reason


def test_color_optionality_and_parentheses_cleaning() -> None:
    """Ensure catalog parenthetical colors are extracted, noise is stripped, and unmentioned color is accepted."""
    target = "30 Magna T3 INV (Milky White Textured)"

    # Candidate omits color entirely -> MUST ACCEPT
    cand_no_color = "Dawlance Magna 30 T3 Inverter AC - HomeCart"
    dec_accept = referee_match(target, cand_no_color, brand="Dawlance")
    assert dec_accept.is_match is True

    # Candidate has conflicting color (Silver) -> MUST REJECT
    cand_silver = "Dawlance Magna 30 T3 Inverter AC Silver"
    dec_reject_color = referee_match(target, cand_silver, brand="Dawlance")
    assert dec_reject_color.is_match is False
    assert "Color collision" in dec_reject_color.reason


def test_capacity_mismatch_strictly_rejected() -> None:
    """Ensure capacity code 30 strictly rejects 15 (1.5 Ton vs 1.0 Ton)."""
    target = "30 Magna T3 INV (Milky White Textured)"
    cand_15 = "Dawlance Magna 15 T3 Inverter AC"
    dec = referee_match(target, cand_15, brand="Dawlance")
    assert dec.is_match is False
    assert "Capacity / screen size mismatch" in dec.reason


def test_sub_series_collision_guard() -> None:
    """Ensure genuine sub-series tokens (Pro, Plus, Max) trigger collisions while noise does not."""
    target = "15 Infinity Pro Fix Speed"

    # Exact sub-series match with operational noise -> MUST ACCEPT
    cand_pro = "Dawlance 15 Infinity Pro Fixed Speed AC - On Installment 0% Markup"
    dec_pro = referee_match(target, cand_pro, brand="Dawlance")
    assert dec_pro.is_match is True

    # Missing sub-series 'Pro' -> MUST REJECT
    cand_base = "Dawlance 15 Infinity Fixed Speed AC"
    dec_base = referee_match(target, cand_base, brand="Dawlance")
    assert dec_base.is_match is False
    assert "Missing required series tokens" in dec_base.reason


def test_glued_sku_anchor_matching() -> None:
    """Ensure glued model numbers like DWT11467ES match hyphenated and spaced marketplace listings."""
    target = "AWM DWT11467ES"

    # Hyphenated listing with vendor noise
    cand_hyphen = "Dawlance DWT-11467 ES Automatic Washing Machine - ElectroEase"
    dec_hyphen = referee_match(target, cand_hyphen, brand="Dawlance")
    assert dec_hyphen.is_match is True

    # Spaced listing with brand
    cand_spaced = "Dawlance 11467 ES Washing Machine"
    dec_spaced = referee_match(target, cand_spaced, brand="Dawlance")
    assert dec_spaced.is_match is True

    # Wrong numeric model code (11465 vs 11467) -> MUST REJECT
    cand_wrong = "Dawlance DWT-11465 ES Washing Machine"
    dec_wrong = referee_match(target, cand_wrong, brand="Dawlance")
    assert dec_wrong.is_match is False
    assert "Anchor model mismatch" in dec_wrong.reason


def test_hardware_tub_wb_vs_gb_isolation() -> None:
    """Ensure Glass Lid (GB) strictly rejects Plastic Window (WB)."""
    target = "DW 10095 GB Twin Tub Black Lid"

    # Matching GB
    cand_gb = "Dawlance DW-10095 GB Twin Tub Washing Machine"
    assert referee_match(target, cand_gb, brand="Dawlance").is_match is True

    # Mismatching WB
    cand_wb = "Dawlance DW-10095 WB Twin Tub Washing Machine"
    dec_wb = referee_match(target, cand_wb, brand="Dawlance")
    assert dec_wb.is_match is False
    assert "Hardware tub mismatch" in dec_wb.reason


def test_marketplace_noise_cleaner() -> None:
    """Verify clean_marketplace_noise strips seller tags, delivery, payment terms, and HVAC tags."""
    raw = "Dawlance AC 1.5 Ton On Installment 0% Markup Free Delivery ElectroEase ISPK-991 Heat & Cool"
    cleaned = clean_marketplace_noise(raw)
    assert "Installment" not in cleaned
    assert "0% Markup" not in cleaned
    assert "Free Delivery" not in cleaned
    assert "ElectroEase" not in cleaned
    assert "ISPK-991" not in cleaned
    assert "Heat & Cool" not in cleaned
````

## File: tests/test_db.py
````python
import asyncio
from unittest.mock import AsyncMock, MagicMock

from pricing_engine.db import SupabaseClient


def test_supabase_client_unconfigured_graceful_fallback() -> None:
    """When credentials are not set, client should not crash and return empty defaults."""

    async def _test() -> None:
        client = SupabaseClient(url="", key="")
        assert client.is_configured is False

        capacities = await client.fetch_approved_capacities()
        assert capacities == []

        synonyms = await client.fetch_approved_synonyms()
        assert synonyms == []

        recorded = await client.record_observations_batch(
            [
                {
                    "brand": "Haier",
                    "category": "WASHING_MACHINE",
                    "anchor_model": "120-826S6",
                    "target_residual": "GC",
                    "candidate_residual": "GLASS DOOR",
                    "vendor_name": "Vendor A",
                    "normalized_merchant": "vendora",
                    "raw_title": "Haier 120-826S6 Glass Door",
                }
            ]
        )
        assert recorded == 0

    asyncio.run(_test())


def test_supabase_client_fetches_approved_capacities() -> None:
    """When configured, client calls Supabase REST endpoint for capacity registry."""

    async def _test() -> None:
        client = SupabaseClient(url="https://mock.supabase.co", key="mock-anon-key")
        assert client.is_configured is True

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"brand": "DAWLANCE", "code": "30", "tonnage": "1.5", "status": "APPROVED"}
        ]

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp
        client._session = mock_session

        caps = await client.fetch_approved_capacities(brand="Dawlance")
        assert len(caps) == 1
        assert caps[0]["code"] == "30"
        assert mock_session.get.call_count == 1
        url_called = mock_session.get.call_args[0][0]
        assert "capacity_registry" in url_called
        assert "brand=eq.DAWLANCE" in url_called

    asyncio.run(_test())


def test_supabase_client_fetches_approved_synonyms_with_category_isolation() -> None:
    """Client filters synonyms by both brand and category to maintain category isolation."""

    async def _test() -> None:
        client = SupabaseClient(url="https://mock.supabase.co", key="mock-anon-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "brand": "HAIER",
                "category": "WASHING_MACHINE",
                "tag": "GC",
                "alias": "GLASS DOOR",
                "status": "APPROVED",
            }
        ]

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp
        client._session = mock_session

        syns = await client.fetch_approved_synonyms(brand="Haier", category="Washing_Machine")
        assert len(syns) == 1
        assert syns[0]["tag"] == "GC"
        url_called = mock_session.get.call_args[0][0]
        assert "synonym_registry" in url_called
        assert "category=eq.WASHING_MACHINE" in url_called

    asyncio.run(_test())


def test_supabase_client_batch_records_observations_without_n_plus_one() -> None:
    """Client posts batch observation payload in a single HTTP POST request."""

    async def _test() -> None:
        client = SupabaseClient(url="https://mock.supabase.co", key="mock-anon-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = [{"id": "1"}, {"id": "2"}]

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_resp
        client._session = mock_session

        batch = [
            {
                "brand": "HAIER",
                "category": "WASHING_MACHINE",
                "anchor_model": "120-826S6",
                "target_residual": "GC",
                "candidate_residual": "GLASS DOOR",
                "vendor_name": "Vendor A",
                "normalized_merchant": "vendora",
                "raw_title": "Haier 120-826S6 Glass Door",
            },
            {
                "brand": "HAIER",
                "category": "WASHING_MACHINE",
                "anchor_model": "120-826S6",
                "target_residual": "GC",
                "candidate_residual": "GLASS COVER",
                "vendor_name": "Vendor B",
                "normalized_merchant": "vendorb",
                "raw_title": "Haier 120-826S6 Glass Cover",
            },
        ]

        recorded = await client.record_observations_batch(batch)
        assert recorded == 2
        assert mock_session.post.call_count == 1
        post_args = mock_session.post.call_args
        assert "learning_observations" in post_args[0][0]
        assert len(post_args[1]["json"]) == 2
        assert post_args[1]["headers"]["Prefer"] == "resolution=ignore-duplicates"

    asyncio.run(_test())


def test_supabase_client_handles_network_error_gracefully() -> None:
    """When network raises exception, client catches it and returns empty results."""

    async def _test() -> None:
        client = SupabaseClient(url="https://mock.supabase.co", key="mock-anon-key")

        mock_session = AsyncMock()
        mock_session.get.side_effect = RuntimeError("Connection refused")
        mock_session.post.side_effect = RuntimeError("Connection timeout")
        client._session = mock_session

        assert await client.fetch_approved_capacities() == []
        assert await client.fetch_approved_synonyms() == []
        assert await client.record_observations_batch([{"dummy": "data"}]) == 0

    asyncio.run(_test())
````

## File: tests/test_exporter.py
````python
"""Tests for exporter module and timestamped catalog management."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from pricing_engine.exporter import (
    ExportManifest,
    export_results,
    format_export_price,
)


def test_format_export_price() -> None:
    assert format_export_price(147000) == "147000"
    assert format_export_price(147000.0) == "147000"
    assert format_export_price("147,000") == "147000"
    assert format_export_price(None) == ""
    assert format_export_price(float("nan")) == ""
    assert format_export_price("NaN") == ""
    assert format_export_price("") == ""


def test_export_results_creates_both_files_and_dir(tmp_path: Path) -> None:
    out_dir = tmp_path / "custom_outputs"
    assert not out_dir.exists()

    df = pd.DataFrame(
        {
            "Brand": ["Gree", "Gree"],
            "Name": ["Gree AC 1", "Gree AC 2"],
            "Final Price Alfa": [147000.0, 183000.0],
            "Final Price Digi": [145000.0, float("nan")],
            "Alfa Real Profit": [4500.0, 5200.0],
        }
    )

    fixed_dt = datetime(2026, 9, 30, 13, 30, 15)
    manifest = export_results(
        df=df,
        source_filename="Gree_AC.csv",
        output_dir=out_dir,
        timestamp=fixed_dt,
        render_panel=False,
    )

    assert isinstance(manifest, ExportManifest)
    assert out_dir.is_dir()
    assert manifest.timestamp == "20260930_133015"
    assert manifest.total_rows == 2

    expected_ts_file = out_dir / "Gree_AC_repriced_20260930_133015.csv"
    expected_latest_file = out_dir / "Gree_AC_repriced_latest.csv"

    assert manifest.timestamped_path == expected_ts_file
    assert manifest.latest_path == expected_latest_file

    assert expected_ts_file.is_file()
    assert expected_latest_file.is_file()

    # Content of both files must be identical
    ts_content = expected_ts_file.read_text(encoding="utf-8")
    latest_content = expected_latest_file.read_text(encoding="utf-8")
    assert ts_content == latest_content

    # Check pure integer formatting (no .0 drift)
    loaded_df = pd.read_csv(expected_latest_file, dtype=str)
    assert loaded_df["Final Price Alfa"].iloc[0] == "147000"
    assert loaded_df["Final Price Alfa"].iloc[1] == "183000"
    assert loaded_df["Final Price Digi"].iloc[0] == "145000"
    # NaN price should be empty string
    assert pd.isna(loaded_df["Final Price Digi"].iloc[1]) or loaded_df["Final Price Digi"].iloc[1] == ""


def test_export_results_handles_existing_repriced_suffix(tmp_path: Path) -> None:
    out_dir = tmp_path / "outputs"
    df = pd.DataFrame({"Brand": ["Haier"]})

    manifest = export_results(
        df=df,
        source_filename="Haier_Washers_repriced.csv",
        output_dir=out_dir,
        timestamp=datetime(2026, 9, 30, 12, 0, 0),
        render_panel=False,
    )

    assert manifest.timestamped_path.name == "Haier_Washers_repriced_20260930_120000.csv"
    assert manifest.latest_path.name == "Haier_Washers_repriced_latest.csv"
````

## File: tests/test_registry.py
````python
import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from pricing_engine.registry import InMemoryRegistry


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    InMemoryRegistry.reset_to_defaults()


def test_registry_seed_defaults_are_available_immediately() -> None:
    """Registry should contain standard seed capacities and synonyms right out of the box."""
    # Universal AC
    assert InMemoryRegistry.get_tonnage(code="18", brand="Gree") == "1.5"
    assert InMemoryRegistry.get_tonnage(code="24", brand="Haier") == "2"

    # Dawlance AC custom codes
    assert InMemoryRegistry.get_tonnage(code="10", brand="Dawlance") == "0.75"
    assert InMemoryRegistry.get_tonnage(code="15", brand="Dawlance") == "1"
    assert InMemoryRegistry.get_tonnage(code="30", brand="Dawlance") == "1.5"

    # Seed synonyms for Haier washing machine
    assert (
        InMemoryRegistry.get_canonical_tag(
            alias="GLASS DOOR", brand="Haier", category="WASHING_MACHINE"
        )
        == "GC"
    )
    assert InMemoryRegistry.are_synonyms(
        "GC", "GLASS DOOR", brand="Haier", category="WASHING_MACHINE"
    )


def test_registry_lookup_latency_is_under_microsecond() -> None:
    """RAM cache lookup must execute in < 0.01ms to ensure zero matching latency."""
    start = time.perf_counter()
    for _ in range(10_000):
        _ = InMemoryRegistry.get_tonnage("30", "Dawlance")
        _ = InMemoryRegistry.are_synonyms(
            "GC", "GLASS DOOR", brand="Haier", category="WASHING_MACHINE"
        )
    duration = time.perf_counter() - start
    avg_call_ms = (duration / 20_000) * 1000
    assert avg_call_ms < 0.01, f"Lookup took {avg_call_ms:.5f}ms, expected <0.01ms"


def test_registry_load_from_db_merges_cloud_knowledge() -> None:
    """load_from_db asynchronously fetches from SupabaseClient and populates RAM cache."""

    async def _test() -> None:
        mock_client = AsyncMock()
        mock_client.is_configured = True
        # Future code '14' -> 1.0 Ton learned from market
        mock_client.fetch_approved_capacities.return_value = [
            {"brand": "DAWLANCE", "code": "14", "tonnage": "1.0", "status": "APPROVED"}
        ]
        mock_client.fetch_approved_synonyms.return_value = [
            {
                "brand": "DAWLANCE",
                "category": "AIR_CONDITIONER",
                "tag": "CHROME",
                "alias": "CHROME PRO",
                "status": "APPROVED",
            }
        ]

        await InMemoryRegistry.load_from_db(mock_client)

        # Discovered code '14' is now instantly available in RAM!
        assert InMemoryRegistry.get_tonnage(code="14", brand="Dawlance") == "1.0"
        assert InMemoryRegistry.are_synonyms(
            "CHROME", "CHROME PRO", brand="Dawlance", category="AIR_CONDITIONER"
        )

    asyncio.run(_test())


def test_registry_hot_reload_without_restart() -> None:
    """hot_reload updates RAM cache dynamically in-place."""
    assert InMemoryRegistry.get_tonnage("99", "Dawlance") is None

    InMemoryRegistry.hot_reload(
        new_capacities=[{"brand": "DAWLANCE", "code": "99", "tonnage": "5.0"}]
    )

    assert InMemoryRegistry.get_tonnage("99", "Dawlance") == "5.0"


def test_registry_category_isolation_prevents_cross_contamination() -> None:
    """GC in Washing Machine must NOT be considered synonym in Refrigerator or AC."""
    # In Washing Machine, GC == GLASS DOOR
    assert InMemoryRegistry.are_synonyms(
        "GC", "GLASS DOOR", brand="Haier", category="WASHING_MACHINE"
    )
    # In Refrigerator, GC is NOT Glass Door (Category-bounded isolation!)
    assert not InMemoryRegistry.are_synonyms(
        "GC", "GLASS DOOR", brand="Haier", category="REFRIGERATOR"
    )
````

## File: requirements.txt
````
curl_cffi>=0.7.0
pandas>=2.0.0
rich>=13.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
mypy>=1.9.0
ruff>=0.3.0
````

## File: pricing_engine/exporter.py
````python
"""Timestamped Output Manager for Repriced Catalogs.

Handles saving repriced DataFrames to structured directories with
timestamps and maintaining an always-current latest copy.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

PRICE_INT_COLUMNS: list[str] = [
    "Total Without Profit",
    "Calculation",
    "Minimum Price Alfa",
    "Maximum Price Alfa",
    "Minimum Price Digi",
    "Maximum Price Digi",
    "Final Price Alfa",
    "Final Price Digi",
    "Alfa Real Profit",
    "Digi Real Profit",
]


def format_export_price(val: Any) -> str:
    """Format integer price values for CSV export without float drift (.0) or empty on None/NaN.

    Args:
        val: Numeric, None, or NaN price value.

    Returns:
        Pure integer string (e.g. '165000') or empty string '' if None/NaN.
    """
    if val is None or pd.isna(val):
        return ""
    try:
        clean = str(val).replace(",", "").strip()
        if not clean or clean.lower() == "nan" or clean.lower() == "none":
            return ""
        return str(int(round(float(clean))))
    except (ValueError, TypeError):
        return ""


def format_export_sno(val: Any) -> str:
    """Format S.NO value without float drift (.0) while preserving string identifiers.

    Args:
        val: Numeric, string, None, or NaN serial number.

    Returns:
        Clean string representation without decimal point if integer-equivalent.
    """
    if val is None or pd.isna(val):
        return ""
    try:
        f = float(val)
        if f.is_integer():
            return str(int(f))
    except (ValueError, TypeError):
        pass
    return str(val).strip()


@dataclass(frozen=True, slots=True)
class ExportManifest:
    """Manifest describing exported catalog artifacts."""

    timestamped_path: Path
    latest_path: Path
    timestamp: str
    total_rows: int


def render_export_panel(manifest: ExportManifest) -> None:
    """Render a clean Rich finish panel with output file paths."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column(style="green")

    table.add_row("Timestamped Audit:", str(manifest.timestamped_path))
    table.add_row("Latest Upload Ready:", str(manifest.latest_path))
    table.add_row("Rows Exported:", str(manifest.total_rows))
    table.add_row("Generated At:", manifest.timestamp)

    panel = Panel(
        table,
        title="[bold green]💾 Catalog Repricing Exported[/bold green]",
        border_style="green",
        expand=False,
    )
    console.print(panel)


def export_results(
    df: pd.DataFrame,
    source_filename: str | Path,
    output_dir: str | Path = "data/outputs",
    timestamp: datetime | None = None,
    render_panel: bool = True,
) -> ExportManifest:
    """Format and export results DataFrame to timestamped and latest CSV files.

    Args:
        df: Processed DataFrame containing repricing results.
        source_filename: Source catalog name/path used to derive output stem.
        output_dir: Target directory where outputs should be saved.
        timestamp: Optional explicit datetime (defaults to datetime.now()).
        render_panel: If True, prints Rich finish panel.

    Returns:
        ExportManifest with paths to generated files.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dt = timestamp or datetime.now()
    ts_str = dt.strftime("%Y%m%d_%H%M%S")

    stem = Path(source_filename).stem
    if stem.endswith("_repriced_latest"):
        stem = stem[: -len("_repriced_latest")]
    elif stem.endswith("_repriced"):
        stem = stem[: -len("_repriced")]

    timestamped_filename = f"{stem}_repriced_{ts_str}.csv"
    latest_filename = f"{stem}_repriced_latest.csv"

    timestamped_path = out_dir / timestamped_filename
    latest_path = out_dir / latest_filename

    export_df = df.copy()
    if "S.NO" in export_df.columns:
        export_df["S.NO"] = export_df["S.NO"].apply(format_export_sno)

    for col in PRICE_INT_COLUMNS:
        if col in export_df.columns:
            export_df[col] = export_df[col].apply(format_export_price)

    export_df.to_csv(timestamped_path, index=False)
    shutil.copyfile(timestamped_path, latest_path)

    manifest = ExportManifest(
        timestamped_path=timestamped_path,
        latest_path=latest_path,
        timestamp=ts_str,
        total_rows=len(export_df),
    )

    if render_panel:
        render_export_panel(manifest)

    return manifest
````

## File: pricing_engine/registry.py
````python
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Base Seed Fallback Maps (Used for cold starts and offline mode)
_SEED_DAWLANCE_CAPACITIES: dict[str, str] = {
    "10": "0.75",
    "15": "1",
    "20": "1.25",
    "30": "1.5",
    "45": "2",
}

_SEED_UNIVERSAL_CAPACITIES: dict[str, str] = {
    "09": "0.75",
    "9": "0.75",
    "12": "1",
    "18": "1.5",
    "24": "2",
    "28": "2.5",
    "30": "2.5",
    "36": "3",
    "48": "4",
}

_SEED_SYNONYMS: list[tuple[str, str, str, str]] = [
    # (Brand, Category, Tag, Alias)
    ("HAIER", "WASHING_MACHINE", "GC", "GLASS DOOR"),
    ("HAIER", "WASHING_MACHINE", "GC", "GLASS COVER"),
    ("HAIER", "WASHING_MACHINE", "PL", "PILLOW DRUM"),
]


class InMemoryRegistry:
    """Zero-latency in-memory registry mirror of Supabase Cloud knowledge.

    Features (ADR-003):
    - Sub-microsecond RAM lookups (<0.01ms).
    - Category-bounded isolation preventing polysemic synonym collisions.
    - Zero network I/O during core matching loop.
    - Dynamic hot-reloading without process restarts.
    """

    # Primary RAM Caches
    # (brand, code) -> tonnage
    _capacity_cache: dict[tuple[str, str], str] = {}
    # (brand, category, alias) -> tag
    _alias_to_tag: dict[tuple[str, str, str], str] = {}
    # (brand, category, tag) -> set of aliases
    _tag_to_aliases: dict[tuple[str, str, str], set[str]] = {}

    _is_initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        if not cls._is_initialized:
            cls.reset_to_defaults()

    @classmethod
    def reset_to_defaults(cls) -> None:
        """Reset in-memory cache to standard verified seed defaults."""
        cls._capacity_cache.clear()
        cls._alias_to_tag.clear()
        cls._tag_to_aliases.clear()

        # Seed Dawlance capacities
        for code, ton in _SEED_DAWLANCE_CAPACITIES.items():
            cls._capacity_cache[("DAWLANCE", code.upper())] = ton
            cls._capacity_cache[("DAW", code.upper())] = ton

        # Seed Universal capacities
        for code, ton in _SEED_UNIVERSAL_CAPACITIES.items():
            cls._capacity_cache[("UNIVERSAL", code.upper())] = ton

        # Seed Synonyms
        for brand, cat, tag, alias in _SEED_SYNONYMS:
            b_u, c_u, t_u, a_u = brand.upper(), cat.upper(), tag.upper(), alias.upper()
            cls._alias_to_tag[(b_u, c_u, a_u)] = t_u
            cls._tag_to_aliases.setdefault((b_u, c_u, t_u), set()).add(a_u)

        cls._is_initialized = True

    @classmethod
    async def load_from_db(cls, client: Any) -> None:
        """Asynchronously load approved knowledge from Supabase REST client."""
        cls._ensure_initialized()
        if not client or not getattr(client, "is_configured", False):
            return

        try:
            # 1. Fetch approved capacities
            capacities = await client.fetch_approved_capacities()
            if capacities:
                cls.hot_reload(new_capacities=capacities)

            # 2. Fetch approved synonyms
            synonyms = await client.fetch_approved_synonyms()
            if synonyms:
                cls.hot_reload(new_synonyms=synonyms)

            logger.info(
                "InMemoryRegistry successfully synced from Supabase: %d capacities, %d synonyms",
                len(capacities),
                len(synonyms),
            )
        except Exception as exc:
            logger.warning("InMemoryRegistry sync from Supabase failed gracefully: %s", exc)

    @classmethod
    def hot_reload(
        cls,
        new_capacities: list[dict[str, Any]] | None = None,
        new_synonyms: list[dict[str, Any]] | None = None,
    ) -> None:
        """In-place atomic update of RAM cache without process restart."""
        cls._ensure_initialized()

        if new_capacities:
            for item in new_capacities:
                brand = str(item.get("brand", "")).strip().upper()
                code = str(item.get("code", "")).strip().upper()
                tonnage = str(item.get("tonnage", "")).strip()
                if brand and code and tonnage:
                    cls._capacity_cache[(brand, code)] = tonnage
                    if brand == "DAWLANCE":
                        cls._capacity_cache[("DAW", code)] = tonnage

        if new_synonyms:
            for item in new_synonyms:
                brand = str(item.get("brand", "")).strip().upper()
                category = str(item.get("category", "")).strip().upper()
                tag = str(item.get("tag", "")).strip().upper()
                alias = str(item.get("alias", "")).strip().upper()
                if brand and category and tag and alias:
                    cls._alias_to_tag[(brand, category, alias)] = tag
                    cls._tag_to_aliases.setdefault((brand, category, tag), set()).add(alias)

    @classmethod
    def get_tonnage(cls, code: str, brand: str = "") -> str | None:
        """Resolve AC tonnage for a capacity code in <0.01ms from RAM."""
        cls._ensure_initialized()
        c_u = code.strip().upper()
        b_u = brand.strip().upper()

        if b_u:
            # 1. Check brand-specific entry
            ton = cls._capacity_cache.get((b_u, c_u))
            if ton:
                return ton
            if b_u.startswith("DAW"):
                ton = cls._capacity_cache.get(("DAWLANCE", c_u))
                if ton:
                    return ton

        # 2. Check Universal brand entry
        ton = cls._capacity_cache.get(("UNIVERSAL", c_u))
        if ton:
            return ton

        # 3. Brand-unknown fallback: check Dawlance first if code is distinctive
        if c_u in ("10", "15", "20", "45"):
            return cls._capacity_cache.get(("DAWLANCE", c_u))

        return None

    @classmethod
    def get_canonical_tag(cls, alias: str, brand: str = "", category: str = "") -> str | None:
        """Resolve canonical tag for an observed alias token in <0.01ms from RAM."""
        cls._ensure_initialized()
        a_u = alias.strip().upper()
        b_u = brand.strip().upper()
        c_u = category.strip().upper()

        return cls._alias_to_tag.get((b_u, c_u, a_u))

    @classmethod
    def are_synonyms(cls, token1: str, token2: str, brand: str = "", category: str = "") -> bool:
        """Determine if two tokens are equivalent within (brand, category) bounds in <0.01ms."""
        cls._ensure_initialized()
        t1 = token1.strip().upper()
        t2 = token2.strip().upper()

        if t1 == t2:
            return True

        b_u = brand.strip().upper()
        c_u = category.strip().upper()

        # Check if t1 is tag and t2 is registered alias
        aliases_for_t1 = cls._tag_to_aliases.get((b_u, c_u, t1), set())
        if t2 in aliases_for_t1:
            return True

        # Check if t2 is tag and t1 is registered alias
        aliases_for_t2 = cls._tag_to_aliases.get((b_u, c_u, t2), set())
        if t1 in aliases_for_t2:
            return True

        # Check if both resolve to the same canonical tag
        tag1 = cls._alias_to_tag.get((b_u, c_u, t1))
        tag2 = cls._alias_to_tag.get((b_u, c_u, t2))
        return bool(tag1 and tag2 and tag1 == tag2)
````

## File: scripts/setup_supabase.sql
````sql
-- Supabase Cloud PostgreSQL Schema: Autonomous Graph Memory & Learning Registry
-- Enterprise Dynamic Repricing Engine (Category-Bounded & Sybil-Guarded)

-- 1. Capacity Registry
-- Maps brand-specific cooling/washing capacity codes to standardized units (e.g. Dawlance 30 -> 1.5T)
CREATE TABLE IF NOT EXISTS capacity_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand VARCHAR(64) NOT NULL,
    code VARCHAR(32) NOT NULL,
    tonnage VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'APPROVED', -- 'APPROVED', 'CANDIDATE', 'QUARANTINED'
    occurrences INT NOT NULL DEFAULT 1,
    confidence NUMERIC(4, 3) NOT NULL DEFAULT 1.000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_capacity_brand_code UNIQUE (brand, code)
);

CREATE INDEX IF NOT EXISTS idx_capacity_lookup ON capacity_registry (brand, code);
CREATE INDEX IF NOT EXISTS idx_capacity_status ON capacity_registry (status);

-- 2. Synonym Registry (Reviewer Guard 1: Strict Category-Bounded Polysemy Isolation)
-- Discovered equivalence pairs (e.g. 'GC' <=> 'Glass Door') bounded to (brand, category)
CREATE TABLE IF NOT EXISTS synonym_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand VARCHAR(64) NOT NULL,
    category VARCHAR(64) NOT NULL,
    tag VARCHAR(64) NOT NULL,
    alias VARCHAR(128) NOT NULL,
    occurrences INT NOT NULL DEFAULT 1,
    distinct_vendors INT NOT NULL DEFAULT 1,
    status VARCHAR(32) NOT NULL DEFAULT 'CANDIDATE', -- 'APPROVED', 'CANDIDATE', 'CONFLICT'
    confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.500,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_synonym_pair UNIQUE (brand, category, tag, alias)
);

CREATE INDEX IF NOT EXISTS idx_synonym_lookup ON synonym_registry (brand, category, tag);
CREATE INDEX IF NOT EXISTS idx_synonym_status ON synonym_registry (status);

-- 3. Learning Observations (Reviewer Guards 1, 2, 3: Sybil Protection & Normalization)
-- Append-only raw market observation audit log with normalized merchant uniqueness constraint
CREATE TABLE IF NOT EXISTS learning_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand VARCHAR(64) NOT NULL,
    category VARCHAR(64) NOT NULL,
    anchor_model VARCHAR(64) NOT NULL DEFAULT '',
    target_residual VARCHAR(64) NOT NULL,
    candidate_residual VARCHAR(128) NOT NULL,
    vendor_name VARCHAR(128) NOT NULL,
    normalized_merchant VARCHAR(64) NOT NULL,
    raw_title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_merchant_observation UNIQUE (brand, category, anchor_model, target_residual, candidate_residual, normalized_merchant)
);

CREATE INDEX IF NOT EXISTS idx_obs_distinct_vendors ON learning_observations (brand, category, target_residual, candidate_residual);
CREATE INDEX IF NOT EXISTS idx_obs_anchor ON learning_observations (brand, anchor_model);

-- 4. Seed Canonical Seed Capacities (Idempotent Upsert)
INSERT INTO capacity_registry (brand, code, tonnage, status, occurrences, confidence) VALUES
    ('DAWLANCE', '10', '0.75', 'APPROVED', 10, 1.000),
    ('DAWLANCE', '15', '1', 'APPROVED', 10, 1.000),
    ('DAWLANCE', '20', '1.25', 'APPROVED', 10, 1.000),
    ('DAWLANCE', '30', '1.5', 'APPROVED', 10, 1.000),
    ('DAWLANCE', '45', '2', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '09', '0.75', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '9', '0.75', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '12', '1', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '18', '1.5', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '24', '2', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '28', '2.5', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '30', '2.5', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '36', '3', 'APPROVED', 10, 1.000),
    ('UNIVERSAL', '48', '4', 'APPROVED', 10, 1.000)
ON CONFLICT (brand, code) DO NOTHING;

-- 5. Seed Canonical Seed Synonyms (Idempotent Upsert)
INSERT INTO synonym_registry (brand, category, tag, alias, occurrences, distinct_vendors, status, confidence) VALUES
    ('HAIER', 'WASHING_MACHINE', 'GC', 'GLASS DOOR', 5, 5, 'APPROVED', 1.000),
    ('HAIER', 'WASHING_MACHINE', 'GC', 'GLASS COVER', 5, 5, 'APPROVED', 1.000),
    ('HAIER', 'WASHING_MACHINE', 'PL', 'PILLOW DRUM', 5, 5, 'APPROVED', 1.000)
ON CONFLICT (brand, category, tag, alias) DO NOTHING;

-- 6. Enable Row Level Security (RLS)
ALTER TABLE capacity_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE synonym_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_observations ENABLE ROW LEVEL SECURITY;

-- 7. RLS Policies for service_role and anon/authenticated
DO $$
BEGIN
    DROP POLICY IF EXISTS "Allow public read on approved capacity" ON capacity_registry;
    DROP POLICY IF EXISTS "Allow public read on approved synonyms" ON synonym_registry;
    DROP POLICY IF EXISTS "Allow service_role all on capacity" ON capacity_registry;
    DROP POLICY IF EXISTS "Allow service_role all on synonyms" ON synonym_registry;
    DROP POLICY IF EXISTS "Allow service_role all on observations" ON learning_observations;
    DROP POLICY IF EXISTS "Allow public insert on observations" ON learning_observations;
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

CREATE POLICY "Allow public read on approved capacity" ON capacity_registry
    FOR SELECT USING (status = 'APPROVED');

CREATE POLICY "Allow public read on approved synonyms" ON synonym_registry
    FOR SELECT USING (status = 'APPROVED');

CREATE POLICY "Allow service_role all on capacity" ON capacity_registry
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Allow service_role all on synonyms" ON synonym_registry
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Allow service_role all on observations" ON learning_observations
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- SECURITY NOTICE (Principle of Least Privilege & STRIDE Hardening):
-- 1. `learning_observations` is an internal telemetry and model-learning ledger.
--    No public (anon) access is permitted. Only `service_role` (backend engine)
--    can read, insert, or prune observation records.
-- 2. `capacity_registry` and `synonym_registry` permit public SELECT ONLY for
--    pre-approved entries (`status = 'APPROVED'`). All mutations require `service_role`.
-- ============================================================================
````

## File: scripts/test_supabase_connection.py
````python
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.panel import Panel

from pricing_engine.db import SupabaseClient

console = Console(legacy_windows=False)


async def check_connection() -> None:
    console.print(Panel("[bold cyan]Supabase Cloud Connection Diagnostic[/]", expand=False))

    client = SupabaseClient()

    if not client.is_configured:
        console.print(
            "\n[bold yellow]⚠️  Supabase is NOT configured yet.[/]\n"
            "[dim]The engine is currently running in [bold green]Offline Graceful Fallback Mode[/] using verified in-memory seed defaults.[/]\n\n"
            "[bold white]To connect your live Supabase database:[/]\n"
            "1. Copy [cyan].env.example[/] to [cyan].env[/]\n"
            "2. Paste your [bold]SUPABASE_URL[/] and [bold]SUPABASE_KEY[/]\n"
            "3. Run the schema in [cyan]scripts/setup_supabase.sql[/] in the Supabase SQL Editor\n"
            "4. Re-run this script: [green]python scripts/test_supabase_connection.py[/]\n"
        )
        return

    session = client._ensure_session()
    try:
        resp = await session.get(
            f"{client.url}/rest/v1/capacity_registry?select=*&status=eq.APPROVED",
            headers=client._headers(),
            timeout=client.timeout,
        )
    except Exception as exc:
        console.print(f"\n[bold red]❌ Network Connection Failed:[/] {exc}")
        return

    if resp.status_code == 401:
        console.print(
            "\n[bold red]❌ Authentication Failed (HTTP 401 - Invalid API key)![/]\n"
            "[yellow]Supabase REST API ne is key ko reject kar diya hai.[/]\n\n"
            "[bold white]Asal API Key Kahan se Milegi:[/]\n"
            "1. Supabase Dashboard mein [cyan]Project Settings (⚙️) -> API[/] par jayein.\n"
            "2. [bold]Project API keys[/] section mein jayein.\n"
            "3. [bold green]anon (public)[/] ya [bold yellow]service_role[/] key copy karein (jo [bold]eyJhbGci...[/] se shuru hoti hai).\n"
            "4. Apni [cyan].env[/] file mein [bold]SUPABASE_KEY=eyJ...[/] paste karein.\n"
        )
        return

    if resp.status_code == 404:
        console.print(
            "\n[bold yellow]⚠️  API Key Valid hai, lekin Tables nahi mile (HTTP 404)![/]\n"
            "[dim]Aap ne abhi tak SQL schema run nahi kiya.[/]\n\n"
            "[bold white]Fix:[/]\n"
            "1. Supabase Dashboard mein [cyan]SQL Editor[/] kholen.\n"
            "2. [cyan]scripts/setup_supabase.sql[/] ka code paste kar ke [bold]RUN[/] dabayein.\n"
        )
        return

    capacities = await client.fetch_approved_capacities()
    synonyms = await client.fetch_approved_synonyms()

    console.print(f"  • Approved Capacity Codes fetched: [bold green]{len(capacities)}[/]")
    console.print(f"  • Approved Synonym Pairs fetched:  [bold green]{len(synonyms)}[/]")

    console.print("\n[bold green]✅ Successfully connected to live Supabase Cloud PostgreSQL![/]\n")


if __name__ == "__main__":
    asyncio.run(check_connection())
````

## File: tests/test_haier_benchmark.py
````python
"""Haier benchmark test suite for multi-stage search, deduplication, and referee matching.

Validates the resolution of 25 benchmark models that previously experienced SOLO/false monopolies:
1. Technical Compound Slashes (/DC, /AC, /Z):
   - 24 HE/DC, 48 CE/DC, Cassette 18 HE/DC contain /DC (Direct Current rating).
   - Must NEVER split into alternative series HE or DC.
2. Alternative Variant Slashes (OR Branches):
   - HRF-418 TIFG1U1/TIFB1U1 (IOT), HGL-25MXP8 / 25MXP9.
   - Must expand into Cartesian branches and match candidates from either branch.
3. Dynamic Brand-Initial Prefix Synthesis:
   - Bare catalog stems like 11lf, 13hfn under brand Haier match portal listings HRF-11LF, HSU-13HFN.
4. Asymmetric Negative Guards:
   - HAF 50 MB vs HAF 50 DB (variant collision).
   - COOL ONLY vs Heat & Cool (operating mode collision).
   - T3 vs non-T3, IoT vs non-IoT.
"""

from pricing_engine.matcher import (
    expand_cartesian_branches,
    generate_search_patterns,
    normalize_technical_slashes,
    referee_match,
)


def test_technical_slash_dc_never_splits_into_alternative_series() -> None:
    """Ensure /DC (Direct Current) is preserved as a compound code and never split into HE or DC series."""
    # 1. 24 HE/DC
    norm_24 = normalize_technical_slashes("24 HE/DC")
    assert "HE-DC" in norm_24 or "HEDC" in norm_24
    branches_24 = expand_cartesian_branches("24 HE/DC")
    assert len(branches_24) == 1
    assert "DC 24" not in branches_24[0]
    assert "HE 24" not in branches_24[0]

    # Search patterns must contain 24 and HE-DC together, NOT bare HE or DC
    p24 = generate_search_patterns("24 HE/DC", brand="Haier")
    t1_24 = p24["tier_1"]
    assert any("HE-DC" in q or "HEDC" in q or "24 HE" in q for q in t1_24)
    # Ensure neither tier_1 nor tier_2 has standalone "DC" as a series search
    assert not any(q.strip().upper() == "DC" or q.strip().upper() == "HAIER DC" for q in p24["tier_2"])

    # 2. 48 CE/DC
    norm_48 = normalize_technical_slashes("48 CE/DC")
    assert "CE-DC" in norm_48 or "CEDC" in norm_48
    branches_48 = expand_cartesian_branches("48 CE/DC")
    assert len(branches_48) == 1

    # 3. Cassette 18 HE/DC
    norm_c18 = normalize_technical_slashes("Cassette 18 HE/DC")
    assert "18 HE-DC" in norm_c18 or "18HE-DC" in norm_c18
    branches_c18 = expand_cartesian_branches("Cassette 18 HE/DC")
    assert len(branches_c18) == 1


def test_compound_slash_z_normalizes_to_hdz() -> None:
    """Ensure 24 HD/Z W normalizes to 24 HDZ W and does not split into Z series."""
    norm = normalize_technical_slashes("24 HD/Z W")
    assert "HDZ" in norm
    branches = expand_cartesian_branches("24 HD/Z W")
    assert len(branches) == 1
    assert "HDZ" in branches[0]


def test_alternative_slashes_expand_cartesian_branches() -> None:
    """Ensure true alternative model variants expand into independent branches."""
    # 1. Dual model refrigerator
    target_rf = "HRF-418 TIFG1U1/TIFB1U1 (IOT)"
    branches_rf = expand_cartesian_branches(target_rf)
    assert len(branches_rf) >= 2
    assert any("TIFG1U1" in b for b in branches_rf)
    assert any("TIFB1U1" in b for b in branches_rf)

    # 2. Dual model microwave oven
    target_mwo = "HGL-25MXP8 / 25MXP9"
    branches_mwo = expand_cartesian_branches(target_mwo)
    assert len(branches_mwo) >= 2
    assert any("25MXP8" in b for b in branches_mwo)
    assert any("25MXP9" in b for b in branches_mwo)


def test_haier_multi_pattern_generation_tiers() -> None:
    """Ensure Haier models generate comprehensive queries across all 3 tiers."""
    # 1. Bare alphanumeric refrigerator stem: 11lf
    p_11lf = generate_search_patterns("11lf", brand="Haier")
    assert any("11lf" in q.lower() for q in p_11lf["tier_1"])
    assert any("haier" in q.lower() for q in p_11lf["tier_1"])

    # 2. Microwave with spaced prefix: HMO-62 MX80
    p_mx80 = generate_search_patterns("HMO-62 MX80", brand="Haier")
    assert any("62" in q and "MX80" in q.upper() for q in p_mx80["tier_1"])

    # 3. Air fryer with separated variant: HAF 50 MB
    p_50mb = generate_search_patterns("HAF 50 MB", brand="Haier")
    assert any("50" in q and "MB" in q.upper() for q in p_50mb["tier_1"])


def test_haier_referee_dynamic_brand_initial_synthesis() -> None:
    """Ensure bare catalog stems match portal listings with Haier brand initial prefixes (HRF, HSU)."""
    # 11lf -> HRF-11LF
    dec_11lf = referee_match("11lf", "Haier HRF-11LF Refrigerator Direct Cool", brand="Haier")
    assert dec_11lf.is_match is True

    # 13hfn -> HSU-13HFN
    dec_13hfn = referee_match("13hfn", "Haier Inverter Air Conditioner 1 Ton HSU-13HFN", brand="Haier")
    assert dec_13hfn.is_match is True


def test_haier_referee_dc_compound_ac_matching() -> None:
    """Ensure candidate listings with HE/DC, CE/DC, HDZ match cleanly without false monopoly."""
    # Cassette 18 HE/DC
    dec_c18 = referee_match(
        "Cassette 18 HE/DC",
        "Haier Cassette 1.5 Ton Inverter 18HE/DC AC",
        brand="Haier",
    )
    assert dec_c18.is_match is True

    # 48 CE/DC
    dec_48 = referee_match(
        "48 CE/DC",
        "Haier Floor Standing 4 Ton Inverter 48CE/DC",
        brand="Haier",
    )
    assert dec_48.is_match is True

    # 24 HD/Z W vs 24 HDZ White (Base Match)
    dec_24hdz = referee_match(
        "24 HD/Z W",
        "Haier 2 Ton Inverter AC 24 HDZ White",
        brand="Haier",
    )
    assert dec_24hdz.is_match is True

    # 24 HD/Z UV W vs 24 HDZ UV White (UV Category 2 Match)
    dec_24hdz_uv = referee_match(
        "24 HD/Z UV W",
        "Haier 2 Ton Inverter AC 24 HDZ UV White",
        brand="Haier",
    )
    assert dec_24hdz_uv.is_match is True


def test_haier_referee_alternative_branches_acceptance() -> None:
    """Ensure candidate matching either branch of a slash model is accepted."""
    target_rf = "HRF-418 TIFG1U1/TIFB1U1 (IOT)"
    # Match G1 branch
    cand_g1 = "Haier HRF-418 TIFG1U1 Glass Door Smart Refrigerator (IoT)"
    dec_g1 = referee_match(target_rf, cand_g1, brand="Haier")
    assert dec_g1.is_match is True

    # Match B1 branch
    cand_b1 = "Haier HRF-418 TIFB1U1 Glass Door Smart Refrigerator"
    dec_b1 = referee_match(target_rf, cand_b1, brand="Haier")
    assert dec_b1.is_match is True

    target_mwo = "HGL-25MXP8 / 25MXP9"
    # Match MXP8
    cand_p8 = "Haier Microwave Oven HGL-25MXP8 Grill 25 Litres"
    dec_p8 = referee_match(target_mwo, cand_p8, brand="Haier")
    assert dec_p8.is_match is True

    # Match MXP9
    cand_p9 = "Haier Microwave Oven HGL-25MXP9 Grill"
    dec_p9 = referee_match(target_mwo, cand_p9, brand="Haier")
    assert dec_p9.is_match is True


def test_haier_referee_variant_tag_collision_guard() -> None:
    """Ensure conflicting variant tags (50MB vs 50DB) trigger zero-tolerance rejection."""
    target_mb = "HAF 50 MB"
    cand_matching = "Haier Air Fryer HAF-50MB Black"
    assert referee_match(target_mb, cand_matching, brand="Haier").is_match is True

    cand_conflicting = "Haier Air Fryer HAF-50DB Dark Brown"
    dec_rej = referee_match(target_mb, cand_conflicting, brand="Haier")
    assert dec_rej.is_match is False
    assert "Variant tag collision" in dec_rej.reason


def test_haier_referee_operating_mode_collision_guard() -> None:
    """Ensure Cool Only target strictly rejects Heat & Cool candidates to avoid commercial mispricing."""
    target_cool_only = "Cassette 48 HE/DC COOL ONLY"
    cand_heat_cool = "Haier 4 Ton Cassette Inverter 48HE/DC Heat and Cool"
    dec_mode = referee_match(target_cool_only, cand_heat_cool, brand="Haier")
    assert dec_mode.is_match is False
    assert "Operating mode collision" in dec_mode.reason


def test_haier_descriptive_series_and_tv_screen_matching() -> None:
    """Ensure descriptive series (Solar hybrid) and TV screen codes (32 D2) match properly."""
    # Solar hybrid 1.5ton
    dec_solar = referee_match(
        "Solar hybrid 1.5ton",
        "Haier Inverter Air Conditioner 1.5 Ton Solar Hybrid HSU-18HNS",
        brand="Haier",
    )
    assert dec_solar.is_match is True

    # 32" D2 LED TV
    dec_tv = referee_match(
        "32\" D2",
        "Haier 32 Inch HD LED TV 32D2 Official Warranty",
        brand="Haier",
    )
    assert dec_tv.is_match is True
````

## File: tests/test_learner.py
````python
import asyncio
from unittest.mock import AsyncMock

from pricing_engine.learner import (
    AutonomousLearner,
    is_valid_residual_token,
    is_valid_synonym_candidate,
    normalize_merchant_name,
)


def test_is_valid_residual_token_rejects_digits_and_metrics() -> None:
    """Residual tokens can NEVER contain numbers or unit specifications (Reviewer Guard 2)."""
    # Numbers and mixed alphanumeric metric leakage must be rejected
    assert is_valid_residual_token("12KG") is False
    assert is_valid_residual_token("12-KILO") is False
    assert is_valid_residual_token("1.5T") is False
    assert is_valid_residual_token("120-826S6") is False
    assert is_valid_residual_token("30") is False

    # Standard unit tokens must be rejected
    assert is_valid_residual_token("KG") is False
    assert is_valid_residual_token("TON") is False
    assert is_valid_residual_token("INCH") is False

    # Single-letter junk must be rejected
    assert is_valid_residual_token("A") is False
    assert is_valid_residual_token("") is False

    # Legitimate cosmetic/feature tokens must be accepted
    assert is_valid_residual_token("GC") is True
    assert is_valid_residual_token("GLASS DOOR") is True
    assert is_valid_residual_token("PILLOW DRUM") is True


def test_normalize_merchant_name_prevents_sybil_variations() -> None:
    """Merchant normalization prevents slight title variations from acting as distinct sellers (Reviewer Guard 3)."""
    m1 = normalize_merchant_name("Mega Store")
    m2 = normalize_merchant_name("MegaStore")
    m3 = normalize_merchant_name("Mega-Store!")
    assert m1 == m2 == m3 == "megastore"


def test_is_valid_synonym_candidate_enforces_symmetry_and_ratio() -> None:
    """Enforces non-empty symmetry and prevents multi-word fluff asymmetry (Reviewer Guard 6)."""
    # Empty strings cannot be mapped
    assert is_valid_synonym_candidate("", "PILLOW DRUM") is False
    assert is_valid_synonym_candidate("GC", "") is False

    # Asymmetry ratio guard: 1 word vs 4 words is fluff, not a variant synonym
    assert is_valid_synonym_candidate("GC", "GLASS DOOR PILLOW DRUM SUPER SILENT") is False

    # Valid symmetric 1-to-1 or 1-to-2 phrases are accepted
    assert is_valid_synonym_candidate("GC", "GLASS DOOR") is True
    assert is_valid_synonym_candidate("PL", "PILLOW DRUM") is True


def test_autonomous_learner_buffers_valid_observations_in_memory() -> None:
    """Observations are buffered in memory and reject invalid/empty categories (Reviewer Guards 1 & 4)."""
    learner = AutonomousLearner()
    learner.clear_buffer()

    # Missing category is rejected (Reviewer Guard 1)
    rejected = learner.buffer_observation(
        brand="Haier",
        category="",  # Empty category
        anchor_model="120-826S6",
        target_residual="GC",
        candidate_residual="GLASS DOOR",
        vendor_name="Mega Store",
        raw_title="Haier 120-826S6 Glass Door",
    )
    assert rejected is False
    assert learner.buffer_size == 0

    # Valid category and tokens are buffered
    accepted = learner.buffer_observation(
        brand="Haier",
        category="WASHING_MACHINE",
        anchor_model="120-826S6",
        target_residual="GC",
        candidate_residual="GLASS DOOR",
        vendor_name="Mega Store",
        raw_title="Haier 120-826S6 Glass Door",
    )
    assert accepted is True
    assert learner.buffer_size == 1


def test_autonomous_learner_bulk_flushes_to_supabase() -> None:
    """Bulk flush sends single batch POST to Supabase client without N+1 calls (Reviewer Guard 4)."""

    async def _test() -> None:
        learner = AutonomousLearner()
        learner.clear_buffer()

        learner.buffer_observation(
            brand="Haier",
            category="WASHING_MACHINE",
            anchor_model="120-826S6",
            target_residual="GC",
            candidate_residual="GLASS DOOR",
            vendor_name="Seller A",
            raw_title="Haier 120-826S6 Glass Door",
        )
        learner.buffer_observation(
            brand="Haier",
            category="WASHING_MACHINE",
            anchor_model="120-826S6",
            target_residual="GC",
            candidate_residual="GLASS COVER",
            vendor_name="Seller B",
            raw_title="Haier 120-826S6 Glass Cover",
        )

        mock_client = AsyncMock()
        mock_client.record_observations_batch.return_value = 2

        recorded = await learner.flush_observations(mock_client)
        assert recorded == 2
        assert mock_client.record_observations_batch.call_count == 1
        assert learner.buffer_size == 0

    asyncio.run(_test())


def test_autonomous_learner_promotes_candidates_with_three_distinct_vendors() -> None:
    """Candidates are promoted to APPROVED only when >= 3 distinct normalized merchants confirm (Reviewer Guard 3)."""
    learner = AutonomousLearner()

    # Observations from 3 distinct vendors for the same pair
    observations = [
        {"vendor_name": "Mega Store", "normalized_merchant": "megastore"},
        {"vendor_name": "Daraz Mall", "normalized_merchant": "darazmall"},
        {"vendor_name": "Lahore Electronics", "normalized_merchant": "lahoreelectronics"},
    ]

    distinct_merchants = learner.count_distinct_merchants(observations)
    assert distinct_merchants == 3
    assert learner.is_consensus_reached(distinct_merchants, threshold=3) is True

    # 3 listings from the SAME vendor should count as only 1 merchant
    sybil_observations = [
        {"vendor_name": "Mega Store", "normalized_merchant": "megastore"},
        {"vendor_name": "MegaStore", "normalized_merchant": "megastore"},
        {"vendor_name": "Mega-Store Official", "normalized_merchant": "megastoreofficial"},
    ]
    assert learner.count_distinct_merchants(sybil_observations) == 2
    assert (
        learner.is_consensus_reached(
            learner.count_distinct_merchants(sybil_observations), threshold=3
        )
        is False
    )


def test_learner_multi_catalog_real_world_washing_machines_and_appliances() -> None:
    """Test learning across real items from Stock Holding Report and Haier Washing Machines."""
    learner = AutonomousLearner()
    learner.clear_buffer()

    # 1. Dawlance DWT-1165 PL (Pillow Drum)
    assert (
        learner.buffer_observation(
            brand="Dawlance",
            category="WASHING_MACHINE",
            anchor_model="DWT-1165",
            target_residual="PL",
            candidate_residual="PILLOW DRUM",
            vendor_name="AlfaMall Partner A",
            raw_title="Dawlance DWT-1165 Pillow Drum Automatic Washing Machine",
        )
        is True
    )

    # 2. Dawlance DWT-14470 ES (Energy Saver)
    assert (
        learner.buffer_observation(
            brand="Dawlance",
            category="WASHING_MACHINE",
            anchor_model="DWT-14470",
            target_residual="ES",
            candidate_residual="ENERGY SAVER",
            vendor_name="DigiMall Store B",
            raw_title="Dawlance DWT-14470 Energy Saver Top Load",
        )
        is True
    )

    # 3. Dawlance DWT-11671 FLT (Flush Lid Top)
    assert (
        learner.buffer_observation(
            brand="Dawlance",
            category="WASHING_MACHINE",
            anchor_model="DWT-11671",
            target_residual="FLT",
            candidate_residual="FLUSH LID",
            vendor_name="Lahore Appliances",
            raw_title="Dawlance DWT-11671 Flush Lid Washing Machine",
        )
        is True
    )

    # 4. Haier Front Load HW 105-BD14376PGU1 (Direct Motion / Belt Drive)
    assert (
        learner.buffer_observation(
            brand="Haier",
            category="FRONT_LOAD_WASHING_MACHINE",
            anchor_model="105-BD14376PGU1",
            target_residual="DM",
            candidate_residual="DIRECT MOTION",
            vendor_name="Official Haier Flagship",
            raw_title="Haier 105-BD14376PGU1 Front Load Direct Motion",
        )
        is True
    )

    # 5. Microwave Oven touch panel (from M/O category in Stock Holding Report)
    assert (
        learner.buffer_observation(
            brand="Dawlance",
            category="MICROWAVE_OVEN",
            anchor_model="DW-MD7",
            target_residual="TP",
            candidate_residual="TOUCH PANEL",
            vendor_name="Metro Electronics",
            raw_title="Dawlance DW-MD7 Touch Panel Microwave Oven",
        )
        is True
    )

    assert learner.buffer_size == 5


def test_learner_blocks_anchor_and_metric_leakage_from_stock_sheet_models() -> None:
    """Validate that actual anchors and metrics from the Stock Holding Report can NEVER be learned as residuals."""
    learner = AutonomousLearner()
    learner.clear_buffer()

    real_anchors_and_metrics = [
        ("DWT-1165", "PL"),  # Real anchor DWT-1165 cannot be target_residual
        ("PL", "DWT-1165"),  # Real anchor cannot be candidate_residual
        ("11671", "FLT"),  # Digits from DWT-11671
        ("FTV60AXV1", "NORMAL"),  # Daikin AC model
        ("1088", "INSECT"),  # Anex 1088 model
        ("12KG", "10KG"),  # Capacity leakage
        ("2.0TON", "1.5TON"),  # Tonnage leakage
        ("3FT", "AIR CURTAIN"),  # Air curtain dimension
    ]

    for target_res, cand_res in real_anchors_and_metrics:
        buffered = learner.buffer_observation(
            brand="Dawlance",
            category="APPLIANCE",
            anchor_model="TEST-MODEL",
            target_residual=target_res,
            candidate_residual=cand_res,
            vendor_name="Sample Vendor",
            raw_title="Sample Title",
        )
        assert buffered is False, f"Failed: ({target_res}, {cand_res}) should have been rejected!"

    assert learner.buffer_size == 0


def test_learner_cross_category_polysemy_isolation_across_catalogs() -> None:
    """Ensure distinct categories in the stock sheet cannot contaminate each other's synonyms."""
    learner = AutonomousLearner()
    learner.clear_buffer()

    # 'GC' in WASHING_MACHINE = Glass Cover / Glass Door
    wm_ok = learner.buffer_observation(
        brand="Haier",
        category="WASHING_MACHINE",
        anchor_model="120-826S6",
        target_residual="GC",
        candidate_residual="GLASS DOOR",
        vendor_name="Vendor 1",
        raw_title="Haier 120-826S6 Glass Door Washing Machine",
    )
    assert wm_ok is True

    # 'GC' in REFRIGERATOR = Glass Chrome
    rf_ok = learner.buffer_observation(
        brand="Dawlance",
        category="REFRIGERATOR",
        anchor_model="9170",
        target_residual="GC",
        candidate_residual="GLASS CHROME",
        vendor_name="Vendor 2",
        raw_title="Dawlance 9170 Glass Chrome Refrigerator",
    )
    assert rf_ok is True

    # Check that both are buffered with strict isolated categories
    assert learner.buffer_size == 2
    cats = {obs["category"] for obs in learner._buffer}
    assert cats == {"WASHING_MACHINE", "REFRIGERATOR"}
````

## File: .env.example
````
# Supabase Cloud Configuration
# 1. Go to your Supabase Project Dashboard (https://supabase.com/dashboard)
# 2. In Project Settings -> API, copy:
#    - Project URL -> SUPABASE_URL
#    - Project API Keys:
#        * For backend repricing & observation logging: use `service_role` key (SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY)
#        * Note: NEVER expose the `service_role` key in public frontend client code!
#        * `anon` key only has read-only access to approved capacities & synonyms (RLS enforced).

SUPABASE_URL=https://your-project-id.supabase.co
# Backend pipeline secret (service_role recommended for full automated observation writes):
SUPABASE_KEY=your-supabase-service-role-or-anon-key-here
````

## File: README.md
````markdown
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

#### Option D: Background / Cron Mode (Legacy)
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
````

## File: pricing_engine/ingestion.py
````python
"""Catalog CSV Ingestion & Pre-flight Validation.

Reads, sanitizes, and validates catalog CSV files with strict required
column enforcement, whitespace cleanup, and backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pricing_engine.models import ProductInput

console = Console()

REQUIRED_COLUMNS: list[str] = [
    "Brand",
    "Name",
    "Net Price",
    "Length",
    "Width",
    "Height",
]

INVALID_BRAND_VALUES: frozenset[str] = frozenset(
    {"", "-", "--", "---", "_", ".", "/", "\\", "n/a", "na", "nan", "none", "null", "?"}
)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert arbitrary values to float, handling strings with commas or NaNs."""
    if val is None or pd.isna(val):
        return default
    try:
        clean_str = str(val).replace(",", "").strip()
        return float(clean_str)
    except (ValueError, TypeError):
        return default


def _extract_sno(row: pd.Series | dict[str, Any], default: int) -> int | str:
    """Extract serial number from row checking various casing or fallback to 1-based index."""
    for key in ("S.NO", "S.No", "S. No", "S.No.", "SNO", "sno", "Serial No", "Serial Number"):
        val = row.get(key)
        if val is not None and not pd.isna(val) and str(val).strip() != "":
            try:
                f = float(val)
                if f.is_integer():
                    return int(f)
            except (ValueError, TypeError):
                pass
            return str(val).strip()
    return default


@dataclass(frozen=True, slots=True)
class IngestionReport:
    """Pre-flight audit report generated upon ingesting a catalog CSV."""

    source_file: str
    total_rows: int
    valid_rows: int
    profit_source: str  # 'column' | 'default'


def render_ingestion_banner(report: IngestionReport) -> None:
    """Render a clean Rich pre-flight banner showing ingestion statistics."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column(style="green")

    table.add_row("Source File:", report.source_file)
    table.add_row("Total Items:", str(report.total_rows))
    table.add_row("Valid Items:", str(report.valid_rows))
    table.add_row("Profit Policy:", f"From {report.profit_source.upper()} (Rs. 500 default)")

    panel = Panel(
        table,
        title="[bold green]📦 Catalog Pre-flight Ingestion[/bold green]",
        border_style="green",
        expand=False,
    )
    console.print(panel)


def ingest_catalog(
    csv_path: str | Path,
    render_banner: bool = True,
) -> tuple[list[ProductInput], IngestionReport]:
    """Ingest, clean, and validate a catalog CSV file.

    Args:
        csv_path: Path to the input CSV file.
        render_banner: If True, renders a Rich pre-flight banner to console.

    Returns:
        A tuple of (list of ProductInput models, IngestionReport).

    Raises:
        FileNotFoundError: If the provided file does not exist.
        ValueError: If any required column is missing from the CSV.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Input catalog CSV not found: {path}")

    df = pd.read_csv(path)

    # Clean and strip whitespace from all column headers
    df.columns = [str(c).strip() for c in df.columns]

    # Validate required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in CSV: {sorted(missing)}. "
            f"Expected at least: {REQUIRED_COLUMNS}"
        )

    has_profit_col = "Profit" in df.columns
    profit_source = "column" if has_profit_col else "default"

    products: list[ProductInput] = []
    for idx, (_, row) in enumerate(df.iterrows()):
        sno = _extract_sno(row, idx + 1)

        raw_name = row.get("Name")
        name = str(raw_name).strip() if (raw_name is not None and not pd.isna(raw_name)) else ""
        if not name or name.lower() in ("nan", "none", "-", "--", "n/a"):
            raise ValueError(
                f"Row {idx + 1}: Product 'Name' is empty or missing in CSV. Please enter the product name."
            )

        raw_brand = row.get("Brand")
        brand = str(raw_brand).strip() if (raw_brand is not None and not pd.isna(raw_brand)) else ""

        # Strictly enforce non-empty, valid brand value in Brand column
        if not brand or brand.lower() in INVALID_BRAND_VALUES:
            raise ValueError(
                f"Row {idx + 1} ('{name}'): 'Brand' column is empty or invalid ('{brand or raw_brand}'). "
                "Please enter a valid brand name in the 'Brand' column for this product. "
                "Products cannot be processed or matched without a brand because without it, the wrong product could be matched."
            )

        length = _safe_float(row.get("Length"), 0.0)
        width = _safe_float(row.get("Width"), 0.0)
        height = _safe_float(row.get("Height"), 0.0)
        net_price = _safe_float(row.get("Net Price"), 0.0)

        # Per-row profit: use column if provided and valid, otherwise fallback to 500.0
        profit_val = row.get("Profit") if has_profit_col else None
        profit = _safe_float(profit_val, 500.0) if profit_val is not None else 500.0

        product = ProductInput(
            sno=sno,
            brand=brand,
            name=name,
            length=length,
            width=width,
            height=height,
            net_price=net_price,
            profit=profit,
            raw_row=row.to_dict(),
        )
        products.append(product)

    report = IngestionReport(
        source_file=path.name,
        total_rows=len(df),
        valid_rows=len(products),
        profit_source=profit_source,
    )

    if render_banner and len(products) > 0:
        render_ingestion_banner(report)

    return products, report
````

## File: tests/test_fixtures.py
````python
"""Test fixtures and multi-catalog data validation suite.

Validates that:
1. Haier Washing Machines input and benchmark CSVs load cleanly.
2. Cross-category catalog samples from Stock Holding Report are structured and parseable.
"""

from pathlib import Path

import pandas as pd

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _get_fixture(filename: str) -> Path:
    p = FIXTURES_DIR / filename
    if p.exists():
        return p
    return Path(filename)


def test_haier_washing_machines_catalog_integrity() -> None:
    """Verify that Haier washing machines catalog contains 38 verified products."""
    catalog_path = _get_fixture("Haier_Washing_Machines_Uploading_and_Price.csv")
    assert catalog_path.exists(), "Haier washing machine catalog missing from test fixtures"

    df = pd.read_csv(catalog_path)
    assert len(df) == 38, f"Expected 38 products, got {len(df)}"

    required_columns = {
        "S.NO",
        "Brand",
        "Name ",
        "Length",
        "Width",
        "Height",
        "Net Price",
        "Profit",
    }
    assert required_columns.issubset(set(df.columns)), (
        f"Missing columns: {required_columns - set(df.columns)}"
    )

    # Ensure all net prices and dimensions are valid positive numbers (strip commas if formatted as strings)
    net_prices = df["Net Price"].astype(str).str.replace(",", "").str.strip().astype(float)
    assert (net_prices > 0).all(), "Net Price must be strictly positive"
    assert (df["Length"] > 0).all(), "Length must be strictly positive"
    assert (df["Width"] > 0).all(), "Width must be strictly positive"
    assert (df["Height"] > 0).all(), "Height must be strictly positive"


def test_stock_holding_report_cross_category_samples() -> None:
    """Verify multi-category catalog samples across Refrigerators, ACs, Dispensers, W/M, and Microwaves."""
    stock_path = _get_fixture("Stock Holding Report - FINAC - Products - MainSheet.csv")
    assert stock_path.exists(), "Stock Holding Report missing from test fixtures"

    df = pd.read_csv(stock_path)
    assert len(df) >= 700, f"Expected 700+ rows, got {len(df)}"

    categories = set(df["Category"].dropna().unique())
    assert "SPLIT AC" in categories
    assert "REFRIGERATOR" in categories
    assert "W/M" in categories
    assert "W/D" in categories

    # Verify specific representative models exist in 'Item Name' column
    names = df["Item Name"].dropna().tolist()
    assert any("276EBS SILVER" in n for n in names)
    assert any("306IDB BLACK" in n for n in names)
    assert any("MAGNA T3 INVERTER 30 MILKY" in n for n in names)
    assert any("CHROME PRO INVERTER 30" in n for n in names)
    assert any("1051 GD SILVER" in n for n in names)
    assert any("6580 CB FL" in n for n in names)
````

## File: tests/test_ingestion.py
````python
"""Tests for catalog CSV ingestion and pre-flight validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from pricing_engine.ingestion import IngestionReport, ingest_catalog


def test_ingest_catalog_clean_6_column_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "catalog.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92\n"
        "Gree,GREE SPLIT AC 18AITH21W-T3,183000,104,39,103\n",
        encoding="utf-8",
    )

    products, report = ingest_catalog(csv_file, render_banner=False)

    assert len(products) == 2
    assert isinstance(report, IngestionReport)
    assert report.total_rows == 2
    assert report.valid_rows == 2
    assert report.profit_source == "default"

    p1 = products[0]
    assert p1.sno == 1
    assert p1.brand == "Gree"
    assert p1.name == "GREE SPLIT AC 12AITH21W-T3"
    assert p1.net_price == 147000.0
    assert p1.length == 87.0
    assert p1.width == 35.5
    assert p1.height == 92.0
    assert p1.profit == 500.0


def test_ingest_catalog_7_column_csv_with_profit(tmp_path: Path) -> None:
    csv_file = tmp_path / "catalog_profit.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height,Profit\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92,1500\n"
        "Gree,GREE SPLIT AC 18AITH21W-T3,183000,104,39,103,\n",
        encoding="utf-8",
    )

    products, report = ingest_catalog(csv_file, render_banner=False)

    assert len(products) == 2
    assert report.profit_source == "column"
    assert products[0].profit == 1500.0
    # Empty cell defaults gracefully to 500.0
    assert products[1].profit == 500.0


def test_ingest_catalog_handles_price_with_commas(tmp_path: Path) -> None:
    csv_file = tmp_path / "catalog_commas.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n"
        'Dawlance,Dawlance Refrigerator,"125,500",60,60,160\n',
        encoding="utf-8",
    )

    products, _ = ingest_catalog(csv_file, render_banner=False)

    assert len(products) == 1
    assert products[0].net_price == 125500.0


def test_ingest_catalog_strips_column_whitespace(tmp_path: Path) -> None:
    csv_file = tmp_path / "catalog_whitespace.csv"
    csv_file.write_text(
        " Brand , Name  , Net Price , Length , Width , Height \n"
        "Haier,Haier Washing Machine,65000,60,60,85\n",
        encoding="utf-8",
    )

    products, report = ingest_catalog(csv_file, render_banner=False)

    assert len(products) == 1
    assert products[0].brand == "Haier"
    assert products[0].name == "Haier Washing Machine"


def test_ingest_catalog_missing_net_price_column_raises(tmp_path: Path) -> None:
    csv_file = tmp_path / "invalid_catalog.csv"
    csv_file.write_text(
        "Brand,Name,Length,Width,Height\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,87,35.5,92\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        ingest_catalog(csv_file, render_banner=False)

    assert "Missing required columns in CSV" in str(exc_info.value)
    assert "Net Price" in str(exc_info.value)


def test_ingest_catalog_missing_brand_column_raises(tmp_path: Path) -> None:
    csv_file = tmp_path / "invalid_catalog.csv"
    csv_file.write_text(
        "Name,Net Price,Length,Width,Height\n"
        "Gree AC,140000,87,35.5,92\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        ingest_catalog(csv_file, render_banner=False)

    assert "Brand" in str(exc_info.value)


def test_ingest_catalog_file_not_found_raises() -> None:
    with pytest.raises(FileNotFoundError):
        ingest_catalog("non_existent_file_xyz_123.csv", render_banner=False)


def test_ingest_catalog_empty_csv_headers_only(tmp_path: Path) -> None:
    csv_file = tmp_path / "empty_catalog.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n",
        encoding="utf-8",
    )

    products, report = ingest_catalog(csv_file, render_banner=False)

    assert len(products) == 0
    assert report.total_rows == 0
    assert report.valid_rows == 0


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _get_fixture(filename: str) -> Path:
    p = FIXTURES_DIR / filename
    if p.exists():
        return p
    return Path(filename)


def test_ingest_catalog_legacy_gree_csv() -> None:
    legacy_path = _get_fixture("Gree_Uploading_on_DigiMall_and_Price.csv")
    if not legacy_path.is_file():
        pytest.skip("Gree CSV fixture not found")

    products, report = ingest_catalog(legacy_path, render_banner=False)

    assert len(products) > 0
    assert report.total_rows == len(products)
    assert products[0].brand == "Gree"
    assert products[0].net_price > 0


def test_ingest_catalog_legacy_haier_csv() -> None:
    legacy_path = _get_fixture("Haier_Washing_Machines_Uploading_and_Price.csv")
    if not legacy_path.is_file():
        pytest.skip("Haier CSV fixture not found")

    products, report = ingest_catalog(legacy_path, render_banner=False)

    assert len(products) > 0
    assert report.total_rows == len(products)
    assert products[0].brand == "Haier"


def test_ingest_catalog_empty_brand_cell_raises(tmp_path: Path) -> None:
    csv_file = tmp_path / "empty_brand.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n"
        ",Dawlance 4467 SD MINI BAR,55000,50,50,85\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        ingest_catalog(csv_file, render_banner=False)

    assert "'Brand' column is empty or invalid" in str(exc_info.value)
    assert "Please enter a valid brand name in the 'Brand' column" in str(exc_info.value)


def test_ingest_catalog_placeholder_brand_cell_raises(tmp_path: Path) -> None:
    for idx, placeholder in enumerate(["-", "--", "N/A", "none", "nan", "?"]):
        csv_file = tmp_path / f"placeholder_{idx}.csv"
        csv_file.write_text(
            f"Brand,Name,Net Price,Length,Width,Height\n"
            f"{placeholder},Dawlance 4467 SD MINI BAR,55000,50,50,85\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError) as exc_info:
            ingest_catalog(csv_file, render_banner=False)

        assert "'Brand' column is empty or invalid" in str(exc_info.value)
````

## File: tests/test_pipeline_resilience.py
````python
"""Deep resilience and edge-case testing for Phase 1 pipeline.

Tests multi-angle variations:
1. User provides S.NO explicitly (e.g. 101, 102).
2. User provides S.No (lowercase 'o' or casing variants).
3. User provides string/alphanumeric S.NO ("SKU-001", "GREE-12A").
4. User does not provide S.NO column at all (auto-generation 1, 2, 3...).
5. User provides S.NO with empty/blank cells.
6. User provides custom extra columns (e.g. "Color", "Supplier").
7. Concurrent pipeline execution preserves deterministic row sequence.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from pricing_engine.models import ScrapeResult
from pricing_engine.pipeline import (
    _extract_sno,
    build_output_record,
    parse_product_input,
    run_pipeline,
)


def test_extract_sno_various_casings() -> None:
    assert _extract_sno({"S.NO": 10}, 1) == 10
    assert _extract_sno({"S.No": 20}, 1) == 20
    assert _extract_sno({"S. No": 30}, 1) == 30
    assert _extract_sno({"SNO": 40}, 1) == 40
    assert _extract_sno({"sno": 50}, 1) == 50
    assert _extract_sno({"Serial No": "A-1"}, 1) == "A-1"
    # Empty cell / NaN falls back to default
    assert _extract_sno({"S.NO": float("nan")}, 99) == 99
    assert _extract_sno({"S.NO": ""}, 99) == 99
    assert _extract_sno({"S.NO": None}, 99) == 99
    assert _extract_sno({}, 99) == 99


def test_extract_sno_handles_float_drift() -> None:
    # Float 1.0 converts to int 1
    assert _extract_sno({"S.No": 1.0}, 99) == 1
    # String float "2.0" converts to int 2
    assert _extract_sno({"S.NO": "2.0"}, 99) == 2
    # Alphanumeric string preserved
    assert _extract_sno({"sno": "SKU-99"}, 99) == "SKU-99"


def test_parse_product_input_with_explicit_sno() -> None:
    row = pd.Series(
        {
            "S.NO": 105,
            "Brand": "Gree",
            "Name": "Gree Split AC 12AITH21W",
            "Net Price": 140000,
            "Length": 87,
            "Width": 35.5,
            "Height": 92,
        }
    )
    product = parse_product_input(0, row)
    assert product.sno == 105
    assert product.brand == "Gree"
    assert product.length == 87.0


def test_parse_product_input_with_lowercase_sno() -> None:
    row = pd.Series(
        {
            "S.No": "GREE-01",
            "Brand": "Gree",
            "Name": "Gree Split AC 12AITH21W",
            "Net Price": 140000,
            "Length": 87,
            "Width": 35.5,
            "Height": 92,
        }
    )
    product = parse_product_input(4, row)
    assert product.sno == "GREE-01"


def test_parse_product_input_without_sno_column_defaults_to_1_indexed() -> None:
    row = pd.Series(
        {
            "Brand": "Dawlance",
            "Name": "Dawlance Refrigerator",
            "Net Price": 95000,
            "Length": 60,
            "Width": 60,
            "Height": 160,
        }
    )
    product = parse_product_input(0, row)
    assert product.sno == 1

    product_row_5 = parse_product_input(4, row)
    assert product_row_5.sno == 5


def test_build_output_record_guarantees_sno_present_and_clean() -> None:
    # 1. Product without S.NO in raw_row gets product.sno assigned to 'S.NO'
    product = parse_product_input(
        2,  # row index 2 -> sno = 3
        pd.Series(
            {
                "Brand": "Haier",
                "Name": "Haier Washing Machine",
                "Net Price": 80000,
                "Length": 60,
                "Width": 60,
                "Height": 85,
            }
        ),
    )

    from pricing_engine.calculator import calculate_cost_base, calculate_floors
    from pricing_engine.models import PlatformPricingResult

    floors = calculate_floors(calculate_cost_base(80000, 3500))
    dummy_res = PlatformPricingResult(
        min_price=90000,
        max_price=95000,
        final_price=92999,
        real_profit=3500,
        reason="Won",
        status="Won",
        effective_comm="10.00%",
    )

    rec = build_output_record(
        product=product,
        shipping=3500.0,
        floors=floors,
        baseline_calc=95000.0,
        alfa_res=dummy_res,
        digi_res=dummy_res,
    )

    # Must contain "S.NO" with value 3
    assert "S.NO" in rec
    assert rec["S.NO"] == 3


def test_build_output_record_normalizes_lowercase_sno_alias() -> None:
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.No": 999,
                "Brand": "Haier",
                "Name": "Haier Washer",
                "Net Price": 75000,
                "Length": 60,
                "Width": 60,
                "Height": 85,
            }
        ),
    )

    from pricing_engine.calculator import calculate_cost_base, calculate_floors
    from pricing_engine.models import PlatformPricingResult

    floors = calculate_floors(calculate_cost_base(75000, 3000))
    dummy_res = PlatformPricingResult(
        min_price=85000,
        max_price=90000,
        final_price=87999,
        real_profit=3000,
        reason="Won",
        status="Won",
        effective_comm="10.00%",
    )

    rec = build_output_record(
        product=product,
        shipping=3000.0,
        floors=floors,
        baseline_calc=88000.0,
        alfa_res=dummy_res,
        digi_res=dummy_res,
    )

    assert rec["S.NO"] == 999
    # The lower-case alias "S.No" must be removed to prevent duplicate columns
    assert "S.No" not in rec


def test_full_pipeline_with_various_sno_and_missing_sno(tmp_path: Path) -> None:
    """Test full pipeline run with a CSV having mixed S.NO (explicit, alphanumeric, empty)."""
    input_csv = tmp_path / "mixed_sno_catalog.csv"
    input_csv.write_text(
        "S.NO,Brand,Name,Net Price,Length,Width,Height,Custom Tag\n"
        "101,Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92,Special Edition\n"
        "SKU-99,Haier,Haier Washing Machine HW80,75000,60,60,85,In Stock\n"
        ",Dawlance,Dawlance Refrigerator 9170,110000,60,65,165,Best Seller\n",
        encoding="utf-8",
    )
    output_csv = tmp_path / "repriced_output.csv"

    mock_offers = ScrapeResult(offers=[], is_success=True, status_code=200)

    async def _run() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_offers),
            patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_offers),
        ):
            out_df = await run_pipeline(
                input_path=input_csv,
                output_path=output_csv,
                concurrency=2,
                verbose=False,
            )

            assert len(out_df) == 3
            # Check S.NO values
            assert str(out_df["S.NO"].iloc[0]) == "101"
            assert str(out_df["S.NO"].iloc[1]) == "SKU-99"
            # Row 3 with empty S.NO auto-filled with row number 3
            assert str(out_df["S.NO"].iloc[2]) == "3"
            # Custom tag column preserved
            assert out_df["Custom Tag"].iloc[0] == "Special Edition"
            # Pricing calculated (Monopoly since 0 offers)
            assert out_df["Final Price Alfa"].iloc[0] != ""
            assert out_df["Final Price Digi"].iloc[0] != ""

    asyncio.run(_run())


def test_full_pipeline_pure_clean_template_without_sno(tmp_path: Path) -> None:
    """Test full pipeline with clean 6-column template that has NO S.NO column."""
    input_csv = tmp_path / "pure_clean_template.csv"
    input_csv.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92\n"
        "Gree,GREE SPLIT AC 18AITH21W-T3,183000,104,39,103\n",
        encoding="utf-8",
    )
    export_dir = tmp_path / "structured_outputs"

    mock_offers = ScrapeResult(offers=[], is_success=True, status_code=200)

    async def _run() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_offers),
            patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_offers),
        ):
            out_df = await run_pipeline(
                input_path=input_csv,
                output_path=None,
                concurrency=2,
                verbose=False,
                use_structured_export=True,
                export_dir=export_dir,
            )

            assert len(out_df) == 2
            # S.NO automatically created as 1, 2
            assert "S.NO" in out_df.columns
            assert list(out_df["S.NO"]) == [1, 2]

            # Output files exist in export directory
            latest_file = export_dir / "pure_clean_template_repriced_latest.csv"
            assert latest_file.is_file()
            read_back = pd.read_csv(latest_file)
            assert "S.NO" in read_back.columns
            assert list(read_back["S.NO"]) == [1, 2]
            # Ensure S.NO is the first column in the exported CSV
            assert list(read_back.columns)[0] == "S.NO"

    asyncio.run(_run())


def test_format_export_sno() -> None:
    from pricing_engine.exporter import format_export_sno

    assert format_export_sno(1) == "1"
    assert format_export_sno(1.0) == "1"
    assert format_export_sno("2.0") == "2"
    assert format_export_sno("SKU-100") == "SKU-100"
    assert format_export_sno(None) == ""
    assert format_export_sno(float("nan")) == ""


def test_full_pipeline_lowercase_sno_first_column(tmp_path: Path) -> None:
    """Test when input has 'S.No' as first column, output standardizes to 'S.NO' in first column."""
    input_csv = tmp_path / "lowercase_sno_first.csv"
    input_csv.write_text(
        "S.No,Brand,Name,Net Price,Length,Width,Height\n"
        "10,Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92\n"
        "20,Haier,Haier Washing Machine,75000,60,60,85\n",
        encoding="utf-8",
    )
    output_csv = tmp_path / "standardized_output.csv"

    mock_offers = ScrapeResult(offers=[], is_success=True, status_code=200)

    async def _run() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_offers),
            patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_offers),
        ):
            out_df = await run_pipeline(
                input_path=input_csv,
                output_path=output_csv,
                concurrency=2,
                verbose=False,
            )

            assert list(out_df.columns)[0] == "S.NO"
            assert "S.No" not in out_df.columns
            assert list(out_df["S.NO"]) == [10, 20]

    asyncio.run(_run())


def test_haier_washer_hyphenated_and_spaced_matching() -> None:
    from pricing_engine.matcher import referee_match

    # 1. Spaced model prefix matching candidate with glued SKU
    t1 = "Haier HW 90-BP12357S8 Front Load Washing Machine"
    c1 = "Haier HW90-BP12357S8 9 KG Front Load Inverter Automatic Washing Machine"
    assert referee_match(t1, c1, brand="Haier").is_match is True

    # 2. Form factor Single Tub with promotional noise trailer
    t2 = "Haier HWM 130-1217 WB Single Tub Washing Machine"
    c2 = "Haier HWM 130-1217 13kg Top Load Washing Machine - Manual Control Washer | Big Capacity, Strong Performance, Home Use"
    assert referee_match(t2, c2, brand="Haier").is_match is True


def test_haier_lowercase_variant_tag_matching() -> None:
    from pricing_engine.matcher import referee_match

    # Lowercase color code 'ow' (Off White) matching HSU-14HFTEX-OW
    t = "14hft ow"
    c = "HAIER 1.25 TON HSU-14HFTEX-OW PLUS INVERTER AIR CONDITIONER"
    assert referee_match(t, c, brand="Haier").is_match is True


def test_dawlance_refrigerator_soft_styling_optionality() -> None:
    from pricing_engine.matcher import referee_match

    # Soft styling trim (Chrome FH) omitted by seller for unique model stems
    t1 = "9173 WB Chrome FH"
    c1 = "Dawlance 9173WB 12 Cu Ft Coral Red Refrigerator"
    assert referee_match(t1, c1, brand="Dawlance").is_match is True

    t2 = "91999 WB Chrome FH"
    c2 = "Dawlance DW-91999 20 Cu Ft Coral Red Double Door Refrigerator"
    assert referee_match(t2, c2, brand="Dawlance").is_match is True

    t3 = "9140 WB LVS FH"
    c3 = "Dawlance REF-9140WB 8 Cu Ft Grey Double Door Refrigerator"
    assert referee_match(t3, c3, brand="Dawlance").is_match is True


def test_dawlance_refrigerator_series_collision_protection() -> None:
    from pricing_engine.matcher import referee_match

    # Distinct series (Avante, Acce, Graze) must never match Chrome model
    target = "9173 WB Chrome FH"
    cand_avante = "Dawlance 9173-WB-Avante+ 12 Cu Ft Cloud White Refrigerator"
    cand_acce = "Dawlance 9173LF-Acce-Pro 12 Cu Ft Crimson Red Refrigerator"
    cand_graze = "Dawlance 9173 12 Cu Ft Graze+ Gem Black Glass Refrigerator"

    assert referee_match(target, cand_avante, brand="Dawlance").is_match is False
    assert referee_match(target, cand_acce, brand="Dawlance").is_match is False
    assert referee_match(target, cand_graze, brand="Dawlance").is_match is False


def test_gree_ac_screen_size_guard_and_energy_rating() -> None:
    from pricing_engine.matcher import referee_match

    # Floor standing AC with AA+ energy rating must not be treated as screen size or series AA
    t1 = "GREE FLOOR STANDING 36TFIH AA+"
    c1 = "GREE 3 TON GF-36TFIH INVERTER FLOOR STANDING AIR CONDITIONER"
    assert referee_match(t1, c1, brand="Gree").is_match is True

    # 1.5T Pular with AAA energy badge must not fail on screen size or AAA series
    t2 = "GREE SPLIT AC 18PITH11G AAA"
    c2 = "Gree 1.5 Ton Pular Series GS-18PITH11G Inverter Heat and Cool Split Air Conditioner"
    assert referee_match(t2, c2, brand="Gree").is_match is True

    # 1T Airy Pro GS-12AITH24S-T3 must match without capacity screen size conflict
    t3 = "GREE SPLIT AC 12AITH24S-T3"
    c3 = "Gree 1 Ton Airy Pro GS-12AITH24S-T3 Inverter Heat & Cool Split Air Conditioner"
    assert referee_match(t3, c3, brand="Gree").is_match is True


def test_category1_soft_descriptor_sd_and_dd_isolation() -> None:
    """Category 1: Soft descriptors (SD, GD) match base model and fullforms, but reject opposing finishes (DD, INOX)."""
    from pricing_engine.matcher import referee_match

    target = "DMB-4467 SD"
    brand = "Dawlance"

    # Must match with-tag listing
    assert referee_match(target, "Dawlance Minibar DMB-4467 SD", brand=brand).is_match is True
    # Must match fullform expansion
    assert referee_match(target, "Dawlance Minibar DMB-4467 Single Door", brand=brand).is_match is True
    # Must match base model listing seamlessly (physically identical machine)
    assert referee_match(target, "Dawlance Minibar DMB-4467", brand=brand).is_match is True

    # Must strictly reject opposing door structure
    dec_dd = referee_match(target, "Dawlance Minibar DMB-4467 DD", brand=brand)
    assert dec_dd.is_match is False
    assert "Door structure collision" in dec_dd.reason

    dec_double = referee_match(target, "Dawlance Minibar DMB-4467 Double Door", brand=brand)
    assert dec_double.is_match is False
    assert "Door structure collision" in dec_double.reason


def test_category2_hardware_modifier_fallback_and_cross_check_notices() -> None:
    """Category 2: When target specifies T3, exact is preferred; if omitted, falls back with cross-check notices."""
    from unittest.mock import AsyncMock, MagicMock

    from pricing_engine.calculator import calculate_floors
    from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
    from pricing_engine.pipeline import _format_summary_price
    from pricing_engine.scraper import scrape_alfamall

    # 1. Exact Priority when T3 exists in marketplace
    async def _test_exact() -> None:
        base_resp = MagicMock()
        base_resp.status_code = 200
        base_resp.json.return_value = {
            "results": [
                {
                    "title": "GREE 18AITH24S Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "190,000"},
                    "vendor": {"name": "Base Store"},
                }
            ]
        }
        t3_resp = MagicMock()
        t3_resp.status_code = 200
        t3_resp.json.return_value = {
            "results": [
                {
                    "title": "GREE 18AITH24S-T3 Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "195,000"},
                    "vendor": {"name": "T3 Store"},
                }
            ]
        }
        mock_session = AsyncMock()
        mock_session.get.side_effect = [base_resp, t3_resp]

        res = await scrape_alfamall(
            mock_session,
            {"tier_1": ["18AITH24S"], "tier_2": ["18AITH24S-T3"], "tier_3": []},
            "18AITH24S-T3",
            brand="Gree",
        )
        assert [o.vendor_name for o in res.offers] == ["T3 Store"]
        assert res.active_modifier_fallback is None

    asyncio.run(_test_exact())

    # 2. Safe Fallback to Base Model when market omitted T3
    async def _test_fallback() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "GREE 18AITH24S Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "190,000"},
                    "vendor": {"name": "Base Store"},
                }
            ]
        }
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        res = await scrape_alfamall(
            mock_session,
            {"tier_1": ["18AITH24S"], "tier_2": [], "tier_3": []},
            "18AITH24S-T3",
            brand="Gree",
        )
        assert [o.vendor_name for o in res.offers] == ["Base Store"]
        assert res.active_modifier_fallback == "T3"

        # Evaluator reason annotation
        floors = calculate_floors(150000.0)
        alfa_eval = evaluate_alfa_pricing(floors, res)
        assert alfa_eval.status == "Competitive Win"
        assert "[FALLBACK MODEL: Target specified 'T3', but market listings omitted it; repriced against base model]" in alfa_eval.reason

        digi_eval = evaluate_digi_pricing(floors, res)
        assert "Safe Win" in digi_eval.status
        assert "[FALLBACK MODEL: Target specified 'T3', but market listings omitted it; repriced against base model]" in digi_eval.reason

        # Executive summary table badge
        disp_price = _format_summary_price(alfa_eval.final_price, min_comp_price=190000.0, reason=alfa_eval.reason)
        assert "CROSS-CHECK" in disp_price

    asyncio.run(_test_fallback())


def test_glass_door_and_inox_category2_fallback_and_collision() -> None:
    """Category 2: GD and INOX match when present, fall back to base model when omitted, and strictly collide with each other."""
    from pricing_engine.matcher import referee_match

    brand = "Dawlance"

    # --- Glass Door (GD) ---
    target_gd = "7950 Glass Door"
    # Mila toh lelo (Exact match when present)
    dec_gd_match = referee_match(target_gd, "Dawlance 7950 GD Refrigerator", brand=brand)
    assert dec_gd_match.is_match is True
    assert dec_gd_match.is_base_match is False

    # Nahi mila toh fallback (Fallback to base model when omitted)
    dec_gd_omitted = referee_match(target_gd, "Dawlance 7950 Refrigerator", brand=brand)
    assert dec_gd_omitted.is_match is False
    assert dec_gd_omitted.is_base_match is True
    assert dec_gd_omitted.missing_modifier == "GD"

    # Opposing finish collision
    dec_gd_inox = referee_match(target_gd, "Dawlance 7950 INOX Refrigerator", brand=brand)
    assert dec_gd_inox.is_match is False
    assert dec_gd_inox.is_base_match is False
    assert "Hardware finish collision" in dec_gd_inox.reason

    # --- INOX ---
    target_inox = "DMB 7950 Inox"
    # Mila toh lelo
    dec_inox_match = referee_match(target_inox, "Dawlance 7950 Inox Refrigerator", brand=brand)
    assert dec_inox_match.is_match is True
    assert dec_inox_match.is_base_match is False

    # Nahi mila toh fallback
    dec_inox_omitted = referee_match(target_inox, "Dawlance 7950 Refrigerator", brand=brand)
    assert dec_inox_omitted.is_match is False
    assert dec_inox_omitted.is_base_match is True
    assert dec_inox_omitted.missing_modifier == "INOX"

    # Opposing finish collision
    dec_inox_gd = referee_match(target_inox, "Dawlance 7950 GD Refrigerator", brand=brand)
    assert dec_inox_gd.is_match is False
    assert dec_inox_gd.is_base_match is False
    assert "Hardware finish collision" in dec_inox_gd.reason


def test_category2_inverter_and_es_generic_fallback() -> None:
    """Category 2: Inverter strictly rejects Non-Inverter, but safely falls back to base model when omitted."""
    from pricing_engine.matcher import referee_match

    # Inverter vs Non-Inverter collision
    dec_col = referee_match("9170 Inverter GD", "Dawlance 9170 Non-Inverter GD", brand="Dawlance")
    assert dec_col.is_match is False
    assert "Inverter mode collision" in dec_col.reason

    # Inverter vs Omitted Inverter (Base Match)
    dec_base = referee_match("9170 Inverter GD", "Dawlance 9170 GD Refrigerator", brand="Dawlance")
    assert dec_base.is_match is False
    assert dec_base.is_base_match is True
    assert dec_base.missing_modifier == "INVERTER"

    # ES8 vs Omitted ES8 (Base Match)
    dec_es = referee_match("18PITH11G ES8", "Gree GS-18PITH11G Inverter AC", brand="Gree")
    assert dec_es.is_match is False
    assert dec_es.is_base_match is True
    assert dec_es.missing_modifier == "ES8"


def test_category1_single_door_and_double_door_isolation() -> None:
    """Category 1: SD strictly matches baseline and fullform, but strictly collides with DD."""
    from pricing_engine.matcher import referee_match

    brand = "Dawlance"
    target = "DMB-4467 SD"

    # Must match full form Single Door
    assert referee_match(target, "Dawlance DMB-4467 Single Door Refrigerator", brand=brand).is_match is True
    # Must match baseline listing where seller omitted SD (ZERO fallback warning, direct normal match)
    dec_base = referee_match(target, "Dawlance DMB-4467 Refrigerator", brand=brand)
    assert dec_base.is_match is True
    assert dec_base.is_base_match is False

    # Must strictly reject opposing Double Door structure
    dec_dd = referee_match(target, "Dawlance DMB-4467 Double Door Refrigerator", brand=brand)
    assert dec_dd.is_match is False
    assert "Door structure collision" in dec_dd.reason


def test_category2_generic_hardware_capabilities_comprehensive() -> None:
    """Category 2: Generic hardware capabilities (T3, ES8, ES, INVERTER, WIFI, IOT) with zero hardcoding."""
    from pricing_engine.matcher import referee_match

    # 1. T3 Target vs Omitted Candidate -> Base Match
    dec_t3_omitted = referee_match("18AITH24S-T3", "Gree GS-18AITH24S Inverter AC", brand="Gree")
    assert dec_t3_omitted.is_match is False
    assert dec_t3_omitted.is_base_match is True
    assert dec_t3_omitted.missing_modifier == "T3"

    # 2. Non-T3 Target vs Upgraded T3 Candidate -> Hard Rejection (NOT a base match)
    dec_t3_upgraded = referee_match("18AITH24S", "Gree GS-18AITH24S-T3 Inverter AC", brand="Gree")
    assert dec_t3_upgraded.is_match is False
    assert dec_t3_upgraded.is_base_match is False
    assert "Hardware capability mismatch" in dec_t3_upgraded.reason

    # 3. T3 Target vs T3 Candidate -> Full Match
    dec_t3_both = referee_match("18AITH24S-T3", "Gree GS-18AITH24S-T3 Inverter AC", brand="Gree")
    assert dec_t3_both.is_match is True
    assert dec_t3_both.is_base_match is False

    # 4. Standalone ES Target vs Omitted Candidate -> Base Match
    dec_es = referee_match("18PITH11G ES", "Gree GS-18PITH11G Inverter AC", brand="Gree")
    assert dec_es.is_match is False
    assert dec_es.is_base_match is True
    assert dec_es.missing_modifier == "ES"

    # 5. Standalone ES Target vs ES Candidate -> Full Match
    dec_es_match = referee_match("18PITH11G ES", "Gree GS-18PITH11G ES Inverter AC", brand="Gree")
    assert dec_es_match.is_match is True
    assert dec_es_match.is_base_match is False

    # 6. WiFi Target vs Omitted Candidate -> Base Match
    dec_wifi = referee_match("18AITH24S WiFi", "Gree GS-18AITH24S Inverter AC", brand="Gree")
    assert dec_wifi.is_match is False
    assert dec_wifi.is_base_match is True
    assert dec_wifi.missing_modifier == "WIFI"

    # 7. IoT Target vs Smart Candidate -> Full Match
    dec_iot_smart = referee_match(
        "HRF-418 TIFG1U1 (IOT)",
        "Haier HRF-418 TIFG1U1 Glass Door Smart Refrigerator",
        brand="Haier",
    )
    assert dec_iot_smart.is_match is True
    assert dec_iot_smart.is_base_match is False


def test_dynamic_post_model_code_and_finish_rules() -> None:
    """Validate dynamic post-model code grabbing (ES, ES8, UV) and GD/INOX Category 2 fallback."""
    from pricing_engine.matcher import (
        CATEGORY_1_DIRECT_MATCH_MODIFIERS,
        referee_match,
    )

    # 1. Category 1 list verification: Strictly contains only SD
    assert {"SD"} == CATEGORY_1_DIRECT_MATCH_MODIFIERS

    # 2. Washing Machine: Dynamic code right after model (e.g. DWT-11467 ES)
    # A. Exact match when candidate has ES
    dec_es_match = referee_match(
        "DWT-11467 ES",
        "Dawlance DWT-11467 ES Automatic Washing Machine",
        brand="Dawlance",
    )
    assert dec_es_match.is_match is True
    assert dec_es_match.is_base_match is False

    # B. Candidate omits ES -> Fallback to base model
    dec_es_omit = referee_match(
        "DWT-11467 ES",
        "Dawlance DWT-11467 Automatic Washing Machine",
        brand="Dawlance",
    )
    assert dec_es_omit.is_match is False
    assert dec_es_omit.is_base_match is True
    assert dec_es_omit.missing_modifier == "ES"

    # C. Candidate has different post-model code (ES8) -> Hard mismatch
    dec_es_diff = referee_match(
        "DWT-11467 ES",
        "Dawlance DWT-11467 ES8 Automatic Washing Machine",
        brand="Dawlance",
    )
    assert dec_es_diff.is_match is False
    assert dec_es_diff.is_base_match is False

    # 3. Hardware Door Finish: GD and INOX (Category 2 fallback rule: mila toh lelon, nahi mila toh fallback)
    # A. Target GD vs Candidate GD -> Full Match ("mila toh lelon")
    dec_gd_match = referee_match(
        "7950 Glass Door",
        "Dawlance 7950 GD Refrigerator",
        brand="Dawlance",
    )
    assert dec_gd_match.is_match is True
    assert dec_gd_match.is_base_match is False

    # B. Target GD vs Candidate Omitted GD -> Fallback to base model ("nahi mila toh fallback")
    dec_gd_omit = referee_match(
        "7950 Glass Door",
        "Dawlance 7950 Refrigerator",
        brand="Dawlance",
    )
    assert dec_gd_omit.is_match is False
    assert dec_gd_omit.is_base_match is True
    assert dec_gd_omit.missing_modifier == "GD"

    # C. Target INOX vs Candidate INOX -> Full Match ("mila toh lelon")
    dec_inox_match = referee_match(
        "7950 Inox",
        "Dawlance 7950 Inox Refrigerator",
        brand="Dawlance",
    )
    assert dec_inox_match.is_match is True
    assert dec_inox_match.is_base_match is False

    # D. Target INOX vs Candidate Omitted INOX -> Fallback to base model ("nahi mila toh fallback")
    dec_inox_omit = referee_match(
        "7950 Inox",
        "Dawlance 7950 Refrigerator",
        brand="Dawlance",
    )
    assert dec_inox_omit.is_match is False
    assert dec_inox_omit.is_base_match is True
    assert dec_inox_omit.missing_modifier == "INOX"

    # E. Target GD vs Candidate INOX -> Opposing finish collision
    dec_finish_col = referee_match(
        "7950 Glass Door",
        "Dawlance 7950 Inox Refrigerator",
        brand="Dawlance",
    )
    assert dec_finish_col.is_match is False
    assert dec_finish_col.is_base_match is False
    assert "Hardware finish collision" in dec_finish_col.reason


def test_dynamic_post_model_arbitrary_codes_category2() -> None:
    """Validate arbitrary post-model variant codes (e.g. 4907 IFGA vs IPPA vs Base) with zero hardcoding."""
    from pricing_engine.matcher import referee_match

    # 1. 4907 IFGA vs 4907 IPPA -> Hard Mismatch (Category 2 collision)
    dec_col = referee_match(
        "Dawlance 4907 IFGA Refrigerator",
        "Dawlance 4907 IPPA Refrigerator",
        brand="Dawlance",
    )
    assert dec_col.is_match is False
    assert dec_col.is_base_match is False
    assert "Hardware capability mismatch" in dec_col.reason

    # 2. 4907 IFGA vs 4907 IFGA -> Full Exact Match
    dec_match = referee_match(
        "Dawlance 4907 IFGA Refrigerator",
        "Dawlance 4907 IFGA Refrigerator",
        brand="Dawlance",
    )
    assert dec_match.is_match is True
    assert dec_match.is_base_match is False

    # 3. 4907 IFGA Target vs 4907 Omitted Candidate -> Fallback to Base Model ("nahi mila toh fallback")
    dec_fallback = referee_match(
        "Dawlance 4907 IFGA Refrigerator",
        "Dawlance 4907 Refrigerator",
        brand="Dawlance",
    )
    assert dec_fallback.is_match is False
    assert dec_fallback.is_base_match is True
    assert dec_fallback.missing_modifier == "IFGA"

    # 4. 4907 Base Target vs 4907 IFGA Upgraded Candidate -> Hard Mismatch
    dec_upgraded = referee_match(
        "Dawlance 4907 Refrigerator",
        "Dawlance 4907 IFGA Refrigerator",
        brand="Dawlance",
    )
    assert dec_upgraded.is_match is False
    assert dec_upgraded.is_base_match is False
    assert "Hardware capability mismatch" in dec_upgraded.reason

    # 5. Gree 24 HDZ UV vs Gree 24 HDZ -> Fallback to Base Model with UV warning
    dec_hdz_uv_base = referee_match(
        "Gree 24 HDZ UV Inverter Split AC",
        "Gree 24 HDZ Inverter Split AC",
        brand="Gree",
    )
    assert dec_hdz_uv_base.is_match is False
    assert dec_hdz_uv_base.is_base_match is True
    assert dec_hdz_uv_base.missing_modifier == "UV"

    # 6. Gree 24 HDZ UV vs Gree 24 HDZ UV -> Full Exact Match
    dec_hdz_uv_exact = referee_match(
        "Gree 24 HDZ UV Inverter Split AC",
        "Gree 24 HDZ UV Inverter Split AC",
        brand="Gree",
    )
    assert dec_hdz_uv_exact.is_match is True
    assert dec_hdz_uv_exact.is_base_match is False

    # 7. Gree 24 HDZ (Base) vs Gree 24 HDZ UV (Upgraded) -> Hard Mismatch
    dec_hdz_extra_uv = referee_match(
        "Gree 24 HDZ Inverter Split AC",
        "Gree 24 HDZ UV Inverter Split AC",
        brand="Gree",
    )
    assert dec_hdz_extra_uv.is_match is False
    assert dec_hdz_extra_uv.is_base_match is False
    assert "Hardware capability mismatch" in dec_hdz_extra_uv.reason
````

## File: tests/test_simulation.py
````python
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from pricing_engine.models import ScrapedOffer, ScrapeResult
from pricing_engine.pipeline import run_pipeline

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _get_fixture(filename: str) -> Path:
    p = FIXTURES_DIR / filename
    if p.exists():
        return p
    return Path(filename)


def test_simulation_haier_washing_machine_pipeline() -> None:
    """Run full E2E pipeline simulation on real Haier Washing Machine catalog."""
    input_csv = _get_fixture("Haier_Washing_Machines_Uploading_and_Price.csv")
    assert input_csv.exists()

    df_full = pd.read_csv(input_csv)
    # Take first 5 models representing Front Load, Top Load, and Tub series
    sample_df = df_full.head(5).copy()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_input = Path(tmp_dir) / "sample_haier_input.csv"
        tmp_output = Path(tmp_dir) / "sample_haier_output.csv"
        sample_df.to_csv(tmp_input, index=False)

        # Mock scraped offers with realistic marketplace competitors
        mock_alfa_offers = ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name="Official Alfa Partner",
                    price=98500.0,
                    is_sold_out=False,
                    raw_title="Haier Automatic Washing Machine 120-826S6 GC Glass Door",
                ),
                ScrapedOffer(
                    vendor_name="Market Seller B",
                    price=99999.0,
                    is_sold_out=False,
                    raw_title="Haier 120-826S6 Glass Door",
                ),
            ],
            is_success=True,
            status_code=200,
        )

        mock_digi_offers = ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name="Faysal Digi Merchant",
                    price=96999.0,
                    is_sold_out=False,
                    raw_title="Haier Automatic Washing Machine 120-826S6 GC",
                )
            ],
            is_success=True,
            status_code=200,
        )

        async def _run() -> None:
            with (
                patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_alfa_offers),
                patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_digi_offers),
            ):
                out_df = await run_pipeline(
                    input_path=tmp_input,
                    output_path=tmp_output,
                    concurrency=2,
                    verbose=False,
                )

                assert len(out_df) == 5
                assert tmp_output.exists()

                # Verify all required schema columns are present
                required_cols = [
                    "S.NO",
                    "Brand",
                    "Name ",
                    "Shipping Estimate",
                    "Total Without Profit",
                    "Calculation",
                    "Minimum Price Alfa",
                    "Maximum Price Alfa",
                    "Final Price Alfa",
                    "Final Price Digi",
                    "Alfa Real Profit",
                    "Digi Real Profit",
                    "Alfa Reason",
                    "Digi Reason",
                ]
                for col in required_cols:
                    assert col in out_df.columns, f"Missing output column: {col}"

                # Verify prices are formatted as pure integers without float drift
                for p in out_df["Final Price Alfa"].dropna():
                    if str(p).strip():
                        assert "." not in str(p), f"Price contained float decimal: {p}"

        asyncio.run(_run())


def test_simulation_gree_ac_pipeline_two_tier_switch() -> None:
    """Run E2E pipeline simulation on Gree AC catalog validating two-tier 10% -> 8% switch."""
    input_csv = _get_fixture("Gree_Uploading_on_DigiMall_and_Price.csv")
    assert input_csv.exists()

    df_full = pd.read_csv(input_csv)
    sample_df = df_full.head(3).copy()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_input = Path(tmp_dir) / "sample_gree_input.csv"
        tmp_output = Path(tmp_dir) / "sample_gree_output.csv"
        sample_df.to_csv(tmp_input, index=False)

        # Simulate competitive scenario triggering 8% bank rate switch
        mock_alfa = ScrapeResult(offers=[], is_success=True, status_code=200)
        mock_digi = ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name="Lahore Aircon",
                    price=158000.0,
                    is_sold_out=False,
                    raw_title="Gree Inverter AC 1.5 Ton GS-18PITH11W",
                )
            ],
            is_success=True,
            status_code=200,
        )

        async def _run() -> None:
            with (
                patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_alfa),
                patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_digi),
            ):
                out_df = await run_pipeline(
                    input_path=tmp_input,
                    output_path=tmp_output,
                    concurrency=2,
                    verbose=False,
                )

                assert len(out_df) == 3
                # Verify that commission rate is explicitly tagged
                assert "Digi Effective Commision" in out_df.columns
                for comm in out_df["Digi Effective Commision"].dropna():
                    assert comm in ("10.00%", "8.00%")

        asyncio.run(_run())


def test_simulation_stock_holding_report_cross_category_and_risk_alerts() -> None:
    """Run E2E simulation across multi-category appliances (Refrigerators, Microwave, TV) verifying risk alerts."""
    multi_category_data = pd.DataFrame(
        [
            {
                "S.NO": 1,
                "Brand": "Dawlance",
                "Category": "REFRIGERATOR",
                "Name ": "Dawlance 9170 WB Chrome Refrigerator",
                "Length": 60,
                "Width": 65,
                "Height": 160,
                "Net Price": 85000,
                "Profit": 4000,
            },
            {
                "S.NO": 2,
                "Brand": "Dawlance",
                "Category": "MICROWAVE_OVEN",
                "Name ": "Dawlance DW-MD7 Microwave Oven 20L",
                "Length": 45,
                "Width": 35,
                "Height": 30,
                "Net Price": 22000,
                "Profit": 1500,
            },
            {
                "S.NO": 3,
                "Brand": "TCL",
                "Category": "LED",
                "Name ": "TCL 50S80EUX 4K UHD Smart LED TV 50 INCH",
                "Length": 120,
                "Width": 15,
                "Height": 75,
                "Net Price": 95000,
                "Profit": 5000,
            },
        ]
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_input = Path(tmp_dir) / "sample_stock_input.csv"
        tmp_output = Path(tmp_dir) / "sample_stock_output.csv"
        multi_category_data.to_csv(tmp_input, index=False)

        mock_alfa = ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name="Seller A",
                    price=92000.0,
                    is_sold_out=False,
                    raw_title="Dawlance 9170 WB Refrigerator",
                )
            ],
            is_success=True,
            status_code=200,
        )
        mock_digi = ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name="Seller B",
                    price=25000.0,
                    is_sold_out=False,
                    raw_title="Dawlance DW-MD7 Microwave",
                )
            ],
            is_success=True,
            status_code=200,
        )

        async def _run() -> None:
            with (
                patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_alfa),
                patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_digi),
            ):
                out_df = await run_pipeline(
                    input_path=tmp_input,
                    output_path=tmp_output,
                    concurrency=2,
                    verbose=False,
                )

                assert len(out_df) == 3
                assert "Alfa Risk Alert" in out_df.columns
                assert "Digi Risk Alert" in out_df.columns

                for alert in out_df["Alfa Risk Alert"].dropna():
                    assert alert in (
                        "NONE",
                        "THIN_BUFFER",
                        "SAFE_FALLBACK",
                        "SERVER_DOWN",
                        "NEGATIVE_MARGIN",
                    )

                # Verify clean output without ANSI color leakage
                for text in out_df["Alfa Reason"].dropna():
                    assert "\x1b[" not in str(text), (
                        "ANSI color escape leaked into CSV reason string"
                    )

        asyncio.run(_run())
````

## File: .gitignore
````
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
build/
dist/
*.egg-info/

# Environment & Secrets
.env
.env.*
.env.local
.env.*.local
!.env.example
*.pem
*.key

# Virtual Environments
.venv
env/
venv/
ENV/

# Testing & Coverage
.pytest_cache/
.coverage
htmlcov/

# Tooling Caches
.ruff_cache/
.mypy_cache/

# IDE & OS files
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store
.agents

# Data Pipeline
data/outputs/*.csv
!data/outputs/.gitkeep
!data/inputs/template.csv
````

## File: index.py
````python
"""AlfaMall & DigiMall Dynamic Repricing Automation Engine.

Entrypoint script for high-speed dynamic repricing pipeline.
Executes concurrent price discovery against direct backend search APIs,
applies strict variant matching, and computes winning psychological prices.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pricing_engine.pipeline import run_pipeline

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

console = Console()


def parse_args() -> argparse.Namespace:
    """Parse command line options."""
    parser = argparse.ArgumentParser(
        description="Dynamic Repricing Automation Engine for AlfaMall & DigiMall"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=None,
        help="Input catalog CSV file or directory (default: scan data/inputs/)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output repriced CSV file (default: structured export to data/outputs/)",
    )
    parser.add_argument(
        "-b",
        "-a",
        "--batch",
        action="store_true",
        help="Batch process all catalog CSV files in data/inputs/",
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=3,
        help="Maximum concurrent product search requests (default: 3)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress visual 90-char terminal audit cards",
    )
    return parser.parse_args()


def find_input_catalogs(inputs_dir: Path = Path("data/inputs")) -> list[Path]:
    """Scan directory for catalog CSV files, excluding templates."""
    if not inputs_dir.is_dir():
        return []
    return sorted(
        p
        for p in inputs_dir.glob("*.csv")
        if not p.name.lower().startswith("template") and not p.name.endswith(".gitkeep")
    )


def interactive_catalog_picker(catalogs: list[Path]) -> list[Path] | None:
    """Display a Rich interactive catalog picker and return user selection."""
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Option", style="bold yellow", width=8)
    table.add_column("Catalog File", style="green")

    for idx, cat in enumerate(catalogs, start=1):
        table.add_row(f"[{idx}]", cat.name)
    table.add_row("[A]", "Run All Catalogs (Batch)")
    table.add_row("[Q]", "Quit")

    panel = Panel(
        table,
        title="[bold cyan]📦 Select Catalog to Reprice[/bold cyan]",
        border_style="cyan",
        expand=False,
    )
    console.print(panel)

    try:
        choice = input(f"Select option [1-{len(catalogs)}, A, Q]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Operation cancelled.[/yellow]")
        return None

    if choice.lower() in ("q", "quit", "exit"):
        return None
    if choice.lower() in ("a", "all"):
        return catalogs
    try:
        num = int(choice)
        if 1 <= num <= len(catalogs):
            return [catalogs[num - 1]]
    except ValueError:
        pass

    console.print(f"[bold red]❌ Invalid selection: '{choice}'. Aborting.[/bold red]")
    return None


async def main() -> int:
    """Main asynchronous pipeline entrypoint."""
    args = parse_args()
    input_path: Path | None = args.input
    output_path: Path | None = args.output
    target_catalogs: list[Path] = []

    if args.batch:
        target_catalogs = find_input_catalogs()
        if not target_catalogs:
            console.print(
                "[bold red]❌ No catalog CSV files found in 'data/inputs/'.[/bold red]"
            )
            console.print(
                "Please place your catalog CSVs in 'data/inputs/' or use the -i flag."
            )
            return 1
    elif input_path is not None:
        if not input_path.exists():
            console.print(
                f"\n[bold red]❌ Error: Input catalog file not found: '{input_path}'[/bold red]"
            )
            console.print(
                "Please ensure the CSV file exists or drop it into data/inputs/."
            )
            return 1
        target_catalogs = [input_path]
    else:
        # No input provided: scan data/inputs/
        catalogs = find_input_catalogs()
        if not catalogs:
            console.print(
                "[bold red]❌ No catalog CSV files found in 'data/inputs/'.[/bold red]"
            )
            console.print(
                "Please place your catalog CSV in 'data/inputs/' or specify with -i/--input."
            )
            return 1

        if len(catalogs) == 1:
            console.print(
                f"[bold cyan]ℹ️  Found 1 catalog in data/inputs/: [green]{catalogs[0].name}[/green]. Auto-selecting.[/bold cyan]"
            )
            target_catalogs = [catalogs[0]]
        else:
            # 2+ catalogs found: interactive picker if TTY, else fallback
            if sys.stdin.isatty():
                chosen = interactive_catalog_picker(catalogs)
                if chosen is None:
                    return 0
                target_catalogs = chosen
            else:
                console.print(
                    f"[bold yellow]⚠️  Non-interactive terminal detected. Auto-selecting first catalog: {catalogs[0].name}[/bold yellow]"
                )
                target_catalogs = [catalogs[0]]

    had_errors = False
    for cat in target_catalogs:
        try:
            effective_out = output_path if len(target_catalogs) == 1 else None
            await run_pipeline(
                input_path=cat,
                output_path=effective_out,
                concurrency=args.concurrency,
                verbose=not args.quiet,
                use_structured_export=(effective_out is None),
            )
        except Exception as exc:
            console.print(
                f"\n[bold red]❌ Pipeline execution error for '{cat.name}': {exc}[/bold red]",
                file=sys.stderr,
            )
            had_errors = True

    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
````

## File: pyproject.toml
````toml
[project]
name = "dynamic-repricing-engine"
version = "0.1.0"
description = "Universal Dynamic Repricing Engine for Pakistani e-commerce platforms (AlfaMall & DigiMall)"
requires-python = ">=3.10"
dependencies = [
    "curl_cffi>=0.7.0",
    "pandas>=2.0.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "mypy>=1.9.0",
    "ruff>=0.3.0",
]

[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra -q --strict-markers"
testpaths = ["tests"]
pythonpath = ["."]
markers = [
    "asyncio: mark test as an asyncio coroutine",
]

[tool.mypy]
python_version = "3.12"
strict = true
disallow_any_generics = false
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
show_error_codes = true

[[tool.mypy.overrides]]
module = ["curl_cffi.*", "pandas.*"]
ignore_missing_imports = true

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "UP",  # pyupgrade
    "C4",  # flake8-comprehensions
    "SIM", # flake8-simplify
]
ignore = [
    "E501", # line too long (handled by formatter)
]
````

## File: pricing_engine/calculator.py
````python
import math

from pricing_engine.models import CostFloors

# Standard psychological price endings ordered from highest to lowest margin
PSYCHOLOGICAL_ENDINGS: tuple[int, ...] = (999, 899, 799, 499, 299, 199, 99)


def calculate_volumetric_weight(
    length: float, width: float, height: float, divisor: float = 5000.0
) -> float:
    """Calculate volumetric weight in kilograms.

    Args:
        length: Package length in centimeters.
        width: Package width in centimeters.
        height: Package height in centimeters.
        divisor: Courier volumetric divisor (default 5000.0).

    Returns:
        Volumetric weight in kilograms.
    """
    if divisor <= 0:
        raise ValueError("Divisor must be greater than zero.")
    return (length * width * height) / divisor


def calculate_shipping_estimate(volumetric_weight: float, rate_per_kg: float = 70.0) -> float:
    """Calculate courier shipping estimate based on volumetric weight.

    Args:
        volumetric_weight: Volumetric weight in KG.
        rate_per_kg: Courier rate per KG (default 70.0 PKR).

    Returns:
        Estimated shipping cost rounded to 2 decimal places.
    """
    return round(volumetric_weight * rate_per_kg, 2)


def calculate_cost_base(net_price: float, shipping: float) -> float:
    """Calculate the base landed cost before marketplace commission or profit.

    Args:
        net_price: Vendor wholesale/purchase price.
        shipping: Courier delivery cost estimate.

    Returns:
        Total base cost.
    """
    return round(net_price + shipping, 2)


def calculate_floors(cost_base: float, min_profit: float = 500.0) -> CostFloors:
    """Calculate breakeven costs and absolute minimum profit floors.

    Args:
        cost_base: Total landed cost base.
        min_profit: Minimum profit guarantee in PKR (default 500.0).

    Returns:
        CostFloors object with 0% margin and hard floors (+500 PKR) for Alfa and Digi.
    """
    zero_margin_10 = cost_base / 0.90
    zero_margin_8 = cost_base / 0.92
    floor_alfa = (cost_base + min_profit) / 0.90
    floor_digi_10 = (cost_base + min_profit) / 0.90
    floor_digi_8 = (cost_base + min_profit) / 0.92

    return CostFloors(
        cost_base=cost_base,
        zero_margin_10=zero_margin_10,
        zero_margin_8=zero_margin_8,
        floor_alfa=floor_alfa,
        floor_digi_10=floor_digi_10,
        floor_digi_8=floor_digi_8,
    )


def calculate_baseline(cost_base: float, target_profit: float) -> float:
    """Calculate standard baseline price for comparison.

    Args:
        cost_base: Landed cost base.
        target_profit: Target profit margin from input catalog.

    Returns:
        Baseline catalog price at standard 10% commission.
    """
    return (cost_base + target_profit) / 0.90


def find_winning_psychological_price(
    floor_min: float,
    competitor_price: float,
    undercut_buffer: float = 100.0,
    max_ceiling: float | None = None,
) -> int | None:
    """Determine the optimal winning price strictly undercutting the competitor.

    Constraint:
        floor_min <= Our Price < competitor_price (and <= max_ceiling if specified)

    Prices prioritize standard psychological thresholds (.999, .899, .799, .499, .299, .199, .099).

    Args:
        floor_min: Absolute minimum price floor (+500 PKR profit guaranteed).
        competitor_price: The lowest viable competitor price to undercut.
        undercut_buffer: Safety undercut margin below competitor (default 100.0 PKR).
        max_ceiling: Optional ceiling price cap (e.g. from maximum profit limit).

    Returns:
        Optimal integer price if profitable, otherwise None.
    """
    # Strict win requirement: our price must be strictly lower than competitor
    if competitor_price <= floor_min:
        return None

    floor_ceil = math.ceil(floor_min)
    if floor_ceil >= competitor_price:
        return None

    # Calculate effective maximum ceiling that strictly beats competitor
    target_ceiling = competitor_price - undercut_buffer
    if max_ceiling is not None:
        target_ceiling = min(target_ceiling, max_ceiling)

    if target_ceiling < floor_ceil:
        effective_max = int(competitor_price - 1.0)
        if max_ceiling is not None:
            effective_max = min(effective_max, int(max_ceiling))
    else:
        effective_max = int(target_ceiling)

    if effective_max < floor_ceil:
        effective_max = floor_ceil

    # 1. Search for standard psychological endings in allowed range [floor_ceil, effective_max]
    base_k = int(effective_max // 1000) * 1000
    candidates: list[int] = []

    for b in (base_k, base_k - 1000, base_k - 2000):
        for e in PSYCHOLOGICAL_ENDINGS:
            p = b + e
            if floor_ceil <= p <= effective_max and p < competitor_price:
                candidates.append(p)

    if candidates:
        return max(candidates)

    # 2. Clean 50-step round numbers (e.g. 173,050, 176,850)
    candidate_50 = (effective_max // 50) * 50
    if floor_ceil <= candidate_50 < competitor_price:
        return candidate_50

    # 3. Clean 10-step round numbers (e.g. 173,040, 173,060)
    candidate_10 = (effective_max // 10) * 10
    if floor_ceil <= candidate_10 < competitor_price:
        return candidate_10

    # 4. Clean 5-step round numbers (e.g. 173,045)
    candidate_5 = (effective_max // 5) * 5
    if floor_ceil <= candidate_5 < competitor_price:
        return candidate_5

    # 5. Fallback: match to effective_max or floor_ceil
    if floor_ceil <= effective_max < competitor_price:
        return effective_max

    if floor_ceil < competitor_price:
        return floor_ceil

    return None


def get_monopoly_psychological_price(raw_target: float) -> int:
    """Calculate attractive psychological price when 0 competitors exist.

    Args:
        raw_target: Calculated target price (cost_base + monopoly_profit) / 0.90.

    Returns:
        Psychological price ending in 999 or 499.
    """
    val = round(raw_target)
    base = (val // 1000) * 1000
    remainder = val % 1000
    if remainder >= 500:
        return base + 999
    return base + 499


def get_fallback_psychological_price(
    cost_base: float,
    floor_min: float,
    payout_rate: float,
    profit_target: float = 1500.0,
) -> int:
    """Calculate attractive psychological price when all market competitors are selling at a loss.

    Ensures the price is strictly above the minimum floor, delivers at least profit_target,
    and always terminates in standard retail .999 promo ending.

    Args:
        cost_base: Landed cost base.
        floor_min: Absolute minimum floor.
        payout_rate: Bank payout rate (e.g. 0.92 for Digi, 0.90 for Alfa).
        profit_target: Minimum target profit (default 1500.0 PKR).

    Returns:
        Attractive integer psychological price ending strictly in 999.
    """
    raw_target = (cost_base + profit_target) / payout_rate
    effective_min = max(raw_target, floor_min)
    base = (int(effective_min) // 1000) * 1000
    candidate = base + 999
    if candidate < effective_min:
        candidate = (base + 1000) + 999
    return candidate


def calculate_adaptive_target_price(
    floor_min: float,
    competitor_price: float,
    undercut_buffer: float = 100.0,
    cost_base: float | None = None,
    payout_rate: float = 0.90,
    large_gap_profit_target: float = 10000.0,
    min_buffer_3_zeros: float = 1000.0,
) -> float:
    """Calculate an adaptive target price based on the gap between floor and competitor.

    Tiers:
    - Tier 5 (Gap < 800 PKR, e.g. <= 799): Closest Rs. 100 undercut (or competitor - 1 if tight).
    - Tier 4 (800 <= Gap < 1,500 PKR, e.g. 800, 900, 1000, 1200): Rs. 200 undercut.
    - Tier 3 (1,500 <= Gap < 2,000 PKR, e.g. 1500, 1800, 1900): Rs. 500 customer discount (competitor - 500), min 1,000 buffer.
    - Tier 2 (2,000 <= Gap < 10,000 PKR, 3 Zeros): Proportional 50% split with min 1,000 PKR buffer.
    - Tier 1 (Gap >= 10,000 PKR, 4 Zeros): Option A sweet spot capped around ~10,000 target profit.

    Args:
        floor_min: Minimum selling price floor (+500 PKR profit guaranteed).
        competitor_price: Viable competitor price.
        undercut_buffer: Default undercut margin below competitor (default 100.0).
        cost_base: Optional landed cost base for exact profit targeting.
        payout_rate: Marketplace payout multiplier (e.g. 0.92 for Digi, 0.90 for Alfa).
        large_gap_profit_target: Target profit cap for large gaps (default 10,000.0).
        min_buffer_3_zeros: Minimum profit buffer above floor for 3 zeros (default 1,000.0).

    Returns:
        Target ceiling price before psychological rounding.
    """
    gap = competitor_price - floor_min

    if gap <= 0:
        return competitor_price - undercut_buffer

    # Tier 5: Gap < 800 PKR (e.g. <= 799) -> Closest Rs. 100 undercut (or competitor - 1 if tight)
    if gap < 800.0:
        if gap < 100.0:
            return competitor_price - 1.0
        return competitor_price - 100.0

    # Tier 4: Gap 800 to 1,499 PKR (e.g. 800, 900, 1000, 1200) -> Rs. 200 undercut
    if gap < 1500.0:
        return max(floor_min, competitor_price - 200.0)

    # Tier 3: Gap 1,500 to 1,999 PKR (e.g. 1500, 1800, 1900) -> Rs. 500 discount, min 1,000 buffer
    if gap < 2000.0:
        target = competitor_price - 500.0
        return max(floor_min + 1000.0, target)

    # Tier 2: Gap 2,000 to 9,999 PKR (3 Zeros) -> 50% split with min 1,000 buffer
    if gap < 10000.0:
        buffer = max(gap * 0.50, min_buffer_3_zeros)
        return floor_min + buffer

    # Tier 1: Gap >= 10,000 PKR (4 Zeros) -> Option A: Profit-targeted sweet spot (~10k)
    competitor_ceiling = competitor_price - undercut_buffer
    if cost_base is not None and payout_rate > 0:
        target_profit_price = (cost_base + large_gap_profit_target) / payout_rate
        floor_k = (int(floor_min) // 1000) * 1000
        next_999 = (floor_k + 999) if (floor_k + 999) >= floor_min else (floor_k + 1999)
        bounded_target = max(target_profit_price, float(next_999))
        return min(competitor_ceiling, bounded_target)

    # Fallback to 50% midpoint if cost_base is not provided
    return floor_min + (gap * 0.50)
````

## File: AGENTS.md
````markdown
# AlfaMall & DigiMall Dynamic Repricing Engine — AI Agent Technical Handbook

Automated, high-speed dynamic repricing pipeline for Pakistani e-commerce platforms (**AlfaMall** and **DigiMall / Faysal Bank**). It queries direct backend search APIs, cleans variant mismatches and out-of-stock items, and calculates winning psychological prices under strict profit floors.

---

## 1. System Identity & Mission

- **Target Market**: Pakistani e-commerce retail (Consumer Electronics, Home Appliances, Split ACs, Washing Machines, Refrigerators, LEDs).
- **Core Philosophy**:
  1. **Zero Browser/Selenium Overhead**: Use direct HTTP JSON endpoints via `curl_cffi` (Chrome 120 impersonation) for sub-second responses and zero IP blocking.
  2. **Variant Match Protection**: Strict SKU model extraction. Never allow cross-variant or cross-color mispricing (e.g. `12AITH21W` White must never match `12AITH21B` Black; 8kg washers must never match 10kg washers).
  3. **Guaranteed Profit Floors**: Hard mathematical floor (+Rs. 500 minimum net profit guarantee). Never sell at a loss regardless of competitor price wars.
  4. **Two-Tier Bank Commission Arbitrage**: Leverage DigiMall's special 8% Faysal Bank rate to capture extra profit or win tough competition against competitors paying 10%.
  5. **Deterministic Data Integrity**: Guaranteed Column 1 `S.NO`, pure integer price outputs (zero `.0` float drift), and ANSI-free risk alerts.
  6. **Strict DRY Concept & Generic Dynamic Algorithms (Zero Category & Brand Hardcoding)**:
     - **Zero Static Lists**: Never hardcode category conditionals (`if 'MINI BAR'`), static brand lists (`["DAWLANCE", "GREE", ...]`), or static prefix sets (`(HWM|DWT|DW|WM|...)`) in `matcher.py` or anywhere in the engine.
     - **Dynamic SKU Prefixes**: All SKU prefixes (e.g. `DMB`, `HRF`, `HWM`, `GS`, `PR`, `WF`) must be extracted dynamically via generic regex (`\b([A-Za-z]{2,4})[- ]?{stem_num}`).
     - **Dynamic Initialism Referee**: 2-letter modifier tags (e.g. `SD` vs `Double Door`, `FL` vs `Top Load`) must be matched and collided dynamically via word boundaries and initialisms without static collision dictionaries.
     - **Dynamic Brand-Initial Verification**: Numeric stems must be validated against brand initials dynamically (`{brand[0]}[a-z]{1,3}[- ]?{model}`).
     - **Single Source of Truth**: Data mappings (e.g. AC capacity codes) must be defined once and referenced everywhere.
     - **Strict Ingestion Validation**: Catalogs must provide valid brands; guessing brands from title strings is strictly forbidden.

---

## 2. Core Logistics & Cost Math

### Mathematical Formulas

- **Volumetric Weight**:
  $$\text{Volumetric Weight (KG)} = \frac{\text{Length (cm)} \times \text{Width (cm)} \times \text{Height (cm)}}{5000}$$
- **Courier Shipping Estimate**:
  $$\text{Shipping Estimate (PKR)} = \text{Volumetric Weight} \times 70.0\text{ PKR (Standard Zone Courier Rate)}$$
- **Cost Base**:
  $$\text{Cost Base} = \text{Net Purchase Price} + \text{Shipping Estimate}$$
- **Total Without Profit (0% Margin Breakeven)**:
  - AlfaMall (10% Commission): $\frac{\text{Cost Base}}{0.90}$
  - DigiMall Leverage (8% Commission): $\frac{\text{Cost Base}}{0.92}$
- **Baseline Catalog Calculation**:
  $$\text{Baseline} = \frac{\text{Cost Base} + \text{Profit Target}}{0.90}$$
  *(Profit Target defaults to Rs. 500 if omitted in catalog)*
- **Absolute Hard Profit Floors (+Rs. 500 Net Profit Guarantee)**:
  - $\text{Floor}_{\text{Alfa}} = \frac{\text{Cost Base} + 500}{0.90}$
  - $\text{Floor}_{\text{Digi\_10}} = \frac{\text{Cost Base} + 500}{0.90}$
  - $\text{Floor}_{\text{Digi\_8}} = \frac{\text{Cost Base} + 500}{0.92}$
- **Monopoly Pricing (Zero Competitors in Market)**:
  $$\text{Monopoly Price} = \frac{\text{Cost Base} + 4000}{0.90} \longrightarrow \text{Psychological Threshold}$$

---

## 3. Pricing Decision Logic & Rules

### Strict Winning Condition
$$\text{Floor} \le \text{Our Final Price} < \text{Lowest Viable Competitor}$$
Our price must **always** be strictly lower than the lowest viable competitor to win the buy box.

### Retail Psychological Thresholds
Prices must end strictly in standard retail psychological endings:
- Available endings: `.999`, `.899`, `.799`, `.499`, `.299`, `.199`, `.099`.
- *Example*: If undercut calculation gives `72,877` and floor is `72,500`, final price is snapped to `72,899` or `72,799`.

### Platform Decision Engines

1. **AlfaMall (Strict 10% Commission)**:
   - Discard all scraped offers below $\text{Floor}_{\text{Alfa}}$ (sub-floor loss-makers).
   - If viable competitors exist: Undercut the lowest viable competitor $\ge \text{Floor}_{\text{Alfa}}$.
   - If lowest competitor is excessively inflated above baseline calculation: Apply **Capped Sweet-Spot** rule to protect high sales velocity.
   - If 0 competitors found: Set **Monopoly Price** (+Rs. 4,000 margin with psychological ending).
   - If all competitors are below floor: Fall back safely to $\text{Floor}_{\text{Alfa}}$ or return `NaN` with `SAFE_FALLBACK` alert.

2. **DigiMall (Two-Tier 10% $\rightarrow$ 8% Faysal Bank Switch)**:
   - **Tier 1 (Default 10% Tier)**: If the lowest competitor is $\ge \text{Floor}_{\text{Digi\_10}}$, undercut and win at 10% tier. Bank only charges 8%, capturing an extra 2% bank spread profit. Record `Digi Effective Commision` as `10.00%`.
   - **Tier 2 (Emergency 8% Switch)**: If lowest competitor is below $\text{Floor}_{\text{Digi\_10}}$ but $\ge \text{Floor}_{\text{Digi\_8}}$, switch to 8% bank rate, undercut to win. Record `Digi Effective Commision` as `8.00%`.
   - **Upper Band Undercut**: If lowest competitor is below $\text{Floor}_{\text{Digi\_8}}$, drop them and attempt to undercut the next higher viable competitor at 8%.
   - **Zero Competitors**: Apply Monopoly pricing (+Rs. 4,000 margin).

### Risk Alert Classifications
- `NONE`: Optimal healthy winning price.
- `THIN_BUFFER`: Real net profit is $< \text{Rs. } 700$ (close to floor).
- `SAFE_FALLBACK`: Market is entirely below floor; defaulted safely to floor price.
- `CAPPED_SWEET_SPOT`: Competitor price was artificially inflated; price capped to ensure conversion.
- `SERVER_DOWN`: Upstream platform API timed out or failed (HTTP non-200).

---

## 4. Module Architecture & Code Contracts

```
pricing_engine/
├── calculator.py       # Pure math: volumetric weight, shipping, floors, psychological endings
├── matcher.py          # 4-slot model extraction, brand stripping, negative variant filtering
├── scraper.py          # Async JSON endpoints via curl_cffi, 3-tier waterfall, in-memory cache
├── evaluator.py        # AlfaMall & DigiMall decision logic, sweet-spot capping, profit calculations
├── ingestion.py        # CSV catalog loader, 6-column contract validation, S.NO normalization, pre-flight banner
├── exporter.py         # Timestamped + latest CSV dual export, pure-integer formatting, panel rendering
├── pipeline.py         # Concurrency orchestration, asyncio semaphore, Rich terminal cards, S.NO column guarantee
├── models.py           # Strongly typed dataclasses (ProductInput, PlatformPricingResult, ScrapedOffer, etc.)
├── learner.py          # Autonomous search query pattern extraction engine
├── registry.py         # Regex pattern registry (in-memory + Supabase sync)
└── db.py               # Async Supabase client for pattern registry & price history
```

### Component Details

- **`pricing_engine/ingestion.py`**:
  - Function: `ingest_catalog(file_path: Path, render_banner: bool = True) -> tuple[list[ProductInput], IngestionReport]`
  - Strips whitespace globally across headers and string values.
  - Enforces 6 required columns: `Brand`, `Name`, `Net Price`, `Length`, `Width`, `Height`.
  - Supports optional 7th column: `Profit` (defaults to 500.0).
  - Normalizes `S.NO` from all casings (`S.NO`, `S.No`, `sno`, `Serial No`), handles float drift (`1.0` -> `1`), and auto-generates 1-indexed integers if missing.
  - Ignores custom extra columns silently during validation and preserves them in output.

- **`pricing_engine/exporter.py`**:
  - Function: `export_results(df, source_filename, output_dir="data/outputs", timestamp=None, render_panel=True) -> ExportManifest`
  - Creates two output artifacts:
    - `{stem}_repriced_{YYYYMMDD_HHMMSS}.csv` (permanent audit history).
    - `{stem}_repriced_latest.csv` (always-current upload copy).
  - Sanitizes price columns (`PRICE_INT_COLUMNS`) and `S.NO` using `format_export_price()` and `format_export_sno()` to eliminate `.0` float drift.

- **`pricing_engine/pipeline.py`**:
  - Function: `run_pipeline(input_path, output_path=None, concurrency=3, verbose=True, use_structured_export=False, export_dir=Path("data/outputs"))`
  - Reconstructs `out_record` guaranteeing `S.NO` is Column 1.
  - Binds concurrency via `asyncio.Semaphore(concurrency)`.
  - Renders live Rich execution cards and executive summary tables.

- **`index.py`**:
  - CLI entrypoint. Scans `data/inputs/` for CSVs.
  - Guarded with `sys.stdin.isatty()`: Interactive Rich menu when human terminal is detected; automatic non-blocking selection in headless/cron mode.
  - Flags: `-i / --input`, `-o / --output`, `-b / --batch / -a`, `-c / --concurrency`, `-q / --quiet`.

---

## 5. Input & Output Schema Standards

### Input Catalog Contract (`data/inputs/`)
| Column | Type | Required? | Fallback / Behavior |
| :--- | :--- | :--- | :--- |
| `Brand` | `str` | **Required** | Stripped of whitespace |
| `Name` | `str` | **Required** | Product model extracted from title |
| `Net Price` | `float` | **Required** | Purchase price (commas auto-stripped) |
| `Length` | `float` | **Required** | Box length in cm |
| `Width` | `float` | **Required** | Box width in cm |
| `Height` | `float` | **Required** | Box height in cm |
| `Profit` | `float` | Optional | Defaults to `500.0` if empty or missing |
| `S.NO` / `S.No` | `int/str`| Optional | Auto-generates `1, 2, 3...` if omitted |
| *Custom Cols* | `Any` | Optional | Preserved intact in output CSV |

### Output Catalog Contract (`data/outputs/`)
Standardized output column ordering:
1. `S.NO` (Always Column 1, pure integer or SKU string)
2. Original input columns (`Brand`, `Name`, `Net Price`, `Length`, `Width`, `Height`, `Profit`, any custom tags)
3. Calculated pricing columns:
   - `Shipping Estimate`
   - `Commision` (`10.00%`)
   - `Digi Effective Commision` (`10.00%` or `8.00%`)
   - `Total Without Profit` (Cost base breakeven at effective rate)
   - `Calculation` (Baseline target price)
   - `Minimum Price Alfa`, `Maximum Price Alfa`
   - `Minimum Price Digi`, `Maximum Price Digi`
   - `Final Price Alfa`, `Final Price Digi`
   - `Alfa Real Profit`, `Digi Real Profit`
   - `Alfa Reason`, `Digi Reason`
4. Risk Alert columns (Always final two columns):
   - `Alfa Risk Alert`
   - `Digi Risk Alert`

---

## 6. Scraping & Network Architecture

### Direct JSON Endpoints
- **AlfaMall**:
  `https://be.alfamall.com/storefront/search_products?page=1&q={query}&limit=18&storefront=23&storefront_domain=alfamall.com`
- **DigiMall / Faysal Bank**:
  `https://digimall-be.faysalbank.com/storefront/search_products?storefront=23&q={query}&page=1&limit=18`

### Network Guardrails
- **Client**: `curl_cffi.requests.AsyncSession(impersonate="chrome120")`.
- **Waterfall Strategy**: Tier 1 (Exact clean) $\rightarrow$ Tier 2 (Bare stem) $\rightarrow$ Tier 3 (Permutations). Early exit if Tier 1 yields $\ge 2$ candidates.
- **In-Memory Cache**: Run-scoped `(platform, query)` cache to eliminate duplicate network calls for common models.
- **Out-of-Stock Guard**: Offer dropped immediately if `item.get("sold_out") is True`.

---

## 7. Testing Discipline & Quality Gates

The codebase enforces strict test-driven development:
- **Test Suite**: Located in `tests/` (168 passing tests).
- **Test Fixtures**: Isolated in `tests/fixtures/` (`Gree_Uploading_on_DigiMall_and_Price.csv`, `Haier_Washing_Machines_Uploading_and_Price.csv`, `Stock Holding Report 25-Feb-2026.csv`).
- **Commands**:
  ```bash
  pytest -v               # Run complete test suite (must be 100% green)
  ruff check .            # Linting and style check (must have 0 errors)
  ```
- **Regression Protection**: Every bug fix or edge case must have a corresponding test in `tests/test_pipeline_resilience.py` or the appropriate test module.

---

## 8. Phase 2 Roadmap Blueprint: Supabase History & CLI

When implementing Phase 2, follow these exact requirements:

1. **Database Schema (`scripts/setup_supabase.sql`)**:
   - `repricing_runs`: `id (UUID PK)`, `catalog_name (text)`, `total_items (int)`, `created_at (timestamptz)`.
   - `repricing_results`: `id (UUID PK)`, `run_id (FK)`, `brand (text)`, `model (text)`, `product_name (text)`, `net_price (numeric)`, `shipping (numeric)`, `alfa_price (numeric)`, `digi_price (numeric)`, `alfa_profit (numeric)`, `digi_profit (numeric)`, `alfa_risk (text)`, `digi_risk (text)`, `created_at (timestamptz)`.
   - B-tree indexes on `run_id`, `model`, `brand`, and `created_at`.

2. **Persistence Methods (`pricing_engine/db.py`)**:
   - `create_repricing_run(catalog_name: str, total_items: int) -> str | None`
   - `store_repricing_results(run_id: str, results: list[dict[str, Any]]) -> int`
   - `query_runs_by_date(date_str: str) -> list[dict]`
   - `query_results_by_model(model_pattern: str) -> list[dict]`
   - `query_latest_run() -> dict | None`
   - `query_thin_margin_products(max_profit: float) -> list[dict]`
   - **Offline Resilience**: All DB calls must gracefully return empty/None if credentials are missing or Supabase is unreachable. Never block or crash the CSV repricing pipeline.

3. **CLI History Subcommand (`index.py`)**:
   - Subparser: `python index.py history [--latest | --model <pattern> | --date <YYYY-MM-DD> | --profit-below <amount>]`.
   - If run without flags in an interactive terminal, display an interactive Rich query menu.
   - Render results in styled Rich tables with model, date, prices, profits, and risk alert badges.
````

## File: pricing_engine/db.py
````python
import logging
import os
from pathlib import Path
from typing import Any

from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Zero-dependency loader for .env file in workspace root."""
    env_file = Path(".env")
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    k = key.strip()
                    v = val.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


class SupabaseClient:
    """Async connectionless REST client for Supabase Cloud PostgreSQL.

    Adheres to ADR-003:
    - High-speed REST operations (PostgREST).
    - Batch observation ingestion (N+1 protection).
    - Graceful offline degradation when credentials are missing or network fails.
    """

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        _load_env_file()
        if url is None:
            self.url = (
                os.getenv("SUPABASE_URL")
                or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
                or ""
            ).rstrip("/")
        else:
            self.url = url.rstrip("/")

        if key is None:
            self.key = (
                os.getenv("SUPABASE_KEY")
                or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                or os.getenv("SUPABASE_ANON_KEY")
                or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
                or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
                or ""
            )
        else:
            self.key = key

        self.timeout = timeout
        self._session: AsyncSession | None = None

    @property
    def is_configured(self) -> bool:
        """Return True if legitimate Supabase URL and Key are set."""
        return bool(
            self.url
            and self.key
            and self.url.startswith("http")
            and "placeholder" not in self.url.lower()
        )

    def _ensure_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession(impersonate="chrome120")
        return self._session

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    async def fetch_approved_capacities(self, brand: str = "") -> list[dict[str, Any]]:
        """Fetch all approved brand capacity codes.

        Returns:
            List of dicts containing brand, code, tonnage, status.
        """
        if not self.is_configured:
            return []

        endpoint = f"{self.url}/rest/v1/capacity_registry?select=*&status=eq.APPROVED"
        if brand.strip():
            endpoint += f"&brand=eq.{brand.strip().upper()}"

        session = self._ensure_session()
        try:
            resp = await session.get(endpoint, headers=self._headers(), timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            logger.warning("Supabase fetch capacities returned status %d", resp.status_code)
            return []
        except Exception as exc:
            logger.warning("Supabase capacity fetch failed gracefully: %s", exc)
            return []

    async def fetch_approved_synonyms(
        self, brand: str = "", category: str = ""
    ) -> list[dict[str, Any]]:
        """Fetch approved equivalence synonyms with strict category isolation.

        Returns:
            List of dicts containing brand, category, tag, alias, status.
        """
        if not self.is_configured:
            return []

        endpoint = f"{self.url}/rest/v1/synonym_registry?select=*&status=eq.APPROVED"
        if brand.strip():
            endpoint += f"&brand=eq.{brand.strip().upper()}"
        if category.strip():
            endpoint += f"&category=eq.{category.strip().upper()}"

        session = self._ensure_session()
        try:
            resp = await session.get(endpoint, headers=self._headers(), timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            logger.warning("Supabase fetch synonyms returned status %d", resp.status_code)
            return []
        except Exception as exc:
            logger.warning("Supabase synonym fetch failed gracefully: %s", exc)
            return []

    async def record_observations_batch(self, observations: list[dict[str, Any]]) -> int:
        """Batch insert raw market observations with ignore-duplicates resolution.

        Guarantees:
        - Prevents N+1 HTTP calls by inserting observations in bulk.
        - Idempotent: duplicates ignored via database constraints.

        Args:
            observations: List of observation dictionaries.

        Returns:
            Number of recorded observations.
        """
        if not self.is_configured or not observations:
            return 0

        endpoint = (
            f"{self.url}/rest/v1/learning_observations"
            "?on_conflict=brand,category,anchor_model,target_residual,candidate_residual,normalized_merchant"
        )
        session = self._ensure_session()
        headers = self._headers(prefer="resolution=ignore-duplicates")

        try:
            resp = await session.post(
                endpoint, json=observations, headers=headers, timeout=self.timeout
            )
            if resp.status_code in (200, 201, 204):
                if resp.text and resp.text.strip():
                    try:
                        data = resp.json()
                        return len(data) if isinstance(data, list) else len(observations)
                    except Exception:
                        pass
                return len(observations)
            if resp.status_code == 409:
                # 409 Conflict: Existing market observations safely ignored via database constraint
                logger.debug("Supabase batch observations already present (409 duplicates ignored)")
                return len(observations)
            logger.warning("Supabase batch observation insert returned status %d", resp.status_code)
            return 0
        except Exception as exc:
            logger.warning("Supabase batch observation insert failed gracefully: %s", exc)
            return 0
````

## File: tests/test_calculator.py
````python
import math

from pricing_engine.calculator import (
    calculate_adaptive_target_price,
    calculate_baseline,
    calculate_cost_base,
    calculate_floors,
    calculate_shipping_estimate,
    calculate_volumetric_weight,
    find_winning_psychological_price,
    get_fallback_psychological_price,
    get_monopoly_psychological_price,
)


def test_volumetric_weight_calculation() -> None:
    # 100cm x 50cm x 50cm = 250,000 / 5000 = 50.0 KG
    weight = calculate_volumetric_weight(100.0, 50.0, 50.0)
    assert weight == 50.0


def test_shipping_estimate_calculation() -> None:
    # 50.0 KG * 70 PKR/KG = 3500.0 PKR
    shipping = calculate_shipping_estimate(50.0, rate_per_kg=70.0)
    assert shipping == 3500.0


def test_cost_base_calculation() -> None:
    cost_base = calculate_cost_base(net_price=70000.0, shipping=3500.0)
    assert cost_base == 73500.0


def test_calculate_floors() -> None:
    cost_base = 72000.0
    floors = calculate_floors(cost_base=cost_base, min_profit=500.0)

    # 72000 / 0.90 = 80000.0
    assert math.isclose(floors.zero_margin_10, 80000.0, rel_tol=1e-5)
    # 72000 / 0.92 = 78260.8695
    assert math.isclose(floors.zero_margin_8, 78260.8695, rel_tol=1e-4)

    # (72000 + 500) / 0.90 = 80555.55
    assert math.isclose(floors.floor_alfa, 80555.5555, rel_tol=1e-4)
    assert math.isclose(floors.floor_digi_10, 80555.5555, rel_tol=1e-4)
    # (72000 + 500) / 0.92 = 78804.3478
    assert math.isclose(floors.floor_digi_8, 78804.3478, rel_tol=1e-4)


def test_calculate_baseline() -> None:
    # (70000 + 5000) / 0.90 = 83333.33
    baseline = calculate_baseline(cost_base=70000.0, target_profit=5000.0)
    assert math.isclose(baseline, 83333.3333, rel_tol=1e-4)


def test_winning_psychological_price_standard_case() -> None:
    # Competitor is at 73,000, Floor is at 72,877
    # 73000 - 100 = 72900
    # Candidate endings: 72899 is <= 72900 and >= 72877
    price = find_winning_psychological_price(floor_min=72877.0, competitor_price=73000.0)
    assert price == 72899
    assert price < 73000
    assert price >= 72877


def test_winning_psychological_price_tight_margin() -> None:
    # Competitor at 73,000, Floor at 72,950
    # Target ceiling 72,900 is below floor 72,950
    # Fallback to competitor - 1 = 72999 (which is >= 72950)
    price = find_winning_psychological_price(floor_min=72950.0, competitor_price=73000.0)
    assert price == 72999
    assert price < 73000
    assert price >= 72950


def test_winning_psychological_price_unviable() -> None:
    # Competitor at 72,000, Floor at 72,500 -> impossible to win profitably
    price = find_winning_psychological_price(floor_min=72500.0, competitor_price=72000.0)
    assert price is None


def test_monopoly_psychological_price() -> None:
    # Remainder >= 500 -> base + 999
    assert get_monopoly_psychological_price(74600.0) == 74999
    # Remainder < 500 -> base + 499
    assert get_monopoly_psychological_price(74200.0) == 74499


def test_adaptive_target_tier5_under_800_tight_gap() -> None:
    # Gap < 800 PKR (e.g. 600 or 700 PKR) -> Closest Rs. 100 undercut
    floor = 70000.0
    competitor_600 = 70600.0
    assert (
        calculate_adaptive_target_price(floor_min=floor, competitor_price=competitor_600) == 70500.0
    )

    competitor_700 = 70700.0
    assert (
        calculate_adaptive_target_price(floor_min=floor, competitor_price=competitor_700) == 70600.0
    )


def test_adaptive_target_tier4_800_to_1500_gap() -> None:
    # 800 <= Gap < 1,500 PKR (e.g. 800, 900, 1000, 1200) -> Rs. 200 undercut
    floor = 70000.0
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=70800.0) == 70600.0
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=70900.0) == 70700.0
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=71000.0) == 70800.0
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=71200.0) == 71000.0


def test_adaptive_target_tier3_1500_to_2000_gap() -> None:
    # 1,500 <= Gap < 2,000 PKR (e.g. 1500, 1800, 1900) -> Rs. 500 customer discount, min 1000 buffer
    floor = 70000.0
    # Gap = 1,500 -> 71,500 - 500 = 71,000 (Floor + 1,000)
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=71500.0) == 71000.0
    # Gap = 1,800 -> 71,800 - 500 = 71,300 (Customer gets 500 discount, seller gets 1,300 buffer)
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=71800.0) == 71300.0
    # Gap = 1,900 -> 71,900 - 500 = 71,400 (Customer gets 500 discount, seller gets 1,400 buffer)
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=71900.0) == 71400.0


def test_adaptive_target_tier2_2000_to_10000_gap() -> None:
    # 2,000 <= Gap < 10,000 PKR (3 Zeros) -> 50% split with min 1,000 buffer
    floor = 70000.0
    # Gap = 2,500 -> 50% is 1,250 -> 71,250
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=72500.0) == 71250.0
    # Gap = 5,000 -> 50% is 2,500 -> 72,500
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=75000.0) == 72500.0
    # Gap = 9,000 -> 50% is 4,500 -> 74,500
    assert calculate_adaptive_target_price(floor_min=floor, competitor_price=79000.0) == 74500.0


def test_adaptive_target_4_zeros_large_gap_item1() -> None:
    # Gap >= 10,000 PKR: Item #1 scenario
    # Landed Cost = 430,291, Floor 10% = 478,656.67, Competitor = 489,999.0
    floor = 478656.67
    competitor = 489999.0
    cost_base = 430291.0
    target = calculate_adaptive_target_price(
        floor_min=floor,
        competitor_price=competitor,
        cost_base=cost_base,
        payout_rate=0.92,
        large_gap_profit_target=10000.0,
    )
    # Target should be bounded around the 10k profit point
    price = find_winning_psychological_price(
        floor_min=floor, competitor_price=competitor, max_ceiling=target
    )
    assert price == 478999
    # Profit at 478,999 on DigiMall: (478999 * 0.92) - 430291 = 10,388 (~10k sweet spot with clean .999 ending)
    profit = round((price * 0.92) - cost_base)
    assert profit == 10388


def test_tight_margin_under_100_selects_round_50_item18() -> None:
    # Item #18 scenario: Competitor at 173,099, 8% Floor at 173,003.26 (Gap = 95.74 PKR)
    # System selects clean rounded price 173,050 (multiple of 50) below competitor
    floor_min = 173003.26
    competitor = 173099.0
    cost_base = 158663.0

    target = calculate_adaptive_target_price(
        floor_min=floor_min,
        competitor_price=competitor,
        cost_base=cost_base,
        payout_rate=0.92,
    )
    price = find_winning_psychological_price(
        floor_min=floor_min, competitor_price=competitor, max_ceiling=target
    )

    assert price == 173050
    assert price < competitor
    assert price >= floor_min
    profit = round((price * 0.92) - cost_base)
    assert profit == 543  # Clean +543 PKR profit protected (above 500 guarantee)


def test_undercut_gap_150_selects_round_50_when_no_psychological_price() -> None:
    # Gap = 150 PKR: Competitor at 173,153, Floor at 173,003.26
    # Target ceiling is 173,053. Highest clean multiple of 50 is 173,050
    floor_min = 173003.26
    competitor = 173153.0
    cost_base = 158663.0

    target = calculate_adaptive_target_price(
        floor_min=floor_min,
        competitor_price=competitor,
        cost_base=cost_base,
        payout_rate=0.92,
    )
    price = find_winning_psychological_price(
        floor_min=floor_min, competitor_price=competitor, max_ceiling=target
    )

    assert price == 173050
    assert price < competitor
    assert price >= floor_min
    profit = round((price * 0.92) - cost_base)
    assert profit == 543  # Extra margin protected via round 50 pricing


def test_tight_gaps_roundoff_matrix() -> None:
    # Floor is 173,003.26 -> floor_ceil is 173,004
    floor_min = 173003.26

    # Case 1: Gap = 20 PKR (Competitor = 173,023) -> selects round 10 (173,020)
    p_20 = find_winning_psychological_price(floor_min=floor_min, competitor_price=173023.0)
    assert p_20 == 173020
    assert p_20 < 173023.0
    assert p_20 >= floor_min
    assert p_20 % 10 == 0

    # Case 2: Gap = 15 PKR (Competitor = 173,019) -> selects round 10 (173,010)
    p_15 = find_winning_psychological_price(floor_min=floor_min, competitor_price=173019.0)
    assert p_15 == 173010
    assert p_15 < 173019.0
    assert p_15 >= floor_min
    assert p_15 % 10 == 0

    # Case 3: Gap = 60 PKR (Competitor = 173,064) -> selects round 50 (173,050)
    p_60 = find_winning_psychological_price(floor_min=floor_min, competitor_price=173064.0)
    assert p_60 == 173050
    assert p_60 < 173064.0
    assert p_60 >= floor_min
    assert p_60 % 50 == 0

    # Case 4: Gap = 5 PKR (Competitor = 173,009) -> selects round 5 (173,005)
    p_5 = find_winning_psychological_price(floor_min=floor_min, competitor_price=173009.0)
    assert p_5 == 173005
    assert p_5 < 173009.0
    assert p_5 >= floor_min
    assert p_5 % 5 == 0

    # Case 5: Gap = 0.50 PKR (Competitor = 173,003.70) -> strictly below floor_ceil (173,004) -> None
    p_unviable = find_winning_psychological_price(floor_min=floor_min, competitor_price=173003.70)
    assert p_unviable is None


def test_fallback_psychological_price_always_ends_in_999() -> None:
    # Item #17 numbers: Cost base 137,125, Floor 149,592.39, Payout rate 0.92, Profit target 1,500
    # Must produce standard psychological ending 150,999 (not 150,899)
    price = get_fallback_psychological_price(
        cost_base=137125.0,
        floor_min=149592.39,
        payout_rate=0.92,
        profit_target=1500.0,
    )
    assert price == 150999
    assert price % 1000 == 999
    assert price >= 149592.39
    profit = round((price * 0.92) - 137125.0)
    assert profit == 1794
````

## File: tests/test_scraper.py
````python
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pricing_engine.scraper import (
    clear_scraper_cache,
    get_scraper_cache,
    scrape_alfamall,
    scrape_digimall,
)


@pytest.fixture(autouse=True)
def reset_cache() -> None:
    clear_scraper_cache()


def test_query_cache_stores_valid_offers() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "GREE 36TFIH FLOOR STANDING",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "489,999"},
                    "vendor": {"name": "Test Vendor"},
                }
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        offers1 = await scrape_alfamall(mock_session, "36TFIH", "36TFIH")
        assert len(offers1) == 1
        assert mock_session.get.call_count == 1

        # Second call should hit in-memory cache with 0 remote network calls!
        offers2 = await scrape_alfamall(mock_session, "36TFIH", "36TFIH")
        assert len(offers2) == 1
        assert offers2[0].vendor_name == "Test Vendor"
        assert mock_session.get.call_count == 1  # Still 1! 0ms cache hit

    asyncio.run(_test())


def test_query_cache_never_caches_empty_or_failures() -> None:
    async def _test() -> None:
        # First call fails with 429
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp_429

        offers_failed = await scrape_alfamall(mock_session, "36TFIH", "36TFIH", max_retries=1)
        assert len(offers_failed) == 0

        # Ensure empty failure was NOT cached
        cache = get_scraper_cache()
        assert ("alfamall", "36TFIH") not in cache

        # Next call with 200 OK should fetch fresh and not return poisoned empty list
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {
            "results": [
                {
                    "title": "GREE 36TFIH",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "489,999"},
                    "vendor": {"name": "Real Seller"},
                }
            ]
        }
        mock_session.get.return_value = mock_resp_200

        offers_recovered = await scrape_alfamall(mock_session, "36TFIH", "36TFIH")
        assert len(offers_recovered) == 1
        assert offers_recovered[0].vendor_name == "Real Seller"

    asyncio.run(_test())


def test_digimall_cache_guard_prevents_false_monopoly() -> None:
    async def _test() -> None:
        # If DigiMall fails on first attempt, ensure it does not cache empty
        mock_resp_timeout = MagicMock()
        mock_resp_timeout.status_code = 502

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp_timeout

        offers = await scrape_digimall(mock_session, "12AITH21W", "12AITH21W", max_retries=1)
        assert len(offers) == 0
        assert offers.is_success is False

        cache = get_scraper_cache()
        assert ("digimall", "12AITH21W") not in cache

    asyncio.run(_test())


def test_scraper_soft_200_html_challenge_returns_failure() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Simulate HTML WAF challenge where resp.json() raises JSONDecodeError
        mock_resp.json.side_effect = ValueError("Invalid JSON / HTML challenge")

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        result = await scrape_alfamall(mock_session, "36TFIH", "36TFIH", max_retries=1)
        assert result.is_success is False
        assert len(result.offers) == 0
        assert "Invalid JSON" in (result.error_detail or "")

    asyncio.run(_test())


def test_scraper_supports_data_key_schema() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Storefront returns 'data' key instead of 'results'
        mock_resp.json.return_value = {
            "data": [
                {
                    "title": "GREE SPLIT AC 12AITH21W-T3",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "165,999"},
                    "vendor": {"name": "DataKey Vendor"},
                }
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        result = await scrape_digimall(mock_session, "12AITH21W", "12AITH21W")
        assert result.is_success is True
        assert len(result.offers) == 1
        assert result.offers[0].vendor_name == "DataKey Vendor"

    asyncio.run(_test())


def test_scraper_http_500_returns_failure_result() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        result = await scrape_alfamall(mock_session, "36TFIH", "36TFIH", max_retries=1)
        assert result.is_success is False
        assert result.status_code == 500
        assert len(result.offers) == 0

    asyncio.run(_test())


def test_waterfall_early_exit_when_tier_1_has_two_or_more_offers() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 GC WASHING MACHINE",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "95,000"},
                    "vendor": {"name": "Vendor A"},
                },
                {
                    "title": "HAIER 120-826S6 GC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "97,000"},
                    "vendor": {"name": "Vendor B"},
                },
            ]
        }
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        patterns = {
            "tier_1": ["120-826S6 GC"],
            "tier_2": ["120-826S6"],
            "tier_3": ["120 826S6"],
        }
        result = await scrape_alfamall(mock_session, patterns, "120-826S6 GC")

        assert result.is_success is True
        assert len(result.offers) == 2
        # Exhaustive 3-Tier Multi-Pattern Search: All 3 tiers are queried to ensure complete candidate pool
        assert mock_session.get.call_count == 3

    asyncio.run(_test())


def test_waterfall_cascades_to_tier_2_when_tier_1_has_few_offers() -> None:
    async def _test() -> None:
        # First call (Tier 1) returns 1 offer
        resp_tier1 = MagicMock()
        resp_tier1.status_code = 200
        resp_tier1.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 GC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "95,000"},
                    "vendor": {"name": "Vendor A"},
                }
            ]
        }

        # Second call (Tier 2) returns 1 additional offer
        resp_tier2 = MagicMock()
        resp_tier2.status_code = 200
        resp_tier2.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 AUTOMATIC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "96,000"},
                    "vendor": {"name": "Vendor B"},
                }
            ]
        }

        # Third call (Tier 3) returns 0 offers
        resp_tier3 = MagicMock()
        resp_tier3.status_code = 200
        resp_tier3.json.return_value = {"results": []}

        mock_session = AsyncMock()
        mock_session.get.side_effect = [resp_tier1, resp_tier2, resp_tier3]

        patterns = {
            "tier_1": ["120-826S6 GC"],
            "tier_2": ["120-826S6"],
            "tier_3": ["120 826S6"],
        }
        result = await scrape_digimall(mock_session, patterns, "120-826S6")

        assert result.is_success is True
        assert len(result.offers) == 2
        # Exhaustive search queries all tiers (total 3 HTTP calls across Tier 1, 2, 3)
        assert mock_session.get.call_count == 3

    asyncio.run(_test())


def test_waterfall_deduplicates_overlapping_offers_across_tiers() -> None:
    async def _test() -> None:
        # Tier 1 returns Seller A
        resp_tier1 = MagicMock()
        resp_tier1.status_code = 200
        resp_tier1.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 GC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "95,000"},
                    "vendor": {"name": "Vendor A"},
                }
            ]
        }

        # Tier 2 returns Seller A (same item/price) AND Seller B
        resp_tier2 = MagicMock()
        resp_tier2.status_code = 200
        resp_tier2.json.return_value = {
            "results": [
                {
                    "title": "HAIER 120-826S6 GC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "95,000"},
                    "vendor": {"name": "Vendor A"},
                },
                {
                    "title": "HAIER 120-826S6",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "98,000"},
                    "vendor": {"name": "Vendor B"},
                },
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.side_effect = [resp_tier1, resp_tier2]

        patterns = {
            "tier_1": ["120-826S6 GC"],
            "tier_2": ["120-826S6"],
            "tier_3": ["120 826S6"],
        }
        result = await scrape_alfamall(mock_session, patterns, "120-826S6")

        assert result.is_success is True
        # Deduplication check: Vendor A should appear only ONCE
        assert len(result.offers) == 2
        vendors = [o.vendor_name for o in result.offers]
        assert vendors.count("Vendor A") == 1
        assert vendors.count("Vendor B") == 1

    asyncio.run(_test())


def test_waterfall_prefers_t3_offers_over_base_offers() -> None:
    async def _test() -> None:
        base_response = MagicMock()
        base_response.status_code = 200
        base_response.json.return_value = {
            "results": [
                {
                    "title": "GREE 12AITH21W Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "150,000"},
                    "vendor": {"name": "Base Seller"},
                }
            ]
        }

        t3_response = MagicMock()
        t3_response.status_code = 200
        t3_response.json.return_value = {
            "results": [
                {
                    "title": "GREE 12AITH21W-T3 Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "155,000"},
                    "vendor": {"name": "T3 Seller"},
                }
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.side_effect = [base_response, t3_response]

        result = await scrape_alfamall(
            mock_session,
            {
                "tier_1": ["12AITH21W"],
                "tier_2": ["12AITH21W-T3"],
                "tier_3": [],
            },
            "12AITH21W-T3",
            brand="Gree",
        )

        assert [offer.vendor_name for offer in result.offers] == ["T3 Seller"]
        assert result.active_modifier_fallback is None

    asyncio.run(_test())


def test_waterfall_falls_back_to_base_when_no_t3_offer_exists() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "GREE 12AITH21W Inverter AC",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "150,000"},
                    "vendor": {"name": "Base Seller"},
                }
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        result = await scrape_alfamall(
            mock_session,
            {"tier_1": ["12AITH21W"], "tier_2": [], "tier_3": []},
            "12AITH21W-T3",
            brand="Gree",
        )

        assert [offer.vendor_name for offer in result.offers] == ["Base Seller"]
        assert result.active_modifier_fallback == "T3"

    asyncio.run(_test())


def test_scraper_deduplicates_seller_duplicate_spam_at_same_price() -> None:
    async def _test() -> None:
        # Simulate Tech House spamming identical offers with slightly different title suffixes
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "Haier Top Load Automatic Washing Machine HWM 120-316S6 -By Tech House314",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": "Tech House"},
                },
                {
                    "title": "Haier Top Load Automatic Washing Machine HWM 120-316S6 -By Tech House306",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": "Tech House"},
                },
                {
                    "title": "Haier Top Load Automatic Washing Machine HWM 120-316S6 -By Tech House322",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": "Tech House"},
                },
                {
                    "title": "Haier 120-316S6 Premium Bundle",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "85,000"},
                    "vendor": {"name": "Tech House"},  # Genuine different price
                },
                {
                    "title": "Haier HWM 120-316S6 Washing Machine",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": "One Stop Mall"},  # Distinct vendor at same price
                },
            ]
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        result = await scrape_alfamall(mock_session, "120-316S6", "120-316S6")
        assert result.is_success is True

        # Tech House @ 81,500 should appear only ONCE, with duplicate_count = 3
        # Tech House @ 85,000 should appear ONCE, with duplicate_count = 1
        # One Stop Mall @ 81,500 should appear ONCE, with duplicate_count = 1
        # Total offers should be 3 (not 5)
        assert len(result.offers) == 3

        th_81500 = [o for o in result.offers if o.price == 81500 and o.vendor_name == "Tech House"]
        assert len(th_81500) == 1
        assert th_81500[0].duplicate_count == 3

        th_85000 = [o for o in result.offers if o.price == 85000 and o.vendor_name == "Tech House"]
        assert len(th_85000) == 1
        assert th_85000[0].duplicate_count == 1

        osm_81500 = [o for o in result.offers if o.price == 81500 and o.vendor_name == "One Stop Mall"]
        assert len(osm_81500) == 1
        assert osm_81500[0].duplicate_count == 1

    asyncio.run(_test())


def test_scraper_uses_limit_100_for_single_call_market_depth() -> None:
    async def _test() -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp

        await scrape_alfamall(mock_session, "120-316S6", "120-316S6")
        assert mock_session.get.call_count == 1
        alfa_params = mock_session.get.call_args_list[0].kwargs.get("params") or {}
        assert alfa_params.get("limit") == "100"

        mock_session.reset_mock()
        await scrape_digimall(mock_session, "120-316S6", "120-316S6")
        assert mock_session.get.call_count == 1
        digi_params = mock_session.get.call_args_list[0].kwargs.get("params") or {}
        assert digi_params.get("limit") == "100"

    asyncio.run(_test())



def test_scraper_subfloor_probe_fetches_page_2_when_page_1_is_all_subfloor() -> None:
    async def _test() -> None:
        # Page 1 has 50 items all below floor Rs. 88,000, with total count = 75
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "results": [
                {
                    "title": f"Haier 120-316S6 Seller {i}",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": f"SubFloor Seller {i}"},
                }
                for i in range(50)
            ],
            "count": 75,
        }

        # Page 2 has the viable competitor @ Rs. 88,599
        resp_p2 = MagicMock()
        resp_p2.status_code = 200
        resp_p2.json.return_value = {
            "results": [
                {
                    "title": "Haier 120-316S6",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "88,599"},
                    "vendor": {"name": "Kia Chahiye"},
                }
            ],
            "count": 75,
        }

        mock_session = AsyncMock()
        mock_session.get.side_effect = [resp_p1, resp_p2]

        result = await scrape_alfamall(
            mock_session, "120-316S6", "120-316S6", floor_price=88000.0
        )
        assert result.is_success is True
        # Should have called page 1 then page 2
        assert mock_session.get.call_count == 2
        p2_call = mock_session.get.call_args_list[1].kwargs.get("params") or {}
        assert p2_call.get("page") == "2"

        # Viable competitor from page 2 should be in offers
        viable = [o for o in result.offers if o.price == 88599]
        assert len(viable) == 1
        assert viable[0].vendor_name == "Kia Chahiye"

    asyncio.run(_test())


def test_scraper_subfloor_probe_skips_page_2_when_viable_seller_found_on_page_1() -> None:
    async def _test() -> None:
        # Page 1 contains a viable seller @ 88,599 (> floor 88,000)
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "results": [
                {
                    "title": "Haier 120-316S6",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": "Tech House"},
                },
                {
                    "title": "Haier 120-316S6",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "88,599"},
                    "vendor": {"name": "Kia Chahiye"},
                },
            ],
            "count": 100,  # Even though count is 100, viable seller is already found!
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = resp_p1

        result = await scrape_alfamall(
            mock_session, "120-316S6", "120-316S6", floor_price=88000.0
        )
        assert result.is_success is True
        # Should NOT call page 2! Zero unnecessary latency
        assert mock_session.get.call_count == 1

    asyncio.run(_test())


def test_deduplicate_offers_tracks_duplicate_counts() -> None:
    from pricing_engine.models import ScrapedOffer
    from pricing_engine.scraper import deduplicate_offers

    raw_offers = [
        ScrapedOffer("Tech House", 81500.0, False, "Title 1"),
        ScrapedOffer("Tech House", 81500.0, False, "Title 2"),
        ScrapedOffer("Tech House", 81500.0, False, "Title 3"),
        ScrapedOffer("Tech House", 85000.0, False, "Title 4"),
        ScrapedOffer("Kia Chahiye", 88599.0, False, "Title 5"),
    ]

    deduped = deduplicate_offers(raw_offers)
    assert len(deduped) == 3

    th_81500 = next(o for o in deduped if o.vendor_name == "Tech House" and o.price == 81500.0)
    assert th_81500.duplicate_count == 3

    th_85000 = next(o for o in deduped if o.vendor_name == "Tech House" and o.price == 85000.0)
    assert th_85000.duplicate_count == 1

    kc = next(o for o in deduped if o.vendor_name == "Kia Chahiye")
    assert kc.duplicate_count == 1



def test_subfloor_probe_skips_when_count_less_than_or_equal_to_page_items() -> None:
    async def _test() -> None:
        # Page 1 has 15 items, all sub-floor, but total catalog count is 15 (no more items)
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "results": [
                {
                    "title": f"Haier 120-316S6 Seller {i}",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "81,500"},
                    "vendor": {"name": f"SubFloor Seller {i}"},
                }
                for i in range(15)
            ],
            "count": 15,
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = resp_p1

        result = await scrape_alfamall(
            mock_session, "120-316S6", "120-316S6", floor_price=88000.0
        )
        assert result.is_success is True
        # Should NOT probe page 2 because count (15) <= len(raw_items) (15)
        assert mock_session.get.call_count == 1

    asyncio.run(_test())


def test_digimall_subfloor_probe_fetches_page_2_when_needed() -> None:
    async def _test() -> None:
        # DigiMall page 1 has 50 sub-floor items, total count = 80
        resp_p1 = MagicMock()
        resp_p1.status_code = 200
        resp_p1.json.return_value = {
            "results": [
                {
                    "title": f"Haier 120-316S6 Seller {i}",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "80,000"},
                    "vendor": {"name": f"Digi SubFloor {i}"},
                }
                for i in range(50)
            ],
            "count": 80,
        }

        # Page 2 has the viable competitor
        resp_p2 = MagicMock()
        resp_p2.status_code = 200
        resp_p2.json.return_value = {
            "results": [
                {
                    "title": "Haier 120-316S6",
                    "sold_out": False,
                    "variant_detail": {"discounted_price": "86,702"},
                    "vendor": {"name": "Electronics World"},
                }
            ],
            "count": 80,
        }

        mock_session = AsyncMock()
        mock_session.get.side_effect = [resp_p1, resp_p2]

        result = await scrape_digimall(
            mock_session, "120-316S6", "120-316S6", floor_price=86307.0
        )
        assert result.is_success is True
        assert mock_session.get.call_count == 2
        p2_call = mock_session.get.call_args_list[1].kwargs.get("params") or {}
        assert p2_call.get("page") == "2"

        viable = [o for o in result.offers if o.price == 86702]
        assert len(viable) == 1
        assert viable[0].vendor_name == "Electronics World"

    asyncio.run(_test())
````

## File: tests/test_evaluator.py
````python
import pytest

from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.models import CostFloors, ScrapedOffer, ScrapeResult


@pytest.fixture
def sample_floors() -> CostFloors:
    # cost_base = 72,000
    # 10% floor = (72000 + 500) / 0.90 = 80,555.56
    # 8% floor  = (72000 + 500) / 0.92 = 78,804.35
    cost_base = 72000.0
    return CostFloors(
        cost_base=cost_base,
        zero_margin_10=cost_base / 0.90,
        zero_margin_8=cost_base / 0.92,
        floor_alfa=(cost_base + 500.0) / 0.90,
        floor_digi_10=(cost_base + 500.0) / 0.90,
        floor_digi_8=(cost_base + 500.0) / 0.92,
    )


# ==============================================================================
# ALFAMALL TESTS
# ==============================================================================


def test_alfa_monopoly_when_zero_offers(sample_floors: CostFloors) -> None:
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=[])
    assert result.status == "Monopoly Win"
    assert result.final_price is not None
    # Base target = (72000 + 4000) / 0.90 = 84444.44 -> Monopoly price 84499
    assert result.final_price == 84499
    assert result.real_profit >= 4000


def test_alfa_safe_fallback_when_all_sellers_below_floor(sample_floors: CostFloors) -> None:
    # Floor is 80,555. Both sellers are below floor. Must produce Safe Fallback price, NOT None.
    offers = [
        ScrapedOffer(vendor_name="V1", price=79000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="V2", price=80000.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Safe Fallback"
    assert result.final_price is not None
    assert result.final_price >= sample_floors.floor_alfa
    assert result.real_profit >= 1500
    assert len(result.dropped) == 2
    assert "Safe Fallback Price" in result.reason


def test_alfa_competitive_win_undercut(sample_floors: CostFloors) -> None:
    # Floor is 80,555. One loss maker at 79,000, one viable at 83,000.
    offers = [
        ScrapedOffer(vendor_name="LossVendor", price=79000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="ViableVendor", price=83000.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Competitive Win"
    assert result.final_price is not None
    assert result.final_price < 83000.0
    assert result.final_price >= sample_floors.floor_alfa
    assert result.final_price == 81499
    assert result.real_profit > 500


def test_alfa_ignores_sold_out_offers(sample_floors: CostFloors) -> None:
    offers = [
        ScrapedOffer(vendor_name="SoldOutCheap", price=75000.0, is_sold_out=True, raw_title="AC"),
    ]
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Monopoly Win"


# ==============================================================================
# DIGIMALL TESTS
# ==============================================================================


def test_digi_monopoly_when_zero_offers(sample_floors: CostFloors) -> None:
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=[])
    assert result.status == "Monopoly Win"
    assert result.effective_comm == "10.00%"
    assert result.final_price == 84499
    # Bank charges 8%, so profit is (84499 * 0.92) - 72000
    assert result.real_profit == round((84499 * 0.92) - 72000)


def test_digi_tier1_safe_win_10_percent(sample_floors: CostFloors) -> None:
    # Lowest offer at 84,000 is above 10% floor (80,555.56)
    offers = [
        ScrapedOffer(vendor_name="Competitor1", price=84000.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Safe Win (10% Tier)"
    assert result.effective_comm == "10.00%"
    assert result.final_price is not None
    assert result.final_price < 84000.0
    assert result.final_price >= sample_floors.floor_digi_10
    # Profit calculated at 0.92 bank rate!
    assert result.real_profit == round((result.final_price * 0.92) - sample_floors.cost_base)


def test_digi_tier2_emergency_8_percent_switch(sample_floors: CostFloors) -> None:
    # 10% floor is 80,555.56. 8% floor is 78,804.35.
    # Competitor is at 79,500 (below 10% floor, but above 8% floor)
    offers = [
        ScrapedOffer(vendor_name="TightSeller", price=79500.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Win via 8% Switch"
    assert result.effective_comm == "8.00%"
    assert result.final_price is not None
    assert result.final_price < 79500.0
    assert result.final_price >= sample_floors.floor_digi_8


def test_digi_upper_band_win_when_lowest_below_8_percent(sample_floors: CostFloors) -> None:
    # 8% floor is 78,804.35, 10% floor is 80,555.55
    # Case 1: Upper seller is between 8% floor and 10% floor (79,500) -> Must switch to 8% to win
    offers_8 = [
        ScrapedOffer(vendor_name="SuicideSeller", price=77000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="UpperSellerTight", price=79500.0, is_sold_out=False, raw_title="AC"
        ),
    ]
    result_8 = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers_8)
    assert result_8.status == "Win via 8% Switch"
    assert result_8.effective_comm == "8.00%"
    assert result_8.final_price is not None
    assert result_8.final_price < 79500.0
    assert result_8.final_price >= sample_floors.floor_digi_8
    assert len(result_8.dropped) == 1

    # Case 2: Upper seller is above 10% floor (81,000) -> Stays on default 10% tier (+2% bank spread profit)
    offers_10 = [
        ScrapedOffer(vendor_name="SuicideSeller", price=77000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="UpperSellerHigh", price=81000.0, is_sold_out=False, raw_title="AC"
        ),
    ]
    result_10 = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers_10)
    assert result_10.status == "Safe Win (10% Tier)"
    assert result_10.effective_comm == "10.00%"
    assert result_10.final_price is not None
    assert result_10.final_price < 81000.0
    assert result_10.final_price >= sample_floors.floor_digi_10
    assert len(result_10.dropped) == 1


def test_digi_safe_fallback_when_all_below_8_percent(sample_floors: CostFloors) -> None:
    # 8% floor is 78,804.35. All sellers below 78,000. Must produce Safe Fallback price, NOT None.
    offers = [
        ScrapedOffer(vendor_name="SellerA", price=77000.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="SellerB", price=76500.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=offers)
    assert result.status == "Safe Fallback"
    assert result.final_price is not None
    assert result.final_price >= sample_floors.floor_digi_8
    assert result.real_profit >= 1500
    assert result.effective_comm == "8.00%"
    assert "Safe Fallback Price" in result.reason


def test_digi_high_ticket_item1_wins_at_10_percent() -> None:
    # Item #1: Floor Standing AC (Net 415,000, Shipping 15,291 -> Cost Base 430,291)
    # 10% Floor (+500) = (430,291 + 500) / 0.90 = 478,656.67
    # 8% Floor (+500)  = (430,291 + 500) / 0.92 = 468,251.09
    cost_base = 430291.0
    floors = CostFloors(
        cost_base=cost_base,
        zero_margin_10=cost_base / 0.90,
        zero_margin_8=cost_base / 0.92,
        floor_alfa=(cost_base + 500.0) / 0.90,
        floor_digi_10=(cost_base + 500.0) / 0.90,
        floor_digi_8=(cost_base + 500.0) / 0.92,
    )
    offers = [
        ScrapedOffer(vendor_name="Tech House", price=444999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="Musab Mall", price=444999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="YZ international", price=445099.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(vendor_name="Home Cart", price=463549.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="Scroll-N-Shop.pk", price=489999.0, is_sold_out=False, raw_title="AC"
        ),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)

    # Must win at Default 10% Tier, NOT 8% Emergency Switch!
    assert result.status == "Safe Win (10% Tier)"
    assert result.effective_comm == "10.00%"
    assert result.final_price == 478999
    assert result.real_profit == 10388  # +Rs. 10,388 (~10k sweet spot with clean .999)
    assert len(result.dropped) == 4
    assert "sweet-spot price Rs. 478,999" in result.reason


def test_digi_split_ac_item2_triggers_8_percent_emergency_switch() -> None:
    # Item #2: Split AC 12AITH21W-T3 (Net 147,000, Shipping 3,978 -> Cost Base 150,978)
    # 10% Floor (+500) = (150,978 + 500) / 0.90 = 168,308.89
    # 8% Floor (+500)  = (150,978 + 500) / 0.92 = 164,650.00
    cost_base = 150978.0
    floors = CostFloors(
        cost_base=cost_base,
        zero_margin_10=cost_base / 0.90,
        zero_margin_8=cost_base / 0.92,
        floor_alfa=(cost_base + 500.0) / 0.90,
        floor_digi_10=(cost_base + 500.0) / 0.90,
        floor_digi_8=(cost_base + 500.0) / 0.92,
    )
    offers = [
        ScrapedOffer(
            vendor_name="iShopping Team", price=162299.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(vendor_name="Tech House", price=165999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(vendor_name="Musab Mall", price=165999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="YZ international", price=166099.0, is_sold_out=False, raw_title="AC"
        ),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)

    # Tech House (165,999) < 10% floor (168,309), so 10% loses -> Triggers Emergency 8% Switch!
    # Gap is 1,349 PKR (800-1500 range) -> Undercuts by Rs. 200 to 165,799 (.799 psychological ending)
    assert result.status == "Win via 8% Switch"
    assert result.effective_comm == "8.00%"
    assert result.final_price == 165799
    assert result.real_profit == round((165799 * 0.92) - 150978)  # +Rs. 1,557 profit
    assert len(result.dropped) == 1
    assert "emergency 8% Faysal Bank rate" in result.reason


def test_digi_item18_tight_margin_selects_floor_ceil_wins_with_500_profit() -> None:
    # Item #18: Split AC GS-18PITC12W-T3 (Cost Base 158,663)
    # 8% Floor (+500) = (158,663 + 500) / 0.92 = 173,003.26
    # Lowest viable is YZ international at 173,099.0 (Gap = 95.74 PKR)
    cost_base = 158663.0
    floors = CostFloors(
        cost_base=cost_base,
        zero_margin_10=cost_base / 0.90,
        zero_margin_8=cost_base / 0.92,
        floor_alfa=(cost_base + 500.0) / 0.90,
        floor_digi_10=(cost_base + 500.0) / 0.90,
        floor_digi_8=(cost_base + 500.0) / 0.92,
    )
    offers = [
        ScrapedOffer(
            vendor_name="iShopping Team", price=168749.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(
            vendor_name="Electronics World", price=171304.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(vendor_name="Musab Mall", price=171999.0, is_sold_out=False, raw_title="AC"),
        ScrapedOffer(
            vendor_name="YZ international", price=172099.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(
            vendor_name="YZ international", price=172999.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(
            vendor_name="YZ international", price=173099.0, is_sold_out=False, raw_title="AC"
        ),
        ScrapedOffer(vendor_name="EZZI TRADERS", price=180549.0, is_sold_out=False, raw_title="AC"),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)

    # Must NOT skip! Must win at 8% rounded price 173,050 with guaranteed +543 profit
    assert result.status == "Win via 8% Switch"
    assert result.effective_comm == "8.00%"
    assert result.final_price == 173050
    assert result.real_profit == 543
    assert len(result.dropped) == 5
    assert (
        "gap is tight. Undercut to winning rounded price Rs. 173,050 with guaranteed +Rs. 543 profit."
        in result.reason
    )


def test_digi_item17_all_competitors_selling_at_loss_safe_fallback() -> None:
    # Item #17: Cost Base 137,125. 8% Floor (+500) = 149,592.
    # Competitor iShopping Team at 146,849 is selling at a loss.
    cost_base = 137125.0
    floors = CostFloors(
        cost_base=cost_base,
        zero_margin_10=cost_base / 0.90,
        zero_margin_8=cost_base / 0.92,
        floor_alfa=(cost_base + 500.0) / 0.90,
        floor_digi_10=(cost_base + 500.0) / 0.90,
        floor_digi_8=(cost_base + 500.0) / 0.92,
    )
    offers = [
        ScrapedOffer(
            vendor_name="iShopping Team", price=146849.0, is_sold_out=False, raw_title="AC"
        ),
    ]
    result = evaluate_digi_pricing(cost_floors=floors, offers=offers)

    # Must produce Safe Fallback price: 150,999 with profit +1,794
    assert result.status == "Safe Fallback"
    assert result.effective_comm == "8.00%"
    assert result.final_price == 150999
    assert result.real_profit == 1794
    assert len(result.dropped) == 1
    assert (
        "Listed at Safe Fallback Price Rs. 150,999 (+Rs. 1,794 profit on 8% Faysal Bank rate)"
        in result.reason
    )


def test_alfa_server_down_does_not_trigger_false_monopoly(sample_floors: CostFloors) -> None:
    # When remote server crashes with 500, MUST set Server Down / Unreachable, NOT Monopoly!
    scrape_fail = ScrapeResult(
        offers=[],
        is_success=False,
        status_code=500,
        error_detail="HTTP 500 Internal Server Error",
    )
    result = evaluate_alfa_pricing(cost_floors=sample_floors, offers=scrape_fail)

    assert result.status == "Server Down / Unreachable"
    assert result.final_price is None
    assert result.real_profit == 0
    assert "500" in result.reason
    assert "Skipped to prevent blind mispricing" in result.reason


def test_digi_server_down_does_not_trigger_false_monopoly(sample_floors: CostFloors) -> None:
    # When remote server times out, MUST set Server Down / Unreachable, NOT Monopoly!
    scrape_fail = ScrapeResult(
        offers=[],
        is_success=False,
        status_code=504,
        error_detail="Gateway Timeout after 3 retries",
    )
    result = evaluate_digi_pricing(cost_floors=sample_floors, offers=scrape_fail)

    assert result.status == "Server Down / Unreachable"
    assert result.final_price is None
    assert result.real_profit == 0
    assert "Gateway Timeout" in result.reason
    assert "Skipped to prevent blind mispricing" in result.reason


def test_asymmetric_portal_failure_isolated(sample_floors: CostFloors) -> None:
    # AlfaMall succeeds with viable seller, DigiMall fails with 500.
    # Neither should corrupt or block the other!
    alfa_success = ScrapeResult(
        offers=[
            ScrapedOffer(vendor_name="LiveSeller", price=82000.0, is_sold_out=False, raw_title="AC")
        ],
        is_success=True,
    )
    digi_fail = ScrapeResult(
        offers=[],
        is_success=False,
        status_code=500,
        error_detail="WAF 500 Server Error",
    )

    alfa_res = evaluate_alfa_pricing(cost_floors=sample_floors, offers=alfa_success)
    digi_res = evaluate_digi_pricing(cost_floors=sample_floors, offers=digi_fail)

    # Alfa successfully undercuts
    assert alfa_res.final_price is not None
    assert alfa_res.final_price < 82000.0
    assert alfa_res.status == "Competitive Win"

    # Digi cleanly reports Server Down
    assert digi_res.final_price is None
    assert digi_res.status == "Server Down / Unreachable"
````

## File: pricing_engine/models.py
````python
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

STATUS_SERVER_DOWN: str = "Server Down / Unreachable"


@dataclass(frozen=True, slots=True)
class CostFloors:
    """Represents calculated margin thresholds and hard floors for a product."""

    cost_base: float
    zero_margin_10: float
    zero_margin_8: float
    floor_alfa: float
    floor_digi_10: float
    floor_digi_8: float


@dataclass(frozen=True, slots=True)
class ScrapedOffer:
    """A single competitor product offering scraped from AlfaMall or DigiMall."""

    vendor_name: str
    price: float
    is_sold_out: bool
    raw_title: str
    duplicate_count: int = 1



@dataclass(frozen=True, slots=True)
class ScrapeResult:
    """Rich scrape result contract explicitly distinguishing healthy scrape from server errors."""

    offers: list[ScrapedOffer] = field(default_factory=list)
    is_success: bool = True
    status_code: int | None = 200
    error_detail: str | None = None
    executed_queries: list[str] = field(default_factory=list)
    matched_tier: str | None = None
    tier_summary: dict[str, int] = field(default_factory=dict)
    active_modifier_fallback: str | None = None
    base_offers: list[ScrapedOffer] = field(default_factory=list)

    def __iter__(self) -> Iterator[ScrapedOffer]:
        return iter(self.offers)

    def __len__(self) -> int:
        return len(self.offers)

    def __getitem__(self, index: int) -> ScrapedOffer:
        return self.offers[index]


@dataclass(frozen=True, slots=True)
class PlatformPricingResult:
    """Evaluation result and pricing decision for a single platform."""

    min_price: float | None
    max_price: float | None
    final_price: int | None
    real_profit: int
    status: str
    reason: str
    dropped: list[str] = field(default_factory=list)
    active_pool: list[str] = field(default_factory=list)
    effective_comm: str = "10.00%"


@dataclass(frozen=True, slots=True)
class ProductInput:
    """Standardized input product item read from CSV."""

    sno: int | str
    brand: str
    name: str
    length: float
    width: float
    height: float
    net_price: float
    profit: float
    raw_row: dict[str, Any] = field(default_factory=dict)
````

## File: pricing_engine/evaluator.py
````python
from dataclasses import replace

from pricing_engine.calculator import (
    calculate_adaptive_target_price,
    find_winning_psychological_price,
    get_fallback_psychological_price,
    get_monopoly_psychological_price,
)
from pricing_engine.models import (
    STATUS_SERVER_DOWN,
    CostFloors,
    PlatformPricingResult,
    ScrapedOffer,
    ScrapeResult,
)

MONOPOLY_PROFIT: float = 4000.0
FALLBACK_PROFIT: float = 1500.0


def _annotate_fallback_reason(
    res: PlatformPricingResult, active_fallback: str | None
) -> PlatformPricingResult:
    """Prepend explicit fallback notification to pricing reason when market omitted target modifier."""
    if active_fallback and res.status not in (STATUS_SERVER_DOWN, "Monopoly Win"):
        new_reason = (
            f"[FALLBACK MODEL: Target specified '{active_fallback}', but market listings omitted it; "
            f"repriced against base model] {res.reason}"
        )
        return replace(res, reason=new_reason)
    return res


def evaluate_alfa_pricing(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float = MONOPOLY_PROFIT,
    max_profit_cap: float | None = None,
) -> PlatformPricingResult:
    """Evaluate pricing on AlfaMall with automatic fallback reason annotation."""
    active_fallback = offers.active_modifier_fallback if isinstance(offers, ScrapeResult) else None
    res = _evaluate_alfa_core(
        cost_floors=cost_floors,
        offers=offers,
        monopoly_profit=monopoly_profit,
        max_profit_cap=max_profit_cap,
    )
    return _annotate_fallback_reason(res, active_fallback)


def _evaluate_alfa_core(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float = MONOPOLY_PROFIT,
    max_profit_cap: float | None = None,
) -> PlatformPricingResult:
    """Evaluate pricing on AlfaMall under strict 10% commission rules.

    Rules:
    - If server is unreachable (500/timeout/WAF HTML), return Server Down status (no blind monopoly).
    - Discard out-of-stock items.
    - If 0 active offers and server is healthy, set Monopoly price (+Rs. 4,000 margin).
    - Discard sellers priced <= floor_alfa (unviable loss-makers).
    - If no viable sellers remain, set Safe Fallback Price (+Rs. 1,500 profit) to ensure upload.
    - Otherwise, strictly undercut lowest viable competitor with psychological price.

    Args:
        cost_floors: CostFloors object containing cost base and minimum floors.
        offers: List of scraped competitor offerings or ScrapeResult instance.
        monopoly_profit: Profit added when 0 competitors exist.
        max_profit_cap: Optional profit ceiling cap.

    Returns:
        PlatformPricingResult with final decision, prices, and audit log.
    """
    if isinstance(offers, ScrapeResult):
        scrape_success = offers.is_success
        error_detail = offers.error_detail
        offer_list = offers.offers
    else:
        scrape_success = True
        error_detail = None
        offer_list = list(offers)

    # Server Down / Unreachable Guard: Never set false Monopoly on network/server error
    if not scrape_success:
        err_msg = error_detail or "HTTP Server/Network Error"
        return PlatformPricingResult(
            min_price=None,
            max_price=None,
            final_price=None,
            real_profit=0,
            status=STATUS_SERVER_DOWN,
            reason=(
                f"AlfaMall search API unreachable ({err_msg}). "
                "Skipped to prevent blind mispricing while server is down."
            ),
            dropped=[],
            active_pool=[],
            effective_comm="10.00%",
        )

    active_offers = [o for o in offer_list if not o.is_sold_out]
    valid_prices = sorted([o.price for o in active_offers])

    min_p: float | None = min(valid_prices) if valid_prices else None
    max_p: float | None = max(valid_prices) if valid_prices else None

    # Scenario 1: Zero competitors in market -> Monopoly Pricing
    if not valid_prices:
        raw_target = (cost_floors.cost_base + monopoly_profit) / 0.90
        monopoly_p = get_monopoly_psychological_price(raw_target)
        profit = round((monopoly_p * 0.90) - cost_floors.cost_base)
        return PlatformPricingResult(
            min_price=min_p,
            max_price=max_p,
            final_price=monopoly_p,
            real_profit=profit,
            status="Monopoly Win",
            reason=f"No competitors found in market. Applied Monopoly pricing (+Rs. {monopoly_profit:,.0f} target margin).",
            dropped=[],
            active_pool=[],
            effective_comm="10.00%",
        )

    # Discard loss makers (sellers strictly <= floor cannot be profitably undercut)
    dropped = [o for o in active_offers if o.price <= cost_floors.floor_alfa]
    viable = [o for o in active_offers if o.price > cost_floors.floor_alfa]

    # Scenario 2: All competitors below floor -> Safe Fallback to enable catalog upload
    if not viable:
        lowest_dropped_obj = min(dropped, key=lambda x: x.price)
        lowest_dropped = lowest_dropped_obj.price
        final_fallback_p = get_fallback_psychological_price(
            cost_base=cost_floors.cost_base,
            floor_min=cost_floors.floor_alfa,
            payout_rate=0.90,
            profit_target=FALLBACK_PROFIT,
        )
        profit = round((final_fallback_p * 0.90) - cost_floors.cost_base)
        return PlatformPricingResult(
            min_price=min_p,
            max_price=max_p,
            final_price=final_fallback_p,
            real_profit=profit,
            status="Safe Fallback",
            reason=(
                f"All competitors are selling at a loss (< Floor Rs. {round(cost_floors.floor_alfa):,}, "
                f"lowest: {lowest_dropped_obj.vendor_name} Rs. {lowest_dropped:,.0f}). Undercut skipped to prevent loss. "
                f"Listed at Safe Fallback Price Rs. {final_fallback_p:,.0f} (+Rs. {profit:,} profit) to ensure catalog upload."
            ),
            dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
            active_pool=[],
            effective_comm="10.00%",
        )

    # Scenario 3: Undercut lowest viable seller
    lowest_viable = min(viable, key=lambda x: x.price)
    large_cap_alfa = max_profit_cap if max_profit_cap is not None else 10000.0
    target_adaptive_alfa = calculate_adaptive_target_price(
        floor_min=cost_floors.floor_alfa,
        competitor_price=lowest_viable.price,
        cost_base=cost_floors.cost_base,
        payout_rate=0.90,
        large_gap_profit_target=large_cap_alfa,
    )
    final_p: int | None = find_winning_psychological_price(
        cost_floors.floor_alfa, lowest_viable.price, max_ceiling=target_adaptive_alfa
    )

    if final_p is None:
        # If psychological search couldn't beat lowest, try next higher viable seller
        for higher_viable in sorted(viable, key=lambda x: x.price)[1:]:
            target_adaptive_alfa = calculate_adaptive_target_price(
                floor_min=cost_floors.floor_alfa,
                competitor_price=higher_viable.price,
                cost_base=cost_floors.cost_base,
                payout_rate=0.90,
                large_gap_profit_target=large_cap_alfa,
            )
            final_p = find_winning_psychological_price(
                cost_floors.floor_alfa, higher_viable.price, max_ceiling=target_adaptive_alfa
            )
            if final_p is not None:
                lowest_viable = higher_viable
                break

    if final_p is None:
        return PlatformPricingResult(
            min_price=min_p,
            max_price=max_p,
            final_price=None,
            real_profit=0,
            status="Skip / Unviable",
            reason="Tight competitor margin prevented psychological undercut above floor. Skipped to prevent loss.",
            dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
            active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable],
            effective_comm="10.00%",
        )

    profit = round((final_p * 0.90) - cost_floors.cost_base)
    dropped_prefix = f"Filtered {len(dropped)} sub-floor offer(s). " if dropped else ""
    uncapped_p = find_winning_psychological_price(cost_floors.floor_alfa, lowest_viable.price)
    if uncapped_p is not None and final_p < uncapped_p:
        gap = lowest_viable.price - cost_floors.floor_alfa
        if 2000.0 <= gap < 10000.0:
            reason = (
                f"{dropped_prefix}Large price gap (Rs. {gap:,.0f}) above floor. Applied 50% split midpoint "
                f"to winning psychological price Rs. {final_p:,.0f} (+Rs. {profit:,} profit) for maximum conversion."
            )
        else:
            reason = (
                f"{dropped_prefix}Competitor {lowest_viable.vendor_name} (Rs. {lowest_viable.price:,.0f}) "
                f"price is inflated. Capped price at Rs. {final_p:,.0f} (+Rs. {profit:,} profit) to ensure sales volume."
            )
    else:
        reason = (
            f"{dropped_prefix}Undercut viable competitor {lowest_viable.vendor_name} "
            f"(Rs. {lowest_viable.price:,.0f}) to winning price Rs. {final_p:,.0f}."
            if dropped
            else f"Undercut lowest competitor {lowest_viable.vendor_name} (Rs. {lowest_viable.price:,.0f}) to winning price Rs. {final_p:,.0f}."
        )
    return PlatformPricingResult(
        min_price=min_p,
        max_price=max_p,
        final_price=final_p,
        real_profit=profit,
        status="Competitive Win",
        reason=reason,
        dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
        active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable],
        effective_comm="10.00%",
    )


def evaluate_digi_pricing(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float = MONOPOLY_PROFIT,
    max_profit_cap: float | None = None,
) -> PlatformPricingResult:
    """Evaluate pricing on DigiMall with automatic fallback reason annotation."""
    active_fallback = offers.active_modifier_fallback if isinstance(offers, ScrapeResult) else None
    res = _evaluate_digi_core(
        cost_floors=cost_floors,
        offers=offers,
        monopoly_profit=monopoly_profit,
        max_profit_cap=max_profit_cap,
    )
    return _annotate_fallback_reason(res, active_fallback)


def _evaluate_digi_core(
    cost_floors: CostFloors,
    offers: list[ScrapedOffer] | ScrapeResult,
    monopoly_profit: float = MONOPOLY_PROFIT,
    max_profit_cap: float | None = None,
) -> PlatformPricingResult:
    """Evaluate pricing on DigiMall with Two-Tier Commission Switch (10% -> 8%).

    Rules:
    - If server is unreachable (500/timeout/WAF HTML), return Server Down status (no blind monopoly).
    - Default 10% Tier: If lowest competitor > floor_digi_10, undercut at 10% tier.
      Since bank only charges 8%, we capture extra 2% bank spread profit.
    - Emergency 8% Switch: If lowest competitor <= floor_digi_10 but > floor_digi_8,
      trigger 8% bank rate to win the deal.
    - Upper Band: If lowest competitor <= floor_digi_8, drop them and target next
      viable competitor > floor_digi_8.
    - If all competitors <= floor_digi_8, set Safe Fallback Price (+Rs. 1,500 profit) to ensure upload.

    Args:
        cost_floors: CostFloors containing cost base and floors.
        offers: Scraped competitor offerings or ScrapeResult instance.
        monopoly_profit: Profit added when 0 competitors exist.
        max_profit_cap: Optional profit ceiling cap.

    Returns:
        PlatformPricingResult with decision, price, commission used, and audit details.
    """
    if isinstance(offers, ScrapeResult):
        scrape_success = offers.is_success
        error_detail = offers.error_detail
        offer_list = offers.offers
    else:
        scrape_success = True
        error_detail = None
        offer_list = list(offers)

    # Server Down / Unreachable Guard: Never set false Monopoly on network/server error
    if not scrape_success:
        err_msg = error_detail or "HTTP Server/Network Error"
        return PlatformPricingResult(
            min_price=None,
            max_price=None,
            final_price=None,
            real_profit=0,
            status=STATUS_SERVER_DOWN,
            reason=(
                f"DigiMall search API unreachable ({err_msg}). "
                "Skipped to prevent blind mispricing while server is down."
            ),
            dropped=[],
            active_pool=[],
            effective_comm="8.00%",
        )

    active_offers = [o for o in offer_list if not o.is_sold_out]
    valid_prices = sorted([o.price for o in active_offers])

    min_p: float | None = min(valid_prices) if valid_prices else None
    max_p: float | None = max(valid_prices) if valid_prices else None

    # Scenario 1: Zero competitors in market -> Monopoly Pricing
    if not valid_prices:
        raw_target = (cost_floors.cost_base + monopoly_profit) / 0.90
        monopoly_p = get_monopoly_psychological_price(raw_target)
        profit = round((monopoly_p * 0.92) - cost_floors.cost_base)
        return PlatformPricingResult(
            min_price=min_p,
            max_price=max_p,
            final_price=monopoly_p,
            real_profit=profit,
            status="Monopoly Win",
            reason="No competitors found in market. Applied Monopoly 10% baseline pricing and captured extra 2% bank spread profit via 8% Faysal Bank rate.",
            dropped=[],
            active_pool=[],
            effective_comm="10.00%",
        )

    lowest_offer = min(active_offers, key=lambda x: x.price)
    large_cap = max_profit_cap if max_profit_cap is not None else 10000.0

    # Step A: Check Default 10% Tier
    if lowest_offer.price > cost_floors.floor_digi_10:
        gap_10 = lowest_offer.price - cost_floors.floor_digi_10
        target_adaptive_10 = calculate_adaptive_target_price(
            floor_min=cost_floors.floor_digi_10,
            competitor_price=lowest_offer.price,
            cost_base=cost_floors.cost_base,
            payout_rate=0.92,
            large_gap_profit_target=large_cap,
        )
        final_p_10: int | None = find_winning_psychological_price(
            cost_floors.floor_digi_10, lowest_offer.price, max_ceiling=target_adaptive_10
        )
        if final_p_10 is not None:
            profit = round((final_p_10 * 0.92) - cost_floors.cost_base)
            uncapped_p = find_winning_psychological_price(
                cost_floors.floor_digi_10, lowest_offer.price
            )
            if gap_10 >= 10000.0 and uncapped_p is not None and final_p_10 < uncapped_p:
                reason = (
                    f"Competitor {lowest_offer.vendor_name} (Rs. {lowest_offer.price:,.0f}) "
                    f"price is inflated. Capped price at sweet-spot Rs. {final_p_10:,.0f} (+Rs. {profit:,} profit on 8% Faysal Bank rate) for sales conversion."
                )
            else:
                reason = (
                    f"Lowest competitor {lowest_offer.vendor_name} (Rs. {lowest_offer.price:,.0f}) "
                    f"is above 10% floor. Won at 10% tier with 8% Faysal Bank rate (+Rs. {profit:,} profit incl. 2% bank spread)."
                )
            return PlatformPricingResult(
                min_price=min_p,
                max_price=max_p,
                final_price=final_p_10,
                real_profit=profit,
                status="Safe Win (10% Tier)",
                reason=reason,
                dropped=[],
                active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in active_offers],
                effective_comm="10.00%",
            )

    # Step B: Emergency 8% Bank Rate Switch
    if lowest_offer.price > cost_floors.floor_digi_8:
        gap_8 = lowest_offer.price - cost_floors.floor_digi_8
        target_adaptive_8 = calculate_adaptive_target_price(
            floor_min=cost_floors.floor_digi_8,
            competitor_price=lowest_offer.price,
            cost_base=cost_floors.cost_base,
            payout_rate=0.92,
            large_gap_profit_target=large_cap,
        )
        final_p_8: int | None = find_winning_psychological_price(
            cost_floors.floor_digi_8, lowest_offer.price, max_ceiling=target_adaptive_8
        )
        if final_p_8 is not None:
            profit = round((final_p_8 * 0.92) - cost_floors.cost_base)
            if gap_8 < 100.0:
                reason = (
                    f"Unviable at 10% floor (Rs. {round(cost_floors.floor_digi_10):,}). "
                    f"Triggered emergency 8% Faysal Bank rate. Competitor {lowest_offer.vendor_name} (Rs. {lowest_offer.price:,.0f}) "
                    f"gap is tight. Undercut to winning rounded price Rs. {final_p_8:,.0f} with guaranteed +Rs. {profit:,} profit."
                )
            else:
                uncapped_p = find_winning_psychological_price(
                    cost_floors.floor_digi_8, lowest_offer.price
                )
                if gap_8 >= 10000.0 and uncapped_p is not None and final_p_8 < uncapped_p:
                    reason = (
                        f"Triggered emergency 8% Faysal Bank rate. Competitor {lowest_offer.vendor_name} (Rs. {lowest_offer.price:,.0f}) "
                        f"price is inflated. Capped price at sweet-spot Rs. {final_p_8:,.0f} (+Rs. {profit:,} profit on 8% Faysal Bank rate) for sales conversion."
                    )
                else:
                    reason = (
                        f"Unviable at 10% floor (Rs. {round(cost_floors.floor_digi_10):,}). "
                        f"Triggered emergency 8% Faysal Bank rate to undercut {lowest_offer.vendor_name} (Rs. {lowest_offer.price:,.0f}) "
                        f"to winning price Rs. {final_p_8:,.0f} (+Rs. {profit:,} profit)."
                    )
            return PlatformPricingResult(
                min_price=min_p,
                max_price=max_p,
                final_price=final_p_8,
                real_profit=profit,
                status="Win via 8% Switch",
                reason=reason,
                dropped=[],
                active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in active_offers],
                effective_comm="8.00%",
            )

    # Step C: Lowest seller is <= 8% floor (unviable loss-maker). Try upper band.
    dropped = [o for o in active_offers if o.price <= cost_floors.floor_digi_8]
    viable_8 = [o for o in active_offers if o.price > cost_floors.floor_digi_8]

    if viable_8:
        for lowest_upper in sorted(viable_8, key=lambda x: x.price):
            # Check if lowest upper seller can be won at default 10% tier first
            if lowest_upper.price > cost_floors.floor_digi_10:
                gap_upper_10 = lowest_upper.price - cost_floors.floor_digi_10
                target_adaptive_10 = calculate_adaptive_target_price(
                    floor_min=cost_floors.floor_digi_10,
                    competitor_price=lowest_upper.price,
                    cost_base=cost_floors.cost_base,
                    payout_rate=0.92,
                    large_gap_profit_target=large_cap,
                )
                final_p_10 = find_winning_psychological_price(
                    cost_floors.floor_digi_10, lowest_upper.price, max_ceiling=target_adaptive_10
                )
                if final_p_10 is not None:
                    profit = round((final_p_10 * 0.92) - cost_floors.cost_base)
                    uncapped_p = find_winning_psychological_price(
                        cost_floors.floor_digi_10, lowest_upper.price
                    )
                    if (
                        gap_upper_10 >= 10000.0
                        and uncapped_p is not None
                        and final_p_10 < uncapped_p
                    ):
                        reason = (
                            f"Filtered sub-floor offers. Competitor {lowest_upper.vendor_name} (Rs. {lowest_upper.price:,.0f}) "
                            f"price is inflated. Capped at sweet-spot price Rs. {final_p_10:,.0f} (+Rs. {profit:,} profit on 8% Faysal Bank rate) for sales conversion."
                        )
                    else:
                        reason = (
                            f"Filtered sub-floor offers. Undercut viable competitor {lowest_upper.vendor_name} "
                            f"(Rs. {lowest_upper.price:,.0f}) to winning price Rs. {final_p_10:,.0f} (+Rs. {profit:,} profit on 8% Faysal Bank rate incl. 2% bank spread)."
                        )
                    return PlatformPricingResult(
                        min_price=min_p,
                        max_price=max_p,
                        final_price=final_p_10,
                        real_profit=profit,
                        status="Safe Win (10% Tier)",
                        reason=reason,
                        dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
                        active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable_8],
                        effective_comm="10.00%",
                    )

            gap_upper_8 = lowest_upper.price - cost_floors.floor_digi_8
            target_adaptive_8 = calculate_adaptive_target_price(
                floor_min=cost_floors.floor_digi_8,
                competitor_price=lowest_upper.price,
                cost_base=cost_floors.cost_base,
                payout_rate=0.92,
                large_gap_profit_target=large_cap,
            )
            final_p_upper = find_winning_psychological_price(
                cost_floors.floor_digi_8, lowest_upper.price, max_ceiling=target_adaptive_8
            )
            if final_p_upper is not None:
                profit = round((final_p_upper * 0.92) - cost_floors.cost_base)
                if gap_upper_8 < 100.0:
                    reason = (
                        f"Filtered sub-floor offers. Triggered emergency 8% Faysal Bank rate. Competitor {lowest_upper.vendor_name} "
                        f"(Rs. {lowest_upper.price:,.0f}) gap is tight. Undercut to winning rounded price Rs. {final_p_upper:,.0f} "
                        f"with guaranteed +Rs. {profit:,} profit."
                    )
                else:
                    uncapped_p = find_winning_psychological_price(
                        cost_floors.floor_digi_8, lowest_upper.price
                    )
                    if (
                        gap_upper_8 >= 10000.0
                        and uncapped_p is not None
                        and final_p_upper < uncapped_p
                    ):
                        reason = (
                            f"Filtered sub-floor offers. Triggered emergency 8% Faysal Bank rate. Competitor {lowest_upper.vendor_name} (Rs. {lowest_upper.price:,.0f}) "
                            f"price is inflated. Capped at sweet-spot price Rs. {final_p_upper:,.0f} (+Rs. {profit:,} profit on 8% Faysal Bank rate) for sales conversion."
                        )
                    else:
                        reason = (
                            f"Filtered sub-floor offers. Triggered emergency 8% Faysal Bank rate to undercut "
                            f"upper competitor {lowest_upper.vendor_name} (Rs. {lowest_upper.price:,.0f}) to winning price Rs. {final_p_upper:,.0f} (+Rs. {profit:,} profit)."
                        )
                return PlatformPricingResult(
                    min_price=min_p,
                    max_price=max_p,
                    final_price=final_p_upper,
                    real_profit=profit,
                    status="Win via 8% Switch",
                    reason=reason,
                    dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
                    active_pool=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in viable_8],
                    effective_comm="8.00%",
                )

    # Step D: All sellers below 8% floor -> Safe Fallback to enable catalog upload
    lowest_dropped_obj = min(dropped, key=lambda x: x.price) if dropped else None
    lowest_str = (
        f", lowest: {lowest_dropped_obj.vendor_name} Rs. {lowest_dropped_obj.price:,.0f}"
        if lowest_dropped_obj
        else ""
    )
    final_fallback_p = get_fallback_psychological_price(
        cost_base=cost_floors.cost_base,
        floor_min=cost_floors.floor_digi_8,
        payout_rate=0.92,
        profit_target=FALLBACK_PROFIT,
    )
    profit = round((final_fallback_p * 0.92) - cost_floors.cost_base)
    return PlatformPricingResult(
        min_price=min_p,
        max_price=max_p,
        final_price=final_fallback_p,
        real_profit=profit,
        status="Safe Fallback",
        reason=(
            f"All competitors are selling at a loss (< Floor Rs. {round(cost_floors.floor_digi_8):,}{lowest_str}). "
            f"Undercut skipped to prevent loss. Listed at Safe Fallback Price Rs. {final_fallback_p:,.0f} (+Rs. {profit:,} profit on 8% Faysal Bank rate) "
            f"to ensure catalog upload."
        ),
        dropped=[f"{o.vendor_name} (Rs. {o.price:,.0f})" for o in dropped],
        active_pool=[],
        effective_comm="8.00%",
    )
````

## File: tasks/plan.md
````markdown
# Implementation Plan: 3-Tier Multi-Pattern Search & Robust Unified Referee Engine

## Overview & Executive Summary

Address false monopolies and unmatched "solo" products across brands (especially Dawlance ACs, Refrigerators, Washing Machines, Deep Freezers, and Small Domestic Appliances) by transforming the search and matching architecture into a true **Two-Stage Funnel**:
1. **Stage 1 (Exhaustive 3-Tier Pattern Search & Deduplicated Pooling)**: Remove the premature waterfall early-exit (`break` on $\ge 2$ offers) so all tiered query patterns (exact SKU, bare numeric stem, space/hyphen/prefix permutations, and brand-prefixed variants) execute and merge into an expansive, deduplicated raw candidate pool.
2. **Stage 2 (Unified Centralized Strict Referee)**: Run a robust, noise-resilient referee over the combined candidate pool with clean token normalization (stripping merchant noise, installment text, promo phrases), parenthesis handling, dynamic prefix decoupling (`DWT11467ES` -> `11467`), slash-separated alias tolerance (`Sprinter / Powercon`), and strict guarded facet enforcement (T3, IoT, Capacity, Hardware Tub `WB`/`GB`, Color optionality).

---

## Root Cause Analysis from Empirical Testing (38 Dawlance Products)

Our empirical diagnostic against live AlfaMall & DigiMall APIs on the 38 user-provided Dawlance models revealed:
- **Only 8 of 38 products matched** in the existing implementation, while **30 products became false "solo" (Monopoly priced)**, despite valid listings existing on both portals!
- **Root Cause 1 (Waterfall Premature Exit)**: `scraper.py` terminates query generation as soon as $\ge 2$ offers return for Tier 1, skipping cheaper competitors in Tier 2 and Tier 3 who omitted variant tags or used spaced formats.
- **Root Cause 2 (Noise Pollution in Series Matching)**: Merchant marketing noise (`ElectroEase`, `HomeCart`, `On Installment`, `With Free Delivery`, `Heat & Cool`, `ISPK-0577`) is treated as unmatched "extra series tokens", causing `referee_match` to falsely reject 100% genuine listings (e.g. `Suave+ 30`, `GLACIER 2 Ton FLOOR`).
- **Root Cause 3 (Parenthesis & Punctuation Leakage)**: Punctuation like `(Milky White Textured)` or `Sprinter / Powercon` leaves literal parentheses `(MILKY` or un-split slashes `SPRINTER/POWERCON` in extracted tokens, failing string comparisons.
- **Root Cause 4 (Glued Prefix Extraction)**: Glued catalog SKU codes like `AWM DWT11467ES` or `DW3013AF` fail to decompose into `[Prefix] + [Stem] + [Suffix]` (`DWT` + `11467` + `ES`), searching unindexed strings that return 0 hits.
- **Root Cause 5 (Color Optionality Asymmetry)**: Lack of clear handling when sellers omit the color name on single-color listings versus when sellers list competing color variants (e.g., White target rejecting Silver/Black, but accepting unmentioned color when model matches).

---

## Architectural Decisions

| Decision | Rationale |
| :--- | :--- |
| **Full 3-Tier Query Search (No Early Break)** | Collects all candidate listings from Tier 1 (exact), Tier 2 (bare stem), and Tier 3 (space/prefix permutations) without early exit, ensuring zero hidden competitors are missed. |
| **Comprehensive Merchant & Promo Noise Filtration** | Dynamically strip marketplace junk (merchant signatures, installment terms, warranties, delivery tags, `Heat & Cool`, `DC Inverter`) before computing series token subtraction. |
| **Parenthesis & Punctuation Token Cleaning** | Strip parentheses, brackets, and normalize slashes so `(Milky White Textured)` cleanly maps to `Milky White Textured` color/facets and `Sprinter / Powercon` allows either `Sprinter` or `Powercon`. |
| **Generic Dynamic SKU De-gluing** | Apply generic regex `^([A-Za-z]{2,4})[- ]?(\d+)[- ]?([A-Za-z0-9]*)$` to dynamically break glued codes (e.g. `DWT11467ES` $\to$ Prefix: `DWT`, Stem: `11467`, Suffix: `ES`). |
| **Strict Color Family Collision vs Optional Unmentioned Color** | If target specifies color (e.g. White), reject opposing color families (Silver/Black). If candidate listing does not mention color at all and model matches, accept as unmentioned color. |

---

## Phased Implementation Roadmap

### Phase 1: Exhaustive 3-Tier Pattern Generation & Waterfall Search
- Remove early exit in `pricing_engine/scraper.py` so all tiers query and pool offers.
- Enhance `pricing_engine/matcher.py:generate_search_patterns` to generate glued/de-glued permutations for appliance codes.
- Ensure all queries are collected and deduplicated by `(vendor_name.lower(), round(price, 2))`.

### Phase 2: Title Normalization & Marketing Noise Stripping
- Expand token normalization to strip merchant signatures (`ElectroEase`, `HomeCart`, `ISPK-\d+`, `SNS\d+`, `ET`, `UE\d+`).
- Strip transaction/promo noise (`On Installment`, `Upto \d+ Months`, `0% Markup`, `Free Delivery`, `Special Gift`, `Best Price`).
- Strip common HVAC/appliance operation terms (`Heat & Cool`, `Heat and Cool`, `DC Inverter`) from the Series slot so they don't trigger false "sub-series mismatch".

### Phase 3: Punctuation, Slashes, and Dynamic Initialism Normalization
- Strip parentheses and brackets before slot extraction so `(Milky White Textured)` extracts cleanly.
- Handle slash-separated series names (`Sprinter / Powercon`) by treating them as alternative valid series keywords (OR logic).
- Verify dynamic initialisms (`SD` $\iff$ `Single Door`, `FL` $\iff$ `Front Load`, `TL` $\iff$ `Top Load`).

### Phase 4: Strict Guarded Facets & Color Optionality Enforcement
- Enforce strict T3 compressor guard (T3 target rejects non-T3, non-T3 rejects T3).
- Enforce IoT guard (IoT target rejects non-IoT, non-IoT rejects IoT).
- Enforce Hardware Tub guard (`WB` vs `GB`).
- Enforce Color Family logic: cross-family mismatch rejects; unmentioned color accepted.

### Phase 5: Verification & Benchmark Suite
- Run regression tests on all 38 Dawlance models.
- Run complete test suite (`180+ tests`) ensuring 100% green pass.
- Verify zero float drift and zero ANSI leakage in outputs.
````

## File: tests/test_matcher.py
````python
import pytest

from pricing_engine.matcher import (
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    is_strict_model_match,
    referee_match,
)


@pytest.mark.parametrize(
    ("full_title", "expected_query", "expected_code"),
    [
        (
            "Gree Inverter 1.5 Ton GS-18PITH11W",
            "18PITH11W",
            "18PITH11W",
        ),
        (
            "Gree 1 Ton Fairy Inverter GW-12AITH21W-T3",
            "12AITH21W",
            "12AITH21W-T3",
        ),
        (
            "Gree Floor Standing GF-24FITH1",
            "24FITH1",
            "24FITH1",
        ),
    ],
)
def test_extract_search_query_and_model(
    full_title: str, expected_query: str, expected_code: str
) -> None:
    query, model = extract_search_query_and_model(full_title)
    assert query == expected_query
    assert model.replace("GS-", "").replace("GW-", "").replace("GF-", "") == expected_code


def test_strict_model_match_success() -> None:
    target = "12AITH21W"
    # Exact match in title
    assert is_strict_model_match("Gree Inverter AC 1 Ton 12AITH21W White", target)
    # T3 / AAA variant suffix in title
    assert is_strict_model_match("Gree 12AITH21W-T3 Inverter 1.0 Ton", target)
    # Generic base without color suffix
    assert is_strict_model_match("Gree Inverter 12AITH21 Series", target)


def test_strict_model_match_color_collision_rejection() -> None:
    target = "12AITH21W"  # White target
    # Must reject Black (B)
    assert not is_strict_model_match("Gree 12AITH21B Inverter AC Black", target)
    # Must reject Silver (S)
    assert not is_strict_model_match("Gree 12AITH21S Inverter AC Silver", target)
    # Must reject Grey (G)
    assert not is_strict_model_match("Gree 12AITH21G Inverter AC Grey", target)


def test_strict_model_match_capacity_mismatch_rejection() -> None:
    # 1.5 Ton target must reject 1.0 Ton title
    target = "18PITH11W"
    assert not is_strict_model_match("Gree 12PITH11W Inverter AC 1 Ton", target)
    # 3.0 Ton Floor Standing target must reject 2.0 Ton title
    assert not is_strict_model_match("Gree Floor Standing GF-24TFIH 2 Ton", "36TFIH")
    # 12AITH21W must reject 12AITH24 Pro
    assert not is_strict_model_match("Gree 12AITH24 Pro Inverter AC", "12AITH21W")


def test_strict_model_match_floor_standing_36tfih() -> None:
    target = "36TFIH"
    # Matches Gree Floor Standing GF-36TFIH
    assert is_strict_model_match(
        "Gree - Air Conditioner 3.0 Ton Floor Standing T3 Inverter Heat & Cool - GF-36TFIH",
        target,
    )
    assert is_strict_model_match(
        "Gree | 3.0 Ton | GF-36TFIH | Cabinet | Inverter | Floor Standing",
        target,
    )


def test_strict_model_match_cool_only_vs_heat_cool() -> None:
    # Cool only (PITC) must reject Heat & Cool (PITH)
    target_cool_only = "18PITC12W"
    assert is_strict_model_match(
        "Gree 1.5 Ton Inverter AC GS-18PITC12W-T3 Cool Only", target_cool_only
    )
    assert not is_strict_model_match(
        "Gree 1.5 Ton Inverter AC GS-18PITH12W Heat & Cool", target_cool_only
    )


def test_strict_model_match_black_target_rejects_white() -> None:
    # Target is Black (18AITH21B) -> must reject White (18AITH21W)
    target_black = "18AITH21B"
    assert is_strict_model_match("Gree 1.5 Ton Airy 18AITH21B Black", target_black)
    assert not is_strict_model_match("Gree 1.5 Ton Airy 18AITH21W White", target_black)
    assert not is_strict_model_match("Gree 1.5 Ton Airy 18AITH21 Series", target_black)


def test_strict_model_match_silver_target_rejects_white() -> None:
    # Target is Silver (24PITH11S) -> must reject White (24PITH11W)
    target_silver = "24PITH11S"
    assert is_strict_model_match("Gree 2.0 Ton Pular 24PITH11S Silver", target_silver)
    assert not is_strict_model_match("Gree 2.0 Ton Pular 24PITH11W White", target_silver)


def test_strict_model_match_color_slash_expansion() -> None:
    silver_target = "12AITH24S-T3"
    white_target = "12AITH24W-T3"
    black_target = "12AITH24B-T3"

    # 1. Standard slash: GS-12AITH24W/S matches both Silver and White
    title_standard = "GREE Airy Pro 1 TON Split AC Inverter G-Boost AI T3 GS-12AITH24W/S"
    assert is_strict_model_match(title_standard, silver_target)
    assert is_strict_model_match(title_standard, white_target)
    # But strictly rejects Black
    assert not is_strict_model_match(title_standard, black_target)

    # 2. Hyphenated slash: GS-12AITH24-W/S
    title_hyphen = "Gree Airy Pro 1 Ton GS-12AITH24-W/S Heat & Cool"
    assert is_strict_model_match(title_hyphen, silver_target)
    assert is_strict_model_match(title_hyphen, white_target)

    # 3. Spaced slash: GS-12AITH24 - W/S
    title_spaced = "Gree Airy Pro 1 Ton GS-12AITH24 - W/S Heat & Cool"
    assert is_strict_model_match(title_spaced, silver_target)

    # 4. Trailing -T3 suffix: GS-12AITH24W/S-T3
    title_suffix = "Gree Airy Pro 1 Ton GS-12AITH24W/S-T3 Heat & Cool"
    assert is_strict_model_match(title_suffix, silver_target)
    assert is_strict_model_match(title_suffix, white_target)

    # 5. Trailing space T3 suffix: GS-12AITH24W/S T3
    title_space_suffix = "Gree Airy Pro 1 Ton GS-12AITH24W/S T3 Inverter"
    assert is_strict_model_match(title_space_suffix, silver_target)

    # 5b. Trailing attached T3 (without dash or space): GS-12AITH24W/ST3
    title_attached_suffix = "Gree Airy Pro 1 Ton GS-12AITH24W/ST3 Inverter"
    assert is_strict_model_match(title_attached_suffix, silver_target)
    assert is_strict_model_match(title_attached_suffix, white_target)

    # 6. Single-color isolation: pure White without slash strictly rejects Silver
    pure_white = "GREE Airy Pro 1 TON Split AC Inverter GS-12AITH24W"
    assert not is_strict_model_match(pure_white, silver_target)

    # 7. Extended colors: W/B (White / Black) and W/C (White / Champagne)
    wb_title = "Gree 1.5 Ton Airy GS-18AITH21W/B-T3"
    assert is_strict_model_match(wb_title, "18AITH21W-T3")
    assert is_strict_model_match(wb_title, "18AITH21B-T3")
    assert not is_strict_model_match(wb_title, "18AITH21S-T3")

    wc_title = "Gree 1 Ton Airy GS-12AITH24W/C"
    assert is_strict_model_match(wc_title, "12AITH24W")
    assert is_strict_model_match(wc_title, "12AITH24C")


def test_strict_model_match_series_slash_and_generation_isolation() -> None:
    # 1. Pular batch slash: 14S / 11S
    pular_14s = "12PITH14S"
    pular_11s = "12PITH11S"
    pular_title = "GREE Split AC 1 TON Pular Series Inverter GS-12PITH14S /11S"
    assert is_strict_model_match(pular_title, pular_14s)
    assert is_strict_model_match(pular_title, pular_11s)

    # 2. Pular batch without space: 14S/11S
    assert is_strict_model_match("Gree Pular 1 Ton GS-12PITH14S/11S", pular_14s)
    assert is_strict_model_match("Gree Pular 1 Ton GS-12PITH14S/11S", pular_11s)

    # 3. Generation isolation: ZITH1 and ZITH2 must NEVER match each other
    zeno_1 = "12ZITH1W-T3"
    zeno_2 = "12ZITH2W-T3"
    assert is_strict_model_match("Gree Zeno 1 Ton GS-12ZITH1W Inverter", zeno_1)
    assert not is_strict_model_match("Gree Zeno 1 Ton GS-12ZITH1W Inverter", zeno_2)
    assert is_strict_model_match("Gree Zeno 1 Ton GS-12ZITH2W Inverter", zeno_2)
    assert not is_strict_model_match("Gree Zeno 1 Ton GS-12ZITH2W Inverter", zeno_1)


def test_strict_model_match_pular_shared_color_batch_slashes() -> None:
    target_15g = "GS-24PITH15G-T3"
    target_17g = "GS-24PITH17G-T3"
    target_18g = "GS-24PITH18G-T3"
    target_15w = "GS-24PITH15W-T3"

    # 1. Two-batch with shared color: GS-24PITH15/17G - T3
    title_2batch = "GREE Pular T3 2 TON Split AC GS-24PITH15/17G - T3"
    assert is_strict_model_match(title_2batch, target_15g)
    assert is_strict_model_match(title_2batch, target_17g)
    # Must strictly reject White
    assert not is_strict_model_match(title_2batch, target_15w)

    # 2. Four-batch with shared color: GS-24PITH15/16/17/18G
    title_4batch = "Gree Pular Series 2 Ton Split AC GS-24PITH15/16/17/18G"
    assert is_strict_model_match(title_4batch, target_15g)
    assert is_strict_model_match(title_4batch, target_18g)
    assert not is_strict_model_match(title_4batch, target_15w)

    # 3. Two-batch White with space: GS-24PITH15/ 17W - T3
    title_white_batch = "GREE Pular T3 2 TON Split AC GS-24PITH15/ 17W - T3"
    assert is_strict_model_match(title_white_batch, target_15w)
    # Must strictly reject Grey
    assert not is_strict_model_match(title_white_batch, target_15g)

    # 4. Attached T3 (without dash or space): GS-24PITH15/17GT3
    title_attached = "GREE Pular T3 2 TON Split AC GS-24PITH15/17GT3 Inverter"
    assert is_strict_model_match(title_attached, target_15g)
    assert is_strict_model_match(title_attached, target_17g)
    assert not is_strict_model_match(title_attached, target_15w)


def test_strict_model_match_universal_multivariant_expansion() -> None:
    # 1. Multi-generation slash with trailing tag: GS-18ZITH1W/2W/3W Ultra -T3
    zeno_title = "Gree Split AC GS-18ZITH1W/2W/3W Ultra -T3"
    assert is_strict_model_match(zeno_title, "GS-18ZITH1W-T3")
    assert is_strict_model_match(zeno_title, "GS-18ZITH2W-T3")
    assert is_strict_model_match(zeno_title, "GS-18ZITH3W-T3")
    assert not is_strict_model_match(zeno_title, "GS-18ZITH4W-T3")
    assert not is_strict_model_match(zeno_title, "GS-12ZITH2W-T3")

    # 2. Pure standalone isolation: GS-18ZITH1W-T3 must NOT match target GS-18ZITH2W-T3
    standalone_gen1 = "Gree Split AC GS-18ZITH1W-T3"
    assert not is_strict_model_match(standalone_gen1, "GS-18ZITH2W-T3")

    # 3. Floor standing multi-variant: GF-24FITH1/2
    floor_title = "Gree Floor Standing Cabinet GF-24FITH1/2 Inverter"
    assert is_strict_model_match(floor_title, "24FITH1")
    assert is_strict_model_match(floor_title, "24FITH2")
    assert not is_strict_model_match(floor_title, "24FITH3")

    # 4. Hyphenated and parenthesized variants
    assert is_strict_model_match("Gree Zeno Inverter GS-18ZITH-1W/2W/3W", "GS-18ZITH2W-T3")
    assert is_strict_model_match("Gree Zeno Inverter GS-18ZITH (1W/2W/3W)", "GS-18ZITH2W-T3")
    assert is_strict_model_match("Gree Zeno Inverter GS-18ZITH [1W/2W/3W]", "GS-18ZITH2W-T3")
    assert is_strict_model_match("Gree 2.0 Ton Pular GS-24PITH (15/17G)", "GS-24PITH17G-T3")
    assert is_strict_model_match("Gree 1.0 Ton Airy GS-12AITH24 (W/S)", "GS-12AITH24W-T3")

    # 5. Commercial Floor Standing capacity isolation (24 vs 36 Ton)
    assert not is_strict_model_match("Gree Floor Standing GF-24TFIH 2 Ton", "36TFIH")
    assert not is_strict_model_match("Gree Floor Standing GF-36TFIH 3 Ton", "24TFIH")


def test_electronics_world_headline_case() -> None:
    """Verify headline case: Electronics World listing with hyphenated tag on both sides."""
    title_ew = "Gree GS-24AITH21W-T3/21B-T3 2.0 Ton Inverter Split AC"
    assert is_strict_model_match(title_ew, "24AITH21B-T3")
    assert is_strict_model_match(title_ew, "24AITH21W-T3")
    assert is_strict_model_match(title_ew, "24AITH21B")
    assert is_strict_model_match(title_ew, "24AITH21W")
    assert not is_strict_model_match(title_ew, "24AITH21S-T3")

    # Cross-color isolation: pure black vs pure white must NEVER match
    black_only = "Gree GS-24AITH21B-T3 2.0 Ton Inverter Split AC"
    assert is_strict_model_match(black_only, "24AITH21B")
    assert not is_strict_model_match(black_only, "24AITH21W")
    white_only = "Gree GS-24AITH21W-T3 2.0 Ton Inverter Split AC"
    assert is_strict_model_match(white_only, "24AITH21W")
    assert not is_strict_model_match(white_only, "24AITH21B")


def test_multibrand_extractor_and_compound_colors() -> None:
    """Verify brand-agnostic extraction across 768 products, stripping compound colors without hardcoded lists."""
    test_cases = [
        ("DAW AUTO W/M DWT-1165 PL", "Dawlance", "DWT-1165", "DWT-1165 PL"),
        ("DAW AUTO W/M DWT-11671 FLT", "Dawlance", "DWT-11671", "DWT-11671 FLT"),
        ("DAW AUTO W/M DWT-1006 MYSTIC GREY", "Dawlance", "DWT-1006", "DWT-1006"),
        ("DAW AUTO W/M DWT-14470 ES", "Dawlance", "DWT-14470", "DWT-14470 ES"),
        ("HAIER AUTO W/M 100-1269 S6", "Haier", "100-1269", "100-1269 S6"),
        ("HAIER AUTO W/M 100-316S6 GC", "Haier", "100-316S6", "100-316S6 GC"),
        ("HAIER AUTO W/M 110-688S8 BLACK -", "Haier", "110-688S8", "110-688S8"),
        ("HOMAGE M/O HDG-201S", "Homage", "HDG-201S", "HDG-201S"),
        ("HOMAGE M/OVEN HDG-2312B", "Homage", "HDG-2312B", "HDG-2312B"),
        ("KENWOOD CASSETTE 1.5TON NORMAL KCT-1801H", "Kenwood", "KCT-1801H", "KCT-1801H"),
        ("MIDEA CASSETTE 2TON INVERTER MCD1-24HRDN1", "Midea", "MCD1-24HRDN1", "MCD1-24HRDN1"),
        ("UCOOL AIR CURTAIN 3FEET UCA-315Y", "UCOOL", "UCA-315Y", "UCA-315Y"),
        ("MOULINEX BLENDER 3IN1 LM242025", "Moulinex", "LM242025", "LM242025"),
        ("ECOSTAR SPLIT AC 1 ΤΟN 12NV01WT3", "EcoStar", "12NV01WT3", "12NV01WT3"),
        ("MIDEA DISHWAHSER WQP12-5201F INVERTER BLACK 13SETS", "Midea", "WQP12", "WQP12-5201F"),
        ("HOMAGE SDA SANDWICH MAKER 3IN1 HSM-70300-", "Homage", "HSM-70300", "HSM-70300"),
    ]
    for full_name, brand, exp_query, exp_model in test_cases:
        q, m = extract_search_query_and_model(full_name, brand)
        assert q == exp_query, f"Failed query for {full_name}: got {q}, expected {exp_query}"
        assert m == exp_model, f"Failed model for {full_name}: got {m}, expected {exp_model}"


def test_multibrand_slash_multivariant_expansion() -> None:
    """Verify that multi-brand slash models (Dawlance, Homage) expand correctly."""
    # Dawlance washing machines
    daw_title = "Dawlance Auto W/M DWT-1165/1167 PL Glass Door"
    assert is_strict_model_match(daw_title, "DWT-1165 PL")
    assert is_strict_model_match(daw_title, "DWT-1167 PL")
    assert not is_strict_model_match(daw_title, "DWT-1168 PL")

    # Homage microwave ovens
    homage_title = "Homage Microwave Oven HDG-2312/2313B Digital"
    assert is_strict_model_match(homage_title, "HDG-2312B")
    assert is_strict_model_match(homage_title, "HDG-2313B")
    assert not is_strict_model_match(homage_title, "HDG-2314B")


def test_non_model_safeguards_unmodified() -> None:
    """Verify category acronyms and fractions are 100% untouched."""
    from pricing_engine.matcher import expand_multivariant_titles

    assert expand_multivariant_titles("DAW AUTO W/M DWT-1165 PL") == "DAW AUTO W/M DWT-1165 PL"
    assert expand_multivariant_titles("DAW D/F 9199 H&C Inverter") == "DAW D/F 9199 H&C Inverter"
    assert (
        expand_multivariant_titles("Gree Inverter Heat / Cool Split AC")
        == "Gree Inverter Heat / Cool Split AC"
    )
    assert expand_multivariant_titles("Midea Front Load 12W/8D KG") == "Midea Front Load 12W/8D KG"


def test_technical_slash_safeguards() -> None:
    """Verify technical slashes (/DC, /AC, /KB-xx, /YY year codes, W/O) are NOT expanded."""
    from pricing_engine.matcher import expand_multivariant_titles

    # Haier Cassette /DC (Direct Current) — NOT a variant separator
    assert (
        expand_multivariant_titles("HAIER CASSETTE 1.5TON INVERTER 18HE/DC")
        == "HAIER CASSETTE 1.5TON INVERTER 18HE/DC"
    )
    assert (
        expand_multivariant_titles("HAIER CASSETTE 4TON INVERTER HBU-48E/DC")
        == "HAIER CASSETTE 4TON INVERTER HBU-48E/DC"
    )
    assert (
        expand_multivariant_titles("HAIER FLOOR STANDING 48CE/DC INVERTER")
        == "HAIER FLOOR STANDING 48CE/DC INVERTER"
    )

    # Haier complex technical model
    assert (
        expand_multivariant_titles("HAIER FLOOR 4TON INVERTER HBU-48HE/T3DC-012GE")
        == "HAIER FLOOR 4TON INVERTER HBU-48HE/T3DC-012GE"
    )

    # Haier subordinate model code /KB-01
    assert (
        expand_multivariant_titles("HAIER CASSETTE 2TON NORMAL 24CE03/KB-01")
        == "HAIER CASSETTE 2TON NORMAL 24CE03/KB-01"
    )

    # Gaba National year codes /21, /20, /23
    assert (
        expand_multivariant_titles("GABA NATIONAL HOT PLATE GN-261/21")
        == "GABA NATIONAL HOT PLATE GN-261/21"
    )
    assert (
        expand_multivariant_titles("GABA NATIONAL SANDWITCH MAKER GNE-396/20")
        == "GABA NATIONAL SANDWITCH MAKER GNE-396/20"
    )
    assert (
        expand_multivariant_titles("GABA NATIONAL SPINNER GND-1606/23")
        == "GABA NATIONAL SPINNER GND-1606/23"
    )

    # W/O = "Without" — NOT a variant separator
    assert expand_multivariant_titles("DAW W/D 1060 W/O REF WHITE") == "DAW W/D 1060 W/O REF WHITE"


def test_technical_suffix_model_match() -> None:
    """Verify is_strict_model_match handles technical slash suffixes (/DC, /AC, /KB-xx, /YY)."""
    # 18HE/DC: exact match
    assert is_strict_model_match("Haier Cassette 18HE/DC Inverter 1.5 Ton", "18HE/DC")
    # 18HE/DC: partial match — seller omitted /DC
    assert is_strict_model_match("Haier Cassette 18HE Inverter 1.5 Ton", "18HE/DC")
    # Reverse: our catalog says 18HE, listing says 18HE/DC — should still match
    assert is_strict_model_match("Haier Cassette 18HE/DC Inverter", "18HE")
    # Capacity mismatch: 24HE/DC vs 18HE/DC — must reject
    assert not is_strict_model_match("Haier Cassette 24HE/DC Inverter 2 Ton", "18HE/DC")

    # HBU-48E/DC: exact + partial
    assert is_strict_model_match("Haier Cassette HBU-48E/DC Inverter 4 Ton", "HBU-48E/DC")
    assert is_strict_model_match("Haier Cassette HBU-48E Inverter 4 Ton", "HBU-48E/DC")

    # 48CE/DC
    assert is_strict_model_match("Haier Floor Standing 48CE/DC Inverter", "48CE/DC")
    assert is_strict_model_match("Haier Floor Standing 48CE Inverter", "48CE/DC")

    # GN-261/21: exact match
    assert is_strict_model_match("Gaba National GN-261/21 Hot Plate", "GN-261/21")
    # GN-261/21: seller omitted year
    assert is_strict_model_match("Gaba National GN-261 Hot Plate", "GN-261/21")
    # GN-261/21 must NOT match GN-262
    assert not is_strict_model_match("Gaba National GN-262/21 Hot Plate", "GN-261/21")

    # 24CE03/KB-01: exact match
    assert is_strict_model_match("Haier Cassette 24CE03/KB-01 Normal 2 Ton", "24CE03/KB-01")
    # 24CE03/KB-01: seller omitted subordinate code
    assert is_strict_model_match("Haier Cassette 24CE03 Normal 2 Ton", "24CE03/KB-01")


def test_name_only_extraction_dawlance_acs() -> None:
    """Verify name-only Dawlance ACs extract meaningful search queries and keyword models."""
    # AVANTE 30 CLASSIC — query should contain Avante+30, model should include CLASSIC
    q, m = extract_search_query_and_model("DAW SPLIT AC AVANTE INVERTER 30 (CLASSIC", "Dawlance")
    assert "Avante" in q or "AVANTE" in q.upper()
    assert "30" in q
    assert "AVANTE" in m.upper()
    assert "30" in m
    assert "CLASSIC" in m.upper()

    # AVANTE 30 ELEGANT — differentiated from CLASSIC
    q2, m2 = extract_search_query_and_model("DAW SPLIT AC AVANTE INVERTER 30 (ELEGANT", "Dawlance")
    assert "AVANTE" in q2.upper()
    assert "ELEGANT" in m2.upper()
    assert "CLASSIC" not in m2.upper()

    # FROST 20 COOL ONLY vs FROST 30 COOL ONLY — capacity differentiation
    q3, m3 = extract_search_query_and_model(
        "DAW SPLIT AC FROST INVERTER 20 (COOL ONLY)", "Dawlance"
    )
    assert "FROST" in q3.upper()
    assert "20" in m3
    q4, m4 = extract_search_query_and_model(
        "DAW SPLIT AC FROST INVERTER 30 (COOL ONLY)", "Dawlance"
    )
    assert "30" in m4
    assert m3 != m4  # Different capacities must produce different models

    # CHROME 30 WHITE
    q5, m5 = extract_search_query_and_model("DAW SPLIT AC CHROME INVERTER 30 WHITE", "Dawlance")
    assert "CHROME" in q5.upper()
    assert "WHITE" in m5.upper()

    # ENERCON X 15 — X is part of series name
    q6, m6 = extract_search_query_and_model("DAW SPLIT AC ENERCON X INVERTER 15", "Dawlance")
    assert "ENERCON" in q6.upper()
    assert "ENERCON" in m6.upper()
    assert "X" in m6.upper().split()
    assert "15" in m6

    # DUAL PRO T3 15 — T3 is part of model name
    q7, m7 = extract_search_query_and_model("DAW SPLIT AC DUAL PRO T3 INVERTER 15", "Dawlance")
    assert "DUAL" in m7.upper()
    assert "PRO" in m7.upper()
    assert "T3" in m7.upper()
    assert "15" in m7

    # MEGA T3 PRO 30
    q8, m8 = extract_search_query_and_model("DAW SPLIT AC MEGA T3 PRO INVERTER 30", "Dawlance")
    assert "MEGA" in m8.upper()
    assert "T3" in m8.upper()
    assert "30" in m8

    # Existing model-code products must NOT be affected
    q_gree, m_gree = extract_search_query_and_model("Gree Inverter 1.5 Ton GS-18PITH11W", "Gree")
    assert q_gree == "18PITH11W"


def test_keyword_match_mode() -> None:
    """Verify keyword match mode: ALL keywords must appear in seller title."""
    # AVANTE 30 CLASSIC — all keywords match
    assert is_strict_model_match(
        "Dawlance Avante Inverter 1.5 Ton Classic Gold", "AVANTE 30 CLASSIC"
    )
    # AVANTE 30 CLASSIC must reject ELEGANT
    assert not is_strict_model_match(
        "Dawlance Avante Inverter 1.5 Ton Elegant Silver", "AVANTE 30 CLASSIC"
    )
    # AVANTE 30 ELEGANT — correct match
    assert is_strict_model_match(
        "Dawlance Avante Inverter 1.5 Ton Elegant Silver", "AVANTE 30 ELEGANT"
    )

    # CHROME 30 WHITE vs CHROME 45 COPPER — capacity isolation
    assert is_strict_model_match("Dawlance Chrome Inverter 1.5 Ton White", "CHROME 30 WHITE")
    assert not is_strict_model_match("Dawlance Chrome+ Inverter 2 Ton Copper", "CHROME 30 WHITE")

    # ENERCON X 15 — X is required
    assert is_strict_model_match("Dawlance Enercon X Inverter 1 Ton", "ENERCON X 15")


def test_keyword_match_t3_isolation() -> None:
    """Verify T3 isolation: non-T3 target rejects T3 listings and vice versa."""
    # SPRINTER 30 (non-T3) must reject T3 listing
    assert not is_strict_model_match("Dawlance Sprinter T3 X Inverter 1.5 Ton", "SPRINTER 30")
    # SPRINTER 30 (non-T3) matches non-T3 listing
    assert is_strict_model_match("Dawlance Sprinter Inverter 1.5 Ton", "SPRINTER 30")

    # SPRINTER T3 X 30 (T3 product) must reject non-T3 listing
    assert not is_strict_model_match("Dawlance Sprinter Inverter 1.5 Ton", "SPRINTER T3 X 30")
    # SPRINTER T3 X 30 matches T3 listing
    assert is_strict_model_match("Dawlance Sprinter T3 X Inverter 1.5 Ton", "SPRINTER T3 X 30")

    # MAGNA T3 30 MILKY — T3 is in target, must require T3 in seller
    assert is_strict_model_match(
        "Dawlance Magna T3 Inverter 1.5 Ton Milky White", "MAGNA T3 30 MILKY"
    )
    assert not is_strict_model_match("Dawlance Magna Inverter 1.5 Ton Silver", "MAGNA T3 30 MILKY")

    # Model-code T3 (Gree) should NOT be affected — T3 is auxiliary tag, soft match
    assert is_strict_model_match("Gree 12AITH21W-T3 Inverter AC", "12AITH21W")
    assert is_strict_model_match("Gree 12AITH21W Inverter AC", "12AITH21W-T3")


def test_hyphenated_numeric_skus_and_plus_models() -> None:
    """Verify Haier numeric hyphenated SKUs, pure numbers, and Dawlance '+' series."""
    # Haier washing machines: 100-1269 S6
    assert is_strict_model_match("HAIER AUTO W/M 100-1269 S6", "100-1269 S6")
    assert is_strict_model_match("Haier Automatic Washing Machine 100-1269 S6", "100-1269")
    # Capacity / model isolation: 100-1269 must not match 100-826
    assert not is_strict_model_match("HAIER AUTO W/M 100-826 S6", "100-1269 S6")

    # Haier spinners: 60-50, 80-60
    assert is_strict_model_match("HAIER SPINNER 60-50", "60-50")
    assert is_strict_model_match("HAIER SPINNER 80-60", "80-60")
    assert not is_strict_model_match("HAIER SPINNER 60-50", "80-60")

    # Pure numeric model codes: 1060, 183 S.S
    assert is_strict_model_match("DAW W/D 1060 W/O REF WHITE", "1060")
    assert is_strict_model_match("GABA NATIONAL R/F 183 S.S", "183 S.S")
    assert is_strict_model_match("Gaba National Refrigerator 183 SS", "183 S.S")

    # Dawlance ACs with '+' in series name
    assert is_strict_model_match("DAW FLOOR STANDING GLAMOUR+ INVERTER 45", "GLAMOUR+ 45")
    assert is_strict_model_match("Dawlance Glamour Inverter 2 Ton", "GLAMOUR+ 45")
    assert is_strict_model_match("DAW SPLIT AC ECONO+ X INVERTER 15", "ECONO+ X 15")
    assert is_strict_model_match("DAW SPLIT AC MEGA T+ 10", "MEGA T+ 10")


def test_multibrand_universal_capacity_mappings() -> None:
    """Verify Universal AC capacity structure (Gree, Haier, Orient, PEL, Kenwood) alongside Dawlance.

    Universal standard (BTU / 1,000):
    09/9 = 0.75 Ton, 12 = 1.0 Ton, 18 = 1.5 Ton, 24 = 2.0 Ton, 28/30 = 2.5 Ton

    Dawlance custom standard:
    10 = 0.75 Ton, 15 = 1.0 Ton, 20 = 1.25 Ton, 30 = 1.5 Ton, 45 = 2.0 Ton
    """
    # 1. Haier: 18 = 1.5 Ton, 12 = 1.0 Ton, 24 = 2.0 Ton
    assert is_strict_model_match(
        "Haier Inverter 1.5 Ton Pearl White", "PEARL 18 WHITE", brand="Haier"
    )
    assert is_strict_model_match(
        "Haier Inverter 1.5Ton Pearl White", "PEARL 18 WHITE", brand="Haier"
    )
    assert not is_strict_model_match(
        "Haier Inverter 1.0 Ton Pearl White", "PEARL 18 WHITE", brand="Haier"
    )
    assert not is_strict_model_match(
        "Haier Inverter 2.0 Ton Pearl White", "PEARL 18 WHITE", brand="Haier"
    )
    assert is_strict_model_match("Haier Inverter 1 Ton HSU-12HFP", "12HFP", brand="Haier")

    # 2. Gree: 09 = 0.75 Ton, 12 = 1.0 Ton, 24 = 2.0 Ton, 28/30 = 2.5 Ton
    assert is_strict_model_match("Gree Inverter AC 0.75 Ton Pular", "PULAR 09", brand="Gree")
    assert is_strict_model_match("Gree Inverter AC 1 Ton Fairy", "FAIRY 12", brand="Gree")
    assert is_strict_model_match("Gree Inverter AC 1.0 Ton Fairy", "FAIRY 12", brand="Gree")
    assert not is_strict_model_match("Gree Inverter AC 1.5 Ton Fairy", "FAIRY 12", brand="Gree")
    assert is_strict_model_match("Gree Inverter AC 2 Ton Airy", "AIRY 24", brand="Gree")
    assert is_strict_model_match("Gree Inverter AC 2.5 Ton Pular", "PULAR 28", brand="Gree")
    assert is_strict_model_match("Gree Inverter AC 2.5 Ton Pular", "PULAR 30", brand="Gree")
    # In Gree, 30 is 2.5 Ton — must reject 1.5 Ton!
    assert not is_strict_model_match("Gree Inverter AC 1.5 Ton Pular", "PULAR 30", brand="Gree")

    # 3. Orient: 18 = 1.5 Ton, 24 = 2.0 Ton
    assert is_strict_model_match("Orient Inverter 1.5 Ton Ultron", "ULTRON 18", brand="Orient")
    assert is_strict_model_match("Orient Inverter 2 Ton Ultron", "ULTRON 24", brand="Orient")
    assert is_strict_model_match("Orient Inverter 2.0 Ton Ultron", "ULTRON 24", brand="Orient")
    assert not is_strict_model_match("Orient Inverter 1.5 Ton Ultron", "ULTRON 24", brand="Orient")

    # 4. PEL: 18 = 1.5 Ton, 12 = 1.0 Ton
    assert is_strict_model_match("PEL Split AC 1.5 Ton Inverter Ace", "ACE 18", brand="PEL")
    assert not is_strict_model_match("PEL Split AC 1.0 Ton Inverter Ace", "ACE 18", brand="PEL")
    # Catalog extraction test for PEL explicit 1.5TON phrase
    q_pel, m_pel = extract_search_query_and_model("PEL SPLIT AC 1.5TON INVERTER ACE", "PEL")
    assert "18" in q_pel
    assert "18" in m_pel
    assert is_strict_model_match("PEL Split AC 1.5 Ton Inverter Ace", m_pel, brand="PEL")

    # 5. Kenwood: 18 = 1.5 Ton, 09 = 0.75 Ton
    assert is_strict_model_match("Kenwood Inverter 1.5 Ton eSmart", "ESMART 18", brand="Kenwood")
    assert is_strict_model_match("Kenwood Inverter 0.75 Ton eSmart", "ESMART 09", brand="Kenwood")
    assert not is_strict_model_match(
        "Kenwood Inverter 1.0 Ton eSmart", "ESMART 09", brand="Kenwood"
    )

    # 6. Disambiguation of '30' (Dawlance 1.5 Ton vs Gree/Universal 2.5 Ton)
    assert is_strict_model_match(
        "Dawlance Avante Inverter 1.5 Ton Classic Gold", "AVANTE 30 CLASSIC", brand="Dawlance"
    )
    assert not is_strict_model_match(
        "Dawlance Avante Inverter 2.5 Ton Classic Gold", "AVANTE 30 CLASSIC", brand="Dawlance"
    )
    assert is_strict_model_match("Gree Inverter AC 2.5 Ton Pular", "PULAR 30", brand="Gree")
    assert not is_strict_model_match("Gree Inverter AC 1.5 Ton Pular", "PULAR 30", brand="Gree")

    # 7. Brand auto-detection from title when brand arg is not explicitly provided
    assert is_strict_model_match("Haier Inverter 1.5 Ton Pearl White", "PEARL 18 WHITE")
    assert is_strict_model_match(
        "Dawlance Avante Inverter 1.5 Ton Classic Gold", "AVANTE 30 CLASSIC"
    )
    assert is_strict_model_match("Gree Inverter AC 1.0 Ton Fairy", "FAIRY 12")
    assert is_strict_model_match("Orient Inverter 2.0 Ton Ultron", "ULTRON 24")
    assert is_strict_model_match("Kenwood Inverter 1.5 Ton eSmart", "ESMART 18")


def test_generate_search_patterns_haier_washing_machine() -> None:
    patterns = generate_search_patterns(
        "HAIER TOP LOAD HWM 120-826S6 GC WASHING MACHINE", brand="Haier"
    )
    assert "tier_1" in patterns
    assert "tier_2" in patterns
    assert "tier_3" in patterns
    assert any("120-826S6 GC" in p for p in patterns["tier_1"])
    assert any("120-826S6" in p for p in patterns["tier_2"])
    # Tier 3 spaced/glued/prefixed
    assert any("120 826S6" in p for p in patterns["tier_3"])
    assert any("HWM" in p for p in patterns["tier_3"])


def test_generate_search_patterns_variant_preservation() -> None:
    # WB / GB hardware variant code must NOT be stripped from bare stem
    patterns = generate_search_patterns("HAIER WASHING MACHINE HWM 80-1217WB", brand="Haier")
    assert any("80-1217WB" in p for p in patterns["tier_1"])
    assert any("80-1217WB" in p for p in patterns["tier_2"])
    # WB must not be dropped into just '80-1217'
    assert "80-1217" not in patterns["tier_2"]


def test_generate_search_patterns_tv() -> None:
    patterns = generate_search_patterns("HAIER LED 50S80EUX 4K SMART", brand="Haier")
    assert any("50S80EUX" in p for p in patterns["tier_1"])
    assert any("S80EUX" in p for p in patterns["tier_2"])
    assert any("50 S80EUX" in p for p in patterns["tier_3"])


def test_generate_search_patterns_gree_ac() -> None:
    patterns = generate_search_patterns("GREE SPLIT AC GS-12AITH21W-T3", brand="Gree")
    assert any("12AITH21W-T3" in p for p in patterns["tier_1"])
    assert any("12AITH21W" in p for p in patterns["tier_2"])
    assert any(
        "GS-12AITH21W" in p or "GS-12AITH21W-T3" in p or "12AITH21" in p for p in patterns["tier_3"]
    )


def test_generate_search_patterns_dawlance_series_ac() -> None:
    patterns = generate_search_patterns("DAWLANCE SPLIT AC MAGNA 30 INVERTER", brand="Dawlance")
    assert any("MAGNA 30" in p for p in patterns["tier_1"])
    assert any("MAGNA" in p for p in patterns["tier_2"])
    assert any("MAGNA 1.5 TON" in p for p in patterns["tier_3"])


def test_generate_search_patterns_refrigerator() -> None:
    patterns = generate_search_patterns("DAWLANCE REFRIGERATOR 276EBS SILVER", brand="Dawlance")
    assert any("276EBS" in p for p in patterns["tier_1"])
    assert any("276EBS" in p for p in patterns["tier_2"])
    assert any("276 EBS" in p or "276-EBS" in p for p in patterns["tier_3"])


# ==============================================================================
# PHASE 3: 4-SLOT STRUCTURAL EXTRACTION & NEGATIVE-COLLISION REFEREE TESTS
# ==============================================================================


def test_extract_product_slots_haier_washing_machine() -> None:
    title = "HAIER TOP LOAD HWM 120-826S6 GC WASHING MACHINE"
    slots = extract_product_slots(title, brand="Haier")
    assert slots.anchor == "120-826S6"
    assert "GC" in slots.residuals
    assert slots.guarded_facets.capacity in ("12KG", "12")


def test_referee_match_haier_washing_machine_synonyms() -> None:
    target_slots = extract_product_slots(
        "HAIER TOP LOAD HWM 120-826S6 GC WASHING MACHINE", brand="Haier"
    )
    decision1 = referee_match(
        target_slots, "Haier 120-826S6 Glass Door Washing Machine", brand="Haier"
    )
    assert decision1.is_match is True
    assert "Accepted" in decision1.reason

    decision2 = referee_match(target_slots, "Haier HWM 120-826S6 GC Auto", brand="Haier")
    assert decision2.is_match is True


def test_referee_match_hardware_tub_rejection() -> None:
    # 80-1217WB (Single/White) vs 80-1217GB (Grey/Twin)
    target_slots = extract_product_slots("HAIER WASHING MACHINE HWM 80-1217WB", brand="Haier")
    assert target_slots.guarded_facets.tub_series == "WB"

    decision = referee_match(target_slots, "Haier Washing Machine HWM 80-1217GB", brand="Haier")
    assert decision.is_match is False
    assert "Hardware tub mismatch" in decision.reason or "Collision" in decision.reason


def test_referee_match_t3_isolation() -> None:
    # Non-T3 target strictly rejects T3 listings
    target_non_t3 = extract_product_slots("DAWLANCE SPLIT AC MAGNA 30 INVERTER", brand="Dawlance")
    assert target_non_t3.guarded_facets.t3 is False or target_non_t3.guarded_facets.t3 is None

    decision_rej = referee_match(
        target_non_t3, "Dawlance Magna Inverter AC 1.5 Ton T3", brand="Dawlance"
    )
    assert decision_rej.is_match is False
    assert "T3 mismatch" in decision_rej.reason

    # T3 target strictly rejects non-T3 listings
    target_t3 = extract_product_slots("DAWLANCE SPLIT AC MAGNA T3 30 INVERTER", brand="Dawlance")
    assert target_t3.guarded_facets.t3 is True

    decision_rej_non_t3 = referee_match(
        target_t3, "Dawlance Magna Inverter AC 1.5 Ton", brand="Dawlance"
    )
    assert decision_rej_non_t3.is_match is False
    assert "T3 mismatch" in decision_rej_non_t3.reason

    # T3 target matches T3 listing
    decision_acc_t3 = referee_match(
        target_t3, "Dawlance Magna 1.5 Ton T3 Inverter", brand="Dawlance"
    )
    assert decision_acc_t3.is_match is True


def test_referee_match_tv_screen_size_collision() -> None:
    target_slots = extract_product_slots("HAIER LED 50S80EUX 4K SMART", brand="Haier")
    assert target_slots.guarded_facets.capacity in ("50INCH", "50")

    # 50 matches 50
    decision_pass = referee_match(target_slots, "Haier Smart 4K LED 50 S80EUX", brand="Haier")
    assert decision_pass.is_match is True

    # 50 strictly rejects 43
    decision_fail = referee_match(target_slots, "Haier Smart 4K LED 43S80EUX", brand="Haier")
    assert decision_fail.is_match is False
    assert (
        "Capacity / screen size mismatch" in decision_fail.reason
        or "mismatch" in decision_fail.reason.lower()
    )


def test_referee_match_refrigerator_color_families() -> None:
    target_slots = extract_product_slots("DAWLANCE REFRIGERATOR 276EBS SILVER", brand="Dawlance")
    assert target_slots.guarded_facets.color_family == "Grey / Silver"

    # Same family: Metallic Grey / Steel matches Silver
    decision_same_fam = referee_match(
        target_slots, "Dawlance Refrigerator 276EBS Metallic Grey", brand="Dawlance"
    )
    assert decision_same_fam.is_match is True

    # Cross family: Black collides with Silver
    decision_black = referee_match(
        target_slots, "Dawlance Refrigerator 276EBS Midnight Black", brand="Dawlance"
    )
    assert decision_black.is_match is False
    assert "Color collision" in decision_black.reason or "Color mismatch" in decision_black.reason

    # Model collision: 276EBS vs 276EPR
    decision_model = referee_match(
        target_slots, "Dawlance Refrigerator 276EPR RED", brand="Dawlance"
    )
    assert decision_model.is_match is False


def test_referee_match_sub_series_integrity() -> None:
    # CHROME PRO vs CHROME: PRO is a required sub-series differentiator
    target_pro = extract_product_slots("DAWLANCE INVERTER CHROME PRO 30", brand="Dawlance")
    assert "PRO" in target_pro.series.upper()

    decision_missing_pro = referee_match(
        target_pro, "Dawlance Inverter AC Chrome 1.5 Ton", brand="Dawlance"
    )
    assert decision_missing_pro.is_match is False
    assert (
        "sub-series" in decision_missing_pro.reason.lower()
        or "missing" in decision_missing_pro.reason.lower()
    )

    # AVANTE CLASSIC vs AVANTE ELEGANT
    target_classic = extract_product_slots("DAWLANCE AVANTE CLASSIC 30", brand="Dawlance")
    decision_diff_series = referee_match(
        target_classic, "Dawlance Avante Elegant 1.5 Ton", brand="Dawlance"
    )
    assert decision_diff_series.is_match is False


def test_minibar_4467_sd_extraction_and_search_patterns() -> None:
    _, model = extract_search_query_and_model("DAWLANCE DMB 4467 SD MINI BAR", brand="Dawlance")
    assert "4467" in model

    patterns = generate_search_patterns("DAWLANCE DMB 4467 SD MINI BAR", brand="Dawlance")
    assert any("Dawlance 4467" in p for p in patterns["tier_1"])
    assert any("DMB 4467" in p for p in patterns["tier_1"])
    assert any("DMB-4467" in p for p in patterns["tier_2"])


def test_minibar_4467_sd_dynamic_brand_and_door_type_matching() -> None:
    target = "4467 SD"

    # Match exact model with DMB prefix
    assert is_strict_model_match("Dawlance Refrigerator DMB-4467 SD", target, brand="Dawlance")

    # Match with Single Door expansion
    assert is_strict_model_match(
        "Dawlance 4467 Single Door Bedroom Refrigerator", target, brand="Dawlance"
    )

    # Reject foreign brand (Haier) without hardcoded brand list
    assert not is_strict_model_match("Haier Refrigerator 4467", target, brand="Dawlance")

    # Reject non-appliance item
    assert not is_strict_model_match("Adidas 4467 Running Shoes", target, brand="Dawlance")

    # Reject door collision: Single Door target must reject Double Door offer
    assert not is_strict_model_match(
        "Dawlance Double Door Refrigerator 4467 DD", target, brand="Dawlance"
    )


def test_generate_search_patterns_duplicate_brand_prevention() -> None:
    # 1. Product Name already starts with Brand (case insensitive)
    patterns = generate_search_patterns("HAIER 4607 SD", brand="Haier")
    assert "Haier 4607" in patterns["tier_1"]
    assert not any("Haier Haier" in p for tier in patterns.values() for p in tier)

    # 2. Product Name has repeated Brand name
    patterns_double = generate_search_patterns("Haier Haier 4607 SD", brand="Haier")
    assert "Haier 4607" in patterns_double["tier_1"]
    assert not any("Haier Haier" in p for tier in patterns_double.values() for p in tier)

    # 3. Product Name has hyphenated brand
    patterns_hyphen = generate_search_patterns("haier-4607 sd", brand="haier")
    assert "haier 4607" in patterns_hyphen["tier_1"]
    assert not any("haier haier" in p.lower() for tier in patterns_hyphen.values() for p in tier)


def test_gd_vs_inox_hardware_finish_isolation() -> None:
    # 1. DSS-9055 GD vs INOX
    assert not is_strict_model_match(
        "Dawlance Refrigerator DSS-9055 INOX", "DSS-9055 GD", brand="Dawlance"
    )
    assert not is_strict_model_match(
        "Dawlance Refrigerator DSS-9055 Stainless Steel", "DSS-9055 GD", brand="Dawlance"
    )
    assert is_strict_model_match(
        "Dawlance Refrigerator DSS-9055 GD", "DSS-9055 GD", brand="Dawlance"
    )
    assert is_strict_model_match(
        "Dawlance Refrigerator DSS-9055 Glass Door", "DSS-9055 GD", brand="Dawlance"
    )

    # 2. DSS9055 INOX vs GD
    assert not is_strict_model_match(
        "Dawlance Refrigerator DSS-9055 GD", "DSS9055 INOX", brand="Dawlance"
    )
    assert not is_strict_model_match(
        "Dawlance Refrigerator DSS-9055 Glass Door", "DSS9055 INOX", brand="Dawlance"
    )
    assert is_strict_model_match(
        "Dawlance Refrigerator DSS-9055 INOX", "DSS9055 INOX", brand="Dawlance"
    )
    assert is_strict_model_match(
        "Dawlance Refrigerator DSS-9055 Stainless Steel", "DSS9055 INOX", brand="Dawlance"
    )

    # 3. Other refrigerator catalog pairs
    assert not is_strict_model_match(
        "Dawlance 7950 INOX Refrigerator", "7950 GD", brand="Dawlance"
    )
    assert not is_strict_model_match(
        "Dawlance 7950 GD Refrigerator", "7950 INOX", brand="Dawlance"
    )
    assert not is_strict_model_match(
        "Dawlance DW7650 INOX Refrigerator", "DW7650 GD IOT", brand="Dawlance"
    )
    assert not is_strict_model_match(
        "Dawlance 9060 INVERTER INOX", "9060 INVERTER GD", brand="Dawlance"
    )
    assert not is_strict_model_match(
        "Dawlance DMD 7951 INV INOX", "DMD 7951 INV GD", brand="Dawlance"
    )


def test_inox_sku_tag_extraction_and_search_patterns() -> None:
    _, model_inox = extract_search_query_and_model("Dawlance DSS9055 INOX", brand="Dawlance")
    assert model_inox == "DSS9055 INOX"

    patterns = generate_search_patterns("Dawlance DSS9055 INOX", brand="Dawlance")
    assert any("DSS9055 INOX" in p for p in patterns["tier_1"])
    assert any("Dawlance DSS9055 INOX" in p for p in patterns["tier_1"])


def test_referee_match_gd_inox_collision() -> None:
    decision1 = referee_match("DSS-9055 GD", "Dawlance DSS-9055 INOX Refrigerator", brand="Dawlance")
    assert not decision1.is_match
    assert "Hardware finish collision" in decision1.reason

    decision2 = referee_match("DSS9055 INOX", "Dawlance DSS-9055 GD Refrigerator", brand="Dawlance")
    assert not decision2.is_match
    assert "Hardware finish collision" in decision2.reason


def test_numeric_stem_color_variant_extraction() -> None:
    """Verify that pure numeric model stems preserve color variant descriptors."""
    q_w, m_w = extract_search_query_and_model("9101 white", brand="Dawlance")
    assert q_w == "9101"
    assert m_w == "9101 white"

    q_s, m_s = extract_search_query_and_model("9101 silver", brand="Dawlance")
    assert q_s == "9101"
    assert m_s == "9101 silver"

    q_6w, m_6w = extract_search_query_and_model("9106 white", brand="Dawlance")
    assert q_6w == "9106"
    assert m_6w == "9106 white"

    q_6s, m_6s = extract_search_query_and_model("9106 Silver", brand="Dawlance")
    assert q_6s == "9106"
    assert m_6s == "9106 Silver"


def test_strict_model_match_color_isolation_refrigerator() -> None:
    """Verify that 9101 white strictly rejects opposing colors while matching uncolored and matching color listings."""
    ezze_listing = "Dawlance Single Door Refrigerator 4 Cubic 9101 SD Silver And Black"
    white_listing = "Dawlance 9101 White Single Door Refrigerator"
    digimall_no_color = "Dawlance Bedroom Series Refrigerator 4 Cu Ft (9101)"
    digimall_sd_no_color = "Dawlance Refrigerator 9101 SD"

    # 1. Target is 9101 white: must strictly reject Silver And Black (opposing color)
    assert not is_strict_model_match(ezze_listing, "9101 white", brand="Dawlance")
    # 2. Target is 9101 white: must match pure White listing
    assert is_strict_model_match(white_listing, "9101 white", brand="Dawlance")
    # 3. Target is 9101 white: must match generic listings without color
    assert is_strict_model_match(digimall_no_color, "9101 white", brand="Dawlance")
    assert is_strict_model_match(digimall_sd_no_color, "9101 white", brand="Dawlance")

    # 4. Target is 9101 silver: must match Silver And Black listing
    assert is_strict_model_match(ezze_listing, "9101 silver", brand="Dawlance")
    # 5. Target is 9101 silver: must match generic listings without color
    assert is_strict_model_match(digimall_no_color, "9101 silver", brand="Dawlance")
    assert is_strict_model_match(digimall_sd_no_color, "9101 silver", brand="Dawlance")
    # 6. Target is 9101 silver: must strictly reject White listing (opposing color)
    assert not is_strict_model_match(white_listing, "9101 silver", brand="Dawlance")


def test_search_patterns_numeric_stem_color() -> None:
    """Verify that search patterns for numeric stem color variants query exact variant first."""
    patterns = generate_search_patterns("9101 white", brand="Dawlance")
    assert "Dawlance 9101 white" in patterns["tier_1"]
    assert "Dawlance 9101" in patterns["tier_1"]
````

## File: pricing_engine/scraper.py
````python
import asyncio
import logging
import random
import sys
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession
from rich.console import Console

from pricing_engine.matcher import is_strict_model_match, referee_match
from pricing_engine.models import ScrapedOffer, ScrapeResult

# Configure UTF-8 encoding safely for Windows CLI terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logger = logging.getLogger(__name__)
console = Console(legacy_windows=False)


def _safe_console_print(msg: str) -> None:
    """Print message to console, gracefully falling back to ascii on encoding error."""
    try:
        console.print(msg)
    except UnicodeEncodeError:
        try:
            safe_msg = msg.encode("ascii", "replace").decode("ascii")
            console.print(safe_msg)
        except Exception:
            pass
    except Exception:
        pass


ALFA_SEARCH_URL = "https://be.alfamall.com/storefront/search_products"
DIGI_SEARCH_URL = "https://digimall-be.faysalbank.com/storefront/search_products"

COMMON_HEADERS: dict[str, str] = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate, br, zstd",
    "content-type": "application/json",
    "sec-ch-ua": '"Google Chrome";v="120", "Chromium";v="120", "Not?A_Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """Configuration descriptor for a specific storefront search API."""

    platform_name: str
    display_name: str
    search_url: str
    base_params: dict[str, str]
    headers: dict[str, str]


ALFAMALL_CONFIG = PlatformConfig(
    platform_name="alfamall",
    display_name="AlfaMall",
    search_url=ALFA_SEARCH_URL,
    base_params={
        "page": "1",
        "limit": "100",
        "storefront": "23",
        "storefront_domain": "alfamall.com",
    },
    headers={
        **COMMON_HEADERS,
        "origin": "https://alfamall.com",
        "referer": "https://alfamall.com/",
    },
)

DIGIMALL_CONFIG = PlatformConfig(
    platform_name="digimall",
    display_name="DigiMall",
    search_url=DIGI_SEARCH_URL,
    base_params={
        "storefront": "23",
        "page": "1",
        "limit": "100",
    },
    headers={
        **COMMON_HEADERS,
        "origin": "https://digimall.faysalbank.com",
        "referer": "https://digimall.faysalbank.com/",
    },
)

# Run-scoped on-demand cache: (platform, query) -> ScrapeResult
_query_cache: dict[tuple[str, str], ScrapeResult] = {}
_raw_items_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}


def clear_scraper_cache() -> None:
    """Clear all in-memory query search cache entries."""
    _query_cache.clear()
    _raw_items_cache.clear()


def get_scraper_cache() -> dict[tuple[str, str], ScrapeResult]:
    """Return a read-only copy of current query cache."""
    return dict(_query_cache)


def deduplicate_offers(offers: list[ScrapedOffer]) -> list[ScrapedOffer]:
    """Deduplicate offers by (vendor_name.lower().strip(), round(price, 2)), tracking duplicate counts."""
    counts: dict[tuple[str, float], int] = {}
    first_seen: dict[tuple[str, float], ScrapedOffer] = {}
    for off in offers:
        key = (off.vendor_name.lower().strip(), round(off.price, 2))
        counts[key] = counts.get(key, 0) + (off.duplicate_count or 1)
        if key not in first_seen:
            first_seen[key] = off

    unique_offers: list[ScrapedOffer] = []
    for key, off in first_seen.items():
        total_dupes = counts[key]
        if total_dupes > 1:
            unique_offers.append(
                ScrapedOffer(
                    vendor_name=off.vendor_name,
                    price=off.price,
                    is_sold_out=off.is_sold_out,
                    raw_title=off.raw_title,
                    duplicate_count=total_dupes,
                )
            )
        else:
            unique_offers.append(off)
    return unique_offers


async def _execute_waterfall(
    single_scraper_fn: Callable[..., Coroutine[Any, Any, ScrapeResult]],
    session: AsyncSession,
    patterns: dict[str, list[str]],
    target_model: str,
    timeout: float,
    max_retries: int,
    floor_price: float | None = None,
    brand: str = "",
) -> ScrapeResult:
    """Execute tiered early-exit waterfall candidate retrieval across query tiers.

    Tiers are queried in sequence: tier_1 -> tier_2 -> tier_3.
    Exact matches take priority. If no exact matches exist and target had an
    auxiliary modifier, falls back safely to base model offers with metadata.
    """
    collected_offers: list[ScrapedOffer] = []
    collected_base_offers: list[ScrapedOffer] = []
    seen_offers: set[tuple[str, float]] = set()
    seen_base_offers: set[tuple[str, float]] = set()
    detected_missing_modifier: str | None = None
    any_success = False
    last_status: int | None = None
    last_error: str | None = None
    executed_queries: list[str] = []
    tier_summary: dict[str, int] = {}
    matched_tier: str | None = None

    tier_order = ["tier_1", "tier_2", "tier_3"]
    all_tiers = [t for t in tier_order if t in patterns] + [
        t for t in patterns if t not in tier_order
    ]

    for tier_name in all_tiers:
        tier_queries = patterns[tier_name]
        tier_offers_count = 0
        for q in tier_queries:
            q_str = str(q).strip()
            if not q_str:
                continue
            if q_str not in executed_queries:
                executed_queries.append(q_str)
            sub_res = await single_scraper_fn(
                session=session,
                query=q_str,
                target_model=target_model,
                timeout=timeout,
                max_retries=max_retries,
                floor_price=floor_price,
                brand=brand,
            )
            if sub_res.is_success:
                any_success = True
            last_status = sub_res.status_code
            if sub_res.error_detail:
                last_error = sub_res.error_detail

            for off in sub_res.offers:
                dedupe_key = (off.vendor_name.lower().strip(), round(off.price, 2))
                if dedupe_key not in seen_offers:
                    seen_offers.add(dedupe_key)
                    collected_offers.append(off)
                    tier_offers_count += 1

            for off in sub_res.base_offers:
                dedupe_key = (off.vendor_name.lower().strip(), round(off.price, 2))
                if dedupe_key not in seen_base_offers:
                    seen_base_offers.add(dedupe_key)
                    collected_base_offers.append(off)

            if sub_res.active_modifier_fallback and not detected_missing_modifier:
                detected_missing_modifier = sub_res.active_modifier_fallback

        tier_summary[tier_name] = tier_offers_count
        if tier_offers_count > 0 and matched_tier is None:
            matched_tier = tier_name

    # Priority 1: Exact matches always take precedence if any exist in market
    if collected_offers:
        final_offers = collected_offers
        active_fallback = None
    elif collected_base_offers:
        # Priority 2: When zero exact matches exist and target had an auxiliary modifier, fallback to base model
        final_offers = collected_base_offers
        active_fallback = detected_missing_modifier or "Base Model"
    else:
        final_offers = []
        active_fallback = None

    return ScrapeResult(
        offers=final_offers,
        active_modifier_fallback=active_fallback,
        base_offers=collected_base_offers,
        is_success=any_success if (any_success or not final_offers) else True,
        status_code=last_status if last_status is not None else (200 if any_success else None),
        error_detail=None if any_success else last_error,
        executed_queries=executed_queries,
        matched_tier=matched_tier,
        tier_summary=tier_summary,
    )


def _parse_offers_from_raw_items(
    raw_items: list[dict[str, Any]], target_model: str, brand: str = ""
) -> tuple[list[ScrapedOffer], list[ScrapedOffer], str | None]:
    """Extract and validate offers from raw API items array, segregating exact from base matches."""
    exact_offers: list[ScrapedOffer] = []
    base_offers: list[ScrapedOffer] = []
    detected_modifier: str | None = None

    for item in raw_items:
        title = str(item.get("title", ""))
        decision = referee_match(target_model, title, brand=brand)
        is_exact = decision.is_match
        is_base = decision.is_base_match

        if not is_exact and not is_base:
            if is_strict_model_match(title, target_model, brand=brand):
                is_exact = True
            else:
                continue

        sold_out = bool(item.get("sold_out", False))
        variant = item.get("variant_detail", {})
        price_str = variant.get("discounted_price") or variant.get("original_price") or "0"
        try:
            price = float(str(price_str).replace(",", "").strip())
        except ValueError:
            continue

        vendor_obj = item.get("vendor") or {}
        vendor = vendor_obj.get("name") or "Unknown Vendor"

        if price > 0:
            offer = ScrapedOffer(
                vendor_name=str(vendor),
                price=price,
                is_sold_out=sold_out,
                raw_title=title,
            )
            if is_exact:
                exact_offers.append(offer)
            elif is_base:
                base_offers.append(offer)
                if decision.missing_modifier and not detected_modifier:
                    detected_modifier = decision.missing_modifier

    return exact_offers, base_offers, detected_modifier


async def _scrape_platform_single_query(
    config: PlatformConfig,
    session: AsyncSession,
    query: str,
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
) -> ScrapeResult:
    """Generic single-query scraper for e-commerce storefront search APIs.

    Features:
    - On-demand in-memory caching with strict poisoning guard (only 200 OK + non-empty offers).
    - Modern Chrome 120 headers.
    - Soft 200 OK WAF challenge detection & schema validation for both 'results' and 'data' keys.
    - Fast timeout with jittered exponential backoff.
    - Live terminal telemetry badges on retries/stalls.
    - Conditional sub-floor page 2 probing.
    """
    cache_key = (config.platform_name, query.strip().upper())
    if cache_key in _raw_items_cache:
        raw_cached = _raw_items_cache[cache_key]
        e_cached, b_cached, d_cached = _parse_offers_from_raw_items(raw_cached, target_model, brand=brand)
        e_cached = deduplicate_offers(e_cached)
        b_cached = deduplicate_offers(b_cached)
        return ScrapeResult(
            offers=e_cached,
            base_offers=b_cached,
            active_modifier_fallback=d_cached,
            is_success=True,
            status_code=200,
            error_detail=None,
        )
    if cache_key in _query_cache:
        cached = _query_cache[cache_key]
        return ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name=o.vendor_name,
                    price=o.price,
                    is_sold_out=o.is_sold_out,
                    raw_title=o.raw_title,
                    duplicate_count=o.duplicate_count,
                )
                for o in cached.offers
            ],
            base_offers=[
                ScrapedOffer(
                    vendor_name=o.vendor_name,
                    price=o.price,
                    is_sold_out=o.is_sold_out,
                    raw_title=o.raw_title,
                    duplicate_count=o.duplicate_count,
                )
                for o in cached.base_offers
            ],
            active_modifier_fallback=cached.active_modifier_fallback,
            is_success=cached.is_success,
            status_code=cached.status_code,
            error_detail=cached.error_detail,
        )

    params = {**config.base_params, "q": query}
    headers = config.headers

    exact_offers: list[ScrapedOffer] = []
    base_offers: list[ScrapedOffer] = []
    detected_modifier: str | None = None
    last_status: int | None = None
    last_error: str | None = None

    for attempt in range(max_retries):
        try:
            resp = await session.get(
                config.search_url, params=params, headers=headers, timeout=timeout
            )
            last_status = resp.status_code

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception as exc:
                    last_error = f"Invalid JSON / WAF challenge: {exc}"
                    logger.warning(
                        "%s returned non-JSON body on 200 OK for query '%s'",
                        config.display_name,
                        query,
                    )
                    continue

                if not isinstance(data, dict):
                    last_error = "Invalid response schema (expected JSON object)"
                    continue

                # Support both 'results' and 'data' keys
                raw_items = data.get("results")
                if raw_items is None:
                    raw_items = data.get("data")

                if not isinstance(raw_items, list):
                    last_error = "Missing results/data array in payload"
                    continue

                e_items, b_items, d_mod = _parse_offers_from_raw_items(
                    raw_items, target_model, brand=brand
                )
                exact_offers.extend(e_items)
                base_offers.extend(b_items)
                if d_mod and not detected_modifier:
                    detected_modifier = d_mod

                # Conditional page 2 probe if all page 1 offers are sub-floor
                total_count = data.get("count") or data.get("total")
                active_probe_offers = exact_offers or base_offers
                if (
                    floor_price is not None
                    and isinstance(total_count, int)
                    and total_count > len(raw_items)
                    and active_probe_offers
                    and all(o.price <= floor_price for o in active_probe_offers)
                ):
                    params_p2 = {**params, "page": "2"}
                    try:
                        resp_p2 = await session.get(
                            config.search_url, params=params_p2, headers=headers, timeout=timeout
                        )
                        if resp_p2.status_code == 200:
                            data_p2 = resp_p2.json() if hasattr(resp_p2, "json") else {}
                            raw_p2 = data_p2.get("results") or data_p2.get("data") or []
                            if isinstance(raw_p2, list):
                                e_p2, b_p2, d_p2 = _parse_offers_from_raw_items(
                                    raw_p2, target_model, brand=brand
                                )
                                exact_offers.extend(e_p2)
                                base_offers.extend(b_p2)
                                if d_p2 and not detected_modifier:
                                    detected_modifier = d_p2
                    except Exception as exc_p2:
                        logger.debug("%s page 2 probe exception: %s", config.display_name, exc_p2)

                exact_offers = deduplicate_offers(exact_offers)
                base_offers = deduplicate_offers(base_offers)

                # Strict Cache Guard: Only cache when response is valid and offers exist
                result = ScrapeResult(
                    offers=exact_offers,
                    base_offers=base_offers,
                    active_modifier_fallback=detected_modifier,
                    is_success=True,
                    status_code=200,
                    error_detail=None,
                )
                if exact_offers or base_offers:
                    _query_cache[cache_key] = result
                    if raw_items:
                        _raw_items_cache[cache_key] = list(raw_items)

                return result

            elif resp.status_code in (429, 500, 502, 503, 504):
                last_error = f"HTTP {resp.status_code} Server/Gateway Error"
                backoff = (0.6 * (2**attempt)) + random.uniform(0.1, 0.3)
                if resp.status_code == 429:
                    console.print(
                        f"  [bold red]⛔ [{config.display_name}][/] [dim]{query}[/] "
                        f"WAF Rate-limit (429) hit (Attempt {attempt + 1}/{max_retries}) — Cooling down {backoff:.1f}s..."
                    )
                else:
                    console.print(
                        f"  [bold yellow]⚠️  [{config.display_name}][/] [dim]{query}[/] "
                        f"Server error {resp.status_code} (Attempt {attempt + 1}/{max_retries}) — Retrying in {backoff:.1f}s..."
                    )
                await asyncio.sleep(backoff)
            else:
                last_error = f"HTTP {resp.status_code} Unexpected Status"
                logger.warning(
                    "%s search API returned status %s for query %s",
                    config.display_name,
                    resp.status_code,
                    query,
                )
                break
        except Exception as exc:
            last_error = str(exc) or "Network Connection/Timeout Error"
            err_str = str(exc).lower()
            is_socket_drop = any(
                k in err_str for k in ("wsarecv", "connection was aborted", "reset", "closed")
            )
            is_timeout = any(k in err_str for k in ("28", "timed out", "timeout"))

            if is_timeout:
                backoff = random.uniform(3.5, 5.0) + (attempt * 1.5)
                _safe_console_print(
                    f"  [bold yellow][!] [{config.display_name}][/] [dim]{query}[/] "
                    f"Connection timeout (Attempt {attempt + 1}/{max_retries}) - Backoff cool-down in {backoff:.1f}s..."
                )
            elif is_socket_drop:
                backoff = (0.8 * (2**attempt)) + random.uniform(0.2, 0.5)
                _safe_console_print(
                    f"  [bold yellow][!] [{config.display_name}][/] [dim]{query}[/] "
                    f"Socket drop/aborted (Attempt {attempt + 1}/{max_retries}) - Auto-recovering in {backoff:.1f}s..."
                )
            else:
                backoff = (0.5 * (2**attempt)) + random.uniform(0.1, 0.4)
                _safe_console_print(
                    f"  [bold yellow][!] [{config.display_name}][/] [dim]{query}[/] "
                    f"Network error (Attempt {attempt + 1}/{max_retries}) - Retrying in {backoff:.1f}s..."
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    "%s failed after %d attempts for query '%s': %s",
                    config.display_name,
                    max_retries,
                    query,
                    exc,
                )

    return ScrapeResult(
        offers=[],
        is_success=False,
        status_code=last_status,
        error_detail=last_error or "Exhausted all retries without successful response",
    )


async def _scrape_alfamall_single_query(
    session: AsyncSession,
    query: str,
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
) -> ScrapeResult:
    """Internal single-query scraper for AlfaMall storefront search API."""
    return await _scrape_platform_single_query(
        config=ALFAMALL_CONFIG,
        session=session,
        query=query,
        target_model=target_model,
        timeout=timeout,
        max_retries=max_retries,
        floor_price=floor_price,
        brand=brand,
    )


async def scrape_alfamall(
    session: AsyncSession,
    query: str | dict[str, list[str]],
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
) -> ScrapeResult:
    """Query AlfaMall storefront search API and extract verified product offers with retries.

    Supports both single search query strings and tiered waterfall pattern dictionaries.

    Args:
        session: Active curl_cffi AsyncSession with Chrome impersonation.
        query: Search keyword string or tiered patterns dictionary.
        target_model: Target model string for strict variant validation.
        timeout: HTTP request timeout in seconds (default: 10.0s).
        max_retries: Number of retry attempts on network/timeout failure (default: 3).
        floor_price: Optional price floor to probe page 2 if all page 1 items are sub-floor.
        brand: Optional brand name for strict matching.

    Returns:
        ScrapeResult containing verified offers and explicit success/failure flags.
    """
    if isinstance(query, str):
        return await _scrape_alfamall_single_query(
            session=session,
            query=query,
            target_model=target_model,
            timeout=timeout,
            max_retries=max_retries,
            floor_price=floor_price,
            brand=brand,
        )
    return await _execute_waterfall(
        single_scraper_fn=_scrape_alfamall_single_query,
        session=session,
        patterns=query,
        target_model=target_model,
        timeout=timeout,
        max_retries=max_retries,
        floor_price=floor_price,
        brand=brand,
    )


async def _scrape_digimall_single_query(
    session: AsyncSession,
    query: str,
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
) -> ScrapeResult:
    """Internal single-query scraper for DigiMall storefront search API."""
    return await _scrape_platform_single_query(
        config=DIGIMALL_CONFIG,
        session=session,
        query=query,
        target_model=target_model,
        timeout=timeout,
        max_retries=max_retries,
        floor_price=floor_price,
        brand=brand,
    )


async def scrape_digimall(
    session: AsyncSession,
    query: str | dict[str, list[str]],
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    floor_price: float | None = None,
    brand: str = "",
) -> ScrapeResult:
    """Query DigiMall (Faysal Bank) storefront search API and extract verified product offers.

    Supports both single search query strings and tiered waterfall pattern dictionaries.

    Args:
        session: Active curl_cffi AsyncSession with Chrome impersonation.
        query: Search keyword string or tiered patterns dictionary.
        target_model: Target model string for strict variant validation.
        timeout: HTTP request timeout in seconds (default: 10.0s).
        max_retries: Number of retry attempts on network/timeout failure (default: 3).
        floor_price: Optional price floor for conditional sub-floor page 2 probing.
        brand: Optional brand name for strict matching.

    Returns:
        ScrapeResult containing verified offers and explicit success/failure flags.
    """
    if isinstance(query, str):
        return await _scrape_digimall_single_query(
            session=session,
            query=query,
            target_model=target_model,
            timeout=timeout,
            max_retries=max_retries,
            floor_price=floor_price,
            brand=brand,
        )
    return await _execute_waterfall(
        single_scraper_fn=_scrape_digimall_single_query,
        session=session,
        patterns=query,
        target_model=target_model,
        timeout=timeout,
        max_retries=max_retries,
        floor_price=floor_price,
        brand=brand,
    )
````

## File: tests/test_pipeline.py
````python
import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from pricing_engine.matcher import extract_search_query_and_model, is_strict_model_match
from pricing_engine.models import ScrapedOffer, ScrapeResult
from pricing_engine.pipeline import (
    determine_risk_alert,
    format_export_price,
    parse_product_input,
    process_product_with_offers,
    run_pipeline,
)


def test_parse_product_input_clean() -> None:
    row = pd.Series(
        {
            "S.NO": 1,
            "Brand": "Gree",
            "Name ": "Gree Inverter AC 1.5 Ton GS-18PITH11W",
            "Length": 100,
            "Width": 35,
            "Height": 45,
            "Net Price": "150,000",
            "Profit": "5,000",
        }
    )
    product = parse_product_input(0, row)
    assert product.sno == 1
    assert product.brand == "Gree"
    assert product.name == "Gree Inverter AC 1.5 Ton GS-18PITH11W"
    assert product.length == 100.0
    assert product.width == 35.0
    assert product.height == 45.0
    assert product.net_price == 150000.0
    assert product.profit == 5000.0


def test_parse_product_input_missing_defaults() -> None:
    row = pd.Series(
        {
            "Brand": "Gree",
            "Name": "Generic AC",
            "Net Price": 70000,
        }
    )
    product = parse_product_input(2, row)
    assert product.sno == 3  # idx + 1
    assert product.length == 0.0
    assert product.profit == 500.0


def test_process_product_with_offers_monopoly() -> None:
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "Gree Fairy 12AITH21W",
                "Length": 90,
                "Width": 30,
                "Height": 30,
                "Net Price": 80000,
                "Profit": 3000,
            }
        ),
    )
    # Zero offers from both platforms
    alfa_offers: list[ScrapedOffer] = []
    digi_offers: list[ScrapedOffer] = []

    record = process_product_with_offers(product, alfa_offers, digi_offers)

    assert record["Final Price Alfa"] is not None
    assert record["Final Price Digi"] is not None
    assert record["Commision"] == "10.00%"
    assert record["Digi Effective Commision"] == "10.00%"
    assert "Monopoly" in record["Alfa Reason"]
    assert record["Alfa Real Profit"] >= 4000
    assert record["Digi Real Profit"] >= 4000


def test_build_output_record_contains_all_schema_columns() -> None:
    product = parse_product_input(
        0,
        pd.Series({"S.NO": 1, "Brand": "Gree", "Name ": "AC", "Net Price": 50000}),
    )
    record = process_product_with_offers(product, [], [])

    expected_cols = [
        "Shipping Estimate",
        "Commision",
        "Digi Effective Commision",
        "Total Without Profit",
        "Calculation",
        "Minimum Price Alfa",
        "Maximum Price Alfa",
        "Minimum Price Digi",
        "Maximum Price Digi",
        "Final Price Alfa",
        "Final Price Digi",
        "Alfa Real Profit",
        "Digi Real Profit",
        "Alfa Reason",
        "Digi Reason",
    ]
    for col in expected_cols:
        assert col in record


def test_total_without_profit_matches_digi_effective_commission() -> None:
    # Net Price = 415,000, Shipping = 15,291 -> Cost Base = 430,291
    # 8% breakeven: 430,291 / 0.92 = 467,707.6 -> 467,708
    # 10% breakeven: 430,291 / 0.90 = 478,101.1 -> 478,101
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "GREE FLOOR STANDING 36TFIH AA+",
                "Shipping Estimate": 15291,
                "Net Price": "415,000",
            }
        ),
    )
    # Competitor triggers 8% switch (e.g. at 475,000 which is between 8% floor 468,251 and 10% floor 478,657)
    digi_offer_8 = [
        ScrapedOffer(vendor_name="DigiSeller", price=475000.0, is_sold_out=False, raw_title="AC")
    ]
    record_8 = process_product_with_offers(product, [], digi_offer_8)

    assert record_8["Digi Effective Commision"] == "8.00%"
    assert record_8["Total Without Profit"] == 467708

    # When competitor on a standard product is above 10% floor and within profit cap -> 10% default tier
    prod_standard = parse_product_input(
        1,
        pd.Series(
            {
                "S.NO": 2,
                "Brand": "Gree",
                "Name ": "GREE SPLIT AC 18AITH21W",
                "Shipping Estimate": 5000,
                "Net Price": "140,000",
            }
        ),
    )
    # Cost base = 145,000, 10% floor = 161,667. Competitor at 165,000 is viable at 10% tier
    digi_offer_10 = [
        ScrapedOffer(
            vendor_name="DigiSellerHigh", price=165000.0, is_sold_out=False, raw_title="AC"
        )
    ]
    record_10 = process_product_with_offers(prod_standard, [], digi_offer_10)

    assert record_10["Digi Effective Commision"] == "10.00%"
    assert record_10["Total Without Profit"] == 161111


def test_exact_real_profit_formula_matches_user_bank_payout() -> None:
    # Net Price = 415,000, Shipping = 15,291 -> Cost Base = 430,291
    # If Alfa price is 479,299 at 10%:
    # Profit = (479,299 * 0.90) - 430,291 = 431,369.1 - 430,291 = 1,078
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "FS 36TFIH",
                "Shipping Estimate": 15291,
                "Net Price": 415000,
            }
        ),
    )
    alfa_offers = [
        ScrapedOffer(vendor_name="Nasim", price=479499.0, is_sold_out=False, raw_title="AC")
    ]
    digi_offers = [
        ScrapedOffer(vendor_name="Scroll", price=489999.0, is_sold_out=False, raw_title="AC")
    ]

    record = process_product_with_offers(product, alfa_offers, digi_offers)

    # Alfa undercut Nasim (479,499) to 479,299 -> Profit = 1,078
    assert record["Final Price Alfa"] == 479299
    assert record["Alfa Real Profit"] == 1078

    # Digi caps inflated Scroll (489,999) at Default 10% Tier sweet-spot (~Rs. 10,000 profit):
    # Selling price 478,999 -> Profit = (478,999 * 0.92) - 430,291 = 10,388
    assert record["Final Price Digi"] == 478999
    assert record["Digi Real Profit"] == 10388
    assert record["Digi Effective Commision"] == "10.00%"


def test_ui_rendering_functions_execute_cleanly(tmp_path: Path) -> None:
    from pricing_engine.calculator import calculate_cost_base, calculate_floors
    from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
    from pricing_engine.pipeline import (
        render_audit_card,
        render_finish_banner,
        render_start_banner,
        render_summary_table,
    )

    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "FS 36TFIH AA+",
                "Shipping Estimate": 15291,
                "Net Price": 415000,
                "Length": 127,
                "Width": 43,
                "Height": 200,
            }
        ),
    )
    floors = calculate_floors(calculate_cost_base(product.net_price, 15291))
    alfa_res = evaluate_alfa_pricing(floors, [])
    digi_res = evaluate_digi_pricing(floors, [])

    # Test audit card rendering without raising exceptions
    render_audit_card(
        product=product,
        shipping=15291.0,
        floors=floors,
        baseline_calc=482999.0,
        target_model="GS-36TFIH",
        alfa_offers=[],
        digi_offers=[],
        alfa_res=alfa_res,
        digi_res=digi_res,
    )

    # Test start and finish banners
    in_p = Path("tests/fixtures/Gree_Uploading_on_DigiMall_and_Price.csv")
    out_p = Path("data/outputs/Gree_AC_repriced_latest.csv")
    render_start_banner(in_p, out_p, 25, 3)
    render_finish_banner(out_p, 25, 5.23)

    # Test summary table with mixed (active + skip) rows
    records = [
        {
            "S.NO": 1,
            "Name ": "GREE FLOOR STANDING 36TFIH",
            "Net Price": 415000,
            "Shipping Estimate": 15291,
            "Final Price Alfa": 482999,
            "Alfa Real Profit": 4408,
            "Final Price Digi": 482999,
            "Digi Effective Commision": "10.00%",
            "Digi Real Profit": 14068,
        },
        {
            "S.NO": 2,
            "Name ": "GREE SPLIT AC 18AITH21W-T3",
            "Net Price": 140000,
            "Shipping Estimate": 5292,
            "Final Price Alfa": None,
            "Alfa Real Profit": 0,
            "Final Price Digi": 168499,
            "Digi Effective Commision": "8.00%",
            "Digi Real Profit": 9727,
        },
    ]
    render_summary_table(records)


def test_pipeline_csv_index_preservation_when_completion_is_unordered(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"

    # Create dummy 3-item CSV
    df = pd.DataFrame(
        [
            {"S.NO": 1, "Brand": "Gree", "Name ": "Product A", "Net Price": 50000},
            {"S.NO": 2, "Brand": "Gree", "Name ": "Product B", "Net Price": 60000},
            {"S.NO": 3, "Brand": "Gree", "Name ": "Product C", "Net Price": 70000},
        ]
    )
    df.to_csv(input_csv, index=False)

    # Mock process_item_async to simulate reverse or scrambled completion times
    delays = {1: 0.2, 2: 0.05, 3: 0.1}

    async def mock_process(
        product: Any,
        session: Any,
        semaphore: Any,
        render_lock: Any = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        await asyncio.sleep(delays.get(product.sno, 0.01))
        return {
            "S.NO": product.sno,
            "Final Price Alfa": 55000,
            "Final Price Digi": 55000,
        }

    with patch("pricing_engine.pipeline.process_item_async", side_effect=mock_process):
        asyncio.run(
            run_pipeline(input_path=input_csv, output_path=output_csv, concurrency=3, verbose=False)
        )

    out_df = pd.read_csv(output_csv)
    # Original sequence S.NO: 1, 2, 3 must be strictly preserved!
    assert list(out_df["S.NO"]) == [1, 2, 3]
    # Temporary sorting key must be removed
    assert "_original_idx" not in out_df.columns


def test_process_product_with_offers_server_down_isolation() -> None:
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "Gree Split AC 12AITH21W",
                "Length": 90,
                "Width": 30,
                "Height": 30,
                "Net Price": 80000,
                "Profit": 3000,
            }
        ),
    )
    # Alfa is down (500), Digi is live with 0 offers (Monopoly)
    alfa_down = ScrapeResult(
        offers=[], is_success=False, status_code=500, error_detail="HTTP 500: Server Error"
    )
    digi_ok = ScrapeResult(offers=[], is_success=True, status_code=200)

    record = process_product_with_offers(product, alfa_down, digi_ok)

    # AlfaMall must be Server Down (SKIP / NaN, real profit 0)
    assert record["Final Price Alfa"] is None
    assert record["Alfa Real Profit"] == 0
    assert "unreachable" in record["Alfa Reason"].lower()
    assert "server is down" in record["Alfa Reason"].lower()

    # DigiMall must be unaffected and win legitimate Monopoly
    assert record["Final Price Digi"] is not None
    assert record["Digi Real Profit"] >= 4000
    assert "Monopoly" in record["Digi Reason"]


def test_process_product_with_offers_both_servers_down() -> None:
    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "Gree Split AC 12AITH21W",
                "Length": 90,
                "Width": 30,
                "Height": 30,
                "Net Price": 80000,
                "Profit": 3000,
            }
        ),
    )
    alfa_down = ScrapeResult(
        offers=[], is_success=False, status_code=502, error_detail="Bad Gateway"
    )
    digi_down = ScrapeResult(
        offers=[], is_success=False, status_code=504, error_detail="Gateway Timeout"
    )

    record = process_product_with_offers(product, alfa_down, digi_down)

    assert record["Final Price Alfa"] is None
    assert record["Final Price Digi"] is None
    assert record["Alfa Real Profit"] == 0
    assert record["Digi Real Profit"] == 0
    assert "unreachable" in record["Alfa Reason"].lower()
    assert "server is down" in record["Alfa Reason"].lower()
    assert "unreachable" in record["Digi Reason"].lower()
    assert "server is down" in record["Digi Reason"].lower()


def test_format_export_price_integers_and_nulls() -> None:
    assert format_export_price(None) == ""
    assert format_export_price(float("nan")) == ""
    assert format_export_price("nan") == ""
    assert format_export_price("NaN") == ""
    assert format_export_price("") == ""
    assert format_export_price(165000) == "165000"
    assert format_export_price(165000.0) == "165000"
    assert format_export_price("165,000") == "165000"
    assert format_export_price("165000.0") == "165000"
    assert format_export_price("invalid") == ""


def test_pipeline_csv_export_pure_integers_without_float_drift(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"

    # Row 1 will have price, Row 2 will have None (Server Down simulation)
    df = pd.DataFrame(
        [
            {"S.NO": 1, "Brand": "Gree", "Name ": "Product A", "Net Price": 50000},
            {"S.NO": 2, "Brand": "Gree", "Name ": "Product B", "Net Price": 60000},
        ]
    )
    df.to_csv(input_csv, index=False)

    async def mock_process(
        product: Any,
        session: Any,
        semaphore: Any,
        render_lock: Any = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        if product.sno == 1:
            return {
                "S.NO": product.sno,
                "Final Price Alfa": 55000,
                "Final Price Digi": 56000,
                "Total Without Profit": 52000,
                "Calculation": 55000,
                "Minimum Price Alfa": 53000,
                "Maximum Price Alfa": 58000,
                "Minimum Price Digi": 54000,
                "Maximum Price Digi": 59000,
                "Alfa Real Profit": 2000,
                "Digi Real Profit": 3000,
                "Alfa Reason": "Undercut",
                "Digi Reason": "Undercut",
            }
        else:
            return {
                "S.NO": product.sno,
                "Final Price Alfa": None,
                "Final Price Digi": None,
                "Total Without Profit": 63000,
                "Calculation": 66000,
                "Minimum Price Alfa": None,
                "Maximum Price Alfa": None,
                "Minimum Price Digi": None,
                "Maximum Price Digi": None,
                "Alfa Real Profit": 0,
                "Digi Real Profit": 0,
                "Alfa Reason": "Server Down / Unreachable (HTTP 500)",
                "Digi Reason": "Server Down / Unreachable (HTTP 500)",
            }

    with patch("pricing_engine.pipeline.process_item_async", side_effect=mock_process):
        asyncio.run(
            run_pipeline(input_path=input_csv, output_path=output_csv, concurrency=2, verbose=False)
        )

    # Read raw text lines of output CSV to inspect exact string formatting
    csv_text = output_csv.read_text(encoding="utf-8")
    lines = [line.strip() for line in csv_text.strip().splitlines()]
    header = lines[0].split(",")
    row1 = lines[1].split(",")
    row2 = lines[2].split(",")

    row1_dict = dict(zip(header, row1, strict=True))
    row2_dict = dict(zip(header, row2, strict=True))

    # Row 1 should have pure integer strings (no .0 float drift)
    assert row1_dict["Final Price Alfa"] == "55000"
    assert row1_dict["Final Price Digi"] == "56000"
    assert row1_dict["Minimum Price Alfa"] == "53000"
    assert row1_dict["Alfa Real Profit"] == "2000"

    # Row 2 should have empty string "" for None prices (not NaN or null)
    assert row2_dict["Final Price Alfa"] == ""
    assert row2_dict["Final Price Digi"] == ""
    assert row2_dict["Minimum Price Alfa"] == ""
    assert row2_dict["Alfa Real Profit"] == "0"


def test_render_audit_card_and_summary_with_server_down() -> None:
    from pricing_engine.calculator import calculate_cost_base, calculate_floors
    from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
    from pricing_engine.pipeline import render_audit_card, render_summary_table

    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "Gree Split AC 12AITH21W",
                "Shipping Estimate": 4000,
                "Net Price": 150000,
            }
        ),
    )
    floors = calculate_floors(calculate_cost_base(product.net_price, 4000))
    down_alfa = ScrapeResult(offers=[], is_success=False, status_code=500, error_detail="HTTP 500")
    down_digi = ScrapeResult(offers=[], is_success=False, status_code=502, error_detail="HTTP 502")

    alfa_res = evaluate_alfa_pricing(floors, down_alfa)
    digi_res = evaluate_digi_pricing(floors, down_digi)

    # Must execute and render without any exception
    render_audit_card(
        product=product,
        shipping=4000.0,
        floors=floors,
        baseline_calc=171111.0,
        target_model="12AITH21W",
        alfa_offers=down_alfa,
        digi_offers=down_digi,
        alfa_res=alfa_res,
        digi_res=digi_res,
    )

    records = [
        {
            "S.NO": 1,
            "Name ": "Gree Split AC 12AITH21W",
            "Net Price": 150000,
            "Shipping Estimate": 4000,
            "Final Price Alfa": None,
            "Alfa Real Profit": 0,
            "Alfa Reason": "Server Down / Unreachable (HTTP 500)",
            "Final Price Digi": None,
            "Digi Real Profit": 0,
            "Digi Reason": "Server Down / Unreachable (HTTP 502)",
            "Digi Effective Commision": "10.00%",
        }
    ]
    render_summary_table(records)


def test_determine_risk_alert_states() -> None:
    from pricing_engine.models import PlatformPricingResult

    # 1. SERVER_DOWN: status is Server Down or final_price is None or real_profit is None
    down_res = PlatformPricingResult(
        min_price=None,
        max_price=None,
        final_price=None,
        real_profit=0,
        status="Server Down / Unreachable",
        reason="Error",
    )
    assert determine_risk_alert(down_res) == "SERVER_DOWN"

    null_profit_res = PlatformPricingResult(
        min_price=None,
        max_price=None,
        final_price=None,
        real_profit=0,
        status="Some Status",
        reason="Error",
    )
    assert determine_risk_alert(null_profit_res) == "SERVER_DOWN"

    # 2. NEGATIVE_MARGIN: profit <= 0 when final_price is present
    loss_res = PlatformPricingResult(
        min_price=100000,
        max_price=120000,
        final_price=105000,
        real_profit=-500,
        status="Manual Loss",
        reason="Underpriced",
    )
    assert determine_risk_alert(loss_res) == "NEGATIVE_MARGIN"

    zero_res = PlatformPricingResult(
        min_price=100000,
        max_price=120000,
        final_price=105000,
        real_profit=0,
        status="Zero Margin",
        reason="Breakeven",
    )
    assert determine_risk_alert(zero_res) == "NEGATIVE_MARGIN"

    # 3. SAFE_FALLBACK: all competitors below floor
    fallback_res = PlatformPricingResult(
        min_price=100000,
        max_price=120000,
        final_price=110000,
        real_profit=1950,
        status="Safe Fallback",
        reason="Fallback price",
    )
    assert determine_risk_alert(fallback_res) == "SAFE_FALLBACK"

    # 4. THIN_BUFFER: 0 < profit < 700 (courier packaging re-weighing risk)
    thin_res = PlatformPricingResult(
        min_price=100000,
        max_price=120000,
        final_price=105000,
        real_profit=502,
        status="Competitive Win",
        reason="Undercut",
    )
    assert determine_risk_alert(thin_res) == "THIN_BUFFER"

    # 5. NONE: profit >= 700
    healthy_res = PlatformPricingResult(
        min_price=100000,
        max_price=120000,
        final_price=105000,
        real_profit=1078,
        status="Competitive Win",
        reason="Undercut",
    )
    assert determine_risk_alert(healthy_res) == "NONE"


def test_build_output_record_includes_risk_alerts() -> None:
    product = parse_product_input(
        0,
        pd.Series({"S.NO": 1, "Brand": "Gree", "Name ": "AC", "Net Price": 50000}),
    )
    record = process_product_with_offers(product, [], [])
    assert "Alfa Risk Alert" in record
    assert "Digi Risk Alert" in record
    valid_alerts = {"NONE", "THIN_BUFFER", "SAFE_FALLBACK", "SERVER_DOWN", "NEGATIVE_MARGIN"}
    assert record["Alfa Risk Alert"] in valid_alerts
    assert record["Digi Risk Alert"] in valid_alerts


def test_render_summary_table_risk_visuals() -> None:
    from pricing_engine.pipeline import render_summary_table

    records = [
        {
            "S.NO": 1,
            "Name ": "GREE SPLIT AC 12AITH21W-T3",
            "Net Price": 120000,
            "Shipping Estimate": 4000,
            "Final Price Alfa": 145999,
            "Alfa Real Profit": 1950,
            "Alfa Reason": "Safe Fallback: all competitors below floor",
            "Alfa Risk Alert": "SAFE_FALLBACK",
            "Final Price Digi": 143899,
            "Digi Real Profit": 578,
            "Digi Reason": "Emergency 8% switch: undercut viable seller",
            "Digi Effective Commision": "8.00%",
            "Digi Risk Alert": "THIN_BUFFER",
        },
        {
            "S.NO": 2,
            "Name ": "GREE SPLIT AC 24AITH21W",
            "Net Price": 200000,
            "Shipping Estimate": 6000,
            "Final Price Alfa": 235999,
            "Alfa Real Profit": 6500,
            "Alfa Reason": "Undercut competitor",
            "Alfa Risk Alert": "NONE",
            "Final Price Digi": 234999,
            "Digi Real Profit": 10388,
            "Digi Reason": "Capped at sweet-spot (~Rs. 10,000 profit)",
            "Digi Effective Commision": "10.00%",
            "Digi Risk Alert": "NONE",
        },
        {
            "S.NO": 3,
            "Name ": "GREE FLOOR STANDING 36TFIH",
            "Net Price": 400000,
            "Shipping Estimate": 15000,
            "Final Price Alfa": None,
            "Alfa Real Profit": 0,
            "Alfa Reason": "Server Down / Unreachable (HTTP 500)",
            "Alfa Risk Alert": "SERVER_DOWN",
            "Final Price Digi": 450000,
            "Digi Real Profit": -200,
            "Digi Reason": "Corrupt cost base margin loss",
            "Digi Effective Commision": "10.00%",
            "Digi Risk Alert": "NEGATIVE_MARGIN",
        },
        {
            "S.NO": 4,
            "Name ": "GREE SPLIT AC 18AITH24",
            "Net Price": 160000,
            "Shipping Estimate": 5000,
            "Final Price Alfa": None,
            "Alfa Real Profit": 0,
            "Alfa Reason": "Skip: all competitors unviable",
            "Alfa Risk Alert": "SERVER_DOWN",
            "Final Price Digi": None,
            "Digi Real Profit": 0,
            "Digi Reason": "Skip: all competitors unviable",
            "Digi Effective Commision": "10.00%",
            "Digi Risk Alert": "SERVER_DOWN",
        },
    ]

    # Verify rendering completes cleanly without raising any exceptions
    render_summary_table(records)


def test_pipeline_csv_export_includes_risk_alerts_without_ansi_leakage(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"

    df = pd.DataFrame(
        [
            {
                "S.NO": 1,
                "Brand": "Gree",
                "Name ": "Item 1",
                "Length": 100,
                "Width": 50,
                "Height": 40,
                "Net Price": 100000,
                "Profit": 4000,
            },
            {
                "S.NO": 2,
                "Brand": "Gree",
                "Name ": "Item 2",
                "Length": 100,
                "Width": 50,
                "Height": 40,
                "Net Price": 120000,
                "Profit": 4000,
            },
        ]
    )
    df.to_csv(input_csv, index=False)

    async def mock_process(
        product: Any,
        session: Any,
        semaphore: Any,
        render_lock: Any = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        if product.sno == 1:
            return {
                "S.NO": 1,
                "Final Price Alfa": 115999,
                "Final Price Digi": 114899,
                "Alfa Real Profit": 520,
                "Digi Real Profit": 1050,
                "Alfa Reason": "Undercut seller",
                "Digi Reason": "Undercut seller",
                "Alfa Risk Alert": "THIN_BUFFER",
                "Digi Risk Alert": "NONE",
            }
        return {
            "S.NO": 2,
            "Final Price Alfa": 140999,
            "Final Price Digi": None,
            "Alfa Real Profit": 1950,
            "Digi Real Profit": 0,
            "Alfa Reason": "Safe Fallback: all below floor",
            "Digi Reason": "Server Down / Unreachable",
            "Alfa Risk Alert": "SAFE_FALLBACK",
            "Digi Risk Alert": "SERVER_DOWN",
        }

    with patch("pricing_engine.pipeline.process_item_async", side_effect=mock_process):
        asyncio.run(
            run_pipeline(input_path=input_csv, output_path=output_csv, concurrency=2, verbose=False)
        )

    csv_text = output_csv.read_text(encoding="utf-8")
    lines = [line.strip() for line in csv_text.strip().splitlines()]
    header = lines[0].split(",")

    # Verify risk alert columns are at the end of the CSV header
    assert "Alfa Risk Alert" in header
    assert "Digi Risk Alert" in header
    assert header[-2] == "Alfa Risk Alert"
    assert header[-1] == "Digi Risk Alert"

    # Verify rows contain exact clean string values
    row1 = dict(zip(header, lines[1].split(","), strict=True))
    row2 = dict(zip(header, lines[2].split(","), strict=True))

    assert row1["Alfa Risk Alert"] == "THIN_BUFFER"
    assert row1["Digi Risk Alert"] == "NONE"
    assert row2["Alfa Risk Alert"] == "SAFE_FALLBACK"
    assert row2["Digi Risk Alert"] == "SERVER_DOWN"

    # Absolute verification: NO Rich/ANSI markup in entire CSV content
    assert "[" not in csv_text
    assert "]" not in csv_text
    assert "bold" not in csv_text
    assert "red" not in csv_text
    assert "green" not in csv_text
    assert "yellow" not in csv_text


def test_item_3_slash_expansion_digimall_reprice_win() -> None:
    """Verify Item #3 (12AITH24S-T3 Silver) matches GS-12AITH24W/S on DigiMall.

    Tests that slash variant expansion successfully extracts competitors and
    triggers an Emergency 8% Bank Switch undercutting Rs. 193,999 to Rs. 193,899,
    yielding +Rs. 2,409 healthy net profit instead of false Monopoly fallback.
    """
    product = parse_product_input(
        2,
        pd.Series(
            {
                "S.NO": 3,
                "Brand": "Gree",
                "Name ": "GREE SPLIT AC 12AITH24S-T3",
                "Length": 87,
                "Width": 35.5,
                "Height": 92,
                "Net Price": 172000,
                "Profit": 4000,
            }
        ),
    )

    digi_offers = [
        ScrapedOffer(
            vendor_name="Musab Mall",
            price=193999.0,
            is_sold_out=False,
            raw_title="GREE Airy Pro 1 TON Split AC Inverter G-Boost AI T3 GS-12AITH24W/S",
        ),
        ScrapedOffer(
            vendor_name="Tech House",
            price=193999.0,
            is_sold_out=False,
            raw_title="GREE Airy Pro 1 TON Split AC Inverter G-Boost AI T3 GS-12AITH24W/S",
        ),
        ScrapedOffer(
            vendor_name="YZ International",
            price=194099.0,
            is_sold_out=False,
            raw_title="GREE Airy Pro 1 TON Split AC Inverter G-Boost AI T3 GS-12AITH24W/S",
        ),
    ]

    record = process_product_with_offers(product, alfa_offers=[], digi_offers=digi_offers)

    # 1. Winning price undercuts Musab Mall (193,999) to 192,899 (Adaptive undercut)
    assert record["Final Price Digi"] == 192899

    # 2. Commission switched to 8.00% Emergency Tier
    assert record["Digi Effective Commision"] == "8.00%"

    # 3. Real Profit calculated: (192,899 * 0.92) - 175,978 = +1,489
    assert record["Digi Real Profit"] == 1489

    # 4. Reason documents the 8% switch undercut
    assert (
        "8% bank rate" in record["Digi Reason"].lower()
        or "emergency 8%" in record["Digi Reason"].lower()
    )

    # 5. Risk Alert is NONE (Healthy margin >= 700)
    assert record["Digi Risk Alert"] == "NONE"


def test_item_17_zith2_rejects_cheaper_zith1_competitor() -> None:
    """Verify Item #17 (GS-12ZITH2W-T3) isolates from cheaper Gen 1 (ZITH1) listings.

    Tests that when scraping market offers for 12ZITH2W, any cheaper GS-12ZITH1W
    offers (which would otherwise trigger false undercuts or false loss flags)
    are strictly rejected by the matcher, ensuring only genuine GS-12ZITH2W
    offers are repriced against.
    """
    product = parse_product_input(
        16,
        pd.Series(
            {
                "S.NO": 17,
                "Brand": "Gree",
                "Name ": "GREE SPLIT AC GS-12ZITH2W-T3",
                "Length": 87,
                "Width": 35.5,
                "Height": 92,
                "Net Price": 133147,
                "Profit": 4000,
            }
        ),
    )

    _, model_code = extract_search_query_and_model(product.name, brand=product.brand)

    raw_offers = [
        # Cheaper Gen 1 offer that must be filtered out
        ScrapedOffer(
            vendor_name="Cheap Seller Gen1",
            price=130000.0,
            is_sold_out=False,
            raw_title="Gree Zeno 1 Ton GS-12ZITH1W Inverter",
        ),
        # Real Gen 2 offer that must be retained
        ScrapedOffer(
            vendor_name="Legit Seller Gen2",
            price=153999.0,
            is_sold_out=False,
            raw_title="Gree Zeno 1 Ton GS-12ZITH2W Inverter",
        ),
    ]

    # Scraper strictly filters by model match
    filtered_offers = [o for o in raw_offers if is_strict_model_match(o.raw_title, model_code)]
    assert len(filtered_offers) == 1
    assert filtered_offers[0].vendor_name == "Legit Seller Gen2"

    record = process_product_with_offers(
        product, alfa_offers=filtered_offers, digi_offers=filtered_offers
    )

    # AlfaMall undercuts Gen 2 (153,999 -> Tier 4 adaptive undercut 153,799), completely ignoring Gen 1 (130,000)
    assert record["Final Price Alfa"] == 153799
    assert "Legit Seller Gen2" in record["Alfa Reason"]
    assert "Cheap Seller Gen1" not in record["Alfa Reason"]


def test_item_22_pular_batch_slash_digimall_reprice_win() -> None:
    """Verify Item #22 (GS-24PITH15G-T3) matches GS-24PITH15/17G on DigiMall.

    Tests that shared-color batch expansion (GS-24PITH15/17G) matches Grey 15G,
    strictly rejects White 15W, and undercuts Tech House (247,999) to win
    at 8% bank rate with healthy net profit instead of false Monopoly baseline.
    """
    product = parse_product_input(
        21,
        pd.Series(
            {
                "S.NO": 22,
                "Brand": "Gree",
                "Name ": "GREE SPLIT AC GS-24PITH15G-T3",
                "Length": 106,
                "Width": 42,
                "Height": 110,
                "Net Price": 220000,
                "Profit": 4000,
            }
        ),
    )

    _, model_code = extract_search_query_and_model(product.name, brand=product.brand)

    digi_raw = [
        ScrapedOffer(
            vendor_name="Tech House",
            price=247999.0,
            is_sold_out=False,
            raw_title="GREE Pular T3 2 TON Split AC GS-24PITH15/17G - T3",
        ),
        ScrapedOffer(
            vendor_name="YZ International",
            price=248099.0,
            is_sold_out=False,
            raw_title="GREE Pular T3 2 TON Split AC GS-24PITH15/17G - T3",
        ),
        ScrapedOffer(
            vendor_name="Wrong Color White",
            price=247999.0,
            is_sold_out=False,
            raw_title="GREE Pular T3 2 TON Split AC GS-24PITH15/17W - T3",
        ),
    ]

    filtered = [o for o in digi_raw if is_strict_model_match(o.raw_title, model_code)]
    assert len(filtered) == 2
    assert all(o.vendor_name in ("Tech House", "YZ International") for o in filtered)

    record = process_product_with_offers(product, alfa_offers=[], digi_offers=filtered)

    # 1. Final Price undercuts Tech House (247,999)
    assert record["Final Price Digi"] < 247999
    # 2. Commission switched to 8.00%
    assert record["Digi Effective Commision"] == "8.00%"
    # 3. Real Profit is healthy (+Rs. 1,119)
    assert record["Digi Real Profit"] == 1119
    # 4. Reason documents Tech House undercut and 8% bank rate
    assert "tech house" in record["Digi Reason"].lower()
    assert "8% faysal bank rate" in record["Digi Reason"].lower()
    # 5. Risk Alert is NONE
    assert record["Digi Risk Alert"] == "NONE"


def test_pipeline_autonomous_learner_buffering() -> None:
    """Validate that accepted candidate offers with residual cosmetic differences buffer observations."""
    from pricing_engine.pipeline import default_learner, process_item_async

    default_learner.clear_buffer()

    product = parse_product_input(
        0,
        pd.Series(
            {
                "S.NO": 1,
                "Brand": "Haier",
                "Category": "WASHING_MACHINE",
                "Name ": "Haier HWM 120-826S6 GC Automatic Washing Machine",
                "Length": 60,
                "Width": 60,
                "Height": 90,
                "Net Price": 80000,
                "Profit": 4000,
            }
        ),
    )

    candidate_offers = [
        ScrapedOffer(
            vendor_name="Mega Store Lahore",
            price=85000.0,
            is_sold_out=False,
            raw_title="Haier 120-826S6 Glass Door Automatic Washing Machine",
        )
    ]

    async def _run() -> None:
        from unittest.mock import AsyncMock

        mock_session = AsyncMock()
        sem = asyncio.Semaphore(1)
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", return_value=candidate_offers),
            patch("pricing_engine.pipeline.scrape_digimall", return_value=[]),
        ):
            _ = await process_item_async(product, mock_session, sem, verbose=False)

        assert default_learner.buffer_size >= 1
        obs = default_learner._buffer[-1]
        assert obs["brand"] == "HAIER"
        assert obs["category"] == "WASHING_MACHINE"
        assert obs["anchor_model"] == "120-826S6"
        assert obs["target_residual"] == "GC"
        assert obs["candidate_residual"] == "GLASS DOOR"
        assert obs["normalized_merchant"] == "megastorelahore"

    asyncio.run(_run())


def test_build_scraped_sellers_table_smart_formatting() -> None:
    """Verify smart table formatting renders dropped summary, target undercut, and true ceiling."""
    from pricing_engine.models import CostFloors, PlatformPricingResult, ScrapedOffer
    from pricing_engine.pipeline import build_scraped_sellers_table

    floors = CostFloors(
        floor_alfa=88226.0,
        floor_digi_10=88226.0,
        floor_digi_8=86307.0,
        cost_base=78903.0,
        zero_margin_10=87670.0,
        zero_margin_8=85764.0,
    )

    # 5 sub-floor sellers and 3 viable sellers (total 8 sellers)
    alfa_offers = [
        ScrapedOffer(vendor_name="Sub Seller 1", price=81500.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Sub Seller 2", price=81500.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Sub Seller 3", price=82000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Sub Seller 4", price=83000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Sub Seller 5", price=84000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Kia Chahiye", price=88599.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Electronics World", price=91499.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Ceiling Seller", price=102078.0, is_sold_out=False, raw_title=""),
    ]

    alfa_res = PlatformPricingResult(
        final_price=88499.0,
        min_price=88499.0,
        max_price=88499.0,
        real_profit=746.0,
        reason="Undercut lowest viable",
        status="Won",
        effective_comm="10.00%",
    )
    digi_res = PlatformPricingResult(
        final_price=88499.0,
        min_price=88499.0,
        max_price=88499.0,
        real_profit=2516.0,
        reason="Won at 10%",
        status="Won",
        effective_comm="10.00%",
    )

    tbl = build_scraped_sellers_table(floors, alfa_offers, [], alfa_res, digi_res)

    # Convert table rows to string to inspect contents
    rows_text = []
    for col in tbl.columns:
        for cell in col._cells:
            rows_text.append(str(cell))
    full_table_text = " ".join(rows_text)

    # 1. Target Undercut (Lowest Viable) MUST be present in the table
    assert "Target Undercut (Lowest Viable)" in full_table_text
    assert "Kia Chahiye" in full_table_text
    assert "88,599" in full_table_text

    # 2. Sub-floor rollup must be present because there are 5 dropped sellers (> 3)
    assert "dropped" in full_table_text or "more sub-floor" in full_table_text or "Sub-floor offers" in full_table_text
    assert "Sub Seller 1" in full_table_text
    assert "Sub Seller 2" in full_table_text

    # 3. Market ceiling must be visible
    assert "102,078" in full_table_text


def test_build_scraped_sellers_table_all_subfloor_lossmakers() -> None:
    """Verify clean rendering when all scraped competitors are below the floor."""
    from pricing_engine.models import CostFloors, PlatformPricingResult, ScrapedOffer
    from pricing_engine.pipeline import build_scraped_sellers_table

    floors = CostFloors(
        floor_alfa=88226.0,
        floor_digi_10=88226.0,
        floor_digi_8=86307.0,
        cost_base=78903.0,
        zero_margin_10=87670.0,
        zero_margin_8=85764.0,
    )

    alfa_offers = [
        ScrapedOffer(vendor_name=f"Loss Seller {i}", price=80000.0 + (i * 500), is_sold_out=False, raw_title="")
        for i in range(6)
    ]

    alfa_res = PlatformPricingResult(
        final_price=89999.0,
        min_price=89999.0,
        max_price=89999.0,
        real_profit=2096.0,
        reason="All competitors selling at loss",
        status="Safe Fallback",
        effective_comm="10.00%",
    )
    digi_res = PlatformPricingResult(
        final_price=89999.0,
        min_price=89999.0,
        max_price=89999.0,
        real_profit=3896.0,
        reason="All competitors selling at loss",
        status="Safe Fallback",
        effective_comm="8.00%",
    )

    tbl = build_scraped_sellers_table(floors, alfa_offers, [], alfa_res, digi_res)
    rows_text = []
    for col in tbl.columns:
        for cell in col._cells:
            rows_text.append(str(cell))
    full_table_text = " ".join(rows_text)

    # When all are sub-floor, should render dropped status and loss-makers rollup
    assert "All sub-floor" in full_table_text
    assert "dropped" in full_table_text or "more loss-makers" in full_table_text
    assert "Loss Seller 0" in full_table_text


def test_build_scraped_sellers_table_digimall_two_tier_switch() -> None:
    """Verify DigiMall correctly renders Target Undercut (8% Viable) on emergency switch."""
    from pricing_engine.models import CostFloors, PlatformPricingResult, ScrapedOffer
    from pricing_engine.pipeline import build_scraped_sellers_table

    floors = CostFloors(
        floor_alfa=88226.0,
        floor_digi_10=88226.0,
        floor_digi_8=86307.0,
        cost_base=78903.0,
        zero_margin_10=87670.0,
        zero_margin_8=85764.0,
    )

    digi_offers = [
        ScrapedOffer(vendor_name="Sub Seller", price=85000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Electronics World", price=86702.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Kia Chahiye", price=87500.0, is_sold_out=False, raw_title=""),
    ]

    alfa_res = PlatformPricingResult(
        final_price=88499.0,
        min_price=88499.0,
        max_price=88499.0,
        real_profit=746.0,
        reason="Won",
        status="Won",
        effective_comm="10.00%",
    )
    digi_res = PlatformPricingResult(
        final_price=86499.0,
        min_price=86499.0,
        max_price=86499.0,
        real_profit=677.0,
        reason="Triggered emergency 8% switch",
        status="Won",
        effective_comm="8.00%",
    )

    tbl = build_scraped_sellers_table(floors, [], digi_offers, alfa_res, digi_res)
    rows_text = []
    for col in tbl.columns:
        for cell in col._cells:
            rows_text.append(str(cell))
    full_table_text = " ".join(rows_text)

    # Must display 8% Viable badge
    assert "Target Undercut (8% Viable)" in full_table_text
    assert "Electronics World" in full_table_text
    assert "86,702" in full_table_text


def test_build_scraped_sellers_table_target_predecessor_visibility() -> None:
    """Verify that with many sub-floor sellers, the seller right above target undercut is always visible."""
    from pricing_engine.models import CostFloors, PlatformPricingResult, ScrapedOffer
    from pricing_engine.pipeline import build_scraped_sellers_table

    floors = CostFloors(
        floor_alfa=33964.0,
        floor_digi_10=33964.0,
        floor_digi_8=33226.0,
        cost_base=30000.0,
        zero_margin_10=33333.0,
        zero_margin_8=32608.0,
    )

    # 9 dropped sellers (Allure Beauty, Tech House, etc.) + MZ Electronics as target undercut
    alfa_offers = [
        ScrapedOffer(vendor_name="Allure Beauty", price=16498.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Tech House", price=27999.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Tech House", price=28289.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Other Seller 1", price=30435.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Other Seller 2", price=31000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Other Seller 3", price=31500.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Other Seller 4", price=32000.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Other Seller 5", price=32500.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="Nearest Predecessor", price=33500.0, is_sold_out=False, raw_title=""),
        ScrapedOffer(vendor_name="MZ Electonics", price=34400.0, is_sold_out=False, raw_title=""),
    ]

    alfa_res = PlatformPricingResult(
        final_price=34299.0,
        min_price=34400.0,
        max_price=34400.0,
        real_profit=869.0,
        reason="Undercut lowest viable",
        status="Won",
        effective_comm="10.00%",
    )
    digi_res = PlatformPricingResult(
        final_price=34299.0,
        min_price=34400.0,
        max_price=34400.0,
        real_profit=1557.0,
        reason="Won",
        status="Won",
        effective_comm="10.00%",
    )

    tbl = build_scraped_sellers_table(floors, alfa_offers, [], alfa_res, digi_res)
    rows_text = []
    for col in tbl.columns:
        for cell in col._cells:
            rows_text.append(str(cell))
    full_table_text = " ".join(rows_text)

    # 1. First 2 dropped sellers must be visible
    assert "Allure Beauty" in full_table_text
    assert "16,498" in full_table_text
    assert "Tech House" in full_table_text

    # 2. Middle rollup must be visible (+6 dropped)
    assert "+6 dropped" in full_table_text

    # 3. CRITICAL: The closest seller right before target undercut MUST be visible
    assert "Nearest Predecessor" in full_table_text
    assert "33,500" in full_table_text

    # 4. Target undercut must follow immediately
    assert "MZ Electonics" in full_table_text
    assert "Target Undercut (Lowest Viable)" in full_table_text


def test_run_pipeline_structured_export_mode(tmp_path: Path) -> None:
    """Verify run_pipeline with output_path=None saves to structured export directory."""
    csv_file = tmp_path / "catalog.csv"
    csv_file.write_text(
        "Brand,Name,Net Price,Length,Width,Height\n"
        "Gree,GREE SPLIT AC 12AITH21W-T3,147000,87,35.5,92\n",
        encoding="utf-8",
    )
    export_dir = tmp_path / "data_outputs"

    mock_empty = ScrapeResult(offers=[], is_success=True, status_code=200)

    async def _run() -> None:
        with (
            patch("pricing_engine.pipeline.scrape_alfamall", return_value=mock_empty),
            patch("pricing_engine.pipeline.scrape_digimall", return_value=mock_empty),
        ):
            out_df = await run_pipeline(
                input_path=csv_file,
                output_path=None,
                concurrency=1,
                verbose=False,
                use_structured_export=True,
                export_dir=export_dir,
            )
            assert len(out_df) == 1
            latest_file = export_dir / "catalog_repriced_latest.csv"
            assert latest_file.is_file()
            ts_files = list(export_dir.glob("catalog_repriced_*.csv"))
            assert len(ts_files) >= 2

    asyncio.run(_run())


def test_parse_product_input_invalid_brand_raises_error() -> None:
    for bad_brand in ["", "-", "--", "n/a", "none", "null", "?"]:
        row = pd.Series(
            {
                "S.NO": 1,
                "Brand": bad_brand,
                "Name": "Dawlance Inverter AC",
                "Net Price": 50000,
            }
        )
        with pytest.raises(ValueError, match="Brand.*empty or invalid"):
            parse_product_input(0, row)
````

## File: pricing_engine/matcher.py
````python
import re
from dataclasses import dataclass, field


@dataclass
class GuardedFacets:
    """Zero-tolerance guarded attributes for strict variant collision protection."""

    t3: bool | None = None
    iot: bool | None = None
    capacity: str | None = None  # e.g. "1.5T", "12KG", "50INCH"
    tub_series: str | None = None  # e.g. "WB", "GB"
    color_family: str | None = None  # One of the 9 normalized color families
    color_raw: str | None = None  # Original matched color text
    door_finish: str | None = None  # Hardware finish: 'GD' (Glass Door) vs 'INOX' (Stainless Steel)
    cool_only: bool | None = None  # True if strictly cooling-only AC model
    heat_and_cool: bool | None = None  # True if Heat & Cool AC model
    door_type: str | None = None  # Hardware door structure: 'SD' (Single Door) vs 'DD' (Double Door)
    is_inverter: bool | None = None  # True if Inverter, False if Non-Inverter / Fixed Speed
    capabilities: set[str] = field(default_factory=set)  # Additive hardware capabilities: T3, INVERTER, WIFI, IOT, ES, UV


@dataclass
class ProductSlots:
    """4-Slot structural attribute representation of a product title."""

    anchor: str  # Primary invariant alphanumeric model code (e.g. '120-826S6', '276EBS')
    series: str  # Dynamic series extracted via residual subtraction (e.g. 'MAGNA', 'CHROME PRO')
    guarded_facets: GuardedFacets
    residuals: list[str] = field(default_factory=list)  # Soft modifiers: 'GC', 'GLASS DOOR', etc.


@dataclass
class MatchDecision:
    """Detailed verdict and audit trail from the negative-collision referee."""

    is_match: bool
    reason: str
    target_slots: ProductSlots | None = None
    candidate_slots: ProductSlots | None = None
    is_base_match: bool = False
    missing_modifier: str | None = None


# ==============================================================================
# CATEGORY 1: DIRECT-MATCH MODIFIERS (Skipped / Soft Structural Descriptors)
# ==============================================================================
# Marketplace sellers frequently omit these modifiers (e.g., listing a Single Door
# refrigerator simply as the base model without writing "SD").
# RULE:
# 1. Target has Category 1 modifier & candidate omits it -> ACCEPT DIRECT MATCH (is_match=True, is_base_match=False) with zero warning.
# 2. Target has Category 1 modifier & candidate has opposing code (e.g. SD vs DD) -> HARD COLLISION.
# STRICT REQUIREMENT: Only contains 'SD' right now. The user can add more tokens here in the future.
CATEGORY_1_DIRECT_MATCH_MODIFIERS: set[str] = {
    "SD",  # Single Door (e.g. Refrigerator / Dispenser Single Door)
}


# 9 Normalized Color Families (ADR-002)
COLOR_FAMILIES: dict[str, list[str]] = {
    "White": ["MILKY WHITE", "PEARL WHITE", "WHITE", "MILKY", "IVORY"],
    "Black": ["PIANO BLACK", "MATTE BLACK", "MIDNIGHT BLACK", "BLACK", "DARK", "MIDNIGHT"],
    "Grey / Silver": [
        "METALLIC GREY",
        "DARK METALLIC",
        "METALLIC GRAY",
        "STAINLESS STEEL",
        "INOX",
        "S.S",
        "GREY",
        "GRAY",
        "SILVER",
        "METALLIC",
        "STEEL",
        "TITANIUM",
        "GRAPHITE",
        "PLATINUM",
    ],
    "Red / Maroon": ["RED", "MAROON", "BURGUNDY", "RUBY", "CRIMSON", "CORAL"],
    "Gold / Bronze / Copper": [
        "ROSE GOLD",
        "CLASSIC GOLD",
        "GOLD",
        "CHAMPAGNE",
        "BRONZE",
        "COPPER",
    ],
    "Brown / Wood": ["BROWN", "CHOCOLATE", "WOOD", "WALNUT", "TEAK"],
    "Blue": ["ROYAL BLUE", "SKY BLUE", "NAVY BLUE", "BLUE", "NAVY"],
    "Green": ["GREEN", "EMERALD", "OLIVE"],
    "Purple / Pink": ["PURPLE", "VIOLET", "PINK"],
}

# Single-letter color suffix codes attached to model codes (e.g. 12AITH21W -> W)
COLOR_SUFFIX_MAP: dict[str, str] = {
    "W": "White",
    "B": "Black",
    "D": "Black",
    "S": "Grey / Silver",
    "G": "Grey / Silver",
    "R": "Red / Maroon",
    "P": "Purple / Pink",
}


def normalize_color(title: str, anchor: str = "") -> tuple[str | None, str | None]:
    """Extract and normalize color into one of 9 canonical families with anchor isolation.

    Inviolability Rule: The internal letters of isolated alphanumeric anchors
    (e.g. 120-826S6, 276EBS) are never mutated or parsed as full color names.
    """
    title_search = title
    if anchor:
        title_search = re.sub(rf"\b{re.escape(anchor)}\b", " ", title, flags=re.IGNORECASE)

    # Search for multi-word and single-word color tokens
    for family, aliases in COLOR_FAMILIES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", title_search, re.IGNORECASE):
                return family, alias

    # Fallback to trailing single-letter color code on model anchor (e.g. 12AITH21W -> W -> White)
    if anchor:
        m_suf = re.search(r"\d+[A-Za-z]+?\d+([WBSGDRP])$", anchor, re.IGNORECASE)
        if m_suf:
            letter = m_suf.group(1).upper()
            fam = COLOR_SUFFIX_MAP.get(letter)
            if fam:
                return fam, letter

    return None, None


# Normalized standalone and compound color words derived dynamically from COLOR_FAMILIES
ALL_COLOR_WORDS: set[str] = {
    word.upper()
    for aliases in COLOR_FAMILIES.values()
    for alias in aliases
    for word in alias.split()
    if word.upper() not in {"CLASSIC", "STEEL", "WOOD", "S.S"}
}


def is_color_token(token: str) -> bool:
    """Check if token matches any normalized color word or single-letter color code."""
    clean = token.strip("-_., \"'").upper()
    return clean in ALL_COLOR_WORDS or clean in COLOR_SUFFIX_MAP


def get_all_color_families(text: str) -> set[str]:
    """Extract all canonical color families present in a model code or title."""
    fams: set[str] = set()
    for fam, aliases in COLOR_FAMILIES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", text, re.IGNORECASE):
                fams.add(fam)
                break
    for token in text.split():
        clean_tok = token.strip("-_., \"'")
        # Check single-letter color code on model anchor (e.g. 12AITH21W -> W -> White)
        m_suf = re.search(r"\d+[A-Za-z]+?\d+([WBSGDRP])$", clean_tok, re.IGNORECASE)
        if m_suf:
            letter = m_suf.group(1).upper()
            fam = COLOR_SUFFIX_MAP.get(letter)
            if fam:
                fams.add(fam)
    return fams


# Category acronyms and fractions to safeguard from expansion
SAFEGUARD_PATTERN = re.compile(
    r"\b(?:W/M|W/D|D/F|A/C|H/C|H&C|W/O)\b"
    r"|\bHeat\s*/\s*Cool\b"
    r"|\b\d+/\d+\s*(?:\"|inch|mm)\b"
    r"|\b\d+W/\d+D\b"
    # Technical model suffixes: 18HE/DC, HBU-48E/DC, 48CE/DC, HBU-48HE/T3DC-012GE
    r"|[A-Za-z0-9\-]+/(?:DC|AC)\b"
    r"|[A-Za-z0-9\-]+/T3[A-Za-z0-9\-]*\b"
    # Subordinate model codes: 24CE03/KB-01
    r"|[A-Za-z0-9\-]+/KB[-]?\d+"
    # Model year codes: GN-261/21, GNE-396/20, GND-1606/23 (require hyphen in model code)
    r"|[A-Z]{2,}-\d+/\d{2}\b",
    re.IGNORECASE,
)

TAG_PATTERN = re.compile(r"[-_\s]*(?:T3|AAA|AA\+|AA|PRO|ULTRA|PLUS)+$", re.IGNORECASE)

# Standard category and capacity phrases to strip from search queries
CATEGORY_PATTERNS = re.compile(
    r"\b(?:AWM|AUTO\s+W/M|FRONT\s+LOAD(?:\s+W/M)?|W/M|WASHING\s+MACHINE|AIR\s+CONDITIONER|M/OVEN|M/O|D/F|R/F|W/D|SPLIT\s+AC|SPLIT|FLOOR(?:\s+STANDING)?|DISHWASHER|SPINNER)\b"
    r"|\b(?:AIR\s*CURTAIN|AIR\s*COOLER|AIR\s*FRYER|WATER\s+HEATER|WATER\s+DISPENSER|WATER\s+PURIFIER|INSECT\s+KILLER|JUG\s+KETTLE|HOT\s+PLATE|CHOPPER|BLENDER|IRON|LED|MICROWAVE|OVEN|SANDWI?T?CH\s+MAKER)\b"
    r"|\b(?:MINI\s*BAR|MINIBAR|ROOM\s*FRIDGE|BEDROOM\s*SERIES|REFRIGERATOR|FRIDGE)\b"
    r"|\b(?:SINGLE\s*DOOR|DOUBLE\s*DOOR|TRIPLE\s*DOOR|FOUR\s*DOOR|FRENCH\s*DOOR|SIDE\s*BY\s*SIDE|SINGLE\s*TUB)\b"
    r"|\b(?:INVERTER|NORMAL|SERIES|DIGITAL|GLASS\s+DOOR|CLEAR\s+LID|OPAQUE(?:\s+LID)?|TWIN\s*TUB|NO[\s\-]*FROST|CVT|SMART|WIFI|WI-FI|IOT|4K|FHD|GAS\+ELECTRIC|BUILT-IN|FIX(?:ED)?\s*SPEED)\b"
    r"|\b(?:\d+(?:\.\d+)?\s*(?:TON|ΤΟN|KG|GM|LTR|LITRE|SETS|SETS?|FEET|FT|CU\s*FT|CU\.FT|CFT|CU|INCH|MM|CM|\"|\'))\b",
    re.IGNORECASE,
)

# Common non-SKU unit stop-tokens
NON_SKU_TOKENS = {
    "TON",
    "ΤΟN",
    "KG",
    "GM",
    "LTR",
    "SET",
    "SETS",
    "FEET",
    "FT",
    "CU",
    "CFT",
    "MM",
    "CM",
    "INCH",
    "AC",
    "AND",
    "WITH",
    "THE",
    "FOR",
    "TOP",
    "LID",
    "OPAQUE",
    "CLEAR",
    "DOOR",
    "AIR",
    "CURTAIN",
    "BLENDER",
    "CHOPPER",
    "OVEN",
    "HEATER",
    "WASHER",
    "PURIFIER",
    "KETTLE",
    "SMART",
    "W/O",
    "REF",
    "FRIDGE",
    "REFRIGERATOR",
    "MINIBAR",
    "MINI",
    "BAR",
    "TUB",
    "TWIN",
    "SPIN",
    "DRYER",
    "AIRFRYER",
    "FRONT",
    "LOAD",
    "SEMI",
    "AUTO",
    "CONTROL",
    "MANUAL",
    "SOLUTION",
    "AAA+",
    "AA+",
    "AAA",
    "AA",
    "A+",
    "ON",
    "IN",
    "AT",
    "BY",
    "OF",
    "TO",
    "OR",
    "AS",
    "NO",
    "ALL",
    "BIG",
    "USE",
    "NEW",
    "HOT",
    "COLD",
    "LOW",
    "FIT",
    "ONE",
    "TWO",
    "SIX",
    "TEN",
    "OFF",
    "OUT",
    "BAG",
    "BOX",
    "HOME",
    "ROOM",
    "DRY",
    "WET",
    "RUN",
    "DAY",
    "BUY",
    "PAY",
    "OIL",
    "GAS",
    "CAP",
    "LVS",
    "WASH",
    "FAST",
    "FREE",
    "SALE",
    "BEST",
    "CARD",
    "PACK",
    "YEAR",
    "TONS",
    "FULL",
    "LINE",
    "COOL",
    "HEAT",
    "TYPE",
    "SIZE",
    "LITE",
    "GOLD",
    "PURE",
    "SLIM",
    "WIDE",
    "DEEP",
    "HIGH",
    "DROP",
    "STOP",
    "TRUE",
    "TRIP",
    "QUAD",
    "CARE",
    "SAFE",
    "LOCK",
    "TIME",
    "UNIT",
    "MAKE",
    "PART",
    "LOOK",
    "GOOD",
    "FINE",
    "VERY",
    "WELL",
    "JUST",
    "ALSO",
    "MORE",
    "LESS",
    "EASY",
    "SOFT",
    "HARD",
    "DARK",
    "EVEN",
    "EVER",
    "EACH",
    "FROM",
    "OVER",
    "DOWN",
    "OPEN",
    "SHUT",
    "FLAT",
    "SIDE",
    "REAR",
    "WALL",
    "BASE",
    "BEAM",
    "WIRE",
    "CORD",
    "PLUG",
    "PIPE",
    "HOSE",
    "TUBE",
    "BODY",
    "HEAD",
    "FOOT",
    "HAND",
    "LEAD",
    "PULL",
    "PUSH",
    "TURN",
    "MOVE",
    "KEEP",
    "HOLD",
    "4K",
    "8K",
    "FHD",
    "UHD",
    "HD",
    "LED",
    "OLED",
    "QLED",
    "TV",
    "DC",
}

GENUINE_SUB_SERIES_TOKENS = {
    "PRO",
    "PLUS",
    "MAX",
    "ULTRA",
    "CLASSIC",
    "ELEGANT",
    "PRIMA",
    "X",
    "LITE",
    "SUPER",
    "TOUCH",
}

# Generic marketplace noise (seller signatures, promotions, payment terms, HVAC operational phrases)
MARKETPLACE_NOISE_RE = re.compile(
    r"\b(?:ON\s+INSTALLMENT|INSTALLMENT|0%\s*MARKUP|MARKUP|INTEREST|DOWN\s*PAYMENT|EMI|CASH\s+ON\s+DELIVERY|COD)\b"
    r"|\b(?:FREE\s+(?:HOME\s+)?DELIVERY|FAST\s+DELIVERY|DELIVERY|SHIPPING|EXPRESS|FREE\s+INSTALLATION)\b"
    r"|\b(?:OFFICIAL\s+WARRANTY|BRAND\s+WARRANTY|COMPANY\s+WARRANTY|WARRANTY\s+CARD|WARRANTY|\d+\s*YEARS?\s+WARRANTY)\b"
    r"|\b(?:SALE|DISCOUNT|DEAL|OFFER|PROMO|PROMOTION|RAMADAN\s+OFFER|EID\s+OFFER|SUPER\s+SALE)\b"
    r"|\b(?:ORIGINAL|AUTHENTIC|GENUINE|BRAND\s+NEW|SEALED\s+PACK|SEALED|BOX\s+PACK|100%\s*ORIG(?:I)?NAL)\b"
    r"|\b(?:SPECIAL\s+GIFT|SURPRISE\s+GIFT|FREE\s+GIFT|BEST\s+PRICE)\b"
    r"|\b(?:ELECTROEASE|HOMECART|METRO|HYPERSTAR|ALFAMALL|FAYSAL\s*BANK|QISTBAZAAR|ESBUY|TELEMART|YAYVO)\b"
    r"|\b(?:HEAT\s*(?:&|AND|/)\s*COOL|H\s*&\s*C|COOLING\s*ONLY|COOL\s*ONLY)\b"
    r"|\b(?:INVERTER\s*AC|DC\s*INVERTER|FIX(?:ED)?\s*SPEED|NON[\s\-]*INVERTER)\b"
    r"|\b(?:AAA\+|AA\+|A\+{1,3}|AAA|AA)\b"
    r"|\b(?:ISPK|SNS|SKU|ID)[-_]?\w+",
    re.IGNORECASE,
)


def normalize_technical_slashes(text: str) -> str:
    """Normalize technical compound codes (/DC, /AC, /Z, etc.) while preserving model boundaries."""
    t = text
    # 24 HD/Z -> 24 HDZ
    t = re.sub(r"\b([A-Za-z0-9]+)/Z\b", r"\1Z", t, flags=re.IGNORECASE)
    # 18HE/DC -> 18HE-DC, 48CE/DC -> 48CE-DC, 24 HE/DC -> 24 HE-DC
    t = re.sub(r"\b([A-Za-z0-9]+)/(DC|AC)\b", r"\1-\2", t, flags=re.IGNORECASE)
    t = re.sub(r"\bH\s*&\s*C\b", "Heat and Cool", t, flags=re.IGNORECASE)
    t = re.sub(r"\bH/C\b", "Heat and Cool", t, flags=re.IGNORECASE)
    t = re.sub(r"\bW/M\b", "Washing Machine", t, flags=re.IGNORECASE)
    t = re.sub(r"\bA/C\b", "AC", t, flags=re.IGNORECASE)
    return t


def expand_cartesian_branches(title: str) -> list[str]:
    """If title contains slash-separated alternative models/variants, expand into independent branches."""
    t_norm = normalize_technical_slashes(title)
    # Detect alternative model codes separated by slash:
    # e.g. 'HRF-418 TIFG1U1/TIFB1U1 (IOT)' or 'HGL-25MXP8 / 25MXP9' or '30 Sprinter / Powercon'
    m_slash = re.search(r"(\b[A-Za-z0-9\-_]+)\s*/\s*([A-Za-z0-9\-_]+)", t_norm)
    if m_slash:
        left = m_slash.group(1).strip()
        right = m_slash.group(2).strip()
        if len(left) >= 3 and len(right) >= 3:
            b1 = t_norm[: m_slash.start()] + left + t_norm[m_slash.end() :]
            b2 = t_norm[: m_slash.start()] + right + t_norm[m_slash.end() :]
            branches = [b1.strip(), b2.strip()]
            if "-" in left:
                pfx, stem_left = left.rsplit("-", 1)
                branches.append((t_norm[: m_slash.start()] + stem_left + t_norm[m_slash.end() :]).strip())
                branches.append((t_norm[: m_slash.start()] + f"{pfx}-{right}" + t_norm[m_slash.end() :]).strip())
            return list(dict.fromkeys(branches))
    return [t_norm.strip()]


def clean_marketplace_noise(text: str) -> str:
    """Strip common e-commerce noise (seller signatures, promos, payment terms, HVAC operational tags)."""
    # 1. Pipe and dash trailers: ' | Fast Drying Solution', ' – Electric Clothes Spinner', ' - ElectroEase'
    t = re.sub(r"\s*[|–—].*$", "", text.strip())
    t = re.sub(r"\s*(?:[-|/]|--)\s*(?:By\s+|Official\s+)?[A-Z][A-Za-z0-9\s.]{2,}$", "", t)
    # 2. Structural promotional and transactional expressions
    return MARKETPLACE_NOISE_RE.sub(" ", t).strip()


def is_dimension_or_spec_token(token: str) -> bool:
    """Check if a token represents physical dimensions, capacity, or feature counts instead of a model code."""
    clean = token.strip("-_., \"'")
    if not clean:
        return True
    if re.match(r"^T\d+$", clean, re.IGNORECASE):
        return True
    # Units attached to numbers: 3FEET, 3FT, 4FEET, 7KG, 13SETS, 40INCH, 1000W, 3IN1, etc.
    if re.match(
        r"^\d+(?:\.\d+)?(?:FEET|FT|INCH|MM|CM|KG|GM|LTR|LITRE|SETS?|TON|WATTS?|W|\"|\')?$",
        clean,
        re.IGNORECASE,
    ):
        # Standalone pure numbers with >= 3 digits (like 1088, 1400, 9270, 330) are valid model codes
        if re.match(r"^\d+$", clean):
            return len(clean) <= 2
        return True
    return bool(re.match(r"^\d+IN\d+$", clean, re.IGNORECASE))  # 3IN1, 2IN1


def is_sku_variant_tag(token: str) -> bool:
    """Dynamically determine if a trailing token is an SKU variant tag (PL, FLT, ES, T3)
    vs a marketing or color word (WHITE, BLACK, MYSTIC, GREY, CLOUD, EMERALD).

    Structural Rule (Zero Hardcoded Color Lists):
    - Pure numbers and decimal floats (e.g. 2.0, 1.5, 12) -> Capacity / Specs, NOT an SKU tag!
    - Genuine sub-series tokens (e.g. PRO, PLUS, MAX, ULTRA) -> Sub-series, NOT an SKU tag!
    - Contains digits AND letters (e.g. S6, S8, T3, 11S, ES8) -> SKU Variant Tag.
    - Short code <= 3 characters (e.g. PL, FLT, FLP, DG, CP, PB, ES, SD, DD, UV) -> SKU Variant Tag.
    - English words, colors, and marketing descriptions have length >= 4 -> Automatically Excluded!
    """
    clean = token.strip("-_., \"'")
    if not clean or clean.upper() in NON_SKU_TOKENS:
        return False
    if clean.upper() in {"WB", "GB"}:
        return False
    # Universal variant finish codes
    if clean.upper() in {"INOX"}:
        return True
    if is_color_token(clean):
        return False
    if clean.upper() in GENUINE_SUB_SERIES_TOKENS:
        return False
    # Pure numbers or decimal floats (e.g. 2.0, 1.5, 24) are capacities, not SKU variant tags
    if re.match(r"^\d+(?:\.\d+)?$", clean):
        return False
    # Units attached to numbers (e.g. 1.5TON, 9KG, 40INCH, 1000W) are specs, not SKU variant tags
    if re.match(
        r"^\d+(?:\.\d+)?(?:FEET|FT|INCH|MM|CM|KG|GM|LTR|LITRE|SETS?|TON|WATTS?|W|\"|\')$",
        clean,
        re.IGNORECASE,
    ):
        return False
    if re.match(r"^\d+IN\d+$", clean, re.IGNORECASE):  # 3IN1, 2IN1
        return False
    # If contains digits, must also contain letters and have at most 2 digits (e.g. T3, T4, ES8, S6, S8, 11S, MXP8)
    if re.search(r"\d", clean):
        digits = re.findall(r"\d", clean)
        return bool(re.search(r"[A-Za-z]", clean)) and len(digits) <= 2 and len(clean) <= 4
    # 2 to 4 letter variant codes (e.g. ES, SD, DD, FLT, IFGA, IPPA, CHZP, TIFG, TIFB)
    return 2 <= len(clean) <= 4 and clean.isalpha()


# Universal AC capacity code → tonnage mapping (Gree, Haier, Orient, PEL, Kenwood, EcoStar, TCL, Midea, etc.)
# Follows industry-standard BTU coding (BTU / 1,000):
# 09 / 9 = 0.75 Ton (approx. 9,000 BTU)
# 12     = 1.0 Ton  (approx. 12,000 BTU)
# 18     = 1.5 Ton  (approx. 18,000 - 19,000 BTU)
# 24     = 2.0 Ton  (approx. 24,000 BTU)
# 28, 30 = 2.5 Ton  (approx. 28,000 - 30,000 BTU)
# 36     = 3.0 Ton  (approx. 36,000 BTU)
# 48     = 4.0 Ton  (approx. 48,000 BTU)
UNIVERSAL_CAPACITY_TO_TONNAGE: dict[str, str] = {
    "09": "0.75",
    "9": "0.75",
    "12": "1",
    "18": "1.5",
    "24": "2",
    "28": "2.5",
    "30": "2.5",
    "36": "3",
    "48": "4",
}

# Dawlance proprietary AC capacity code → tonnage mapping
# Dawlance uses custom cooling codes:
# 10 = 0.75 Ton (9,000 - 10,000 BTU)
# 15 = 1.0 Ton  (12,000 BTU)
# 20 = 1.25 Ton (14,000 - 15,000 BTU)
# 30 = 1.5 Ton  (18,000 BTU)
# 45 = 2.0 Ton  (24,000 BTU)
DAWLANCE_CAPACITY_TO_TONNAGE: dict[str, str] = {
    "10": "0.75",
    "15": "1",
    "20": "1.25",
    "30": "1.5",
    "45": "2",
}

# Backward compatibility alias
_CAPACITY_TO_TONNAGE: dict[str, str] = DAWLANCE_CAPACITY_TO_TONNAGE


def _invert_capacity_map(cap_map: dict[str, str]) -> dict[str, set[str]]:
    """Invert capacity-to-tonnage map and generate equivalent tonnage representations."""
    inv: dict[str, set[str]] = {}
    for code, ton in cap_map.items():
        inv.setdefault(ton, set()).add(code)
        if "." not in ton:
            inv.setdefault(f"{ton}.0", set()).add(code)
    return inv


UNIVERSAL_TONNAGE_TO_CODES: dict[str, set[str]] = _invert_capacity_map(
    UNIVERSAL_CAPACITY_TO_TONNAGE
)
DAWLANCE_TONNAGE_TO_CODES: dict[str, set[str]] = _invert_capacity_map(DAWLANCE_CAPACITY_TO_TONNAGE)

# Dynamic Brand-to-Capacity System Registry
BRAND_CAPACITY_SYSTEMS: dict[str, dict[str, str]] = {
    "DAW": DAWLANCE_CAPACITY_TO_TONNAGE,
}


def get_capacity_map(brand: str = "") -> dict[str, str]:
    """Dynamically resolve capacity mapping for a given brand from registry, defaulting to Universal."""
    b_upper = brand.strip().upper()
    for prefix, cap_map in BRAND_CAPACITY_SYSTEMS.items():
        if b_upper.startswith(prefix):
            return cap_map
    return UNIVERSAL_CAPACITY_TO_TONNAGE


def get_tonnage_map(brand: str = "") -> dict[str, set[str]]:
    """Dynamically get tonnage-to-codes mapping for a given brand."""
    return _invert_capacity_map(get_capacity_map(brand))


def get_capacity_tonnage(code: str, brand: str = "") -> str | None:
    """Get the tonnage string for an AC capacity code, brand-aware."""
    clean_code = code.strip().upper()
    if brand:
        return get_capacity_map(brand).get(clean_code)

    # Brand unknown: determine by code exclusivity across systems
    for cap_map in BRAND_CAPACITY_SYSTEMS.values():
        if clean_code in cap_map and clean_code not in UNIVERSAL_CAPACITY_TO_TONNAGE:
            return cap_map.get(clean_code)
    return UNIVERSAL_CAPACITY_TO_TONNAGE.get(clean_code)


def extract_search_query_and_model(full_name: str, brand: str = "") -> tuple[str, str]:
    """Extract search token and full model identifier from a catalog product name.

    100% Brand-Agnostic & DRY: Zero hardcoded brand lists, zero hardcoded color lists.
    Dynamically strips brand and category fluff using catalog metadata and structural rules.

    Args:
        full_name: The full descriptive catalog name of the product.
        brand: Optional brand name from catalog metadata (e.g. 'Dawlance', 'Gree', 'Haier').

    Returns:
        Tuple of (clean_search_query, raw_model_code).
    """
    clean = full_name.strip()

    # 1. Dynamically strip Brand name and brand abbreviation using catalog brand metadata
    detected_brand = (brand or (clean.split()[0] if clean else "")).strip()
    if detected_brand:
        b_prefix_re = rf"^(?:{re.escape(detected_brand)}|{re.escape(detected_brand[:3]) if len(detected_brand) >= 4 else '---'})[\s\-_,:]*"
        while re.match(b_prefix_re, clean, flags=re.IGNORECASE):
            clean = re.sub(b_prefix_re, "", clean, count=1, flags=re.IGNORECASE).strip()

    # Pre-process technical slashes before category stripping (24 HD/Z -> 24 HDZ, 24 HE/DC -> 24 HE-DC)
    clean = normalize_technical_slashes(clean)

    # Check for descriptive series + capacity ONLY if anchored to end without trailing model code
    m_desc = re.search(
        r"^(.*?)\s+(\d+(?:\.\d+)?)\s*(?:ton|tonnage|kg|inch|\"|\')(?:\s+(?:inverter|fix(?:ed)?\s*speed|ac|split|heat\s*&\s*cool|cool\s*only))*$",
        clean,
        flags=re.IGNORECASE,
    )
    if m_desc and m_desc.group(1).strip().upper() not in {"SPLIT", "SPLIT AC", "INVERTER", "AC", "AUTO", "AWM"}:
        series_name = m_desc.group(1).strip()
        cap_val = m_desc.group(2).strip()
        query = f"{detected_brand} {series_name} {cap_val}".strip() if detected_brand else f"{series_name} {cap_val}"
        return query, f"{series_name} {cap_val}"

    # Check for TV pattern: e.g. 32" D2 -> 32 D2
    m_tv = re.search(r"\b(\d{2})\s*(?:\"|inch|\')\s+([A-Za-z0-9]+)\b", clean, flags=re.IGNORECASE)
    if m_tv:
        screen = m_tv.group(1)
        model = m_tv.group(2)
        query = f"{detected_brand} {screen} {model}".strip() if detected_brand else f"{screen} {model}"
        return query, f"{screen} {model}"

    # 2. Strip standard category and capacity phrases
    clean = CATEGORY_PATTERNS.sub(" ", clean).strip()

    # 3. Find model code:
    # Primary model token contains digits: e.g. DWT-1165, 100-316S6, HDG-201S, 12AITH21W-T3
    # Subsequent tokens are SKU variant tags (<= 3 chars or containing digits, e.g. PL, FLT, ES, GC)
    tokens = clean.split()
    model_tokens: list[str] = []

    # Check for capacity + series pattern: e.g. 24 HDZ, 48 EDC, 18 HE-DC
    if len(tokens) >= 2 and tokens[0].isdigit() and len(tokens[0]) <= 2:
        m_next_alpha = re.search(r"^[A-Za-z0-9\-_]+$", tokens[1].strip("-.,_ \"'"))
        if m_next_alpha and tokens[1].strip("-.,_ \"'").upper() not in NON_SKU_TOKENS:
            cap_tok = tokens[0]
            ser_tok = tokens[1].strip("-.,_ \"'")
            rest_toks = [t.strip("-.,_ \"'") for t in tokens[2:] if is_sku_variant_tag(t)]
            raw_model = f"{cap_tok} {ser_tok}" + (f" {' '.join(rest_toks)}" if rest_toks else "")
            query = f"{detected_brand} {ser_tok} {cap_tok}".strip() if detected_brand else f"{ser_tok} {cap_tok}"
            return query, raw_model

    for t in tokens:
        t_clean = t.strip("-.,_ \"'")
        if not t_clean or t_clean.upper() in NON_SKU_TOKENS:
            continue
        if not model_tokens:
            if (
                len(t_clean) >= 3
                and re.search(r"\d", t_clean)
                and not is_dimension_or_spec_token(t_clean)
                and re.match(r"^[A-Za-z0-9\-_]+$", t_clean)
            ):
                model_tokens.append(t_clean)
        else:
            if is_sku_variant_tag(t_clean) or (
                model_tokens and model_tokens[0].isdigit() and is_color_token(t_clean)
            ):
                model_tokens.append(t_clean)
            else:
                break

    if model_tokens:
        raw_model = " ".join(model_tokens)
        first_token = model_tokens[0]
        # Only strip brand initial form-factor wrapper if the token begins with brand initial followed by form-factor letter AND has more letters after digits (like Gree GS-12AITH -> 12AITH)
        # Never strip genuine prefixes like WF-5254 (Westpoint) or GN-5024 (Gaba National) where no series letters follow the digits!
        clean_first = first_token
        if detected_brand and re.search(r"\d+[A-Za-z]", first_token):
            clean_first = re.sub(
                rf"^{re.escape(detected_brand[0])}[A-Za-z][-_]?(?=\d)",
                "",
                first_token,
                flags=re.IGNORECASE,
            )
        parts = clean_first.split("-")
        search_token = parts[0] if parts and len(parts[0]) >= 5 else clean_first
        return search_token, raw_model

    # 4. Name-only fallback: no digit-based model token found.
    # Collect series names, capacity codes, and sub-variant descriptors.
    # Stop-words that are NOT part of the product identity:
    _NAME_STOP = {
        "INVERTER",
        "INV",
        "SERIES",
        "NORMAL",
        "COOL",
        "ONLY",
        "+",
        "(",
        ")",
        "[",
        "]",
    }
    # Brand-aware AC capacity codes derived dynamically from single source of truth:
    _CAPACITY_CODES = set(UNIVERSAL_CAPACITY_TO_TONNAGE.keys()).union(
        *(m.keys() for m in BRAND_CAPACITY_SYSTEMS.values())
    )

    remaining = CATEGORY_PATTERNS.sub(" ", clean).strip()
    remaining = re.sub(r"[()]", " ", remaining)  # Strip parentheses
    name_tokens = remaining.split()

    significant: list[str] = []
    capacity: str = ""
    for t in name_tokens:
        t_clean = t.strip("-.,_ \"'+")
        if not t_clean:
            continue
        t_upper = t_clean.upper()
        if t_upper in _CAPACITY_CODES and not capacity:
            capacity = t_clean
            significant.append(t_clean)
        elif t_upper not in _NAME_STOP and t_upper not in NON_SKU_TOKENS:
            significant.append(t_clean)

    # If no numeric capacity code was found in name tokens, check for explicit tonnage phrase in full title
    if not capacity:
        m_ton = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:TON|ΤΟN)\b", full_name, re.IGNORECASE)
        if m_ton:
            ton_val = m_ton.group(1)
            ton_map = get_tonnage_map(detected_brand)
            ton_codes = ton_map.get(ton_val)
            if ton_codes:
                capacity = sorted(ton_codes)[0]
                significant.append(capacity)

    if significant:
        # Search query: Brand + first significant word + capacity (broad search)
        query_parts = []
        if detected_brand:
            query_parts.append(detected_brand)
        # Avoid repeating capacity if capacity is at index 0 (e.g. '15 Infinity Pro' -> 'Dawlance Infinity 15')
        series_words = [w for w in significant if w != capacity and w != "/"]
        if series_words:
            query_parts.append(series_words[0])
        elif significant:
            query_parts.append(significant[0])
        if capacity:
            query_parts.append(capacity)
        search_query = " ".join(query_parts)
        keyword_model = " ".join(significant)
        return search_query, keyword_model

    parts = clean.split()
    fallback = parts[-1] if parts else clean
    return fallback, clean


def extract_tag(s: str) -> tuple[str, str]:
    """Separate trailing auxiliary tag (e.g. -T3, -ES, AAA, PRO) from token core."""
    if "-" in s:
        parts = s.split("-")
        if len(parts) > 1 and any(re.search(r"\d", p) for p in parts[:-1]):
            trailing = parts[-1].strip()
            if is_sku_variant_tag(trailing) or trailing.upper() in GENUINE_SUB_SERIES_TOKENS:
                return "-".join(parts[:-1]), f"-{trailing}"
    # Glued trailing variant tag on prefix+numeric stem with >= 3 digits (e.g. DWT11467ES -> DWT11467, -ES)
    m_stem_tag = re.match(r"^([A-Za-z]{2,4}\d{3,})([A-Za-z]{2,4})$", s)
    if m_stem_tag:
        stem = m_stem_tag.group(1)
        tag = m_stem_tag.group(2)
        if is_sku_variant_tag(tag):
            return stem, f"-{tag}"
    m = TAG_PATTERN.search(s)
    if m:
        return s[: m.start()], m.group(0)
    return s, ""


def split_runs(s: str) -> list[tuple[str, str]]:
    """Split an alphanumeric string into ordered typed runs: ('D', digits), ('L', letters), ('P', punctuation)."""
    runs: list[tuple[str, str]] = []
    for m in re.finditer(r"([0-9]+)|([A-Za-z]+)|([^0-9A-Za-z\s]+)", s):
        if m.group(1):
            runs.append(("D", m.group(1)))
        elif m.group(2):
            runs.append(("L", m.group(2)))
        elif m.group(3):
            runs.append(("P", m.group(3)))
    return runs


def distribute_runs(stem: str, parts: list[str], trailing_tag: str = "") -> list[str]:
    """Distribute shared numeric prefixes, letter suffixes, and tags across asymmetric variant parts."""
    parsed: list[dict[str, str]] = []
    for p in parts:
        core, tag = extract_tag(p)
        m_dig = re.match(r"^([0-9]+)", core)
        digits = m_dig.group(1) if m_dig else ""
        remainder = core[len(digits) :]
        m_let = re.search(r"([A-Za-z]+)$", remainder)
        letters = m_let.group(1) if m_let else ""
        middle = remainder[: len(remainder) - len(letters)]
        parsed.append(
            {
                "raw": p,
                "core": core,
                "digits": digits,
                "middle": middle,
                "letters": letters,
                "tag": tag,
            }
        )

    common_tag = trailing_tag
    if not common_tag:
        for item in reversed(parsed):
            if item["tag"]:
                common_tag = item["tag"]
                break

    has_leading_digits = parsed[0]["digits"] != ""
    some_lack_digits = any(item["digits"] == "" and item["letters"] != "" for item in parsed[1:])
    distribute_pre = parsed[0]["digits"] if (has_leading_digits and some_lack_digits) else ""

    last_letters = parsed[-1]["letters"]
    some_lack_letters = any(item["letters"] == "" for item in parsed[:-1])
    distribute_suf = last_letters if (last_letters and some_lack_letters) else ""

    results: list[str] = []
    for item in parsed:
        dig = item["digits"] or distribute_pre
        let_val = item["letters"] or distribute_suf
        mid = item["middle"]
        tag = item["tag"] or common_tag
        built = f"{stem}{dig}{mid}{let_val}{tag}"
        results.append(built)

    return results


def expand_slash_word(word: str) -> list[str]:
    """Expand a single slash-separated model token using structural token-run alignment."""
    raw_parts = [p.strip() for p in word.split("/") if p.strip()]
    if len(raw_parts) < 2:
        return [word]

    parsed: list[dict[str, str]] = []
    for p in raw_parts:
        core, tag = extract_tag(p)
        m_dig = re.match(r"^([0-9]+)", core)
        digits = m_dig.group(1) if m_dig else ""
        remainder = core[len(digits) :]
        m_let = re.search(r"([A-Za-z]+)$", remainder)
        letters = m_let.group(1) if m_let else ""
        middle = remainder[: len(remainder) - len(letters)]
        parsed.append(
            {
                "raw": p,
                "core": core,
                "digits": digits,
                "middle": middle,
                "letters": letters,
                "tag": tag,
            }
        )

    p0 = parsed[0]["core"]
    p1 = parsed[1]["core"]

    lead_runs = split_runs(p0)
    sub_runs = split_runs(p1)

    n_sub = len(sub_runs)
    n_lead = len(lead_runs)
    sub_types = [t for t, _ in sub_runs]
    split_idx = -1

    # 1. Exact run sequence match at tail of lead_runs
    if n_lead >= n_sub and [t for t, _ in lead_runs[n_lead - n_sub :]] == sub_types:
        split_idx = n_lead - n_sub

    # 2. Match numeric runs: align with the last digit run in lead_runs
    if split_idx == -1 and sub_types and sub_types[0] == "D":
        sub_len = len(sub_runs[0][1])
        for start_idx in range(n_lead - 1, -1, -1):
            if lead_runs[start_idx][0] == "D" and len(lead_runs[start_idx][1]) == sub_len:
                split_idx = start_idx
                break

    # 3. Match single letter runs
    if split_idx == -1 and sub_types == ["L"]:
        for start_idx in range(n_lead - 1, -1, -1):
            if lead_runs[start_idx][0] == "L":
                split_idx = start_idx
                break

    # 4. Fallback: match first type from right
    if split_idx == -1 and sub_types:
        for start_idx in range(n_lead - 1, -1, -1):
            if lead_runs[start_idx][0] == sub_types[0]:
                split_idx = start_idx
                break

    if split_idx != -1:
        stem = "".join(val for _, val in lead_runs[:split_idx])
        var0_core = "".join(val for _, val in lead_runs[split_idx:])
    else:
        stem = ""
        var0_core = p0

    common_tag = ""
    for item in reversed(parsed):
        if item["tag"]:
            common_tag = item["tag"]
            break

    m_var0_dig = re.match(r"^([0-9]+)", var0_core)
    prefix_digits = m_var0_dig.group(1) if m_var0_dig else ""
    some_lack_dig = any(item["digits"] == "" and item["letters"] != "" for item in parsed[1:])
    distribute_pre = prefix_digits if (prefix_digits and some_lack_dig) else ""

    last_letters = parsed[-1]["letters"]
    var0_remainder = var0_core[len(prefix_digits) :]
    m_var0_let = re.search(r"([A-Za-z]+)$", var0_remainder)
    var0_has_letters = bool(m_var0_let)
    distribute_suf = last_letters if (last_letters and not var0_has_letters) else ""

    results: list[str] = []
    t0_core = var0_core + (distribute_suf if not var0_has_letters else "")
    t0_tag = parsed[0]["tag"] or common_tag
    results.append(f"{stem}{t0_core}{t0_tag}")

    for item in parsed[1:]:
        dig = item["digits"] or distribute_pre
        let_val = item["letters"] or distribute_suf
        mid = item["middle"]
        tag = item["tag"] or common_tag
        results.append(f"{stem}{dig}{mid}{let_val}{tag}")

    return results


def expand_multivariant_titles(title: str) -> str:
    """Dynamically expand slash/comma-separated variant tokens using structural token runs.

    A single, unified, DRY algorithm that handles any combination of:
    - Compound Hyphenated Suffixes: GS-24AITH21W-T3/21B-T3 -> GS-24AITH21W-T3 GS-24AITH21B-T3
    - Colors: GS-12AITH24W/S-T3 -> GS-12AITH24W-T3 GS-12AITH24S-T3
    - Multi-generation Series: GS-18ZITH1W/2W/3W -> GS-18ZITH1W GS-18ZITH2W GS-18ZITH3W
    - Parenthesized Variants: GS-24PITH (15/17G) -> GS-24PITH15G GS-24PITH17G
    - Multi-Brand Models: DWT-1165/1167 PL -> DWT-1165 DWT-1167 PL
    - Microwave Series: HDG-2312/2313B -> HDG-2312B HDG-2313B
    Safeguarded terms (W/M, D/F, Heat / Cool, 12W/8D, 1/2" pipe) are completely untouched.

    Args:
        title: Raw product title string.

    Returns:
        Expanded title string with distinct virtual model tokens.
    """
    safeguards: list[str] = []

    def mask_fn(m: re.Match[str]) -> str:
        safeguards.append(m.group(0))
        return f"__SAFEGUARD_{len(safeguards) - 1}__"

    clean_title = SAFEGUARD_PATTERN.sub(mask_fn, title)

    # 1. Directly expand parenthesized/bracketed variants: STEM (V1/V2...)
    def paren_repl(m: re.Match[str]) -> str:
        stem = m.group(1).rstrip("-_ ")
        variants = m.group(2)
        parts = [p.strip() for p in re.split(r"\s*[/,]\s*", variants) if p.strip()]
        if len(parts) < 2:
            return m.group(0)
        expanded = distribute_runs(stem, parts)
        return " ".join(expanded)

    clean_title = re.sub(
        r"\b([A-Za-z0-9\-_]+)\s*[\(\[]\s*([A-Za-z0-9\-_]+(?:\s*[/,]\s*[A-Za-z0-9\-_]+)+)\s*[\)\]]",
        paren_repl,
        clean_title,
        flags=re.IGNORECASE,
    )

    # 2. Universal finish / door-type synonym expansion:
    # Ensures 'Glass Door' provides 'GD' and 'Stainless Steel' provides 'INOX'
    clean_title = re.sub(r"\bGLASS\s+DOOR\b", "GLASS DOOR GD", clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r"\bSTAINLESS\s+STEEL\b", "STAINLESS STEEL INOX", clean_title, flags=re.IGNORECASE)

    # 3. Normalize spaced slashes: e.g. "14S /11S" -> "14S/11S"
    clean_title = re.sub(r"([A-Za-z0-9\-_]+)\s*[/,]\s*([A-Za-z0-9\-_]+)", r"\1/\2", clean_title)
    clean_title = re.sub(r"([A-Za-z0-9]+)\s+-\s+([A-Za-z0-9]+/[A-Za-z0-9]+)", r"\1-\2", clean_title)

    # 4. Process tokens containing '/'
    words = clean_title.split()
    expanded_words: list[str] = []
    i = 0
    while i < len(words):
        w = words[i]
        if "/" in w and not w.startswith("__SAFEGUARD_"):
            expanded = expand_slash_word(w)
            if i + 1 < len(words) and is_sku_variant_tag(words[i + 1]):
                trailing_sku_tag = words[i + 1]
                expanded = [f"{x} {trailing_sku_tag}" for x in expanded]
                i += 1
            expanded_words.extend(expanded)
        else:
            expanded_words.append(w)
        i += 1

    result = " ".join(expanded_words)

    # 4. Restore safeguards
    for idx, orig in enumerate(safeguards):
        result = result.replace(f"__SAFEGUARD_{idx}__", orig)

    return result




def tonnage_matches_title(tonnage: str, title_upper: str) -> bool:
    """Check if title contains the specified tonnage phrase (e.g. 1.5 Ton, 1 Ton, 1.0 Ton)."""
    if "." not in tonnage:
        num_pat = rf"(?:{re.escape(tonnage)}(?:\.0)?)"
    elif tonnage.startswith("0."):
        num_pat = rf"(?:0?{re.escape(tonnage[1:])})"
    else:
        num_pat = rf"(?:{re.escape(tonnage)})"
    ton_pattern = rf"\b{num_pat}\s*(?:TON|ΤΟN)\b"
    return bool(re.search(ton_pattern, title_upper))


def reverse_tonnage_matches(kw: str, title_words: set[str], brand: str = "") -> bool:
    """If kw is a tonnage (e.g. '1.5', '1', '2'), check if title contains equivalent capacity code."""
    tonnage_map = get_tonnage_map(brand)
    equiv_codes = tonnage_map.get(kw)
    if equiv_codes:
        return bool(equiv_codes.intersection(title_words))
    return False


def _keyword_match(expanded_title: str, target_keywords: str, brand: str = "") -> bool:
    """Strict all-keyword containment match for name-only products.

    ALL significant keywords from the target must appear in the seller title.
    Implements T3 isolation: non-T3 target rejects T3 listings.
    Supports both Universal (Gree, Haier, Orient, PEL, Kenwood) and Dawlance capacity mappings.

    Args:
        expanded_title: Expanded seller product title.
        target_keywords: Space-separated keyword model (e.g. "AVANTE 30 CLASSIC", "PEARL 18").
        brand: Optional brand name for capacity standard disambiguation.

    Returns:
        True if all keywords match; False otherwise.
    """
    title_upper = expanded_title.upper()
    title_words = set(re.findall(r"[A-Z0-9]+", title_upper))

    target_tokens = [re.sub(r"[^A-Z0-9]", "", t.upper()) for t in target_keywords.split()]
    target_tokens = [t for t in target_tokens if t]
    target_set = set(target_tokens)

    target_brand = brand.strip()
    if not target_brand:
        words = set(re.findall(r"[A-Za-z]+", f"{expanded_title} {target_keywords}".upper()))
        for pfx in BRAND_CAPACITY_SYSTEMS:
            if any(w.startswith(pfx) for w in words):
                target_brand = pfx
                break

    # T3 isolation: if target does NOT contain T3, reject sellers that DO have T3
    has_t3_target = "T3" in target_set
    has_t3_title = "T3" in title_words
    if not has_t3_target and has_t3_title:
        return False

    # Check each keyword
    for kw in target_tokens:
        if kw in title_words:
            continue
        # Capacity code mapping (Dawlance vs Universal brands)
        tonnage = get_capacity_tonnage(kw, target_brand)
        if tonnage and tonnage_matches_title(tonnage, title_upper):
            continue
        # Reverse mapping: tonnage in target -> code in title
        if reverse_tonnage_matches(kw, title_words, target_brand):
            continue
        return False

    return True


def is_strict_model_match(scraped_title: str, target_model: str, brand: str = "") -> bool:
    """Validate that scraped product title strictly matches target model.

    Enforces:
    1. Base target model must be contained in the scraped title.
    2. Zero-hardcoded capacity & series slot invariance.
    3. Strict variant & color isolation.

    Args:
        scraped_title: Raw product title returned by marketplace search API.
        target_model: Target model code from our catalog.

    Returns:
        True if product title strictly matches target variant; False otherwise.
    """
    expanded_title = expand_multivariant_titles(scraped_title)

    clean_target = target_model.strip()

    # Keyword mode detection: if target has no standard model-code token
    # (e.g. "AVANTE 30 CLASSIC" vs "12AITH21W-T3"), use keyword matching.
    # A standard model code is:
    # 1. Alphanumeric compound token of 3+ chars (e.g. 12AITH21W, DWT-1165, HBU-48E)
    # 2. Hyphenated numeric SKU (e.g. 100-1269, 60-50, 120-826)
    # 3. Standalone numeric model code of 3+ digits (e.g. 1060, 183, 184)
    _has_model_code = any(
        (len(t) >= 3 and re.search(r"\d", t) and re.search(r"[A-Za-z]", t))
        or bool(re.search(r"^\d+-\d+$", t))
        or bool(re.search(r"^\d{3,}$", t))
        for t in clean_target.split()
        if t
    )

    if not _has_model_code:
        if _keyword_match(expanded_title, clean_target, brand=brand):
            return True
        return referee_match(clean_target, expanded_title, brand=brand).is_match

    # Normalize alphanumerics for baseline containment
    norm_target = re.sub(r"[^A-Z0-9]", "", clean_target.upper())
    norm_title = re.sub(r"[^A-Z0-9]", "", expanded_title.upper())

    # Auxiliary tag stripping (T3, AAA, AA, PRO, ULTRA, GC, GT, JT) for core base comparison
    tag_pattern = re.compile(r"(?:T3|AAA|AA\+|AA|PRO|ULTRA|GC|GT|JT)+$", re.IGNORECASE)
    base_target = tag_pattern.sub("", norm_target)

    # 1. Structural numeric prefix collision check (e.g. 18 vs 24 vs 12, or 100 vs 120):
    m_target_num = re.match(r"^([0-9]+)([A-Z]+)", base_target)
    if m_target_num:
        target_num = m_target_num.group(1)
        target_series = m_target_num.group(2)
        # If target is not already present, reject titles that have a conflicting capacity number
        if base_target not in norm_title:
            for m_found in re.finditer(rf"([0-9]+){re.escape(target_series)}", norm_title):
                found_num = m_found.group(1)
                if len(found_num) == len(target_num) and found_num != target_num:
                    return False

    # Zero-Tolerance Hardware Door / Finish Collision Guard (GD vs INOX):
    # GD (Glass Door) and INOX (Stainless Steel) are 100% mutually exclusive appliance finishes.
    target_has_gd = bool(re.search(r"\b(?:GD|GLASS\s+DOOR)\b", clean_target, re.IGNORECASE))
    target_has_inox = bool(re.search(r"\b(?:INOX|STAINLESS(?:\s+STEEL)?|S\.S)\b", clean_target, re.IGNORECASE))
    cand_has_gd = bool(re.search(r"\b(?:GD|GLASS\s+DOOR)\b", expanded_title, re.IGNORECASE))
    cand_has_inox = bool(re.search(r"\b(?:INOX|STAINLESS(?:\s+STEEL)?|S\.S)\b", expanded_title, re.IGNORECASE))

    if target_has_gd and cand_has_inox:
        return False
    if target_has_inox and cand_has_gd:
        return False

    # Zero-Tolerance Color Collision Guard:
    # If target specifies a color family, candidate MUST NOT specify an opposing/conflicting color family.
    target_colors = get_all_color_families(clean_target)
    if target_colors:
        cand_colors = get_all_color_families(expanded_title)
        if cand_colors and not target_colors.intersection(cand_colors):
            return False

    # 2. Multi-token model containment (e.g. "DWT-1165 PL" -> "DWT1165" and "PL")
    target_tokens = [re.sub(r"[^A-Z0-9]", "", t.upper()) for t in clean_target.split() if t.strip()]
    # Core SKU tokens MUST contain digits or be substantial series words (>= 4 chars), excluding standalone color words
    core_tokens = [
        t
        for t in target_tokens
        if (any(c.isdigit() for c in t) or len(t) >= 4) and not is_color_token(t)
    ]
    if not core_tokens:
        core_tokens = [t for t in target_tokens if any(c.isdigit() for c in t) or len(t) >= 4]

    # 100% Dynamic Initialism / Acronym Collision Protection (Zero Hardcoded Acronyms):
    # For any 2-letter modifier acronym in target (e.g. SD, DD, FL, TL):
    # Detects if candidate title contains an opposing initialism on the same noun
    # (e.g. target has 'SD', candidate has 'DD' or 'Double Door' where first letter differs).
    target_acronyms = [t for t in target_tokens if len(t) == 2 and t.isalpha()]
    if target_acronyms:
        clean_cand_title = expanded_title
        if brand:
            clean_cand_title = re.sub(rf"\b{re.escape(brand)}\b", "", clean_cand_title, flags=re.IGNORECASE)

        # Split into tokens; tokens containing digits (e.g. 4467, DMB-4467) serve as word boundaries
        raw_tokens = clean_cand_title.split()
        cand_words: list[str | None] = []
        for t in raw_tokens:
            if re.search(r"\d", t):
                cand_words.append(None)
            else:
                w_clean = re.sub(r"[^A-Za-z]", "", t).upper()
                if w_clean:
                    cand_words.append(w_clean)

        for acr in target_acronyms:
            if acr in cand_words or acr in norm_title:
                continue
            a1, a2 = acr[0], acr[1]
            # 1. Collision with standalone 2-letter acronym in title (e.g. DD vs SD, TL vs FL)
            for w in cand_words:
                if w and len(w) == 2 and w[1] == a2 and w[0] != a1:
                    return False
            # 2. Collision with consecutive word phrases (e.g. 'Double Door' vs 'SD', 'Top Load' vs 'FL')
            for i in range(len(cand_words) - 1):
                w1, w2 = cand_words[i], cand_words[i + 1]
                if (
                    w1
                    and w2
                    and len(w1) >= 3
                    and len(w2) >= 3
                    and w2[0] == a2
                    and w1[0] != a1
                    and w1[0] not in ("A", "AN", "THE")
                ):
                    return False

    # Dynamic Brand Verification for pure numeric model stems (e.g. 4467, 105, 538):
    # Pure numbers must match the target brand name OR a brand-initial SKU prefix (e.g. HRF-538, HWM-120, DMB-4467, DWT-1165, GS-12)
    if brand and core_tokens and core_tokens[0].isdigit():
        b_clean = brand.strip().lower()
        title_lower = expanded_title.lower()
        # 1. Full brand name in title (e.g. "haier" or "dawlance")
        has_brand_name = b_clean in title_lower
        # 2. Dynamic brand-initial prefix: Brand initial + 1-3 letters + model number (e.g. HRF-538, HWM-120, DMB-4467, DWT-1165, GS-12)
        brand_sku_pattern = rf"\b{re.escape(b_clean[0])}[a-z]{{1,3}}[- ]?{re.escape(core_tokens[0])}\b"
        has_brand_sku = bool(re.search(brand_sku_pattern, title_lower))
        if not (has_brand_name or has_brand_sku):
            return False

    if len(core_tokens) > 1 and all(t in norm_title for t in core_tokens):
        return True
    if len(core_tokens) == 1 and core_tokens[0] in norm_title and len(core_tokens[0]) >= 3:
        return True

    # 3. Exact base target containment
    if base_target in norm_title:
        return True

    # 4. White / Default Color Fallback:
    # If target is White (ends with 'W'), allow generic base without 'W' ONLY IF no conflicting color code is present
    if base_target.endswith("W"):
        base_no_w = base_target[:-1]
        if base_no_w in norm_title:
            conflict = False
            for w in expanded_title.split():
                norm_w = re.sub(r"[^A-Z0-9]", "", w.upper())
                norm_w_core = tag_pattern.sub("", norm_w)
                idx = norm_w_core.find(base_no_w)
                if idx != -1:
                    rem = norm_w_core[idx + len(base_no_w) :]
                    if rem and rem != "W":
                        conflict = True
                        break
            if not conflict:
                return True

    # 5. Technical slash suffix fallback:
    # If target contains '/' (e.g. 18HE/DC, GN-261/21, 24CE03/KB-01),
    # try matching just the base part before the slash — seller may have omitted the suffix.
    if "/" in clean_target:
        base_before_slash = clean_target.split("/")[0].strip()
        norm_base_slash = re.sub(r"[^A-Z0-9]", "", base_before_slash.upper())
        base_slash_core = tag_pattern.sub("", norm_base_slash)
        if base_slash_core and base_slash_core in norm_title:
            # Verify no capacity collision (reuse structural prefix check)
            m_slash_num = re.match(r"^([0-9]+)([A-Z]+)", base_slash_core)
            if m_slash_num:
                slash_num = m_slash_num.group(1)
                slash_series = m_slash_num.group(2)
                for m_found in re.finditer(rf"([0-9]+){re.escape(slash_series)}", norm_title):
                    found_num = m_found.group(1)
                    if len(found_num) == len(slash_num) and found_num != slash_num:
                        return False
            return True

    return False


def _generate_single_branch_patterns(canonical_name: str, brand: str = "") -> dict[str, list[str]]:
    """Internal helper to generate tiered search query patterns for a single canonical branch.

    Tiers (ADR-001):
    - Tier 1 (Exact Clean): Target SKU with variant tags (e.g. '120-826S6 GC', '50S80EUX').
    - Tier 2 (Bare Alphanumeric Stem): Core model without cosmetic tags/prefixes (e.g. '120-826S6', 'S80EUX').
    - Tier 3 (Permutated Stem): Spaced, glued, and prefixed permutations, plus series tonnage
      (e.g. '120 826S6', '50 S80EUX', 'MAGNA 1.5 TON').

    Args:
        canonical_name: Catalog product name.
        brand: Optional brand name (e.g. 'Haier', 'Gree', 'Dawlance').

    Returns:
        Dictionary mapping 'tier_1', 'tier_2', 'tier_3' to ordered lists of unique search strings.
    """
    clean_name = canonical_name.strip()
    if not clean_name:
        return {"tier_1": [], "tier_2": [], "tier_3": []}

    detected_brand = brand.strip() or clean_name.split()[0]
    search_token, raw_model = extract_search_query_and_model(clean_name, brand=detected_brand)

    tier_1: list[str] = []
    tier_2: list[str] = []
    tier_3: list[str] = []

    def _with_brand(b: str, text: str) -> str:
        b_clean = b.strip()
        t_clean = text.strip()
        if not b_clean:
            return t_clean
        if not t_clean:
            return b_clean
        if t_clean.lower().startswith(b_clean.lower()):
            return t_clean
        return f"{b_clean} {t_clean}"

    def _with_prefix(p: str, text: str, sep: str = " ") -> str:
        p_clean = p.strip().upper()
        t_clean = text.strip()
        if not p_clean or not t_clean:
            return t_clean
        if t_clean.upper().startswith(p_clean):
            return t_clean
        return f"{p_clean}{sep}{t_clean}"

    # Dynamic SKU Prefix Extraction (100% Generic & Brand-Agnostic):
    # Detects any 2-4 letter brand/form-factor acronym directly preceding or hyphenated with the model
    # (e.g. DMB-4467, HRF-538, HWM-120, DWT-1165, GS-12)
    pfx = ""
    num_match = re.search(r"\d+", clean_name)
    if num_match:
        stem_num = num_match.group(0)
        m_pfx = re.search(rf"\b([A-Za-z]{{2,4}})[- ]?{re.escape(stem_num)}", clean_name)
        if m_pfx:
            candidate_pfx = m_pfx.group(1).upper()
            if candidate_pfx.lower() != detected_brand.lower() and candidate_pfx not in NON_SKU_TOKENS:
                pfx = candidate_pfx

    tokens = raw_model.split()
    first_token = tokens[0] if tokens else raw_model

    # Check for TV pattern: 2-digit screen size glued to series (e.g. 50S80EUX, 43P735)
    tv_match = re.match(r"^(\d{2})([A-Z]\w{3,})$", first_token)

    # Check for series + capacity pattern:
    # Trailing capacity: MAGNA 30, AVANTE 15, PEARL 18
    # Leading capacity: 30 MAGNA, 15 INFINITY PRO, 30 SPRINTER / POWERCON
    is_trailing_cap = len(tokens) >= 2 and tokens[-1].isdigit() and len(tokens[-1]) <= 2
    is_leading_cap = len(tokens) >= 2 and tokens[0].isdigit() and len(tokens[0]) <= 2
    is_series_capacity = is_trailing_cap or is_leading_cap

    # Check for refrigerator alphanumeric stem (e.g. 276EBS, 306IDB)
    fridge_match = re.match(r"^(\d{3,})([A-Za-z]+)$", first_token)

    # Auxiliary tag stripping (e.g. -T3, AAA, PRO)
    core_stem, aux_tag = extract_tag(first_token)

    if tv_match:
        screen_size = tv_match.group(1)
        tv_series = tv_match.group(2)
        tier_1.append(first_token)
        if detected_brand:
            tier_1.append(_with_brand(detected_brand, first_token))
        tier_2.append(tv_series)
        tier_3.append(f"{screen_size} {tv_series}")
        if detected_brand:
            tier_3.append(_with_brand(detected_brand, tv_series))

    elif is_series_capacity:
        if is_leading_cap:
            cap_code = tokens[0]
            series_tokens = tokens[1:]
        else:
            cap_code = tokens[-1]
            series_tokens = tokens[:-1]

        # Clean series tokens of non-sku tokens and punctuation
        series_clean = " ".join([t for t in series_tokens if t.upper() not in NON_SKU_TOKENS and t != "+"]).strip()
        # Handle slash-separated alternatives (e.g. Sprinter / Powercon)
        if "/" in series_clean:
            series_options = [s.strip() for s in series_clean.split("/") if s.strip()]
        else:
            series_options = [series_clean] if series_clean else [" ".join(series_tokens)]

        for s_opt in series_options:
            tier_1.append(f"{s_opt} {cap_code}")
            tier_1.append(f"{cap_code} {s_opt}")
            if detected_brand:
                tier_1.append(_with_brand(detected_brand, f"{s_opt} {cap_code}"))
                tier_1.append(_with_brand(detected_brand, s_opt))
            tier_2.append(s_opt)
            if detected_brand:
                tier_2.append(_with_brand(detected_brand, s_opt))

            tonnage = get_capacity_tonnage(cap_code, detected_brand)
            if tonnage:
                tier_3.append(f"{s_opt} {tonnage} TON")
                tier_3.append(f"{s_opt} {tonnage}TON")
                if detected_brand:
                    tier_3.append(_with_brand(detected_brand, f"{s_opt} {tonnage} TON"))
            tier_3.append(f"{s_opt} {cap_code}")
            tier_3.append(f"{cap_code} {s_opt}")

        tier_1.append(raw_model)
        if detected_brand:
            tier_1.append(_with_brand(detected_brand, raw_model))

    else:
        # Standard model codes: washing machines, ACs, refrigerators
        bare_stem = core_stem
        is_numeric_stem = bare_stem.isdigit()

        if detected_brand:
            if pfx:
                # Top priority: Full brand + prefix + model (e.g. Dawlance DMB 4467, Haier HRF 538)
                tier_1.append(_with_brand(detected_brand, _with_prefix(pfx, bare_stem, " ")))
                tier_1.append(_with_brand(detected_brand, _with_prefix(pfx, bare_stem, "-")))
                if stem_num and stem_num != bare_stem:
                    tier_1.append(_with_brand(detected_brand, _with_prefix(pfx, stem_num, " ")))
                    tier_1.append(_with_brand(detected_brand, _with_prefix(pfx, stem_num, "-")))
                tier_1.append(_with_brand(detected_brand, raw_model))
                # Standalone prefix for sellers who omit brand name (e.g. DMB 4467, HRF 538)
                tier_1.append(_with_prefix(pfx, bare_stem, " "))
                if stem_num and stem_num != bare_stem:
                    tier_1.append(_with_prefix(pfx, stem_num, " "))
                    tier_2.append(_with_prefix(pfx, stem_num, "-"))
                    if len(stem_num) >= 4:
                        tier_2.append(stem_num)
                        tier_2.append(_with_brand(detected_brand, stem_num))
                tier_2.append(_with_prefix(pfx, bare_stem, "-"))

            tier_1.append(_with_brand(detected_brand, raw_model))
            tier_1.append(_with_brand(detected_brand, bare_stem))
            tier_2.append(_with_brand(detected_brand, bare_stem))

        # Only allow unbranded queries if stem is complex alphanumeric (e.g. 12AITH21W, 120-826S6)
        # Pure numeric stems (e.g. 4467, 105) must NEVER be queried bare to prevent matching random shoes, clothes, etc.
        if not is_numeric_stem:
            tier_1.append(raw_model)
            if aux_tag and core_stem not in tier_1:
                tier_1.append(core_stem)
            tier_2.append(bare_stem)

        # Tier 3: Spaced, glued, and prefixed permutations
        if "-" in bare_stem:
            spaced = bare_stem.replace("-", " ")
            glued = bare_stem.replace("-", "")
            tier_3.append(spaced)
            tier_3.append(glued)
            if pfx and not bare_stem.upper().startswith(pfx):
                tier_3.append(f"{pfx}-{bare_stem}")
                tier_3.append(f"{pfx} {bare_stem}")
                tier_3.append(f"{pfx} {spaced}")
        elif fridge_match:
            digits = fridge_match.group(1)
            letters = fridge_match.group(2)
            tier_3.append(f"{digits} {letters}")
            tier_3.append(f"{digits}-{letters}")
            if detected_brand:
                tier_3.append(_with_brand(detected_brand, bare_stem))

        if pfx and "-" not in bare_stem and not bare_stem.upper().startswith(pfx):
            tier_3.append(f"{pfx}-{bare_stem}")
            tier_3.append(f"{pfx} {bare_stem}")

        # If AC model ends with color letter (W, B, S, G), also add bare series to tier 3
        m_color_suffix = re.match(r"^(\d+[A-Za-z]+?\d+)[WBSG]$", bare_stem, re.IGNORECASE)
        if m_color_suffix:
            tier_3.append(m_color_suffix.group(1))

        if detected_brand:
            tier_3.append(_with_brand(detected_brand, raw_model))

    # Helper to deduplicate while preserving order
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        res: list[str] = []
        for x in items:
            s = x.strip()
            if s and s not in seen:
                seen.add(s)
                res.append(s)
        return res

    return {
        "tier_1": _dedupe(tier_1),
        "tier_2": _dedupe(tier_2),
        "tier_3": _dedupe(tier_3),
    }


def generate_search_patterns(canonical_name: str, brand: str = "") -> dict[str, list[str]]:
    """Generate tiered search query patterns for multi-pattern waterfall candidate retrieval.

    Tiers (ADR-001):
    - Tier 1 (Exact Clean): Target SKU with variant tags (e.g. '120-826S6 GC', '50S80EUX').
    - Tier 2 (Bare Alphanumeric Stem): Core model without cosmetic tags/prefixes (e.g. '120-826S6', 'S80EUX').
    - Tier 3 (Permutated Stem): Spaced, glued, and prefixed permutations, plus series tonnage
      (e.g. '120 826S6', '50 S80EUX', 'MAGNA 1.5 TON').

    Args:
        canonical_name: Catalog product name.
        brand: Optional brand name (e.g. 'Haier', 'Gree', 'Dawlance').

    Returns:
        Dictionary mapping 'tier_1', 'tier_2', 'tier_3' to ordered lists of unique search strings.
    """
    clean_name = canonical_name.strip()
    if not clean_name:
        return {"tier_1": [], "tier_2": [], "tier_3": []}

    branches = expand_cartesian_branches(clean_name)
    if len(branches) > 1:
        t1: list[str] = []
        t2: list[str] = []
        t3: list[str] = []
        for b in branches:
            res = _generate_single_branch_patterns(b, brand=brand)
            t1.extend(res.get("tier_1", []))
            t2.extend(res.get("tier_2", []))
            t3.extend(res.get("tier_3", []))
        return {
            "tier_1": list(dict.fromkeys(t1)),
            "tier_2": list(dict.fromkeys(t2)),
            "tier_3": list(dict.fromkeys(t3)),
        }

    return _generate_single_branch_patterns(clean_name, brand=brand)


ROOT_COLORS: set[str] = {
    "WHITE",
    "BLACK",
    "GREY",
    "GRAY",
    "SILVER",
    "RED",
    "BLUE",
    "GREEN",
    "GOLD",
    "BROWN",
    "PINK",
    "PURPLE",
    "MILKY",
    "DARK",
    "MAROON",
    "BURGUNDY",
}


def extract_product_slots(title: str, brand: str = "") -> ProductSlots:
    """Factor a catalog target or marketplace title into 4 orthogonal slots.

    Slots (ADR-002):
    1. anchor: Primary numeric or alphanumeric SKU run.
    2. series: Extracted dynamically via CSV metadata subtraction (Zero Static Noise Dict).
    3. guarded_facets: T3, capacity, tub_series, color_family, color_raw.
    4. residuals: Extra marketing/cosmetic tokens ('GC', 'Glass Door', 'Pillow Drum').

    Args:
        title: Catalog or marketplace product title.
        brand: Optional brand name from catalog metadata.

    Returns:
        Structured ProductSlots instance.
    """
    clean_title = normalize_technical_slashes(title.strip())
    detected_brand = brand.strip() or (clean_title.split()[0] if clean_title else "")
    search_token, raw_model = extract_search_query_and_model(clean_title, brand=detected_brand)

    tokens = raw_model.split()
    first_token = tokens[0] if tokens else raw_model

    # 1. Anchor Extraction
    anchor = ""
    all_known_cap_codes = set(UNIVERSAL_CAPACITY_TO_TONNAGE.keys()).union(
        *(m.keys() for m in BRAND_CAPACITY_SYSTEMS.values())
    )
    if (
        re.search(r"\d", first_token)
        and not is_dimension_or_spec_token(first_token)
        and not (first_token.isdigit() and first_token in all_known_cap_codes)
    ):
        core_stem, _ = extract_tag(first_token)
        anchor = core_stem

    # Enhanced anchor detection for compound models (e.g. 24 HDZ, 48 EDC, 18 HE-DC, HMO-45200, HAF-50MB, 32 D2)
    if not anchor:
        sub_anchor = clean_marketplace_noise(clean_title)
        if detected_brand:
            sub_anchor = re.sub(
                rf"^(?:{re.escape(detected_brand)}|{re.escape(detected_brand[:3]) if len(detected_brand) >= 4 else '---'})[\s\-_,:]*",
                "",
                sub_anchor,
                flags=re.IGNORECASE,
            )
        m_pfx_stem = re.search(r"\b([A-Za-z]{2,4})[-_ ]?(\d+(?:-\d+)?)[-_ ]?([A-Za-z0-9]*)\b", sub_anchor)
        if m_pfx_stem:
            pfx = m_pfx_stem.group(1).upper()
            num = m_pfx_stem.group(2)
            suf = (m_pfx_stem.group(3) or "").upper()
            suf = re.sub(r"[()]", "", suf).strip()
            if num.isdigit() and len(num) <= 2 and (not suf or pfx in GENUINE_SUB_SERIES_TOKENS or pfx in {"SPLIT", "AUTO", "AWM"}):
                pass
            elif suf and len(suf) <= 8 and suf not in {"INVERTER", "SERIES", "NORMAL"}:
                anchor = f"{pfx}-{num}{suf}"
            elif not (num.isdigit() and len(num) <= 2):
                anchor = f"{pfx}-{num}"
        else:
            m_alpha = re.search(r"\b(\d+[A-Za-z]+[A-Za-z0-9\-]*|[A-Za-z]+\d+[A-Za-z0-9\-]*)\b", sub_anchor)
            if m_alpha and not is_dimension_or_spec_token(m_alpha.group(1)):
                anchor = m_alpha.group(1).upper()
            else:
                m_cap_ser = re.search(r"\b(\d{1,2})\s+([A-Za-z0-9]+(?:-[A-Za-z0-9]+)?)\b", sub_anchor)
                if (
                    m_cap_ser
                    and m_cap_ser.group(2).upper() not in NON_SKU_TOKENS
                    and not is_sku_variant_tag(m_cap_ser.group(2))
                ):
                    w = m_cap_ser.group(2)
                    vowels = len(re.findall(r"[AEIOU]", w.upper()))
                    is_series_word = (len(w) >= 4 and vowels >= 2) or w.upper() in GENUINE_SUB_SERIES_TOKENS or w.upper() in {"INVERTER", "SERIES", "NORMAL"}
                    if not is_series_word:
                        anchor = f"{m_cap_ser.group(1)}{w.upper()}"

    # 2. Guarded Facets Extraction
    # 2a. T3
    t3_match = bool(re.search(r"(?:-|\b)T3\b", clean_title, re.IGNORECASE))
    is_non_ac = bool(
        re.search(
            r"\b(?:CU\s*FT|CU\.FT|CFT|REFRIGERATOR|FRIDGE|WASHER|WASHING|DISPENSER|OVEN|MICROWAVE)\b",
            clean_title,
            re.IGNORECASE,
        )
    )
    has_ac_keyword = bool(
        re.search(r"\b(?:AC|SPLIT|INVERTER|INV|T3|TON|ΤΟN)\b", clean_title, re.IGNORECASE)
    )
    has_ac_cap_code = any(t in all_known_cap_codes for t in clean_title.split())
    is_ac = (has_ac_keyword or has_ac_cap_code) and not is_non_ac
    t3 = t3_match if (t3_match or is_ac) else None

    # 2b. IoT / Smart connectivity
    iot = True if re.search(r"\b(?:IOT|SMART|WIFI)\b", clean_title, re.IGNORECASE) else None

    # 2c. Operating Mode: Cool Only vs Heat & Cool
    cool_only = True if re.search(r"\b(?:COOL\s+ONLY|COOLING\s+ONLY|ONLY\s+COOL)\b", clean_title, re.IGNORECASE) else None
    heat_and_cool = True if re.search(r"\b(?:HEAT\s*(?:&|AND|/)\s*COOL|H\s*&\s*C|H/C)\b", clean_title, re.IGNORECASE) else None

    # 2d. Capacity
    capacity: str | None = None
    # Screen size (only for displays or explicit INCH / " unit)
    is_display = bool(
        re.search(
            r"\b(?:LED|TV|TELEVISION|MONITOR|DISPLAY|SMART\s*TV|OLED|QLED|UHD|FHD)\b",
            clean_title,
            re.IGNORECASE,
        )
    )
    m_screen = re.search(r"\b(\d{2})\s*(?:INCH|\"|\')\b", clean_title, re.IGNORECASE)
    if m_screen:
        capacity = f"{m_screen.group(1)}INCH"
    elif is_display and anchor and re.match(r"^(\d{2})[A-Z]\w{3,}$", anchor):
        capacity = f"{anchor[:2]}INCH"
    else:
        # Refrigerator CFT (Cubic Feet)
        m_cft = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:CU\s*FT|CU\.FT|CFT)\b", clean_title, re.IGNORECASE)
        if m_cft:
            capacity = f"{int(float(m_cft.group(1)))}CFT"
        else:
            # Washing machine KG
            m_kg = re.search(r"\b(\d+(?:\.\d+)?)\s*KG\b", clean_title, re.IGNORECASE)
            if m_kg:
                capacity = f"{int(float(m_kg.group(1)))}KG"
            elif anchor and re.match(r"^(\d{2,3})-\d+", anchor):
                num_val = int(re.match(r"^(\d{2,3})-\d+", anchor).group(1))
                capacity = f"{num_val // 10}KG"
            elif not is_non_ac:
                # AC Tonnage
                m_ton = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:TON|ΤΟN)\b", clean_title, re.IGNORECASE)
                if m_ton:
                    capacity = f"{m_ton.group(1)}T"
                elif is_ac:
                    # AC capacity codes
                    for t in tokens + clean_title.split():
                        t_c = t.strip("-_., \"'")
                        ton = get_capacity_tonnage(t_c, detected_brand)
                        if ton:
                            capacity = f"{ton}T"
                            break
                    if not capacity and anchor:
                        m_anc_cap = re.match(r"^(\d{2})[A-Za-z]", anchor)
                        if m_anc_cap:
                            ton = get_capacity_tonnage(m_anc_cap.group(1), detected_brand)
                            if ton:
                                capacity = f"{ton}T"

    # 2e. Tub Series
    m_tub = re.search(r"\b\d+-\d+(WB|GB)\b|\b(WB|GB)\b", clean_title, re.IGNORECASE)
    tub_series = (m_tub.group(1) or m_tub.group(2)).upper() if m_tub else None

    # 2f. Color Family & Raw
    color_fam, color_raw = normalize_color(clean_title, anchor=anchor)

    # 2g. Hardware Door Finish (GD vs INOX)
    door_finish = None
    if re.search(r"\b(?:GD|GLASS\s+DOOR)\b", clean_title, re.IGNORECASE):
        door_finish = "GD"
    elif re.search(r"\b(?:INOX|STAINLESS(?:\s+STEEL)?|S\.S)\b", clean_title, re.IGNORECASE):
        door_finish = "INOX"

    door_type = None
    if re.search(r"\b(?:SD|SINGLE\s+DOOR)\b", clean_title, re.IGNORECASE):
        door_type = "SD"
    elif re.search(r"\b(?:DD|DOUBLE\s+DOOR)\b", clean_title, re.IGNORECASE):
        door_type = "DD"

    # 2h. Inverter Mode
    is_inverter = None
    if re.search(r"\b(?:NON[\s\-]*INVERTER|FIX(?:ED)?\s*SPEED|CONVENTIONAL)\b", clean_title, re.IGNORECASE):
        is_inverter = False
    elif re.search(r"\b(?:INVERTER|INV|DC\s*INVERTER)\b", clean_title, re.IGNORECASE):
        is_inverter = True

    # 2i. Dynamic Post-Model Code & Category 2 Modifiers Engine
    # Dynamically grabs the code right after the model and across remaining tokens
    # (e.g. ES, ES8, T3, T4, UV, WIFI, IOT) with ZERO hardcoding.
    # RULE:
    # - If token in CATEGORY_1_DIRECT_MATCH_MODIFIERS -> Category 1 (Direct match when omitted)
    # - Else -> Category 2 (Exact match if present, fallback if omitted, collision if extra/different)
    caps: set[str] = set()

    # 1. Connectivity keywords across title
    if re.search(r"\b(?:WIFI|WI-FI)\b", clean_title, re.IGNORECASE):
        caps.add("WIFI")
    if re.search(r"\b(?:IOT|SMART)\b", clean_title, re.IGNORECASE):
        caps.add("IOT")

    # 2. Extract candidate modifier tokens:
    candidate_tokens: list[str] = []

    # A. Hyphenated trailing modifier attached directly to the model/anchor (e.g. 18AITH24S-T3 -> T3, DWT-11467-ES -> ES)
    if anchor and "-" in anchor:
        anc_parts = anchor.split("-")
        if len(anc_parts) > 1 and any(re.search(r"\d", p) for p in anc_parts[:-1]) and is_sku_variant_tag(anc_parts[-1]):
            candidate_tokens.append(anc_parts[-1].upper())

    # B. Trailing tokens immediately following the model in raw_model:
    # If the first token is a 1-2 digit capacity code (e.g. '24 HDZ', '32 D2', '50 MB'),
    # the compound model is tokens[0] + tokens[1], and trailing modifiers start at tokens[2:]!
    post_model_tokens = tokens[2:] if (len(tokens) >= 2 and tokens[0].isdigit() and len(tokens[0]) <= 2) else tokens[1:]
    for t in post_model_tokens:
        t_clean = t.strip("-.,_ \"'/").upper()
        if is_sku_variant_tag(t_clean):
            candidate_tokens.append(t_clean)

    # C. Search code right after the model AND across all remaining tokens in clean_title:
    post_words: list[str] = []
    if anchor:
        anc_variants = [anchor]
        if "-" in anchor:
            anc_variants.extend([anchor.replace("-", " "), anchor.replace("-", "")])
        # Find position of anchor in clean_title
        found_pos = -1
        for v in anc_variants:
            idx = clean_title.upper().find(v.upper())
            if idx != -1:
                found_pos = idx + len(v)
                break
        if found_pos != -1:
            post_anchor = clean_title[found_pos:]
            post_words = post_anchor.split()
        else:
            # Fallback: check if numeric stem exists in title
            m_stem = re.search(r"\d{3,}", anchor)
            if m_stem:
                idx = clean_title.find(m_stem.group(0))
                if idx != -1:
                    post_anchor = clean_title[idx + len(m_stem.group(0)) :]
                    post_words = post_anchor.split()

    for w in post_words:
        w_clean = w.strip("()[]-.,_ \"'/").upper()
        if is_sku_variant_tag(w_clean):
            candidate_tokens.append(w_clean)
        elif "-" in w:
            w_sub = w.split("-")[-1].strip("()[]-.,_ \"'/").upper()
            if is_sku_variant_tag(w_sub):
                candidate_tokens.append(w_sub)

    # D. Glued trailing code on numeric stem >= 3 digits (e.g. DWT11467ES -> ES, 11467ES8 -> ES8)
    m_glued_stem = re.search(r"\b[A-Za-z]{0,4}(\d{3,})([A-Za-z]{2,4})\b", clean_title)
    if m_glued_stem:
        glued_tag = m_glued_stem.group(2).upper()
        if is_sku_variant_tag(glued_tag):
            candidate_tokens.append(glued_tag)

    # Tokens managed by dedicated orthogonal slots or soft styling residuals:
    dedicated_orthogonal_slots = {"GD", "INOX", "DD", "INVERTER", "INV", "WB", "GB", "GC", "FH", "CHROME", "LVS"}

    anc_core, _ = extract_tag(anchor) if anchor else ("", "")
    norm_anc = anc_core.replace("-", "").upper() if anc_core else ""

    # Distribute candidate tokens into Category 1 vs Category 2:
    for tok in candidate_tokens:
        if tok in dedicated_orthogonal_slots:
            continue
        if norm_anc and tok in norm_anc:
            continue
        if tok in CATEGORY_1_DIRECT_MATCH_MODIFIERS:
            # Category 1 modifier (strictly 'SD') -> Handled by Category 1 direct-match logic
            continue
        # Category 2: All other hardware/variant codes go here dynamically (e.g. ES, ES8, T3, T4, UV, S6)!
        caps.add(tok)

    guarded = GuardedFacets(
        t3=t3,
        iot=iot,
        capacity=capacity,
        tub_series=tub_series,
        color_family=color_fam,
        color_raw=color_raw,
        door_finish=door_finish,
        cool_only=cool_only,
        heat_and_cool=heat_and_cool,
        door_type=door_type,
        is_inverter=is_inverter,
        capabilities=caps,
    )

    # 3. Soft Residual Modifiers
    residuals: list[str] = []
    m_gc = re.search(
        r"\b(?:GC|GLASS\s+DOOR|CLEAR\s+LID|PILLOW\s+DRUM)\b", clean_title, re.IGNORECASE
    )
    if m_gc:
        residuals.append(m_gc.group(0).upper())
    if anchor and anchor in clean_title:
        post_anchor = clean_title.split(anchor, 1)[1]
        for t in post_anchor.split():
            t_c = t.strip("-.,_ \"'")
            if is_sku_variant_tag(t_c) and t_c.upper() not in residuals:
                residuals.append(t_c.upper())
    elif anchor:
        for t in tokens[1:]:
            if is_sku_variant_tag(t) and t.upper() not in residuals:
                residuals.append(t.upper())
    residuals = list(dict.fromkeys(residuals))

    # 4. Dynamic Series Extraction via CSV Metadata Subtraction
    sub = clean_title
    sub = clean_marketplace_noise(sub)
    # Strip parenthetical annotations after extracting color/finish (e.g. "(Milky White Textured)")
    sub = re.sub(r"\([^)]*\)", " ", sub)
    if detected_brand:
        sub = re.sub(rf"\b{re.escape(detected_brand)}\b", " ", sub, flags=re.IGNORECASE)
    sub = CATEGORY_PATTERNS.sub(" ", sub)
    sub = re.sub(r"\b(?:\d+(?:\.\d+)?\s*(?:CU\s*FT|CU\.FT|CFT|CU))\b", " ", sub, flags=re.IGNORECASE)
    sub = re.sub(r"\b(?:SINGLE\s*TUB)\b", " ", sub, flags=re.IGNORECASE)
    # Dynamically strip any 2-4 letter brand/form-factor SKU prefix attached to anchor
    if anchor:
        sub = re.sub(rf"\b[A-Za-z]{{2,4}}[- ]?{re.escape(anchor)}\b", " ", sub, flags=re.IGNORECASE)
        sub = re.sub(rf"\b{re.escape(anchor)}\b", " ", sub, flags=re.IGNORECASE)
        anchor_unhyphenated = anchor.replace("-", "")
        sub = re.sub(rf"\b{re.escape(anchor_unhyphenated)}[A-Za-z0-9]*\b", " ", sub, flags=re.IGNORECASE)
        for part in re.findall(r"[A-Za-z]+|\d+", anchor):
            if part:
                sub = re.sub(rf"\b{re.escape(part)}\b", " ", sub, flags=re.IGNORECASE)
        if "-" in anchor:
            anchor_prefix = anchor.split("-")[0]
            if len(anchor_prefix) <= 4:
                sub = re.sub(rf"\b{re.escape(anchor_prefix)}\b", " ", sub, flags=re.IGNORECASE)
        stem = anchor.split("-")[-1]
        if stem.isdigit() and len(stem) >= 3:
            sub = re.sub(rf"\b{re.escape(stem)}[A-Za-z0-9]*\b", " ", sub, flags=re.IGNORECASE)
    # Strip any hyphenated prefix-number codes (e.g. HWM-120, DWT-1165, GS-12)
    sub = re.sub(r"\b[A-Za-z]{2,4}-\d+", " ", sub)
    sub = re.sub(
        r"\b(?:NON[\s\-]*INVERTER|FIX(?:ED)?\s*SPEED|CONVENTIONAL|T3|INVERTER|INV|4K|SMART|WIFI|WI-FI|IOT|FHD|HD|SPLIT|AC|AUTO|TOP\s+LOAD|FRONT\s+LOAD|AAA\+|AA\+|A\+{1,3}|AAA|AA)\b",
        " ",
        sub,
        flags=re.IGNORECASE,
    )
    if tub_series:
        sub = re.sub(rf"\b{re.escape(tub_series)}\b", " ", sub, flags=re.IGNORECASE)
    for r in residuals:
        sub = re.sub(rf"\b{re.escape(r)}\b", " ", sub, flags=re.IGNORECASE)
    for c in caps:
        sub = re.sub(rf"\b{re.escape(c)}\b", " ", sub, flags=re.IGNORECASE)
    for c1 in CATEGORY_1_DIRECT_MATCH_MODIFIERS:
        sub = re.sub(rf"\b{re.escape(c1)}\b", " ", sub, flags=re.IGNORECASE)
    # Strip all color tokens
    sub_words = [
        tok for tok in sub.split()
        if tok.upper() not in ALL_COLOR_WORDS and not is_color_token(tok)
    ]
    sub = " ".join(sub_words)
    if anchor:
        sub = re.sub(rf"\b{re.escape(anchor)}\b", " ", sub, flags=re.IGNORECASE)
    # Strip any standalone numbers that match capacity (e.g. 30, 18, 12)
    if capacity:
        cap_num = re.sub(r"[^0-9\.]", "", capacity)
        if cap_num:
            sub = re.sub(rf"\b{re.escape(cap_num)}\b", " ", sub)
    for code in all_known_cap_codes:
        sub = re.sub(rf"\b{code}\b", " ", sub)

    series_tokens = [tok if tok == "/" else tok.strip("-.,_ \"'+") for tok in sub.split()]
    series_tokens = [
        tok
        for tok in series_tokens
        if tok and (tok == "/" or (tok.upper() not in NON_SKU_TOKENS and len(tok) > 1 and not tok.isdigit()))
    ]
    series = " ".join(series_tokens).strip()
    series = re.sub(r"\s*/\s*", " / ", series).strip(" /")

    return ProductSlots(
        anchor=anchor,
        series=series,
        guarded_facets=guarded,
        residuals=residuals,
    )


def referee_match(
    target: ProductSlots | str,
    candidate_title: str,
    brand: str = "",
) -> MatchDecision:
    """Evaluate candidate marketplace listing against target product slots.

    Decision Principle (ADR-002):
    Decision = Anchor Match AND NOT(Any Guarded Facet Collision)

    Returns:
        MatchDecision containing boolean verdict and detailed human-readable audit reason.
    """
    if isinstance(target, str):
        branches = expand_cartesian_branches(target)
        if len(branches) > 1:
            decs = [referee_match(b, candidate_title, brand=brand) for b in branches]
            for dec in decs:
                if dec.is_match:
                    return dec
            for dec in decs:
                if any(x in dec.reason for x in ("mismatch", "collision")):
                    return dec
            return decs[0]

    target_slots = extract_product_slots(target, brand=brand) if isinstance(target, str) else target
    cand_slots = extract_product_slots(candidate_title, brand=brand)

    # 1. Zero-Tolerance Hardware Tub Series Guard (e.g. WB vs GB)
    if (
        target_slots.guarded_facets.tub_series
        and cand_slots.guarded_facets.tub_series
        and target_slots.guarded_facets.tub_series != cand_slots.guarded_facets.tub_series
    ):
        return MatchDecision(
            is_match=False,
            reason=(
                f"Hardware tub mismatch: {target_slots.guarded_facets.tub_series} "
                f"vs {cand_slots.guarded_facets.tub_series}"
            ),
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # 1b. Zero-Tolerance Hardware Finish / Door Guard (GD vs INOX)
    if (
        target_slots.guarded_facets.door_finish
        and cand_slots.guarded_facets.door_finish
        and target_slots.guarded_facets.door_finish != cand_slots.guarded_facets.door_finish
    ):
        return MatchDecision(
            is_match=False,
            reason=(
                f"Hardware finish collision: target is {target_slots.guarded_facets.door_finish} "
                f"vs candidate {cand_slots.guarded_facets.door_finish}"
            ),
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # Category 2 Rule for Hardware Finish (GD / INOX):
    # 1. Target specifies finish (GD or INOX), but candidate omitted it:
    # "mila toh lelon leken nahi mila toh fallback"
    if (
        target_slots.guarded_facets.door_finish
        and not cand_slots.guarded_facets.door_finish
        and target_slots.guarded_facets.door_finish not in CATEGORY_1_DIRECT_MATCH_MODIFIERS
    ):
        missing_finish = target_slots.guarded_facets.door_finish
        return MatchDecision(
            is_match=False,
            reason=f"Hardware finish omitted ({missing_finish} mismatch): Target specifies {missing_finish} but candidate does not",
            target_slots=target_slots,
            candidate_slots=cand_slots,
            is_base_match=True,
            missing_modifier=missing_finish,
        )

    # 1b2. Zero-Tolerance Door Structure Guard (SD vs DD)
    if (
        target_slots.guarded_facets.door_type
        and cand_slots.guarded_facets.door_type
        and target_slots.guarded_facets.door_type != cand_slots.guarded_facets.door_type
    ):
        return MatchDecision(
            is_match=False,
            reason=(
                f"Door structure collision: target is {target_slots.guarded_facets.door_type} "
                f"vs candidate {cand_slots.guarded_facets.door_type}"
            ),
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # 1b3. Zero-Tolerance Inverter Mode Guard (Inverter vs Non-Inverter / Fixed Speed)
    if (
        target_slots.guarded_facets.is_inverter is not None
        and cand_slots.guarded_facets.is_inverter is not None
        and target_slots.guarded_facets.is_inverter != cand_slots.guarded_facets.is_inverter
    ):
        t_inv = "Inverter" if target_slots.guarded_facets.is_inverter else "Non-Inverter"
        c_inv = "Inverter" if cand_slots.guarded_facets.is_inverter else "Non-Inverter"
        return MatchDecision(
            is_match=False,
            reason=f"Inverter mode collision: target is {t_inv} vs candidate {c_inv}",
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # Category 2 Rule for Inverter:
    # If target explicitly specifies INVERTER, but candidate omitted it:
    if target_slots.guarded_facets.is_inverter is True and cand_slots.guarded_facets.is_inverter is None:
        return MatchDecision(
            is_match=False,
            reason="Hardware capability omitted (INVERTER mismatch): Target specifies INVERTER but candidate does not",
            target_slots=target_slots,
            candidate_slots=cand_slots,
            is_base_match=True,
            missing_modifier="INVERTER",
        )

    # 1c. Zero-Tolerance Operating Mode Guard (Cool Only vs Heat & Cool)
    if target_slots.guarded_facets.cool_only and cand_slots.guarded_facets.heat_and_cool:
        return MatchDecision(
            is_match=False,
            reason="Operating mode collision: Target is Cool Only vs Candidate is Heat & Cool",
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )
    if target_slots.guarded_facets.heat_and_cool and cand_slots.guarded_facets.cool_only:
        return MatchDecision(
            is_match=False,
            reason="Operating mode collision: Target is Heat & Cool vs Candidate is Cool Only",
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # 2. Anchor Model Check
    if target_slots.anchor:
        norm_t = re.sub(r"[^A-Z0-9]", "", target_slots.anchor.upper())
        norm_cand_title = re.sub(r"[^A-Z0-9]", "", candidate_title.upper())

        matched_anchor = False
        if cand_slots.anchor:
            norm_c = re.sub(r"[^A-Z0-9]", "", cand_slots.anchor.upper())
            if norm_t == norm_c or norm_t in norm_c or norm_c in norm_t or norm_t in norm_cand_title:
                matched_anchor = True
            else:
                t_stem = re.search(r"\d{3,}", norm_t)
                c_stem = re.search(r"\d{3,}", norm_c)
                if t_stem and c_stem and t_stem.group(0) == c_stem.group(0):
                    matched_anchor = True
        elif norm_t in norm_cand_title:
            matched_anchor = True
        else:
            t_stem = re.search(r"\d{3,}", norm_t)
            if t_stem and t_stem.group(0) in norm_cand_title:
                matched_anchor = True

        # Dynamic Brand-Initial Prefix Synthesis check:
        # e.g. target anchor '11LF' with brand 'Haier' matches candidate listing with 'HRF-11LF'
        # e.g. target anchor '13HFN' with brand 'Haier' matches candidate listing with 'HSU-13HFN'
        if not matched_anchor and brand:
            b_init = brand[0].upper()
            if re.search(rf"{b_init}[A-Z]{{1,3}}{re.escape(norm_t)}", norm_cand_title):
                matched_anchor = True
            elif cand_slots.anchor:
                norm_c = re.sub(r"[^A-Z0-9]", "", cand_slots.anchor.upper())
                if norm_t.startswith(b_init) and norm_c.startswith(b_init):
                    core_t = re.sub(r"^[A-Z]{2,4}", "", norm_t)
                    core_c = re.sub(r"^[A-Z]{2,4}", "", norm_c)
                    if core_t and core_c and (core_t == core_c or core_t in core_c or core_c in core_t):
                        matched_anchor = True

        # Variant tag collision check (e.g. 50MB vs 50DB)
        if cand_slots.anchor:
            norm_c = re.sub(r"[^A-Z0-9]", "", cand_slots.anchor.upper())
            if len(norm_t) >= 4 and len(norm_c) >= 4:
                suf_t = norm_t[-2:]
                suf_c = norm_c[-2:]
                if suf_t.isalpha() and suf_c.isalpha() and norm_t[:2] == norm_c[:2] and suf_t != suf_c:
                    return MatchDecision(
                        is_match=False,
                        reason=f"Variant tag collision: {norm_t} vs {norm_c}",
                        target_slots=target_slots,
                        candidate_slots=cand_slots,
                    )

        if not matched_anchor:
            return MatchDecision(
                is_match=False,
                reason=f"Anchor model mismatch: {target_slots.anchor} vs {cand_slots.anchor or candidate_title}",
                target_slots=target_slots,
                candidate_slots=cand_slots,
            )

    # 2. Dynamic Series and Sub-series Check (Pure Token-Based Set Logic, Zero Hardcoding)
    if target_slots.series:
        # Check if target series has slash-separated alternatives (e.g. "SPRINTER / POWERCON")
        if "/" in target_slots.series:
            alternatives = [s.strip().upper() for s in target_slots.series.split("/") if s.strip()]
        else:
            alternatives = [target_slots.series.upper()]

        cand_clean = clean_marketplace_noise(candidate_title)
        cand_clean = re.sub(r"\([^)]*\)", " ", cand_clean)
        cand_words = set(re.findall(r"[A-Z0-9]+", cand_clean.upper()))

        matched_alt = None
        for alt in alternatives:
            alt_words = set(alt.upper().split())
            if not (alt_words - cand_words):
                matched_alt = alt
                break

        # Soft Feature & Styling Optionality Rule:
        # If target has a unique numeric stem of >= 4 digits (e.g. 9173, 91999) or anchor is matched,
        # AND candidate did not specify an opposing/conflicting series (cand_slots.series is empty),
        # AND candidate anchor does not contain extra unmatched variant letters (e.g. LFACCE),
        # allow match where seller omitted the soft styling tag (Chrome, FH, LVS).
        if not matched_alt:
            is_unique_stem = target_slots.anchor and bool(re.search(r"\d{4,}", target_slots.anchor))
            extra_ok = False
            if is_unique_stem and not cand_slots.series:
                target_all_text = f"{target_slots.anchor} {target_slots.series} {target_slots.guarded_facets.tub_series or ''} {' '.join(target_slots.residuals)}".upper()
                target_all_chars = re.sub(r"[^A-Z0-9]", "", target_all_text)
                cand_anchor_norm = re.sub(r"[^A-Z0-9]", "", cand_slots.anchor.upper()) if cand_slots.anchor else ""
                t_stem_match = re.search(r"\d{4,}", target_slots.anchor)
                stem_val = t_stem_match.group(0) if t_stem_match else ""
                extra_cand_letters = cand_anchor_norm.replace(stem_val, "")
                if brand:
                    b_init = brand[0].upper()
                    extra_cand_letters = re.sub(rf"^{re.escape(b_init)}[A-Z]{{0,3}}", "", extra_cand_letters)
                extra_ok = not extra_cand_letters or all(c in target_all_chars for c in extra_cand_letters)

            if is_unique_stem and not cand_slots.series and extra_ok:
                matched_alt = alternatives[0]
            else:
                return MatchDecision(
                    is_match=False,
                    reason=f"Missing required series tokens for any alternative in '{target_slots.series}'",
                    target_slots=target_slots,
                    candidate_slots=cand_slots,
                )

        target_sub_tokens = set(matched_alt.split()) & GENUINE_SUB_SERIES_TOKENS
        cand_sub_tokens = set(cand_slots.series.upper().split()) & GENUINE_SUB_SERIES_TOKENS
        extra_sub = cand_sub_tokens - target_sub_tokens
        if extra_sub:
            return MatchDecision(
                is_match=False,
                reason=f"Sub-series mismatch: candidate has extra series token(s) {', '.join(sorted(extra_sub))} not in target '{matched_alt}'",
                target_slots=target_slots,
                candidate_slots=cand_slots,
            )

    # 3. Guarded Facets Zero-Tolerance Checks
    # 3a. Generic Category 2 Hardware Capabilities & Modifiers Engine (Zero Hardcoding, Pure Dynamic Set Logic)
    target_caps = target_slots.guarded_facets.capabilities
    cand_caps = cand_slots.guarded_facets.capabilities

    # Collision 1: Candidate has extra hardware capabilities/modifiers that target lacks -> Hard mismatch
    # (Cannot reprice baseline target against upgraded listing with extra physical components)
    extra_cand_caps = cand_caps - target_caps
    if extra_cand_caps:
        extra_str = ", ".join(sorted(extra_cand_caps))
        return MatchDecision(
            is_match=False,
            reason=f"Hardware capability mismatch ({extra_str} mismatch): Candidate has extra capability {extra_str} not present in target",
            target_slots=target_slots,
            candidate_slots=cand_slots,
            is_base_match=False,
        )

    # Fallback 2: Target specifies Category 2 modifiers that candidate omitted -> Valid base-model fallback
    missing_target_caps = target_caps - cand_caps
    if missing_target_caps:
        missing_str = ", ".join(sorted(missing_target_caps))
        return MatchDecision(
            is_match=False,
            reason=f"Hardware capability omitted ({missing_str} mismatch): Target specifies {missing_str} but candidate does not",
            target_slots=target_slots,
            candidate_slots=cand_slots,
            is_base_match=True,
            missing_modifier=missing_str,
        )

    # 3b. Capacity / Screen Size Guard
    if target_slots.guarded_facets.capacity and cand_slots.guarded_facets.capacity:

        def _norm_cap(c: str) -> float | str:
            val_str = re.sub(r"[^0-9\.]", "", c)
            try:
                return float(val_str)
            except (ValueError, TypeError):
                return val_str

        if _norm_cap(target_slots.guarded_facets.capacity) != _norm_cap(
            cand_slots.guarded_facets.capacity
        ):
            return MatchDecision(
                is_match=False,
                reason=(
                    f"Capacity / screen size mismatch: {target_slots.guarded_facets.capacity} "
                    f"vs {cand_slots.guarded_facets.capacity}"
                ),
                target_slots=target_slots,
                candidate_slots=cand_slots,
            )

    # 3c. Color Family Collision Guard
    if (
        target_slots.guarded_facets.color_family
        and cand_slots.guarded_facets.color_family
        and target_slots.guarded_facets.color_family != cand_slots.guarded_facets.color_family
    ):
        return MatchDecision(
            is_match=False,
            reason=(
                f"Color collision: {target_slots.guarded_facets.color_raw} "
                f"({target_slots.guarded_facets.color_family}) vs {cand_slots.guarded_facets.color_raw} "
                f"({cand_slots.guarded_facets.color_family})"
            ),
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # All checks passed cleanly
    matched_id = target_slots.anchor or target_slots.series or "Target"
    return MatchDecision(
        is_match=True,
        reason=f"Accepted: {matched_id} matched with zero guarded facet collisions",
        target_slots=target_slots,
        candidate_slots=cand_slots,
    )
````

## File: tasks/todo.md
````markdown
# Task List: 3-Tier Multi-Pattern Search & Robust Unified Referee Engine

## Phase 1: Exhaustive 3-Tier Pattern Generation & Waterfall Search
- [x] Task 1.1: Remove premature early-exit (`break` on $\ge 2$ offers) in `pricing_engine/scraper.py:_execute_waterfall` to allow all tiers to query and pool.
- [x] Task 1.2: Upgrade `generate_search_patterns()` in `pricing_engine/matcher.py` to decouple glued SKU codes (e.g. `DWT11467ES` -> `DWT-11467`, `11467 ES`, `11467`).
- [x] Task 1.3: Ensure unified deduplication in `scraper.py` by `(vendor_name.lower(), round(price, 2))`.

## Phase 2: Title Normalization & Merchant Noise Cleansing
- [x] Task 2.1: Add marketplace noise cleaner for seller names (`ElectroEase`, `HomeCart`, `ISPK-\d+`, `SNS\d+`, `ET`, `UE\d+`) and promo phrases (`On Installment`, `Free Delivery`, `Special Gift`).
- [x] Task 2.2: Isolate operational descriptors (`Heat & Cool`, `DC Inverter`) so they don't pollute the extracted Series slot.
- [x] Task 2.3: Clean parentheses, brackets, and normalize slashes in `extract_product_slots()` so `(Milky White Textured)` maps cleanly to facets.

## Phase 3: Dynamic Initialisms & Slash-Separated Series Support
- [x] Task 3.1: Support slash-separated series names (`Sprinter / Powercon`) with OR logic in `referee_match()`.
- [x] Task 3.2: Verify and enhance dynamic initialism referee (`SD` $\iff$ `Single Door`, `DD` $\iff$ `Double Door`, `FL` $\iff$ `Front Load`, `TL` $\iff$ `Top Load`).

## Phase 4: Strict Guarded Facets & Color Optionality Enforcement
- [x] Task 4.1: Enforce strict T3 compressor guard in `referee_match()`.
- [x] Task 4.2: Enforce IoT smart appliance guard in `referee_match()` (reject basic model against IoT inverter).
- [x] Task 4.3: Implement Color Optionality Rule: Reject conflicting color families; accept unmentioned color when model matches.
- [x] Task 4.4: Enforce Hardware Tub guard (`WB` vs `GB`).

## Phase 5: Verification & Benchmark Suite
- [x] Task 5.1: Create test suite in `tests/test_dawlance_benchmark.py` covering the 38 benchmark Dawlance models.
- [x] Task 5.2: Run full regression test suite (`pytest`) to ensure 100% green pass.
- [x] Task 5.3: Verify end-to-end pipeline run with rich terminal output and pure integer exports.
````

## File: pricing_engine/pipeline.py
````python
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
from curl_cffi.requests import AsyncSession
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pricing_engine.calculator import (
    calculate_baseline,
    calculate_cost_base,
    calculate_floors,
    calculate_shipping_estimate,
    calculate_volumetric_weight,
)
from pricing_engine.db import SupabaseClient
from pricing_engine.evaluator import evaluate_alfa_pricing, evaluate_digi_pricing
from pricing_engine.exporter import export_results
from pricing_engine.ingestion import INVALID_BRAND_VALUES
from pricing_engine.learner import AutonomousLearner
from pricing_engine.matcher import (
    extract_product_slots,
    extract_search_query_and_model,
    generate_search_patterns,
    referee_match,
)
from pricing_engine.models import (
    STATUS_SERVER_DOWN,
    CostFloors,
    PlatformPricingResult,
    ProductInput,
    ScrapedOffer,
    ScrapeResult,
)
from pricing_engine.registry import InMemoryRegistry
from pricing_engine.scraper import scrape_alfamall, scrape_digimall

default_learner = AutonomousLearner()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

console = Console(legacy_windows=False, width=max(105, Console().width or 105))
logger = logging.getLogger(__name__)

ZONE_PRICE: float = 70.0
DIVISOR: float = 5000.0


def _format_dupe_tag(count: int) -> str:
    """Format compact dupe tag only when duplicate listings were collapsed."""
    dupes = count - 1
    if dupes <= 0:
        return ""
    word = "dupe" if dupes == 1 else "dupes"
    return f" [dim][{dupes} {word}][/]"


def format_export_price(val: Any) -> str:
    """Format integer price values for CSV export without float drift (.0) or empty on None/NaN.

    Args:
        val: Numeric, None, or NaN price value.

    Returns:
        Pure integer string (e.g. '165000') or empty string '' if None/NaN.
    """
    if val is None or pd.isna(val):
        return ""
    try:
        clean = str(val).replace(",", "").strip()
        if not clean or clean.lower() == "nan" or clean.lower() == "none":
            return ""
        return str(int(round(float(clean))))
    except (ValueError, TypeError):
        return ""


def determine_risk_alert(res: PlatformPricingResult) -> str:
    """Determine standardized commercial risk alert code following priority hierarchy.

    Priority hierarchy:
    1. SERVER_DOWN: Connection failed, portal down, or final price/profit missing.
    2. NEGATIVE_MARGIN: Defensive check in case profit is zero or negative.
    3. SAFE_FALLBACK: Competitors are dumping below floor, price is uncompetitive.
    4. THIN_BUFFER: Profit is between Rs. 1 and Rs. 699 (courier re-weighing risk).
    5. NONE: Healthy optimal margin (profit >= Rs. 700).

    Args:
        res: PlatformPricingResult from platform evaluation.

    Returns:
        One of 'SERVER_DOWN', 'NEGATIVE_MARGIN', 'SAFE_FALLBACK', 'THIN_BUFFER', 'NONE'.
    """
    if (
        res.status == STATUS_SERVER_DOWN
        or res.final_price is None
        or res.real_profit is None
    ):
        return "SERVER_DOWN"
    if res.real_profit <= 0:
        return "NEGATIVE_MARGIN"
    if res.status == "Safe Fallback":
        return "SAFE_FALLBACK"
    if res.real_profit < 700:
        return "THIN_BUFFER"
    return "NONE"


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert arbitrary values to float, handling strings with commas or NaNs."""
    if val is None or pd.isna(val):
        return default
    try:
        clean_str = str(val).replace(",", "").strip()
        return float(clean_str)
    except (ValueError, TypeError):
        return default


def resolve_shipping_estimate(product: ProductInput) -> float:
    """Resolve shipping estimate from CSV if provided, or compute from volumetric weight."""
    csv_shipping = product.raw_row.get("Shipping Estimate")
    if pd.notna(csv_shipping) and _safe_float(csv_shipping) > 0:
        return round(_safe_float(csv_shipping), 2)
    vol_weight = calculate_volumetric_weight(
        product.length, product.width, product.height, divisor=DIVISOR
    )
    return calculate_shipping_estimate(vol_weight, rate_per_kg=ZONE_PRICE)



def _extract_sno(row: pd.Series | dict[str, Any], default: int) -> int | str:
    """Extract serial number from row checking various casing or fallback to 1-based index."""
    for key in ("S.NO", "S.No", "S. No", "S.No.", "SNO", "sno", "Serial No", "Serial Number"):
        val = row.get(key)
        if val is not None and not pd.isna(val) and str(val).strip() != "":
            try:
                f = float(val)
                if f.is_integer():
                    return int(f)
            except (ValueError, TypeError):
                pass
            return str(val).strip()
    return default


def parse_product_input(idx: int, row: pd.Series) -> ProductInput:
    """Parse and sanitize a raw CSV row into a strongly typed ProductInput.

    Args:
        idx: 0-indexed row number from DataFrame iteration.
        row: Pandas Series representing the product row.

    Returns:
        Structured ProductInput instance.
    """
    sno = _extract_sno(row, idx + 1)
    raw_brand = row.get("Brand")
    brand = str(raw_brand).strip() if (raw_brand is not None and not pd.isna(raw_brand)) else ""
    raw_name = row.get("Name ")
    if raw_name is None or pd.isna(raw_name):
        raw_name = row.get("Name", "Product")
    name = str(raw_name).strip()

    if not brand or brand.lower() in INVALID_BRAND_VALUES:
        raise ValueError(
            f"Row {idx + 1} ('{name}'): 'Brand' column is empty or invalid ('{brand or raw_brand}'). "
            "Please enter a valid brand name in the 'Brand' column for this product."
        )

    length = _safe_float(row.get("Length"), 0.0)
    width = _safe_float(row.get("Width"), 0.0)
    height = _safe_float(row.get("Height"), 0.0)
    net_price = _safe_float(row.get("Net Price"), 0.0)
    profit = _safe_float(row.get("Profit"), 500.0)

    return ProductInput(
        sno=sno,
        brand=brand,
        name=name,
        length=length,
        width=width,
        height=height,
        net_price=net_price,
        profit=profit,
        raw_row=row.to_dict(),
    )


def determine_platform_status(
    price_val: Any,
    min_comp_price: Any = None,
    reason: str = "",
    alert: str = "",
) -> str:
    """Determine outcome status badge string: e.g. 'WIN (-500)', 'SOLO', 'FALLBACK', 'CAPPED', 'SERVER_DOWN'.

    Strict Market-Wide Winning Rule:
    A price is marked as WIN if and only if:
    1. diff = (min_comp_price - price_val) > 0 (our price beats the absolute lowest competitor in the entire mall).
    2. No sub-floor competitors were dropped who are selling below our floor (i.e. 'sub-floor' not in reason).
    """
    reason_lower = str(reason).lower()
    alert_str = str(alert)

    if (
        "server is down" in reason_lower
        or "unreachable" in reason_lower
        or alert_str == "SERVER_DOWN"
    ):
        return "SERVER_DOWN"

    if alert_str == "SAFE_FALLBACK" or "safe fallback" in reason_lower:
        return "FALLBACK"

    if pd.notna(price_val) and price_val is not None and str(price_val).strip() != "":
        if (
            min_comp_price is not None
            and pd.notna(min_comp_price)
            and str(min_comp_price).strip() != ""
        ):
            try:
                min_p = float(min_comp_price)
                f_p = float(price_val)
                diff = int(round(min_p - f_p))
                if diff > 0 and "sub-floor" not in reason_lower:
                    if "capped" in reason_lower:
                        return f"CAPPED (-{diff:,})"
                    return f"WIN (-{diff:,})"
            except (ValueError, TypeError):
                pass

        if "monopoly" in reason_lower or "no competitors" in reason_lower:
            return "SOLO"
        if "capped" in reason_lower:
            return "CAPPED"
        return ""

    return ""


def build_output_record(
    product: ProductInput,
    shipping: float,
    floors: CostFloors,
    baseline_calc: float,
    alfa_res: PlatformPricingResult,
    digi_res: PlatformPricingResult,
) -> dict[str, Any]:
    """Combine input row data and calculated platform results into final output dictionary.

    Args:
        product: Input product item.
        shipping: Calculated or catalog shipping estimate.
        floors: CostFloors object.
        baseline_calc: Standard baseline catalog price.
        alfa_res: PlatformPricingResult for AlfaMall.
        digi_res: PlatformPricingResult for DigiMall.

    Returns:
        Dictionary adhering to the target CSV schema.
    """
    # Guarantee S.NO is the first column in output
    out_record: dict[str, Any] = {"S.NO": product.sno}

    # Copy remaining raw_row fields, excluding any S.NO aliases
    sno_aliases = {"S.NO", "S.No", "S. No", "S.No.", "SNO", "sno", "Serial No", "Serial Number"}
    for k, v in product.raw_row.items():
        if k not in sno_aliases:
            out_record[k] = v

    out_record["Shipping Estimate"] = shipping
    out_record["Commision"] = "10.00%"
    out_record["Digi Effective Commision"] = digi_res.effective_comm

    # Total Without Profit: If Digi uses 8%, record 8% breakeven (cost_base / 0.92)
    # If 10%, record 10% breakeven (cost_base / 0.90)
    if digi_res.effective_comm == "8.00%":
        out_record["Total Without Profit"] = round(floors.zero_margin_8)
    else:
        out_record["Total Without Profit"] = round(floors.zero_margin_10)

    out_record["Calculation"] = round(baseline_calc)

    out_record["Minimum Price Alfa"] = alfa_res.min_price
    out_record["Maximum Price Alfa"] = alfa_res.max_price
    out_record["Minimum Price Digi"] = digi_res.min_price
    out_record["Maximum Price Digi"] = digi_res.max_price

    alfa_alert = determine_risk_alert(alfa_res)
    digi_alert = determine_risk_alert(digi_res)

    out_record["Final Price Alfa"] = alfa_res.final_price
    out_record["Alfa Status"] = determine_platform_status(
        alfa_res.final_price, alfa_res.min_price, alfa_res.reason, alfa_alert
    )
    out_record["Final Price Digi"] = digi_res.final_price
    out_record["Digi Status"] = determine_platform_status(
        digi_res.final_price, digi_res.min_price, digi_res.reason, digi_alert
    )
    out_record["Alfa Real Profit"] = alfa_res.real_profit
    out_record["Digi Real Profit"] = digi_res.real_profit
    out_record["Alfa Reason"] = alfa_res.reason
    out_record["Digi Reason"] = digi_res.reason
    out_record["Alfa Risk Alert"] = alfa_alert
    out_record["Digi Risk Alert"] = digi_alert

    return out_record


def process_product_with_offers(
    product: ProductInput,
    alfa_offers: list[ScrapedOffer] | ScrapeResult,
    digi_offers: list[ScrapedOffer] | ScrapeResult,
) -> dict[str, Any]:
    """Execute complete cost math and pricing decisions given fetched competitor offers.

    Args:
        product: ProductInput instance.
        alfa_offers: Offers scraped from AlfaMall (or ScrapeResult).
        digi_offers: Offers scraped from DigiMall (or ScrapeResult).

    Returns:
        Repriced output dictionary.
    """
    shipping = resolve_shipping_estimate(product)

    cost_base = calculate_cost_base(product.net_price, shipping)
    floors = calculate_floors(cost_base, min_profit=500.0)
    baseline_calc = calculate_baseline(cost_base, target_profit=product.profit)

    alfa_res = evaluate_alfa_pricing(floors, alfa_offers)
    digi_res = evaluate_digi_pricing(floors, digi_offers)

    return build_output_record(
        product=product,
        shipping=shipping,
        floors=floors,
        baseline_calc=baseline_calc,
        alfa_res=alfa_res,
        digi_res=digi_res,
    )


def render_start_banner(
    input_path: Path,
    output_path: Path,
    total_items: int,
    concurrency: int,
) -> None:
    """Render executive startup banner with operational parameters."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", width=18)
    grid.add_column(style="white")
    grid.add_row("Source Catalog:", f"{input_path.name} ({total_items} items loaded)")
    grid.add_row("Output Target:", f"{output_path.name}")
    grid.add_row("Scraper Workers:", f"Direct JSON Search APIs ({concurrency} concurrent workers)")
    grid.add_row(
        "Pricing Strategy:", "AlfaMall 10% Floor | DigiMall Two-Tier (10% -> 8% Bank Switch)"
    )

    console.print()
    console.print(
        Panel(
            grid,
            title="[bold green]ALFAMALL & DIGIMALL DYNAMIC REPRICING ENGINE[/]",
            subtitle="[dim]Real-time Competitive Price Discovery & Margin Optimization[/]",
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


def render_finish_banner(
    output_path: Path,
    total_processed: int,
    elapsed_seconds: float,
) -> None:
    """Render clean executive completion banner."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", width=18)
    grid.add_column(style="white")
    grid.add_row("Execution Status:", "[bold green]Successfully Completed[/]")
    grid.add_row("Total Repriced:", f"{total_processed} catalog items")
    grid.add_row("Exported File:", f"[bold white]{output_path.resolve()}[/]")
    grid.add_row("Elapsed Time:", f"{elapsed_seconds:.2f} seconds")

    console.print()
    console.print(
        Panel(
            grid,
            title="[bold green]PIPELINE EXECUTION COMPLETE[/]",
            subtitle="[dim]All catalog items evaluated & exported to disk[/]",
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )
    console.print()


def _render_platform_offers_to_table(
    tbl: Table,
    platform_tag: str,
    offers: list[ScrapedOffer] | ScrapeResult,
    res: PlatformPricingResult,
    floor_price: float,
    floor_label: str,
    empty_label: str,
    target_undercut_label: str,
) -> None:
    """Render verified scraped offers and drop reasons for a platform into the summary table."""
    is_down = res.status == STATUS_SERVER_DOWN or (
        isinstance(offers, ScrapeResult) and not offers.is_success
    )
    if is_down:
        tbl.add_row(
            platform_tag,
            "[bold red]Connection Failed[/]",
            "[dim]N/A[/]",
            "[bold red]Remote Portal Down / Unreachable (Skipped)[/]",
        )
        return

    if not offers:
        tbl.add_row(
            platform_tag,
            "[dim]No sellers found[/]",
            "[dim]0 scraped[/]",
            empty_label,
        )
        return

    active_offers = [o for o in offers if not o.is_sold_out]
    sorted_offers = sorted(active_offers, key=lambda x: x.price)
    sold_out = [o for o in offers if o.is_sold_out]

    dropped = [o for o in sorted_offers if o.price <= floor_price]
    viable = [o for o in sorted_offers if o.price > floor_price]

    if viable:
        # 1. Dropped sub-floor offers (first 2 + rollup + immediate predecessor before target)
        if len(dropped) > 3:
            for o in dropped[:2]:
                dupe_tag = _format_dupe_tag(o.duplicate_count)
                tbl.add_row(
                    platform_tag,
                    o.vendor_name[:21],
                    f"Rs. {o.price:,.0f}",
                    f"[red]Dropped (< {floor_label})[/]{dupe_tag}",
                )
            rem_dropped = len(dropped) - 3
            tbl.add_row(
                platform_tag,
                f"[dim]... +{rem_dropped} dropped[/]",
                f"[dim]Rs. {dropped[2].price:,.0f}+[/]",
                f"[dim red]Sub-floor offers (up to Rs. {floor_price - 1:,.0f})[/]",
            )
            # Explicitly render the closest sub-floor seller right before target undercut
            closest_dropped = dropped[-1]
            c_dupe = _format_dupe_tag(closest_dropped.duplicate_count)
            tbl.add_row(
                platform_tag,
                closest_dropped.vendor_name[:21],
                f"Rs. {closest_dropped.price:,.0f}",
                f"[red]Dropped (< {floor_label})[/]{c_dupe}",
            )
        else:
            for o in dropped:
                dupe_tag = _format_dupe_tag(o.duplicate_count)
                tbl.add_row(
                    platform_tag,
                    o.vendor_name[:21],
                    f"Rs. {o.price:,.0f}",
                    f"[red]Dropped (< {floor_label})[/]{dupe_tag}",
                )

        # 2. Target Undercut - ALWAYS explicitly rendered
        lowest_viable = viable[0]
        lv_dupe = _format_dupe_tag(lowest_viable.duplicate_count)
        lv_title = f"\n[dim white]-> {lowest_viable.raw_title[:65]}[/]" if lowest_viable.raw_title else ""
        tbl.add_row(
            platform_tag,
            lowest_viable.vendor_name[:21],
            f"Rs. {lowest_viable.price:,.0f}",
            f"{target_undercut_label}{lv_dupe}{lv_title}",
        )

        # 3. Next 2-3 viable competitors
        for o in viable[1:4]:
            v_dupe = _format_dupe_tag(o.duplicate_count)
            v_title = f"\n[dim white]-> {o.raw_title[:65]}[/]" if o.raw_title else ""
            tbl.add_row(
                platform_tag,
                o.vendor_name[:21],
                f"Rs. {o.price:,.0f}",
                f"[dim]Viable Competitor[/]{v_dupe}{v_title}",
            )

        # 4. Rollup higher offers with true max ceiling
        if len(viable) > 4:
            rem_viable = len(viable) - 4
            min_rem = viable[4].price
            max_rem = viable[-1].price
            tbl.add_row(
                platform_tag,
                f"[dim]... +{rem_viable} more[/]",
                f"[dim]Rs. {min_rem:,.0f}+[/]",
                f"[dim]Higher offers (up to Rs. {max_rem:,.0f})[/]",
            )
    else:
        # All scraped competitors are selling below floor
        for o in dropped[:3]:
            dupe_tag = _format_dupe_tag(o.duplicate_count)
            tbl.add_row(
                platform_tag,
                o.vendor_name[:21],
                f"Rs. {o.price:,.0f}",
                f"[red]Dropped (< {floor_label})[/]{dupe_tag}",
            )
        if len(dropped) > 3:
            rem_dropped = len(dropped) - 3
            min_rem = dropped[3].price
            max_rem = dropped[-1].price
            tbl.add_row(
                platform_tag,
                f"[dim]... +{rem_dropped} dropped[/]",
                f"[dim]Rs. {min_rem:,.0f}+[/]",
                f"[dim red]All sub-floor (up to Rs. {max_rem:,.0f})[/]",
            )

    for s in sold_out[:2]:
        tbl.add_row(
            platform_tag,
            s.vendor_name[:21],
            f"Rs. {s.price:,.0f}",
            "[dim red]Out of Stock (Ignored)[/]",
        )


def build_scraped_sellers_table(
    floors: CostFloors,
    alfa_offers: list[ScrapedOffer] | ScrapeResult,
    digi_offers: list[ScrapedOffer] | ScrapeResult,
    alfa_res: PlatformPricingResult,
    digi_res: PlatformPricingResult,
) -> Table:
    """Build a crystal-clear table listing all scraped competitor sellers, prices, and status."""
    tbl = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
        expand=True,
    )
    tbl.add_column("Platform", width=9)
    tbl.add_column("Seller / Vendor", style="bold white", width=21)
    tbl.add_column("Scraped Price", justify="right", style="bold yellow", width=13)
    tbl.add_column("Status", ratio=1)

    # 1. AlfaMall Scraped Competitors
    _render_platform_offers_to_table(
        tbl=tbl,
        platform_tag="[bold #2c4699]AlfaMall[/]",
        offers=alfa_offers,
        res=alfa_res,
        floor_price=floors.floor_alfa,
        floor_label=f"Floor Rs. {floors.floor_alfa:,.0f}",
        empty_label="[bold cyan]Monopoly Pricing (+Rs. 4,000 margin)[/]",
        target_undercut_label="[bold green]Target Undercut (Lowest Viable)[/]",
    )

    # 2. DigiMall Scraped Competitors
    digi_comm_note = "8% Viable" if digi_res.effective_comm == "8.00%" else "10% Viable"
    _render_platform_offers_to_table(
        tbl=tbl,
        platform_tag="[bold #229693]DigiMall[/]",
        offers=digi_offers,
        res=digi_res,
        floor_price=floors.floor_digi_8,
        floor_label=f"8% Floor Rs. {floors.floor_digi_8:,.0f}",
        empty_label="[bold cyan]Baseline Undercut (+2% margin)[/]",
        target_undercut_label=f"[bold green]Target Undercut ({digi_comm_note})[/]",
    )

    return tbl


def render_audit_card(
    product: ProductInput,
    shipping: float,
    floors: CostFloors,
    baseline_calc: float,
    target_model: str,
    alfa_offers: list[ScrapedOffer] | ScrapeResult,
    digi_offers: list[ScrapedOffer] | ScrapeResult,
    alfa_res: PlatformPricingResult,
    digi_res: PlatformPricingResult,
) -> None:
    """Print a polished, executive-grade audit card enclosed in a rounded box."""
    tot_10 = round(floors.zero_margin_10)
    tot_8 = round(floors.zero_margin_8)

    # 1. Logistics and Cost Breakdown Grid
    specs = Table.grid(padding=(0, 3), expand=True)
    specs.add_column(style="cyan")
    specs.add_column(style="bold white")
    specs.add_column(style="cyan")
    specs.add_column(style="bold white")

    dim_str = f"{product.length:g}x{product.width:g}x{product.height:g} cm"
    specs.add_row(
        "Net Catalog Price:",
        f"Rs. {product.net_price:,.0f}",
        "[#2c4699]Alfa 10% (Without 500):[/]",
        f"Rs. {tot_10:,}",
    )
    specs.add_row(
        "Courier Shipping:",
        f"Rs. {shipping:,.2f}",
        "[bold #2c4699]Alfa 10% Floor (+500):[/]",
        f"[bold #2c4699]Rs. {floors.floor_alfa:,.0f}[/]",
    )
    specs.add_row(
        "Real Landed Cost:",
        f"[bold green]Rs. {floors.cost_base:,.2f}[/]",
        "[#229693]Digi 8% (Without 500):[/]",
        f"Rs. {tot_8:,}",
    )
    specs.add_row(
        "Dimensions:",
        dim_str,
        "[bold #229693]Digi 8% Floor (+500):[/]",
        f"[bold #229693]Rs. {floors.floor_digi_8:,.0f}[/]",
    )

    # 2. Competitor Sellers Table
    sellers_tbl = build_scraped_sellers_table(
        floors=floors,
        alfa_offers=alfa_offers,
        digi_offers=digi_offers,
        alfa_res=alfa_res,
        digi_res=digi_res,
    )

    # 3. Platform Comparison Table
    plat_tbl = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
        expand=True,
    )
    plat_tbl.add_column("Decision Metric", style="bold cyan", width=16)
    plat_tbl.add_column("[bold #2c4699]AlfaMall (Strict 10%)[/]", style="white", ratio=1)
    plat_tbl.add_column("[bold #229693]DigiMall (Two-Tier Switch)[/]", style="white", ratio=1)

    # Active offers summary
    is_alfa_down = alfa_res.status == STATUS_SERVER_DOWN or (
        isinstance(alfa_offers, ScrapeResult) and not alfa_offers.is_success
    )
    is_digi_down = digi_res.status == STATUS_SERVER_DOWN or (
        isinstance(digi_offers, ScrapeResult) and not digi_offers.is_success
    )

    if is_alfa_down:
        alfa_offers_str = "[bold red]Connection Failed (Down)[/]"
    else:
        alfa_active_count = len([o for o in alfa_offers if not o.is_sold_out])
        alfa_drop_count = len(alfa_res.dropped)
        alfa_offers_str = f"{alfa_active_count} verified offers"
        if alfa_drop_count > 0:
            alfa_offers_str += f" ({alfa_drop_count} dropped)"

    if is_digi_down:
        digi_offers_str = "[bold red]Connection Failed (Down)[/]"
    else:
        digi_active_count = len([o for o in digi_offers if not o.is_sold_out])
        digi_drop_count = len(digi_res.dropped)
        digi_offers_str = f"{digi_active_count} verified offers"
        if digi_drop_count > 0:
            digi_offers_str += f" ({digi_drop_count} dropped)"

    plat_tbl.add_row("Scraped Offers", alfa_offers_str, digi_offers_str)

    # Commission tier applied
    if digi_res.effective_comm == "8.00%":
        digi_comm_badge = "[bold blue]8.00% Emergency Switch[/]"
    else:
        digi_comm_badge = "[#229693]8% + 2% Spread[/]"
    plat_tbl.add_row("Bank Commission", "10.00% Standard", digi_comm_badge)

    # Final Price
    if alfa_res.status == STATUS_SERVER_DOWN:
        alfa_p_str = "[bold red][SERVER DOWN - RETRY LATER][/]"
    elif alfa_res.final_price is not None:
        if alfa_res.status == "Safe Fallback":
            alfa_p_str = (
                f"[bold red]Rs. {alfa_res.final_price:,} (SAFE FALLBACK - UNCOMPETITIVE)[/]"
            )
        elif "capped" in (alfa_res.reason or "").lower():
            alfa_p_str = f"[bold yellow]Rs. {alfa_res.final_price:,} (CAPPED SWEET-SPOT)[/]"
        else:
            alfa_p_str = f"[bold #2c4699]Rs. {alfa_res.final_price:,}[/]"
    else:
        alfa_p_str = "[bold yellow]SKIP / NaN (Loss Prevented)[/]"

    if digi_res.status == STATUS_SERVER_DOWN:
        digi_p_str = "[bold red][SERVER DOWN - RETRY LATER][/]"
    elif digi_res.final_price is not None:
        if digi_res.status == "Safe Fallback":
            digi_p_str = (
                f"[bold red]Rs. {digi_res.final_price:,} (SAFE FALLBACK - UNCOMPETITIVE)[/]"
            )
        elif "capped" in (digi_res.reason or "").lower():
            digi_p_str = f"[bold yellow]Rs. {digi_res.final_price:,} (CAPPED SWEET-SPOT)[/]"
        else:
            digi_p_str = f"[bold #229693]Rs. {digi_res.final_price:,}[/]"
    else:
        digi_p_str = "[bold yellow]SKIP / NaN (Loss Prevented)[/]"

    plat_tbl.add_row("Final Price", alfa_p_str, digi_p_str)

    # Real Profit
    if alfa_res.status == STATUS_SERVER_DOWN:
        alfa_prof_str = "[dim red]Rs. 0 (Server Down)[/]"
    elif alfa_res.final_price is not None:
        if alfa_res.real_profit <= 0:
            alfa_prof_str = f"[bold white on red]Rs. {alfa_res.real_profit:,} (NEGATIVE MARGIN)[/]"
        elif alfa_res.real_profit < 700:
            alfa_prof_str = (
                f"[bold red]+Rs. {alfa_res.real_profit:,} (THIN BUFFER - VOLUMETRIC RISK)[/]"
            )
        else:
            alfa_prof_str = f"[bold green]+Rs. {alfa_res.real_profit:,}[/]"
    else:
        alfa_prof_str = "[dim]Rs. 0 (Loss Prevented)[/]"

    if digi_res.status == STATUS_SERVER_DOWN:
        digi_prof_str = "[dim red]Rs. 0 (Server Down)[/]"
    elif digi_res.final_price is not None:
        if digi_res.real_profit <= 0:
            digi_prof_str = f"[bold white on red]Rs. {digi_res.real_profit:,} (NEGATIVE MARGIN)[/]"
        elif digi_res.real_profit < 700:
            digi_prof_str = (
                f"[bold red]+Rs. {digi_res.real_profit:,} (THIN BUFFER - VOLUMETRIC RISK)[/]"
            )
        else:
            digi_prof_str = f"[bold green]+Rs. {digi_res.real_profit:,}[/]"
    else:
        digi_prof_str = "[dim]Rs. 0 (Loss Prevented)[/]"

    plat_tbl.add_row("Real Net Profit", alfa_prof_str, digi_prof_str)
    plat_tbl.add_row("Strategy Reason", alfa_res.reason, digi_res.reason)

    # 1b. Search Query & Waterfall Fallback Telemetry
    def _format_search_telemetry(
        p_name: str, p_color: str, offers_res: list[ScrapedOffer] | ScrapeResult
    ) -> str:
        if isinstance(offers_res, ScrapeResult) and offers_res.active_modifier_fallback:
            mod = offers_res.active_modifier_fallback
            count = len(offers_res.offers)
            return (
                f"[{p_color}]{p_name}:[/] [bold yellow]⚠️ MODIFIER '{mod}' OMITTED BY MARKET[/] -> "
                f"[bold green]Matched {count} base model offer{'s' if count != 1 else ''} (DO CROSS-CHECK)[/]"
            )
        if isinstance(offers_res, ScrapeResult) and offers_res.executed_queries:
            q_list = offers_res.executed_queries
            t_sum = offers_res.tier_summary
            if t_sum.get("tier_1", 0) > 0:
                q_disp = q_list[0] if q_list else target_model
                count = t_sum["tier_1"]
                return (
                    f"[{p_color}]{p_name}:[/] [bold white]'{q_disp}'[/] "
                    f"[green](Exact Query -> {count} verified offer{'s' if count > 1 else ''})[/]"
                )
            elif t_sum.get("tier_2", 0) > 0:
                t1_q = q_list[0] if q_list else ""
                t2_q = q_list[1] if len(q_list) > 1 else (q_list[0] if q_list else target_model)
                count = t_sum["tier_2"]
                return (
                    f"[{p_color}]{p_name}:[/] [dim]'{t1_q}' (0 found)[/] -> "
                    f"[bold yellow]Fallback Stem:[/] [bold white]'{t2_q}'[/] "
                    f"[green]({count} offer{'s' if count > 1 else ''} strictly verified)[/]"
                )
            elif t_sum.get("tier_3", 0) > 0:
                tier3_q = q_list[-1] if q_list else target_model
                count = t_sum["tier_3"]
                return (
                    f"[{p_color}]{p_name}:[/] [dim]Tiers 1 & 2 (0 found)[/] -> "
                    f"[bold yellow]Permutation Fallback:[/] [bold white]'{tier3_q}'[/] "
                    f"[green]({count} offer{'s' if count > 1 else ''} verified)[/]"
                )
            else:
                tried_str = ", ".join(f"'{q}'" for q in q_list[:2])
                return (
                    f"[{p_color}]{p_name}:[/] [dim]Queried {tried_str} (0 offers found in market)[/] -> "
                    f"[bold cyan]Monopoly Price Applied[/]"
                )
        return f"[{p_color}]{p_name}:[/] [dim]Target: '{target_model}'[/]"

    query_grid = Table.grid(padding=(0, 2), expand=True)
    query_grid.add_column(style="bold cyan", width=16)
    query_grid.add_column(style="white", ratio=1)
    query_grid.add_row(
        "Search Audit:",
        _format_search_telemetry("AlfaMall", "#2c4699", alfa_offers),
    )
    query_grid.add_row(
        "",
        _format_search_telemetry("DigiMall", "#229693", digi_offers),
    )

    content = Table.grid(padding=(1, 0), expand=True)
    content.add_row(specs)
    content.add_row(query_grid)
    content.add_row(sellers_tbl)
    content.add_row(plat_tbl)

    active_fallback_mod = (
        alfa_offers.active_modifier_fallback
        if isinstance(alfa_offers, ScrapeResult) and alfa_offers.active_modifier_fallback
        else (
            digi_offers.active_modifier_fallback
            if isinstance(digi_offers, ScrapeResult) and digi_offers.active_modifier_fallback
            else None
        )
    )
    if active_fallback_mod:
        warning_banner = Panel(
            f"[bold yellow]⚠️  NOTICE (DO CROSS-CHECK):[/] Target specified [bold cyan]'{active_fallback_mod}'[/], but marketplace listings omitted it. "
            f"Repriced against verified [bold green]base model[/] listings.",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        content.add_row(warning_banner)

    card = Panel(
        content,
        title=(
            f"[bold yellow]ITEM #{product.sno}[/] [bold white]{product.name}[/]"
            f" [dim](Model: {target_model})[/]"
        ),
        border_style="blue",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print()
    console.print(card)


async def process_item_async(
    product: ProductInput,
    session: AsyncSession,
    semaphore: asyncio.Semaphore,
    render_lock: asyncio.Lock | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Execute scraping and pricing calculations for a single product with concurrency control."""
    _, target_model = extract_search_query_and_model(product.name, brand=product.brand)
    patterns = generate_search_patterns(product.name, brand=product.brand)

    shipping = resolve_shipping_estimate(product)

    cost_base = calculate_cost_base(product.net_price, shipping)
    floors = calculate_floors(cost_base, min_profit=500.0)
    baseline_calc = calculate_baseline(cost_base, target_profit=product.profit)

    async with semaphore:
        alfa_task = scrape_alfamall(
            session, patterns, target_model, floor_price=floors.floor_alfa, brand=product.brand
        )
        digi_task = scrape_digimall(
            session, patterns, target_model, floor_price=floors.floor_digi_8, brand=product.brand
        )
        alfa_offers, digi_offers = await asyncio.gather(alfa_task, digi_task)

    alfa_res = evaluate_alfa_pricing(floors, alfa_offers)
    digi_res = evaluate_digi_pricing(floors, digi_offers)

    # Autonomous Multi-Catalog Learning Ingestion (ADR-003)
    target_slots = extract_product_slots(product.name, brand=product.brand)
    all_raw_offers: list[ScrapedOffer] = []
    if isinstance(alfa_offers, ScrapeResult):
        all_raw_offers.extend(alfa_offers.offers)
    elif isinstance(alfa_offers, list):
        all_raw_offers.extend(alfa_offers)

    if isinstance(digi_offers, ScrapeResult):
        all_raw_offers.extend(digi_offers.offers)
    elif isinstance(digi_offers, list):
        all_raw_offers.extend(digi_offers)

    category = str(product.raw_row.get("Category", "")).strip() or "APPLIANCE"
    for offer in all_raw_offers:
        if offer.is_sold_out:
            continue
        match_dec = referee_match(target_slots, offer.raw_title, brand=product.brand)
        if (
            match_dec.is_match
            and target_slots.residuals
            and match_dec.candidate_slots
            and match_dec.candidate_slots.residuals
        ):
            for t_res in target_slots.residuals:
                for c_res in match_dec.candidate_slots.residuals:
                    default_learner.buffer_observation(
                        brand=product.brand,
                        category=category,
                        anchor_model=target_slots.anchor,
                        target_residual=t_res,
                        candidate_residual=c_res,
                        vendor_name=offer.vendor_name,
                        raw_title=offer.raw_title,
                    )

    if verbose:
        if render_lock is not None:
            async with render_lock:
                render_audit_card(
                    product=product,
                    shipping=shipping,
                    floors=floors,
                    baseline_calc=baseline_calc,
                    target_model=target_model,
                    alfa_offers=alfa_offers,
                    digi_offers=digi_offers,
                    alfa_res=alfa_res,
                    digi_res=digi_res,
                )
        else:
            render_audit_card(
                product=product,
                shipping=shipping,
                floors=floors,
                baseline_calc=baseline_calc,
                target_model=target_model,
                alfa_offers=alfa_offers,
                digi_offers=digi_offers,
                alfa_res=alfa_res,
                digi_res=digi_res,
            )

    return build_output_record(
        product=product,
        shipping=shipping,
        floors=floors,
        baseline_calc=baseline_calc,
        alfa_res=alfa_res,
        digi_res=digi_res,
    )


async def _process_item_worker(
    idx: int,
    product: ProductInput,
    session: AsyncSession,
    semaphore: asyncio.Semaphore,
    render_lock: asyncio.Lock,
    verbose: bool = True,
) -> dict[str, Any]:
    """Helper worker to execute an item and attach its original row index for deterministic sorting."""
    record = await process_item_async(
        product=product,
        session=session,
        semaphore=semaphore,
        render_lock=render_lock,
        verbose=verbose,
    )
    record["_original_idx"] = idx
    return record


def _format_summary_price(
    price_val: Any,
    min_comp_price: Any = None,
    reason: str = "",
    alert: str = "",
    brand_color: str = "white",
) -> str:
    """Format product price string with inline market winning badges for terminal executive summary table."""
    status = determine_platform_status(price_val, min_comp_price, reason, alert)
    if status == "SERVER_DOWN":
        return "[bold red]DOWN[/]"
    if pd.isna(price_val) or price_val is None or str(price_val).strip() == "":
        return "SKIP"

    raw_p = f"{int(float(price_val)):,}"
    price_str = f"[{brand_color}]{raw_p}[/]"
    is_modifier_fallback = "fallback model" in reason.lower()
    mod_tag = " [bold yellow]CROSS-CHECK[/]" if is_modifier_fallback else ""

    if status == "FALLBACK":
        return f"[bold red]{raw_p}[/] [red]FALLBACK[/]{mod_tag}"
    if status.startswith("WIN"):
        return f"{price_str} [bold green]{status}[/]{mod_tag}"
    if status == "SOLO":
        return f"{price_str} [dim]SOLO[/]{mod_tag}"
    if status.startswith("CAPPED"):
        return f"{price_str} [bold yellow]{status}[/]{mod_tag}"
    return f"{price_str}{mod_tag}"


def _format_summary_profit(
    price_val: Any,
    profit_val: Any,
    reason: str,
    alert: str,
) -> str:
    """Format profit string for terminal executive summary table."""
    reason_lower = reason.lower()
    if (
        "server is down" in reason_lower
        or "unreachable" in reason_lower
        or alert == "SERVER_DOWN"
    ):
        return "[dim red]0[/]"
    if pd.notna(price_val) and price_val is not None and str(price_val).strip() != "":
        p_val = float(profit_val or 0)
        if p_val <= 0:
            return f"[bold white on red]{int(p_val):,}[/]"
        if p_val < 700:
            return f"[bold red]+{int(p_val):,}[/]"
        return f"[bold green]+{int(p_val):,}[/]"
    return "0"


def render_summary_table(records: list[dict[str, Any]]) -> None:
    """Render a crystal-clear executive summary table of all repriced products."""
    table = Table(
        title="[bold cyan]DYNAMIC REPRICING EXECUTIVE SUMMARY[/]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
        expand=False,
    )
    table.add_column("S#", justify="right", style="bold yellow")
    table.add_column("Model / Product", style="bold white", no_wrap=True)
    table.add_column("Cost Base", justify="right", style="dim")
    table.add_column("Alfa Price", justify="right", no_wrap=True)
    table.add_column("Alfa Net", justify="right")
    table.add_column("Digi Price", justify="right", no_wrap=True)
    table.add_column("Rate", justify="center", style="blue")
    table.add_column("Digi Net", justify="right", style="bold green")

    for rec in records:
        sno = str(rec.get("S.NO", ""))
        name = str(rec.get("Name ", rec.get("Name", "Product")))
        short_name = name.replace("GREE SPLIT AC ", "").replace("GREE FLOOR STANDING ", "FS ")
        if len(short_name) > 18:
            short_name = short_name[:16] + ".."

        net_val = _safe_float(rec.get("Net Price", 0))
        ship_val = _safe_float(rec.get("Shipping Estimate", 0))
        real_cost_str = f"{(net_val + ship_val):,.0f}"

        alfa_p_val = rec.get("Final Price Alfa")
        alfa_min_val = rec.get("Minimum Price Alfa")
        alfa_reason = str(rec.get("Alfa Reason", ""))
        alfa_alert = str(rec.get("Alfa Risk Alert", ""))
        alfa_p = _format_summary_price(
            alfa_p_val,
            min_comp_price=alfa_min_val,
            reason=alfa_reason,
            alert=alfa_alert,
            brand_color="bold #2c4699",
        )
        alfa_profit = _format_summary_profit(
            alfa_p_val, rec.get("Alfa Real Profit", 0), alfa_reason, alfa_alert
        )

        digi_p_val = rec.get("Final Price Digi")
        digi_min_val = rec.get("Minimum Price Digi")
        digi_reason = str(rec.get("Digi Reason", ""))
        digi_alert = str(rec.get("Digi Risk Alert", ""))
        digi_p = _format_summary_price(
            digi_p_val,
            min_comp_price=digi_min_val,
            reason=digi_reason,
            alert=digi_alert,
            brand_color="bold #229693",
        )
        digi_profit = _format_summary_profit(
            digi_p_val, rec.get("Digi Real Profit", 0), digi_reason, digi_alert
        )

        if (
            "server is down" in digi_reason.lower()
            or "unreachable" in digi_reason.lower()
            or digi_alert == "SERVER_DOWN"
        ):
            digi_comm = "[dim red]N/A[/]"
        elif pd.notna(digi_p_val) and digi_p_val is not None and str(digi_p_val).strip() != "":
            raw_digi_comm = (
                str(rec.get("Digi Effective Commision", "10.00%")).replace("%", "") + "%"
            )
            if "8" in raw_digi_comm:
                digi_comm = f"[bold yellow]{raw_digi_comm}[/]"
            else:
                digi_comm = f"[blue]{raw_digi_comm}[/]"
        else:
            digi_comm = str(rec.get("Digi Effective Commision", "10.00%")).replace("%", "") + "%"

        table.add_row(
            sno,
            short_name,
            real_cost_str,
            alfa_p,
            alfa_profit,
            digi_p,
            digi_comm,
            digi_profit,
        )

    console.print()
    console.print(table)
    console.print(
        "[dim]LEGEND:[/dim] "
        "[bold red]RED[/]: Safe Fallback (Market Below Floor) / Thin Margin (< Rs. 700) | "
        "[bold yellow]YELLOW[/]: Capped Sweet-Spot / 8% Bank Switch | "
        "[bold green]GREEN[/]: Optimal Win | "
        "[bold yellow]CROSS-CHECK[/]: Target modifier omitted in listings (priced against base model)"
    )
    console.print()


async def run_pipeline(
    input_path: str | Path,
    output_path: str | Path | None = None,
    concurrency: int = 3,
    verbose: bool = True,
    use_structured_export: bool = False,
    export_dir: str | Path = "data/outputs",
) -> pd.DataFrame:
    """Run dynamic repricing pipeline on an input CSV and export results to output CSV.

    Features:
    - Micro-staggered launch (200ms) to prevent T=0 burst wave / WAF socket drops.
    - True bounded concurrency via asyncio.Semaphore(concurrency).
    - Atomic terminal audit rendering protected by asyncio.Lock.
    - 100% deterministic output row sorting preserving original CSV row sequence.
    - Optional structured export to data/outputs/ with timestamp and latest copy.

    Args:
        input_path: Path to the source CSV file.
        output_path: Optional path where repriced CSV should be written.
        concurrency: Max simultaneous product search requests (default: 3).
        verbose: Print visual terminal audit cards if True.
        use_structured_export: If True or output_path is None, exports structured files.
        export_dir: Directory where structured outputs are saved (default: data/outputs).

    Returns:
        Processed DataFrame with repriced data.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found at: {input_path}")

    df = pd.read_csv(input_path)
    # Strip whitespace from column headers, preserving legacy 'Name ' key if present
    has_legacy_name_space = "Name " in df.columns
    df.columns = [
        "Name " if c == "Name " and has_legacy_name_space else str(c).strip()
        for c in df.columns
    ]
    start_time = time.perf_counter()

    supabase_client = SupabaseClient()
    if supabase_client.is_configured:
        await InMemoryRegistry.load_from_db(supabase_client)

    banner_output_path = (
        Path(output_path)
        if output_path is not None
        else Path(export_dir) / f"{input_path.stem}_repriced_latest.csv"
    )

    if verbose:
        render_start_banner(
            input_path=input_path,
            output_path=banner_output_path,
            total_items=len(df),
            concurrency=concurrency,
        )

    semaphore = asyncio.Semaphore(concurrency)
    render_lock = asyncio.Lock()
    tasks: list[asyncio.Task[dict[str, Any]]] = []

    async with AsyncSession(impersonate="chrome120") as session:
        for idx, row in df.iterrows():
            product = parse_product_input(idx, row)
            task = asyncio.create_task(
                _process_item_worker(
                    idx=int(idx),
                    product=product,
                    session=session,
                    semaphore=semaphore,
                    render_lock=render_lock,
                    verbose=verbose,
                )
            )
            tasks.append(task)
            if idx < len(df) - 1:
                # Micro-stagger launch by 400ms to eliminate burst wave against WAF
                await asyncio.sleep(0.4)

        raw_records = await asyncio.gather(*tasks)

    # Guarantee deterministic 1:1 original CSV row sorting
    raw_records.sort(key=lambda r: int(r.get("_original_idx", 0)))
    records: list[dict[str, Any]] = []
    for r in raw_records:
        r.pop("_original_idx", None)
        records.append(r)

    out_df = pd.DataFrame(records)

    price_int_cols = [
        "Total Without Profit",
        "Calculation",
        "Minimum Price Alfa",
        "Maximum Price Alfa",
        "Minimum Price Digi",
        "Maximum Price Digi",
        "Final Price Alfa",
        "Final Price Digi",
        "Alfa Real Profit",
        "Digi Real Profit",
    ]
    for col in price_int_cols:
        if col in out_df.columns:
            out_df[col] = out_df[col].apply(format_export_price)

    effective_finish_path: Path
    if output_path is not None:
        target_out = Path(output_path)
        if target_out.parent and not target_out.parent.exists():
            target_out.parent.mkdir(parents=True, exist_ok=True)
        out_df.to_csv(target_out, index=False)
        effective_finish_path = target_out
    else:
        manifest = export_results(
            df=out_df,
            source_filename=input_path,
            output_dir=export_dir,
            render_panel=False,
        )
        effective_finish_path = manifest.timestamped_path

    if supabase_client.is_configured and default_learner.buffer_size > 0:
        flushed_count = await default_learner.flush_observations(supabase_client)
        if verbose and flushed_count > 0:
            console.print(
                f"  [bold cyan]☁️  [Supabase Memory][/] Synchronized {flushed_count} new market observations to cloud registry."
            )

    if verbose and records:
        render_summary_table(records)

    elapsed = time.perf_counter() - start_time
    if verbose:
        render_finish_banner(
            output_path=effective_finish_path,
            total_processed=len(records),
            elapsed_seconds=elapsed,
        )

    return out_df
````
