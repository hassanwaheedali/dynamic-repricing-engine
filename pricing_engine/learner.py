import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

INVALID_METRIC_UNITS: set[str] = {
    "KG",
    "TON",
    "\u03a4\u039fN",  # Intentional Greek Tau/Omicron homoglyph defense against copy-pasted titles
    "LTR",
    "LITRE",
    "LITER",
    "CFT",
    "CUFT",
    "INCH",
    "FT",
    "FEET",
    "MM",
    "CM",
    "GM",
    "TAP",
    "TAPS",
    "BTU",
    "WATT",
    "WATTS",
    "VOLT",
    "VOLTS",
    "AMP",
    "AMPS",
}


def is_valid_residual_token(token: str) -> bool:
    """Validate that a token is a legitimate cosmetic/feature modifier and not a number or metric.

    Enforces Reviewer Guard 2:
    - Digits are strictly forbidden (numbers belong to anchors, capacities, or specs).
    - Minimum length >= 2 to reject single-letter noise.
    - Standard metric unit tokens are explicitly rejected.
    """
    clean = token.strip("-_., \"'")
    if len(clean) < 2:
        return False

    # Residuals can NEVER contain numbers (prevents anchor and metric leakage)
    if any(char.isdigit() for char in clean):
        return False

    return clean.upper() not in INVALID_METRIC_UNITS


def normalize_merchant_name(name: str) -> str:
    """Normalize vendor name into an invariant lowercase alphanumeric ID.

    Enforces Reviewer Guard 3:
    Prevents Sybil attacks and duplicate listings from acting as multiple distinct vendors.
    """
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def is_valid_synonym_candidate(target_res: str, cand_res: str) -> bool:
    """Evaluate if a target/candidate residual pair represents a viable synonym candidate.

    Enforces Reviewer Guard 6:
    - Symmetric Non-Empty Guard: Both sides must be non-empty and valid tokens.
    - Ratio Guard: Prevents mapping a 1-token acronym to 4+ words of marketing fluff.
    """
    if not is_valid_residual_token(target_res) or not is_valid_residual_token(cand_res):
        return False

    t_words = target_res.split()
    c_words = cand_res.split()

    return not (len(c_words) > 3 * len(t_words) or len(t_words) > 3 * len(c_words))


class AutonomousLearner:
    """Autonomous market observation accumulator and consensus promotion miner.

    Adheres to ADR-003 and Reviewer Guards 1, 2, 3, 4, 6:
    - In-Memory Observation Buffer (prevents N+1 REST API flooding).
    - Category-bounded polysemy isolation.
    - Sybil-resistant distinct merchant consensus gate (>= 3 distinct normalized vendors).
    """

    def __init__(self) -> None:
        self._buffer: list[dict[str, Any]] = []

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

    def clear_buffer(self) -> None:
        self._buffer.clear()

    def buffer_observation(
        self,
        brand: str,
        category: str,
        anchor_model: str,
        target_residual: str,
        candidate_residual: str,
        vendor_name: str,
        raw_title: str,
    ) -> bool:
        """Validate and append an observed market difference to the in-memory batch buffer.

        Returns:
            True if observation was valid and buffered, False otherwise.
        """
        # Reviewer Guard 1: Category MUST NOT be empty
        clean_category = category.strip().upper()
        if not clean_category:
            return False

        clean_brand = brand.strip().upper()
        if not clean_brand:
            return False

        # Reviewer Guards 2 & 6: Validate tokens and symmetric ratio
        if not is_valid_synonym_candidate(target_residual, candidate_residual):
            return False

        # Reviewer Guard 3: Normalize merchant for Sybil defense
        norm_merchant = normalize_merchant_name(vendor_name)
        if not norm_merchant:
            return False

        observation = {
            "brand": clean_brand,
            "category": clean_category,
            "anchor_model": anchor_model.strip().upper(),
            "target_residual": target_residual.strip().upper(),
            "candidate_residual": candidate_residual.strip().upper(),
            "vendor_name": vendor_name.strip(),
            "normalized_merchant": norm_merchant,
            "raw_title": raw_title.strip(),
        }
        self._buffer.append(observation)
        return True

    async def flush_observations(self, client: Any) -> int:
        """Bulk flush all buffered observations to Supabase in a single batch POST.

        Enforces Reviewer Guard 4 (N+1 REST flooding prevention).
        """
        if not self._buffer or not client:
            return 0

        to_flush = list(self._buffer)
        try:
            recorded: int = int(await client.record_observations_batch(to_flush) or 0)
            self.clear_buffer()
            return recorded
        except Exception as exc:
            logger.warning("Flush observations failed gracefully: %s", exc)
            return 0

    @staticmethod
    def count_distinct_merchants(observations: list[dict[str, Any]]) -> int:
        """Count unique normalized merchants from an observation collection."""
        merchants: set[str] = set()
        for obs in observations:
            norm = obs.get("normalized_merchant")
            if not norm and obs.get("vendor_name"):
                norm = normalize_merchant_name(obs["vendor_name"])
            if norm:
                merchants.add(norm)
        return len(merchants)

    @staticmethod
    def is_consensus_reached(distinct_merchants: int, threshold: int = 3) -> bool:
        """Determine if observation has achieved multi-seller promotion consensus."""
        return distinct_merchants >= threshold
