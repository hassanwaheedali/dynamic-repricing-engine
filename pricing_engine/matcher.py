import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from pricing_engine.registry import (
    _SEED_DAWLANCE_CAPACITIES,
    _SEED_UNIVERSAL_CAPACITIES,
    InMemoryRegistry,
)

OPT_TAG_RE = re.compile(r"\[(?:OPT|ALLOW|IGNORE):([^\]]+)\]", re.IGNORECASE)


def extract_and_strip_opt_tags(text: str) -> tuple[str, set[str]]:
    """Extract [OPT:T3,QC0] tags and strip them before slot/query parsing."""
    allowed: set[str] = set()
    for m in OPT_TAG_RE.finditer(text):
        for tok in re.split(r"[,/| ]+", m.group(1)):
            if tok.strip():
                allowed.add(tok.strip().upper())
    cleaned = OPT_TAG_RE.sub(" ", text).strip()
    return cleaned, allowed


@dataclass
class GuardedFacets:
    """Zero-tolerance guarded attributes for strict variant collision protection."""

    capacity: str | None = None  # e.g. "1.5T", "12KG", "50INCH"
    tub_series: str | None = None  # e.g. "WB", "GB"
    color_family: str | None = None  # One of the 9 normalized color families
    color_raw: str | None = None  # Original matched color text
    door_finish: str | None = None  # Hardware finish: 'GD' (Glass Door) vs 'INOX' (Stainless Steel)
    cool_only: bool | None = None  # True if strictly cooling-only AC model
    heat_and_cool: bool | None = None  # True if Heat & Cool AC model
    door_type: str | None = (
        None  # Hardware door structure: 'SD' (Single Door) vs 'DD' (Double Door)
    )
    load_type: str | None = None  # Washer loading: 'FL' (Front Load) vs 'TL' (Top Load)
    tub_type: str | None = None  # Washer tub: 'TWIN' (Twin Tub) vs 'SINGLE' (Single Tub)
    automation_type: str | None = (
        None  # Washer automation: 'AUTO' (Fully Automatic) vs 'SEMI' (Semi Automatic)
    )
    defrost_type: str | None = None  # Refrigerator defrost: 'NO_FROST' vs 'DIRECT_COOL'
    is_inverter: bool | None = None  # True if Inverter, False if Non-Inverter / Fixed Speed
    capabilities: set[str] = field(
        default_factory=set
    )  # Additive hardware capabilities: T3, INVERTER, WIFI, IOT, ES, UV, ADS+
    negative_capabilities: set[str] = field(
        default_factory=set
    )  # Explicitly negated capabilities: Non-T3, Without-WiFi, Non-ADS+
    ambiguous_capabilities: set[str] = field(
        default_factory=set
    )  # Quarantined contradictory capabilities within same title: T3 + Non-T3
    allowed_feature_tags: set[str] = field(
        default_factory=set
    )  # Permitted optional hardware tags (e.g. T3, QC0)


@dataclass
class ProductSlots:
    """4-Slot structural attribute representation of a product title."""

    anchor: str  # Primary invariant alphanumeric model code (e.g. '120-826S6', '276EBS')
    series: str  # Dynamic series extracted via residual subtraction (e.g. 'MAGNA', 'CHROME PRO')
    guarded_facets: GuardedFacets
    residuals: list[str] = field(default_factory=list)  # Soft modifiers: 'GC', 'GLASS DOOR', etc.
    subordinate_codes: list[str] = field(default_factory=list)  # AC chassis/revision codes: '012DC(GE)'
    base_stem: str = ""  # Decomposed 2-digit capacity + 3-letter AC core series stem (e.g. '18HFP')
    sub_model_tag: str = ""  # Optional 1-2 letter AC sub-edition tag (e.g. 'CA', 'E')


@dataclass
class MatchDecision:
    """Detailed verdict and audit trail from the negative-collision referee."""

    is_match: bool
    reason: str
    target_slots: ProductSlots | None = None
    candidate_slots: ProductSlots | None = None
    is_base_match: bool = False
    missing_modifier: str | None = None
    modifier_source: str = "target"
    match_tier: int | None = None
    compatibility_notice: str | None = None


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
    "GT",  # Glass Top (e.g. Washing Machine Glass Top)
}


# 9 Normalized Color Families (ADR-002)
COLOR_FAMILIES: dict[str, list[str]] = {
    "White": [
        "OFF WHITE",
        "OFF-WHITE",
        "OCEAN WHITE",
        "MILKY WHITE",
        "PEARL WHITE",
        "WHITE",
        "MILKY",
        "IVORY",
    ],
    "Black": ["PIANO BLACK", "MATTE BLACK", "MIDNIGHT BLACK", "BLACK", "MIDNIGHT"],
    "Grey / Silver": [
        "DARK GREY",
        "DARK GRAY",
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
        "GOLDEN",
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

# Single and two-letter color suffix codes (e.g. G -> Golden, DG -> Dark Grey, W -> White)
COLOR_SUFFIX_MAP: dict[str, str] = {
    "W": "White",
    "B": "Black",
    "D": "Black",
    "S": "Grey / Silver",
    "G": "Gold / Bronze / Copper",
    "SG": "Gold / Bronze / Copper",
    "S-G": "Gold / Bronze / Copper",
    "SW": "White",
    "S-W": "White",
    "OW": "White",
    "DG": "Grey / Silver",
    "R": "Red / Maroon",
    "P": "Purple / Pink",
}

# Full name mapping for color initialisms
COLOR_CODE_FULL_NAMES: dict[str, str] = {
    "G": "Golden",
    "SG": "Golden",
    "S-G": "Golden",
    "DG": "Dark Grey",
    "OW": "Off White",
    "W": "White",
    "B": "Black",
    "S": "Silver",
    "R": "Red",
}


def normalize_color(title: str, anchor: str = "") -> tuple[str | None, str | None]:
    """Extract and normalize color into one of 9 canonical families with anchor isolation.

    Inviolability Rule: The internal letters of isolated alphanumeric anchors
    (e.g. 120-826S6, 276EBS) are never mutated or parsed as full color names.
    """
    title_search = re.sub(
        r"\b(?:R/F|D/F|W/M|W/D|M/O)\b",
        " ",
        _bind_standalone_measurement_units(title),
        flags=re.IGNORECASE,
    )
    is_washer_slash_wb = _detect_appliance_family(title) == "WASHING_MACHINE" or bool(
        re.search(r"\b(?:[A-Za-z]{2,4}[-_])?\d{2,3}-\d{3,4}/(?:WB|GB)\b", title, re.IGNORECASE)
    )
    has_slash_wood_brown = not is_washer_slash_wb and bool(
        re.search(r"(?<=\d)/WB(?=\b|[\s\-_()])", title_search, re.IGNORECASE)
    )
    if anchor:
        title_search = re.sub(rf"\b{re.escape(anchor)}\b", " ", title_search, flags=re.IGNORECASE)

    # Search for multi-word and single-word color tokens sorted by length descending
    # so compound phrases like 'DARK GREY' match before shorter words
    all_aliases: list[tuple[int, str, str]] = []
    for fam, aliases in COLOR_FAMILIES.items():
        for a in aliases:
            all_aliases.append((len(a), fam, a))
    all_aliases.sort(key=lambda x: x[0], reverse=True)
    for _, family, alias in all_aliases:
        if re.search(rf"\b{re.escape(alias)}\b", title_search, re.IGNORECASE):
            return family, alias

    if has_slash_wood_brown:
        return "Brown / Wood", "WB"

    # Detect parenthesized, hyphenated, or isolated color codes: (G), -G, (DG), -DG, (OW), (S-G), (W), (B), (S)
    # e.g. HSU-19HFS (G), HSU-19HFS-G, HSU-19HFS(G), HSU-19HFS (S-G), HSU-19HFS (DG), HSU-20HFTEX(OW)
    m_code = re.search(
        r"[\(\s\-_/](S[-_]?G|S[-_]?W|DG|OW|[WBSGDRP])(?=[\(\)\s\-_/]|$)",
        title_search,
        re.IGNORECASE,
    )
    if m_code:
        code = m_code.group(1).upper()
        code_fam = COLOR_SUFFIX_MAP.get(code)
        if code_fam:
            return code_fam, code

    # Fallback to trailing single/two-letter color code on model anchor (e.g. 12AITH21W -> W -> White, 20HFTEXOW -> OW -> White)
    if anchor:
        m_suf = re.search(
            r"(?:\d+[A-Za-z]+?\d+(S[-_]?G|S[-_]?W|DG|OW|[WBSGDRP])|\d{2,}[A-Za-z]{3,}(DG|OW))$",
            anchor,
            re.IGNORECASE,
        )
        if m_suf:
            letter = (m_suf.group(1) or m_suf.group(2)).upper()
            letter_fam = COLOR_SUFFIX_MAP.get(letter)
            if letter_fam:
                return letter_fam, letter
    m_glued_col = re.search(
        r"\b(?:[A-Za-z]{2,4}[-_])?\d{2,}[A-Za-z]{3,}(DG|OW)\b",
        title,
        re.IGNORECASE,
    )
    if m_glued_col:
        letter = m_glued_col.group(1).upper()
        letter_fam = COLOR_SUFFIX_MAP.get(letter)
        if letter_fam:
            return letter_fam, letter

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
        # Check single/two-letter color code on model anchor (e.g. 12AITH21W -> W -> White, 20HFTEXDG -> DG -> Grey / Silver)
        m_suf = re.search(
            r"(?:\d+[A-Za-z]+?\d+(DG|OW|[WBSGDRP])|\d{2,}[A-Za-z]{3,}(DG|OW))$",
            clean_tok,
            re.IGNORECASE,
        )
        if m_suf:
            letter = (m_suf.group(1) or m_suf.group(2)).upper()
            tok_fam = COLOR_SUFFIX_MAP.get(letter)
            if tok_fam:
                fams.add(tok_fam)
    return fams


# Strictly AC-anchored subordinate chassis/outdoor slash codes (e.g. HPU-48HE/012DC(GE)-T3, HSU-18HFP/023DC, 18HE/DC)
SUBORDINATE_AC_SLASH_RE = re.compile(
    r"\b([A-Za-z]{2,4}[-_]\d{2}[A-Za-z]{1,5}|\d{2}[A-Za-z]{2,5})"
    r"\s*/\s*"
    r"((?:\d{2,3}[A-Za-z]{1,4}|DC|AC)(?:\([A-Za-z0-9_-]{1,6}\))?)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

# Boundary-safe generic capability polarity scanner ((?!\w) preserves trailing '+' in ADS+)
CAPABILITY_POLARITY_PATTERN = re.compile(
    r"\b(?:(NON|NO|WITHOUT|NOT)[-_\s]*)?(T[-_\s]?[34]|UV|ADS\+?|WIFI|WI-FI|IOT|SMART)(?!\w)",
    re.IGNORECASE,
)


def _normalize_capability_token(raw_tok: str) -> str:
    """Normalize capability token while preserving trailing '+' on ADS+."""
    tok = re.sub(r"[-_\s]", "", raw_tok).upper()
    if tok == "WIFI":
        return "WIFI"
    if tok.startswith("ADS"):
        return "ADS+" if tok.endswith("+") else "ADS"
    return tok


# 2-digit BTU capacity + 3-letter core AC series stem + optional 1-2 letter sub-edition tag
AC_SKU_DECOMPOSITION_RE = re.compile(
    r"^(?:[A-Z]{2,4}[-_]?)?(\d{2}[A-Z]{3})([A-Z]{1,2})?$"
)


def _decompose_ac_sku(anchor: str, is_ac_context: bool) -> tuple[str, str]:
    """Decompose an AC SKU into (base_stem, sub_model_tag) when structurally valid."""
    if not anchor or not is_ac_context:
        return "", ""
    norm = re.sub(r"[^A-Za-z0-9\-_]", "", anchor.strip()).upper()
    m = AC_SKU_DECOMPOSITION_RE.match(norm)
    if not m:
        return "", ""
    base_stem = m.group(1)
    sub_tag = m.group(2) or ""
    btu_num = int(base_stem[:2])
    if not (9 <= btu_num <= 60):
        return "", ""
    return base_stem, sub_tag

# Category acronyms and fractions to safeguard from expansion
SAFEGUARD_PATTERN = re.compile(
    r"\b(?:W/M|W/D|D/F|R/F|M/O|A/C|H/C|H&C|W/O)\b"
    r"|\bHeat\s*/\s*Cool\b"
    r"|\b\d+/\d+\s*(?:\"|(?:inch|mm)\b)"
    r"|\b\d+W/\d+D\b"
    # Technical model suffixes: 18HE/DC, HBU-48E/DC, 48CE/DC, HPU-48HE/012DC(GE)-T3, HSU-18HFP/023DC
    rf"|{SUBORDINATE_AC_SLASH_RE.pattern}"
    r"|[A-Za-z0-9\-]+/(?:DC|AC)\b"
    r"|[A-Za-z0-9\-]+/\d{3}(?:DC|AC|GE)\b"
    r"|[A-Za-z0-9\-]+/T3[A-Za-z0-9\-]*\b"
    # Subordinate model codes: 24CE03/KB-01
    r"|[A-Za-z0-9\-]+/KB[-]?\d+"
    # Model year codes: GN-261/21, GNE-396/20, GND-1606/23 (require hyphen in model code)
    r"|[A-Z]{2,}-\d+/\d{2}\b"
    # Slash-attached finish/color/tub codes on 3+ digit appliance stems (e.g. DMB-91060/WB, DMB-91060/GD)
    r"|[A-Za-z0-9\-]*\d{3,}/(?:WB|GB|GD|SD|DD|OW|DG|SG|SW|[WBSGDRP])\b",
    re.IGNORECASE,
)

# Require an explicit delimiter before pure-letter trailing tags so SKUs like HSU-19HFPAA
# are never amputated to HSU-19HFP, while still stripping attached or delimited T3 tags (e.g. 17GT3, -T3).
TAG_PATTERN = re.compile(r"(?:[-_\s]*T3|[-_\s]+(?:AAA|AA\+|AA|PRO|ULTRA|PLUS))+$", re.IGNORECASE)

# Standard category and capacity phrases to strip from search queries
CATEGORY_PATTERNS = re.compile(
    r"\b(?:AWM|AUTO\s+W/M|FRONT\s+LOAD(?:ING)?(?:\s+W/M)?|TOP\s+LOAD(?:ING)?(?:\s+W/M)?|W/M|WASHING\s+MACHINE|WASH\s*(?:&|AND)\s*SPIN|SHOWER\s+RINSE|AIR\s+CONDITIONER|M/OVEN|M/O|MWO|D/F|R/F|W/D|SPLIT\s+AC|SPLIT|FLOOR(?:\s+STANDING)?|DISHWASHER|SPINNER|DRYER)\b"
    r"|\b(?:AIR\s*CURTAIN|AIR\s*COOLER|ROOM\s*COOLER|DESERT\s*COOLER|EVAPORATIVE\s*COOLER|AIR\s*FRYER|WATER\s+HEATER|INSTANT\s+GEYSER|GAS\s+GEYSER|ELECTRIC\s+GEYSER|GEYSER|WATER\s+DISPENSER|WATER\s+PURIFIER|INSECT\s+KILLER|JUG\s+KETTLE|HOT\s+PLATE|COOKING\s+RANGE|KITCHEN\s+HOOD|CHOPPER|BLENDER|IRON|LED|MICROWAVE|OVEN|SANDWI?T?CH\s+MAKER)\b"
    r"|\b(?:MINI\s*BAR|MINIBAR|ROOM\s*FRIDGE|BEDROOM\s*SERIES|REFRIGERATOR|FRIDGE|DEEP\s*FREEZER|CHEST\s*FREEZER|VERTICAL\s*FREEZER|FREEZER)\b"
    r"|\b(?:SINGLE\s*DOOR|DOUBLE\s*DOOR|TRIPLE\s*DOOR|FOUR\s*DOOR|FRENCH\s*DOOR|SIDE\s*BY\s*SIDE|SINGLE\s*TUB|TWIN\s*TUB|DOUBLE\s*TUB|TWIN\s*DOOR|DOUBLE\s*(?:WASHING\s*)?(?:MACHINE|WASHER))\b"
    r"|\b(?:FULLY\s+AUTOMATIC|SEMI[\s\-]*AUTOMATIC|AUTOMATIC|INVERTER|NORMAL|SERIES|DIGITAL|GLASS\s+DOOR|CLEAR\s+LID|OPAQUE(?:\s+LID)?|NO[\s\-]*FROST|CVT|SMART|WIFI|WI-FI|IOT|4K|8K|FHD|UHD|HD|QLED|OLED|GOOGLE\s*TV|ANDROID\s*TV|GAS\+ELECTRIC|BUILT-IN|FIX(?:ED)?\s*SPEED|ENERGY\s*SAVER|ENERGY\s*SAVING|ENERGY\s*SAVE|POWER\s*SAVER|ECO\s*SAVER|EXTENDED\s*DURABILITY|DURABILITY|SIGNATURE|REGULAR(?:\s+SERIES)?|STUCCO(?:\s+PCM)?|PCM)\b"
    r"|\b(?:HEATING|SOLO|GRILL|IN\s+GRILL|BEZEL\s*LESS|FRAMELESS)\b"
    r"|\b\d+(?:\.\d+)?[\s\-_]*(?:(?:TON|ΤΟΝ|KG|KGS|GM|LTR|LITRE|LITRES?|LITERS?|L|SETS|SETS?|FEET|FT|CU\s*FT|CU\.FT|CFT|CU|INCH(?:ES)?|MM|CM|WATTS?|GALLONS?|GAL)\b|[\"\'])",
    re.IGNORECASE,
)

# Common non-SKU unit stop-tokens
NON_SKU_TOKENS = {
    "TON",
    "ΤΟN",
    "KG",
    "GM",
    "LTR",
    "LITRE",
    "LITRES",
    "LTRS",
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
    "COD",
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
    "FREEZER",
    "DEEP",
    "SAVER",
    "SAVING",
    "MINIBAR",
    "MINI",
    "BAR",
    "TUB",
    "TWIN",
    "DOUBLE",
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
    "GOOGLE",
    "ANDROID",
    "INCHES",
    "MODEL",
    "DOT",
    "UPTO",
    "HUB",
    "ONLY",
    "SERIES",
    "SPLIT",
    "SAVEIN",
    "SAVE",
    "TAP",
    "TAPS",
    "BTU",
    "RPM",
    "AMP",
    "AMPS",
    "VOLT",
    "VOLTS",
    "WATT",
    "WATTS",
    "CUFT",
    "WI",
    "FI",
    "PCM",
    "STUCCO",
    "ARC",
    "GIFT",
    "DEAL",
    "PROMO",
    "OFFER",
    "ITEM",
    "PIECE",
    "STOCK",
    "PRICE",
    "BRAND",
    "ORIGINAL",
    "WARRANTY",
    "REGULAR",
    "EXTENDED",
    "DURABILITY",
    "SIGNATURE",
    "FULLY",
    "AUTOMATIC",
    "LOADING",
    "DIRECT",
    "DRIVE",
    "MOUNT",
    "MOUNTED",
    "COOLING",
    "PLASTIC",
    "METAL",
    "WOOD",
    "RUST",
    "PROOF",
    "HEAVY",
    "DUTY",
    "GARMENT",
    "STEAMER",
    "DISPENSER",
    "CHAMBER",
    "CAPACITY",
    "DESIGN",
    "SYMPHONY",
    "BUDS",
    "AIRBUDS",
    "EARBUDS",
    "HEADPHONES",
    "RINSE",
    "SHOWER",
    "KARACHI",
    "LAHORE",
    "ISLAMABAD",
    "RAWALPINDI",
    "FAISALABAD",
    "MULTAN",
    "PESHAWAR",
    "HYDERABAD",
    "QUETTA",
    "SIALKOT",
    "GUJRANWALA",
    "PAKISTAN",
    "CITIES",
    "MAIN",
    "NOISE",
    "SILENT",
    "QUIET",
    "ENERGY",
    "ESTAR",
    "STAR",
    "NON",
    "FEES",
    "PROCESSING",
    "MARK",
    "INSTALLATION",
    "UPS",
    "ENABLED",
    "ENABLE",
    "SELF",
    "CLEAN",
    "CLEANING",
    "TURBO",
    "AMPERE",
    "YEARS",
    "TECH",
    "HOUSE",
}

GENUINE_SUB_SERIES_TOKENS = {
    "PRO",
    "PLUS",
    "MAX",
    "ULTRA",
    "CLASSIC",
    "ELEGANT",
    "PRIMA",
    "PRIME",
    "X",
    "LITE",
    "SUPER",
    "TOUCH",
    "II",
    "III",
    "IV",
}

_PLUS_SERIES_EXCLUDED_LEFT: frozenset[str] = frozenset(
    {
        "A",
        "AA",
        "AAA",
        "ADS",
        "GAS",
        "WASH",
        "WASHER",
        "WASHING",
        "SPIN",
        "SPINNER",
        "DRYER",
        "HEAT",
        "COOL",
        "INVERTER",
        "DC",
        "AC",
        "SMART",
        "SELF",
        "CLEANING",
        "UPS",
        "TURBO",
        "WIFI",
        "IOT",
        "FREE",
        "WARRANTY",
        "DELIVERY",
        "INSTALLATION",
        "T3",
        "T4",
    }
)

_PROSE_SLASH_NEIGHBOR_WORDS: frozenset[str] = frozenset(
    {
        "TON",
        "TONS",
        "SERIES",
        "INVERTER",
        "CONDITIONER",
        "AC",
        "AIR",
        "SPLIT",
        "WARRANTY",
        "INSTALLATION",
        "INSTALLA",
        "INSTALLATIO",
        "DELIVERY",
        "YEAR",
        "YEARS",
        "MONTH",
        "MONTHS",
        "FREE",
        "OFFICIAL",
        "KG",
        "KGS",
        "CFT",
        "REFRIGERATOR",
        "MACHINE",
        "COLOUR",
        "COLOR",
    }
)


def _canonicalize_plus_series(text: str) -> str:
    """Canonicalize meaningful Plus-series designations ('Avante+' -> 'Avante PLUS',
    'GLAMOUR + INVERTER 45' -> 'GLAMOUR PLUS INVERTER 45') without conflating multi-feature
    marketing lists ('( Smart DC Inverter + Self Cleaning + UPS )'), energy ratings ('AA+'),
    or AC 'T3 Plus' compressor badges."""
    if not text:
        return text

    # 1. Normalize AC 'T3 Plus' / 'T3+' tropical compressor badge -> 'T3'
    t = re.sub(r"\bT[-_\s]?3\s*(?:\+|\bPLUS\b)", "T3", text, flags=re.IGNORECASE)

    if "+" not in t:
        return t

    # 2. Mask parenthetical feature lists containing '+' so '( A + B + C )' never creates 'PLUS'
    masked_parens: list[str] = []

    def _mask_paren(m: re.Match[str]) -> str:
        inner = m.group(0)
        if "+" in inner:
            masked_parens.append(inner)
            return f"__PARENPLUS_{len(masked_parens) - 1}__"
        return inner

    t = re.sub(r"\([^)]*\)", _mask_paren, t)

    # 3. Direct attached plus on series word: 'Avante+' -> 'Avante PLUS', 'Glamour+' -> 'Glamour PLUS'
    def _replace_attached_plus(m: re.Match[str]) -> str:
        word = m.group(1)
        if word.upper() in _PLUS_SERIES_EXCLUDED_LEFT:
            return m.group(0)
        return f"{word} PLUS "

    t = re.sub(r"\b([A-Za-z]{3,})\+(?![A-Za-z0-9+])", _replace_attached_plus, t)

    # 4. Single spaced plus following a series word when not a multi-plus feature list:
    # e.g. 'GLAMOUR + INVERTER 45' -> 'GLAMOUR PLUS INVERTER 45'
    if t.count("+") == 1:

        def _replace_spaced_plus(m: re.Match[str]) -> str:
            left_w = m.group(1)
            right_w = m.group(2)
            if (
                left_w.upper() in _PLUS_SERIES_EXCLUDED_LEFT
                or left_w.upper() in NON_SKU_TOKENS
                or right_w.upper() in {"SPIN", "SPINNER", "DRYER"}
            ):
                return m.group(0)
            return f"{left_w} PLUS {right_w}"

        t = re.sub(r"\b([A-Za-z]{3,})\s+\+\s+([A-Za-z0-9]+)\b", _replace_spaced_plus, t)

    for idx, orig in enumerate(masked_parens):
        t = t.replace(f"__PARENPLUS_{idx}__", orig)
    return re.sub(r"\s{2,}", " ", t).strip()


def _tokenize_series_words(text: str) -> set[str]:
    """Canonical series tokenizer splitting hyphenated generation/series names consistently."""
    if not text:
        return set()
    canon = _canonicalize_plus_series(text)
    return set(re.findall(r"[A-Z0-9]+", canon.upper()))


def _join_spaced_ac_btu_sku(text: str) -> str:
    """Join spaced AC BTU capacity prefix and uppercase SKU model suffix (e.g. '24 HFAB' -> '24HFAB',
    '20 HFTEX' -> '20HFTEX', 'HSU-14 HFTEX-T3' -> 'HSU-14HFTEX-T3') without touching series names."""
    if not text:
        return text
    # 1. Explicit prefixed AC model with space after 2-digit BTU code: 'HSU-14 HFTEX-T3' -> 'HSU-14HFTEX-T3'
    t = re.sub(
        r"\b([A-Za-z]{2,4}[-_]\d{2})\s+([A-Z]{2,7}(?:[-_][A-Za-z0-9]{1,5})?)\b",
        lambda m: (
            f"{m.group(1)}{m.group(2)}"
            if m.group(2).split("-")[0].upper() not in NON_SKU_TOKENS
            and m.group(2).split("-")[0].upper() not in GENUINE_SUB_SERIES_TOKENS
            and not is_color_token(m.group(2).split("-")[0])
            else m.group(0)
        ),
        text,
    )
    has_lower = any(c.islower() for c in t)

    def _join_unprefixed(m: re.Match[str]) -> str:
        btu, code = m.group(1), m.group(2)
        base_code = re.split(r"[-_]", code)[0]
        base_u = base_code.upper()
        if (
            base_u in NON_SKU_TOKENS
            or base_u in GENUINE_SUB_SERIES_TOKENS
            or is_color_token(base_u)
            or base_u in {"T3", "T4", "INV", "INVERTER", "SERIES", "SPLIT", "TON", "WIFI", "IOT"}
        ):
            return m.group(0)
        has_digit_or_hyph = bool(re.search(r"[\d\-_]", code))
        vowels = len(re.findall(r"[AEIOU]", base_u))
        non_english_cluster = bool(
            re.match(r"^[BCDFGHJKMNPQSTVWXZ]{2}", base_u)
            and not base_u.startswith(("SP", "ST", "PR", "TR", "CR", "FR", "GL", "FL", "PL", "SM"))
        )
        if (
            has_digit_or_hyph
            or (has_lower and code.isupper() and vowels <= 1)
            or (vowels == 0 or (vowels <= 1 and non_english_cluster))
        ):
            return f"{btu}{code}"
        return m.group(0)

    return re.sub(
        r"\b(09|1[2-4]|1[89]|2[048]|3[06]|48)\s+([A-Z]{2,7}(?:[-_][A-Za-z0-9]{1,5})?)\b",
        _join_unprefixed,
        t,
    )


def _normalize_ac_transposed_cap_x(text: str, brand: str = "") -> str:
    """Normalize transposed and glued AC series capacity+X notation ('Aura 15X', 'Sprinter 15 X', 'Sprinter X15' -> 'Sprinter X 15') in AC titles."""
    if _detect_appliance_family(text) != "AIR_CONDITIONER" and not re.search(
        r"\b(?:TON|ΤΟN|SPLIT\s+AC|AIR\s+CONDITIONER)\b", text, re.IGNORECASE
    ):
        return text
    cap_codes = set(UNIVERSAL_CAPACITY_TO_TONNAGE.keys()).union(
        *(m.keys() for m in BRAND_CAPACITY_SYSTEMS.values())
    )

    def _repl(m: re.Match[str]) -> str:
        prev_w, cap_num = m.group(1), m.group(2)
        if (
            cap_num in cap_codes
            and prev_w.upper() not in NON_SKU_TOKENS
            and (
                any(c.islower() for c in prev_w) or len(re.findall(r"[AEIOU]", prev_w.upper())) >= 2
            )
        ):
            return f"{prev_w} X {cap_num}"
        return m.group(0)

    # 1. Glued suffix: 'Sprinter 15X' -> 'Sprinter X 15'
    t = re.sub(r"\b([A-Za-z]{3,})\s+(\d{2})[xX]\b", _repl, text)
    # 2. Spaced transposition: 'Sprinter 15 X' -> 'Sprinter X 15'
    t = re.sub(r"\b([A-Za-z]{3,})\s+(\d{2})\s+[xX]\b", _repl, t)
    # 3. Glued prefix: 'Sprinter X15' -> 'Sprinter X 15'
    t = re.sub(r"\b([A-Za-z]{3,})\s+[xX](\d{2})\b", _repl, t)
    return t


MERCHANT_TRACKING_CODE_RE = re.compile(
    r"\s*\((?:ISPK|SNS|SKU|ID|NS|UE)[-_]?[A-Za-z0-9]+\)\s*|\b(?:ISPK|SNS|SKU|ID|NS|UE)[-_]?[A-Za-z0-9]+\b",
    re.IGNORECASE,
)

# Generic marketplace noise (seller signatures, promotions, payment terms, HVAC operational phrases)
MARKETPLACE_NOISE_RE = re.compile(
    r"(?:(?<!\w)0%\s*(?:MARK\s*UP|PROCESSING\s*FEES?)\b|\b(?:ON\s+INSTALLMENT|INSTALLMENT|MARK\s*UP|MARKUP|PROCESSING\s*FEES?|INTEREST|DOWN\s*PAYMENT|EMI|CASH\s+ON\s+DELIVERY|COD)\b|(?<!\w)0%(?!\w))"
    r"|\b(?:UPTO\s+\d+\s*MONTHS?|\d+\s*MONTHS?|UPTO|MONTHLY|PER\s+MONTH)\b"
    r"|\b(?:FREE\s+(?:HOME\s+)?DELIVERY|FAST\s+DELIVERY|DELIVERY|SHIPPING|EXPRESS|FREE\s+INSTALLATION)\b"
    r"|\b(?:OFFICIAL\s+WARRANTY|BRAND\s+WARRANTY|COMPANY\s+WARRANTY|WARRANTY\s+CARD|WARRANTY|\d+\s*YEARS?\s+WARRANTY)\b"
    r"|\b(?:SALE|DISCOUNT|DEAL|OFFER|PROMO|PROMOTION|RAMADAN\s+OFFER|EID\s+OFFER|SUPER\s+SALE)\b"
    r"|\b(?:ORIGINAL|AUTHENTIC|GENUINE|BRAND\s+NEW|SEALED\s+PACK|SEALED|BOX\s+PACK|100%\s*ORIG(?:I)?NAL)\b"
    r"|\b(?:SPECIAL\s+GIFT|SURPRISE\s+GIFT|FREE\s+GIFT|GIFT\s+PACK|GIFT|BEST\s+PRICE)\b"
    r"|\b(?:WITH\s+)?FREE\s+(?:AIR\s*BUDS|EARBUDS|BUDS|GIFT|HEADPHONES|SURPRISE\s*GIFT)\b"
    r"|\s*\(\s*(?:with\s+)?(?:free\s+)?(?:gift|air\s*buds|earbuds|buds|watch|speakers?|discount|voucher|surprise)[^)]*\)"
    r"|\b(?:QUANTUM\s+DOT|QUANTUM|TECHNOLOGY)\b"
    r"|\b(?:ELECTROEASE|HOMECART|METRO|HYPERSTAR|ALFAMALL|FAYSAL\s*BANK|QISTBAZAAR|ESBUY|TELEMART|YAYVO)\b"
    r"|\b(?:HEAT\s*(?:&|AND|/)\s*COOL|HE\s*(?:&|AND)\s*COOL|H\s*&\s*C|COOLING\s*ONLY|COOL\s*ONLY)\b"
    r"|\b(?:INVERTER\s*AC|DC\s*INVERTER|FIX(?:ED)?\s*SPEED|NON[\s\-]*INVERTER|E[\s\-]*STAR)\b"
    r"|\b(?:AAA\+|AA\+|A\+{1,3}|AAA|AA)\b"
    r"|\b(?:FOR\s+[A-Za-z]+\s+ONLY)\b"
    rf"|{MERCHANT_TRACKING_CODE_RE.pattern}",
    re.IGNORECASE,
)


def _is_dawlance_context(text: str, brand: str = "") -> bool:
    """Return True when catalog brand or leading title brand token is Dawlance."""
    b_norm = (brand or "").strip().upper()
    if b_norm in {"DAWLANCE", "DAW"}:
        return True
    return bool(re.match(r"^\s*(?:DAWLANCE|DAW)\b", text or "", re.IGNORECASE))


_UNAMBIGUOUS_MULTI_LETTER_UNITS_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s+(WATTS?|KGS?|RPM|LTRS?|LITRES?|LITERS?|TONS?|BTU|CFT|CUFT|VOLTS?|AMPS?|HZ)\b",
    re.IGNORECASE,
)
_SINGLE_LETTER_WL_UNIT_RE = re.compile(
    r"(?<![A-Za-z0-9\-_/.])(\d+(?:\.\d+)?)\s+([WL])\b",
    re.IGNORECASE,
)
def _has_earlier_model_anchor(prefix_text: str) -> bool:
    """Return True only when prefix_text contains a genuine non-dimension model stem."""
    for m_sp in re.finditer(r"\b([A-Za-z]{2,4})\s+(\d{3,6})\b", prefix_text):
        pfx_w = m_sp.group(1)
        if pfx_w.upper() not in NON_SKU_TOKENS and not is_color_token(pfx_w):
            return True
    for raw_tok in prefix_text.split():
        tok_c = raw_tok.strip("()[].,\"'|")
        if not tok_c or is_dimension_or_spec_token(tok_c):
            continue
        if re.match(
            r"^(?:[A-Za-z]{1,5}[-_]\d{2,}[A-Za-z0-9\-_]*|[A-Za-z]{2,5}\d{2,}[A-Za-z0-9\-_]*|\d{2,}[A-Za-z]{2,}[A-Za-z0-9\-_]*|\d{4,6})$",
            tok_c,
        ):
            return True
    return False


def _bind_standalone_measurement_units(text: str) -> str:
    """Bind standalone measurement units without swallowing trailing 'W'/'L' SKU/color suffixes."""
    if not text:
        return text
    t = _UNAMBIGUOUS_MULTI_LETTER_UNITS_RE.sub(r"\1\2", text)

    def _bind_wl(m: re.Match[str]) -> str:
        num_str, unit_ch = m.group(1), m.group(2)
        if "." in num_str:
            return f"{num_str}{unit_ch}"
        if unit_ch.upper() == "W" and len(num_str) >= 5:
            return m.group(0)
        prefix_text = t[: m.start()]
        prev_tokens = prefix_text.split()
        prev_raw = prev_tokens[-1].strip("()[].,\"'|") if prev_tokens else ""
        if prev_raw and re.match(r"^[A-Za-z]{2,4}$", prev_raw) and prev_raw.upper() not in NON_SKU_TOKENS:
            return m.group(0)
        if prev_raw.isdigit() and 50 <= int(prev_raw) <= 250:
            return m.group(0)
        m_pref_drum = re.match(r"^[A-Za-z]{2,4}[-_](\d{2,3})$", prev_raw)
        if m_pref_drum and 50 <= int(m_pref_drum.group(1)) <= 250:
            return m.group(0)
        if _has_earlier_model_anchor(prefix_text):
            return f"{num_str}{unit_ch}"
        return m.group(0)

    return _SINGLE_LETTER_WL_UNIT_RE.sub(_bind_wl, t)


def normalize_technical_slashes(text: str) -> str:
    """Normalize technical compound codes (/DC, /AC, /Z, etc.) and screen units while preserving model boundaries."""
    t = text
    # 24 HD/Z -> 24 HDZ
    t = re.sub(r"\b([A-Za-z0-9]+)/Z\b", r"\1Z", t, flags=re.IGNORECASE)
    # Technical compressor/electrical codes (18HE/DC -> 18HE-DC, 48CE/DC -> 48CE-DC, 24 HE/DC -> 24 HE-DC)
    # Only applies to known technical codes HE/DC, CE/DC, GE/DC, etc. or when preceded by 2-digit capacity
    t = re.sub(
        r"\b((?:\d{2}\s*)?(?:HE|CE|GE|SE|HBU|HCF|P|C))/(DC|AC)\b", r"\1-\2", t, flags=re.IGNORECASE
    )
    t = re.sub(r"\bH\s*&\s*C\b", "Heat and Cool", t, flags=re.IGNORECASE)
    t = re.sub(r"\bH/C\b", "Heat and Cool", t, flags=re.IGNORECASE)
    t = re.sub(r"\bR/F\b", "Refrigerator", t, flags=re.IGNORECASE)
    t = re.sub(r"\bD/F\b", "Deep Freezer", t, flags=re.IGNORECASE)
    t = re.sub(r"\bW/M\b", "Washing Machine", t, flags=re.IGNORECASE)
    t = re.sub(r"\bW/D\b", "Water Dispenser", t, flags=re.IGNORECASE)
    t = re.sub(r"\bM/O\b", "Microwave Oven", t, flags=re.IGNORECASE)
    t = re.sub(r"\bA/C\b", "AC", t, flags=re.IGNORECASE)
    t = re.sub(r"\bWI[\s\-]+FI\b", "WIFI", t, flags=re.IGNORECASE)
    return normalize_screen_units(t)


def normalize_screen_units(text: str) -> str:
    """Canonicalise screen-size notation: 32" / 32-inch / 32 Inches -> '32 INCH'.
    Fractions such as 1/2" or 12/16" (pipe sizes) are left untouched."""
    t = re.sub(
        r"(?<![\d./])(\d{2,3})\s*-?\s*(?:INCHES|INCH)\b", r"\1 INCH", text, flags=re.IGNORECASE
    )
    t = re.sub(r"(?<![\d./])(\d{2,3})\s*(?:\"|\u201d|\u2033)", r"\1 INCH", t)
    return t


def expand_cartesian_branches(title: str) -> list[str]:
    """If title contains slash-separated alternative models/variants, expand into independent branches."""
    t_norm = normalize_technical_slashes(title)
    # 0. Detect model followed by slash-separated variant tags (e.g. 'HPU-24HDZ CA/DC', 'DF-400 EDS/ES')
    # Preserves alternative sister variant models like HPU-24HDZCA vs HPU-24HDZDC
    m_var_slash = re.search(
        r"\b([A-Za-z]{2,4}[-_]?[A-Za-z0-9]+)\s+([A-Za-z0-9]{2,4})\s*/\s*([A-Za-z0-9]{2,4})\b",
        t_norm,
    )
    if (
        m_var_slash
        and re.search(r"\d", m_var_slash.group(1))
        and not SUBORDINATE_AC_SLASH_RE.search(m_var_slash.group(0))
    ):
        base, v1, v2 = m_var_slash.group(1), m_var_slash.group(2), m_var_slash.group(3)
        b1_glued = t_norm[: m_var_slash.start()] + f"{base}{v1}" + t_norm[m_var_slash.end() :]
        b1_spaced = t_norm[: m_var_slash.start()] + f"{base} {v1}" + t_norm[m_var_slash.end() :]
        b2_glued = t_norm[: m_var_slash.start()] + f"{base}{v2}" + t_norm[m_var_slash.end() :]
        b2_spaced = t_norm[: m_var_slash.start()] + f"{base} {v2}" + t_norm[m_var_slash.end() :]
        return list(
            dict.fromkeys(
                [b1_glued.strip(), b1_spaced.strip(), b2_glued.strip(), b2_spaced.strip()]
            )
        )

    # Glued model slash: e.g. HPU-24HDZCA/DC (both sister tags alphabetic, never slicing numeric stems like DMB-91060/WB)
    m_glued_var_slash = re.search(
        r"\b([A-Za-z]{2,4}[-_]?[A-Za-z0-9]+?)([A-Za-z]{2,4})\s*/\s*([A-Za-z]{2,4})\b",
        t_norm,
    )
    if m_glued_var_slash:
        base, v1, v2 = (
            m_glued_var_slash.group(1),
            m_glued_var_slash.group(2),
            m_glued_var_slash.group(3),
        )
        if (
            len(base) >= 5
            and re.search(r"\d", base)
            and not SUBORDINATE_AC_SLASH_RE.search(m_glued_var_slash.group(0))
        ):
            b1_glued = (
                t_norm[: m_glued_var_slash.start()]
                + f"{base}{v1}"
                + t_norm[m_glued_var_slash.end() :]
            )
            b2_glued = (
                t_norm[: m_glued_var_slash.start()]
                + f"{base}{v2}"
                + t_norm[m_glued_var_slash.end() :]
            )
            return list(dict.fromkeys([b1_glued.strip(), b2_glued.strip()]))

    safeguards: list[str] = []

    def mask_fn(m: re.Match[str]) -> str:
        safeguards.append(m.group(0))
        return f"__SAFEGUARD_{len(safeguards) - 1}__"

    t_masked = SAFEGUARD_PATTERN.sub(mask_fn, t_norm)

    # Convert prose breadcrumb slashes (e.g. '1 Ton / Flexis Inverter Series / HSU-13HFCP',
    # 'Air Conditioner / AC / 10 Year Warranty') into pipe delimiters so SKU/capacity tokens are
    # never amputated across false Cartesian branches, while preserving genuine model/series/color slashes.
    def _replace_prose_slash(m: re.Match[str]) -> str:
        left_tok = m.group(1).strip("()[]-.,_ \"'").upper()
        right_tok = m.group(2).strip("()[]-.,_ \"'").upper()
        if (
            left_tok in _PROSE_SLASH_NEIGHBOR_WORDS
            or right_tok in _PROSE_SLASH_NEIGHBOR_WORDS
            or is_dimension_or_spec_token(left_tok)
            or is_dimension_or_spec_token(right_tok)
        ):
            return f"{m.group(1)} | {m.group(2)}"
        return m.group(0)

    for _ in range(3):
        updated_t = re.sub(
            r"(\b[A-Za-z0-9\-_%]+)\s*/\s*([A-Za-z0-9\-_%]+\b)",
            _replace_prose_slash,
            t_masked,
        )
        if updated_t == t_masked:
            break
        t_masked = updated_t

    # Detect N-way (>= 3) slash chains first (e.g. 'White / Silver / Black' -> 3 clean branches)
    m_multi_chain = re.search(
        r"\b[A-Za-z0-9\-_]+(?:\s*/\s*[A-Za-z0-9\-_]+){2,}\b",
        t_masked,
    )
    branches: list[str]
    if m_multi_chain:
        chain_parts = [p.strip() for p in m_multi_chain.group(0).split("/") if p.strip()]
        if all(len(p) >= 2 and not p.startswith("__SAFEGUARD_") for p in chain_parts):
            branches = list(
                dict.fromkeys(
                    (
                        t_masked[: m_multi_chain.start()] + part + t_masked[m_multi_chain.end() :]
                    ).strip()
                    for part in chain_parts
                )
            )
        else:
            branches = [t_masked.strip()]
    else:
        # Detect alternative model codes separated by slash:
        # e.g. 'HRF-418 TIFG1U1/TIFB1U1 (IOT)' or 'HGL-25MXP8 / 25MXP9' or '30 Sprinter / Powercon'
        # or paired slashes: 'HRF-346 EPR/EPB (Red/Black)'
        slashes = list(re.finditer(r"(\b[A-Za-z0-9\-_]+)\s*/\s*([A-Za-z0-9\-_]+)", t_masked))
        if len(slashes) >= 2 and all(
            len(s.group(1)) >= 2
            and len(s.group(2)) >= 2
            and not s.group(1).startswith("__SAFEGUARD_")
            and not s.group(2).startswith("__SAFEGUARD_")
            for s in slashes[:2]
        ):
            s1, s2 = slashes[0], slashes[1]
            b1 = (
                t_masked[: s1.start()]
                + s1.group(1)
                + t_masked[s1.end() : s2.start()]
                + s2.group(1)
                + t_masked[s2.end() :]
            ).strip()
            b2 = (
                t_masked[: s1.start()]
                + s1.group(2)
                + t_masked[s1.end() : s2.start()]
                + s2.group(2)
                + t_masked[s2.end() :]
            ).strip()
            branches = [b1, b2]
        elif len(slashes) == 1:
            m_slash = slashes[0]
            left = m_slash.group(1).strip()
            right = m_slash.group(2).strip()
            if (
                len(left) >= 2
                and len(right) >= 2
                and not left.startswith("__SAFEGUARD_")
                and not right.startswith("__SAFEGUARD_")
            ):
                b1 = t_masked[: m_slash.start()] + left + t_masked[m_slash.end() :]
                b2 = t_masked[: m_slash.start()] + right + t_masked[m_slash.end() :]
                branches = [b1.strip(), b2.strip()]
                if "-" in left:
                    pfx, stem_left = left.rsplit("-", 1)
                    branches.append(
                        (
                            t_masked[: m_slash.start()] + stem_left + t_masked[m_slash.end() :]
                        ).strip()
                    )
                    branches.append(
                        (
                            t_masked[: m_slash.start()]
                            + f"{pfx}-{right}"
                            + t_masked[m_slash.end() :]
                        ).strip()
                    )
                branches = list(dict.fromkeys(branches))
            else:
                branches = [t_masked.strip()]
        else:
            branches = [t_masked.strip()]

    restored_branches: list[str] = []
    for b in branches:
        for idx, orig in enumerate(safeguards):
            b = b.replace(f"__SAFEGUARD_{idx}__", orig)
        restored_branches.append(b)

    return restored_branches


_EXPLICIT_SELLER_TRAILER_RE = re.compile(
    r"^(?:By|From|Sold\s+By)\b|\b(?:Official\s+Store|Pvt\.?\s+Ltd\.?|Traders?|Electronics?\s+Store|Mart|Emporium|Installments?|0%\s*Markup|Free\s+Delivery)\b",
    re.IGNORECASE,
)

_HARDWARE_SPEC_TRAILER_RE = re.compile(
    r"\b(?:COOL\s+ONLY|COOLING\s+ONLY|ONLY\s+COOL|HEAT\s*(?:&|AND|/)\s*COOL|H\s*&\s*C|H/C"
    r"|TWIN[\s\-]*TUB|DOUBLE[\s\-]*TUB|SINGLE[\s\-]*TUB|TOP\s*LOAD(?:ING)?|FRONT\s*LOAD(?:ING)?"
    r"|(?:FULLY|SEMI)[\s\-]*AUTO(?:MATIC)?"
    r"|GLASS\s+DOOR|METAL\s+DOOR|STEEL\s+DOOR|VCM\s+DOOR|INOX|STAINLESS\s+STEEL"
    r"|SINGLE\s+DOOR|DOUBLE\s+DOOR|SIDE\s+BY\s+SIDE"
    r"|NO[\s\-]*FROST|FROST[\s\-]*FREE|DIRECT[\s\-]*COOL"
    r"|CLEAR\s+(?:FLAT\s+)?LID|GLASS\s+(?:FLAT\s+)?LID|WHITE\s+(?:FLAT\s+)?LID|PILLOW\s+DRUM"
    r"|NON[\s\-]*INVERTER|FIX(?:ED)?\s*SPEED|DC\s*INVERTER|INVERTER"
    r"|FLOOR\s*STANDING|WALL\s*MOUNT(?:ED)?|CABINET|CASSETTE|PORTABLE"
    r"|T[-_\s]?[34]|ADS\+?|WIFI|WI-FI|IOT|LVS|GD|WB|GB|SD|DD|FL|TL|CFL|WFL)\b",
    re.IGNORECASE,
)

_SELLER_SINGLE_TOKEN_STOP_WORDS: set[str] = {
    "ET",
    "ISPK",
    "COD",
    "EMI",
    "NEW",
    "SALE",
    "DEAL",
    "GIFT",
    "FREE",
}


def _is_product_spec_trailer(segment: str) -> bool:
    """Return True if a trailing hyphen/pipe clause carries genuine hardware, SKU, capacity, or color data."""
    clean_seg = segment.strip(" -–—|()[]")
    if not clean_seg:
        return False
    if _EXPLICIT_SELLER_TRAILER_RE.search(clean_seg):
        return False
    if _HARDWARE_SPEC_TRAILER_RE.search(clean_seg):
        return True
    if re.search(
        r"\b\d+(?:\.\d+)?\s*[-]?\s*(?:kg|kgs|ton|tons|ΤΟN|ltr|ltrs|liter|liters|litre|litres|cft|cu\s*ft|cu\.ft|inch|inches|ft|feet|w|watts?|v|volts?|hz|btu|taps?)\b",
        clean_seg,
        re.IGNORECASE,
    ):
        return True
    # Preserve segments containing genuine SKU model identifiers (letters + >= 2 consecutive digits, e.g. DWT1016-PRIMA, GF-36TFIH, Sprinter 15)
    if re.search(
        r"\b(?:[A-Za-z]{1,5}[-_]?\d{2,}[A-Za-z0-9\-_]*|\d{2,}[A-Za-z]{1,5}[A-Za-z0-9\-_]*|[A-Za-z]{3,}\s+\d{2,})\b",
        clean_seg,
    ):
        return True
    if clean_seg.isdigit():
        return True
    seg_words = [w.strip(".,'\"/()") for w in clean_seg.split() if w.strip(".,'\"/()")]
    if seg_words and all(is_color_token(w) for w in seg_words):
        return True
    if len(seg_words) == 1:
        tok = seg_words[0]
        if tok.upper() in _SELLER_SINGLE_TOKEN_STOP_WORDS:
            return False
        if is_dimension_or_spec_token(tok) or is_sku_variant_tag(tok):
            return True
    return False


def _strip_trailing_seller_clauses(text: str) -> str:
    """Iteratively strip rightmost pipe/dash seller/promo clauses while preserving genuine hardware specs."""
    cur = text.strip()
    for _ in range(8):
        m = re.search(
            r"(?:\s+[-–—]|\s*\|)\s*(?:(By\s+|From\s+|Official\s+))?[^|–—\-\n]{2,}$",
            cur,
            flags=re.IGNORECASE,
        )
        if not m:
            break
        seg = m.group(0).strip(" -–—|")
        is_explicit_seller = bool(m.group(1)) or bool(_EXPLICIT_SELLER_TRAILER_RE.search(seg))
        if not is_explicit_seller and _is_product_spec_trailer(seg):
            break
        has_digits = bool(re.search(r"\d", seg))
        is_pipe = "|" in m.group(0)
        if is_explicit_seller or not has_digits or is_pipe:
            cur = cur[: m.start()].strip()
        else:
            break
    return cur


def clean_marketplace_noise(text: str) -> str:
    """Strip common e-commerce noise (seller signatures, promos, payment terms, HVAC operational tags)."""
    # 1. Structural promotional and transactional expressions first (so Non-Inverter / E-Star are not split at "-")
    t = MARKETPLACE_NOISE_RE.sub(" ", text.strip()).strip()
    # 2. Right-to-left pipe and dash seller/marketing trailers (preserving genuine hardware specification clauses)
    t = _strip_trailing_seller_clauses(t)
    t = re.sub(r"\s+\b(?:By|From)\s+[A-Z][A-Za-z0-9\s.]{2,}$", "", t, flags=re.IGNORECASE)
    t = _bind_standalone_measurement_units(t)
    return re.sub(r"\s+", " ", MARKETPLACE_NOISE_RE.sub(" ", t)).strip()


def is_dimension_or_spec_token(token: str) -> bool:
    """Check if a token represents physical dimensions, capacity, or feature counts instead of a model code."""
    clean = token.strip("-_., \"'")
    if not clean:
        return True
    if re.match(r"^T\d+$", clean, re.IGNORECASE):
        return True
    # 4-digit calendar years (e.g. 2024, 2025, 2026) are model-year specs, not SKU model codes
    if re.match(r"^(?:19|20)\d{2}$", clean):
        return True
    if clean.upper() in NON_SKU_TOKENS or re.match(r"^\d{1,2}K$", clean, re.IGNORECASE):
        return True
    # Units attached to numbers: 3FEET, 3FT, 7KG, 13SETS, 40INCH, 1000W, 3.2L, 12CFT, 1400RPM, 12000BTU, etc.
    if re.match(
        r"^\d+(?:\.\d+)?(?:[-_]?(?:FEET|FT|INCH|MM|CM|KG|KGS|GM|LTR|LTRS|LITRE|LITRES?|LITERS?|L|CFT|CUFT|SETS?|TON|TONS|WATTS?|W|VOLTS?|V|AMPS?|HZ|BTU|RPM|TAPS?|\"|\'))?$",
        clean,
        re.IGNORECASE,
    ):
        # Standalone pure numbers with >= 3 digits (like 1088, 1400, 9270, 330) are valid model codes
        if re.match(r"^\d+$", clean):
            return len(clean) <= 2
        return True
    if re.match(r"^(?:480|576|720|1080|1440|2160)[PI]$", clean, re.IGNORECASE):  # 1080P 2160P
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
    if MERCHANT_TRACKING_CODE_RE.search(clean):
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
    # Units attached to numbers (e.g. 1.5TON, 9KG, 8-KG, 40INCH, 1000W, 3.2L, 12CFT, 1400RPM) are specs, not SKU variant tags
    if re.match(
        r"^\d+(?:\.\d+)?(?:[-_]?(?:FEET|FT|INCH|MM|CM|KG|KGS|GM|LTR|LTRS|LITRE|LITRES?|LITERS?|L|CFT|CUFT|SETS?|TON|TONS|WATTS?|W|VOLTS?|V|AMPS?|HZ|BTU|RPM|TAPS?|\"|\'))$",
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
# Single Source of Truth capacity tables delegated to InMemoryRegistry (pricing_engine/registry.py)
UNIVERSAL_CAPACITY_TO_TONNAGE: dict[str, str] = dict(_SEED_UNIVERSAL_CAPACITIES)
DAWLANCE_CAPACITY_TO_TONNAGE: dict[str, str] = dict(_SEED_DAWLANCE_CAPACITIES)

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
    """Dynamically resolve capacity mapping for a given brand from InMemoryRegistry."""
    reg_map = InMemoryRegistry.get_capacity_map(brand)
    if reg_map:
        return reg_map
    b_upper = brand.strip().upper()
    for prefix, cap_map in BRAND_CAPACITY_SYSTEMS.items():
        if b_upper.startswith(prefix):
            return cap_map
    return UNIVERSAL_CAPACITY_TO_TONNAGE


def get_tonnage_map(brand: str = "") -> dict[str, set[str]]:
    """Dynamically get tonnage-to-codes mapping for a given brand."""
    return _invert_capacity_map(get_capacity_map(brand))


def get_capacity_tonnage(code: str, brand: str = "") -> str | None:
    """Get the tonnage string for an AC capacity code via InMemoryRegistry single source of truth."""
    return InMemoryRegistry.get_tonnage(code, brand=brand)


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
    full_name_clean, _ = extract_and_strip_opt_tags(full_name)
    full_name_clean = _strip_trailing_seller_clauses(full_name_clean)
    full_name_clean = _canonicalize_plus_series(full_name_clean)
    full_name_clean = _normalize_ac_transposed_cap_x(full_name_clean, brand=brand)
    clean = (
        full_name_clean.replace("—", " ")
        .replace("–", " ")
        .replace("|", " ")
        .replace("[", "(")
        .replace("]", ")")
        .replace("{", "(")
        .replace("}", ")")
        .strip()
    )
    # Strip multi-item marketing feature parentheticals like '( Smart DC Inverter + Self Cleaning + UPS ... )'
    clean = re.sub(
        r"\([^)]*(?:\+|\bself\s+cleaning\b|\bups\b|\bturbo\b|\bampere\b|\bwarranty\b)[^)]*\)",
        " ",
        clean,
        flags=re.IGNORECASE,
    )
    # Isolate AC subordinate chassis/revision codes (e.g. HPU-48HE/012DC(GE)-T3 -> HPU-48HE-T3)
    # BEFORE parenthesis unwrapping so '(GE)' never leaks as an orphaned capability token.
    clean = SUBORDINATE_AC_SLASH_RE.sub(
        lambda m: m.group(0) if m.group(2).upper() in {"DC", "AC"} else m.group(1),
        clean,
    )
    clean = re.sub(r"\(([A-Za-z0-9_-]+)\)", r" \1 ", clean).strip()
    # Strip subordinate PCB/factory revision codes after slash on AC SKUs (e.g. HSU-18HFP/023DC -> HSU-18HFP)
    clean = re.sub(
        r"\b([A-Za-z]{2,4}[-_]\d{2}[A-Za-z]{2,7})/\d{2,3}[A-Za-z]{1,3}\b",
        r"\1",
        clean,
    )

    # 1. Dynamically strip Brand name and brand abbreviation using catalog brand metadata
    first_w = clean.split()[0] if clean else ""
    detected_brand = (
        brand or (first_w if first_w and not re.search(r"\d", first_w) else "")
    ).strip()
    if detected_brand:
        b_prefix_re = rf"^(?:{re.escape(detected_brand)}|{re.escape(detected_brand[:3]) if len(detected_brand) >= 4 else '---'})[\s\-_,:]*"
        while re.match(b_prefix_re, clean, flags=re.IGNORECASE):
            clean = re.sub(b_prefix_re, "", clean, count=1, flags=re.IGNORECASE).strip()

    # Pre-process technical slashes and standalone measurement units before category stripping
    clean = _bind_standalone_measurement_units(normalize_technical_slashes(clean))
    is_dawlance_brand = _is_dawlance_context(full_name_clean, brand=detected_brand)

    # Normalize spaced capacity code before alphanumeric model stem (e.g. 12 SVN-AI-CO-31S -> 12SVN-AI-CO-31S, 24 HFAB -> 24HFAB)
    caps_pattern = "|".join(sorted(UNIVERSAL_CAPACITY_TO_TONNAGE.keys(), key=len, reverse=True))
    clean = re.sub(
        rf"\b({caps_pattern})\s+([A-Za-z]{{2,}}[-_A-Za-z0-9]*(?:\d+|-)[-_A-Za-z0-9]*)\b",
        r"\1\2",
        clean,
    )
    clean = _join_spaced_ac_btu_sku(clean)

    # Check for descriptive AC series + tonnage ONLY when the prefix has ZERO digits (no model code!)
    m_desc = re.search(
        r"^(.*?)\s+(\d+(?:\.\d+)?)\s*(?:ton|tonnage)(?:\s+(?:inverter|fix(?:ed)?\s*speed|ac|split|heat\s*(?:&|and)\s*cool|cool\s*only))*$",
        clean,
        flags=re.IGNORECASE,
    )
    if m_desc and not re.search(r"\d", m_desc.group(1)):
        series_candidate = CATEGORY_PATTERNS.sub(" ", m_desc.group(1)).strip(" -_,()")
        if series_candidate and series_candidate.upper() not in {
            "SPLIT",
            "SPLIT AC",
            "INVERTER",
            "AC",
            "AUTO",
            "AWM",
        }:
            cap_val = m_desc.group(2).strip()
            query = (
                f"{detected_brand} {series_candidate} {cap_val}".strip()
                if detected_brand
                else f"{series_candidate} {cap_val}"
            )
            return query, f"{series_candidate} {cap_val}"

    # Check for TV pattern: e.g. 32" D2 -> 32 D2 (only if model is not a generic descriptor/non-sku token)
    m_tv = re.search(
        r"\b(\d{2})\s*-?\s*(?:\"|inches|inch|\')\s+([A-Za-z0-9][A-Za-z0-9\-_]*)\b",
        clean,
        flags=re.IGNORECASE,
    )
    if m_tv and m_tv.group(2).upper() not in NON_SKU_TOKENS:
        cand_tv = m_tv.group(2)
        has_downstream_sku = bool(
            re.search(
                r"\b(?!\d{2}\s*(?:inch|\"|\'))[A-Za-z0-9\-_]*\d+[A-Za-z0-9\-_]*\b",
                clean[m_tv.end() :],
                flags=re.IGNORECASE,
            )
        )
        if re.search(r"\d", cand_tv) or not has_downstream_sku:
            screen = m_tv.group(1)
            model = cand_tv
            query = (
                f"{detected_brand} {screen} {model}".strip()
                if detected_brand
                else f"{screen} {model}"
            )
            return query, f"{screen} {model}"

    # 2. Strip standard category and capacity phrases
    is_ac_full = _detect_appliance_family(full_name_clean) == "AIR_CONDITIONER" or bool(
        re.search(r"\b(?:TON|ΤΟN|SPLIT\s+AC|AIR\s+CONDITIONER)\b", full_name_clean, re.IGNORECASE)
    )
    all_ac_cap_codes = set(UNIVERSAL_CAPACITY_TO_TONNAGE.keys()).union(
        *(m.keys() for m in BRAND_CAPACITY_SYSTEMS.values())
    )
    clean = CATEGORY_PATTERNS.sub(" ", clean).strip()

    # 3. Find model code:
    # Primary model token contains digits: e.g. DWT-1165, 100-316S6, HDG-201S, 12AITH21W-T3
    # Subsequent tokens are SKU variant tags (<= 3 chars or containing digits, e.g. PL, FLT, ES, GC)
    raw_tokens = clean.split()
    tokens: list[str] = []
    i = 0
    while i < len(raw_tokens):
        t = raw_tokens[i].strip("()[]-.,_ \"'")
        if i + 1 < len(raw_tokens):
            nxt = raw_tokens[i + 1].strip("()[]-.,_ \"'")
            # Case A0: Unprefixed spaced drum capacity + series code ("80 1217", "120 826S6", "60 50", "130 B699S8")
            if (
                re.match(r"^\d{2,3}$", t)
                and 50 <= int(t) <= 200
                and re.match(
                    r"^(?:\d{2,4}[A-Za-z0-9]{0,4}|[A-Za-z]{1,2}\d{3,5}[A-Za-z0-9]{0,3})$", nxt
                )
                and not is_dimension_or_spec_token(nxt)
            ):
                tokens.append(f"{t}-{nxt}")
                i += 2
                continue
            # Case A: Prefix + spaced drum capacity + series code ("HWM 80 1217", "DWF 85 1214", "HWM 130 B699S8")
            if (
                i + 2 < len(raw_tokens)
                and re.match(r"^[A-Za-z]{2,4}$", t)
                and t.upper() not in GENUINE_SUB_SERIES_TOKENS
                and t.upper() not in NON_SKU_TOKENS
                and re.match(r"^\d{2,3}$", nxt)
                and 50 <= int(nxt) <= 200
            ):
                third = raw_tokens[i + 2].strip("()[]-.,_ \"'")
                if re.match(
                    r"^(?:\d{2,4}[A-Za-z0-9]{0,4}|[A-Za-z]{1,2}\d{3,5}[A-Za-z0-9]{0,3})$", third
                ) and not is_dimension_or_spec_token(third):
                    tokens.append(f"{t}-{nxt}-{third}")
                    i += 3
                    continue
            # Case B: Prefix + 1-to-6-digit (optionally glued suffix) model number ("GS 18", "DWT 270 C", "DWT 255C", "DW 11095 C")
            # Guard: Never glue a mixed-case / vowel-rich AC series word + bare 2-digit AC capacity code (e.g. "Mega Flex 15", "Aura 15", "Dual 15").
            m_stem_suf = re.match(r"^(\d{1,6})([A-Za-z]{1,3})?$", nxt)
            is_ac_series_word_before_cap = bool(
                is_ac_full
                and m_stem_suf
                and (not m_stem_suf.group(2) or m_stem_suf.group(2).upper() == "K")
                and m_stem_suf.group(1) in all_ac_cap_codes
                and (
                    any(c.islower() for c in t)
                    or len(re.findall(r"[AEIOU]", t.upper())) >= 2
                    or (i > 0 and raw_tokens[i - 1].strip("()[]-.,_ \"'").isalpha())
                )
            )
            is_prefixed_ac_btu_k = bool(
                re.match(r"^\d{2}K$", nxt, re.IGNORECASE) and nxt[:2] in all_ac_cap_codes
            )
            if (
                re.match(r"^[A-Za-z]{2,4}(?:-[A-Za-z]{2,4})?$", t)
                and t.upper() not in GENUINE_SUB_SERIES_TOKENS
                and t.upper() not in NON_SKU_TOKENS
                and not is_color_token(t)
                and "-" not in nxt
                and m_stem_suf
                and not is_ac_series_word_before_cap
                and (
                    is_prefixed_ac_btu_k
                    or not (len(nxt) >= 3 and is_dimension_or_spec_token(nxt))
                )
            ):
                num_stem = m_stem_suf.group(1)
                glued_suf = m_stem_suf.group(2)
                if glued_suf:
                    # 1-2 digits are typically AC tonnage / series codes (e.g. GS-18A), glued without hyphen.
                    # 3+ digits are appliance model stems (e.g. DWT-255-C, DW-7500-C), separated with hyphen.
                    if len(num_stem) <= 2:
                        tokens.append(f"{t}-{num_stem}{glued_suf}")
                    else:
                        tokens.append(f"{t}-{num_stem}-{glued_suf}")
                    i += 2
                    continue
                if (
                    i + 2 < len(raw_tokens)
                    and re.match(r"^[A-Za-z]{1,3}$", raw_tokens[i + 2].strip("()[]-.,_ \"'"))
                    and raw_tokens[i + 2].strip("()[]-.,_ \"'").upper() not in NON_SKU_TOKENS
                    and raw_tokens[i + 2].strip("()[]-.,_ \"'").upper()
                    not in CATEGORY_1_DIRECT_MATCH_MODIFIERS
                    and not is_color_token(raw_tokens[i + 2].strip("()[]-.,_ \"'"))
                    and not (
                        is_dawlance_brand
                        and raw_tokens[i + 2].strip("()[]-.,_ \"'").upper() == "X"
                    )
                ):
                    suf_tok = raw_tokens[i + 2].strip("()[]-.,_ \"'")
                    if len(nxt) <= 2:
                        tokens.append(f"{t}-{nxt}{suf_tok}")
                    else:
                        tokens.append(f"{t}-{nxt}-{suf_tok}")
                    i += 3
                    continue
                tokens.append(f"{t}-{nxt}")
                i += 2
                continue
        tokens.append(raw_tokens[i])
        i += 1

    model_tokens: list[str] = []

    # Check for capacity + series pattern: e.g. 24 HDZ, 48 EDC, 18 HE-DC
    if len(tokens) >= 2 and tokens[0].isdigit() and len(tokens[0]) <= 2:
        m_next_alpha = re.search(r"^[A-Za-z0-9\-_]+$", tokens[1].strip("()[]-.,_ \"'"))
        if m_next_alpha and tokens[1].strip("()[]-.,_ \"'").upper() not in NON_SKU_TOKENS:
            cap_tok = tokens[0]
            ser_tok = tokens[1].strip("()[]-.,_ \"'")
            rest_toks = [t.strip("()[]-.,_ \"'") for t in tokens[2:] if is_sku_variant_tag(t)]
            raw_model = f"{cap_tok} {ser_tok}" + (f" {' '.join(rest_toks)}" if rest_toks else "")
            query = (
                f"{detected_brand} {ser_tok} {cap_tok}".strip()
                if detected_brand
                else f"{ser_tok} {cap_tok}"
            )
            return query, raw_model

    for t in tokens:
        t_clean = t.strip("()[]-.,_ \"'")
        if not t_clean or t_clean.upper() in NON_SKU_TOKENS:
            continue
        if not model_tokens:
            if (
                len(t_clean) >= 3
                and re.search(r"\d", t_clean)
                and not is_dimension_or_spec_token(t_clean)
                and re.match(r"^[A-Za-z0-9\-_\/]+$", t_clean)
            ):
                model_tokens.append(t_clean)
        else:
            is_numeric_stem_color = bool(
                model_tokens and model_tokens[0].isdigit() and is_color_token(t_clean)
            )
            is_short_color_code = len(t_clean) <= 2 and t_clean.upper() in COLOR_SUFFIX_MAP
            if is_sku_variant_tag(t_clean) or is_numeric_stem_color or is_short_color_code:
                first_parts = [p.upper() for p in model_tokens[0].split("-")]
                if t_clean.upper() not in first_parts:
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
        if "/" in clean_first:
            base_slash = clean_first.split("/")[0].strip()
            parts = base_slash.split("-")
            search_token = parts[0] if parts and len(parts[0]) >= 5 else base_slash
        else:
            parts = clean_first.split("-")
            search_token = parts[0] if parts and len(parts[0]) >= 5 else clean_first
        if re.search(r"Save[-_ ]?IN", search_token, re.IGNORECASE):
            search_token = re.sub(r"Save[-_ ]?IN", "SVN", search_token, flags=re.IGNORECASE)
        return search_token, raw_model

    # 4. Name-only fallback: no digit-based model token found.
    # Collect series names, capacity codes, and sub-variant descriptors.
    # Stop-words that are NOT part of the product identity:
    _NAME_STOP = {
        "INVERTER",
        "INV",
        "SERIES",
        "NORMAL",
        "HEAT",
        "COOL",
        "ONLY",
        "AND",
        "&",
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

    remaining = MARKETPLACE_NOISE_RE.sub(" ", clean)
    remaining = CATEGORY_PATTERNS.sub(" ", remaining).strip()
    remaining = re.sub(r"[()]", " ", remaining)  # Strip parentheses
    name_tokens = remaining.split()

    significant: list[str] = []
    capacity: str = ""
    for t in name_tokens:
        t_clean = t.strip("-.,_ \"'+/:;()[]{}")
        if not t_clean:
            continue
        t_upper = t_clean.upper()
        btu_k_code = t_upper[:-1] if re.match(r"^\d{2}K$", t_upper) else ""
        if t_upper in _CAPACITY_CODES and not capacity:
            capacity = t_clean
            significant.append(t_clean)
        elif btu_k_code in _CAPACITY_CODES and not capacity:
            capacity = btu_k_code
            significant.append(btu_k_code)
        elif (
            t_upper not in _NAME_STOP
            and t_upper not in NON_SKU_TOKENS
            and not re.match(r"^\d{1,2}K$", t_upper)
        ):
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

    punc_chars = " -_,.:;/()[]{}"
    clean_stripped = clean.strip(punc_chars)
    if not clean_stripped:
        base_title = full_name_clean.strip(punc_chars)
        fallback_query = (
            f"{detected_brand} {base_title}".strip()
            if detected_brand and not base_title.upper().startswith(detected_brand.upper())
            else base_title
        )
        return fallback_query, base_title

    parts = [p.strip(punc_chars) for p in clean_stripped.split() if p.strip(punc_chars)]
    fallback = parts[-1] if parts else clean_stripped
    query = (
        f"{detected_brand} {fallback}".strip()
        if detected_brand and not fallback.upper().startswith(detected_brand.upper())
        else fallback
    )
    return query, clean_stripped


def extract_tag(s: str) -> tuple[str, str]:
    """Separate trailing auxiliary tag (e.g. -T3, -ES, AAA, PRO) from token core."""
    m_slash_finish = re.match(
        r"^((?:[A-Za-z]{2,4}[-_]?)?(?:\d{2,3}-\d{3,}|\d{3,}))/([A-Za-z]{1,4})$", s
    )
    if m_slash_finish:
        slash_stem = m_slash_finish.group(1)
        slash_tag = m_slash_finish.group(2).upper()
        if slash_tag in COLOR_SUFFIX_MAP or slash_tag in {"WB", "GD", "INOX", "GB", "SD", "DD"}:
            return slash_stem, f"-{slash_tag}"
    if "-" in s:
        parts = s.split("-")
        if len(parts) > 1 and any(re.search(r"\d", p) for p in parts[:-1]):
            trailing = parts[-1].strip()
            if is_sku_variant_tag(trailing) or trailing.upper() in GENUINE_SUB_SERIES_TOKENS:
                return "-".join(parts[:-1]), f"-{trailing}"
    # Glued trailing variant tag on prefix+numeric stem with >= 3 digits (e.g. DWT11467ES -> DWT11467, HRF-216EBS -> HRF-216)
    m_stem_tag = re.match(r"^([A-Za-z]{2,4}[-_]?\d{3,})([A-Za-z]{2,4})$", s)
    if m_stem_tag:
        stem = m_stem_tag.group(1)
        tag = m_stem_tag.group(2)
        if is_sku_variant_tag(tag):
            return stem, f"-{tag}"
    # Glued single-letter variant on numeric hyphenated washer anchor (e.g. 150-826E -> 150-826, -E)
    m_num_hyph_letter = re.match(r"^((?:[A-Za-z]{2,4}-)?\d{2,3}-\d{3,4})([A-Za-z])$", s)
    if m_num_hyph_letter:
        return m_num_hyph_letter.group(1), f"-{m_num_hyph_letter.group(2).upper()}"
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
    clean_title = re.sub(
        r"\bSTAINLESS\s+STEEL\b", "STAINLESS STEEL INOX", clean_title, flags=re.IGNORECASE
    )

    # 2b. Universal capacity joining with alphanumeric model stems (e.g. 12 SVN-AI-CO-31S -> 12SVN-AI-CO-31S)
    caps_pattern = "|".join(sorted(UNIVERSAL_CAPACITY_TO_TONNAGE.keys(), key=len, reverse=True))
    clean_title = re.sub(
        rf"\b({caps_pattern})\s+([A-Za-z]{{2,}}[-_A-Za-z0-9]*(?:\d+|-)[-_A-Za-z0-9]*)\b",
        r"\1\2",
        clean_title,
    )

    # 2c. Universal series acronym equivalence: SaveIN <-> SVN
    def _repl_full_savein_svn(m: re.Match[str]) -> str:
        num = m.group(1)
        tag = m.group(2)
        rest = m.group(3)
        alt_tag = "SVN" if "SAVE" in tag.upper() else "SaveIN"
        return f"{m.group(0)} {num}{alt_tag}{rest} TAC-{num}SVN{rest}"

    clean_title = re.sub(
        rf"\b(?:TAC[-_]?)?({caps_pattern})[-_]?(SaveIN|SVN)([-_][A-Za-z0-9\-_]+)\b",
        _repl_full_savein_svn,
        clean_title,
        flags=re.IGNORECASE,
    )

    def _repl_bare_savein_svn(m: re.Match[str]) -> str:
        num = m.group(1)
        tag = m.group(2)
        alt_tag = "SVN" if "SAVE" in tag.upper() else "SaveIN"
        return f"{m.group(0)} {num}{alt_tag} TAC-{num}SVN"

    clean_title = re.sub(
        rf"\b({caps_pattern})\s*[-_]?\s*(SaveIN|SVN)\b(?![A-Za-z0-9\-_])",
        _repl_bare_savein_svn,
        clean_title,
        flags=re.IGNORECASE,
    )

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


def _single_letter_suffix_collision(target_model: str, candidate_title: str) -> bool:
    """Detect a conflicting single-letter variant suffix after the same model stem.

    Handles both spaced ('DWT-270 C', 'DW 7500 C') and glued/hyphenated ('DWT-270C', 'DWT-270-C')
    target stems against candidate titles.
    """
    stems_and_letters: list[tuple[str, str, str]] = []
    tokens = target_model.split()

    # 1. Spaced single-letter suffix: "DWT-270 C" or "DW 7500 C"
    for i, tok in enumerate(tokens[:-1]):
        nxt = tokens[i + 1].strip("()[]-.,_ \"'")
        m_stem = re.fullmatch(r"([A-Za-z]*)[- ]?(\d{3,})", tok.strip("()[]-.,_ \"'"))
        if m_stem and re.fullmatch(r"[A-Za-z]", nxt):
            stems_and_letters.append((m_stem.group(1), m_stem.group(2), nxt.upper()))

    # 2. Glued or hyphenated single-letter suffix: "DWT-270C" or "DWT-270-C"
    for tok in tokens:
        m_glued = re.fullmatch(
            r"([A-Za-z]{2,4})[-_]?(\d{3,})[-_]?([A-Za-z])", tok.strip("()[]-.,_ \"'")
        )
        if m_glued:
            stems_and_letters.append((m_glued.group(1), m_glued.group(2), m_glued.group(3).upper()))

    for letters, digits, target_letter in stems_and_letters:
        pattern = (
            rf"(?<![A-Za-z0-9]){re.escape(letters)}[-\s]?{digits}(?!\d)"
            r"(?:[-\s]?([A-Za-z])(?![A-Za-z0-9]))?"
        )
        found = [
            m.group(1).upper()
            for m in re.finditer(pattern, candidate_title, re.IGNORECASE)
            if m.group(1)
        ]
        if found and target_letter not in found:
            return True
    return False


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
    caps_pattern = "|".join(sorted(UNIVERSAL_CAPACITY_TO_TONNAGE.keys(), key=len, reverse=True))
    clean_target = re.sub(
        rf"\b({caps_pattern})\s+([A-Za-z]{{2,}}[-_A-Za-z0-9]*(?:\d+|-)[-_A-Za-z0-9]*)\b",
        r"\1\2",
        clean_target,
    )

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

    # Base target variants (e.g. SaveIN <-> SVN)
    base_targets = [base_target]
    if "SAVEIN" in base_target:
        base_targets.append(base_target.replace("SAVEIN", "SVN"))
    elif "SVN" in base_target:
        base_targets.append(base_target.replace("SVN", "SAVEIN"))

    # 1. Structural numeric prefix collision check (e.g. 18 vs 24 vs 12, or 100 vs 120):
    m_target_num = re.match(r"^([0-9]+)([A-Z]+)", base_target)
    if m_target_num:
        target_num = m_target_num.group(1)
        target_series = m_target_num.group(2)
        # If target is not already present, reject titles that have a conflicting capacity number
        if not any(bt in norm_title for bt in base_targets):
            for m_found in re.finditer(rf"([0-9]+){re.escape(target_series)}", norm_title):
                found_num = m_found.group(1)
                if len(found_num) == len(target_num) and found_num != target_num:
                    return False

    # Zero-Tolerance Hardware Door / Finish Collision Guard (GD vs INOX):
    # GD (Glass Door) and INOX (Stainless Steel) are 100% mutually exclusive appliance finishes.
    target_has_gd = bool(re.search(r"\b(?:GD|GLASS\s+DOOR)\b", clean_target, re.IGNORECASE))
    target_has_inox = bool(
        re.search(r"\b(?:INOX|STAINLESS(?:\s+STEEL)?|S\.S)\b", clean_target, re.IGNORECASE)
    )
    cand_has_gd = bool(re.search(r"\b(?:GD|GLASS\s+DOOR)\b", expanded_title, re.IGNORECASE))
    cand_has_inox = bool(
        re.search(r"\b(?:INOX|STAINLESS(?:\s+STEEL)?|S\.S)\b", expanded_title, re.IGNORECASE)
    )

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

    # Single-letter variant suffix guard (e.g. DWT-270 C vs DWT 270 S)
    if _single_letter_suffix_collision(clean_target, expanded_title):
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
            clean_cand_title = re.sub(
                rf"\b{re.escape(brand)}\b", "", clean_cand_title, flags=re.IGNORECASE
            )

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
        brand_sku_pattern = (
            rf"\b{re.escape(b_clean[0])}[a-z]{{1,3}}[- ]?{re.escape(core_tokens[0])}\b"
        )
        has_brand_sku = bool(re.search(brand_sku_pattern, title_lower))
        if not (has_brand_name or has_brand_sku):
            return False

    if len(core_tokens) > 1 and all(t in norm_title for t in core_tokens):
        return True
    if len(core_tokens) == 1 and core_tokens[0] in norm_title and len(core_tokens[0]) >= 3:
        return True

    # 3. Exact base target containment
    if any(bt in norm_title for bt in base_targets):
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
    has_explicit_plus_series = bool(re.search(r"\b[A-Za-z]{3,}\+(?![A-Za-z0-9+])", clean_name))
    caps_pattern = "|".join(sorted(UNIVERSAL_CAPACITY_TO_TONNAGE.keys(), key=len, reverse=True))
    clean_name = re.sub(
        rf"\b({caps_pattern})\s+([A-Za-z]{{2,}}[-_A-Za-z0-9]*(?:\d+|-)[-_A-Za-z0-9]*)\b",
        r"\1\2",
        clean_name,
    )
    clean_name = _join_spaced_ac_btu_sku(clean_name)
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

    tokens = raw_model.split()
    first_token = tokens[0] if tokens else raw_model

    # Dynamic SKU Prefix Extraction (100% Generic & Brand-Agnostic):
    # Detects any 2-4 letter brand/form-factor acronym directly preceding or hyphenated with the model
    # (e.g. DMB-4467, HRF-538, HWM-120, DWT-1165, GS-12)
    pfx = ""
    stem_num = ""
    m_pfx_direct = re.match(r"^([A-Za-z]{2,4})[-_](?=[A-Za-z0-9])", first_token)
    if m_pfx_direct:
        candidate_pfx = m_pfx_direct.group(1).upper()
        if candidate_pfx.lower() != detected_brand.lower() and candidate_pfx not in NON_SKU_TOKENS:
            pfx = candidate_pfx
        stem_num_match = re.search(r"\d+", first_token[m_pfx_direct.end() :])
        if stem_num_match:
            stem_num = stem_num_match.group(0)
    else:
        num_match = re.search(r"\d+", first_token)
        if num_match:
            stem_num = num_match.group(0)
            m_pfx = re.search(rf"\b([A-Za-z]{{2,4}})[- ]?{re.escape(first_token)}\b", clean_name)
            if not m_pfx and stem_num:
                m_pfx = re.search(rf"\b([A-Za-z]{{2,4}})[- ]?{re.escape(stem_num)}\b", clean_name)
            if m_pfx:
                candidate_pfx = m_pfx.group(1).upper()
                if (
                    candidate_pfx.lower() != detected_brand.lower()
                    and candidate_pfx not in NON_SKU_TOKENS
                ):
                    pfx = candidate_pfx

    # Check for TV pattern: 2-digit screen size glued to series (e.g. 50S80EUX, 43P735)
    # Guard against AC SKUs (e.g. 13HFCP, 13HFAB, 20HJUV, 24CE03, 18CFCP, 18HFPCA, 48CE03) via appliance context
    appliance_family = _detect_appliance_family(clean_name)
    is_ac_context = appliance_family == "AIR_CONDITIONER" or bool(
        re.search(
            r"\b(?:TON|ΤΟN|SPLIT\s+AC|AIR\s+CONDITIONER|FLOOR\s*STANDING|T3)\b",
            clean_name,
            re.IGNORECASE,
        )
    )
    tv_match = re.match(r"^(\d{2})([A-Z]\w{3,})$", first_token) if not is_ac_context else None

    # Check for series + capacity pattern:
    # Trailing capacity: MAGNA 30, AVANTE 15, PEARL 18, SPRINTER X 15 T3, GLACIER 45 PRO T3
    # Leading capacity: 30 MAGNA, 15 INFINITY PRO, 30 SPRINTER / POWERCON
    # Guard: Product with complex alphanumeric model (e.g. HSU-13HFS, 120-316S6) is NOT a series capacity product
    has_alphanumeric_model = any(
        not is_dimension_or_spec_token(t)
        and not re.match(r"^T[34]$", t, re.IGNORECASE)
        and (
            (re.search(r"\d", t) and re.search(r"[A-Za-z]", t))
            or ("-" in t and any(c.isdigit() for c in t))
        )
        for t in tokens
    )
    cap_token_idx: int | None = None
    if len(tokens) >= 2 and not has_alphanumeric_model:
        if tokens[-1].isdigit() and len(tokens[-1]) <= 2:
            cap_token_idx = len(tokens) - 1
        elif tokens[0].isdigit() and len(tokens[0]) <= 2:
            cap_token_idx = 0
        else:
            for idx_tok, tok_val in enumerate(tokens):
                if tok_val.isdigit() and len(tok_val) <= 2:
                    cap_token_idx = idx_tok
                    break
    is_leading_cap = cap_token_idx == 0
    is_series_capacity = cap_token_idx is not None and not has_alphanumeric_model

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

    elif is_series_capacity and cap_token_idx is not None:
        if is_leading_cap:
            cap_code = tokens[0]
            series_tokens = tokens[1:]
        else:
            cap_code = tokens[cap_token_idx]
            series_tokens = tokens[:cap_token_idx] + tokens[cap_token_idx + 1 :]

        source_without_units = CATEGORY_PATTERNS.sub(" ", clean_name)
        cap_in_source = bool(re.search(rf"\b{re.escape(cap_code)}\b", source_without_units))

        # Clean series tokens of non-sku tokens and punctuation
        series_clean = " ".join(
            [t for t in series_tokens if t.upper() not in NON_SKU_TOKENS and t != "+"]
        ).strip()
        # Handle slash-separated alternatives (e.g. Sprinter / Powercon)
        if "/" in series_clean:
            series_options = [s.strip() for s in series_clean.split("/") if s.strip()]
        else:
            series_options = [series_clean] if series_clean else [" ".join(series_tokens)]

        # Generic Series Refinement:
        # 1. Base series without trailing capability token (e.g. T3, T4, UV, WIFI, IOT)
        base_series_opts: list[str] = []
        for s in series_options:
            base_s = re.sub(
                r"\s+\b(?:T[34]|UV|WIFI|WI-FI|IOT)\b$", "", s, flags=re.IGNORECASE
            ).strip()
            if (
                base_s
                and base_s != s
                and base_s not in series_options
                and base_s not in base_series_opts
            ):
                base_series_opts.append(base_s)
        series_options.extend(base_series_opts)

        # 2. Generic unhyphenated variant expansion (e.g. 'Solar Hybrid-IV' -> 'Solar Hybrid IV')
        unhyphen_series_opts: list[str] = []
        for s in series_options:
            if "-" in s:
                s_unhyphen = re.sub(r"-(?=[A-Za-z0-9])", " ", s).strip()
                if (
                    s_unhyphen != s
                    and s_unhyphen not in series_options
                    and s_unhyphen not in unhyphen_series_opts
                ):
                    unhyphen_series_opts.append(s_unhyphen)
        series_options.extend(unhyphen_series_opts)

        # 3. For Dawlance series across all categories, generate the base series without 'X'
        # so listings titled e.g. 'Sprinter 15' or 'Elegance' are retrieved alongside 'X' forms.
        if _is_dawlance_context(canonical_name, brand=detected_brand):
            dawlance_no_x_opts: list[str] = []
            for s in series_options:
                s_no_x = re.sub(r"\s+\bX\b", "", s, flags=re.IGNORECASE).strip()
                if (
                    s_no_x
                    and s_no_x != s
                    and s_no_x not in series_options
                    and s_no_x not in dawlance_no_x_opts
                ):
                    dawlance_no_x_opts.append(s_no_x)
            series_options.extend(dawlance_no_x_opts)

        # When capacity code was synthesized from tonnage (not present in source title, e.g. Solar Hybrid-III T3),
        # prioritize clean source-faithful series queries in Tier 1 so Tier 1 never fails on synthesized codes.
        if not cap_in_source:
            for s_opt in series_options:
                tier_1.append(s_opt)
                if detected_brand:
                    tier_1.append(_with_brand(detected_brand, s_opt))

        for s_opt in series_options:
            tier_1.append(f"{s_opt} {cap_code}")
            tier_1.append(f"{cap_code} {s_opt}")
            if detected_brand:
                tier_1.append(_with_brand(detected_brand, f"{s_opt} {cap_code}"))
                tier_1.append(_with_brand(detected_brand, f"{cap_code} {s_opt}"))
            tier_2.append(s_opt)
            if detected_brand:
                tier_2.append(_with_brand(detected_brand, s_opt))

            tonnage = get_capacity_tonnage(cap_code, detected_brand)
            if tonnage:
                tier_3.append(f"{s_opt} {tonnage} TON")
                tier_3.append(f"{s_opt} {tonnage}TON")
                if detected_brand:
                    tier_3.append(_with_brand(detected_brand, f"{s_opt} {tonnage} TON"))

        # If source title used '+' series notation (e.g. 'Glamour+ 45', 'Avante+ 30'), also emit '+' and root-series
        # search queries so marketplace listings titled 'GLAMOUR + INVERTER 45' or 'Glamour+ 45' are retrieved
        # while referee_match enforces strict Plus-series compatibility.
        if has_explicit_plus_series:
            for s_opt in series_options:
                s_plus_sym = re.sub(r"\s+PLUS\b", "+", s_opt, flags=re.IGNORECASE)
                s_base_root = re.sub(r"\s+PLUS\b", "", s_opt, flags=re.IGNORECASE).strip()
                if s_plus_sym != s_opt:
                    tier_1.append(f"{s_plus_sym} {cap_code}")
                    if detected_brand:
                        tier_1.append(_with_brand(detected_brand, f"{s_plus_sym} {cap_code}"))
                if s_base_root and s_base_root != s_opt:
                    tier_2.append(f"{s_base_root} {cap_code}")
                    if detected_brand:
                        tier_2.append(_with_brand(detected_brand, f"{s_base_root} {cap_code}"))
                        tier_2.append(_with_brand(detected_brand, s_base_root))

        if cap_in_source:
            tier_1.append(raw_model)
            if detected_brand:
                tier_1.append(_with_brand(detected_brand, raw_model))
        else:
            tier_2.append(raw_model)
            if detected_brand:
                tier_2.append(_with_brand(detected_brand, raw_model))

    else:
        # Standard model codes: washing machines, ACs, refrigerators
        bare_stem = core_stem
        is_numeric_stem = bare_stem.isdigit()

        if detected_brand:
            if pfx:
                # Top priority: Full brand + prefix + model (e.g. Dawlance DMB 4467, Haier HRF 538)
                tier_1.append(_with_brand(detected_brand, _with_prefix(pfx, bare_stem, " ")))
                tier_1.append(_with_brand(detected_brand, _with_prefix(pfx, bare_stem, "-")))
                if stem_num and stem_num != bare_stem and not re.match(r"^\d+-\d+", bare_stem):
                    tier_1.append(_with_brand(detected_brand, _with_prefix(pfx, stem_num, " ")))
                    tier_1.append(_with_brand(detected_brand, _with_prefix(pfx, stem_num, "-")))
                    if len(stem_num) >= 3:
                        tier_1.append(_with_brand(detected_brand, stem_num))
                tier_1.append(_with_brand(detected_brand, raw_model))
                # Standalone prefix for sellers who omit brand name (e.g. DMB 4467, HRF 538)
                tier_1.append(_with_prefix(pfx, bare_stem, " "))
                if stem_num and stem_num != bare_stem and not re.match(r"^\d+-\d+", bare_stem):
                    tier_1.append(_with_prefix(pfx, stem_num, " "))
                    tier_2.append(_with_prefix(pfx, stem_num, "-"))
                    if len(stem_num) >= 4:
                        tier_2.append(stem_num)
                        tier_2.append(_with_brand(detected_brand, stem_num))
                tier_2.append(_with_prefix(pfx, bare_stem, "-"))

            tier_1.append(_with_brand(detected_brand, raw_model))
            tier_1.append(_with_brand(detected_brand, bare_stem))
            tier_2.append(_with_brand(detected_brand, bare_stem))

        # Add pure alphanumeric stem without prefix (e.g. '18AITH21B' from 'GS-18AITH21B')
        pure_stem = (
            re.sub(rf"^{re.escape(pfx)}[-_]?", "", bare_stem, flags=re.IGNORECASE) if pfx else ""
        )
        if pure_stem and pure_stem != bare_stem and not pure_stem.isdigit() and len(pure_stem) >= 4:
            tier_1.append(pure_stem)
            if detected_brand:
                tier_1.append(_with_brand(detected_brand, pure_stem))
            mod_tag = aux_tag or (" ".join(tokens[1:]).strip() if len(tokens) > 1 else "")
            if mod_tag:
                clean_mod = mod_tag.replace(" ", "")
                tier_1.append(f"{pure_stem}{clean_mod}")
                tier_1.append(f"{pure_stem}-{clean_mod}")
                if detected_brand:
                    tier_1.append(_with_brand(detected_brand, f"{pure_stem}{clean_mod}"))
                    tier_1.append(_with_brand(detected_brand, f"{pure_stem}-{clean_mod}"))
            tier_2.append(pure_stem)
            if detected_brand:
                tier_2.append(_with_brand(detected_brand, pure_stem))

        # Only allow unbranded queries if stem is complex alphanumeric (e.g. 12AITH21W, 120-826S6)
        # Pure numeric stems (e.g. 4467, 105) must NEVER be queried bare to prevent matching random shoes, clothes, etc.
        if not is_numeric_stem:
            tier_1.append(raw_model)
            if bare_stem != raw_model:
                tier_1.append(bare_stem)
            mod_tag = aux_tag or (" ".join(tokens[1:]).strip() if len(tokens) > 1 else "")
            if mod_tag:
                clean_mod = mod_tag.replace(" ", "")
                tier_1.append(f"{bare_stem}{clean_mod}")
                if "-" in bare_stem:
                    tier_1.append(f"{bare_stem.replace('-', '')}{clean_mod}")
                if detected_brand:
                    tier_1.append(_with_brand(detected_brand, f"{bare_stem}{clean_mod}"))
            tier_2.append(bare_stem)
            # Spaced BTU + code query permutation for AC SKUs (e.g. '14HFT' -> '14 HFT', '20HFT' -> '20 HFT')
            stem_for_space = pure_stem or bare_stem
            m_ac_btu_code = (
                re.match(r"^(\d{2})([A-Za-z]{2,}[A-Za-z0-9]*)$", stem_for_space)
                if is_ac_context
                else None
            )
            if m_ac_btu_code:
                spaced_btu_sku = f"{m_ac_btu_code.group(1)} {m_ac_btu_code.group(2)}"
                tier_3.append(spaced_btu_sku)
                if detected_brand:
                    tier_3.append(_with_brand(detected_brand, spaced_btu_sku))
            decomp_base, decomp_sub = _decompose_ac_sku(stem_for_space, is_ac_context)
            if decomp_base and decomp_sub:
                if detected_brand:
                    tier_2.append(_with_brand(detected_brand, decomp_base))
                tier_2.append(decomp_base)
                if pfx:
                    tier_2.append(f"{pfx}-{decomp_base}")
                    if detected_brand:
                        tier_2.append(_with_brand(detected_brand, f"{pfx}-{decomp_base}"))
                spaced_decomp = f"{decomp_base[:2]} {decomp_base[2:]}"
                tier_3.append(spaced_decomp)
                if detected_brand:
                    tier_3.append(_with_brand(detected_brand, spaced_decomp))

        # Color-specific search permutations if target specifies a distinct color (e.g. (G), Golden, (DG), Dark Grey, White, Black)
        _, raw_color = normalize_color(clean_name, anchor=bare_stem)
        if raw_color:
            color_upper = raw_color.upper()
            color_candidates: list[str] = []
            if color_upper in COLOR_CODE_FULL_NAMES:
                full_color = COLOR_CODE_FULL_NAMES[color_upper]
                color_candidates.extend(
                    [
                        f"{bare_stem} {color_upper}",
                        f"{bare_stem} {full_color}",
                        f"{bare_stem}-{color_upper}",
                    ]
                )
                if pfx:
                    pure_stem = re.sub(
                        rf"^{re.escape(pfx)}[-_]?", "", bare_stem, flags=re.IGNORECASE
                    )
                    if pure_stem and pure_stem != bare_stem:
                        color_candidates.extend(
                            [
                                f"{pure_stem} {color_upper}",
                                f"{pure_stem} {full_color}",
                                f"{pure_stem}-{color_upper}",
                                f"{pure_stem}({color_upper})",
                            ]
                        )
                    color_candidates.extend(
                        [
                            _with_prefix(pfx, f"{bare_stem} {color_upper}", " "),
                            _with_prefix(pfx, f"{bare_stem} {full_color}", " "),
                            _with_prefix(pfx, f"{bare_stem}-{color_upper}", "-"),
                            _with_prefix(pfx, f"{bare_stem}({color_upper})", "-"),
                        ]
                    )
            else:
                color_tok = raw_color.title()
                color_candidates.append(f"{bare_stem} {color_tok}")
                if raw_color.lower() != color_tok.lower():
                    color_candidates.append(f"{bare_stem} {raw_color}")
                if pfx:
                    color_candidates.append(_with_prefix(pfx, f"{bare_stem} {color_tok}", " "))

            tier_1.extend(color_candidates)
            if detected_brand:
                tier_1.extend([_with_brand(detected_brand, cq) for cq in color_candidates])

        # Universal SaveIN <-> SVN series equivalence (e.g. TCL SaveIN / SVN)
        if (
            re.search(r"Save[-_ ]?IN", bare_stem, re.IGNORECASE)
            or re.search(r"\bSVN\b", bare_stem, re.IGNORECASE)
            or re.search(r"\d+SVN", bare_stem, re.IGNORECASE)
        ):
            svn_stem = re.sub(r"Save[-_ ]?IN", "SVN", bare_stem, flags=re.IGNORECASE)
            savein_stem = re.sub(r"SVN", "SaveIN", bare_stem, flags=re.IGNORECASE)
            tac_svn = _with_prefix("TAC", svn_stem, "-")
            no_tac_svn = re.sub(r"^TAC[-_]?", "", svn_stem, flags=re.IGNORECASE)
            no_tac_savein = re.sub(r"^TAC[-_]?", "", savein_stem, flags=re.IGNORECASE)

            tier_1.extend([svn_stem, tac_svn, no_tac_svn, savein_stem, no_tac_savein])
            if detected_brand:
                tier_1.extend(
                    [
                        _with_brand(detected_brand, svn_stem),
                        _with_brand(detected_brand, tac_svn),
                        _with_brand(detected_brand, no_tac_svn),
                        _with_brand(detected_brand, savein_stem),
                    ]
                )

            tier_2.extend([svn_stem, tac_svn, no_tac_svn, savein_stem])
            if detected_brand:
                tier_2.extend(
                    [
                        _with_brand(detected_brand, svn_stem),
                        _with_brand(detected_brand, no_tac_svn),
                    ]
                )

            m_cap_svn = re.search(r"\b(\d{1,2})(?:SVN|SaveIN)", svn_stem, re.IGNORECASE)
            if m_cap_svn:
                cap_svn = m_cap_svn.group(1)
                tier_3.extend([f"{cap_svn}SVN", f"TAC-{cap_svn}SVN"])
                if detected_brand:
                    tier_3.append(_with_brand(detected_brand, f"{cap_svn}SVN"))

        # Dynamic Multi-Block Segmented Appliance Patterns (e.g. HW90-BP12357S8 -> HW-90-BP12357-S8)
        # Matches any brand form-factor prefix (2-4 letters) + capacity (50-250) + series/sub-model
        m_drum_multi = re.match(r"^([A-Za-z]{2,4})(\d{2,3})[-_ ]?([A-Za-z0-9].*)$", bare_stem)
        if m_drum_multi and 50 <= int(m_drum_multi.group(2)) <= 250:
            d_pfx, d_cap, d_rest = m_drum_multi.groups()
            m_sub = re.match(r"^([A-Za-z0-9]+?)[-_ ]?([A-Za-z]\d|\b[A-Za-z]\b)$", d_rest)
            segmented_variants: list[str] = []
            if m_sub:
                sub_stem, sub_tag = m_sub.group(1), m_sub.group(2)
                segmented_variants.append(f"{d_pfx}-{d_cap}-{sub_stem}-{sub_tag}")
                segmented_variants.append(f"{d_pfx} {d_cap} {sub_stem} {sub_tag}")
            segmented_variants.append(f"{d_pfx}-{d_cap}-{d_rest}")
            segmented_variants.append(f"{d_pfx} {d_cap} {d_rest}")

            for sv in segmented_variants:
                if "-" in sv:
                    tier_1.append(sv)
                    if detected_brand:
                        tier_1.append(_with_brand(detected_brand, sv))
                    tier_2.append(sv)
                else:
                    tier_3.append(sv)

        # Tier 3: Spaced, glued, and prefixed permutations
        if "-" in bare_stem:
            spaced = bare_stem.replace("-", " ")
            glued = bare_stem.replace("-", "")
            if re.match(r"^[A-Za-z]{2,4}-\d{3,4}-[A-Za-z0-9]{1,3}$", bare_stem):
                tier_2.append(glued)
            tier_3.append(spaced)
            tier_3.append(glued)
            if pfx and not bare_stem.upper().startswith(pfx):
                tier_2.append(f"{pfx} {bare_stem}")
                tier_2.append(f"{pfx}-{bare_stem}")
                tier_3.append(f"{pfx}-{bare_stem}")
                tier_3.append(f"{pfx} {bare_stem}")
                tier_3.append(f"{pfx} {spaced}")
            elif (
                not pfx
                and detected_brand.upper() == "HAIER"
                and re.match(r"^\d{2,3}-[A-Za-z0-9]{3,8}$", bare_stem)
            ):
                tier_1.insert(0, f"Haier HWM {bare_stem}")
                tier_1.insert(1, f"Haier HWM-{bare_stem}")
                tier_2.insert(0, f"HWM {bare_stem}")
                tier_2.insert(1, f"HWM-{bare_stem}")
        elif fridge_match:
            digits = fridge_match.group(1)
            letters = fridge_match.group(2)
            tier_3.append(f"{digits} {letters}")
            tier_3.append(f"{digits}-{letters}")
            if detected_brand:
                tier_3.append(_with_brand(detected_brand, bare_stem))
        else:
            m_drum_glued = re.match(
                r"^([A-Za-z]{0,4}?)(\d{2,3}?)(\d{3,4})([A-Za-z]{0,2})$",
                bare_stem,
            )
            if m_drum_glued and 50 <= int(m_drum_glued.group(2)) <= 200:
                d_pfx, d_cap, d_ser, d_suf = m_drum_glued.groups()
                split_hyphen = f"{d_pfx + '-' if d_pfx else ''}{d_cap}-{d_ser}{d_suf}"
                split_space = f"{d_pfx + ' ' if d_pfx else ''}{d_cap} {d_ser}"
                tier_2.append(split_hyphen)
                if detected_brand:
                    tier_1.append(_with_brand(detected_brand, split_hyphen))
                tier_3.append(split_space)

        if pfx and "-" not in bare_stem and not bare_stem.upper().startswith(pfx):
            tier_3.append(f"{pfx}-{bare_stem}")
            tier_3.append(f"{pfx} {bare_stem}")

        # If AC model ends with color letter (W, B, S, G), also add bare series to tier 3
        m_color_suffix = re.match(r"^(\d+[A-Za-z]+?\d+)[WBSG]$", bare_stem, re.IGNORECASE)
        if m_color_suffix:
            tier_3.append(m_color_suffix.group(1))

        if detected_brand:
            tier_3.append(_with_brand(detected_brand, raw_model))

    # Helper to deduplicate while preserving order case-insensitively
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        res: list[str] = []
        for x in items:
            s = x.strip()
            s_lower = s.lower()
            if s and s_lower not in seen:
                seen.add(s_lower)
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

    def _dedupe_list(items: list[str]) -> list[str]:
        seen: set[str] = set()
        res: list[str] = []
        for x in items:
            s = x.strip()
            s_lower = s.lower()
            if s and s_lower not in seen:
                seen.add(s_lower)
                res.append(s)
        return res

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
            "tier_1": _dedupe_list(t1),
            "tier_2": _dedupe_list(t2),
            "tier_3": _dedupe_list(t3),
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


def _anchor_from_prefix_match(m: re.Match[str], first_token_tag: str) -> tuple[str, str]:
    pfx = m.group(1).upper()
    num = m.group(2)
    suf = (m.group(3) or "").upper()
    suf = re.sub(r"[()]", "", suf).strip()
    matched_raw = m.group(0)
    has_space_pfx = bool(re.search(rf"^{re.escape(m.group(1))}\s+", matched_raw))
    # Only defer when num is 1-2 digits and suf is glued directly to num (e.g. "TV 32D2", "AC 24SVN")
    is_glued_num_suf = bool(
        suf and re.search(rf"{re.escape(num)}{re.escape(suf)}", matched_raw, re.IGNORECASE)
    )
    if has_space_pfx and is_glued_num_suf and len(num) <= 2:
        return "", first_token_tag
    if (
        num.isdigit()
        and len(num) <= 2
        and (not suf or pfx in GENUINE_SUB_SERIES_TOKENS or pfx in {"SPLIT", "AUTO", "AWM"})
    ):
        return "", first_token_tag
    elif pfx in NON_SKU_TOKENS:
        # Category noise words (e.g. 'TV', 'AC', 'REF') should NEVER become anchor prefixes!
        # If followed by alphanumeric model (e.g. 32D2, 24SVN-AI-41), defer to alphanumeric candidate search
        if not suf and not (num.isdigit() and len(num) <= 2):
            return num, first_token_tag
        return "", first_token_tag
    elif is_glued_num_suf and len(suf) <= 8 and suf not in {"INVERTER", "SERIES", "NORMAL"}:
        if is_sku_variant_tag(suf) and len(num) >= 3:
            return f"{pfx}-{num}", (first_token_tag if first_token_tag else suf)
        else:
            return f"{pfx}-{num}{suf}", first_token_tag
    elif not (num.isdigit() and len(num) <= 2):
        return f"{pfx}-{num}", first_token_tag
    return "", first_token_tag


def _text_after_anchor(clean_title: str, anchor: str) -> str | None:
    """Return text occurring strictly after anchor (case-insensitive, checking hyphen variants)."""
    if not anchor:
        return None
    anc_variants = [anchor]
    if "-" in anchor:
        anc_variants.extend([anchor.replace("-", " "), anchor.replace("-", "")])
    upper_title = clean_title.upper()
    for v in anc_variants:
        idx = upper_title.find(v.upper())
        if idx != -1:
            return clean_title[idx + len(v) :]
    return None


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
    title_no_opt, allowed_tags = extract_and_strip_opt_tags(title)
    # Strip payment & promotional parentheticals (0% markup, EMI, down payment, installment, processing fees)
    raw_clean = re.sub(
        r"\s*\([^)]*(?:0%|markup|mark\s*up|installment|emi|down\s*payment|interest|gift|free|warranty|discount|deal|delivery|processing|fees?|installation)[^)]*\)",
        " ",
        title_no_opt,
        flags=re.IGNORECASE,
    )
    raw_clean = re.sub(r"\s*\(\s*\)", " ", raw_clean).strip()

    # Clean trailing seller store tags (e.g. ' - ET', ' - By Tech House', ' |3AZ Mart', ' - ElectroEase')
    # Guarantees hardware facets (GD, WB, GB, FL, TL, IOT, Cool Only, Twin Tub, EBS, Metal Door) are NEVER stripped!
    raw_clean = _strip_trailing_seller_clauses(raw_clean)
    raw_clean = _canonicalize_plus_series(raw_clean)
    raw_clean = _normalize_ac_transposed_cap_x(raw_clean, brand=brand)

    raw_clean = (
        raw_clean.replace("—", " ")
        .replace("–", " ")
        .replace("|", " | ")
        .replace("[", "(")
        .replace("]", ")")
        .replace("{", "(")
        .replace("}", ")")
        .strip()
    )
    # Strip multi-item marketing feature parentheticals like '( Smart DC Inverter + Self Cleaning + UPS ... )'
    raw_clean = re.sub(
        r"\([^)]*(?:\+|\bself\s+cleaning\b|\bups\b|\bturbo\b|\bampere\b)[^)]*\)",
        " ",
        raw_clean,
        flags=re.IGNORECASE,
    )
    # Atomically isolate AC subordinate slash codes (e.g. HPU-48HE/012DC(GE)-T3, HSU-18HFP/023DC, 18HE/DC)
    # BEFORE parenthesis unwrapping in extract_search_query_and_model so '(GE)' never becomes an orphaned token.
    subordinate_codes: list[str] = []

    def _capture_subordinate_ac_slash(m: re.Match[str]) -> str:
        sub_code = m.group(2).strip()
        if sub_code and sub_code not in subordinate_codes:
            subordinate_codes.append(sub_code)
        return m.group(1)

    raw_clean = SUBORDINATE_AC_SLASH_RE.sub(_capture_subordinate_ac_slash, raw_clean)
    for m_sp_dc in re.finditer(
        r"\b\d{2}\s+(?:HE|CE|GE|SE|HBU|HCF|P|C)/(DC|AC)\b", raw_clean, re.IGNORECASE
    ):
        sp_code = m_sp_dc.group(1).upper()
        if sp_code not in subordinate_codes:
            subordinate_codes.append(sp_code)
    # Strip subordinate PCB/factory revision codes after slash on AC SKUs (e.g. HSU-18HFP/023DC -> HSU-18HFP)
    raw_clean = re.sub(
        r"\b([A-Za-z]{2,4}[-_]\d{2}[A-Za-z]{2,7})/\d{3}(?:DC|AC|GE)\b",
        r"\1",
        raw_clean,
        flags=re.IGNORECASE,
    )

    raw_clean = MERCHANT_TRACKING_CODE_RE.sub(" ", raw_clean)
    clean_title = _bind_standalone_measurement_units(
        _join_spaced_ac_btu_sku(normalize_technical_slashes(raw_clean))
    )
    first_w = clean_title.split()[0] if clean_title else ""
    detected_brand = brand.strip() or (first_w if first_w and not re.search(r"\d", first_w) else "")
    search_token, raw_model = extract_search_query_and_model(clean_title, brand=detected_brand)

    tokens = [t.strip("()[]-.,_ \"'") for t in raw_model.split() if t.strip("()[]-.,_ \"'")]
    first_token = tokens[0] if tokens else raw_model.strip("()[]-.,_ \"'")

    # 1. Anchor Extraction
    anchor = ""
    all_known_cap_codes = set(UNIVERSAL_CAPACITY_TO_TONNAGE.keys()).union(
        *(m.keys() for m in BRAND_CAPACITY_SYSTEMS.values())
    )
    first_token_tag = ""
    if (
        re.search(r"\d", first_token)
        and not is_dimension_or_spec_token(first_token)
        and not (first_token.isdigit() and first_token in all_known_cap_codes)
    ):
        core_stem, first_token_tag = extract_tag(first_token)
        anchor = core_stem.strip("()[]-.,_ \"'")
        m_col_suf = re.search(r"-(S[-_]?G|S[-_]?W|DG|OW|[WBSGDRP])$", anchor, re.IGNORECASE)
        if m_col_suf:
            anchor = anchor[: m_col_suf.start()]
        elif re.search(r"\d{2,}[A-Za-z]{3,}(DG|OW)$", anchor, re.IGNORECASE):
            anchor = anchor[:-2]

    # Enhanced anchor detection for compound models (e.g. 24 HDZ, 48 EDC, 18 HE-DC, HMO-45200, HAF-50MB, 32 D2)
    if not anchor:
        sub_anchor = clean_marketplace_noise(clean_title)
        sub_anchor = re.sub(
            r"\b\d+(?:\.\d+)?[\s\-_]*(?:TON|ΤΟN|KG|KGS|CFT|CU\s*FT|CU\.FT|LTR|LITRES?|LITERS?|WATTS?)\b",
            " ",
            sub_anchor,
            flags=re.IGNORECASE,
        )
        if detected_brand:
            sub_anchor = re.sub(
                rf"^(?:{re.escape(detected_brand)}|{re.escape(detected_brand[:3]) if len(detected_brand) >= 4 else '---'})[\s\-_,:]*",
                "",
                sub_anchor,
                flags=re.IGNORECASE,
            )
        for m_pfx in re.finditer(
            r"\b([A-Za-z]{2,4})[-_ ]?(\d+(?:-\d+)?)[-_ ]?([A-Za-z0-9]*)\b", sub_anchor
        ):
            cand_anc, cand_tag = _anchor_from_prefix_match(m_pfx, first_token_tag)
            num_suf = f"{m_pfx.group(2)}{(m_pfx.group(3) or '').upper()}"
            is_valid_btu_k_suf = bool(
                re.match(r"^\d{2}K$", num_suf, re.IGNORECASE)
                and m_pfx.group(2) in all_known_cap_codes
            )
            if (
                not cand_anc
                or is_dimension_or_spec_token(cand_anc)
                or (not is_valid_btu_k_suf and is_dimension_or_spec_token(num_suf))
            ):
                continue
            anchor = cand_anc.strip("()[]-.,_ \"'")
            first_token_tag = cand_tag
            break

        if not anchor:
            for m_cand in re.finditer(
                r"\b(\d+[A-Za-z]+[A-Za-z0-9\-]*|[A-Za-z]+\d+[A-Za-z0-9\-]*)\b", sub_anchor
            ):
                cand_tok = m_cand.group(1).upper()
                if not is_dimension_or_spec_token(cand_tok):
                    m_lead_num = re.search(
                        rf"\b(\d{{1,2}})\s+{re.escape(m_cand.group(1))}\b", sub_anchor
                    )
                    if m_lead_num and not cand_tok[0].isdigit():
                        anchor = f"{m_lead_num.group(1)}{cand_tok}".strip("()[]-.,_ \"'")
                    else:
                        anchor = cand_tok.strip("()[]-.,_ \"'")
                    break
            if not anchor:
                m_cap_ser = re.search(
                    r"\b(\d{1,2})\s+([A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)?)\b", sub_anchor
                )
                if (
                    m_cap_ser
                    and m_cap_ser.group(2).upper() not in NON_SKU_TOKENS
                    and not is_sku_variant_tag(m_cap_ser.group(2))
                ):
                    w = m_cap_ser.group(2)
                    vowels = len(re.findall(r"[AEIOU]", w.upper()))
                    is_series_word = (
                        (len(w) >= 4 and vowels >= 2)
                        or w.upper() in GENUINE_SUB_SERIES_TOKENS
                        or w.upper() in {"INVERTER", "SERIES", "NORMAL"}
                    )
                    if not is_series_word:
                        anchor = f"{m_cap_ser.group(1)}{w.upper()}".strip("()[]-.,_ \"'")

    # Prefix-optional glued 3/4-letter variant tag split on >= 3-digit stems (e.g. '216EBS' -> anchor '216', tag '-EBS')
    if anchor and not is_dimension_or_spec_token(anchor):
        m_unpref_glued = re.match(r"^((?:[A-Za-z]{2,4}[-_]?)?\d{3,4})([A-Za-z]{3,4})$", anchor)
        if m_unpref_glued and is_sku_variant_tag(m_unpref_glued.group(2)):
            anchor = m_unpref_glued.group(1)
            if not first_token_tag:
                first_token_tag = f"-{m_unpref_glued.group(2)}"

    # 2. Guarded Facets Extraction
    # AC Category Detection (used for AC tonnage capacity extraction)
    detected_family = _detect_appliance_family(clean_title)
    is_non_ac = (detected_family is not None and detected_family != "AIR_CONDITIONER") or bool(
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

    # 2a. Operating Mode: Cool Only vs Heat & Cool
    cool_only = (
        True
        if re.search(r"\b(?:COOL\s+ONLY|COOLING\s+ONLY|ONLY\s+COOL)\b", clean_title, re.IGNORECASE)
        else None
    )
    heat_and_cool = (
        True
        if re.search(r"\b(?:HEAT\s*(?:&|AND|/)\s*COOL|H\s*&\s*C|H/C)\b", clean_title, re.IGNORECASE)
        else None
    )

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
    m_screen = re.search(
        r"(?<![\d./])(\d{2})\s*-?\s*(?:INCH(?:ES)?\b|\"|\')", clean_title, re.IGNORECASE
    )
    if m_screen:
        capacity = f"{m_screen.group(1)}INCH"
        is_display = True
    elif is_display and anchor and re.match(r"^(\d{2})[A-Z]\w{3,}$", anchor):
        capacity = f"{anchor[:2]}INCH"
    else:
        # Refrigerator CFT (Cubic Feet)
        m_cft = re.search(
            r"\b(\d+(?:\.\d+)?)\s*(?:CU\s*FT|CU\.FT|CFT)\b", clean_title, re.IGNORECASE
        )
        if m_cft:
            capacity = f"{int(float(m_cft.group(1)))}CFT"
        else:
            # Washing machine KG
            m_kg = re.search(r"\b(\d+(?:\.\d+)?)\s*[-]?\s*KGS?\b", clean_title, re.IGNORECASE)
            if m_kg:
                kg_val = float(m_kg.group(1))
                capacity = f"{kg_val:g}KG"
            elif anchor and (
                m_anchor := re.match(r"^(?:[A-Za-z]{2,4}-)?(\d{2,3})-[A-Za-z0-9]+", anchor)
            ):
                num_val = int(m_anchor.group(1))
                if 50 <= num_val <= 250:
                    cap_val = num_val / 10.0
                    capacity = f"{cap_val:g}KG"
            elif not is_non_ac:
                # AC Tonnage
                m_ton = re.search(
                    r"\b(\d+(?:\.\d+)?)\s*[-]?\s*(?:TON|ΤΟN)\b", clean_title, re.IGNORECASE
                )
                if m_ton:
                    capacity = f"{m_ton.group(1)}T"
                elif is_ac:
                    # AC capacity codes
                    for t in tokens + clean_title.split():
                        t_c = t.strip("-_., \"'")
                        ton = get_capacity_tonnage(t_c, detected_brand)
                        if not ton and re.match(r"^\d{2}K$", t_c, re.IGNORECASE):
                            ton = get_capacity_tonnage(t_c[:2], detected_brand)
                        if ton:
                            capacity = f"{ton}T"
                            break
                    if not capacity and anchor:
                        m_anc_cap = re.match(
                            r"^(?:[A-Za-z]{2,4}-)?(\d{2})(?:K\b|[A-Za-z])", anchor, re.IGNORECASE
                        )
                        if m_anc_cap:
                            ton = get_capacity_tonnage(m_anc_cap.group(1), detected_brand)
                            if ton:
                                capacity = f"{ton}T"

    if not capacity:
        # Water Dispenser Tap Count (e.g. 2 Tap vs 3 Tap)
        m_tap = re.search(
            r"\b([1-4])\s*[-]?\s*(?:TAPS?|FAUCETS?)\b|\b(SINGLE|TWO|THREE|FOUR|DOUBLE)\s*(?:TAPS?|FAUCETS?)\b",
            clean_title,
            re.IGNORECASE,
        )
        if m_tap:
            val = m_tap.group(1) or m_tap.group(2)
            word_map = {"SINGLE": "1", "TWO": "2", "DOUBLE": "2", "THREE": "3", "FOUR": "4"}
            tap_num = word_map.get(val.upper(), val)
            capacity = f"{tap_num}TAP"

    # 2e. Tub Series (slash-attached /WB is Wide Body on washers, Wood Brown color on non-washer stems)
    is_washer_tub_ctx = detected_family == "WASHING_MACHINE" or bool(
        re.search(
            r"\b(?:[A-Za-z]{2,4}[-_])?\d{2,3}-\d{3,4}/(?:WB|GB)\b",
            clean_title,
            re.IGNORECASE,
        )
    )
    if is_washer_tub_ctx:
        m_tub = re.search(r"\b\d+(?:-\d+)?/?(WB|GB)\b|\b(WB|GB)\b", clean_title, re.IGNORECASE)
    else:
        m_tub = re.search(r"\b\d+(?:-\d+)?(WB|GB)\b|(?<!/)\b(WB|GB)\b", clean_title, re.IGNORECASE)
    tub_series = (m_tub.group(1) or m_tub.group(2)).upper() if m_tub else None

    # 2f. Color Family & Raw
    color_fam, color_raw = normalize_color(raw_clean, anchor=anchor)
    if not color_fam:
        color_fam, color_raw = normalize_color(clean_title, anchor=anchor)

    # 2g. Hardware Door Finish (GD vs INOX vs METAL)
    door_finish = None
    if re.search(r"\b(?:GD|GLASS\s+DOOR)\b", clean_title, re.IGNORECASE):
        door_finish = "GD"
    elif re.search(r"\b(?:INOX|STAINLESS(?:\s+STEEL)?|S\.S)\b", clean_title, re.IGNORECASE):
        door_finish = "INOX"
    elif re.search(r"\b(?:METAL\s+DOOR|STEEL\s+DOOR|VCM\s+DOOR)\b", clean_title, re.IGNORECASE):
        door_finish = "METAL"

    door_type = None
    if re.search(r"\b(?:SD|SINGLE\s+DOOR)\b", clean_title, re.IGNORECASE):
        door_type = "SD"
    elif re.search(r"\b(?:DD|DOUBLE\s+DOOR)\b", clean_title, re.IGNORECASE):
        door_type = "DD"

    # 2g3. Washer Tub Architecture (TWIN vs SINGLE)
    tub_type = None
    if re.search(
        r"\b(?:TT|TWIN[\s\-]*TUB|DOUBLE[\s\-]*TUB|WASH(?:ER|ING)?\s*(?:&|AND|/|\+)\s*SPIN(?:NER)?(?:\s*DRYER)?)\b",
        clean_title,
        re.IGNORECASE,
    ):
        tub_type = "TWIN"
    elif re.search(
        r"\b(?:ST|SINGLE[\s\-]*TUB|WASHER\s+ONLY|SPINNER\s+ONLY)\b", clean_title, re.IGNORECASE
    ) or (
        re.search(r"\b(?:SPINNER|DRYER)\b", clean_title, re.IGNORECASE)
        and not re.search(r"\b(?:WASH(?:ER|ING)|TWIN|DOUBLE)\b", clean_title, re.IGNORECASE)
    ):
        tub_type = "SINGLE"

    # 2g4. Washer Automation Type (AUTO vs SEMI)
    automation_type = None
    is_dw_semi_series = bool(
        (anchor and re.match(r"^DW-\d+", anchor, re.IGNORECASE))
        or re.search(r"\bDW[-_\s]*\d{3,4}\b", clean_title, re.IGNORECASE)
    )
    if re.search(r"\b(?:SEMI[\s\-]*AUTO(?:MATIC)?|MANUAL)\b", clean_title, re.IGNORECASE):
        automation_type = "SEMI"
    elif re.search(r"\b(?:FA|FULLY[\s\-]*AUTO(?:MATIC)?)\b", clean_title, re.IGNORECASE) or (
        re.search(
            r"\b(?<!SEMI[\s\-])AUTO(?:MATIC)?(?:\s*WASH(?:ING|ER)?)?\b", clean_title, re.IGNORECASE
        )
        and tub_type != "TWIN"
        and not is_dw_semi_series
    ):
        automation_type = "AUTO"

    # 2g2. Washer Loading Type (FL vs TL)
    # Guard 2-letter 'FL'/'TL' abbreviations when the listing explicitly declares Twin/Single Tub or Semi-Auto
    # (e.g. 'DW-10600 W FL Twin Tub Semi Automatic', where 'FL' is a lid/filter SKU suffix, not Front Load).
    load_type = None
    if re.search(r"\bFRONT\s*LOAD(?:ING)?\b", clean_title, re.IGNORECASE):
        load_type = "FL"
    elif re.search(r"\bTOP\s*LOAD(?:ING)?\b", clean_title, re.IGNORECASE):
        load_type = "TL"
    elif tub_type not in {"TWIN", "SINGLE"} and automation_type != "SEMI":
        if re.search(r"\bFL\b", clean_title, re.IGNORECASE):
            load_type = "FL"
        elif re.search(r"\bTL\b", clean_title, re.IGNORECASE):
            load_type = "TL"

    # 2g5. Refrigerator Defrost System (NO_FROST vs DIRECT_COOL)
    defrost_type = None
    if re.search(r"\b(?:NO[\s\-]*FROST|FROST[\s\-]*FREE)\b", clean_title, re.IGNORECASE):
        defrost_type = "NO_FROST"
    elif re.search(r"\b(?:DIRECT[\s\-]*COOL)\b", clean_title, re.IGNORECASE):
        defrost_type = "DIRECT_COOL"

    # 2h. Inverter Mode
    has_ac_dc_suffix = bool(
        (detected_family == "AIR_CONDITIONER" or (is_ac and not is_non_ac))
        and (
            any(
                re.search(r"(?:^|/|-|\b)(?:\d{0,3})?DC(?:\(|$|\b)", sub_c, re.IGNORECASE)
                for sub_c in subordinate_codes
            )
            or bool(
                re.search(
                    r"\b(?:[A-Za-z]{2,4}[-_])?\d{2}[A-Za-z]{1,5}-(?:\d{0,3})?DC\b",
                    clean_title,
                    re.IGNORECASE,
                )
            )
        )
    )
    is_inverter = None
    if re.search(
        r"\b(?:NON[\s\-]*INVERTER|FIX(?:ED)?\s*SPEED|CONVENTIONAL)\b", clean_title, re.IGNORECASE
    ):
        is_inverter = False
    elif (
        re.search(r"\b(?:INVERTER|INV|DC\s*INVERTER|SAVEIN)\b", clean_title, re.IGNORECASE)
        or (anchor and re.search(r"(?:SVN|INV)", anchor, re.IGNORECASE))
        or has_ac_dc_suffix
    ):
        is_inverter = True

    # 2i. Dynamic Post-Model Code, Capability Polarity & Category 2 Modifiers Engine
    # Scans capabilities with boundary-safe polarity & ambiguity quarantine ((?!\w) preserves ADS+)
    # and dynamically grabs post-model codes (e.g. ES, ES8, S6) with ZERO hardcoding.
    raw_pos_caps: set[str] = set()
    raw_neg_caps: set[str] = set()
    polarity_matches: list[tuple[bool, str]] = []
    for m_pol in CAPABILITY_POLARITY_PATTERN.finditer(clean_title):
        has_neg = bool(m_pol.group(1))
        norm_pol_tok = _normalize_capability_token(m_pol.group(2))
        polarity_matches.append((has_neg, norm_pol_tok))

    has_pos_wifi = any(not neg and tok == "WIFI" for neg, tok in polarity_matches)
    for has_neg, norm_pol_tok in polarity_matches:
        eff_tok = (
            "SMART"
            if (norm_pol_tok == "SMART" and is_display)
            else ("IOT" if norm_pol_tok == "SMART" else norm_pol_tok)
        )
        if has_neg:
            raw_neg_caps.add(eff_tok)
        else:
            raw_pos_caps.add(eff_tok)

    if is_display and re.search(
        r"\b(?:GOOGLE\s+TV|ANDROID(?:\s+TV)?|WEBOS|VIDAA)\b", clean_title, re.IGNORECASE
    ):
        raw_pos_caps.add("SMART")

    ambiguous_caps: set[str] = set(raw_pos_caps & raw_neg_caps)
    if ({"ADS", "ADS+"} & raw_pos_caps) and ({"ADS", "ADS+"} & raw_neg_caps):
        ambiguous_caps |= ({"ADS", "ADS+"} & (raw_pos_caps | raw_neg_caps))
    if has_pos_wifi and "IOT" not in ambiguous_caps and "IOT" not in raw_neg_caps:
        raw_pos_caps.discard("IOT")
    neg_caps: set[str] = set(raw_neg_caps - ambiguous_caps)
    caps: set[str] = set(raw_pos_caps - ambiguous_caps)

    clean_title_for_post = CAPABILITY_POLARITY_PATTERN.sub(
        lambda m: " " if m.group(1) else m.group(0),
        clean_title,
    )

    # 2. Extract candidate modifier tokens:
    candidate_tokens: list[str] = []

    # A0. Tag extracted from first token:
    if first_token_tag:
        clean_tag = first_token_tag.strip("()[]-.,_ \"'/").upper()
        if is_sku_variant_tag(clean_tag):
            candidate_tokens.append(clean_tag)

    # A. Hyphenated trailing modifier attached directly to the model/anchor (e.g. 18AITH24S-T3 -> T3, DWT-11467-ES -> ES)
    if anchor and "-" in anchor:
        anc_parts = anchor.split("-")
        if (
            len(anc_parts) > 1
            and any(re.search(r"\d", p) for p in anc_parts[:-1])
            and is_sku_variant_tag(anc_parts[-1])
        ):
            candidate_tokens.append(anc_parts[-1].upper())

    # B. Trailing tokens immediately following the model in raw_model (ONLY when an SKU anchor exists;
    # when anchor == "", tokens are series words + capacity code, never post-SKU variant suffixes):
    if anchor:
        post_model_tokens = (
            tokens[2:]
            if (len(tokens) >= 2 and tokens[0].isdigit() and len(tokens[0]) <= 2)
            else tokens[1:]
        )
        for t in post_model_tokens:
            t_clean = t.strip("()[]-.,_ \"'/").upper()
            if is_sku_variant_tag(t_clean):
                candidate_tokens.append(t_clean)

    # C. Search code right after the model AND across all remaining tokens in clean_title:
    post_words: list[str] = []
    if anchor:
        post_anchor = _text_after_anchor(clean_title_for_post, anchor)
        if post_anchor is not None:
            post_words = post_anchor.split()
        else:
            # Fallback: check if numeric stem exists in title
            m_stem = re.search(r"\d{3,}", anchor)
            if m_stem:
                idx = clean_title_for_post.find(m_stem.group(0))
                if idx != -1:
                    post_anchor = clean_title_for_post[idx + len(m_stem.group(0)) :]
                    post_words = post_anchor.split()

    _POST_STOP_WORDS = {
        "REGULAR",
        "DEEP",
        "FREEZER",
        "BRAND",
        "NEW",
        "BOX",
        "PACK",
        "WITH",
        "ORIGINAL",
        "WARRANTY",
        "BEST",
        "PRICE",
        "ON",
        "INSTALLMENT",
        "INSTALLMENTS",
        "MARKUP",
        "MARK",
        "UP",
        "0%",
        "EMI",
        "STUCCO",
        "PCM",
        "ARC",
        "WHITE",
        "BLACK",
        "GREY",
        "SILVER",
        "TECH",
        "HOUSE",
        "ISPK",
        "COD",
        "GIFT",
        "FREE",
        "BUDS",
        "AIRBUDS",
        "EARBUDS",
        "ET",
        "FEES",
        "PROCESSING",
        "STAR",
        "ESTAR",
        "E-STAR",
        "DELIVERY",
        "INSTALLATION",
        "UPS",
        "ENABLED",
        "ENABLE",
        "SELF",
        "CLEAN",
        "CLEANING",
        "TURBO",
        "AMP",
        "LOCK",
        "AMPERE",
        "HEAT",
        "COOL",
        "YEAR",
        "YEARS",
    }
    for w in post_words:
        if w.strip() in ("-", "–", "—", "|"):
            break
        w_clean = w.strip("()[]-.,_ \"'/|").upper()
        if not w_clean:
            continue
        if w_clean in _POST_STOP_WORDS or "%" in w:
            break
        if is_sku_variant_tag(w_clean):
            candidate_tokens.append(w_clean)
        elif "-" in w:
            w_parts = [
                p.strip("()[]-.,_ \"'/|").upper() for p in w.split("-") if p.strip("()[]-.,_ \"'/|")
            ]
            if w_parts and w_parts[-1] in _POST_STOP_WORDS:
                break
            # Only extract hyphenated suffix when the prefix is a model stem (contains digits)
            if len(w_parts) >= 2 and any(re.search(r"\d", p) for p in w_parts[:-1]):
                w_sub = w_parts[-1]
                if is_sku_variant_tag(w_sub):
                    candidate_tokens.append(w_sub)

    # D. Glued trailing code on numeric stem >= 3 digits (e.g. DWT11467ES -> ES, 11467ES8 -> ES8)
    m_glued_stem = re.search(r"\b[A-Za-z]{0,4}(\d{3,})([A-Za-z]{2,4})\b", clean_title)
    if m_glued_stem:
        glued_tag = m_glued_stem.group(2).upper()
        if is_sku_variant_tag(glued_tag):
            candidate_tokens.append(glued_tag)

    # Tokens managed by dedicated orthogonal slots or soft styling residuals:
    dedicated_orthogonal_slots = {
        "GD",
        "INOX",
        "DD",
        "INVERTER",
        "INV",
        "WB",
        "GB",
        "GC",
        "FH",
        "CHROME",
        "LVS",
        "WFL",
        "CFL",
    }

    if is_ac:
        dedicated_orthogonal_slots.add("DC")

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
        if tok == "ADS" and "ADS+" in caps:
            continue
        # Category 2: All other hardware/variant codes go here dynamically (e.g. ES, ES8, T3, T4, UV, S6)!
        caps.add(tok)

    # Enforce strict polarity quarantine: negated or ambiguous tokens can never leak into positive caps
    caps -= neg_caps | ambiguous_caps | {"NON", "WITHOUT", "NOT", "NONT3", "NONT4"}
    if ("ADS+" in neg_caps or "ADS+" in ambiguous_caps) and "ADS" in caps:
        caps.discard("ADS")

    guarded = GuardedFacets(
        capacity=capacity,
        tub_series=tub_series,
        color_family=color_fam,
        color_raw=color_raw,
        door_finish=door_finish,
        cool_only=cool_only,
        heat_and_cool=heat_and_cool,
        door_type=door_type,
        load_type=load_type,
        tub_type=tub_type,
        automation_type=automation_type,
        defrost_type=defrost_type,
        is_inverter=is_inverter,
        capabilities=caps,
        negative_capabilities=neg_caps,
        ambiguous_capabilities=ambiguous_caps,
        allowed_feature_tags=allowed_tags,
    )

    # 3. Soft Residual Modifiers
    residuals: list[str] = []
    for m_gc in re.finditer(
        r"\b(?:GC|GLASS\s+DOOR|CLEAR\s+(?:FLAT\s+)?LID|CFL|GLASS\s+(?:FLAT\s+)?LID|WHITE\s+(?:FLAT\s+)?LID|WFL|PILLOW\s+DRUM)\b",
        clean_title,
        re.IGNORECASE,
    ):
        val_gc = re.sub(r"\s+", " ", m_gc.group(0).upper().strip())
        if val_gc not in residuals:
            residuals.append(val_gc)
    if anchor:
        post_anchor = _text_after_anchor(clean_title, anchor)
        if post_anchor is not None:
            for t in post_anchor.split():
                t_c = t.strip("-.,_ \"'")
                if is_sku_variant_tag(t_c) and t_c.upper() not in residuals:
                    residuals.append(t_c.upper())
        else:
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
    sub = re.sub(r"\b(?:METAL\s+DOOR|STEEL\s+DOOR|VCM\s+DOOR)\b", " ", sub, flags=re.IGNORECASE)
    sub = re.sub(
        r"\b(?:\d+(?:\.\d+)?\s*(?:CU\s*FT|CU\.FT|CFT|CU|LITRES?|LITERS?|LTRS?|LTR|L|KG|TON))\b",
        " ",
        sub,
        flags=re.IGNORECASE,
    )
    sub = re.sub(r"\b(?:SINGLE\s*TUB)\b", " ", sub, flags=re.IGNORECASE)
    # Dynamically strip any 2-4 letter brand/form-factor SKU prefix attached to anchor
    if anchor:
        if _is_dawlance_context(title_no_opt, brand=detected_brand):
            sub = re.sub(r"(?<!\d\s)\bX\b(?!\s*\d)", " ", sub, flags=re.IGNORECASE)
        sub = re.sub(rf"\b[A-Za-z]{{2,4}}[- ]?{re.escape(anchor)}\b", " ", sub, flags=re.IGNORECASE)
        sub = re.sub(rf"\b{re.escape(anchor)}\b", " ", sub, flags=re.IGNORECASE)
        anchor_unhyphenated = anchor.replace("-", "")
        sub = re.sub(
            rf"\b{re.escape(anchor_unhyphenated)}[A-Za-z0-9]*\b", " ", sub, flags=re.IGNORECASE
        )
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
        r"(?:(?<!\w)0%(?!\w)|\b(?:NON[\s\-]*INVERTER|E[\s\-]*STAR|FIX(?:ED)?\s*SPEED|CONVENTIONAL|T3|INVERTER|INV|\d{1,2}K|SMART|WIFI|WI-FI|IOT|FHD|HD|SPLIT|AC|AUTO|TOP\s+LOAD|FRONT\s+LOAD|AAA\+|AA\+|A\+{1,3}|AAA|AA)\b)",
        " ",
        sub,
        flags=re.IGNORECASE,
    )
    if tub_series:
        sub = re.sub(rf"(?:/|\b){re.escape(tub_series)}\b", " ", sub, flags=re.IGNORECASE)
    if color_raw and len(color_raw) <= 3:
        sub = re.sub(rf"(?:/|\b){re.escape(color_raw)}\b", " ", sub, flags=re.IGNORECASE)
    if door_finish:
        sub = re.sub(rf"(?:/|\b){re.escape(door_finish)}\b", " ", sub, flags=re.IGNORECASE)
    sub = CAPABILITY_POLARITY_PATTERN.sub(" ", sub)
    for r in residuals:
        sub = re.sub(rf"\b{re.escape(r)}\b", " ", sub, flags=re.IGNORECASE)
    for c in caps | neg_caps | ambiguous_caps:
        c_core = c.rstrip("+")
        if c_core:
            sub = re.sub(rf"\b{re.escape(c_core)}\+?(?!\w)", " ", sub, flags=re.IGNORECASE)
    for c1 in CATEGORY_1_DIRECT_MATCH_MODIFIERS:
        sub = re.sub(rf"\b{re.escape(c1)}\b", " ", sub, flags=re.IGNORECASE)
    # Strip all color tokens
    sub_words = [
        tok for tok in sub.split() if tok.upper() not in ALL_COLOR_WORDS and not is_color_token(tok)
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

    series_tokens = [tok if tok == "/" else tok.strip("()[]-.,_ \"'+|%") for tok in sub.split()]
    series_tokens = [
        tok
        for tok in series_tokens
        if tok
        and (
            tok == "/"
            or (
                tok.upper() not in NON_SKU_TOKENS
                and (len(tok) > 1 or tok.upper() in GENUINE_SUB_SERIES_TOKENS)
                and not tok.isdigit()
            )
        )
    ]
    series = " ".join(series_tokens).strip()
    series = re.sub(r"\s*/\s*", " / ", series).strip(" /")

    base_stem, sub_model_tag = _decompose_ac_sku(anchor, is_ac and not is_display)

    return ProductSlots(
        anchor=anchor,
        series=series,
        guarded_facets=guarded,
        residuals=residuals,
        subordinate_codes=subordinate_codes,
        base_stem=base_stem,
        sub_model_tag=sub_model_tag,
    )


LEGITIMATE_EDITION_EXTENSIONS: frozenset[str] = frozenset({"EX"})


def _strip_leading_sku_prefix(norm_code: str) -> tuple[str, str]:
    """Split normalized uppercase SKU into (leading_alpha_prefix, core_stem) when digits follow."""
    m = re.match(r"^([A-Z]{2,4})(\d.+)$", norm_code)
    if m:
        return m.group(1), m.group(2)
    return "", norm_code


def _evaluate_anchor_compatibility(
    norm_t: str,
    norm_c: str,
    target_slots: ProductSlots,
    cand_slots: ProductSlots,
    candidate_title: str,
) -> tuple[bool, str | None]:
    """Evaluate structured SKU anchor compatibility between target and candidate.

    Distinguishes:
    1. Exact core model stems (including prefix-optional forms: 13HFCP <-> HSU-13HFCP, 91999 <-> DW-91999).
    2. Legitimate edition extensions (e.g. 20HFT -> HSU-20HFTEX, 14HFT -> HSU-14HFTEX), returning
       an explicit scraped designation label for downstream yellow compatibility notices.
    3. Orthogonal tub/color/single-letter variant suffixes handled by dedicated facet guards.
    4. Genuinely incompatible sub-models/suffixes (e.g. 18HFPCA != HSU-18HFP, 18HFP != 18HFPAAS,
       19HFPAA != HSU-19HFP, 19HFC != HSU-19HFCS, 13LF != HSU-13HFP), returning (False, None).
    """
    norm_t_eq = norm_t.replace("SAVEIN", "SVN")
    norm_c_eq = norm_c.replace("SAVEIN", "SVN")
    if norm_t_eq == norm_c_eq:
        return True, None

    _, stem_t = _strip_leading_sku_prefix(norm_t_eq)
    _, stem_c = _strip_leading_sku_prefix(norm_c_eq)
    if stem_t == stem_c:
        return True, None

    # Symmetric screen/capacity-prefixed stem equivalence (e.g. '32" D2' [anchor='D2', cap='32INCH'] <-> '32D2')
    t_cap = target_slots.guarded_facets.capacity
    c_cap = cand_slots.guarded_facets.capacity
    if not (t_cap and c_cap and t_cap != c_cap):
        eff_cap = t_cap or c_cap or ""
        m_cap_dig = re.match(r"^(\d{2,3})INCH$", eff_cap)
        if m_cap_dig:
            cap_dig = m_cap_dig.group(1)
            if f"{cap_dig}{stem_t}" == stem_c or f"{cap_dig}{stem_c}" == stem_t:
                return True, None

    t_nums = re.findall(r"\d{2,}", stem_t)
    c_nums = re.findall(r"\d{2,}", stem_c)
    if t_nums and c_nums:
        if len(t_nums) > 1 and len(c_nums) > 1 and set(t_nums) != set(c_nums):
            return False, None
        if len(t_nums) == 1 and len(c_nums) == 1 and t_nums[0] != c_nums[0]:
            return False, None
        if (
            len(t_nums) == 1
            and len(c_nums) > 1
            and not _is_valid_single_to_multi_num_match(target_slots, cand_slots, t_nums, c_nums)
        ):
            return False, None
        if len(t_nums) > 1 and len(c_nums) == 1:
            return _matches_single_num_candidate(target_slots, cand_slots, candidate_title), None

    # Case A: Candidate stem extends target stem (stem_c == stem_t + ext)
    if stem_c.startswith(stem_t) and len(stem_c) > len(stem_t):
        ext = stem_c[len(stem_t) :]
        # Pure numeric stem (>= 3 digits, e.g. 9140 -> 9140WB, DWT-255 -> DWT-255C)
        if stem_t.isdigit() and len(stem_t) >= 3:
            if (
                ext in {"WB", "GB", "GD", "SD", "DD"}
                or ext in COLOR_SUFFIX_MAP
                or (len(ext) == 1 and ext.isalpha())
            ):
                return True, None
            return False, None

        # Alphanumeric model stem:
        # 1. Explicit Legitimate Edition Extension (e.g. 20HFT -> HSU-20HFTEX, 14HFT -> HSU-14HFTEX)
        ext_core = ext
        for col_code in ("OW", "DG"):
            if ext_core.endswith(col_code) and len(ext_core) > len(col_code):
                ext_core = ext_core[: -len(col_code)]
                break
        if ext_core in LEGITIMATE_EDITION_EXTENSIONS and re.match(r"^\d{2,}[A-Z]{2,}$", stem_t):
            designation = cand_slots.anchor.strip() or norm_c
            return True, designation

        # 2. Trailing color suffix attached to SKU (2-letter OW/DG, or 1-letter after a digit like 12AITH21W)
        if ext in {"OW", "DG", "SG", "SW"} or (stem_t[-1].isdigit() and ext in COLOR_SUFFIX_MAP):
            return True, None

        # 3. Delimited multi-part subordinate descriptor after >= 5-char stem (e.g. 12SVN -> 12SVN-AI-CO-31S, 24CE03 -> 24CE03/KB-01)
        # or delimited electrical power tag (-DC/-AC) after >= 4-char stem (e.g. 18HE -> 18HE-DC)
        cand_anc_eq = cand_slots.anchor.upper().replace("SAVEIN", "SVN")
        if (len(stem_t) >= 5 or (len(stem_t) >= 4 and ext in {"DC", "AC"})) and re.search(
            rf"{re.escape(stem_t)}[-_/]", cand_anc_eq
        ):
            return True, None

        return False, None

    # Case B: Target stem extends candidate stem (stem_t == stem_c + rem)
    if stem_t.startswith(stem_c) and len(stem_t) > len(stem_c):
        rem = stem_t[len(stem_c) :]
        if stem_c.isdigit() and len(stem_c) >= 3:
            if (
                rem in {"WB", "GB", "GD", "SD", "DD"}
                or rem in COLOR_SUFFIX_MAP
                or (len(rem) == 1 and rem.isalpha())
            ):
                return True, None
            return False, None

        if rem in {"OW", "DG", "SG", "SW"} or (stem_c[-1].isdigit() and rem in COLOR_SUFFIX_MAP):
            return True, None

        targ_anc_eq = target_slots.anchor.upper().replace("SAVEIN", "SVN")
        if (len(stem_c) >= 5 or (len(stem_c) >= 4 and rem in {"DC", "AC"})) and re.search(
            rf"{re.escape(stem_c)}[-_/]", targ_anc_eq
        ):
            return True, None

        if (
            target_slots.base_stem
            and cand_slots.base_stem
            and target_slots.base_stem == cand_slots.base_stem
            and target_slots.sub_model_tag != ""
        ):
            return True, None

        return False, None

    # Shared 2-digit capacity + 3-letter AC core series stem fallback (Tier 2 Base & Tier 3 Sibling):
    # Permitted ONLY when target specifies a sub_model_tag (e.g. 18HFPCA -> 18HFP or 18HFPE);
    # bare base targets (e.g. 19HFC) never match upgraded non-EX sub-models (e.g. 19HFCS).
    if (
        target_slots.base_stem
        and cand_slots.base_stem
        and target_slots.base_stem == cand_slots.base_stem
        and target_slots.sub_model_tag != ""
    ):
        return True, None

    return False, None


def _is_valid_single_to_multi_num_match(
    target_slots: ProductSlots,
    cand_slots: ProductSlots,
    t_nums: list[str],
    c_nums: list[str],
) -> bool:
    """Check if a single-number target anchor validly matches a multi-number candidate anchor."""
    if len(t_nums) != 1 or len(c_nums) <= 1:
        return False
    t_num = t_nums[0]
    if t_num not in c_nums:
        return False
    # Check alphabetic prefix compatibility if both anchors have leading letters
    m_pfx_t = re.match(r"^([A-Za-z]+)", target_slots.anchor)
    m_pfx_c = re.match(r"^([A-Za-z]+)", cand_slots.anchor)
    if m_pfx_t and m_pfx_c and m_pfx_t.group(1).upper() != m_pfx_c.group(1).upper():
        return False
    # Reject compound multi-number anchors (both pure-digit '120-826' and alphanumeric '120-B699S8', '120-M826', '260-X500')
    # as well as any candidate anchor carrying a second >= 3-digit model stem (preserving 2-digit TV screen sizes & 2-digit AC gen tags).
    if re.search(r"\d{2,4}-[A-Za-z]{0,4}\d{2,5}", cand_slots.anchor):
        return False
    if any(len(n) >= 3 for n in c_nums if n != t_num) or c_nums.count(t_num) > 1:
        return False
    return len(t_num) >= 3


_WASHER_SPINNER_BUNDLE_RE = re.compile(
    r"\b(?:WASH(?:ER|ING\s+MACHINE)\b[^|()\n]{0,35}?(?:\+|\bWITH\b)[^|()\n]{0,35}?\b(?:SPIN(?:NER)?|DRYER)\b"
    r"|WASH(?:ER|ING\s+MACHINE)\s*(?:&|\bAND\b)\s*(?:SPIN(?:NER)?|DRYER)\s+(?:COMBO|BUNDLE|PACK(?:AGE)?|SET|PAIR|DEAL)\b"
    r"|\b(?:SPIN(?:NER)?|DRYER)\s+(?:COMBO|BUNDLE|PACKAGE\s+DEAL)\b"
    r"|(?:COMBO|BUNDLE)\s+(?:PACK|DEAL|OFFER|SET)\b.*?\b(?:SPIN(?:NER)?|DRYER)\b)",
    re.IGNORECASE,
)
_GENERIC_DUAL_APPLIANCE_SKU_RE = re.compile(
    r"\b([A-Za-z]{2,4})[-_ ]?(\d{3,5})\b[^/|()\n]{0,35}?(?:\+|&|\bWITH\b|\bAND\b)[^/|()\n]{0,35}?\b([A-Za-z]{2,4})[-_ ]?(\d{3,5})\b",
    re.IGNORECASE,
)


def _has_dual_appliance_skus(text: str) -> bool:
    """Generic zero-dictionary detector for two distinct appliance SKUs combined in one bundle listing."""
    for m in _GENERIC_DUAL_APPLIANCE_SKU_RE.finditer(text):
        p1, n1, p2, n2 = m.group(1).upper(), m.group(2), m.group(3).upper(), m.group(4)
        if p1 in NON_SKU_TOKENS or p2 in NON_SKU_TOKENS:
            continue
        if is_dimension_or_spec_token(f"{p1}{n1}") or is_dimension_or_spec_token(f"{p2}{n2}"):
            continue
        if (p1, n1) != (p2, n2):
            return True
    return False


def _has_bundle_collision(target_text: str, candidate_title: str) -> bool:
    """Detect when candidate is a multi-unit washer+spinner/dryer combo/bundle but target is a single unit."""
    target_is_bundle = bool(
        _WASHER_SPINNER_BUNDLE_RE.search(target_text) or _has_dual_appliance_skus(target_text)
    )
    if target_is_bundle:
        return False
    return bool(
        _WASHER_SPINNER_BUNDLE_RE.search(candidate_title)
        or _has_dual_appliance_skus(candidate_title)
    )


def _matches_single_num_candidate(
    target_slots: ProductSlots,
    cand_slots: ProductSlots,
    candidate_title: str,
) -> bool:
    """Verify if single-number candidate validly matches multi-number target (e.g. TV display screen size)."""
    if (
        re.search(rf"\b{re.escape(target_slots.anchor)}\b", candidate_title, re.IGNORECASE)
        is not None
    ):
        return True
    t_cap = target_slots.guarded_facets.capacity
    c_cap = cand_slots.guarded_facets.capacity
    return bool(t_cap and c_cap and t_cap == c_cap and "INCH" in t_cap)


def _matches_brand_initial_synthesis(
    norm_t: str,
    cand_anchor: str,
    norm_cand_title: str,
    brand: str,
) -> bool:
    """Dynamic Brand-Initial Prefix Synthesis for asymmetric unprefixed-to-prefixed stems (e.g. '11LF' <-> 'HRF-11LF').

    Strictly forbids overriding explicit conflicting alphabetic SKU prefixes (e.g. HRF-240 vs HWM-240).
    """
    if not brand or not norm_t:
        return False
    b_init = brand[0].upper()
    norm_c = re.sub(r"[^A-Z0-9]", "", cand_anchor.upper()) if cand_anchor else ""

    # Never synthesize across two explicit conflicting alphabetic SKU prefixes
    m_alpha_t = re.match(r"^([A-Z]{2,4})\d", norm_t)
    m_alpha_c = re.match(r"^([A-Z]{2,4})\d", norm_c)
    if m_alpha_t and m_alpha_c and m_alpha_t.group(1) != m_alpha_c.group(1):
        return False

    # Case 1: Unprefixed target ('11LF', '13HFN', '216') -> Brand-initial prefixed candidate ('HRF11LF', 'HSU13HFN')
    if norm_t[0].isdigit() and re.search(
        rf"{b_init}[A-Z]{{1,3}}{re.escape(norm_t)}(?!\d)", norm_cand_title
    ):
        return True

    # Case 2: Brand-initial prefixed target ('HRF216') -> Unprefixed candidate anchor ('216')
    if m_alpha_t and m_alpha_t.group(1).startswith(b_init) and norm_c and norm_c[0].isdigit():
        core_t = norm_t[len(m_alpha_t.group(1)) :]
        if core_t == norm_c:
            return True

    return False


def _has_variant_tag_collision(norm_t: str, norm_c: str) -> bool:
    """Detect conflicting 2-letter variant tags (e.g. 50MB vs 50DB)."""
    if len(norm_t) < 4 or len(norm_c) < 4:
        return False
    suf_t, suf_c = norm_t[-2:], norm_c[-2:]
    if not (suf_t.isalpha() and suf_c.isalpha()):
        return False
    if norm_t[:2] != norm_c[:2] or suf_t == suf_c:
        return False
    # If one is simply a base prefix of the other, not a collision
    if norm_c.startswith(norm_t) or norm_t.startswith(norm_c):
        return False
    return not (norm_c == norm_t[:-2] or norm_t == norm_c[:-2])


def _has_generation_series_collision(norm_t: str, norm_c: str) -> tuple[bool, str]:
    """Detect generation / series code collision (e.g. S8 vs S6, G1 vs G2)."""
    gen_t = re.search(r"([A-Z]\d)$", norm_t)
    gen_c = re.search(r"([A-Z]\d)$", norm_c)
    if gen_t and gen_c and gen_t.group(1) != gen_c.group(1):
        return True, f"{gen_t.group(1)} vs {gen_c.group(1)} ({norm_t} vs {norm_c})"
    return False, ""


def _extract_stem_single_letter_variant(
    text: str, anchor: str = "", brand: str = ""
) -> str | None:
    """Extract single-letter variant suffix (e.g. 'C', 'S', 'G', 'W', 'E') attached to or following a 3+ digit model stem."""
    check_str = f"{anchor} {text}".strip()
    is_daw = _is_dawlance_context(text, brand=brand)
    # 1. Hyphenated anchor suffix: DWT-255-C, DWT-270-S
    if anchor and "-" in anchor:
        parts = anchor.split("-")
        if (
            len(parts) >= 2
            and any(re.search(r"\d{3,}", p) for p in parts[:-1])
            and len(parts[-1]) == 1
            and parts[-1].isalpha()
        ):
            cand_v = parts[-1].upper()
            if not (is_daw and cand_v == "X"):
                return cand_v
    # 2. Glued or spaced on prefix/capacity+digits (or alphanumeric sub-stem like 1678S8 E):
    m = re.search(
        r"(?:[A-Za-z]{2,4}[-_ ]?|\b\d{1,3}[-_ ])(\d{3,6}(?:[A-Za-z]{1,2}\d)?)[-_ ]?([A-Za-z])(?![A-Za-z0-9]|-[A-Za-z0-9])",
        check_str,
    )
    if m:
        cand_v = m.group(2).upper()
        if not (is_daw and cand_v == "X"):
            return cand_v
    return None


def _resolve_effective_single_letter_variant(
    raw_text: str, slots: ProductSlots, brand: str = ""
) -> tuple[str | None, str | None]:
    """Resolve single-letter variant suffix and human-readable label from stem suffix or lid phrases."""
    base_var = _extract_stem_single_letter_variant(raw_text, slots.anchor, brand=brand)
    res_set = {r.upper() for r in slots.residuals}
    if (
        "CLEAR LID" in res_set
        or "CLEAR FLAT LID" in res_set
        or "CFL" in res_set
        or bool(re.search(r"\bCLEAR\s+(?:FLAT\s+)?LID\b|\bCFL\b", raw_text, re.IGNORECASE))
    ):
        return "C", "Clear Lid"
    if (
        "GLASS LID" in res_set
        or "GLASS FLAT LID" in res_set
        or bool(re.search(r"\bGLASS\s+(?:FLAT\s+)?LID\b", raw_text, re.IGNORECASE))
    ):
        return "G", "Glass Lid"
    if (
        "WHITE LID" in res_set
        or "WHITE FLAT LID" in res_set
        or "WFL" in res_set
        or bool(re.search(r"\bWHITE\s+(?:FLAT\s+)?LID\b|\bWFL\b", raw_text, re.IGNORECASE))
    ):
        return "W", "White Lid"
    if base_var:
        return base_var, f"Variant {base_var}"
    return None, None


def _detect_ac_form_factor(text: str) -> str | None:
    """Detect explicit AC physical mounting form-factor (SPLIT vs FLOOR_STANDING vs CASSETTE vs PORTABLE vs WINDOW)."""
    if re.search(
        r"\b(?:FLOOR\s*STANDING|CABINET(?:\s+AC)?|TOWER\s+AC|STANDING\s+AC)\b", text, re.IGNORECASE
    ):
        return "FLOOR_STANDING"
    if re.search(r"\bCASSETTE\b", text, re.IGNORECASE):
        return "CASSETTE"
    if re.search(r"\bPORTABLE\s*(?:AC|AIR\s*CONDITIONER)\b", text, re.IGNORECASE):
        return "PORTABLE"
    if re.search(r"\bWINDOW\s*(?:AC|AIR\s*CONDITIONER)\b", text, re.IGNORECASE):
        return "WINDOW"
    if re.search(r"\b(?:SPLIT|WALL\s*MOUNT(?:ED)?)\b", text, re.IGNORECASE):
        return "SPLIT"
    return None


def _detect_appliance_family(text: str) -> str | None:
    """Detect explicit macro-appliance product category when stated unambiguously in title text."""
    if re.search(
        r"\b(?:TELEVISION|SMART\s*TV|LED\s*TV|QLED|OLED|UHD\s*TV|GOOGLE\s*TV|ANDROID\s*TV|MONITOR)\b",
        text,
        re.IGNORECASE,
    ):
        return "TV_DISPLAY"
    if re.search(r"\b(?:MICROWAVE|MWO|BAKING\s*OVEN)\b", text, re.IGNORECASE):
        return "MICROWAVE_OVEN"
    if re.search(r"\b(?:WATER\s*DISPENSER|DISPENSER)\b", text, re.IGNORECASE):
        return "WATER_DISPENSER"
    if re.search(r"\b(?:AIR\s*FRYER|AIRFRYER)\b", text, re.IGNORECASE):
        return "AIR_FRYER"
    if re.search(
        r"\b(?:JUICER|BLENDER|CHOPPER|SANDWI?T?CH\s*MAKER|TOASTER|JUG\s*KETTLE|ELECTRIC\s*KETTLE|FOOD\s*PROCESSOR)\b",
        text,
        re.IGNORECASE,
    ):
        return "SMALL_KITCHEN"
    if re.search(
        r"\b(?:WASHING\s*MACHINE|WASHER|TWIN[\s\-]*TUB|SINGLE[\s\-]*TUB|SPIN(?:NER)?\s*DRYER|CLOTHES\s*SPINNER|FRONT\s*LOAD|TOP\s*LOAD)\b",
        text,
        re.IGNORECASE,
    ):
        return "WASHING_MACHINE"
    if re.search(r"\b(?:REFRIGERATOR|FRIDGE|MINI\s*BAR|MINIBAR)\b", text, re.IGNORECASE):
        return "REFRIGERATOR"
    if re.search(r"\b(?:DEEP\s*FREEZER|CHEST\s*FREEZER)\b", text, re.IGNORECASE):
        return (
            "DEEP_FREEZER"
            if not re.search(r"\bCONVERTIBLE\b", text, re.IGNORECASE)
            else "REFRIGERATOR"
        )
    if re.search(r"\b(?:AIR\s*COOLER|ROOM\s*COOLER|DESERT\s*COOLER)\b", text, re.IGNORECASE):
        return "AIR_COOLER"
    if re.search(
        r"\b(?:AIR\s*CONDITIONER|SPLIT\s*AC|INVERTER\s*AC|FLOOR\s*STANDING(?:\s*AC)?|CABINET\s*AC|CASSETTE\s*AC|AC)\b",
        text,
        re.IGNORECASE,
    ):
        return "AIR_CONDITIONER"
    return None


def _extract_slash_color_chain(text: str) -> list[str]:
    """Return distinct slash-separated color tokens (2-way or N-way) if present in text."""
    for m in re.finditer(r"\b([A-Za-z]+(?:\s*/\s*[A-Za-z]+)+)\b", text):
        parts = [p.strip() for p in m.group(1).split("/") if p.strip()]
        # Extract contiguous runs of >=2 distinct color tokens within any slash chain
        run: list[str] = []
        for p in parts:
            if is_color_token(p):
                run.append(p)
            else:
                if len(run) >= 2 and len({c.upper() for c in run}) >= 2:
                    return run
                run = []
        if len(run) >= 2 and len({c.upper() for c in run}) >= 2:
            return run
    return []


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
                if dec.is_base_match or dec.match_tier == 2:
                    return dec
            for dec in decs:
                if dec.match_tier == 3:
                    return dec
            for dec in decs:
                if any(
                    x in dec.reason.lower()
                    for x in ("mismatch", "collision", "contradiction", "conflict")
                ):
                    return dec
            return decs[0]

    cand_branches = expand_cartesian_branches(candidate_title)
    if len(cand_branches) > 1:
        decs = [referee_match(target, cb, brand=brand) for cb in cand_branches]
        target_has_col_slash = isinstance(target, str) and bool(_extract_slash_color_chain(target))
        cand_col_chain = _extract_slash_color_chain(candidate_title)
        for dec in decs:
            if dec.is_match:
                # TASK-10 & AUD-MED-02: If candidate has slash-separated dual/multi colors (e.g. White / Grey or White / Silver / Black)
                # and target is single-color or uncolored, annotate missing_modifier so downstream surfaces a Cross-Check Notice.
                if cand_col_chain and not target_has_col_slash and not dec.missing_modifier:
                    joined_cols = "/".join(c.title() for c in cand_col_chain)
                    dec.missing_modifier = f"Dual-Color ({joined_cols})"
                    dec.modifier_source = "market"
                    if not dec.compatibility_notice:
                        dec.compatibility_notice = (
                            f"⚠️ [CROSS-CHECK NOTICE: Market listing includes "
                            f"'{dec.missing_modifier}' not specified in target catalog]"
                        )
                return dec
        for dec in decs:
            if dec.is_base_match or dec.match_tier == 2:
                return dec
        for dec in decs:
            if dec.match_tier == 3:
                return dec
        for dec in decs:
            if any(
                x in dec.reason.lower()
                for x in ("mismatch", "collision", "contradiction", "conflict")
            ):
                return dec
        return decs[0]

    target_slots = extract_product_slots(target, brand=brand) if isinstance(target, str) else target
    cand_slots = extract_product_slots(candidate_title, brand=brand)

    # Polarity Rule A — Internal Candidate Ambiguity (100% REJECT)
    if cand_slots.guarded_facets.ambiguous_capabilities:
        conf_str = ", ".join(sorted(cand_slots.guarded_facets.ambiguous_capabilities))
        return MatchDecision(
            is_match=False,
            reason=(
                f"Ambiguous specification conflict ({conf_str}): "
                "Candidate title contains internally contradictory claims"
            ),
            target_slots=target_slots,
            candidate_slots=cand_slots,
            match_tier=None,
        )

    # Polarity Rule B — Explicit Opposing Capability Polarity Contradiction (100% REJECT)
    def _polarity_family_set(cap_set: set[str]) -> set[str]:
        expanded = set(cap_set)
        if {"ADS", "ADS+"} & expanded:
            expanded.add("ADS+")
        return expanded

    contradictions = (
        _polarity_family_set(target_slots.guarded_facets.capabilities)
        & _polarity_family_set(cand_slots.guarded_facets.negative_capabilities)
    ) | (
        _polarity_family_set(target_slots.guarded_facets.negative_capabilities)
        & _polarity_family_set(cand_slots.guarded_facets.capabilities)
    )
    if contradictions:
        contra_str = ", ".join(sorted(contradictions))
        return MatchDecision(
            is_match=False,
            reason=(
                f"Hardware capability contradiction ({contra_str}): "
                "Target and candidate specify opposing polarities"
            ),
            target_slots=target_slots,
            candidate_slots=cand_slots,
            match_tier=None,
        )

    # 0. Zero-Tolerance Brand Collision Guard & Dynamic Brand Extraction
    if brand:
        b_target = brand.strip().upper()
        target_init = b_target[0]
        cand_words = [
            w.strip("()[]-.,_ \"'/|:;#")
            for w in candidate_title.upper().split()
            if w.strip("()[]-.,_ \"'/|:;#")
        ]

        # 0a. Check if target brand is present in candidate title
        has_target_brand = False
        if re.search(rf"\b{re.escape(b_target)}\b", candidate_title, re.IGNORECASE):
            has_target_brand = True
        else:
            for w in cand_words:
                if len(w) >= 4 and SequenceMatcher(None, w, b_target).ratio() >= 0.85:
                    has_target_brand = True
                    break

        # 0b. Dynamic Candidate Brand Extraction (from beginning of listing title)
        # Filter out numbers, dimensions/units, appliance types, and generic product words
        NON_BRAND_TOKENS = {
            # Units & dimensions
            "TON",
            "TONS",
            "KG",
            "KGS",
            "INCH",
            "INCHES",
            "LTR",
            "LTRS",
            "LITER",
            "LITERS",
            "CUFT",
            "FT",
            "MM",
            "CM",
            "V",
            "VOLT",
            "W",
            "WATT",
            "WATTS",
            # Common marketing / status descriptors
            "NEW",
            "LATEST",
            "ORIGINAL",
            "GENUINE",
            "IMPORTED",
            "AUTHENTIC",
            "OFFICIAL",
            "PREMIUM",
            "SALE",
            "HOT",
            "BEST",
            # Generic structure / tech words
            "MODEL",
            "SERIES",
            "EDITION",
            "TYPE",
            "COLOR",
            "COLOUR",
            "SIZE",
            "AUTOMATIC",
            "SEMI",
            "MANUAL",
            "TOP",
            "FRONT",
            "LOAD",
            "LOADING",
            "INVERTER",
            "NON-INVERTER",
            "FIXED",
            "SPEED",
            "DC",
            "SMART",
            "PRIMA",
            "ECO",
            "PLUS",
            "PRO",
            "MAX",
            "ULTRA",
            "LVS",
            "GREEN",
            "ENERGY",
            "SAVER",
            # Appliance categories
            "AC",
            "AIR",
            "CONDITIONER",
            "REFRIGERATOR",
            "FRIDGE",
            "FREEZER",
            "WASHING",
            "MACHINE",
            "WASHER",
            "SPINNER",
            "DRYER",
            "LED",
            "TV",
            "TELEVISION",
            "MICROWAVE",
            "OVEN",
            "DISPENSER",
            "COOLER",
            "HEATER",
            "GEYSER",
            "FAN",
        }

        cand_leading_brands = []
        for w in cand_words:
            # Skip numbers, units, measurements (e.g. 1.5, 10KG, 55")
            if re.match(r"^\d+(\.\d+)?(KG|TON|INCH|LTR|L)?$", w) or any(c.isdigit() for c in w):
                continue
            # Skip non-brand descriptive words
            if w in NON_BRAND_TOKENS:
                continue
            # Alpha token >= 2 chars that is not a generic descriptor is a brand token
            if w.isalpha():
                cand_leading_brands.append(w)
                if len(cand_leading_brands) >= 2:
                    break

        cand_brand_1 = cand_leading_brands[0] if cand_leading_brands else ""
        cand_brand_2 = (
            " ".join(cand_leading_brands[:2]) if len(cand_leading_brands) >= 2 else cand_brand_1
        )

        # Check if detected brand matches target brand
        is_leading_target = (
            cand_brand_1 == b_target
            or cand_brand_2 == b_target
            or (
                len(cand_brand_1) >= 4
                and SequenceMatcher(None, cand_brand_1, b_target).ratio() >= 0.85
            )
            or (
                len(cand_brand_2) >= 4
                and SequenceMatcher(None, cand_brand_2, b_target).ratio() >= 0.85
            )
        )

        if not has_target_brand and not is_leading_target and cand_brand_1:
            # Candidate title has a foreign brand (e.g. ROYAL, PIERRE, HAIER)
            # Only allow if cand_brand_1 is a model prefix starting with target initial (e.g. DWT, DW for Dawlance)
            is_target_prefix = cand_brand_1.startswith(target_init) and (
                (
                    target_slots.anchor
                    and cand_brand_1.startswith(target_slots.anchor.split("-")[0].upper())
                )
                or bool(re.match(rf"^{re.escape(target_init)}[A-Za-z]{{1,3}}$", cand_brand_1))
            )
            if not is_target_prefix:
                # Distinguish between 2-4 letter SKU prefixes attached/spaced to digits (e.g. HWM 120, RWM-1016) and standalone brand names
                if re.search(rf"\b{re.escape(cand_brand_1)}[-_ ]?\d+", candidate_title):
                    return MatchDecision(
                        is_match=False,
                        reason=f"Brand initial collision: target is {brand} vs candidate prefix '{cand_brand_1}'",
                        target_slots=target_slots,
                        candidate_slots=cand_slots,
                    )
                detected_other_brand = (
                    cand_brand_2 if len(cand_leading_brands) >= 2 else cand_brand_1
                )
                return MatchDecision(
                    is_match=False,
                    reason=f"Brand collision: target is {brand} vs candidate mentions {detected_other_brand}",
                    target_slots=target_slots,
                    candidate_slots=cand_slots,
                )

        # 0c. Dynamic Brand-Initial Prefix Collision (e.g. RWM-1016 vs DWT-1016, HWM vs DWT)
        # Even if brand name is omitted, check candidate's SKU prefix initial against target
        check_anchor_or_title = f"{cand_slots.anchor} {candidate_title}".strip()
        m_pfx = re.search(r"\b([A-Za-z]{2,4})[-_ ]?\d+", check_anchor_or_title)
        if m_pfx:
            pfx = m_pfx.group(1).upper()
            if pfx not in NON_BRAND_TOKENS and pfx[0] != target_init and not has_target_brand:
                return MatchDecision(
                    is_match=False,
                    reason=f"Brand initial collision: target is {brand} vs candidate prefix '{pfx}'",
                    target_slots=target_slots,
                    candidate_slots=cand_slots,
                )

    # 0d. Zero-Tolerance Multi-Unit Bundle / Combo Guard (TASK-12 & AUD-HIGH-06)
    raw_target_str = (
        target if isinstance(target, str) else f"{target_slots.anchor} {target_slots.series}"
    )
    if _has_bundle_collision(raw_target_str, candidate_title):
        return MatchDecision(
            is_match=False,
            reason="Bundle/Combo collision: candidate is a multi-unit bundle/combo listing",
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # 0e. Zero-Tolerance Macro-Appliance Category & AC Mounting Form-Factor Guard (AUD-CRIT-05)
    if isinstance(target, str):
        t_family = _detect_appliance_family(target)
        c_family = _detect_appliance_family(candidate_title)
        if t_family and c_family and t_family != c_family:
            # Allow Convertible Freezer/Refrigerator overlap only when explicitly marked convertible
            is_convertible = bool(
                {t_family, c_family} == {"REFRIGERATOR", "DEEP_FREEZER"}
                and re.search(r"\bCONVERTIBLE\b", f"{target} {candidate_title}", re.IGNORECASE)
            )
            if not is_convertible:
                return MatchDecision(
                    is_match=False,
                    reason=f"Appliance category collision: target is {t_family} vs candidate {c_family}",
                    target_slots=target_slots,
                    candidate_slots=cand_slots,
                )

        if t_family in (None, "AIR_CONDITIONER") and c_family in (None, "AIR_CONDITIONER"):
            t_ac_ff = _detect_ac_form_factor(target)
            c_ac_ff = _detect_ac_form_factor(candidate_title)
            if t_ac_ff and c_ac_ff and t_ac_ff != c_ac_ff:
                return MatchDecision(
                    is_match=False,
                    reason=f"AC mounting form-factor collision: target is {t_ac_ff} vs candidate {c_ac_ff}",
                    target_slots=target_slots,
                    candidate_slots=cand_slots,
                )

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

    # 1b. Zero-Tolerance Hardware Finish / Door Guard (GD vs INOX, plus slash-coded /WB Wood Brown vs GD/INOX)
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
    if (
        target_slots.guarded_facets.color_raw == "WB"
        and not target_slots.guarded_facets.door_finish
        and cand_slots.guarded_facets.door_finish in {"GD", "INOX"}
        and cand_slots.guarded_facets.color_family != target_slots.guarded_facets.color_family
    ) or (
        cand_slots.guarded_facets.color_raw == "WB"
        and not cand_slots.guarded_facets.door_finish
        and target_slots.guarded_facets.door_finish in {"GD", "INOX"}
        and target_slots.guarded_facets.color_family != cand_slots.guarded_facets.color_family
    ):
        return MatchDecision(
            is_match=False,
            reason="Hardware finish collision: slash-coded Wood Brown (/WB) is incompatible with Glass/Inox Door",
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # Track deferred base-model modifier omissions (evaluated ONLY after Anchor, Series, Extra-Cap, Capacity, and Color guards pass!)
    omitted_fallbacks: list[tuple[str, str, str]] = []

    # Category 2 Rule for Hardware Finish (GD / INOX):
    # 1. Target specifies finish (GD or INOX), but candidate omitted it:
    # "mila toh lelon leken nahi mila toh fallback"
    if target_slots.guarded_facets.door_finish and not cand_slots.guarded_facets.door_finish:
        missing_finish = target_slots.guarded_facets.door_finish
        # For unique 5-digit catalog models (e.g. 91998 deep freezers), Glass Door is inherent to the SKU
        # and frequently omitted by marketplace sellers in listing titles.
        is_5digit_stem = bool(target_slots.anchor and re.search(r"\d{5,}", target_slots.anchor))
        if missing_finish == "GD" and is_5digit_stem:
            pass  # Accept as direct match
        else:
            omitted_fallbacks.append(
                (
                    missing_finish,
                    f"Hardware finish omitted ({missing_finish} mismatch): Target specifies {missing_finish} but candidate does not",
                    "target",
                )
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

    # 1b2b. Zero-Tolerance Washer Loading Type Guard (Front Load vs Top Load)
    if (
        target_slots.guarded_facets.load_type
        and cand_slots.guarded_facets.load_type
        and target_slots.guarded_facets.load_type != cand_slots.guarded_facets.load_type
    ):
        return MatchDecision(
            is_match=False,
            reason=(
                f"Loading type collision: target is {target_slots.guarded_facets.load_type} "
                f"vs candidate {cand_slots.guarded_facets.load_type}"
            ),
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # 1b2c. Zero-Tolerance Washer Tub Architecture Guard (Twin Tub vs Single Tub)
    if (
        target_slots.guarded_facets.tub_type
        and cand_slots.guarded_facets.tub_type
        and target_slots.guarded_facets.tub_type != cand_slots.guarded_facets.tub_type
    ):
        return MatchDecision(
            is_match=False,
            reason=(
                f"Tub type collision: target is {target_slots.guarded_facets.tub_type} "
                f"vs candidate {cand_slots.guarded_facets.tub_type}"
            ),
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # 1b2d. Zero-Tolerance Washer Automation Guard (Fully Automatic vs Semi-Automatic)
    if (
        target_slots.guarded_facets.automation_type
        and cand_slots.guarded_facets.automation_type
        and target_slots.guarded_facets.automation_type != cand_slots.guarded_facets.automation_type
    ):
        return MatchDecision(
            is_match=False,
            reason=(
                f"Automation type collision: target is {target_slots.guarded_facets.automation_type} "
                f"vs candidate {cand_slots.guarded_facets.automation_type}"
            ),
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # 1b2d_cross. Cross-Facet Washer Architecture Mutual Exclusion Guard (AUD-HIGH-05)
    t_load = target_slots.guarded_facets.load_type
    c_load = cand_slots.guarded_facets.load_type
    t_tub = target_slots.guarded_facets.tub_type
    c_tub = cand_slots.guarded_facets.tub_type
    t_auto = target_slots.guarded_facets.automation_type
    c_auto = cand_slots.guarded_facets.automation_type
    # If one side inferred 'FL' solely from a 2-letter 'FL' token (not spelled-out 'Front Load')
    # and the other side also carries that same 'FL' SKU suffix token alongside Twin/Semi, do not misclassify as Front-Load collision.
    if (
        t_load == "FL"
        and isinstance(target, str)
        and not re.search(r"\bFRONT\s*LOAD(?:ING)?\b", target, re.IGNORECASE)
        and re.search(r"\bFL\b", candidate_title, re.IGNORECASE)
    ):
        t_load = None
    if (
        c_load == "FL"
        and not re.search(r"\bFRONT\s*LOAD(?:ING)?\b", candidate_title, re.IGNORECASE)
        and isinstance(target, str)
        and re.search(r"\bFL\b", target, re.IGNORECASE)
    ):
        c_load = None
    if (
        (t_load == "FL" and (c_tub in {"TWIN", "SINGLE"} or c_auto == "SEMI"))
        or (c_load == "FL" and (t_tub in {"TWIN", "SINGLE"} or t_auto == "SEMI"))
        or (t_load == "TL" and c_tub == "TWIN")
        or (c_load == "TL" and t_tub == "TWIN")
        or (t_auto == "AUTO" and c_tub in {"TWIN", "SINGLE"})
        or (c_auto == "AUTO" and t_tub in {"TWIN", "SINGLE"})
    ):
        return MatchDecision(
            is_match=False,
            reason=(
                f"Washer architecture collision: target ({t_load or t_tub or t_auto}) "
                f"is incompatible with candidate ({c_load or c_tub or c_auto})"
            ),
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    # 1b2e. Zero-Tolerance Refrigerator Defrost System Guard (Direct Cool vs No Frost)
    if (
        target_slots.guarded_facets.defrost_type
        and cand_slots.guarded_facets.defrost_type
        and target_slots.guarded_facets.defrost_type != cand_slots.guarded_facets.defrost_type
    ):
        return MatchDecision(
            is_match=False,
            reason=(
                f"Defrost type collision: target is {target_slots.guarded_facets.defrost_type} "
                f"vs candidate {cand_slots.guarded_facets.defrost_type}"
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

    # Inverter is a descriptor, not an identity: once the anchor model matches, a listing that
    # merely omits the word "Inverter" is the same product. Only an explicit opposite
    # (Inverter vs Non-Inverter, guarded above) is a collision.

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

    # 2. Minimum Identity & Anchor Model Check (AUD-CRIT-04 & AUD-CRIT-05)
    if not target_slots.anchor and not target_slots.series:
        return MatchDecision(
            is_match=False,
            is_base_match=False,
            reason="Insufficient model identity: target lacks both SKU anchor and distinct model series",
            target_slots=target_slots,
            candidate_slots=cand_slots,
        )

    extended_edition_designation: str | None = None
    market_inherent_specs: list[str] = []

    if target_slots.anchor:
        norm_t = re.sub(r"[^A-Z0-9]", "", target_slots.anchor.upper())
        norm_cand_title = re.sub(r"[^A-Z0-9]", "", candidate_title.upper())

        # Explicit Leading Alphabetic SKU Prefix Collision Guard (e.g. HRF-240 vs HWM-240, DW-200 vs DMB-200, SA-240 vs SD-240)
        if cand_slots.anchor:
            m_lead_pfx_t = re.match(r"^([A-Za-z]{2,4})(?:[-_]|\d)", target_slots.anchor)
            m_lead_pfx_c = re.match(r"^([A-Za-z]{2,4})(?:[-_]|\d)", cand_slots.anchor)
            if m_lead_pfx_t and m_lead_pfx_c:
                pfx_t_val = m_lead_pfx_t.group(1).upper()
                pfx_c_val = m_lead_pfx_c.group(1).upper()
                if pfx_t_val != pfx_c_val:
                    t_check_nums = re.findall(r"\d{2,}", norm_t)
                    c_check_nums = re.findall(
                        r"^\d{2,}|\d{2,}", re.sub(r"[^A-Z0-9]", "", cand_slots.anchor.upper())
                    )
                    # Only permit sub-prefix abbreviation (e.g. HW vs HWM) when BOTH share an identical >= 2-part compound model with >= 3-digit sub-stem
                    is_compound_subprefix = (
                        len(t_check_nums) >= 2
                        and t_check_nums == c_check_nums
                        and any(len(n) >= 3 for n in t_check_nums[1:])
                        and (pfx_t_val.startswith(pfx_c_val) or pfx_c_val.startswith(pfx_t_val))
                    )
                    if not is_compound_subprefix:
                        return MatchDecision(
                            is_match=False,
                            is_base_match=False,
                            reason=f"SKU prefix collision: target prefix '{pfx_t_val}' vs candidate prefix '{pfx_c_val}'",
                            target_slots=target_slots,
                            candidate_slots=cand_slots,
                        )

        matched_anchor = False
        _, stem_t_core = _strip_leading_sku_prefix(norm_t)
        if cand_slots.anchor:
            norm_c = re.sub(r"[^A-Z0-9]", "", cand_slots.anchor.upper())
            _, stem_c_core = _strip_leading_sku_prefix(norm_c)
            matched_anchor, extended_edition_designation = _evaluate_anchor_compatibility(
                norm_t, norm_c, target_slots, cand_slots, candidate_title
            )
            if not matched_anchor:
                t_nums = re.findall(r"\d{2,}", stem_t_core)
                c_nums = re.findall(r"\d{2,}", stem_c_core)
                # Pure-numeric stem fallback ONLY when neither stem carries conflicting model letters
                if stem_t_core.isdigit() and stem_c_core.isdigit() and t_nums and c_nums:
                    if len(t_nums) > 1 and len(c_nums) > 1:
                        matched_anchor = set(t_nums) == set(c_nums)
                    elif len(t_nums) == 1 and len(c_nums) == 1:
                        matched_anchor = t_nums[0] == c_nums[0]
                    elif len(t_nums) == 1 and t_nums[0] in c_nums:
                        matched_anchor = _is_valid_single_to_multi_num_match(
                            target_slots, cand_slots, t_nums, c_nums
                        )
        else:
            # Candidate had no extracted anchor: check strict token-bounded stem presence in candidate title
            m_title_exact = re.search(
                rf"(?<![A-Z0-9]){re.escape(stem_t_core)}(EX)?(?![A-Z0-9])",
                candidate_title.upper(),
            )
            if m_title_exact:
                matched_anchor = True
                if m_title_exact.group(1):
                    extended_edition_designation = f"{stem_t_core}EX"
            elif stem_t_core.isdigit():
                t_nums = re.findall(r"\d{3,}", stem_t_core)
                if len(t_nums) == 1 and re.search(
                    rf"(?<!\d){re.escape(t_nums[0])}(?!\d)", candidate_title
                ):
                    matched_anchor = True

        # Dynamic Brand-Initial Prefix Synthesis check (only when candidate lacks conflicting alphanumeric SKU suffix)
        if (
            not matched_anchor
            and not cand_slots.anchor
            and _matches_brand_initial_synthesis(norm_t, cand_slots.anchor, norm_cand_title, brand)
        ):
            matched_anchor = True

        # Variant tag collision check on prefix-stripped core stems (e.g. 50MB vs 50DB, 13LF vs 13HFP)
        is_shared_ac_base_stem = bool(
            target_slots.base_stem
            and cand_slots.base_stem
            and target_slots.base_stem == cand_slots.base_stem
            and target_slots.sub_model_tag != ""
        )
        if cand_slots.anchor:
            norm_c = re.sub(r"[^A-Z0-9]", "", cand_slots.anchor.upper())
            _, stem_c_core = _strip_leading_sku_prefix(norm_c)
            if not is_shared_ac_base_stem and _has_variant_tag_collision(stem_t_core, stem_c_core):
                return MatchDecision(
                    is_match=False,
                    reason=f"Variant tag collision: {target_slots.anchor} vs {cand_slots.anchor}",
                    target_slots=target_slots,
                    candidate_slots=cand_slots,
                )

            is_gen_collision, gen_detail = _has_generation_series_collision(
                stem_t_core, stem_c_core
            )
            if is_gen_collision:
                return MatchDecision(
                    is_match=False,
                    reason=f"Generation series collision: {gen_detail}",
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

        # Single-letter variant suffix guard (5-Case Referee)
        raw_t_check = (
            target
            if isinstance(target, str)
            else (
                f"{target_slots.anchor} "
                f"{target_slots.guarded_facets.color_raw or ''} "
                f"{' '.join(target_slots.residuals)}"
            )
        )
        effective_t_var, t_mod_label = _resolve_effective_single_letter_variant(
            raw_t_check, target_slots, brand=brand
        )
        effective_c_var, _ = _resolve_effective_single_letter_variant(
            candidate_title, cand_slots, brand=brand
        )

        if effective_t_var and effective_c_var and effective_t_var != effective_c_var:
            return MatchDecision(
                is_match=False,
                reason=f"Single-letter variant suffix collision: {effective_t_var} vs {effective_c_var}",
                target_slots=target_slots,
                candidate_slots=cand_slots,
            )
        t_var_satisfied_by_color = bool(
            effective_t_var
            and effective_t_var in COLOR_SUFFIX_MAP
            and cand_slots.guarded_facets.color_family == COLOR_SUFFIX_MAP[effective_t_var]
        )
        c_var_satisfied_by_color = bool(
            effective_c_var
            and effective_c_var in COLOR_SUFFIX_MAP
            and target_slots.guarded_facets.color_family == COLOR_SUFFIX_MAP[effective_c_var]
        )
        if effective_t_var and not effective_c_var and not t_var_satisfied_by_color:
            mod_name = t_mod_label or f"Variant {effective_t_var}"
            omitted_fallbacks.append(
                (
                    mod_name,
                    f"Single-letter variant '{effective_t_var}' omitted by candidate; fallback to base model",
                    "target",
                )
            )
        if not effective_t_var and effective_c_var and not c_var_satisfied_by_color:
            omitted_fallbacks.append(
                (
                    f"Variant {effective_c_var}",
                    f"Candidate has variant suffix '{effective_c_var}' omitted in target; fallback with cross-check",
                    "market",
                )
            )

    # 2. Dynamic Series and Sub-series Check (Pure Token-Based Set Logic, Zero Hardcoding)
    if target_slots.series:
        # Check if target series has slash-separated alternatives (e.g. "SPRINTER / POWERCON")
        if "/" in target_slots.series:
            alternatives = [s.strip().upper() for s in target_slots.series.split("/") if s.strip()]
        else:
            alternatives = [target_slots.series.upper()]

        cand_clean = clean_marketplace_noise(_canonicalize_plus_series(candidate_title))
        cand_clean = re.sub(r"\([^)]*\)", " ", cand_clean)
        cand_series_words = _tokenize_series_words(cand_clean)
        if cand_slots.series:
            cand_series_words |= _tokenize_series_words(cand_slots.series)

        target_text = (
            target if isinstance(target, str) else f"{target_slots.series} {target_slots.anchor}"
        )
        is_dawlance_brand = _is_dawlance_context(target_text, brand=brand) or _is_dawlance_context(
            candidate_title, brand=brand
        )

        matched_alt = None
        for alt in alternatives:
            alt_words = _tokenize_series_words(alt)
            diff = alt_words - cand_series_words
            if not diff:
                matched_alt = alt
                break
            if (
                is_dawlance_brand
                and diff == {"X"}
                and (alt_words - {"X"})
                and (alt_words - {"X"}).issubset(cand_series_words)
            ):
                matched_alt = alt
                break

        # Soft Feature & Styling Optionality Rule:
        # If target has a unique numeric stem of >= 4 digits (e.g. 9173, 91999) or anchor is matched,
        # AND candidate did not specify an opposing/conflicting series (cand_slots.series is empty),
        # AND candidate anchor does not contain extra unmatched variant letters (e.g. LFACCE),
        # allow match where seller omitted the soft styling tag (Chrome, FH, LVS).
        if not matched_alt:
            is_distinct_model = bool(
                target_slots.anchor
                and (
                    re.search(r"\d{3,}", target_slots.anchor)
                    or re.search(r"[A-Za-z]+[-_]?\d+", target_slots.anchor)
                    or (
                        cand_slots.anchor
                        and target_slots.anchor.upper() in cand_slots.anchor.upper()
                    )
                )
            )
            target_all_text = f"{target_slots.anchor} {target_slots.series} {target_slots.guarded_facets.tub_series or ''} {' '.join(target_slots.residuals)} {' '.join(target_slots.guarded_facets.capabilities)}".upper()
            target_all_words = _tokenize_series_words(target_all_text)
            # Check if candidate has an opposing, conflicting series
            cand_ser_clean = cand_slots.series.strip().upper()
            cand_ser_words = _tokenize_series_words(cand_ser_clean) if cand_ser_clean else set()
            has_conflicting_series = bool(
                cand_ser_clean
                and cand_ser_clean not in {"REGULAR", "STANDARD", "NORMAL"}
                and not any(cand_ser_clean in alt for alt in alternatives)
                and not any(alt in cand_ser_clean for alt in alternatives)
                and not (cand_ser_words and cand_ser_words.issubset(target_all_words))
            )
            target_all_chars = re.sub(r"[^A-Za-z0-9]", "", target_all_text)
            cand_anchor_norm = (
                re.sub(r"[^A-Za-z0-9]", "", cand_slots.anchor.upper()) if cand_slots.anchor else ""
            )
            t_stem_match = re.search(r"\d{2,}", target_slots.anchor)
            stem_val = t_stem_match.group(0) if t_stem_match else ""
            extra_cand_letters = cand_anchor_norm.replace(stem_val, "")
            if brand:
                b_init = brand[0].upper()
                extra_cand_letters = re.sub(
                    rf"^{re.escape(b_init)}[A-Z]{{0,3}}", "", extra_cand_letters
                )
            extra_ok = not extra_cand_letters or all(
                c in target_all_chars for c in extra_cand_letters
            )

            if is_distinct_model and not has_conflicting_series and extra_ok:
                matched_alt = alternatives[0]
            else:
                return MatchDecision(
                    is_match=False,
                    reason=f"Missing required series tokens for any alternative in '{target_slots.series}'",
                    target_slots=target_slots,
                    candidate_slots=cand_slots,
                )

        target_sub_tokens = _tokenize_series_words(matched_alt) & GENUINE_SUB_SERIES_TOKENS
        cand_sub_tokens = _tokenize_series_words(cand_slots.series) & GENUINE_SUB_SERIES_TOKENS
        extra_sub = cand_sub_tokens - target_sub_tokens
        if is_dawlance_brand:
            extra_sub.discard("X")
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
    target_series_toks = _tokenize_series_words(target_slots.series)

    # Check if target title specifies optional/allowed feature tags like [OPT:T3,QC0] or [ALLOW:T3]
    allowed_feature_tags = set(target_slots.guarded_facets.allowed_feature_tags)
    if isinstance(target, str):
        _, parsed_opt = extract_and_strip_opt_tags(target)
        allowed_feature_tags.update(parsed_opt)

    # Inherent AC compressor specification check:
    # When target has a specific alphanumeric AC SKU anchor (e.g. HSU-24HFAB, 20HFT, 14HFT) and omits 'T3',
    # while candidate matches that SKU and mentions 'T3' as descriptive specification prose (NOT a non-extended
    # '<SKU>-T3' upgraded SKU suffix like 'GS-18AITH24S-T3'), treat 'T3' as a market-documented inherent spec.
    has_inherent_prose_t3 = False
    if (
        "T3" in (cand_caps - target_caps)
        and "T3" not in allowed_feature_tags
        and target_slots.anchor
    ):
        _, t_core_for_t3 = _strip_leading_sku_prefix(
            re.sub(r"[^A-Z0-9]", "", target_slots.anchor.upper())
        )
        is_alnum_ac_sku = bool(
            re.match(r"^\d{2}[A-Z]{2,}", t_core_for_t3)
            and (
                (target_slots.guarded_facets.capacity or "").endswith("T")
                or (cand_slots.guarded_facets.capacity or "").endswith("T")
                or _detect_appliance_family(candidate_title) == "AIR_CONDITIONER"
            )
        )
        if is_alnum_ac_sku:
            cand_anc_raw = cand_slots.anchor.strip()
            has_explicit_sku_t3_suffix = bool(
                cand_anc_raw
                and extended_edition_designation is None
                and re.search(
                    rf"\b{re.escape(cand_anc_raw)}[-_]T3\b",
                    candidate_title,
                    re.IGNORECASE,
                )
            )
            if not has_explicit_sku_t3_suffix:
                has_inherent_prose_t3 = True
                market_inherent_specs.append("T3")

    # Collision 1: Candidate has extra hardware capabilities/modifiers that target lacks -> Hard mismatch
    # (Cannot reprice baseline target against upgraded listing with extra physical components)
    extra_cand_caps = {
        c
        for c in (cand_caps - target_caps)
        if not (target_slots.anchor and c in target_slots.anchor.upper())
        and c not in target_series_toks
        and c not in {"WIFI", "IOT", "SMART"}
        and c not in allowed_feature_tags
        and not (c == "T3" and has_inherent_prose_t3)
    }
    if extra_cand_caps:
        extra_str = ", ".join(sorted(extra_cand_caps))
        return MatchDecision(
            is_match=False,
            reason=f"Hardware capability mismatch ({extra_str} mismatch): Candidate has extra capability {extra_str} not present in target",
            target_slots=target_slots,
            candidate_slots=cand_slots,
            is_base_match=False,
        )

    # AUD-MED-03: If target is a pure numeric base stem (e.g. HRF-458, DW-7650) without WIFI/IOT and candidate adds IOT/WIFI,
    # classify as market-added cross-check fallback rather than a silent exact match (while preserving inherent Wi-Fi prose on full alphanumeric AC SKUs like HSU-19HFS).
    extra_conn_caps = {
        c
        for c in (cand_caps - target_caps)
        if c in {"WIFI", "IOT", "SMART"} and c not in allowed_feature_tags
    }
    if extra_conn_caps:
        stripped_t_anc = re.sub(r"^[A-Z]{2,4}[-_]?", "", (target_slots.anchor or "").upper())
        if not stripped_t_anc or stripped_t_anc.isdigit():
            conn_str = ", ".join(sorted(extra_conn_caps))
            omitted_fallbacks.append(
                (
                    conn_str,
                    f"Candidate adds connectivity capability ({conn_str}) omitted in target; fallback with cross-check",
                    "market",
                )
            )

    # Fallback 2: Target specifies Category 2 modifiers that candidate omitted -> Valid base-model fallback
    missing_target_caps = {
        c
        for c in (target_caps - cand_caps)
        if not (cand_slots.anchor and c in cand_slots.anchor.upper())
        and not re.search(rf"\b{re.escape(c)}\b", candidate_title, re.IGNORECASE)
        and not (cand_slots.series and c in cand_slots.series.upper())
        and c not in allowed_feature_tags
        and not (
            c == "SMART"
            and cand_slots.anchor
            and not re.sub(r"^[A-Z]{2,4}[-_]?", "", cand_slots.anchor.upper()).isdigit()
        )
    }
    if missing_target_caps:
        missing_str = ", ".join(sorted(missing_target_caps))
        omitted_fallbacks.append(
            (
                missing_str,
                f"Hardware capability omitted ({missing_str} mismatch): Target specifies {missing_str} but candidate does not",
                "target",
            )
        )

    # 3b. Capacity / Screen Size Guard (Unit-Preserving Normalization - AUD-HIGH-03)
    if target_slots.guarded_facets.capacity and cand_slots.guarded_facets.capacity:

        def _norm_cap(c: str) -> str:
            val_str = re.sub(r"[^0-9.]", "", c)
            unit_str = re.sub(r"[0-9.\s\-_]", "", c).upper()
            try:
                return f"{float(val_str):g}_{unit_str}"
            except (ValueError, TypeError):
                return c.strip().upper()

        norm_cap_t = _norm_cap(target_slots.guarded_facets.capacity)
        norm_cap_c = _norm_cap(cand_slots.guarded_facets.capacity)
        # Allow 1T <-> 1.25T rounded prose tonnage equivalence ONLY when BOTH sides share an identical
        # matched 13xxx/14xxx BTU AC SKU anchor (e.g. 14HFT 1.25 Ton <-> HSU-14HFT / HSU-14HFTEX 1.0 Ton).
        is_identical_14k_btu_sku = False
        if (
            {norm_cap_t, norm_cap_c} == {"1_T", "1.25_T"}
            and target_slots.anchor
            and cand_slots.anchor
        ):
            _, st_t = _strip_leading_sku_prefix(
                re.sub(r"[^A-Z0-9]", "", target_slots.anchor.upper())
            )
            _, st_c = _strip_leading_sku_prefix(re.sub(r"[^A-Z0-9]", "", cand_slots.anchor.upper()))
            m_btu_t = re.match(r"^(1[34])[A-Z]{2,}", st_t)
            m_btu_c = re.match(r"^(1[34])[A-Z]{2,}", st_c)
            if m_btu_t and m_btu_c and m_btu_t.group(1) == m_btu_c.group(1):
                is_identical_14k_btu_sku = True

        if norm_cap_t != norm_cap_c and not is_identical_14k_btu_sku:
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

    # 3d. AC Sub-Edition Base & Sibling Classification (after all Guarded Facets pass!)
    ac_base_model_notice: str | None = None
    if (
        target_slots.base_stem
        and cand_slots.base_stem
        and target_slots.base_stem == cand_slots.base_stem
        and target_slots.sub_model_tag != cand_slots.sub_model_tag
        and target_slots.sub_model_tag != ""
    ):
        t_label = target_slots.anchor or f"{target_slots.base_stem}{target_slots.sub_model_tag}"
        c_label = cand_slots.anchor or f"{cand_slots.base_stem}{cand_slots.sub_model_tag}"
        extra_target_omitted = [m for m, _, src in omitted_fallbacks if src == "target"]
        if cand_slots.sub_model_tag == "":
            if extra_target_omitted:
                extra_join = ", ".join(extra_target_omitted)
                ac_base_model_notice = (
                    f"⚠️ [FALLBACK MODEL: Target specified '{t_label}' ({extra_join}), "
                    f"but market listing is base model '{c_label}' omitting '{extra_join}']"
                )
            else:
                ac_base_model_notice = (
                    f"⚠️ [FALLBACK MODEL: Target specified '{t_label}', "
                    f"but market listing is base model '{c_label}']"
                )
            omitted_fallbacks.insert(
                0,
                (
                    target_slots.sub_model_tag,
                    f"Base model fallback: target '{t_label}' matched base model '{c_label}'",
                    "target",
                ),
            )
        else:
            if extra_target_omitted:
                return MatchDecision(
                    is_match=False,
                    is_base_match=False,
                    reason=omitted_fallbacks[0][1],
                    target_slots=target_slots,
                    candidate_slots=cand_slots,
                    match_tier=None,
                )
            sibling_notice = (
                f"⚠️ [SIBLING SUB-MODEL FALLBACK: Target specified '{t_label}', "
                f"but market listing is sibling edition '{c_label}' "
                f"sharing base '{target_slots.base_stem}']"
            )
            return MatchDecision(
                is_match=False,
                is_base_match=False,
                reason=(
                    f"Sibling sub-model tag collision fallback: target '{t_label}' vs "
                    f"sibling edition '{c_label}' sharing base '{target_slots.base_stem}'"
                ),
                target_slots=target_slots,
                candidate_slots=cand_slots,
                missing_modifier=f"{target_slots.sub_model_tag}->{cand_slots.sub_model_tag}",
                modifier_source="market",
                match_tier=3,
                compatibility_notice=sibling_notice,
            )

    # 4. Evaluate Deferred Base-Model Modifier Omissions (ONLY after Anchor, Series, Extra-Cap, Capacity & Color all pass!)
    if omitted_fallbacks:
        if extended_edition_designation:
            omitted_fallbacks.insert(
                0,
                (
                    f"Extended Edition ({extended_edition_designation})",
                    f"Accepted extended model designation '{extended_edition_designation}'",
                    "market",
                ),
            )
        primary_mod, primary_reason, primary_source = omitted_fallbacks[0]
        final_mod = primary_mod
        if len(omitted_fallbacks) > 1 and len({src for _, _, src in omitted_fallbacks}) == 1:
            all_mods: list[str] = []
            for mod_entry, _, _ in omitted_fallbacks:
                for sub_m in (p.strip() for p in mod_entry.split(",") if p.strip()):
                    if sub_m not in all_mods:
                        all_mods.append(sub_m)
            # Collapse redundant Direct-Drive Motor ('DDM') acronym when 'INVERTER' is already listed
            if "INVERTER" in all_mods and "DDM" in all_mods:
                all_mods.remove("DDM")
            final_mod = ", ".join(all_mods)

        if ac_base_model_notice is not None:
            tier2_notice = ac_base_model_notice
        elif primary_source == "market":
            tier2_notice = (
                f"⚠️ [CROSS-CHECK NOTICE: Market listing includes '{final_mod}' "
                "not specified in target catalog]"
            )
        else:
            tier2_notice = (
                f"⚠️ [FALLBACK MODEL: Target specified '{final_mod}', "
                f"but market listing omitted '{final_mod}']"
            )
        return MatchDecision(
            is_match=False,
            reason=primary_reason,
            target_slots=target_slots,
            candidate_slots=cand_slots,
            is_base_match=True,
            missing_modifier=final_mod,
            modifier_source=primary_source,
            match_tier=2,
            compatibility_notice=tier2_notice,
        )

    # All checks passed cleanly; preserve explicit compatibility notice when an extended model
    # designation (e.g. 20HFT -> HSU-20HFTEX) or market-documented inherent spec (Rule C) was accepted.
    compat_notices: list[str] = []
    if extended_edition_designation:
        compat_notices.append(f"Extended Edition ({extended_edition_designation})")
    for spec_tok in market_inherent_specs:
        if spec_tok not in compat_notices:
            compat_notices.append(spec_tok)
    compat_mod_str = ", ".join(compat_notices) if compat_notices else None

    tier1_notice: str | None = None
    if extended_edition_designation:
        tier1_notice = (
            f"[COMPATIBILITY NOTICE: Accepted legitimate extended model designation "
            f"'{extended_edition_designation}' — verify edition/color alignment]"
        )
    elif has_inherent_prose_t3:
        tier1_notice = (
            "ℹ️ [OPTIONAL SPECIFICATION: Target did not specify 'T3', "
            "but market listing specifies 'T3']"
        )

    matched_id = target_slots.anchor or target_slots.series or "Target"
    reason_msg = (
        f"Accepted extended model '{extended_edition_designation}' for target '{matched_id}'"
        if extended_edition_designation
        else f"Accepted: {matched_id} matched with zero guarded facet collisions"
    )
    return MatchDecision(
        is_match=True,
        reason=reason_msg,
        target_slots=target_slots,
        candidate_slots=cand_slots,
        missing_modifier=compat_mod_str,
        modifier_source="market" if compat_mod_str else "target",
        match_tier=1,
        compatibility_notice=tier1_notice,
    )
