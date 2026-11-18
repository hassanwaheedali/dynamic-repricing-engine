"""Per-file publication, crash acknowledgement, and verified winner retirement."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pricing_engine.publication import Publication
from pricing_engine.run_lock import canonical_path


def test_partial_publication_is_journaled_and_old_file_is_preserved(tmp_path: Path) -> None:
    journal: dict = {}
    publication = Publication("run", journal, lambda: None)
    first, locked = tmp_path / "output.csv", tmp_path / "output.xlsx"
    locked.write_text("older")
    publication.write(first, lambda stage: stage.write_text("current"), required=True)
    original_replace = Path.replace

    def replace(path: Path, destination: Path) -> Path:
        if destination == locked:
            raise PermissionError("locked by Excel")
        return original_replace(path, destination)

    with patch.object(Path, "replace", replace), pytest.raises(PermissionError):
        publication.write(locked, lambda stage: stage.write_text("new"), required=False)
    assert first.read_text() == "current"
    assert locked.read_text() == "older"
    assert journal["artifacts"][canonical_path(first)]["status"] == "published"
    assert journal["artifacts"][canonical_path(locked)]["status"] == "failed"


def test_zero_winners_retire_only_verified_current_files(tmp_path: Path) -> None:
    previous: dict = {}
    old = Publication("previous", previous, lambda: None)
    verified = tmp_path / "winner_latest.csv"
    modified = tmp_path / "winner_latest.xlsx"
    historical = tmp_path / "winner_20260101_010101.csv"
    unverified = tmp_path / "other_latest.csv"
    for path in (verified, modified):
        old.write(path, lambda stage: stage.write_text("old"), required=False, role="winner_latest")
    historical.write_text("history")
    unverified.write_text("unowned")
    modified.write_text("user's edited workbook")
    current: dict = {}
    publication = Publication("current", current, lambda: None, previous=previous)
    publication.retire_winners([verified, modified, historical, unverified])
    assert not verified.exists()
    assert modified.read_text() == "user's edited workbook"
    assert historical.read_text() == "history"
    assert unverified.read_text() == "unowned"
    assert current["artifacts"][canonical_path(modified)]["status"] == "retained_unverified"


def test_failed_optional_artifact_is_not_reported_as_published(tmp_path: Path) -> None:
    journal: dict = {}
    publication = Publication("run", journal, lambda: None)

    def failed_writer(stage: Path) -> None:
        stage.write_text("partial")
        raise OSError("writer failed")

    destination = tmp_path / "optional.xlsx"
    with pytest.raises(OSError):
        publication.write(destination, failed_writer, required=False)
    assert not destination.exists()
    assert publication.warnings


def test_recover_replace_before_acknowledgement(tmp_path: Path) -> None:
    journal: dict = {}
    durable: dict = {}

    def save() -> None:
        import copy
        durable.clear()
        durable.update(copy.deepcopy(journal))

    publication = Publication("run", journal, save)
    destination = tmp_path / "out.csv"
    publication.write(destination, lambda stage: stage.write_text("expected"), required=True)
    entry = durable["artifacts"][canonical_path(destination)]
    entry["status"] = "publishing"
    entry.pop("identity", None)
    recovered = Publication("run", durable, lambda: None)
    recovered.recover_pending()
    assert durable["artifacts"][canonical_path(destination)]["status"] == "published"


def test_pending_intent_cannot_adopt_identical_unowned_file(tmp_path: Path) -> None:
    import copy
    journal: dict = {}
    durable: dict = {}
    destination = tmp_path / "winner_latest.csv"
    destination.write_text("same bytes")

    def crash_before_replace() -> None:
        durable.clear()
        durable.update(copy.deepcopy(journal))
        if any(entry["status"] == "publishing" for entry in journal["artifacts"].values()):
            raise KeyboardInterrupt

    publication = Publication("interrupted", journal, crash_before_replace)
    with pytest.raises(KeyboardInterrupt):
        publication.write(destination, lambda stage: stage.write_text("same bytes"), required=True, role="winner_latest")
    recovered = Publication("interrupted", durable, lambda: None)
    recovered.recover_pending()
    recovered.retire_winners([destination])
    assert destination.read_text() == "same bytes"


def test_required_outputs_are_verified_at_completion(tmp_path: Path) -> None:
    publication = Publication("run", {}, lambda: None)
    destination = tmp_path / "required.csv"
    publication.write(destination, lambda stage: stage.write_text("published"), required=True)
    destination.unlink()
    with pytest.raises(OSError, match="incomplete"):
        publication.check_required()


def test_range_audit_history_survives_timestamp_collision(tmp_path: Path) -> None:
    from datetime import datetime

    import pandas as pd

    from pricing_engine.exporter import export_range_results

    frame = pd.DataFrame({"S.NO": [1], "Name": ["Synthetic"], "Minimum Price Alfa": [100]})
    options = {"output_dir": tmp_path, "timestamp": datetime(2026, 1, 1), "render_panel": False}
    first = export_range_results(frame, "catalog.csv", **options)
    original = first.csv_path.read_bytes()
    frame["Minimum Price Alfa"] = [200]
    second = export_range_results(frame, "catalog.csv", **options)
    assert first.csv_path != second.csv_path
    assert first.csv_path.read_bytes() == original
    assert second.csv_latest.read_bytes() == second.csv_path.read_bytes()


def test_unreadable_optional_recovery_does_not_abort_primary_publication(tmp_path: Path) -> None:
    journal: dict = {}
    publication = Publication("run", journal, lambda: None)
    optional = tmp_path / "optional.xlsx"
    publication.write(optional, lambda stage: stage.write_text("workbook"), required=False)
    journal["artifacts"][canonical_path(optional)]["status"] = "publishing"
    with patch("pricing_engine.publication.file_digest", side_effect=PermissionError("locked")):
        publication.recover_pending()
    primary = tmp_path / "primary.csv"
    publication.write(primary, lambda stage: stage.write_text("complete"), required=True)
    publication.check_required()
    assert primary.read_text() == "complete"
    assert publication.warnings
