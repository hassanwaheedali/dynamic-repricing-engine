"""Nonblocking OS ownership of resources shared by pipeline invocations."""

from __future__ import annotations

import hashlib
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType
from typing import BinaryIO


def canonical_path(path: str | Path) -> str:
    """Resolve aliases and platform casing before identifying a resource."""
    return os.path.normcase(str(Path(path).resolve()))


class RunLocks:
    """Hold byte locks until the owning invocation exits or its process dies.

    Lock files are deliberately never unlinked: removing one could create two
    separately lockable files for the same resource while another process waits.
    """

    def __init__(self, resources: Iterable[Path], *, lock_dir: Path) -> None:
        self.resources = sorted({canonical_path(path) for path in resources})
        self.lock_dir = lock_dir
        self._handles: list[BinaryIO] = []

    def __enter__(self) -> RunLocks:
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        try:
            for resource in self.resources:
                key = hashlib.sha256(resource.encode()).hexdigest()
                handle = (self.lock_dir / f"{key}.lock").open("a+b")
                try:
                    if handle.seek(0, 2) == 0:
                        handle.write(b"\0")
                        handle.flush()
                    handle.seek(0)
                    if sys.platform == "win32":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    handle.close()
                    raise RuntimeError(
                        f"Another run owns shared resource {resource}. Retry after it finishes."
                    ) from exc
                self._handles.append(handle)
        except BaseException:
            self._release()
            raise
        return self

    def _release(self) -> None:
        for handle in reversed(self._handles):
            try:
                handle.seek(0)
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
        self._handles.clear()

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        self._release()
