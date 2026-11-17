"""Audited, non-secret dependency projections for processing and publication."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import config
from pricing_engine.registry import InMemoryRegistry
from pricing_engine.state_io import digest, file_digest

# These components affect publication or optional persistence, not worker results.
_NON_PROCESSING_MODULES = frozenset({"exporter", "publication", "db", "learner", "run_lock"})
_SAFE_HEADERS = frozenset({
    "accept", "accept-language", "accept-encoding", "content-type", "origin", "referer",
    "user-agent", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
    "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site",
})


@dataclass(frozen=True)
class RunSignatures:
    """Only digests and safe component names may be persisted or logged."""

    processing: str
    export: str
    components: dict[str, str]


def build_signatures(mode: str, platform: str, personal_comm_pct: float) -> RunSignatures:
    """Hash explicit business configuration and actual loaded registry contents.

    Source-module hashing deliberately errs toward invalidation when a shared
    module changes. Runtime configuration projections avoid invalidating Alfa
    work for an unrelated Digi commission override, and range for pricing values.
    Unknown authenticated headers disable persisted reuse rather than recording
    credential-derived values or assuming they cannot affect search results.
    """
    package = Path(__file__).parent
    components = {
        f"source:{path.stem}": file_digest(path)
        for path in sorted(package.glob("*.py"))
        if path.stem not in _NON_PROCESSING_MODULES
    }
    components["source:config"] = file_digest(Path(config.__file__))
    components["registry"] = digest(InMemoryRegistry.signature_data())
    components["context"] = digest([mode, platform, personal_comm_pct, "result-payload-v1"])
    components["runtime"] = digest({name: version(name) for name in ("pandas", "curl_cffi")})
    if mode != "range":
        components["pricing"] = digest({name: getattr(config, name) for name in (
            "COMPANY_MIN_PROFIT_PKR", "MONOPOLY_PROFIT_PKR", "FALLBACK_PROFIT_PKR",
            "LARGE_GAP_PROFIT_CAP_PKR", "THIN_BUFFER_THRESHOLD_PKR",
            "COURIER_RATE_PER_KG", "VOLUMETRIC_DIVISOR",
            "DEFAULT_CAPACITY_RULES", "DEFAULT_CATEGORY_SHIPPING",
        )})
    for vendor, descriptor in (("alfa", config.ALFAMALL_CONFIG), ("digi", config.DIGIMALL_CONFIG)):
        if platform not in {"all", vendor}:
            continue
        if any(key.lower() not in _SAFE_HEADERS for key in descriptor.headers):
            raise ValueError("Untracked request headers prevent safe reuse; use --rerun full")
        components[f"network:{vendor}"] = digest({
            "url": descriptor.search_url, "params": descriptor.base_params,
            "public_headers": descriptor.headers,
        })
        if mode != "range":
            components[f"commission:{vendor}"] = digest([
                config.get_vendor_commission_pct(vendor),
                getattr(config, f"{vendor.upper()}_PERSONAL_COMM_PCT") if personal_comm_pct > 0 else 0,
            ])
        if vendor == "digi":
            components["discovery:digi"] = digest([
                config.DIGI_PAGE_SIZE, config.DIGI_MAX_PAGES, config.DIGI_QUERY_BUDGET,
            ])
    export = digest({
        "source": file_digest(package / "exporter.py"),
        "publication": file_digest(package / "publication.py") if (package / "publication.py").exists() else "",
        "runtime": version("openpyxl"), "schema": "export-v1",
    })
    return RunSignatures(digest(components), export, components)
