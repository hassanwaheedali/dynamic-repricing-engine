import logging
import os
from pathlib import Path
from typing import Any

from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Zero-dependency loader for .env file in workspace root."""
    env_file = Path(".env")
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    k = key.strip()
                    v = val.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


class SupabaseClient:
    """Async connectionless REST client for Supabase Cloud PostgreSQL.

    Adheres to ADR-003:
    - High-speed REST operations (PostgREST).
    - Batch observation ingestion (N+1 protection).
    - Graceful offline degradation when credentials are missing or network fails.
    """

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        _load_env_file()
        if url is None:
            self.url = (
                os.getenv("SUPABASE_URL")
                or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
                or ""
            ).rstrip("/")
        else:
            self.url = url.rstrip("/")

        if key is None:
            self.key = (
                os.getenv("SUPABASE_KEY")
                or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                or os.getenv("SUPABASE_ANON_KEY")
                or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
                or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
                or ""
            )
        else:
            self.key = key

        self.timeout = timeout
        self._session: AsyncSession[Any] | None = None

    @property
    def is_configured(self) -> bool:
        """Return True if legitimate Supabase URL and Key are set."""
        return bool(
            self.url
            and self.key
            and self.url.startswith("http")
            and "placeholder" not in self.url.lower()
        )

    def _ensure_session(self) -> AsyncSession[Any]:
        if self._session is None:
            self._session = AsyncSession(impersonate="chrome120")
        return self._session

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    async def fetch_approved_capacities(self, brand: str = "") -> list[dict[str, Any]]:
        """Fetch all approved brand capacity codes.

        Returns:
            List of dicts containing brand, code, tonnage, status.
        """
        if not self.is_configured:
            return []

        endpoint = f"{self.url}/rest/v1/capacity_registry?select=*&status=eq.APPROVED"
        if brand.strip():
            endpoint += f"&brand=eq.{brand.strip().upper()}"

        session = self._ensure_session()
        try:
            resp = await session.get(endpoint, headers=self._headers(), timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            logger.warning("Supabase fetch capacities returned status %d", resp.status_code)
            return []
        except Exception as exc:
            logger.warning("Supabase capacity fetch failed gracefully: %s", exc)
            return []

    async def fetch_approved_synonyms(
        self, brand: str = "", category: str = ""
    ) -> list[dict[str, Any]]:
        """Fetch approved equivalence synonyms with strict category isolation.

        Returns:
            List of dicts containing brand, category, tag, alias, status.
        """
        if not self.is_configured:
            return []

        endpoint = f"{self.url}/rest/v1/synonym_registry?select=*&status=eq.APPROVED"
        if brand.strip():
            endpoint += f"&brand=eq.{brand.strip().upper()}"
        if category.strip():
            endpoint += f"&category=eq.{category.strip().upper()}"

        session = self._ensure_session()
        try:
            resp = await session.get(endpoint, headers=self._headers(), timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            logger.warning("Supabase fetch synonyms returned status %d", resp.status_code)
            return []
        except Exception as exc:
            logger.warning("Supabase synonym fetch failed gracefully: %s", exc)
            return []

    async def record_observations_batch(self, observations: list[dict[str, Any]]) -> int:
        """Batch insert raw market observations with ignore-duplicates resolution.

        Guarantees:
        - Prevents N+1 HTTP calls by inserting observations in bulk.
        - Idempotent: duplicates ignored via database constraints.

        Args:
            observations: List of observation dictionaries.

        Returns:
            Number of recorded observations.
        """
        if not self.is_configured or not observations:
            return 0

        endpoint = (
            f"{self.url}/rest/v1/learning_observations"
            "?on_conflict=brand,category,anchor_model,target_residual,candidate_residual,normalized_merchant"
        )
        session = self._ensure_session()
        headers = self._headers(prefer="resolution=ignore-duplicates")

        try:
            resp = await session.post(
                endpoint, json=observations, headers=headers, timeout=self.timeout
            )
            if resp.status_code in (200, 201, 204):
                if resp.text and resp.text.strip():
                    try:
                        data = resp.json()
                        return len(data) if isinstance(data, list) else len(observations)
                    except Exception:
                        pass
                return len(observations)
            if resp.status_code == 409:
                # 409 Conflict: Existing market observations safely ignored via database constraint
                logger.debug("Supabase batch observations already present (409 duplicates ignored)")
                return len(observations)
            logger.warning("Supabase batch observation insert returned status %d", resp.status_code)
            return 0
        except Exception as exc:
            logger.warning("Supabase batch observation insert failed gracefully: %s", exc)
            return 0
