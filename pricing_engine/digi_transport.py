"""Bounded, page-addressable raw HTTP retrieval for DigiMall only."""

import asyncio
import copy
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from curl_cffi.requests import AsyncSession

from pricing_engine.digi_discovery import DIGI_MAX_PAGES, DIGI_PAGE_SIZE, normalize_query

if TYPE_CHECKING:
    from pricing_engine.scraper import PlatformConfig

PageKey = tuple[str, str, tuple[tuple[str, str], ...]]


@dataclass(frozen=True, slots=True)
class DigiPage:
    """Validated raw response; contains no target-dependent match decisions."""

    number: int
    items: list[dict[str, Any]] = field(default_factory=list)
    total: int | None = None
    success: bool = False
    status_code: int | None = None
    error: str = ""


def parse_total(payload: dict[str, Any]) -> int | None:
    """Read the first present count field; do not turn invalid counts into zero."""
    for key in ("count", "total", "total_count"):
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
            return int(value.strip())
        return None
    return None


def required_pages(total: int | None) -> tuple[int, ...]:
    """Return the complete bounded page budget, independent of matching/floors."""
    count = (
        DIGI_MAX_PAGES
        if total is None
        else min(DIGI_MAX_PAGES, max(1, (total + DIGI_PAGE_SIZE - 1) // DIGI_PAGE_SIZE))
    )
    return tuple(range(1, count + 1))


def retry_delay(attempt: int, error: str, status: int | None) -> float:
    """Use the existing scraper's timeout/socket/server backoff schedules."""
    low = error.lower()
    if status in (429, 500, 502, 503, 504):
        return 0.6 * 2.0**attempt + random.uniform(0.1, 0.3)
    if any(word in low for word in ("28", "timed out", "timeout")):
        return random.uniform(3.5, 5.0) + attempt * 1.5
    if any(word in low for word in ("wsarecv", "connection was aborted", "reset", "closed")):
        return 0.8 * 2.0**attempt + random.uniform(0.2, 0.5)
    return 0.5 * 2.0**attempt + random.uniform(0.1, 0.4)


class DigiDiscoveryContext:
    """One run's request budget, validated page cache and shared in-flight work."""

    def __init__(self, concurrency: int = 3) -> None:
        if concurrency < 1:
            raise ValueError("DigiMall concurrency must be positive")
        self.semaphore = asyncio.Semaphore(concurrency)
        self.cache: dict[PageKey, DigiPage] = {}
        self.inflight: dict[PageKey, asyncio.Task[DigiPage]] = {}
        self.waiters: dict[PageKey, int] = {}

    @staticmethod
    def _key(config: "PlatformConfig", query: str, page: int) -> PageKey:
        params = {**config.base_params, "q": normalize_query(query), "page": str(page)}
        return config.platform_name, config.search_url, tuple(sorted(params.items()))

    def discard(self, config: "PlatformConfig", query: str, page: int) -> None:
        """Invalidate a schema-valid page whose pagination metadata proved inconsistent."""
        self.cache.pop(self._key(config, query, page), None)

    async def fetch(
        self,
        config: "PlatformConfig",
        session: AsyncSession[Any],
        query: str,
        page: int,
        timeout: float,
        max_retries: int,
    ) -> DigiPage:
        """Share only raw page requests and return isolated payloads to callers."""
        params = {**config.base_params, "q": query, "page": str(page)}
        key = self._key(config, query, page)
        if key in self.cache:
            return copy.deepcopy(self.cache[key])
        task = self.inflight.get(key)
        if task is None:
            task = asyncio.create_task(
                self._request(config, session, params, page, timeout, max_retries)
            )
            self.inflight[key] = task
        self.waiters[key] = self.waiters.get(key, 0) + 1
        try:
            result = await asyncio.shield(task)
            if result.success:
                self.cache[key] = result
            return copy.deepcopy(result)
        finally:
            self.waiters[key] -= 1
            if self.waiters[key] == 0:
                self.waiters.pop(key)
                self.inflight.pop(key, None)
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

    async def _request(
        self,
        config: "PlatformConfig",
        session: AsyncSession[Any],
        params: dict[str, str],
        page: int,
        timeout: float,
        max_retries: int,
    ) -> DigiPage:
        status: int | None = None
        error = "No request attempts configured"
        for attempt in range(max_retries):
            retryable = True
            try:
                async with self.semaphore:
                    response = await session.get(
                        config.search_url,
                        params=params,
                        headers=config.headers,
                        timeout=timeout + attempt * 5.0,
                    )
                status = response.status_code
                if status != 200:
                    error = f"HTTP {status}"
                    retryable = status in (429, 500, 502, 503, 504)
                else:
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise ValueError("Expected JSON object")
                    items = payload.get("results")
                    if items is None:
                        items = payload.get("data")
                    if not isinstance(items, list) or any(
                        not isinstance(item, dict)
                        or not isinstance(item.get("variant_detail", {}), dict)
                        or not isinstance(item.get("vendor") or {}, dict)
                        for item in items
                    ):
                        raise ValueError("Invalid results/data array or listing schema")
                    return DigiPage(page, items, parse_total(payload), True, status)
            except Exception as exc:
                error = str(exc) or type(exc).__name__
            if not retryable:
                break
            if attempt + 1 < max_retries:
                delay = retry_delay(attempt, error, status)
                from pricing_engine.scraper import _safe_console_print

                _safe_console_print(
                    f"[yellow][DigiMall] Page {page}: {error}. "
                    f"Retry {attempt + 2}/{max_retries} in {delay:.1f}s...[/]"
                )
                await asyncio.sleep(delay)
        from pricing_engine.scraper import _safe_console_print

        _safe_console_print(
            f"[yellow][DigiMall] Page {page}: {error}. Page retrieval failed; see search coverage summary.[/]"
        )
        return DigiPage(page, status_code=status, error=f"Page {page}: {error}")
