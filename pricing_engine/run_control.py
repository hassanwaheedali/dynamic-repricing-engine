"""Shared run selection and recovery lifecycle; product workers stay in their pipelines."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from rich.console import Console
from rich.markup import escape

from pricing_engine import checkpoint
from pricing_engine.models import SNO_ALIASES_LOWER, ProductInput
from pricing_engine.run_lock import RunLocks
from pricing_engine.run_signature import build_signatures
from pricing_engine.run_state import RowComparison, RunStore, reconcile_rows
from pricing_engine.state_io import file_digest, json_value

RerunMode = Literal["targeted", "full"]


def retry_reason(record: dict[str, Any], platform: str) -> str:
    """Retry existing failed/incomplete/review statuses without changing evaluation policy."""
    reasons: list[str] = []
    for vendor in ("Alfa", "Digi"):
        if platform not in {"all", vendor.lower()}:
            continue
        alert = str(record.get(f"{vendor} Risk Alert", ""))
        if alert in {"SERVER_DOWN", "INCOMPLETE_DISCOVERY", "AMBIGUOUS_VARIANT", "CANDIDATES_REJECTED"}:
            reasons.append(f"{vendor}: {alert}")
        if record.get(f"{vendor} Discovery Coverage") in {"FAILED", "INCOMPLETE", "UNKNOWN"}:
            reasons.append(f"{vendor}: incomplete discovery")
    return "; ".join(reasons)


async def gather_workers(tasks: list[asyncio.Task[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Cancel and join siblings before resources and file locks can be released."""
    try:
        return list(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


class RunExecution:
    """One explicitly owned invocation, shared by repricing and market range."""

    def __init__(
        self, source: Path, mode: str, output_dirs: list[Path], *,
        platform: str, personal_comm_pct: float = 0, resume: bool = True,
        rerun: RerunMode | None = None, verbose: bool = True,
    ) -> None:
        if rerun not in {None, "targeted", "full"}:
            raise ValueError("rerun must be 'targeted' or 'full'")
        if not resume and rerun == "targeted":
            raise ValueError("--no-resume/--fresh conflicts with --rerun targeted")
        self.source, self.mode, self.platform = source, mode, platform
        self.personal_comm_pct, self.verbose = personal_comm_pct, verbose
        self.rerun = "full" if not resume else rerun
        self.store = RunStore(source, mode, checkpoint.DEFAULT_CHECKPOINT_DIR)
        self.locks = RunLocks(
            [source, self.store.working_path, self.store.snapshot_path, *output_dirs],
            lock_dir=checkpoint.DEFAULT_CHECKPOINT_DIR / ".locks",
        )
        self.console = Console(legacy_windows=False)
        self.state: dict[str, Any] | None = None
        self.baseline: dict[str, Any] | None = None
        self.cached: dict[int, dict[str, Any]] = {}
        self.comparison = RowComparison()
        self.source_digest = ""
        self.export_signature = ""

    def prepare(self, products: list[ProductInput]) -> None:
        """Choose work before initializing any search/discovery requests."""
        inputs = [json_value(product.raw_row) for product in products]
        try:
            signatures = build_signatures(self.mode, self.platform, self.personal_comm_pct)
            signature = signatures.processing
            self.export_signature = signatures.export
            components = signatures.components
        except ValueError:
            if self.rerun == "targeted":
                raise
            signature, components = uuid4().hex, {}
            self.console.print("Reuse unavailable for current dependencies; processing a full run.")
        completed, baseline, issue = self.store.select(signature)
        self.baseline = baseline
        previous = baseline["inputs"] if baseline else []
        finished = {int(key) for key in baseline["completed_records"]} if baseline else set()
        self.comparison = reconcile_rows(inputs, previous, finished)
        if baseline and (self.verbose or self.rerun is None and sys.stdin.isatty()):
            self._show_comparison(baseline)
        choice = self.rerun
        if choice == "targeted" and baseline is None and self.store.has_prior_state:
            if not sys.stdin.isatty():
                raise ValueError(issue or "No compatible state; use --rerun full")
            self.console.print(escape(issue))
            choice = self._prompt(compatible=False)
        elif choice is None:
            if sys.stdin.isatty() and self.store.has_prior_state:
                if issue:
                    self.console.print(escape(issue))
                choice = self._prompt(compatible=baseline is not None)
            else:
                choice = "full"
                if self.store.has_prior_state:
                    self.console.print("Non-interactive execution: full run (use --rerun targeted to reuse).")
        if baseline is None and not self.store.has_prior_state and choice == "targeted":
            self.console.print("First run: no reusable baseline; processing all rows.")
        reused: dict[int, tuple[dict[str, Any], str]] = {}
        if choice == "targeted" and baseline:
            for idx, old_idx in self.comparison.reuse.items():
                old_record = baseline["completed_records"][str(old_idx)]
                record = self._refresh(old_record, baseline["inputs"][old_idx], products[idx])
                self.cached[idx] = record
                reused[idx] = (record, baseline["observed_at"][str(old_idx)])
        else:
            self.comparison.to_run = list(range(len(products)))
        if file_digest(self.source) != self.source_digest:
            raise ValueError("Input changed while it was being read; rerun the current file")
        self.state = self.store.begin(inputs, signature, reused, completed)
        self.state["signature_components"] = components
        self.state["export_signature"] = self.export_signature
        # Ownership receipts remain useful even after dependency invalidation.
        self.state["previous_publication"] = (baseline or completed or {}).get("publication", {})
        self.store.save(self.state)
        self.console.print(
            f"{choice or 'full'} run: {len(self.comparison.to_run)} row(s) to process, "
            f"{len(self.cached)} validated row(s) reused."
        )

    def _prompt(self, *, compatible: bool) -> RerunMode:
        while True:
            if compatible:
                self.console.print("[1] Targeted Re-run — Changed/New/Pending Rows Only")
            self.console.print("[2] Full Re-run — All Rows")
            try:
                answer = input("Choose re-run mode (q to cancel): ").strip().lower()
            except EOFError as exc:
                raise ValueError("No re-run choice received; use --rerun targeted or --rerun full") from exc
            if answer == "1" and compatible:
                return "targeted"
            if answer == "2":
                return "full"
            if answer in {"q", "quit"}:
                raise ValueError("Re-run cancelled; no processing started")

    def _show_comparison(self, baseline: dict[str, Any]) -> None:
        report = self.comparison
        self.console.print(
            f"Changes: {len(report.changed)} modified, {len(report.unmatched)} new/unmatched, "
            f"{len(report.previous_only)} previous-only, {len(report.uncertain)} uncertain, "
            f"{len(report.pending)} pending; {len(report.reuse)} reusable."
        )
        for idx, columns in report.changed.items():
            self.console.print(escape(f"Row {idx + 1}: {', '.join(columns)}"))
        for label, indices in (("New/unmatched", report.unmatched), ("Uncertain", report.uncertain), ("Pending", report.pending)):
            if indices:
                self.console.print(f"{label} current rows: {', '.join(str(i + 1) for i in indices)}")
        if report.previous_only:
            self.console.print("Previous-only rows (removed or unmatched edits): " + ", ".join(str(i + 1) for i in report.previous_only))
        observed = sorted(set(baseline["observed_at"].values()))
        if observed:
            self.console.print(escape(f"Prior observations: {observed[0]} through {observed[-1]}. Reused rows are not market refreshes."))

    @staticmethod
    def _refresh(record: dict[str, Any], old_input: dict[str, Any], product: ProductInput) -> dict[str, Any]:
        """Apply current display inputs while retaining deliberate resolved-output overrides."""
        refreshed: dict[str, Any] = {"S.NO": product.sno}
        saved_by_label = {key.strip(): key for key in record if key != "S.NO"}
        old_by_label = {key.strip(): value for key, value in old_input.items()}
        consumed: set[str] = set()
        for key, value in product.raw_row.items():
            if key.strip().lower() in SNO_ALIASES_LOWER:
                continue
            saved_key = saved_by_label.get(key.strip())
            if saved_key is not None:
                old_value = record[saved_key]
                refreshed[key] = value if old_value == old_by_label.get(key.strip()) else old_value
                consumed.add(saved_key)
        refreshed.update({key: value for key, value in record.items() if key not in consumed and key != "S.NO"})
        return refreshed

    async def worker(self, idx: int, work: Awaitable[dict[str, Any]]) -> dict[str, Any]:
        """Persist each existing worker's outcome before considering it completed."""
        record = dict(await work)
        record.pop("_original_idx", None)
        if self.state is None:
            raise RuntimeError("Run has not been prepared")
        self.store.record(self.state, idx, record, retry_reason(record, self.platform))
        return record

    def before_publication(self) -> None:
        """Validate coverage and source consistency before any destination is replaced."""
        if self.state is None:
            raise RuntimeError("Run has not been prepared")
        coverage = self.state["completed_records"].keys() | self.state["pending_records"].keys()
        if coverage != {str(i) for i in range(self.state["total_items"])}:
            raise ValueError("Missing worker outcomes; export stopped")
        if file_digest(self.source) != self.source_digest:
            raise ValueError("Input changed during execution; results retained, publication stopped")
        self.state["phase"] = "publishing"
        self.store.save(self.state)

    def finish(self) -> None:
        """Publish only fully resolved generations; unresolved work remains resumable."""
        if self.state is not None and not self.state["pending_indices"]:
            self.store.promote(self.state)

    def __enter__(self) -> RunExecution:
        self.locks.__enter__()
        try:
            self.source_digest = file_digest(self.source)
        except BaseException:
            self.locks.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *args: Any) -> None:
        self.locks.__exit__(*args)
