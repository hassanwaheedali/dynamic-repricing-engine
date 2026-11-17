"""Cross-process ownership of shared input, state, and output resources."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from pricing_engine.run_lock import RunLocks


def test_overlapping_resources_fail_without_releasing_owner(tmp_path: Path) -> None:
    resource = tmp_path / "shared-output"
    with RunLocks([resource], lock_dir=tmp_path / "locks"):
        with (
            pytest.raises(RuntimeError, match="Another run"),
            RunLocks([resource, tmp_path / "other"], lock_dir=tmp_path / "locks"),
        ):
            pytest.fail("overlap acquired")
        with (
            pytest.raises(RuntimeError, match="Another run"),
            RunLocks([resource], lock_dir=tmp_path / "locks"),
        ):
            pytest.fail("owner lost its lock")
    with RunLocks([resource], lock_dir=tmp_path / "locks"):
        pass


def test_locks_release_after_process_termination(tmp_path: Path) -> None:
    script = (
        "import sys; from pathlib import Path; "
        "from pricing_engine.run_lock import RunLocks; "
        "lock = RunLocks([Path(sys.argv[1])], lock_dir=Path(sys.argv[2])); "
        "lock.__enter__(); print('owned', flush=True); sys.stdin.read()"
    )
    resource, locks = tmp_path / "catalog.csv", tmp_path / "locks"
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(resource), str(locks)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "owned"
        with pytest.raises(RuntimeError, match="Another run"), RunLocks([resource], lock_dir=locks):
            pytest.fail("cross-process overlap acquired")
    finally:
        process.kill()
        process.communicate(timeout=10)
    with RunLocks([resource], lock_dir=locks):
        pass
