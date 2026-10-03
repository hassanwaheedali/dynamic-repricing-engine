import re
from dataclasses import dataclass, field


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
    "GT",  # Glass Top (e.g. Washing Machine Glass Top)
}


# 9 Normalized Color Families (ADR-002)
COLOR_FAMILIES: dict[str, list[str]] = {
    "White": ["MILKY WHITE", "PEARL WHITE", "WHITE", "MILKY", "IVORY"],
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
    title_search = title
    if anchor:
        title_search = re.sub(rf"\b{re.escape(anchor)}\b", " ", title, flags=re.IGNORECASE)

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

    # Detect parenthesized, hyphenated, or isolated color codes: (G), -G, (DG), -DG, (S-G), (W), (B), (S)
    # e.g. HSU-19HFS (G), HSU-19HFS-G, HSU-19HFS(G), HSU-19HFS (S-G), HSU-19HFS (DG)
    m_code = re.search(r"[\(\s\-_/](S[-_]?G|S[-_]?W|DG|[WBSGDRP])(?=[\(\)\s\-_/]|$)", title_search, re.IGNORECASE)
    if m_code:
        code = m_code.group(1).upper()
        fam = COLOR_SUFFIX_MAP.get(code)
        if fam:
            return fam, code

    # Fallback to trailing single-letter color code on model anchor (e.g. 12AITH21W -> W -> White)
    if anchor:
        m_suf = re.search(r"\d+[A-Za-z]+?\d+(S[-_]?G|S[-_]?W|DG|[WBSGDRP])$", anchor, re.IGNORECASE)
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
    r"|\b\d+/\d+\s*(?:\"|(?:inch|mm)\b)"
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
    r"\b(?:AWM|AUTO\s+W/M|FRONT\s+LOAD(?:\s+W/M)?|W/M|WASHING\s+MACHINE|AIR\s+CONDITIONER|M/OVEN|M/O|MWO|D/F|R/F|W/D|SPLIT\s+AC|SPLIT|FLOOR(?:\s+STANDING)?|DISHWASHER|SPINNER|DRYER)\b"
    r"|\b(?:AIR\s*CURTAIN|AIR\s*COOLER|AIR\s*FRYER|WATER\s+HEATER|WATER\s+DISPENSER|WATER\s+PURIFIER|INSECT\s+KILLER|JUG\s+KETTLE|HOT\s+PLATE|CHOPPER|BLENDER|IRON|LED|MICROWAVE|OVEN|SANDWI?T?CH\s+MAKER)\b"
    r"|\b(?:MINI\s*BAR|MINIBAR|ROOM\s*FRIDGE|BEDROOM\s*SERIES|REFRIGERATOR|FRIDGE|DEEP\s*FREEZER|CHEST\s*FREEZER|FREEZER)\b"
    r"|\b(?:SINGLE\s*DOOR|DOUBLE\s*DOOR|TRIPLE\s*DOOR|FOUR\s*DOOR|FRENCH\s*DOOR|SIDE\s*BY\s*SIDE|SINGLE\s*TUB|TWIN\s*TUB|TWIN\s*DOOR)\b"
    r"|\b(?:INVERTER|NORMAL|SERIES|DIGITAL|GLASS\s+DOOR|CLEAR\s+LID|OPAQUE(?:\s+LID)?|NO[\s\-]*FROST|CVT|SMART|WIFI|WI-FI|IOT|4K|8K|FHD|UHD|HD|QLED|OLED|GOOGLE\s*TV|ANDROID\s*TV|GAS\+ELECTRIC|BUILT-IN|FIX(?:ED)?\s*SPEED|ENERGY\s*SAVER|ENERGY\s*SAVING|ENERGY\s*SAVE|POWER\s*SAVER|ECO\s*SAVER|EXTENDED\s*DURABILITY|DURABILITY|SIGNATURE|REGULAR(?:\s+SERIES)?|STUCCO(?:\s+PCM)?|PCM)\b"
    r"|\b(?:HEATING|SOLO|GRILL|IN\s+GRILL|BEZEL\s*LESS|FRAMELESS)\b"
    r"|\b\d+(?:\.\d+)?[\s\-_]*(?:(?:TON|ΤΟN|KG|GM|LTR|LITRE|LITRES?|LITERS?|L|SETS|SETS?|FEET|FT|CU\s*FT|CU\.FT|CFT|CU|INCH(?:ES)?|MM|CM)\b|[\"\'])",
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

MERCHANT_TRACKING_CODE_RE = re.compile(
    r"\s*\((?:ISPK|SNS|SKU|ID|NS|UE)[-_]?[A-Za-z0-9]+\)\s*|\b(?:ISPK|SNS|SKU|ID|NS|UE)[-_]?[A-Za-z0-9]+\b",
    re.IGNORECASE,
)

# Generic marketplace noise (seller signatures, promotions, payment terms, HVAC operational phrases)
MARKETPLACE_NOISE_RE = re.compile(
    r"\b(?:ON\s+INSTALLMENT|INSTALLMENT|0%\s*MARKUP|MARKUP|INTEREST|DOWN\s*PAYMENT|EMI|CASH\s+ON\s+DELIVERY|COD)\b"
    r"|\b(?:UPTO\s+\d+\s*MONTHS?|\d+\s*MONTHS?|UPTO|MONTHLY|PER\s+MONTH)\b"
    r"|\b(?:FREE\s+(?:HOME\s+)?DELIVERY|FAST\s+DELIVERY|DELIVERY|SHIPPING|EXPRESS|FREE\s+INSTALLATION)\b"
    r"|\b(?:OFFICIAL\s+WARRANTY|BRAND\s+WARRANTY|COMPANY\s+WARRANTY|WARRANTY\s+CARD|WARRANTY|\d+\s*YEARS?\s+WARRANTY)\b"
    r"|\b(?:SALE|DISCOUNT|DEAL|OFFER|PROMO|PROMOTION|RAMADAN\s+OFFER|EID\s+OFFER|SUPER\s+SALE)\b"
    r"|\b(?:ORIGINAL|AUTHENTIC|GENUINE|BRAND\s+NEW|SEALED\s+PACK|SEALED|BOX\s+PACK|100%\s*ORIG(?:I)?NAL)\b"
    r"|\b(?:SPECIAL\s+GIFT|SURPRISE\s+GIFT|FREE\s+GIFT|GIFT\s+PACK|GIFT|BEST\s+PRICE)\b"
    r"|\b(?:QUANTUM\s+DOT|QUANTUM|TECHNOLOGY)\b"
    r"|\b(?:ELECTROEASE|HOMECART|METRO|HYPERSTAR|ALFAMALL|FAYSAL\s*BANK|QISTBAZAAR|ESBUY|TELEMART|YAYVO)\b"
    r"|\b(?:HEAT\s*(?:&|AND|/)\s*COOL|H\s*&\s*C|COOLING\s*ONLY|COOL\s*ONLY)\b"
    r"|\b(?:INVERTER\s*AC|DC\s*INVERTER|FIX(?:ED)?\s*SPEED|NON[\s\-]*INVERTER)\b"
    r"|\b(?:AAA\+|AA\+|A\+{1,3}|AAA|AA)\b"
    r"|\b(?:FOR\s+[A-Za-z]+\s+ONLY)\b"
    rf"|{MERCHANT_TRACKING_CODE_RE.pattern}",
    re.IGNORECASE,
)


def normalize_technical_slashes(text: str) -> str:
    """Normalize technical compound codes (/DC, /AC, /Z, etc.) and screen units while preserving model boundaries."""
    t = text
    # 24 HD/Z -> 24 HDZ
    t = re.sub(r"\b([A-Za-z0-9]+)/Z\b", r"\1Z", t, flags=re.IGNORECASE)
    # Technical compressor/electrical codes (18HE/DC -> 18HE-DC, 48CE/DC -> 48CE-DC, 24 HE/DC -> 24 HE-DC)
    # Only applies to known technical codes HE/DC, CE/DC, GE/DC, etc. or when preceded by 2-digit capacity
    t = re.sub(r"\b((?:\d{2}\s*)?(?:HE|CE|GE|SE|HBU|HCF|P|C))/(DC|AC)\b", r"\1-\2", t, flags=re.IGNORECASE)
    t = re.sub(r"\bH\s*&\s*C\b", "Heat and Cool", t, flags=re.IGNORECASE)
    t = re.sub(r"\bH/C\b", "Heat and Cool", t, flags=re.IGNORECASE)
    t = re.sub(r"\bW/M\b", "Washing Machine", t, flags=re.IGNORECASE)
    t = re.sub(r"\bA/C\b", "AC", t, flags=re.IGNORECASE)
    t = re.sub(r"\bWI[\s\-]+FI\b", "WIFI", t, flags=re.IGNORECASE)
    return normalize_screen_units(t)


def normalize_screen_units(text: str) -> str:
    """Canonicalise screen-size notation: 32" / 32-inch / 32 Inches -> '32 INCH'.
    Fractions such as 1/2" or 12/16" (pipe sizes) are left untouched."""
    t = re.sub(r"(?<![\d./])(\d{2,3})\s*-?\s*(?:INCHES|INCH)\b", r"\1 INCH", text, flags=re.IGNORECASE)
    t = re.sub(r"(?<![\d./])(\d{2,3})\s*(?:\"|\u201d|\u2033)", r"\1 INCH", t)
    return t


def expand_cartesian_branches(title: str) -> list[str]:
    """If title contains slash-separated alternative models/variants, expand into independent branches."""
    # 0. Detect model followed by slash-separated variant tags (e.g. 'HPU-24HDZ CA/DC', 'DF-400 EDS/ES')
    # Preserves alternative sister variant models like HPU-24HDZCA vs HPU-24HDZDC
    m_var_slash = re.search(
        r"\b([A-Za-z]{2,4}[-_]?[A-Za-z0-9]+)\s+([A-Za-z0-9]{2,4})\s*/\s*([A-Za-z0-9]{2,4})\b",
        title,
    )
    if m_var_slash:
        base, v1, v2 = m_var_slash.group(1), m_var_slash.group(2), m_var_slash.group(3)
        b1_glued = title[: m_var_slash.start()] + f"{base}{v1}" + title[m_var_slash.end() :]
        b1_spaced = title[: m_var_slash.start()] + f"{base} {v1}" + title[m_var_slash.end() :]
        b2_glued = title[: m_var_slash.start()] + f"{base}{v2}" + title[m_var_slash.end() :]
        b2_spaced = title[: m_var_slash.start()] + f"{base} {v2}" + title[m_var_slash.end() :]
        return list(dict.fromkeys([b1_glued.strip(), b1_spaced.strip(), b2_glued.strip(), b2_spaced.strip()]))

    # Glued model slash: e.g. HPU-24HDZCA/DC
    m_glued_var_slash = re.search(
        r"\b([A-Za-z]{2,4}[-_]?[A-Za-z0-9]+?)([A-Za-z0-9]{2,4})\s*/\s*([A-Za-z0-9]{2,4})\b",
        title,
    )
    if m_glued_var_slash:
        base, v1, v2 = m_glued_var_slash.group(1), m_glued_var_slash.group(2), m_glued_var_slash.group(3)
        if len(base) >= 5 and re.search(r"\d", base):
            b1_glued = title[: m_glued_var_slash.start()] + f"{base}{v1}" + title[m_glued_var_slash.end() :]
            b2_glued = title[: m_glued_var_slash.start()] + f"{base}{v2}" + title[m_glued_var_slash.end() :]
            return list(dict.fromkeys([b1_glued.strip(), b2_glued.strip()]))

    t_norm = normalize_technical_slashes(title)
    safeguards: list[str] = []

    def mask_fn(m: re.Match[str]) -> str:
        safeguards.append(m.group(0))
        return f"__SAFEGUARD_{len(safeguards) - 1}__"

    t_masked = SAFEGUARD_PATTERN.sub(mask_fn, t_norm)

    # Detect alternative model codes separated by slash:
    # e.g. 'HRF-418 TIFG1U1/TIFB1U1 (IOT)' or 'HGL-25MXP8 / 25MXP9' or '30 Sprinter / Powercon'
    # or paired slashes: 'HRF-346 EPR/EPB (Red/Black)'
    slashes = list(re.finditer(r"(\b[A-Za-z0-9\-_]+)\s*/\s*([A-Za-z0-9\-_]+)", t_masked))
    branches: list[str]
    if len(slashes) >= 2 and all(
        len(s.group(1)) >= 2 and len(s.group(2)) >= 2
        and not s.group(1).startswith("__SAFEGUARD_")
        and not s.group(2).startswith("__SAFEGUARD_")
        for s in slashes[:2]
    ):
        s1, s2 = slashes[0], slashes[1]
        b1 = (t_masked[: s1.start()] + s1.group(1) + t_masked[s1.end() : s2.start()] + s2.group(1) + t_masked[s2.end() :]).strip()
        b2 = (t_masked[: s1.start()] + s1.group(2) + t_masked[s1.end() : s2.start()] + s2.group(2) + t_masked[s2.end() :]).strip()
        branches = [b1, b2]
    elif len(slashes) == 1:
        m_slash = slashes[0]
        left = m_slash.group(1).strip()
        right = m_slash.group(2).strip()
        if len(left) >= 2 and len(right) >= 2 and not left.startswith("__SAFEGUARD_") and not right.startswith("__SAFEGUARD_"):
            b1 = t_masked[: m_slash.start()] + left + t_masked[m_slash.end() :]
            b2 = t_masked[: m_slash.start()] + right + t_masked[m_slash.end() :]
            branches = [b1.strip(), b2.strip()]
            if "-" in left:
                pfx, stem_left = left.rsplit("-", 1)
                branches.append((t_masked[: m_slash.start()] + stem_left + t_masked[m_slash.end() :]).strip())
                branches.append((t_masked[: m_slash.start()] + f"{pfx}-{right}" + t_masked[m_slash.end() :]).strip())
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
    # 4-digit calendar years (e.g. 2024, 2025, 2026) are model-year specs, not SKU model codes
    if re.match(r"^(?:19|20)\d{2}$", clean):
        return True
    if clean.upper() in NON_SKU_TOKENS or re.match(r"^[48]K$", clean, re.IGNORECASE):
        return True
    # Units attached to numbers: 3FEET, 3FT, 4FEET, 7KG, 8-KG, 13SETS, 40INCH, 1000W, 3.2L, 3IN1, etc.
    if re.match(
        r"^\d+(?:\.\d+)?(?:[-_]?(?:FEET|FT|INCH|MM|CM|KG|GM|LTR|LITRE|LITRES?|LITERS?|L|SETS?|TON|WATTS?|W|V|HZ|\"|\'))?$",
        clean,
        re.IGNORECASE,
    ):
        # Standalone pure numbers with >= 3 digits (like 1088, 1400, 9270, 330) are valid model codes
        if re.match(r"^\d+$", clean):
            return len(clean) <= 2
        return True
    if re.match(r"^\d{1,2}K$", clean, re.IGNORECASE):  # 2K 4K 8K
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
    # Units attached to numbers (e.g. 1.5TON, 9KG, 8-KG, 40INCH, 1000W, 3.2L) are specs, not SKU variant tags
    if re.match(
        r"^\d+(?:\.\d+)?(?:[-_]?(?:FEET|FT|INCH|MM|CM|KG|GM|LTR|LITRE|LITRES?|LITERS?|L|SETS?|TON|WATTS?|W|V|HZ|\"|\'))$",
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
    clean = full_name.replace("—", " ").replace("–", " ").replace("|", " ").replace("[", "(").replace("]", ")").replace("{", "(").replace("}", ")").strip()
    clean = re.sub(r"\(([A-Za-z0-9_-]+)\)", r" \1 ", clean).strip()

    # 1. Dynamically strip Brand name and brand abbreviation using catalog brand metadata
    first_w = clean.split()[0] if clean else ""
    detected_brand = (brand or (first_w if first_w and not re.search(r"\d", first_w) else "")).strip()
    if detected_brand:
        b_prefix_re = rf"^(?:{re.escape(detected_brand)}|{re.escape(detected_brand[:3]) if len(detected_brand) >= 4 else '---'})[\s\-_,:]*"
        while re.match(b_prefix_re, clean, flags=re.IGNORECASE):
            clean = re.sub(b_prefix_re, "", clean, count=1, flags=re.IGNORECASE).strip()

    # Pre-process technical slashes before category stripping (24 HD/Z -> 24 HDZ, 24 HE/DC -> 24 HE-DC)
    clean = normalize_technical_slashes(clean)

    # Normalize spaced capacity code before alphanumeric model stem (e.g. 12 SVN-AI-CO-31S -> 12SVN-AI-CO-31S)
    caps_pattern = "|".join(sorted(UNIVERSAL_CAPACITY_TO_TONNAGE.keys(), key=len, reverse=True))
    clean = re.sub(
        rf"\b({caps_pattern})\s+([A-Za-z]{{2,}}[-_A-Za-z0-9]*(?:\d+|-)[-_A-Za-z0-9]*)\b",
        r"\1\2",
        clean,
    )

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

    # Check for TV pattern: e.g. 32" D2 -> 32 D2 (only if model is not a generic descriptor/non-sku token)
    m_tv = re.search(r"\b(\d{2})\s*-?\s*(?:\"|inches|inch|\')\s+([A-Za-z0-9][A-Za-z0-9\-_]*)\b", clean, flags=re.IGNORECASE)
    if m_tv and m_tv.group(2).upper() not in NON_SKU_TOKENS:
        cand_tv = m_tv.group(2)
        has_downstream_sku = bool(
            re.search(
                r"\b(?!\d{2}\s*(?:inch|\"|\'))[A-Za-z0-9\-_]*\d+[A-Za-z0-9\-_]*\b",
                clean[m_tv.end():],
                flags=re.IGNORECASE,
            )
        )
        if re.search(r"\d", cand_tv) or not has_downstream_sku:
            screen = m_tv.group(1)
            model = cand_tv
            query = f"{detected_brand} {screen} {model}".strip() if detected_brand else f"{screen} {model}"
            return query, f"{screen} {model}"

    # 2. Strip standard category and capacity phrases
    clean = CATEGORY_PATTERNS.sub(" ", clean).strip()

    # 3. Find model code:
    # Primary model token contains digits: e.g. DWT-1165, 100-316S6, HDG-201S, 12AITH21W-T3
    # Subsequent tokens are SKU variant tags (<= 3 chars or containing digits, e.g. PL, FLT, ES, GC)
    raw_tokens = clean.split()
    tokens: list[str] = []
    i = 0
    while i < len(raw_tokens):
        t = raw_tokens[i]
        if i + 1 < len(raw_tokens):
            nxt = raw_tokens[i + 1]
            if (
                re.match(r"^[A-Za-z]{2,4}(?:-[A-Za-z]{2,4})?$", t)
                and t.upper() not in GENUINE_SUB_SERIES_TOKENS
                and t.upper() not in NON_SKU_TOKENS
                and re.match(r"^\d{1,2}$", nxt)
            ):
                if (
                    i + 2 < len(raw_tokens)
                    and re.match(r"^[A-Za-z]{1,3}$", raw_tokens[i + 2])
                    and raw_tokens[i + 2].upper() not in NON_SKU_TOKENS
                    and not is_color_token(raw_tokens[i + 2])
                ):
                    tokens.append(f"{t}-{nxt}{raw_tokens[i + 2]}")
                    i += 3
                    continue
                tokens.append(f"{t}-{nxt}")
                i += 2
                continue
        tokens.append(t)
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
            query = f"{detected_brand} {ser_tok} {cap_tok}".strip() if detected_brand else f"{ser_tok} {cap_tok}"
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
            is_numeric_stem_color = bool(model_tokens and model_tokens[0].isdigit() and is_color_token(t_clean))
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

    Target ``DWT-270 C`` carries variant letter ``C``. A candidate ``DWT 270 S LVS+``
    carries ``S`` after the same stem -> collision. A candidate with no suffix letter
    (``DWT 270 LVS+``) is not a collision. Fully dynamic: no letters or stems hardcoded.
    """
    tokens = target_model.split()
    for i, tok in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        m_stem = re.fullmatch(r"([A-Za-z]*)[- ]?(\d{3,})", tok.strip())
        if not (m_stem and re.fullmatch(r"[A-Za-z]", nxt)):
            continue
        letters, digits = m_stem.group(1), m_stem.group(2)
        target_letter = nxt.upper()
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
    caps_pattern = "|".join(sorted(UNIVERSAL_CAPACITY_TO_TONNAGE.keys(), key=len, reverse=True))
    clean_name = re.sub(
        rf"\b({caps_pattern})\s+([A-Za-z]{{2,}}[-_A-Za-z0-9]*(?:\d+|-)[-_A-Za-z0-9]*)\b",
        r"\1\2",
        clean_name,
    )
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
    # Guard: Product with complex alphanumeric model (e.g. HSU-13HFS, 120-316S6) is NOT a series capacity product
    has_alphanumeric_model = any(
        not is_dimension_or_spec_token(t)
        and (
            (re.search(r"\d", t) and re.search(r"[A-Za-z]", t))
            or ("-" in t and any(c.isdigit() for c in t))
        )
        for t in tokens
    )
    is_trailing_cap = len(tokens) >= 2 and tokens[-1].isdigit() and len(tokens[-1]) <= 2
    is_leading_cap = len(tokens) >= 2 and tokens[0].isdigit() and len(tokens[0]) <= 2
    is_series_capacity = (is_trailing_cap or is_leading_cap) and not has_alphanumeric_model

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
                if stem_num and stem_num != bare_stem and "-" not in bare_stem:
                    tier_1.append(_with_brand(detected_brand, _with_prefix(pfx, stem_num, " ")))
                    tier_1.append(_with_brand(detected_brand, _with_prefix(pfx, stem_num, "-")))
                tier_1.append(_with_brand(detected_brand, raw_model))
                # Standalone prefix for sellers who omit brand name (e.g. DMB 4467, HRF 538)
                tier_1.append(_with_prefix(pfx, bare_stem, " "))
                if stem_num and stem_num != bare_stem and "-" not in bare_stem:
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
        pure_stem = re.sub(rf"^{re.escape(pfx)}[-_]?", "", bare_stem, flags=re.IGNORECASE) if pfx else ""
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
            mod_tag = aux_tag or (" ".join(tokens[1:]).strip() if len(tokens) > 1 else "")
            if mod_tag:
                clean_mod = mod_tag.replace(" ", "")
                tier_1.append(f"{bare_stem}{clean_mod}")
                if "-" in bare_stem:
                    tier_1.append(f"{bare_stem.replace('-', '')}{clean_mod}")
                if detected_brand:
                    tier_1.append(_with_brand(detected_brand, f"{bare_stem}{clean_mod}"))
            tier_2.append(bare_stem)

        # Color-specific search permutations if target specifies a distinct color (e.g. (G), Golden, (DG), Dark Grey, White, Black)
        _, raw_color = normalize_color(clean_name, anchor=bare_stem)
        if raw_color:
            color_upper = raw_color.upper()
            color_candidates: list[str] = []
            if color_upper in COLOR_CODE_FULL_NAMES:
                full_color = COLOR_CODE_FULL_NAMES[color_upper]
                color_candidates.extend([
                    f"{bare_stem} {color_upper}",
                    f"{bare_stem} {full_color}",
                    f"{bare_stem}-{color_upper}",
                ])
                if pfx:
                    pure_stem = re.sub(rf"^{re.escape(pfx)}[-_]?", "", bare_stem, flags=re.IGNORECASE)
                    if pure_stem and pure_stem != bare_stem:
                        color_candidates.extend([
                            f"{pure_stem} {color_upper}",
                            f"{pure_stem} {full_color}",
                            f"{pure_stem}-{color_upper}",
                            f"{pure_stem}({color_upper})",
                        ])
                    color_candidates.extend([
                        _with_prefix(pfx, f"{bare_stem} {color_upper}", " "),
                        _with_prefix(pfx, f"{bare_stem} {full_color}", " "),
                        _with_prefix(pfx, f"{bare_stem}-{color_upper}", "-"),
                        _with_prefix(pfx, f"{bare_stem}({color_upper})", "-"),
                    ])
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
        if re.search(r"Save[-_ ]?IN", bare_stem, re.IGNORECASE) or re.search(r"\bSVN\b", bare_stem, re.IGNORECASE) or re.search(r"\d+SVN", bare_stem, re.IGNORECASE):
            svn_stem = re.sub(r"Save[-_ ]?IN", "SVN", bare_stem, flags=re.IGNORECASE)
            savein_stem = re.sub(r"SVN", "SaveIN", bare_stem, flags=re.IGNORECASE)
            tac_svn = _with_prefix("TAC", svn_stem, "-")
            no_tac_svn = re.sub(r"^TAC[-_]?", "", svn_stem, flags=re.IGNORECASE)
            no_tac_savein = re.sub(r"^TAC[-_]?", "", savein_stem, flags=re.IGNORECASE)

            tier_1.extend([svn_stem, tac_svn, no_tac_svn, savein_stem, no_tac_savein])
            if detected_brand:
                tier_1.extend([
                    _with_brand(detected_brand, svn_stem),
                    _with_brand(detected_brand, tac_svn),
                    _with_brand(detected_brand, no_tac_svn),
                    _with_brand(detected_brand, savein_stem),
                ])

            tier_2.extend([svn_stem, tac_svn, no_tac_svn, savein_stem])
            if detected_brand:
                tier_2.extend([
                    _with_brand(detected_brand, svn_stem),
                    _with_brand(detected_brand, no_tac_svn),
                ])

            m_cap_svn = re.search(r"\b(\d{1,2})(?:SVN|SaveIN)", svn_stem, re.IGNORECASE)
            if m_cap_svn:
                cap_svn = m_cap_svn.group(1)
                tier_3.extend([f"{cap_svn}SVN", f"TAC-{cap_svn}SVN"])
                if detected_brand:
                    tier_3.append(_with_brand(detected_brand, f"{cap_svn}SVN"))

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
    if has_space_pfx and suf:
        # pfx was separated by space, while num+suf form a digit-first alphanumeric model (e.g. 24SVN-AI-41, 32D2)
        return "", first_token_tag
    if num.isdigit() and len(num) <= 2 and (not suf or pfx in GENUINE_SUB_SERIES_TOKENS or pfx in {"SPLIT", "AUTO", "AWM"}):
        return "", first_token_tag
    elif pfx in NON_SKU_TOKENS:
        # Category noise words (e.g. 'TV', 'AC', 'REF') should NEVER become anchor prefixes!
        # If followed by alphanumeric model (e.g. 32D2, 24SVN-AI-41), defer to alphanumeric candidate search
        if not suf and not (num.isdigit() and len(num) <= 2):
            return num, first_token_tag
        return "", first_token_tag
    elif suf and len(suf) <= 8 and suf not in {"INVERTER", "SERIES", "NORMAL"}:
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
    raw_clean = title.replace("—", " ").replace("–", " ").replace("|", " ").replace("[", "(").replace("]", ")").replace("{", "(").replace("}", ")").strip()
    raw_clean = re.sub(r"\s*[-–—|]\s*(?:By\s+|Official\s+)[A-Za-z0-9\s.]{2,}$", "", raw_clean, flags=re.IGNORECASE)
    raw_clean = re.sub(r"\s*[-–—|]\s*(?:HomeCart|ElectroEase|Telemart|Metro|Hyperstar|AlfaMall|Faysal Bank|QistBazaar)\b.*$", "", raw_clean, flags=re.IGNORECASE)
    raw_clean = MERCHANT_TRACKING_CODE_RE.sub(" ", raw_clean)
    clean_title = normalize_technical_slashes(raw_clean)
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
        for m_pfx in re.finditer(r"\b([A-Za-z]{2,4})[-_ ]?(\d+(?:-\d+)?)[-_ ]?([A-Za-z0-9]*)\b", sub_anchor):
            cand_anc, cand_tag = _anchor_from_prefix_match(m_pfx, first_token_tag)
            num_suf = f"{m_pfx.group(2)}{(m_pfx.group(3) or '').upper()}"
            if not cand_anc or is_dimension_or_spec_token(cand_anc) or is_dimension_or_spec_token(num_suf):
                continue
            anchor = cand_anc.strip("()[]-.,_ \"'")
            first_token_tag = cand_tag
            break

        if not anchor:
            for m_cand in re.finditer(r"\b(\d+[A-Za-z]+[A-Za-z0-9\-]*|[A-Za-z]+\d+[A-Za-z0-9\-]*)\b", sub_anchor):
                cand_tok = m_cand.group(1).upper()
                if not is_dimension_or_spec_token(cand_tok):
                    m_lead_num = re.search(rf"\b(\d{{1,2}})\s+{re.escape(m_cand.group(1))}\b", sub_anchor)
                    if m_lead_num and not cand_tok[0].isdigit():
                        anchor = f"{m_lead_num.group(1)}{cand_tok}".strip("()[]-.,_ \"'")
                    else:
                        anchor = cand_tok.strip("()[]-.,_ \"'")
                    break
            if not anchor:
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
                        anchor = f"{m_cap_ser.group(1)}{w.upper()}".strip("()[]-.,_ \"'")

    # 2. Guarded Facets Extraction
    # AC Category Detection (used for AC tonnage capacity extraction)
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

    # 2a. Operating Mode: Cool Only vs Heat & Cool
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
    m_screen = re.search(r"(?<![\d./])(\d{2})\s*-?\s*(?:INCH(?:ES)?\b|\"|\')", clean_title, re.IGNORECASE)
    if m_screen:
        capacity = f"{m_screen.group(1)}INCH"
        is_display = True
    elif is_display and anchor and re.match(r"^(\d{2})[A-Z]\w{3,}$", anchor):
        capacity = f"{anchor[:2]}INCH"
    else:
        # Refrigerator CFT (Cubic Feet)
        m_cft = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:CU\s*FT|CU\.FT|CFT)\b", clean_title, re.IGNORECASE)
        if m_cft:
            capacity = f"{int(float(m_cft.group(1)))}CFT"
        else:
            # Washing machine KG
            m_kg = re.search(r"\b(\d+(?:\.\d+)?)\s*[-]?\s*KG\b", clean_title, re.IGNORECASE)
            if m_kg:
                capacity = f"{int(float(m_kg.group(1)))}KG"
            elif anchor and re.match(r"^(\d{2,3})-\d+", anchor):
                num_val = int(re.match(r"^(\d{2,3})-\d+", anchor).group(1))
                capacity = f"{num_val // 10}KG"
            elif not is_non_ac:
                # AC Tonnage
                m_ton = re.search(r"\b(\d+(?:\.\d+)?)\s*[-]?\s*(?:TON|ΤΟN)\b", clean_title, re.IGNORECASE)
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
    elif re.search(r"\b(?:INVERTER|INV|DC\s*INVERTER|SAVEIN)\b", clean_title, re.IGNORECASE) or (
        anchor and re.search(r"(?:SVN|INV)", anchor, re.IGNORECASE)
    ):
        is_inverter = True

    # 2i. Dynamic Post-Model Code & Category 2 Modifiers Engine
    # Dynamically grabs the code right after the model and across remaining tokens
    # (e.g. ES, ES8, T3, T4, UV, WIFI, IOT) with ZERO hardcoding.
    # RULE:
    # - If token in CATEGORY_1_DIRECT_MATCH_MODIFIERS -> Category 1 (Direct match when omitted)
    # - Else -> Category 2 (Exact match if present, fallback if omitted, collision if extra/different)
    caps: set[str] = set()

    # 1. Connectivity and hardware keywords across title
    has_wifi = bool(re.search(r"\b(?:WIFI|WI-FI)\b", clean_title, re.IGNORECASE))
    if has_wifi:
        caps.add("WIFI")
    if re.search(r"\bIOT\b", clean_title, re.IGNORECASE) or (
        not is_display and not has_wifi and re.search(r"\bSMART\b", clean_title, re.IGNORECASE)
    ):
        caps.add("IOT")
    for m_hw in re.finditer(r"\b(?:T[-_\s]?[34]|UV)\b", clean_title, re.IGNORECASE):
        caps.add(re.sub(r"[-_\s]", "", m_hw.group(0)).upper())

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
        if len(anc_parts) > 1 and any(re.search(r"\d", p) for p in anc_parts[:-1]) and is_sku_variant_tag(anc_parts[-1]):
            candidate_tokens.append(anc_parts[-1].upper())

    # B. Trailing tokens immediately following the model in raw_model:
    # If the first token is a 1-2 digit capacity code (e.g. '24 HDZ', '32 D2', '50 MB'),
    # the compound model is tokens[0] + tokens[1], and trailing modifiers start at tokens[2:]!
    post_model_tokens = tokens[2:] if (len(tokens) >= 2 and tokens[0].isdigit() and len(tokens[0]) <= 2) else tokens[1:]
    for t in post_model_tokens:
        t_clean = t.strip("()[]-.,_ \"'/").upper()
        if is_sku_variant_tag(t_clean):
            candidate_tokens.append(t_clean)

    # C. Search code right after the model AND across all remaining tokens in clean_title:
    post_words: list[str] = []
    if anchor:
        post_anchor = _text_after_anchor(clean_title, anchor)
        if post_anchor is not None:
            post_words = post_anchor.split()
        else:
            # Fallback: check if numeric stem exists in title
            m_stem = re.search(r"\d{3,}", anchor)
            if m_stem:
                idx = clean_title.find(m_stem.group(0))
                if idx != -1:
                    post_anchor = clean_title[idx + len(m_stem.group(0)) :]
                    post_words = post_anchor.split()

    _POST_STOP_WORDS = {
        "REGULAR", "DEEP", "FREEZER", "BRAND", "NEW", "BOX", "PACK", "WITH",
        "ORIGINAL", "WARRANTY", "BEST", "PRICE", "ON", "INSTALLMENT", "STUCCO",
        "PCM", "ARC", "WHITE", "BLACK", "GREY", "SILVER", "TECH", "HOUSE", "ISPK", "COD",
    }
    for w in post_words:
        w_clean = w.strip("()[]-.,_ \"'/").upper()
        if w_clean in _POST_STOP_WORDS:
            break
        if is_sku_variant_tag(w_clean):
            candidate_tokens.append(w_clean)
        elif "-" in w:
            w_sub = w.split("-")[-1].strip("()[]-.,_ \"'/").upper()
            if w_sub in _POST_STOP_WORDS:
                break
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
    sub = re.sub(r"\b(?:\d+(?:\.\d+)?\s*(?:CU\s*FT|CU\.FT|CFT|CU|LITRES?|LITERS?|LTRS?|LTR|L|KG|TON))\b", " ", sub, flags=re.IGNORECASE)
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

    series_tokens = [tok if tok == "/" else tok.strip("()[]-.,_ \"'+") for tok in sub.split()]
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
                if dec.is_base_match:
                    return dec
            for dec in decs:
                if any(x in dec.reason for x in ("mismatch", "collision")):
                    return dec
            return decs[0]

    cand_branches = expand_cartesian_branches(candidate_title)
    if len(cand_branches) > 1:
        decs = [referee_match(target, cb, brand=brand) for cb in cand_branches]
        for dec in decs:
            if dec.is_match:
                return dec
        for dec in decs:
            if dec.is_base_match:
                return dec
        for dec in decs:
            if any(x in dec.reason for x in ("mismatch", "collision")):
                return dec
        return decs[0]

    target_slots = extract_product_slots(target, brand=brand) if isinstance(target, str) else target
    cand_slots = extract_product_slots(candidate_title, brand=brand)

    # 0. Zero-Tolerance Brand Collision Guard
    if brand:
        b_target = brand.strip().upper()
        KNOWN_BRANDS = {
            "DAWLANCE", "HAIER", "GREE", "PEL", "KENWOOD", "ORIENT", "TCL",
            "ECOSTAR", "WAVES", "DANY", "BEURER", "SAMSUNG", "SUPER ASIA",
            "CHANGHONG", "CHANGHONG RUBA", "SONY", "AUDIONIC", "XIAOMI", "ANKER",
        }
        for b in KNOWN_BRANDS:
            if (
                b != b_target
                and re.search(rf"\b{re.escape(b)}\b", candidate_title, re.IGNORECASE)
                and not re.search(rf"\b{re.escape(b_target)}\b", candidate_title, re.IGNORECASE)
            ):
                return MatchDecision(
                    is_match=False,
                    reason=f"Brand collision: target is {brand} vs candidate mentions {b}",
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
    ):
        missing_finish = target_slots.guarded_facets.door_finish
        # For unique 5-digit catalog models (e.g. 91998 deep freezers), Glass Door is inherent to the SKU
        # and frequently omitted by marketplace sellers in listing titles.
        is_5digit_stem = bool(target_slots.anchor and re.search(r"\d{5,}", target_slots.anchor))
        if missing_finish == "GD" and is_5digit_stem:
            pass  # Accept as direct match
        else:
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
            t_nums = re.findall(r"\d{2,}", norm_t)
            c_nums = re.findall(r"\d{2,}", norm_c)
            norm_t_eq = norm_t.replace("SAVEIN", "SVN")
            norm_c_eq = norm_c.replace("SAVEIN", "SVN")

            if norm_t == norm_c or norm_t_eq == norm_c_eq or norm_t in norm_c or norm_t_eq in norm_c_eq or (len(norm_c) >= 3 and norm_c in norm_t) or norm_t in norm_cand_title:
                # Check for conflicting numeric series stems (e.g. 699 vs 2578, 130 vs 150, 316 vs 826)
                if t_nums and c_nums and len(t_nums) > 1 and len(c_nums) > 1:
                    # Multi-segment models: ALL significant numbers (capacity + series) must be consistent
                    matched_anchor = (set(t_nums) == set(c_nums))
                elif t_nums and c_nums and len(t_nums) == 1 and len(c_nums) == 1:
                    matched_anchor = (t_nums[0] == c_nums[0])
                elif (
                    t_nums
                    and c_nums
                    and len(t_nums) > 1
                    and len(c_nums) == 1
                    and (
                        re.search(rf"\b{re.escape(target_slots.anchor)}\b", candidate_title, re.IGNORECASE) is not None
                        or (
                            target_slots.guarded_facets.capacity
                            and cand_slots.guarded_facets.capacity
                            and target_slots.guarded_facets.capacity == cand_slots.guarded_facets.capacity
                            and "INCH" in target_slots.guarded_facets.capacity
                        )
                    )
                ):
                    # Candidate literally contains target's full anchor or matches same display screen + series
                    matched_anchor = True
                elif t_nums and c_nums and len(t_nums) > 1 and len(c_nums) == 1:
                    # Target is a specific multi-part series (e.g. 150B-699); candidate with only 1 number cannot match
                    matched_anchor = False
                else:
                    matched_anchor = True
            else:
                if t_nums and c_nums:
                    if len(t_nums) > 1 and len(c_nums) > 1:
                        matched_anchor = (set(t_nums) == set(c_nums))
                    elif len(t_nums) == 1 and len(c_nums) == 1:
                        m_pfx_t = re.match(r"^([A-Za-z]+)", target_slots.anchor)
                        m_pfx_c = re.match(r"^([A-Za-z]+)", cand_slots.anchor)
                        if m_pfx_t and m_pfx_c and m_pfx_t.group(1).upper() != m_pfx_c.group(1).upper():
                            matched_anchor = False
                        else:
                            matched_anchor = (t_nums[0] == c_nums[0])
                    elif len(t_nums) == 1 and t_nums[0] in c_nums:
                        matched_anchor = True
        elif norm_t in norm_cand_title:
            matched_anchor = True
        else:
            t_nums = re.findall(r"\d{3,}", norm_t)
            if t_nums and len(t_nums) == 1 and t_nums[0] in norm_cand_title:
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
                if (
                    suf_t.isalpha()
                    and suf_c.isalpha()
                    and norm_t[:2] == norm_c[:2]
                    and suf_t != suf_c
                    and not (norm_c == norm_t[:-2] or norm_t == norm_c[:-2])
                ):
                    return MatchDecision(
                        is_match=False,
                        reason=f"Variant tag collision: {norm_t} vs {norm_c}",
                        target_slots=target_slots,
                        candidate_slots=cand_slots,
                    )

                # Generation / series code collision (e.g. S8 vs S6, G1 vs G2)
                gen_t = re.search(r"([A-Z]\d)$", norm_t)
                gen_c = re.search(r"([A-Z]\d)$", norm_c)
                if gen_t and gen_c and gen_t.group(1) != gen_c.group(1):
                    return MatchDecision(
                        is_match=False,
                        reason=f"Generation series collision: {gen_t.group(1)} vs {gen_c.group(1)} ({norm_t} vs {norm_c})",
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
            is_distinct_model = bool(
                target_slots.anchor
                and (
                    re.search(r"\d{3,}", target_slots.anchor)
                    or re.search(r"[A-Za-z]+[-_]?\d+", target_slots.anchor)
                    or (cand_slots.anchor and target_slots.anchor.upper() in cand_slots.anchor.upper())
                )
            )
            # Check if candidate has an opposing, conflicting series
            cand_ser_clean = cand_slots.series.strip().upper()
            has_conflicting_series = bool(
                cand_ser_clean
                and cand_ser_clean not in {"REGULAR", "STANDARD", "NORMAL"}
                and not any(cand_ser_clean in alt for alt in alternatives)
                and not any(alt in cand_ser_clean for alt in alternatives)
            )
            target_all_text = f"{target_slots.anchor} {target_slots.series} {target_slots.guarded_facets.tub_series or ''} {' '.join(target_slots.residuals)}".upper()
            target_all_chars = re.sub(r"[^A-Za-z0-9]", "", target_all_text)
            cand_anchor_norm = re.sub(r"[^A-Za-z0-9]", "", cand_slots.anchor.upper()) if cand_slots.anchor else ""
            t_stem_match = re.search(r"\d{2,}", target_slots.anchor)
            stem_val = t_stem_match.group(0) if t_stem_match else ""
            extra_cand_letters = cand_anchor_norm.replace(stem_val, "")
            if brand:
                b_init = brand[0].upper()
                extra_cand_letters = re.sub(rf"^{re.escape(b_init)}[A-Z]{{0,3}}", "", extra_cand_letters)
            extra_ok = not extra_cand_letters or all(c in target_all_chars for c in extra_cand_letters)

            if is_distinct_model and not has_conflicting_series and extra_ok:
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
    extra_cand_caps = {
        c
        for c in (cand_caps - target_caps)
        if not (target_slots.anchor and c in target_slots.anchor.upper())
        and c not in {"WIFI", "IOT"}
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

    # Fallback 2: Target specifies Category 2 modifiers that candidate omitted -> Valid base-model fallback
    missing_target_caps = {
        c
        for c in (target_caps - cand_caps)
        if not (cand_slots.anchor and c in cand_slots.anchor.upper())
        and not re.search(rf"\b{re.escape(c)}\b", candidate_title, re.IGNORECASE)
        and not (cand_slots.series and c in cand_slots.series.upper())
    }
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
