"""Dependency signatures are stable, bounded, and free of secret payloads."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError

import pytest

import config
from pricing_engine.registry import InMemoryRegistry
from pricing_engine.run_signature import build_signatures


def test_configuration_invalidates_only_relevant_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    before = build_signatures("reprice", "alfa", 0)
    monkeypatch.setattr(config, "DIGI_COMMISSION_PCT", config.DIGI_COMMISSION_PCT + 1)
    assert build_signatures("reprice", "alfa", 0).processing == before.processing
    monkeypatch.setattr(config, "COURIER_RATE_PER_KG", config.COURIER_RATE_PER_KG + 1)
    assert build_signatures("reprice", "alfa", 0).processing != before.processing


def test_registry_order_is_stable_and_values_invalidate(monkeypatch: pytest.MonkeyPatch) -> None:
    InMemoryRegistry._ensure_initialized()
    original = dict(InMemoryRegistry._capacity_cache)
    before = build_signatures("range", "all", 0)
    monkeypatch.setattr(InMemoryRegistry, "_capacity_cache", dict(reversed(list(original.items()))))
    assert build_signatures("range", "all", 0).processing == before.processing
    InMemoryRegistry._capacity_cache[("SYNTHETIC", "999")] = "9"
    assert build_signatures("range", "all", 0).processing != before.processing


def test_environment_secrets_are_neither_persisted_nor_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    before = build_signatures("reprice", "digi", 0)
    secret = "secret-runtime-value-never-store"
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", secret)
    after = build_signatures("reprice", "digi", 0)
    assert before == after
    assert secret not in json.dumps(after.components)


def test_personal_commission_selector_invalidates(monkeypatch: pytest.MonkeyPatch) -> None:
    requested = config.DEFAULT_PERSONAL_COMM_PCT
    before = build_signatures("reprice", "alfa", requested)
    monkeypatch.setattr(config, "DEFAULT_PERSONAL_COMM_PCT", requested + 1)
    assert build_signatures("reprice", "alfa", requested).processing != before.processing


def test_missing_excel_runtime_does_not_disable_processing(monkeypatch: pytest.MonkeyPatch) -> None:
    from pricing_engine import run_signature
    original = run_signature.version

    def optional_missing(name: str) -> str:
        if name == "openpyxl":
            raise PackageNotFoundError(name)
        return original(name)

    before = build_signatures("range", "all", 0)
    monkeypatch.setattr(run_signature, "version", optional_missing)
    after = build_signatures("range", "all", 0)
    assert after.processing == before.processing
    assert after.export != before.export


def test_changed_disk_source_requires_process_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    from pricing_engine import source_provenance
    original = source_provenance.file_digest

    def changed(path: object) -> str:
        from pathlib import Path
        return "changed-on-disk" if Path(path).name == "matcher.py" else original(path)

    monkeypatch.setattr(source_provenance, "file_digest", changed)
    with pytest.raises(RuntimeError, match="restart"):
        build_signatures("reprice", "alfa", 0)


def test_changed_loaded_export_source_requires_process_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    from pricing_engine import source_provenance
    original = source_provenance.file_digest

    def changed(path: object) -> str:
        from pathlib import Path
        return "new-export-code" if Path(path).name == "exporter.py" else original(path)

    monkeypatch.setattr(source_provenance, "file_digest", changed)
    with pytest.raises(RuntimeError, match="restart"):
        build_signatures("reprice", "alfa", 0)
