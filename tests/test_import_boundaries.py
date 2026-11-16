"""Shared layers must import in fresh processes without reverse dependencies."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    "module,forbidden",
    [
        (
            "digi_transport",
            {
                "pricing_engine.scraper",
                "pricing_engine.digi_discovery",
                "pricing_engine.offer_processing",
            },
        ),
        ("digi_discovery", {"pricing_engine.scraper"}),
        (
            "offer_processing",
            {
                "pricing_engine.scraper",
                "pricing_engine.digi_discovery",
                "pricing_engine.digi_transport",
            },
        ),
        (
            "matcher",
            {
                "pricing_engine.scraper",
                "pricing_engine.digi_discovery",
                "pricing_engine.digi_transport",
                "pricing_engine.offer_processing",
            },
        ),
    ],
)
def test_lower_layers_have_no_reverse_imports(module: str, forbidden: set[str]) -> None:
    tree = ast.parse((ROOT / "pricing_engine" / f"{module}.py").read_text("utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not (imports & forbidden)


@pytest.mark.parametrize(
    "modules",
    [
        [
            "scraper",
            "digi_discovery",
            "digi_transport",
            "offer_processing",
            "matcher",
            "series_fallback",
        ],
        [
            "digi_transport",
            "series_fallback",
            "matcher",
            "offer_processing",
            "digi_discovery",
            "scraper",
        ],
    ],
)
def test_import_orders_in_fresh_processes(modules: list[str]) -> None:
    code = "import importlib; " + "; ".join(
        f"importlib.import_module('pricing_engine.{name}')" for name in modules
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
