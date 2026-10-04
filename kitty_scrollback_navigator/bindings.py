from __future__ import annotations

import json
import re
from pathlib import Path


DEFAULT_BINDINGS = {
    "move_left": "h",
    "move_down": "j",
    "move_up": "k",
    "move_right": "l",
    "word_forward": "w",
    "word_backward": "b",
    "line_start": "0",
    "line_end": "$",
    "page_down": "<C-f>",
    "page_up": "<C-b>",
    "half_page_down": "<C-d>",
    "half_page_up": "<C-u>",
    "search_forward": "/",
    "search_backward": "?",
    "repeat_search": "n",
    "reverse_search": "N",
    "jump_character": "s",
    "jump_line": "S",
    "visual_mode": "v",
    "visual_line_mode": "V",
    "visual_block_mode": "<C-v>",
    "yank_selection": "y",
    "accept": "<Enter>",
    "cancel": "<Esc>",
}

_SPECIAL_KEYS = {
    "Enter", "Esc", "Tab", "Backspace", "Delete", "Up", "Down", "Left",
    "Right", "Home", "End", "PageUp", "PageDown", "Insert", "Space",
}
_MODIFIED_KEY = re.compile(r"<[CAS]-[A-Za-z0-9]>\Z")


class BindingError(ValueError):
    """Invalid or ambiguous user key-binding configuration."""


def load_bindings(source: str) -> dict[str, str]:
    try:
        configured = json.loads(source, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, ValueError) as error:
        raise BindingError(f"invalid binding JSON: {error}") from error
    if not isinstance(configured, dict):
        raise BindingError("binding configuration must be a JSON object")

    expected = set(DEFAULT_BINDINGS)
    unknown = set(configured) - expected
    missing = expected - set(configured)
    if unknown:
        raise BindingError(f"unknown actions: {', '.join(sorted(unknown))}")
    if missing:
        raise BindingError(f"missing actions: {', '.join(sorted(missing))}")

    bindings: dict[str, str] = {}
    for action, key in configured.items():
        if not isinstance(key, str) or not _valid_key(key):
            raise BindingError(f"invalid key for {action}: {key!r}")
        bindings[action] = key

    keys = list(bindings.values())
    if len(keys) != len(set(keys)):
        raise BindingError("a key cannot be assigned to multiple actions")
    return bindings


def action_for_key(key: str, bindings: dict[str, str]) -> str | None:
    for action, configured_key in bindings.items():
        if configured_key == key:
            return action
    return None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate action: {key}")
        result[key] = value
    return result


def _valid_key(key: str) -> bool:
    if len(key) == 1:
        return key.isprintable() and not key.isspace()
    if not (key.startswith("<") and key.endswith(">")):
        return False
    name = key[1:-1]
    return name in _SPECIAL_KEYS or _MODIFIED_KEY.fullmatch(key) is not None

def load_bindings_file(path: str | Path | None = None) -> dict[str, str]:
    config = Path(path) if path is not None else Path.home() / ".config/kitty/scrollback-navigator.json"
    try:
        source = config.read_text(encoding="utf-8")
    except FileNotFoundError:
        return dict(DEFAULT_BINDINGS)
    except OSError as error:
        raise BindingError(f"cannot read binding configuration {config}: {error}") from error
    return load_bindings(source)
