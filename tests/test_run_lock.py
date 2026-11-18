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


@pytest.mark.parametrize("shared_input", [True, False])
def test_pipeline_locks_are_shared_across_working_directories(
    tmp_path: Path, shared_input: bool,
) -> None:
    repository = Path(__file__).resolve().parent.parent
    source = tmp_path / "first.csv"
    other = tmp_path / "second.csv"
    for path in (source, other):
        path.write_text("Brand,Name\nSynthetic,ZX-101\n")
    first_cwd, second_cwd = tmp_path / "a", tmp_path / "b"
    first_cwd.mkdir()
    second_cwd.mkdir()
    output = tmp_path / "shared-output"
    script = (
        "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
        "from pricing_engine.run_control import RunExecution; "
        "owner=RunExecution(Path(sys.argv[2]),'reprice',[Path(sys.argv[3])],platform='alfa'); "
        "owner.__enter__(); print('owned',flush=True); sys.stdin.read()"
    )
    first = subprocess.Popen(
        [sys.executable, "-c", script, str(repository), str(source), str(output)],
        cwd=first_cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )
    try:
        assert first.stdout is not None and first.stdout.readline().strip() == "owned"
        second = subprocess.run(
            [sys.executable, "-c", script, str(repository), str(source if shared_input else other),
             str(tmp_path / "different-output" if shared_input else output)],
            cwd=second_cwd, input="", capture_output=True, text=True, timeout=15,
        )
        assert second.returncode != 0 and "Another run owns shared resource" in second.stderr
    finally:
        first.kill()
        first.communicate(timeout=10)
