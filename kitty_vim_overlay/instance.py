from __future__ import annotations

import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def overlay_instance_lock(
    kitty_pid: int, runtime_directory: str | os.PathLike[str] | None = None
) -> Iterator[bool]:
    """Acquire a non-blocking lock so only one Vim overlay runs per Kitty instance."""
    directory = Path(
        runtime_directory
        or os.environ.get("XDG_RUNTIME_DIR")
        or tempfile.gettempdir()
    )
    lock_path = directory / f"kitty-vim-overlay-{kitty_pid}.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    lock_file = os.fdopen(descriptor, "r+")
    acquired = False
    try:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        acquired = True
        yield True
    finally:
        if acquired:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
