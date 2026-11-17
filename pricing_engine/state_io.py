"""Small durable, atomic file primitives shared by state and publication."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any


def json_value(value: Any) -> Any:
    """Convert catalog scalars to JSON without arbitrary object serialization."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    # Pandas/numpy scalar values expose item(); never serialize object __dict__.
    if type(value).__module__.startswith("numpy") and hasattr(value, "item"):
        return json_value(value.item())
    raise ValueError(f"Unsupported state value type: {type(value).__name__}")


def digest(value: Any) -> str:
    """Hash a canonical JSON representation, preserving meaningful list order."""
    payload = json.dumps(json_value(value), sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    """Hash an artifact or source without retaining its contents."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    """Flush a unique sibling temporary file before replacing known-good state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(json_value(value), stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
