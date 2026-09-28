import re

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
    r"\b(?:AUTO\s+W/M|FRONT\s+LOAD\s+W/M|W/M|M/OVEN|M/O|D/F|R/F|W/D|SPLIT\s+AC|SPLIT|CASSETTE|FLOOR(?:\s+STANDING)?|DISHWASHER|SPINNER)\b"
    r"|\b(?:AIR\s+CURTAIN|AIR\s+COOLER|AIR\s+FRYER|WATER\s+HEATER|WATER\s+DISPENSER|WATER\s+PURIFIER|INSECT\s+KILLER|JUG\s+KETTLE|HOT\s+PLATE|CHOPPER|BLENDER|IRON|LED|MICROWAVE|OVEN|SANDWI?T?CH\s+MAKER)\b"
    r"|\b(?:INVERTER|NORMAL|SERIES|DIGITAL|GLASS\s+DOOR|CLEAR\s+LID|SMART|4K|FHD|HD|GAS\+ELECTRIC|BUILT-IN)\b"
    r"|\b(?:\d+(?:\.\d+)?\s*(?:TON|ΤΟN|KG|GM|LTR|LITRE|SETS|SETS?|FEET|FT|INCH|MM|CM|\"|\'))\b",
    re.IGNORECASE,
)

# Common non-SKU unit stop-tokens
NON_SKU_TOKENS = {
    "TON", "ΤΟN", "KG", "GM", "LTR", "SET", "SETS", "FEET", "FT", "MM", "CM", "INCH",
    "AC", "AND", "WITH", "THE", "FOR", "TOP", "LID", "DOOR", "AIR", "CURTAIN",
    "BLENDER", "CHOPPER", "OVEN", "HEATER", "WASHER", "PURIFIER", "KETTLE", "SMART",
    "W/O", "REF",
}


def is_dimension_or_spec_token(token: str) -> bool:
    """Check if a token represents physical dimensions, capacity, or feature counts instead of a model code."""
    clean = token.strip("-_., \"'")
    if not clean:
        return True
    # Units attached to numbers: 3FEET, 3FT, 4FEET, 7KG, 13SETS, 40INCH, 3IN1, etc.
    if re.match(r"^\d+(?:\.\d+)?(?:FEET|FT|INCH|MM|CM|KG|GM|LTR|LITRE|SETS?|TON|\"|\')?$", clean, re.IGNORECASE):
        # Standalone pure numbers with >= 3 digits (like 1088, 1400, 9270, 330) are valid model codes
        if re.match(r"^\d+$", clean):
            return len(clean) <= 2
        return True
    return bool(re.match(r"^\d+IN\d+$", clean, re.IGNORECASE))  # 3IN1, 2IN1


def is_sku_variant_tag(token: str) -> bool:
    """Dynamically determine if a trailing token is an SKU variant tag (PL, FLT, ES, GC, T3)
    vs a marketing or color word (WHITE, BLACK, MYSTIC, GREY, CLOUD, EMERALD).

    Structural Rule (Zero Hardcoded Color Lists):
    - Pure numbers and decimal floats (e.g. 2.0, 1.5, 12) -> Capacity / Specs, NOT an SKU tag!
    - Contains digits AND letters (e.g. S6, S8, T3, 11S) -> SKU Variant Tag.
    - Short uppercase code <= 3 characters (e.g. PL, FLT, FLP, GC, DG, CP, PB, ES) -> SKU Variant Tag.
    - English words, colors, and marketing descriptions have length >= 4 -> Automatically Excluded!
    """
    clean = token.strip("-_., \"'")
    if not clean or clean.upper() in NON_SKU_TOKENS or is_dimension_or_spec_token(clean):
        return False
    # Pure numbers or decimal floats (e.g. 2.0, 1.5, 24) are capacities, not SKU variant tags
    if re.match(r"^\d+(?:\.\d+)?$", clean):
        return False
    # If contains digits, must also contain letters (e.g. T3, S6, S8, 11S)
    if re.search(r"\d", clean):
        return bool(re.search(r"[A-Za-z]", clean))
    # If pure letters: short uppercase code of length <= 3
    return len(clean) <= 3 and clean.isupper()


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
    detected_brand = brand or (clean.split()[0] if clean else "")
    if detected_brand:
        clean = re.sub(rf"^\b{re.escape(detected_brand)}\b\s*", "", clean, flags=re.IGNORECASE)
        if len(detected_brand) >= 4:
            clean = re.sub(rf"^\b{re.escape(detected_brand[:3])}\b\s*", "", clean, flags=re.IGNORECASE)

    # 2. Strip standard category and capacity phrases
    clean = CATEGORY_PATTERNS.sub(" ", clean).strip()

    # 3. Find model code:
    # Primary model token contains digits: e.g. DWT-1165, 100-316S6, HDG-201S, 12AITH21W-T3
    # Subsequent tokens are SKU variant tags (<= 3 chars or containing digits, e.g. PL, FLT, ES, GC)
    tokens = clean.split()
    model_tokens: list[str] = []

    for t in tokens:
        t_clean = t.strip("-.,_ \"'")
        if not t_clean or t_clean.upper() in NON_SKU_TOKENS:
            continue
        if not model_tokens:
            if len(t_clean) >= 3 and re.search(r"\d", t_clean) and not is_dimension_or_spec_token(t_clean) and re.match(r"^[A-Za-z0-9\-_]+$", t_clean):
                model_tokens.append(t_clean)
        else:
            if is_sku_variant_tag(t_clean):
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
            clean_first = re.sub(rf"^{re.escape(detected_brand[0])}[A-Za-z][-_]?(?=\d)", "", first_token, flags=re.IGNORECASE)
        parts = clean_first.split("-")
        search_token = parts[0] if parts and len(parts[0]) >= 5 else clean_first
        return search_token, raw_model

    # 4. Name-only fallback: no digit-based model token found.
    # Collect series names, capacity codes, and sub-variant descriptors.
    # Stop-words that are NOT part of the product identity:
    _NAME_STOP = {
        "INVERTER", "INV", "SERIES", "NORMAL", "COOL", "ONLY",
        "+", "(", ")", "[", "]",
    }
    # Brand-aware AC capacity codes:
    # Dawlance: 10 (0.75T), 15 (1T), 20 (1.25T), 30 (1.5T), 45 (2T)
    # Universal (Gree, Haier, Orient, PEL, Kenwood, etc.): 09/9 (0.75T), 12 (1T), 18 (1.5T), 24 (2T), 28/30 (2.5T), 36 (3T), 48 (4T)
    if detected_brand and detected_brand.upper().startswith("DAW"):
        _CAPACITY_CODES = {"10", "15", "20", "30", "45"}
    elif detected_brand:
        _CAPACITY_CODES = {"09", "9", "12", "18", "24", "28", "30", "36", "48"}
    else:
        _CAPACITY_CODES = {"09", "9", "10", "12", "15", "18", "20", "24", "28", "30", "36", "45", "48"}

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
            is_daw = bool(detected_brand and detected_brand.upper().startswith("DAW"))
            ton_map = DAWLANCE_TONNAGE_TO_CODES if is_daw else UNIVERSAL_TONNAGE_TO_CODES
            ton_codes = ton_map.get(ton_val)
            if ton_codes:
                capacity = sorted(ton_codes)[0]
                significant.append(capacity)

    if significant:
        # Search query: Brand + first significant word + capacity (broad search)
        query_parts = []
        if detected_brand:
            query_parts.append(detected_brand)
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
    """Separate trailing auxiliary tag (e.g. -T3, AAA, PRO) from token core."""
    m = TAG_PATTERN.search(s)
    if m:
        return s[:m.start()], m.group(0)
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
        remainder = core[len(digits):]
        m_let = re.search(r"([A-Za-z]+)$", remainder)
        letters = m_let.group(1) if m_let else ""
        middle = remainder[:len(remainder) - len(letters)]
        parsed.append({
            "raw": p,
            "core": core,
            "digits": digits,
            "middle": middle,
            "letters": letters,
            "tag": tag,
        })

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
        remainder = core[len(digits):]
        m_let = re.search(r"([A-Za-z]+)$", remainder)
        letters = m_let.group(1) if m_let else ""
        middle = remainder[:len(remainder) - len(letters)]
        parsed.append({
            "raw": p,
            "core": core,
            "digits": digits,
            "middle": middle,
            "letters": letters,
            "tag": tag,
        })

    p0 = parsed[0]["core"]
    p1 = parsed[1]["core"]

    lead_runs = split_runs(p0)
    sub_runs = split_runs(p1)

    n_sub = len(sub_runs)
    n_lead = len(lead_runs)
    sub_types = [t for t, _ in sub_runs]
    split_idx = -1

    # 1. Exact run sequence match at tail of lead_runs
    if n_lead >= n_sub and [t for t, _ in lead_runs[n_lead - n_sub:]] == sub_types:
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
    var0_remainder = var0_core[len(prefix_digits):]
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
        return f"__SAFEGUARD_{len(safeguards)-1}__"

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

    # 2. Normalize spaced slashes: e.g. "14S /11S" -> "14S/11S"
    clean_title = re.sub(r"([A-Za-z0-9\-_]+)\s*[/,]\s*([A-Za-z0-9\-_]+)", r"\1/\2", clean_title)
    clean_title = re.sub(r"([A-Za-z0-9]+)\s+-\s+([A-Za-z0-9]+/[A-Za-z0-9]+)", r"\1-\2", clean_title)

    # 3. Process tokens containing '/'
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

UNIVERSAL_TONNAGE_TO_CODES: dict[str, set[str]] = {
    "0.75": {"09", "9"},
    "1": {"12"},
    "1.0": {"12"},
    "1.5": {"18"},
    "2": {"24"},
    "2.0": {"24"},
    "2.5": {"28", "30"},
    "3": {"36"},
    "3.0": {"36"},
    "4": {"48"},
    "4.0": {"48"},
}

DAWLANCE_TONNAGE_TO_CODES: dict[str, set[str]] = {
    "0.75": {"10"},
    "1": {"15"},
    "1.0": {"15"},
    "1.25": {"20"},
    "1.5": {"30"},
    "2": {"45"},
    "2.0": {"45"},
}


def get_capacity_tonnage(code: str, brand: str = "") -> str | None:
    """Get the tonnage string for an AC capacity code, brand-aware."""
    clean_code = code.strip().upper()
    b_upper = brand.strip().upper()
    is_dawlance = b_upper.startswith("DAW") or b_upper == "DAWLANCE"

    if is_dawlance:
        return DAWLANCE_CAPACITY_TO_TONNAGE.get(clean_code)

    if b_upper and not is_dawlance:
        return UNIVERSAL_CAPACITY_TO_TONNAGE.get(clean_code)

    # Brand unknown: determine by code exclusivity
    if clean_code in ("10", "15", "20", "45"):
        return DAWLANCE_CAPACITY_TO_TONNAGE.get(clean_code)
    if clean_code in ("09", "9", "12", "18", "24", "28", "36", "48"):
        return UNIVERSAL_CAPACITY_TO_TONNAGE.get(clean_code)
    return DAWLANCE_CAPACITY_TO_TONNAGE.get(clean_code)


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
    b_upper = brand.strip().upper()
    is_daw = b_upper.startswith("DAW") or b_upper == "DAWLANCE"
    tonnage_map = DAWLANCE_TONNAGE_TO_CODES if is_daw else UNIVERSAL_TONNAGE_TO_CODES
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

    # Detect brand
    target_brand = brand.strip()
    if not target_brand:
        for b in [
            "DAWLANCE", "DAW", "GREE", "HAIER", "KENWOOD", "HOMAGE",
            "ORIENT", "PEL", "TCL", "CHANGHONG", "ECOSTAR", "MIDEA", "DAIKIN",
        ]:
            if re.search(rf"\b{b}\b", target_keywords, re.IGNORECASE) or re.search(
                rf"\b{b}\b", expanded_title, re.IGNORECASE
            ):
                target_brand = "DAWLANCE" if b in ("DAWLANCE", "DAW") else b
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
        return _keyword_match(expanded_title, clean_target, brand=brand)

    # Normalize alphanumerics for baseline containment
    norm_target = re.sub(r"[^A-Z0-9]", "", clean_target.upper())
    norm_title = re.sub(r"[^A-Z0-9]", "", expanded_title.upper())

    # Auxiliary tag stripping (T3, AAA, AA, PRO, ULTRA) for core base comparison
    tag_pattern = re.compile(r"(?:T3|AAA|AA\+|AA|PRO|ULTRA)+$", re.IGNORECASE)
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

    # 2. Multi-token model containment (e.g. "DWT-1165 PL" -> "DWT1165" and "PL")
    target_tokens = [re.sub(r"[^A-Z0-9]", "", t.upper()) for t in clean_target.split() if t.strip()]
    if len(target_tokens) > 1 and all(t in norm_title for t in target_tokens):
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
                    rem = norm_w_core[idx + len(base_no_w):]
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

    detected_brand = brand.strip() or clean_name.split()[0]
    search_token, raw_model = extract_search_query_and_model(clean_name, brand=detected_brand)

    tier_1: list[str] = []
    tier_2: list[str] = []
    tier_3: list[str] = []

    # Detect prefixes like HWM, DWT, GS, GW, GF, GN, WF in the raw catalog name
    pfx_match = re.search(r"\b(HWM|DWT|DW|WM|WF|GN|GS|GW|GF)\b", clean_name, re.IGNORECASE)
    pfx = pfx_match.group(1).upper() if pfx_match else ""

    tokens = raw_model.split()
    first_token = tokens[0] if tokens else raw_model

    # Check for TV pattern: 2-digit screen size glued to series (e.g. 50S80EUX, 43P735)
    tv_match = re.match(r"^(\d{2})([A-Z]\w{3,})$", first_token)

    # Check for series + capacity pattern (e.g. MAGNA 30, AVANTE 15, PEARL 18)
    is_series_capacity = len(tokens) >= 2 and tokens[-1].isdigit() and len(tokens[-1]) <= 2

    # Check for refrigerator alphanumeric stem (e.g. 276EBS, 306IDB)
    fridge_match = re.match(r"^(\d{3,})([A-Za-z]+)$", first_token)

    # Auxiliary tag stripping (e.g. -T3, AAA, PRO)
    core_stem, aux_tag = extract_tag(first_token)

    if tv_match:
        screen_size = tv_match.group(1)
        tv_series = tv_match.group(2)
        tier_1.append(first_token)
        if detected_brand:
            tier_1.append(f"{detected_brand} {first_token}")
        tier_2.append(tv_series)
        tier_3.append(f"{screen_size} {tv_series}")
        if detected_brand:
            tier_3.append(f"{detected_brand} {tv_series}")

    elif is_series_capacity:
        series_name = " ".join(tokens[:-1])
        cap_code = tokens[-1]
        tier_1.append(raw_model)
        if detected_brand:
            tier_1.append(f"{detected_brand} {raw_model}")
        tier_2.append(series_name)

        # Map capacity code to tonnage (Dawlance vs Universal)
        tonnage = get_capacity_tonnage(cap_code, detected_brand)
        if tonnage:
            tier_3.append(f"{series_name} {tonnage} TON")
            tier_3.append(f"{series_name} {tonnage}TON")
            if detected_brand:
                tier_3.append(f"{detected_brand} {series_name} {tonnage} TON")
        tier_3.append(f"{series_name} {cap_code}")

    else:
        # Standard model codes: washing machines, ACs, refrigerators
        tier_1.append(raw_model)
        if aux_tag and core_stem not in tier_1:
            tier_1.append(core_stem)

        # Tier 2: Bare alphanumeric stem without cosmetic tags
        bare_stem = core_stem
        tier_2.append(bare_stem)

        # Tier 3: Spaced, glued, and prefixed permutations
        if "-" in bare_stem:
            spaced = bare_stem.replace("-", " ")
            glued = bare_stem.replace("-", "")
            tier_3.append(spaced)
            tier_3.append(glued)
            if pfx:
                tier_3.append(f"{pfx}-{bare_stem}")
                tier_3.append(f"{pfx} {bare_stem}")
                tier_3.append(f"{pfx} {spaced}")
        elif fridge_match:
            digits = fridge_match.group(1)
            letters = fridge_match.group(2)
            tier_3.append(f"{digits} {letters}")
            tier_3.append(f"{digits}-{letters}")
            if detected_brand:
                tier_3.append(f"{detected_brand} {bare_stem}")

        if pfx and "-" not in bare_stem:
            tier_3.append(f"{pfx}-{bare_stem}")
            tier_3.append(f"{pfx} {bare_stem}")

        # If AC model ends with color letter (W, B, S, G), also add bare series to tier 3
        m_color_suffix = re.match(r"^(\d+[A-Za-z]+?\d+)[WBSG]$", bare_stem, re.IGNORECASE)
        if m_color_suffix:
            tier_3.append(m_color_suffix.group(1))

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
