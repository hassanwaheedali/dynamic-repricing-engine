import re

import pandas as pd

df = pd.read_csv(r"tests\fixtures\test product list.csv")


def get_category(name):
    u = name.upper()
    # 1. Specific small appliances / blenders / juicers
    if any(
        k in u
        for k in [
            "JUICER",
            "BLENDER",
            "CHOPPER",
            "TOASTER",
            "KETTLE",
            "FOOD PROCESSOR",
            "CITRUS",
            "HAND BLENDER",
            "MIXER",
        ]
    ):
        return "SMALL_APPLIANCES"
    # 2. Air Fryer
    if any(k in u for k in ["AIR FRYER", "AIRFRYER", "AIR-FRYER"]):
        return "AIR_FRYER"
    # 3. Microwave Oven (check before washing machine so Dawlance MWO / DW- oven doesn't get confused)
    if any(
        k in u for k in ["MICROWAVE", " MWO ", "MWO-", "MWO ", "OVEN", "HMO-", "HMO ", "BAKING"]
    ):
        return "MICROWAVE_OVEN"
    if re.search(r"\bDW-(?:MD\d+|\d{3}|GSS|CHZP|AF|HZP)\b", u) and (
        "MICROWAVE" in u or "OVEN" in u or "GRILL" in u or "SOLO" in u or "LITRE" in u
    ):
        return "MICROWAVE_OVEN"
    # 4. Water Dispenser
    if any(k in u for k in ["DISPENSER", "WATER DISPENSER", "HWD", "WD "]):
        return "WATER_DISPENSER"
    # 5. LED TV
    if any(
        k in u
        for k in [
            "LED TV",
            "SMART TV",
            "ANDROID TV",
            "GOOGLE TV",
            "QLED",
            "OLED",
            "UHD TV",
            "4K TV",
            "TELEVISION",
        ]
    ) or re.search(r"\b\d{2}[\"']?\s*(?:LED|SMART|4K|UHD|TV)\b", u):
        return "LED_TV"
    # 6. Deep Freezer
    if (
        any(k in u for k in ["DEEP FREEZER", "CHEST FREEZER", "HDF-", "HDF ", "DF-", "FREEZER"])
        and "REFRIGERATOR" not in u
    ):
        return "DEEP_FREEZER"
    # 7. Washing Machine
    if any(
        k in u
        for k in [
            "WASHING MACHINE",
            "WASHER",
            "W/M",
            "HWM",
            "DWT",
            "TWIN TUB",
            "TOP LOAD",
            "FRONT LOAD",
            "SPINNER DRYER",
            "SINGLE TUB",
        ]
    ):
        return "WASHING_MACHINE"
    # 8. Air Conditioner (avoid matching 'capacity' or 'automatic' with raw 'AC')
    if (
        any(
            k in u
            for k in [
                "AIR CONDITIONER",
                "SPLIT",
                "PULAR",
                "FAIRY",
                "HEAT & COOL",
                "HEAT AND COOL",
                "COOL ONLY",
            ]
        )
        or re.search(r"\bAC\b", u)
        or re.search(r"\b\d(?:\.\d)?\s*TON\b", u)
        or re.search(r"\b(?:GS|HSU|ES|PINV)[- ]\d+", u)
    ):
        return "AIR_CONDITIONER"
    # 9. Refrigerator
    if any(
        k in u
        for k in [
            "REFRIGERATOR",
            "FRIDGE",
            "HRF",
            "REF",
            "CU FT",
            "CU.FT",
            "CFT",
            "DIRECT COOL",
            "DOUBLE DOOR",
            "SINGLE DOOR",
        ]
    ):
        return "REFRIGERATOR"
    return "SMALL_APPLIANCES"


def score_suspicion(row):
    name = str(row["Name"]).upper()
    score = 0
    # Modifiers
    if any(
        k in name
        for k in [
            "T3",
            "ES",
            "UV",
            "WIFI",
            "IOT",
            "SD",
            "GD",
            "GLASS DOOR",
            "INOX",
            "STAINLESS",
            "IAPA",
            "IFGA",
            "IPPA",
            "IDPA",
            "TIFG",
            "TIFB",
            "S6",
            "S8",
            "WB",
            "GB",
            "GC",
            "LVS",
        ]
    ):
        score += 4
    if any(c in name for c in ["/", "(", ")", "+"]):
        score += 3
    if any(
        k in name
        for k in [
            "NON-INVERTER",
            "FIXED SPEED",
            "FIX SPEED",
            "COOL ONLY",
            "HEAT & COOL",
            "HEAT AND COOL",
        ]
    ):
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
