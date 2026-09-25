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
    clean_target = re.sub(r"[^A-Z0-9]", "", PREFIX_PATTERN.sub("", target_model.upper()))
    clean_title = re.sub(r"[^A-Z0-9]", "", scraped_title.upper())

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
            # Check color collision using word token boundaries on original title
            # Matches: 12AITH21B, 12AITH21S, 12AITH21G or explicit "Black", "Silver", "Grey"
            title_upper = scraped_title.upper()
            has_color_collision = bool(
                re.search(rf"\b{base_no_color}[BSG](?:[-_\s]|\b)", title_upper)
                or (
                    re.search(rf"\b{base_no_color}\b", title_upper)
                    and any(c in title_upper for c in ("BLACK", "SILVER", "GREY"))
                )
            )
            if not has_color_collision:
                return True

    return False
