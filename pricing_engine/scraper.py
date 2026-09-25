import asyncio
import logging

from curl_cffi.requests import AsyncSession

from pricing_engine.matcher import is_strict_model_match
from pricing_engine.models import ScrapedOffer

logger = logging.getLogger(__name__)

ALFA_SEARCH_URL = "https://be.alfamall.com/storefront/search_products"
DIGI_SEARCH_URL = "https://digimall-be.faysalbank.com/storefront/search_products"

COMMON_HEADERS: dict[str, str] = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
}


async def scrape_alfamall(
    session: AsyncSession,
    query: str,
    target_model: str,
    timeout: float = 25.0,
    max_retries: int = 3,
) -> list[ScrapedOffer]:
    """Query AlfaMall storefront search API and extract verified product offers with retries.

    Args:
        session: Active curl_cffi AsyncSession with Chrome impersonation.
        query: Search keyword extracted from product catalog name.
        target_model: Target model string for strict variant validation.
        timeout: HTTP request timeout in seconds (default: 25.0s).
        max_retries: Number of retry attempts on network/timeout failure (default: 3).

    Returns:
        List of ScrapedOffer instances matching target variant.
    """
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
    for attempt in range(max_retries):
        try:
            resp = await session.get(
                ALFA_SEARCH_URL, params=params, headers=headers, timeout=timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", []):
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
                # Successful response parsed
                return offers
            elif resp.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "AlfaMall returned %s for query '%s' (attempt %d/%d)",
                    resp.status_code,
                    query,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(1.0 * (attempt + 1))
            else:
                logger.warning(
                    "AlfaMall search API returned status %s for query %s", resp.status_code, query
                )
                break
        except Exception as exc:
            logger.warning(
                "AlfaMall query '%s' attempt %d/%d encountered connection/timeout: %s",
                query,
                attempt + 1,
                max_retries,
                exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                logger.error(
                    "AlfaMall failed after %d attempts for query '%s': %s",
                    max_retries,
                    query,
                    exc,
                )

    return offers


async def scrape_digimall(
    session: AsyncSession,
    query: str,
    target_model: str,
    timeout: float = 25.0,
    max_retries: int = 3,
) -> list[ScrapedOffer]:
    """Query DigiMall (Faysal Bank) storefront search API and extract verified product offers.

    Args:
        session: Active curl_cffi AsyncSession with Chrome impersonation.
        query: Search keyword extracted from product catalog name.
        target_model: Target model string for strict variant validation.
        timeout: HTTP request timeout in seconds (default: 25.0s).
        max_retries: Number of retry attempts on network/timeout failure (default: 3).

    Returns:
        List of ScrapedOffer instances matching target variant.
    """
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
    for attempt in range(max_retries):
        try:
            resp = await session.get(
                DIGI_SEARCH_URL, params=params, headers=headers, timeout=timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", []):
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
                return offers
            elif resp.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "DigiMall returned %s for query '%s' (attempt %d/%d)",
                    resp.status_code,
                    query,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(1.0 * (attempt + 1))
            else:
                logger.warning(
                    "DigiMall search API returned status %s for query %s", resp.status_code, query
                )
                break
        except Exception as exc:
            logger.warning(
                "DigiMall query '%s' attempt %d/%d encountered connection/timeout: %s",
                query,
                attempt + 1,
                max_retries,
                exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                logger.error(
                    "DigiMall failed after %d attempts for query '%s': %s",
                    max_retries,
                    query,
                    exc,
                )

    return offers

