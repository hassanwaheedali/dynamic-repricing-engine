import re

PREFIX_PATTERN = re.compile(r"^(?:GS|GF|GW)[-_]?", re.IGNORECASE)


def extract_search_query_and_model(full_name: str) -> tuple[str, str]:
    """Extract search token and normalized model identifier from a product title.

    Strips brand prefixes (GS-, GF-, GW-) to generate broad yet accurate search queries.

    Args:
        full_name: The full descriptive catalog name of the product.

    Returns:
        Tuple of (clean_search_query, raw_model_code).
    """
    clean_name = full_name.strip()
    match = re.search(
        r"([A-Z0-9]+(?:-[A-Z0-9]+)+|[0-9]{2}[A-Z0-9]+)",
        clean_name,
        re.IGNORECASE,
    )

    if match:
        raw_code = match.group(0).upper()
        clean_code = PREFIX_PATTERN.sub("", raw_code)
        # If model has hyphen (e.g. 12AITH21W-T3), search token is base before hyphen
        parts = clean_code.split("-")
        search_token = parts[0] if parts and len(parts[0]) >= 5 else clean_code
        return search_token, raw_code

    parts = clean_name.split()
    fallback = parts[-1] if parts else clean_name
    return fallback, clean_name


TAG_PATTERN = re.compile(r"[-_\s]*(?:T3|AAA|AA|PRO|ULTRA)+$", re.IGNORECASE)
VARIANT_CLUSTER_PATTERN = re.compile(
    r"\b((?:[A-Za-z]{2}[-_])?[0-9]{2}[A-Za-z]+(?:[0-9]+[-\s_]+)?)\s*"
    r"([A-Za-z0-9]+(?:\s*/\s*[A-Za-z0-9]+)+)\b",
    re.IGNORECASE,
)


def expand_multivariant_titles(title: str) -> str:
    """Dynamically expand slash-separated variant tokens using distributive algebra.

    A single, unified, DRY algorithm that handles any combination of:
    - Colors: GS-12AITH24W/S -> GS-12AITH24W GS-12AITH24S
    - Subseries / Generations: GS-18ZITH1W/2W/3W -> GS-18ZITH1W GS-18ZITH2W GS-18ZITH3W
    - Batches with shared suffix: GS-24PITH15/17G -> GS-24PITH15G GS-24PITH17G
    - Multi-variant batches: GS-24PITH15/16/17/18G -> GS-24PITH15G ... 18G
    - Symmetrical tokens: GS-12PITH14S/11S -> GS-12PITH14S GS-12PITH11S
    Non-model slashes (e.g. 1/2" pipe, 3/6 months, Heat/Cool) are completely untouched.

    Args:
        title: Raw product title string.

    Returns:
        Expanded title string with distinct virtual model tokens.
    """
    def repl(m: re.Match[str]) -> str:
        stem = m.group(1).rstrip()
        raw_variants = m.group(2)

        # Separate attached auxiliary tag if present (e.g., ST3 -> S + T3)
        tag_match = TAG_PATTERN.search(raw_variants)
        trailing_tag = ""
        if tag_match:
            trailing_tag = tag_match.group(0)
            raw_variants = raw_variants[:tag_match.start()]

        parts = [p.strip() for p in re.split(r"\s*/\s*", raw_variants) if p.strip()]
        if len(parts) < 2:
            return m.group(0)

        # 1. Distributive Suffix (e.g., ['15', '17G'] -> distribute 'G' to '15' -> '15G')
        last = parts[-1]
        m_suf = re.search(r"([A-Za-z]+)$", last)
        shared_suffix = m_suf.group(1) if m_suf else ""

        # 2. Distributive Prefix (e.g., ['24W', 'S'] -> distribute '24' to 'S' -> '24S')
        first = parts[0]
        m_pre = re.match(r"^([0-9]+)", first)
        shared_prefix = m_pre.group(1) if m_pre else ""

        expanded: list[str] = []
        for p in parts:
            cur = p
            if shared_suffix and not re.search(r"[A-Za-z]$", cur):
                cur = cur + shared_suffix
            elif shared_prefix and not re.match(r"^[0-9]", cur):
                cur = shared_prefix + cur
            expanded.append(cur)

        tokens = [f"{stem}{x}{trailing_tag}" for x in expanded]
        return " ".join(tokens)

    return VARIANT_CLUSTER_PATTERN.sub(repl, title)


def is_strict_model_match(scraped_title: str, target_model: str) -> bool:
    """Validate that scraped product title strictly matches target model.

    Enforces:
    1. Base target model must be contained in the scraped title.
    2. Guard against color collisions (e.g., target 12AITH21W White strictly
       rejects 12AITH21B Black, 12AITH21S Silver, or 12AITH21G Grey).
    3. Guard against capacity/series mismatch (e.g., 18PITH11W rejects 12PITH11W).

    Args:
        scraped_title: Raw product title returned by marketplace search API.
        target_model: Target model code from our catalog.

    Returns:
        True if product title strictly matches target variant; False otherwise.
    """
    expanded_title = expand_multivariant_titles(scraped_title)
    clean_target = re.sub(r"[^A-Z0-9]", "", PREFIX_PATTERN.sub("", target_model.upper()))
    clean_title = re.sub(r"[^A-Z0-9]", "", expanded_title.upper())

    # Strip auxiliary tags like T3, AAA, AA from base target
    base_target = clean_target.replace("T3", "").replace("AAA", "").replace("AA", "")

    # Check capacity prefix (first 2 digits if numeric, e.g. 12, 18, 24)
    target_cap = base_target[:2] if base_target[:2].isdigit() else ""
    if target_cap:
        # Check if the clean title contains a different capacity with the same series
        series_suffix = base_target[2:6]
        if series_suffix:
            for other_cap in ("12", "18", "24"):
                if other_cap != target_cap and (other_cap + series_suffix) in clean_title:
                    return False

    if base_target in clean_title:
        return True

    # If target is White (ending in 'W'), check if title contains generic base without color code
    if base_target.endswith("W"):
        base_no_color = base_target[:-1]
        if base_no_color in clean_title:
            # Check color collision using word token boundaries on expanded title
            # Matches: 12AITH21B, 12AITH21S, 12AITH21G or explicit "Black", "Silver", "Grey", etc.
            title_upper = expanded_title.upper()
            has_color_collision = bool(
                re.search(rf"\b{base_no_color}[BSGC](?:[-_\s]|T3|\b)", title_upper)
                or (
                    re.search(rf"\b{base_no_color}\b", title_upper)
                    and any(
                        c in title_upper
                        for c in ("BLACK", "SILVER", "GREY", "GOLD", "CHAMPAGNE")
                    )
                )
            )
            if not has_color_collision:
                return True

    return False
