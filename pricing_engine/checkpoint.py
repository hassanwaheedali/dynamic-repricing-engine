"""Checkpoint and Resume Engine for AlfaMall & DigiMall Repricing Pipeline.

Provides atomic persistence of catalog processing state, row fingerprinting
(detecting edits across Brand, Title, Net Price, Profit, and Dimensions),
and in-place sorted row reconstruction.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pricing_engine.models import CheckpointState

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT_DIR = Path("data/.checkpoints")


def compute_row_fingerprint(row: pd.Series | dict[str, Any]) -> str:
    """Compute deterministic cryptographic fingerprint of catalog row inputs.

    Detects any user modifications to Brand, Model Title, Net Purchase Price,
    Target Profit, or Landing Dimensions in the input CSV.
    """
    r_dict = row.to_dict() if isinstance(row, pd.Series) else dict(row)

    brand = str(r_dict.get("Brand") or r_dict.get("brand") or "").strip().upper()
    name = str(
        r_dict.get("Name")
        or r_dict.get("name")
        or r_dict.get("Title")
        or r_dict.get("title")
        or r_dict.get("Model")
        or ""
    ).strip().upper()

    def _to_float(v: Any, default: float = 0.0) -> float:
        if v is None or pd.isna(v):
            return default
        try:
            return float(str(v).replace(",", "").strip())
        except (ValueError, TypeError):
            return default

    net_price = _to_float(r_dict.get("Net Price") or r_dict.get("net_price") or r_dict.get("Cost"), 0.0)
    profit = _to_float(r_dict.get("Profit") or r_dict.get("profit"), 500.0)
    length = _to_float(r_dict.get("Length") or r_dict.get("length"), 0.0)
    width = _to_float(r_dict.get("Width") or r_dict.get("width"), 0.0)
    height = _to_float(r_dict.get("Height") or r_dict.get("height"), 0.0)

    raw_signature = f"{brand}|{name}|{net_price:.2f}|{profit:.2f}|{length:.2f}|{width:.2f}|{height:.2f}"
    return hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()[:16]


def get_checkpoint_dir(base_dir: Path = DEFAULT_CHECKPOINT_DIR) -> Path:
    """Ensure and return the checkpoint directory."""
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_checkpoint_path(catalog_path: Path, checkpoint_dir: Path | None = None) -> Path:
    """Get standard checkpoint JSON path for a given catalog file."""
    c_dir = get_checkpoint_dir(checkpoint_dir or DEFAULT_CHECKPOINT_DIR)
    return c_dir / f"{catalog_path.stem}.checkpoint.json"


def save_checkpoint(
    catalog_path: Path,
    state: CheckpointState,
    checkpoint_dir: Path | None = None,
) -> Path:
    """Atomically write checkpoint state to disk to prevent corrupt partial writes."""
    c_path = get_checkpoint_path(catalog_path, checkpoint_dir)
    state.updated_at = datetime.now(UTC).isoformat()

    # Convert state to dict, ensuring keys are integer strings for JSON
    raw_data = asdict(state)
    # Ensure completed_records, row_fingerprints, pending_reasons have string keys in JSON
    raw_data["completed_records"] = {str(k): v for k, v in state.completed_records.items()}
    raw_data["row_fingerprints"] = {str(k): v for k, v in state.row_fingerprints.items()}
    raw_data["pending_reasons"] = {str(k): v for k, v in state.pending_reasons.items()}

    tmp_path = c_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False)
    tmp_path.replace(c_path)
    return c_path


def load_checkpoint(
    catalog_path: Path,
    checkpoint_dir: Path | None = None,
) -> CheckpointState | None:
    """Load and parse checkpoint state if valid file exists on disk."""
    c_path = get_checkpoint_path(catalog_path, checkpoint_dir)
    if not c_path.is_file():
        return None

    try:
        with open(c_path, encoding="utf-8") as f:
            data = json.load(f)

        completed_records: dict[int, dict[str, Any]] = {
            int(k): v for k, v in data.get("completed_records", {}).items()
        }
        row_fingerprints: dict[int, str] = {
            int(k): v for k, v in data.get("row_fingerprints", {}).items()
        }
        pending_reasons: dict[int, str] = {
            int(k): v for k, v in data.get("pending_reasons", {}).items()
        }

        return CheckpointState(
            catalog_name=str(data.get("catalog_name", catalog_path.name)),
            catalog_path=str(data.get("catalog_path", str(catalog_path))),
            catalog_mtime=float(data.get("catalog_mtime", 0.0)),
            total_items=int(data.get("total_items", 0)),
            completed_records=completed_records,
            row_fingerprints=row_fingerprints,
            pending_indices=[int(i) for i in data.get("pending_indices", [])],
            pending_reasons=pending_reasons,
            updated_at=str(data.get("updated_at", "")),
        )
    except Exception as exc:
        logger.warning("Failed to load checkpoint from %s: %s", c_path, exc)
        return None


def delete_checkpoint(
    catalog_path: Path,
    checkpoint_dir: Path | None = None,
) -> bool:
    """Safely delete checkpoint file upon 100% completion."""
    c_path = get_checkpoint_path(catalog_path, checkpoint_dir)
    if c_path.is_file():
        try:
            c_path.unlink()
            return True
        except OSError as exc:
            logger.warning("Could not delete completed checkpoint %s: %s", c_path, exc)
    return False


def detect_dirty_or_pending_rows(
    df: pd.DataFrame,
    state: CheckpointState,
) -> tuple[list[int], dict[int, dict[str, Any]]]:
    """Inspect current catalog dataframe against loaded checkpoint state.

    Compares the row fingerprint of every row in `df`.
    - Unchanged & previously completed rows -> instantly loaded from cache (0 network calls).
    - Rows with changed Brand, Title, or Net Price OR previously pending/skipped -> marked for execution.

    Returns:
        (rows_needing_execution, cached_completed_records)
    """
    rows_to_run: list[int] = []
    cached_records: dict[int, dict[str, Any]] = {}

    for idx, row in df.iterrows():
        i = int(idx)
        current_fp = compute_row_fingerprint(row)
        saved_fp = state.row_fingerprints.get(i)

        is_completed = i in state.completed_records and i not in state.pending_indices
        is_fingerprint_match = saved_fp is not None and saved_fp == current_fp

        if is_completed and is_fingerprint_match:
            cached_records[i] = state.completed_records[i]
        else:
            rows_to_run.append(i)

    return rows_to_run, cached_records


def merge_records_in_order(
    cached_records: dict[int, dict[str, Any]],
    newly_resolved_records: dict[int, dict[str, Any]],
    total_items: int,
) -> list[dict[str, Any]]:
    """Deterministically merge cached and newly resolved records in exact original 0..N-1 row order."""
    combined: list[dict[str, Any]] = []
    all_merged = {**cached_records, **newly_resolved_records}

    for idx in range(total_items):
        if idx in all_merged:
            combined.append(all_merged[idx])
        else:
            logger.warning("Row index %d missing during checkpoint merge", idx)

    return combined
