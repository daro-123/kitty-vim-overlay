from __future__ import annotations

import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

OVERLAY_PANEL_ID_VAR = "kitty_vim_overlay_panel_id"


def overlay_panel_id(
    window_id: int, user_vars: dict[str, str] | None = None
) -> int:
    """Return the original source panel ID carried through nested overlays."""
    inherited_id = (user_vars or {}).get(OVERLAY_PANEL_ID_VAR)
    return int(inherited_id) if inherited_id else window_id



@contextmanager
def overlay_panel_lock(
    kitty_pid: int,
    window_id: int,
    runtime_directory: str | os.PathLike[str] | None = None,
) -> Iterator[bool]:
    """Acquire a non-blocking lock so only one overlay runs per Kitty panel."""
    directory = Path(
        runtime_directory
        or os.environ.get("XDG_RUNTIME_DIR")
        or tempfile.gettempdir()
    )
    lock_path = directory / f"kitty-vim-overlay-{kitty_pid}-{window_id}.lock"
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
