"""Shared run selection and recovery lifecycle; product workers stay in their pipelines."""

from __future__ import annotations

import sys
import tempfile
from collections import Counter
from collections.abc import Awaitable
from pathlib import Path
from secrets import token_bytes
from typing import Any, Literal
from uuid import uuid4

from rich.console import Console
from rich.markup import escape

from pricing_engine import checkpoint
from pricing_engine.models import SNO_ALIASES_LOWER, ProductInput
from pricing_engine.publication import Publication
from pricing_engine.run_lock import RunLocks
from pricing_engine.run_signature import build_signatures, private_request_digest
from pricing_engine.run_state import RowComparison, RunStore, comparable_row, reconcile_rows
from pricing_engine.state_io import digest, file_digest, json_value

RerunMode = Literal["targeted", "full"]


def retry_reason(record: dict[str, Any], platform: str) -> str:
    """Retry existing failed/incomplete/review statuses without changing evaluation policy."""
    reasons: list[str] = []
    for vendor in ("Alfa", "Digi"):
        if platform not in {"all", vendor.lower()}:
            continue
        alert = str(record.get(f"{vendor} Risk Alert", ""))
        if alert in {"SERVER_DOWN", "INCOMPLETE_DISCOVERY", "AMBIGUOUS_VARIANT"}:
            reasons.append(f"{vendor}: {alert}")
        if record.get(f"{vendor} Discovery Coverage") in {"FAILED", "INCOMPLETE", "UNKNOWN"}:
            reasons.append(f"{vendor}: incomplete discovery")
    return "; ".join(reasons)


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
            # Different CWDs/checkouts must contend for the same absolute resources.
            lock_dir=Path(tempfile.gettempdir()) / "pricing-engine-resource-locks-v1",
        )
        self.console = Console(legacy_windows=False)
        self.state: dict[str, Any] | None = None
        self.baseline: dict[str, Any] | None = None
        self.cached: dict[int, dict[str, Any]] = {}
        self.comparison = RowComparison()
        self.source_digest = ""
        self.export_signature = ""
        self.publication: Publication | None = None
        self._request_key = token_bytes(32)
        self._request_digest = ""
        self._input_content_changed = False

    def prepare(self, products: list[ProductInput]) -> None:
        """Choose work before initializing any search/discovery requests."""
        inputs = [json_value(product.raw_row) for product in products]
        signatures = build_signatures(self.mode, self.platform, self.personal_comm_pct)
        signature = signatures.processing
        self.export_signature = signatures.export
        components = signatures.components
        self._request_digest = private_request_digest(self.platform, self._request_key)
        completed, baseline, issue = self.store.select(signature, components=components)
        if not signatures.reusable:
            baseline = None
            issue = "Untracked request headers prevent persisted reuse; use --rerun full"
            self.console.print(issue)
        self.baseline = baseline
        previous = baseline["inputs"] if baseline else []
        finished = {int(key) for key in baseline["completed_records"]} if baseline else set()
        self.comparison = reconcile_rows(inputs, previous, finished)
        self._input_content_changed = (
            Counter(digest(comparable_row(row)) for row in inputs)
            != Counter(digest(comparable_row(row)) for row in previous)
        )
        if baseline is not None and self._should_show_comparison():
            self._show_comparison(baseline)
        choice = self._resolve_rerun_choice(baseline, issue)
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
        self.state["reuse_allowed"] = signatures.reusable
        self.state["export_signature"] = self.export_signature
        # Ownership receipts remain useful even after dependency invalidation.
        self.state["previous_publication"] = (baseline or completed or {}).get("publication", {})
        self.store.save(self.state)
        self.console.print(
            f"{choice or 'full'} run: {len(self.comparison.to_run)} row(s) to process, "
            f"{len(self.cached)} validated row(s) reused."
        )

    def _has_detected_work(self) -> bool:
        """Return whether reconciliation found modified, new, removed, or pending rows."""
        return self._input_content_changed or bool(self.baseline and self.baseline["pending_indices"])

    def _is_interactive_auto_mode(self) -> bool:
        """Return whether execution is running interactively without an explicit --rerun flag."""
        return self.rerun is None and sys.stdin.isatty()

    def _should_show_comparison(self) -> bool:
        """Show change summary when verbose or when prompting an interactive rerun."""
        if self.verbose:
            return True
        return self._is_interactive_auto_mode() and self._has_detected_work()

    def _can_prompt_for_rerun(self, baseline: dict[str, Any] | None) -> bool:
        """Prompt only when a compatible baseline exists and changes or pending work were found."""
        if baseline is None:
            return False
        return self._is_interactive_auto_mode() and self._has_detected_work()

    def _resolve_rerun_choice(self, baseline: dict[str, Any] | None, issue: str) -> RerunMode:
        """Select targeted or full execution without prompting when no targeted choice applies."""
        if self.rerun == "targeted":
            return self._resolve_explicit_targeted(baseline, issue)
        if self.rerun is not None:
            return self.rerun
        if self._can_prompt_for_rerun(baseline):
            if issue:
                self.console.print(escape(issue))
            return self._prompt(compatible=True)
        self._announce_automatic_full_run(baseline, issue)
        return "full"

    def _resolve_explicit_targeted(self, baseline: dict[str, Any] | None, issue: str) -> RerunMode:
        """Handle explicit --rerun targeted requests safely when no compatible baseline exists."""
        if baseline is not None:
            return "targeted"
        if not self.store.has_prior_state:
            self.console.print("First run: no reusable baseline; processing all rows.")
            return "targeted"
        if not sys.stdin.isatty():
            raise ValueError(issue or "No compatible state; use --rerun full")
        self.console.print(escape(issue))
        return self._prompt(compatible=False)

    def _announce_automatic_full_run(self, baseline: dict[str, Any] | None, issue: str) -> None:
        """Explain why an automatic full run was chosen without prompting."""
        if baseline is not None:
            message = (
                "No input changes or pending rows detected; running full."
                if sys.stdin.isatty()
                else "Non-interactive execution: full run (use --rerun targeted to reuse)."
            )
            self.console.print(message)
            return
        if not issue:
            return
        if self.store.working_path.exists() or self.store.snapshot_path.exists():
            self.console.print(escape(f"{issue}; running full."))

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
            saved_key = key if key in record else saved_by_label.get(key.strip())
            if saved_key is not None:
                old_value = record[saved_key]
                original = old_input.get(key, old_by_label.get(key.strip()))
                refreshed[key] = value if old_value == original else old_value
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
        current = build_signatures(self.mode, self.platform, self.personal_comm_pct)
        compatible = (
            current.processing == self.state["signature"]
            and private_request_digest(self.platform, self._request_key) == self._request_digest
        )
        if not compatible:
            # Retain evidence, but never reuse rows evaluated under a mixed context.
            self.state["signature"] = f"invalidated-{uuid4().hex}"
            self.store.save(self.state)
            raise ValueError("Processing dependencies changed during execution; publication stopped")
        self.state["phase"] = "publishing"
        previous = self.state.pop("previous_publication", {})
        if previous:
            prior = Publication(previous.get("run_id", ""), previous, lambda: None)
            prior.recover_pending()
        self.publication = Publication(
            self.state["run_id"], self.state["publication"], lambda: self.store.save(self.state or {}),
            previous=previous,
            protected=[self.source, self.store.working_path, self.store.snapshot_path, self.store.legacy_path],
        )
        self.store.save(self.state)

    def finish(self) -> None:
        """Publish only fully resolved generations; unresolved work remains resumable."""
        if self.publication is not None:
            self.publication.check_required()
            for warning in self.publication.warnings:
                self.console.print(escape(f"Publication warning: {warning}"))
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
        try:
            if args[0] is not None and self.state is not None:
                self.console.print(escape(f"Run incomplete; recovery state: {self.store.working_path}"))
                if self.publication is not None:
                    self.console.print("Publication may be partial; files are replaced individually.")
                    for warning in self.publication.warnings:
                        self.console.print(escape(warning))
        finally:
            self.locks.__exit__(*args)
