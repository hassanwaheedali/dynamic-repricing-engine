"""Recoverable publication with per-file atomic replacement, never a multi-file transaction."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pricing_engine.run_lock import canonical_path
from pricing_engine.state_io import file_digest, json_value


def unique_audit_paths(csv_path: Path, xlsx_path: Path) -> tuple[Path, Path]:
    """Keep earlier audit generations when two locked runs share a timestamp."""
    serial = 0
    candidates = csv_path, xlsx_path
    while any(path.exists() for path in candidates):
        serial += 1
        candidates = (
            csv_path.with_stem(f"{csv_path.stem}_{serial}"),
            xlsx_path.with_stem(f"{xlsx_path.stem}_{serial}"),
        )
    return candidates


def artifact_identity(path: Path) -> list[int]:
    """Identify the exact file last published, including edits with unchanged contents."""
    stat = path.stat()
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]


class Publication:
    """Persist intent before replacing an artifact and acknowledge its actual outcome."""

    def __init__(
        self, run_id: str, journal: dict[str, Any], save: Callable[[], None], *,
        previous: dict[str, Any] | None = None, protected: list[Path] | None = None,
    ) -> None:
        self.run_id, self.journal, self.save = run_id, journal, save
        self.protected = {canonical_path(path) for path in protected or []}
        journal.setdefault("run_id", run_id)
        journal.setdefault("artifacts", {})
        journal.setdefault("owned_artifacts", json_value((previous or {}).get("owned_artifacts", {})))

    @property
    def warnings(self) -> tuple[str, ...]:
        """Expose every failed/retained artifact instead of treating file existence as success."""
        return tuple(
            f"{entry['destination']}: {entry['status']} ({entry.get('error', '')})"
            for entry in self.journal["artifacts"].values()
            if entry["status"] in {"failed", "retained_unverified", "planned", "publishing"}
        )

    def plan(self, destination: Path, *, required: bool, role: str = "output") -> None:
        """Register expected artifacts even if an earlier writer prevents attempting them."""
        key = canonical_path(destination)
        self.journal["artifacts"].setdefault(key, {
            "destination": key, "run_id": self.run_id, "required": required,
            "role": role, "status": "planned",
        })
        self.save()

    def check_required(self) -> None:
        """A valid primary publication cannot mask a missing required winner/CSV artifact."""
        for key, entry in self.journal["artifacts"].items():
            if entry["status"] != "published":
                continue
            path = Path(key)
            try:
                verified = (
                    artifact_identity(path) == entry.get("identity")
                    and file_digest(path) == entry.get("expected_digest")
                )
            except OSError:
                verified = False
            if not verified:
                entry.update(status="failed", error="Published destination is missing or changed")
        self.save()
        missing = [entry["destination"] for entry in self.journal["artifacts"].values()
                   if entry["required"] and entry["status"] != "published"]
        if missing:
            raise OSError("Required publication incomplete: " + ", ".join(missing))

    def write(
        self, destination: Path, writer: Callable[[Path], Any], *,
        required: bool, role: str = "output",
    ) -> None:
        """Stage, flush, journal, and atomically publish one existing writer's output."""
        key = canonical_path(destination)
        if key in self.protected:
            raise ValueError("An output destination aliases the input or run state")
        destination.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {
            "destination": key, "run_id": self.run_id, "required": required,
            "role": role, "status": "preparing", "retained_previous": destination.exists(),
        }
        self.journal["artifacts"][key] = entry
        self.save()
        staged: Path | None = None
        try:
            descriptor, filename = tempfile.mkstemp(
                prefix=f".{destination.stem}.{self.run_id}.", suffix=destination.suffix,
                dir=destination.parent,
            )
            os.close(descriptor)
            staged = Path(filename)
            writer(staged)
            with staged.open("r+b") as stream:
                os.fsync(stream.fileno())
            entry.update(
                status="publishing", expected_digest=file_digest(staged),
                staged_path=str(staged.resolve()), staged_identity=artifact_identity(staged),
            )
            self.save()
            staged.replace(destination)
            entry.update(status="published", identity=artifact_identity(destination))
            self.journal["owned_artifacts"][key] = dict(entry)
            self.save()
        except Exception as exc:
            entry.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            self.save()
            raise
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    def copy(self, source: Path, destination: Path, *, required: bool, role: str = "output") -> None:
        """Copy an audit artifact to a latest destination through the same atomic path."""
        self.write(destination, lambda staged: shutil.copyfile(source, staged), required=required, role=role)

    def recover_pending(self) -> None:
        """Acknowledge a verified replace that happened before journal acknowledgement."""
        for key, entry in self.journal["artifacts"].items():
            if entry["status"] != "publishing":
                continue
            destination = Path(key)
            try:
                verified = (
                    destination.is_file()
                    and artifact_identity(destination) == entry.get("staged_identity")
                    and file_digest(destination) == entry.get("expected_digest")
                )
            except OSError:
                verified = False
            if verified:
                entry.update(status="published", identity=artifact_identity(destination))
                self.journal["owned_artifacts"][key] = dict(entry)
            else:
                entry.update(status="failed", error="Publication interrupted; destination not verified")
        self.save()

    def current_path(self, path: Path | None) -> Path | None:
        """Never advertise a retained older file as a successfully updated artifact."""
        if path is None:
            return None
        entry = self.journal["artifacts"].get(canonical_path(path), {})
        return path if entry.get("status") == "published" else None

    def retire_winners(self, destinations: list[Path]) -> None:
        """Retire only exact, journal-owned winner_latest files; never infer ownership."""
        for destination in destinations:
            key = canonical_path(destination)
            receipt = self.journal["owned_artifacts"].get(key)
            entry = {"destination": key, "run_id": self.run_id, "required": False,
                     "role": "winner_latest", "status": "not_applicable"}
            self.journal["artifacts"][key] = entry
            self.save()
            if not destination.exists():
                continue
            try:
                verified = (
                    not destination.is_symlink() and receipt is not None
                    and destination.stem.endswith("_latest")
                    and receipt.get("role") == "winner_latest" and receipt.get("status") == "published"
                    and artifact_identity(destination) == receipt.get("identity")
                    and file_digest(destination) == receipt.get("expected_digest")
                )
                if verified:
                    destination.unlink()
                    self.journal["owned_artifacts"].pop(key, None)
                else:
                    entry.update(status="retained_unverified", error="No matching ownership/content receipt; file untouched")
            except OSError as exc:
                entry.update(status="failed", error=f"Winner retirement blocked: {exc}")
            self.save()


def write_artifact(
    destination: Path, writer: Callable[[Path], Any], *, publication: Publication | None = None,
    required: bool = True, role: str = "output",
) -> None:
    """Provide atomic writes to existing standalone exporter callers as well."""
    publisher = publication or Publication("standalone", {}, lambda: None)
    publisher.write(destination, writer, required=required, role=role)


def copy_artifact(
    source: Path, destination: Path, *, publication: Publication | None = None,
    required: bool = True, role: str = "output",
) -> None:
    """Preserve existing copy semantics without exposing a partially copied latest file."""
    publisher = publication or Publication("standalone", {}, lambda: None)
    publisher.copy(source, destination, required=required, role=role)
