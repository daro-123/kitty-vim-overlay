from __future__ import annotations


class ScrollbackModel:
    """Local navigation state over Kitty-provided displayed rows."""

    def __init__(
        self,
        lines: tuple[str, ...] | list[str],
        *,
        viewport_height: int,
        row: int = 0,
        column: int = 0,
    ) -> None:
        if viewport_height < 1:
            raise ValueError("viewport_height must be positive")
        if not lines:
            raise ValueError("scrollback must contain at least one displayed row")
        self.lines = tuple(lines)
        self.viewport_height = viewport_height
        self.last_nonblank_row = next(
            (
                row
                for row in range(len(self.lines) - 1, -1, -1)
                if self.lines[row].strip()
            ),
            len(self.lines) - 1,
        )
        self.row = min(max(row, 0), self.last_nonblank_row)
        self.column = self._clamp_column(self.row, column)

    @property
    def page_size(self) -> int:
        return min(self.viewport_height, len(self.lines))

    def move(self, key: str) -> None:
        if key == "h":
            self.column = self._clamp_column(self.row, self.column - 1)
        elif key == "l":
            self.column = self._clamp_column(self.row, self.column + 1)
        elif key == "j":
            self._set_row(self.row + 1)
        elif key == "k":
            self._set_row(self.row - 1)
        elif key == "w":
            self._move_word_forward()
        elif key == "b":
            self._move_word_backward()
        elif key == "0":
            self.column = 0
        elif key == "$":
            self.column = max(0, len(self.lines[self.row]) - 1)
        elif key == "gg":
            self._set_row(0)
        elif key == "GG":
            self._set_row(len(self.lines) - 1)
        elif key == "<C-f>":
            self._set_row(self.row + self.page_size)
        elif key == "<C-b>":
            self._set_row(self.row - self.page_size)
        elif key == "<C-d>":
            self._set_row(self.row + max(1, self.page_size // 2))
        elif key == "<C-u>":
            self._set_row(self.row - max(1, self.page_size // 2))
        else:
            raise ValueError(f"unsupported movement: {key}")

    def selected_text(
        self, first: tuple[int, int], second: tuple[int, int]
    ) -> str:
        """Return inclusive text between two displayed-row positions."""
        start, end = sorted((first, second))
        start_row, start_column = start
        end_row, end_column = end
        if start_row == end_row:
            return self.lines[start_row][start_column : end_column + 1]

        rows = [self.lines[start_row][start_column :]]
        rows.extend(self.lines[start_row + 1 : end_row])
        rows.append(self.lines[end_row][: end_column + 1])
        return "\n".join(rows)

    def selected_lines(self, first_row: int, second_row: int) -> str:
        """Return complete inclusive displayed rows in document order."""
        start, end = sorted((first_row, second_row))
        return "\n".join(self.lines[start : end + 1])

    def selected_block(
        self, first: tuple[int, int], second: tuple[int, int]
    ) -> str:
        """Return an inclusive rectangular selection, padding short rows."""
        start_row, end_row = sorted((first[0], second[0]))
        start_column, end_column = sorted((first[1], second[1]))
        width = end_column - start_column + 1
        return "\n".join(
            self.lines[row][start_column : end_column + 1].ljust(width)
            for row in range(start_row, end_row + 1)
        )

    def _set_row(self, row: int) -> None:
        self.row = min(max(row, 0), self.last_nonblank_row)
        self.column = self._clamp_column(self.row, self.column)

    def _clamp_column(self, row: int, column: int) -> int:
        return min(max(column, 0), max(0, len(self.lines[row]) - 1))

    def _move_word_forward(self) -> None:
        row, column = self.row, self.column
        if self.lines[row] and not self.lines[row][column].isspace():
            column += 1
            while column < len(self.lines[row]) and not self.lines[row][column].isspace():
                column += 1
        while row < len(self.lines):
            while column < len(self.lines[row]):
                if not self.lines[row][column].isspace():
                    self.row, self.column = row, column
                    return
                column += 1
            row += 1
            column = 0

    def _move_word_backward(self) -> None:
        row, column = self.row, self.column
        current_is_word = bool(self.lines[row]) and not self.lines[row][column].isspace()
        if current_is_word and column > 0 and not self.lines[row][column - 1].isspace():
            column -= 1
            while column > 0 and not self.lines[row][column - 1].isspace():
                column -= 1
            self.row, self.column = row, column
            return
        if current_is_word:
            column -= 1
        while row >= 0:
            while column >= 0:
                if not self.lines[row][column].isspace():
                    while column > 0 and not self.lines[row][column - 1].isspace():
                        column -= 1
                    self.row, self.column = row, column
                    return
                column -= 1
            row -= 1
            if row >= 0:
                column = len(self.lines[row]) - 1
