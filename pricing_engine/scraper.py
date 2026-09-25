import asyncio
import logging
import random

from curl_cffi.requests import AsyncSession
from rich.console import Console

from pricing_engine.matcher import is_strict_model_match
from pricing_engine.models import ScrapedOffer, ScrapeResult

logger = logging.getLogger(__name__)
console = Console(legacy_windows=False)

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

# Run-scoped on-demand cache: (platform, query) -> ScrapeResult
_query_cache: dict[tuple[str, str], ScrapeResult] = {}


def clear_scraper_cache() -> None:
    """Clear all in-memory query search cache entries."""
    _query_cache.clear()


def get_scraper_cache() -> dict[tuple[str, str], ScrapeResult]:
    """Return a read-only copy of current query cache."""
    return dict(_query_cache)


async def scrape_alfamall(
    session: AsyncSession,
    query: str,
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
) -> ScrapeResult:
    """Query AlfaMall storefront search API and extract verified product offers with retries.

    Features:
    - On-demand in-memory caching with strict poisoning guard (only 200 OK + non-empty offers).
    - Modern Chrome 120 headers.
    - Soft 200 OK WAF challenge detection & schema validation for both 'results' and 'data' keys.
    - Fast 10.0s timeout with jittered exponential backoff.
    - Live terminal telemetry badges on retries/stalls.

    Args:
        session: Active curl_cffi AsyncSession with Chrome impersonation.
        query: Search keyword extracted from product catalog name.
        target_model: Target model string for strict variant validation.
        timeout: HTTP request timeout in seconds (default: 10.0s).
        max_retries: Number of retry attempts on network/timeout failure (default: 3).

    Returns:
        ScrapeResult containing verified offers and explicit success/failure flags.
    """
    cache_key = ("alfamall", query.strip().upper())
    if cache_key in _query_cache:
        cached = _query_cache[cache_key]
        return ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name=o.vendor_name,
                    price=o.price,
                    is_sold_out=o.is_sold_out,
                    raw_title=o.raw_title,
                )
                for o in cached.offers
            ],
            is_success=cached.is_success,
            status_code=cached.status_code,
            error_detail=cached.error_detail,
        )

    params = {
        "page": "1",
        "q": query,
        "limit": "18",
        "storefront": "23",
        "storefront_domain": "alfamall.com",
    }
    headers = {
        **COMMON_HEADERS,
        "origin": "https://alfamall.com",
        "referer": "https://alfamall.com/",
    }

    offers: list[ScrapedOffer] = []
    last_status: int | None = None
    last_error: str | None = None

    for attempt in range(max_retries):
        try:
            resp = await session.get(
                ALFA_SEARCH_URL, params=params, headers=headers, timeout=timeout
            )
            last_status = resp.status_code

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception as exc:
                    last_error = f"Invalid JSON / WAF challenge: {exc}"
                    logger.warning("AlfaMall returned non-JSON body on 200 OK for query '%s'", query)
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

                for item in raw_items:
                    title = str(item.get("title", ""))
                    if not is_strict_model_match(title, target_model):
                        continue

                    sold_out = bool(item.get("sold_out", False))
                    variant = item.get("variant_detail", {})
                    price_str = (
                        variant.get("discounted_price") or variant.get("original_price") or "0"
                    )
                    try:
                        price = float(str(price_str).replace(",", "").strip())
                    except ValueError:
                        continue

                    vendor_obj = item.get("vendor") or {}
                    vendor = vendor_obj.get("name") or "Unknown Vendor"

                    if price > 0:
                        offers.append(
                            ScrapedOffer(
                                vendor_name=str(vendor),
                                price=price,
                                is_sold_out=sold_out,
                                raw_title=title,
                            )
                        )

                # Strict Cache Guard: Only cache when response is valid and offers exist
                result = ScrapeResult(
                    offers=offers,
                    is_success=True,
                    status_code=200,
                    error_detail=None,
                )
                if offers:
                    _query_cache[cache_key] = result

                return result

            elif resp.status_code in (429, 500, 502, 503, 504):
                last_error = f"HTTP {resp.status_code} Server/Gateway Error"
                backoff = (0.6 * (2**attempt)) + random.uniform(0.1, 0.3)
                if resp.status_code == 429:
                    console.print(
                        f"  [bold red]⛔ [AlfaMall][/] [dim]{query}[/] "
                        f"WAF Rate-limit (429) hit (Attempt {attempt + 1}/{max_retries}) — Cooling down {backoff:.1f}s..."
                    )
                else:
                    console.print(
                        f"  [bold yellow]⚠️  [AlfaMall][/] [dim]{query}[/] "
                        f"Server error {resp.status_code} (Attempt {attempt + 1}/{max_retries}) — Retrying in {backoff:.1f}s..."
                    )
                await asyncio.sleep(backoff)
            else:
                last_error = f"HTTP {resp.status_code} Unexpected Status"
                logger.warning(
                    "AlfaMall search API returned status %s for query %s", resp.status_code, query
                )
                break
        except Exception as exc:
            last_error = str(exc) or "Network Connection/Timeout Error"
            backoff = (0.5 * (2**attempt)) + random.uniform(0.1, 0.4)
            err_str = str(exc).lower()
            is_socket_drop = any(
                k in err_str for k in ("wsarecv", "connection was aborted", "reset", "closed")
            )

            if is_socket_drop:
                console.print(
                    f"  [bold yellow]⚠️  [AlfaMall][/] [dim]{query}[/] "
                    f"Socket drop/aborted (Attempt {attempt + 1}/{max_retries}) — Auto-recovering in {backoff:.1f}s..."
                )
            else:
                console.print(
                    f"  [bold yellow]⚠️  [AlfaMall][/] [dim]{query}[/] "
                    f"Connection timeout (Attempt {attempt + 1}/{max_retries}) — Retrying in {backoff:.1f}s..."
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    "AlfaMall failed after %d attempts for query '%s': %s",
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


async def scrape_digimall(
    session: AsyncSession,
    query: str,
    target_model: str,
    timeout: float = 10.0,
    max_retries: int = 3,
) -> ScrapeResult:
    """Query DigiMall (Faysal Bank) storefront search API and extract verified product offers.

    Features:
    - On-demand in-memory caching with strict poisoning guard (only 200 OK + non-empty offers).
    - Modern Chrome 120 headers.
    - Soft 200 OK WAF challenge detection & schema validation for both 'results' and 'data' keys.
    - Fast 10.0s timeout with jittered exponential backoff.
    - Live terminal telemetry badges on retries/stalls.

    Args:
        session: Active curl_cffi AsyncSession with Chrome impersonation.
        query: Search keyword extracted from product catalog name.
        target_model: Target model string for strict variant validation.
        timeout: HTTP request timeout in seconds (default: 10.0s).
        max_retries: Number of retry attempts on network/timeout failure (default: 3).

    Returns:
        ScrapeResult containing verified offers and explicit success/failure flags.
    """
    cache_key = ("digimall", query.strip().upper())
    if cache_key in _query_cache:
        cached = _query_cache[cache_key]
        return ScrapeResult(
            offers=[
                ScrapedOffer(
                    vendor_name=o.vendor_name,
                    price=o.price,
                    is_sold_out=o.is_sold_out,
                    raw_title=o.raw_title,
                )
                for o in cached.offers
            ],
            is_success=cached.is_success,
            status_code=cached.status_code,
            error_detail=cached.error_detail,
        )

    params = {
        "storefront": "23",
        "q": query,
        "page": "1",
        "limit": "18",
    }
    headers = {
        **COMMON_HEADERS,
        "origin": "https://digimall.faysalbank.com",
        "referer": "https://digimall.faysalbank.com/",
    }

    offers: list[ScrapedOffer] = []
    last_status: int | None = None
    last_error: str | None = None

    for attempt in range(max_retries):
        try:
            resp = await session.get(
                DIGI_SEARCH_URL, params=params, headers=headers, timeout=timeout
            )
            last_status = resp.status_code

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception as exc:
                    last_error = f"Invalid JSON / WAF challenge: {exc}"
                    logger.warning("DigiMall returned non-JSON body on 200 OK for query '%s'", query)
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

                for item in raw_items:
                    title = str(item.get("title", ""))
                    if not is_strict_model_match(title, target_model):
                        continue

                    sold_out = bool(item.get("sold_out", False))
                    variant = item.get("variant_detail", {})
                    price_str = (
                        variant.get("discounted_price") or variant.get("original_price") or "0"
                    )
                    try:
                        price = float(str(price_str).replace(",", "").strip())
                    except ValueError:
                        continue

                    vendor_obj = item.get("vendor") or {}
                    vendor = vendor_obj.get("name") or "Unknown Vendor"

                    if price > 0:
                        offers.append(
                            ScrapedOffer(
                                vendor_name=str(vendor),
                                price=price,
                                is_sold_out=sold_out,
                                raw_title=title,
                            )
                        )

                # Strict Cache Guard: Only cache when response is valid and offers exist
                result = ScrapeResult(
                    offers=offers,
                    is_success=True,
                    status_code=200,
                    error_detail=None,
                )
                if offers:
                    _query_cache[cache_key] = result

                return result

            elif resp.status_code in (429, 500, 502, 503, 504):
                last_error = f"HTTP {resp.status_code} Server/Gateway Error"
                backoff = (0.6 * (2**attempt)) + random.uniform(0.1, 0.3)
                if resp.status_code == 429:
                    console.print(
                        f"  [bold red]⛔ [DigiMall][/] [dim]{query}[/] "
                        f"WAF Rate-limit (429) hit (Attempt {attempt + 1}/{max_retries}) — Cooling down {backoff:.1f}s..."
                    )
                else:
                    console.print(
                        f"  [bold yellow]⚠️  [DigiMall][/] [dim]{query}[/] "
                        f"Server error {resp.status_code} (Attempt {attempt + 1}/{max_retries}) — Retrying in {backoff:.1f}s..."
                    )
                await asyncio.sleep(backoff)
            else:
                last_error = f"HTTP {resp.status_code} Unexpected Status"
                logger.warning(
                    "DigiMall search API returned status %s for query %s", resp.status_code, query
                )
                break
        except Exception as exc:
            last_error = str(exc) or "Network Connection/Timeout Error"
            backoff = (0.5 * (2**attempt)) + random.uniform(0.1, 0.4)
            err_str = str(exc).lower()
            is_socket_drop = any(
                k in err_str for k in ("wsarecv", "connection was aborted", "reset", "closed")
            )

            if is_socket_drop:
                console.print(
                    f"  [bold yellow]⚠️  [DigiMall][/] [dim]{query}[/] "
                    f"Socket drop/aborted (Attempt {attempt + 1}/{max_retries}) — Auto-recovering in {backoff:.1f}s..."
                )
            else:
                console.print(
                    f"  [bold yellow]⚠️  [DigiMall][/] [dim]{query}[/] "
                    f"Connection timeout (Attempt {attempt + 1}/{max_retries}) — Retrying in {backoff:.1f}s..."
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    "DigiMall failed after %d attempts for query '%s': %s",
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

