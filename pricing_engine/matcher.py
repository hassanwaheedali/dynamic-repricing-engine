import re

# Category acronyms and fractions to safeguard from expansion
SAFEGUARD_PATTERN = re.compile(
    r"\b(?:W/M|D/F|A/C|H/C|H&C)\b"
    r"|\bHeat\s*/\s*Cool\b"
    r"|\b\d+/\d+\s*(?:\"|inch|mm)\b"
    r"|\b\d+W/\d+D\b",
    re.IGNORECASE,
)

TAG_PATTERN = re.compile(r"[-_\s]*(?:T3|AAA|AA\+|AA|PRO|ULTRA|PLUS)+$", re.IGNORECASE)

# Standard category and capacity phrases to strip from search queries
CATEGORY_PATTERNS = re.compile(
    r"\b(?:AUTO\s+W/M|FRONT\s+LOAD\s+W/M|W/M|M/OVEN|M/O|D/F|R/F|W/D|SPLIT\s+AC|SPLIT|CASSETTE|FLOOR\s+STANDING|DISHWASHER)\b"
    r"|\b(?:AIR\s+CURTAIN|AIR\s+COOLER|AIR\s+FRYER|WATER\s+HEATER|WATER\s+DISPENSER|WATER\s+PURIFIER|INSECT\s+KILLER|JUG\s+KETTLE|HOT\s+PLATE|CHOPPER|BLENDER|IRON|LED|MICROWAVE|OVEN|SANDWICH\s+MAKER)\b"
    r"|\b(?:INVERTER|NORMAL|SERIES|DIGITAL|GLASS\s+DOOR|CLEAR\s+LID|SMART|4K|FHD|HD|GAS\+ELECTRIC|BUILT-IN)\b"
    r"|\b(?:\d+(?:\.\d+)?\s*(?:TON|ΤΟN|KG|GM|LTR|LITRE|SETS|SETS?|FEET|FT|INCH|MM|CM|\"|\'))\b",
    re.IGNORECASE,
)

# Common non-SKU unit stop-tokens
NON_SKU_TOKENS = {
    "TON", "ΤΟN", "KG", "GM", "LTR", "SET", "SETS", "FEET", "FT", "MM", "CM", "INCH",
    "AC", "AND", "WITH", "THE", "FOR", "TOP", "LID", "DOOR", "AIR", "CURTAIN",
    "BLENDER", "CHOPPER", "OVEN", "HEATER", "WASHER", "PURIFIER", "KETTLE", "SMART",
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
            if re.search(r"\d", t_clean) and not is_dimension_or_spec_token(t_clean) and re.match(r"^[A-Za-z0-9\-_]+$", t_clean):
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


def is_strict_model_match(scraped_title: str, target_model: str) -> bool:
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

    return False
