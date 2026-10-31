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

        # 3. Brand-unknown fallback: check Dawlance first if code is distinctive, then any unique brand code
        if c_u in ("10", "15", "20", "45"):
            return cls._capacity_cache.get(("DAWLANCE", c_u))
        for (cached_brand, cached_code), cached_ton in cls._capacity_cache.items():
            if cached_code == c_u and cached_brand != "UNIVERSAL":
                return cached_ton

        return None

    @classmethod
    def get_capacity_map(cls, brand: str = "") -> dict[str, str]:
        """Return capacity-code -> tonnage mapping for a brand from the single-source RAM cache."""
        cls._ensure_initialized()
        b_u = brand.strip().upper()
        if b_u.startswith("DAW"):
            return {
                code: ton
                for (c_brand, code), ton in cls._capacity_cache.items()
                if c_brand == "DAWLANCE"
            }

        universal_map = {
            code: ton
            for (c_brand, code), ton in cls._capacity_cache.items()
            if c_brand == "UNIVERSAL"
        }
        if b_u:
            brand_overrides = {
                code: ton for (c_brand, code), ton in cls._capacity_cache.items() if c_brand == b_u
            }
            if brand_overrides:
                return {**universal_map, **brand_overrides}
        return universal_map

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
