"""Dependency signatures are stable, bounded, and free of secret payloads."""

from __future__ import annotations

import json

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
