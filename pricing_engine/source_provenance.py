"""Immutable implementation provenance captured before business modules load."""

from __future__ import annotations

from pathlib import Path

from pricing_engine.state_io import file_digest

# Publication and optional persistence do not determine unformatted worker results.
_NON_PROCESSING_MODULES = frozenset({"exporter", "publication", "db", "learner", "run_lock"})


def implementation_sources() -> dict[str, str]:
    """Capture all loaded implementation provenance, including optional exporters."""
    package = Path(__file__).parent
    sources = {
        f"source:{path.stem}": file_digest(path)
        for path in sorted(package.glob("*.py"))
    }
    sources["source:config"] = file_digest(package.parent / "config.py")
    return sources


IMPORTED_SOURCES = tuple(implementation_sources().items())


def processing_sources() -> dict[str, str]:
    """Verify loaded provenance, then project processing-only dependency hashes."""
    sources = implementation_sources()
    if tuple(sources.items()) != IMPORTED_SOURCES:
        raise RuntimeError("Engine source changed after import; restart the process before running")
    return {key: value for key, value in sources.items() if key.removeprefix("source:") not in _NON_PROCESSING_MODULES}
