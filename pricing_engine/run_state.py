"""Validated run generations and conservative content-based reconciliation.

The legacy checkpoint API remains available; new runs use its namespaced paths
and compatible completed/pending fields, with additional validated provenance.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pricing_engine.ingestion import extract_product_name
from pricing_engine.models import SNO_ALIASES_LOWER
from pricing_engine.run_lock import canonical_path
from pricing_engine.state_io import atomic_json, digest, file_digest, json_value

STATE_VERSION = 1


def comparable_row(row: dict[str, Any]) -> dict[str, Any]:
    """Compare all supplied columns except serials using existing scalar semantics."""
    values: dict[str, Any] = {}
    labels = Counter(key.strip() for key in row)
    for key, value in row.items():
        label = key.strip()
        if label.lower() in SNO_ALIASES_LOWER or label.lower().startswith("unnamed:"):
            continue
        if not label:
            continue
        if labels[label] > 1:
            # Distinct legacy headers must not collapse into one comparable value.
            label = key
        plain = json_value(value)
        values[label] = plain.strip() if isinstance(plain, str) else plain
    return values


@dataclass
class RowComparison:
    """Current positions and safely attributable differences; never product IDs."""

    reuse: dict[int, int] = field(default_factory=dict)
    to_run: list[int] = field(default_factory=list)
    changed: dict[int, list[str]] = field(default_factory=dict)
    unmatched: list[int] = field(default_factory=list)
    previous_only: list[int] = field(default_factory=list)
    uncertain: list[int] = field(default_factory=list)
    pending: list[int] = field(default_factory=list)


def reconcile_rows(
    current: list[dict[str, Any]], previous: list[dict[str, Any]], completed: set[int],
) -> RowComparison:
    """Reuse unique equal content; attribute edits only to unique full Brand+Name."""
    result = RowComparison()
    now = [comparable_row(row) for row in current]
    old = [comparable_row(row) for row in previous]
    now_content: dict[str, list[int]] = defaultdict(list)
    old_content: dict[str, list[int]] = defaultdict(list)
    now_names: dict[tuple[Any, Any], list[int]] = defaultdict(list)
    old_names: dict[tuple[Any, Any], list[int]] = defaultdict(list)
    for rows, content, names in ((now, now_content, now_names), (old, old_content, old_names)):
        for idx, row in enumerate(rows):
            content[digest(row)].append(idx)
            names[(row.get("Brand"), extract_product_name(row))].append(idx)
    matched_old: set[int] = set()
    for idx, row in enumerate(now):
        key = digest(row)
        candidates = old_content.get(key, [])
        if len(now_content[key]) == 1 and len(candidates) == 1:
            prev_idx = candidates[0]
            matched_old.add(prev_idx)
            if prev_idx in completed:
                result.reuse[idx] = prev_idx
                continue
            result.pending.append(idx)
        elif len(now_content[key]) > 1 or len(candidates) > 1:
            result.uncertain.append(idx)
        else:
            name = (row.get("Brand"), extract_product_name(row))
            name_candidates = old_names.get(name, [])
            if all(name) and len(now_names[name]) == 1 and len(name_candidates) == 1:
                prev_idx = name_candidates[0]
                matched_old.add(prev_idx)
                result.changed[idx] = sorted(
                    col for col in row.keys() | old[prev_idx].keys()
                    if (col in row) != (col in old[prev_idx]) or row.get(col) != old[prev_idx].get(col)
                )
            elif len(now_names[name]) > 1 or len(name_candidates) > 1:
                result.uncertain.append(idx)
            else:
                result.unmatched.append(idx)
        result.to_run.append(idx)
    result.previous_only = [idx for idx in range(len(old)) if idx not in matched_old]
    return result


def _describe_component_diff(
    saved_state: dict[str, Any] | None,
    current_components: Mapping[str, str] | None,
) -> str:
    """Summarize which dependency signature components changed since the saved run."""
    if saved_state is None or current_components is None:
        return ""
    saved_components = saved_state.get("signature_components")
    if not isinstance(saved_components, dict):
        return ""
    changed = sorted(
        key
        for key in saved_components.keys() | current_components.keys()
        if saved_components.get(key) != current_components.get(key)
    )
    if not changed:
        return ""
    preview = ", ".join(changed[:4])
    if len(changed) > 4:
        preview += f", +{len(changed) - 4} more"
    return f"changed: {preview}"


class RunStore:
    """Persist one source/mode's working generation and last resolved snapshot."""

    def __init__(self, source: Path, mode: str, directory: Path) -> None:
        self.source = source
        self.mode = mode
        key = digest([canonical_path(source), mode])[:24]
        self.working_path = directory / f"{source.stem}.{key}.checkpoint.json"
        self.snapshot_path = directory / f"{source.stem}.{key}.snapshot.json"
        self.legacy_path = directory / f"{source.stem}.checkpoint.json"

    @property
    def has_prior_state(self) -> bool:
        """Corrupt and legacy files are evidence of prior state, never first runs."""
        return any(p.exists() for p in (self.working_path, self.snapshot_path, self.legacy_path))

    def _read(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != STATE_VERSION:
            raise ValueError("unsupported state schema")
        integrity = data.pop("integrity", None)
        if integrity != digest(data):
            raise ValueError("state integrity check failed")
        strings = ("catalog_name", "catalog_path", "mode", "signature", "run_id", "input_digest", "manifest_digest", "updated_at")
        if any(not isinstance(data.get(key), str) or not data[key] for key in strings):
            raise ValueError("missing required state metadata")
        if data.get("phase") not in {"processing", "publishing", "completed"}:
            raise ValueError("invalid run phase")
        if type(data.get("parent_generation")) is not int or data["parent_generation"] < 0:
            raise ValueError("invalid parent generation")
        if "parent_run_id" not in data or (
            data["parent_run_id"] is not None and not isinstance(data["parent_run_id"], str)
        ):
            raise ValueError("invalid parent run provenance")
        if (data["parent_run_id"] is None) != (data["parent_generation"] == 0):
            raise ValueError("inconsistent parent provenance")
        if data.get("catalog_path") != canonical_path(self.source) or data.get("mode") != self.mode:
            raise ValueError("state source/mode mismatch")
        inputs = data.get("inputs")
        if not isinstance(inputs, list) or not all(isinstance(row, dict) for row in inputs):
            raise ValueError("invalid input manifest")
        if data.get("manifest_digest") != digest(inputs) or type(data.get("total_items")) is not int or data["total_items"] != len(inputs):
            raise ValueError("input manifest integrity check failed")
        if type(data.get("generation")) is not int or data["generation"] <= data["parent_generation"]:
            raise ValueError("invalid run generation")
        if not isinstance(data.get("run_id"), str) or not data["run_id"]:
            raise ValueError("missing run provenance")
        for name in ("completed_records", "pending_records", "observed_at", "pending_reasons"):
            if not isinstance(data.get(name), dict):
                raise ValueError("invalid row state")
            if any(not key.isdigit() or str(int(key)) != key or int(key) >= len(inputs) for key in data[name]):
                raise ValueError("row state outside input manifest")
        for name in ("completed_records", "pending_records"):
            if any(not isinstance(record, dict) for record in data[name].values()):
                raise ValueError("invalid result record shape")
        if any(not isinstance(value, str) for name in ("observed_at", "pending_reasons") for value in data[name].values()):
            raise ValueError("invalid row observation/reason metadata")
        pending = data.get("pending_indices")
        if not isinstance(pending, list) or any(type(i) is not int or i not in range(len(inputs)) for i in pending) or len(pending) != len(set(pending)):
            raise ValueError("invalid pending indices")
        finished = {int(key) for key in data["completed_records"]}
        if finished & set(pending) or finished | set(pending) != set(range(len(inputs))):
            raise ValueError("inconsistent completion coverage")
        if not finished <= {int(key) for key in data["observed_at"]}:
            raise ValueError("completed rows missing observation metadata")
        if not {int(key) for key in data["pending_records"]} <= set(pending):
            raise ValueError("inconsistent pending records")
        if path == self.snapshot_path and (data["phase"] != "completed" or pending):
            raise ValueError("snapshot is not a resolved completed run")
        if not isinstance(data.get("publication"), dict):
            raise ValueError("invalid publication journal")
        return data

    def select(
        self,
        signature: str,
        *,
        components: Mapping[str, str] | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
        """Reject stale/wrong-parent work before choosing a compatible baseline."""
        loaded: list[dict[str, Any] | None] = []
        issues: list[str] = []
        for path in (self.snapshot_path, self.working_path):
            try:
                loaded.append(self._read(path))
            except (ValueError, TypeError, KeyError, OSError):
                loaded.append(None)
                issues.append(f"{path.name}: invalid or unreadable state")
        completed, working = loaded
        baseline = completed if completed and completed["signature"] == signature and completed.get("reuse_allowed", True) else None
        if working and working["signature"] == signature and working.get("reuse_allowed", True):
            parent_matches = (
                working["parent_run_id"] == (completed["run_id"] if completed else None)
                and working["parent_generation"] == (completed["generation"] if completed else 0)
                and working["generation"] > (completed["generation"] if completed else 0)
            )
            if parent_matches and (completed is not None or not self.snapshot_path.exists()):
                baseline = working
        if baseline:
            return completed, baseline, ""
        if self.has_prior_state:
            diff_note = _describe_component_diff(working or completed, components)
            detail = f" ({diff_note})" if diff_note else ""
            issues.append(f"No compatible validated baseline{detail}; use --rerun full")
        return completed, None, "; ".join(issues)

    def save(self, state: dict[str, Any]) -> None:
        """Write the current attempt without modifying the completed snapshot."""
        state["updated_at"] = datetime.now(UTC).isoformat()
        atomic_json(self.working_path, {**state, "integrity": digest(state)})

    def begin(
        self, inputs: list[dict[str, Any]], signature: str,
        reused: dict[int, tuple[dict[str, Any], str]], completed: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Allocate a generation under the caller's resource locks and save pending work."""
        generation = completed["generation"] if completed else 0
        try:
            previous = self._read(self.working_path)
            generation = max(generation, previous["generation"] if previous else 0)
        except (ValueError, TypeError, KeyError, OSError):
            pass
        clean_inputs = json_value(inputs)
        state: dict[str, Any] = {
            "schema_version": STATE_VERSION, "catalog_name": self.source.name,
            "catalog_path": canonical_path(self.source), "mode": self.mode,
            "catalog_mtime": self.source.stat().st_mtime, "input_digest": file_digest(self.source),
            "inputs": clean_inputs, "manifest_digest": digest(clean_inputs),
            "total_items": len(inputs), "signature": signature, "run_id": uuid4().hex,
            "generation": generation + 1, "parent_run_id": completed["run_id"] if completed else None,
            "parent_generation": completed["generation"] if completed else 0,
            "completed_records": {str(i): json_value(record) for i, (record, _) in reused.items()},
            "pending_records": {}, "pending_reasons": {},
            "pending_indices": [i for i in range(len(inputs)) if i not in reused],
            "row_fingerprints": {str(i): digest(comparable_row(row)) for i, row in enumerate(inputs)},
            "observed_at": {str(i): observed for i, (_, observed) in reused.items()},
            "phase": "processing", "publication": {}, "updated_at": "",
        }
        self.save(state)
        return state

    def record(self, state: dict[str, Any], idx: int, record: dict[str, Any], retry: str) -> None:
        """Persist a worker outcome immediately, keeping retryable results separate."""
        key = str(idx)
        state["observed_at"][key] = datetime.now(UTC).isoformat()
        if retry:
            state["pending_records"][key] = json_value(record)
            state["pending_reasons"][key] = retry
        else:
            state["completed_records"][key] = json_value(record)
            state["pending_indices"].remove(idx)
        self.save(state)

    def promote(self, state: dict[str, Any]) -> None:
        """Commit resolved state; a leftover working file cannot supersede this run."""
        if state["pending_indices"]:
            raise ValueError("Cannot promote a run with pending rows")
        if file_digest(self.source) != state["input_digest"]:
            raise ValueError("Input changed during execution; results retained, publication stopped")
        state["phase"] = "completed"
        atomic_json(self.snapshot_path, {**state, "integrity": digest(state)})
        self.working_path.unlink(missing_ok=True)
