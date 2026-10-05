from __future__ import annotations

import re

from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from .model import ScrollbackModel


class SearchState:
    """Directional literal search and repeat state for a scrollback model."""

    def __init__(self, model: ScrollbackModel) -> None:
        self.model = model
        self.query: str | None = None
        self.case_sensitive = True
        self.matches: tuple[tuple[int, int], ...] = ()
        self.current_match: tuple[int, int] | None = None

    def search(
        self,
        query: str,
        direction: str,
        *,
        case_sensitive: bool = False,
    ) -> bool:
        if direction not in ("forward", "backward"):
            raise ValueError(f"unsupported search direction: {direction}")
        if not query:
            return False
        self.query = query
        self.case_sensitive = case_sensitive
        self.matches = self.match_positions(query, case_sensitive=case_sensitive)
        self.current_match = None
        return self._find_from((self.model.row, self.model.column), direction)

    def match_positions(
        self,
        query: str,
        *,
        case_sensitive: bool = False,
        rows: range | None = None,
    ) -> tuple[tuple[int, int], ...]:
        if not query:
            return ()
        pattern = (
            None if case_sensitive else re.compile(re.escape(query), re.IGNORECASE)
        )
        positions = []
        row_indices = range(len(self.model.lines)) if rows is None else rows
        for row in row_indices:
            if not 0 <= row < len(self.model.lines):
                continue
            line = self.model.lines[row]
            start = 0
            while start <= len(line) - len(query):
                if pattern is None:
                    column = line.find(query, start)
                else:
                    match = pattern.search(line, start)
                    column = match.start() if match else -1
                if column < 0:
                    break
                positions.append((row, column))
                start = column + 1
        return tuple(positions)

    def repeat(self, direction: str) -> bool:
        if direction not in ("forward", "backward"):
            raise ValueError(f"unsupported search direction: {direction}")
        if self.query is None:
            return False
        return self._find_from((self.model.row, self.model.column), direction)

    def _find_from(self, origin: tuple[int, int], direction: str) -> bool:
        if not self.matches:
            return False
        if direction == "forward":
            index = bisect_right(self.matches, origin)
            target = (
                self.matches[index] if index < len(self.matches) else self.matches[0]
            )
        else:
            index = bisect_left(self.matches, origin) - 1
            target = self.matches[index] if index >= 0 else self.matches[-1]
        self.current_match = target
        self.model.row, self.model.column = target
        return True


@dataclass(frozen=True)
class JumpTarget:
    row: int
    column: int
    label: str


class JumpSession:
    """Build uniquely labeled targets and apply a selected target locally."""

    _LABELS = "asdfghjklqwertyuiopzxcvbnm"

    def __init__(self, model: ScrollbackModel) -> None:
        self.model = model
        self._targets: dict[str, JumpTarget] = {}

    def character_targets(
        self, character: str, rows: range
    ) -> tuple[JumpTarget, ...]:
        if len(character) != 1:
            raise ValueError("character target must be exactly one character")
        folded_character = character.casefold()
        positions = (
            (row, column)
            for row in rows
            if 0 <= row < len(self.model.lines)
            for column, value in enumerate(self.model.lines[row])
            if value.casefold() == folded_character
        )
        self._targets = self._labeled_targets(positions)
        return tuple(self._targets.values())

    def line_targets(self, rows: range) -> tuple[JumpTarget, ...]:
        positions = (
            (row, 0)
            for row in rows
            if 0 <= row <= self.model.last_nonblank_row
        )
        self._targets = self._labeled_targets(positions)
        return tuple(self._targets.values())

    def input_label(self, label_input: str) -> str:
        """Select labels case-insensitively or report whether more input is needed."""
        label_input = label_input.casefold()
        if label_input in self._targets:
            self.select(label_input)
            return "selected"
        if label_input and any(
            label.startswith(label_input) for label in self._targets
        ):
            return "pending"
        return "invalid"

    def select(self, label: str) -> bool:
        target = self._targets.get(label)
        if target is None:
            return False
        self.model.row, self.model.column = target.row, target.column
        return True

    def _labeled_targets(self, positions) -> dict[str, JumpTarget]:
        positions = tuple(positions)
        width = 1
        capacity = len(self._LABELS)
        while capacity < len(positions):
            width += 1
            capacity *= len(self._LABELS)
        targets = {}
        for index, (row, column) in enumerate(positions):
            label = self._label(index, width)
            targets[label] = JumpTarget(row, column, label)
        return targets

    def _label(self, index: int, width: int) -> str:
        digits = [self._LABELS[0]] * width
        for position in range(width - 1, -1, -1):
            index, remainder = divmod(index, len(self._LABELS))
            digits[position] = self._LABELS[remainder]
        return "".join(digits)
