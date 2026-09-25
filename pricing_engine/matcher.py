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


def expand_multivariant_titles(title: str) -> str:
    """Expand slash-separated color variants and batch series into distinct virtual model tokens.

    Handles:
    - Color slashes: GS-12AITH24W/S, GS-12AITH24-W/S, GS-12AITH24W/S-T3
      -> GS-12AITH24W-T3 12AITH24S-T3
    - Batch series slashes: GS-12PITH14S /11S or GS-12PITH14S/11S
      -> GS-12PITH14S 12PITH11S

    Args:
        title: Raw product title string.

    Returns:
        Expanded title string with distinct virtual model tokens.
    """
    # 1. Color slash expansion (W/S, S/W, W/B, W/G, W/C with optional hyphen, space, and trailing suffix)
    p_color = (
        r"\b([0-9]{2}[A-Z0-9]+?)[-\s]*([WBSGC])\s*/\s*([WBSGC])"
        r"((?:[-_\s]*T3|[-_\s]+[A-Z0-9]+)?)\b"
    )

    def repl_color(m: re.Match[str]) -> str:
        base = m.group(1)
        c1 = m.group(2)
        c2 = m.group(3)
        suffix = m.group(4) or ""
        return f"{base}{c1}{suffix} {base}{c2}{suffix}"

    title = re.sub(p_color, repl_color, title, flags=re.IGNORECASE)

    # 2. Pular shared color batch slash (e.g. GS-24PITH15/17G - T3, GS-24PITH15/16/17/18G)
    p_batch_shared = (
        r"\b([0-9]{2}PITH)[-\s]*((?:\d{2}\s*/\s*)+\d{2})\s*([WBSGC])"
        r"((?:[-_\s]*T3|[-_\s]+[A-Z0-9]+)?)\b"
    )

    def repl_batch_shared(m: re.Match[str]) -> str:
        base = m.group(1)
        raw_nums = m.group(2)
        color = m.group(3)
        suffix = m.group(4) or ""
        nums = [n.strip() for n in re.split(r"\s*/\s*", raw_nums) if n.strip()]
        return " ".join(f"{base}{n}{color}{suffix}" for n in nums)

    title = re.sub(p_batch_shared, repl_batch_shared, title, flags=re.IGNORECASE)

    # 3. Pular individual color batch slash (e.g. GS-12PITH14S / 11S)
    p_series = (
        r"\b([0-9]{2}PITH)[-\s]*(\d{2})[-\s]*([WBSGC])\s*/\s*(\d{2})[-\s]*([WBSGC])"
        r"((?:[-_\s]*T3|[-_\s]+[A-Z0-9]+)?)\b"
    )

    def repl_series(m: re.Match[str]) -> str:
        base = m.group(1)
        b1 = m.group(2)
        c1 = m.group(3)
        b2 = m.group(4)
        c2 = m.group(5)
        suffix = m.group(6) or ""
        return f"{base}{b1}{c1}{suffix} {base}{b2}{c2}{suffix}"

    title = re.sub(p_series, repl_series, title, flags=re.IGNORECASE)
    return title


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
