from __future__ import annotations

import re


_ANSI_ESCAPE = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))"
)

_SEARCH_MATCH_BACKGROUND = "\x1b[48;2;70;100;140m"
_CURRENT_SEARCH_MATCH_BACKGROUND = "\x1b[48;2;255;193;7m"


def displayed_rows(text: str) -> tuple[str, ...]:
    rows = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if rows and rows[-1] == "":
        rows.pop()
    return tuple(rows) or ("",)


def styled_displayed_rows(text: str) -> tuple[tuple[str, str], ...]:
    """Return searchable plain rows paired with their original ANSI rendering."""
    return tuple((strip_ansi(row), row) for row in displayed_rows(text))


def strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def highlight_ansi_column(text: str, column: int) -> str:
    """Invert one visible character without counting ANSI control sequences."""
    return highlight_ansi_range(text, column, column)


def highlight_ansi_range(text: str, start: int, end: int) -> str:
    """Invert an inclusive visible-character range without counting ANSI sequences."""
    if start < 0 or end < start:
        return text
    result: list[str] = []
    visible_column = 0
    offset = 0
    for match in _ANSI_ESCAPE.finditer(text):
        for character in text[offset : match.start()]:
            if start <= visible_column <= end:
                result.extend(("\x1b[7m", character, "\x1b[27m"))
            else:
                result.append(character)
            visible_column += 1
        result.append(match.group())
        offset = match.end()
    for character in text[offset:]:
        if start <= visible_column <= end:
            result.extend(("\x1b[7m", character, "\x1b[27m"))
        else:
            result.append(character)
        visible_column += 1
    return "".join(result)


def highlight_ansi_matches(
    text: str,
    starts: tuple[int, ...],
    length: int,
    current_start: int | None,
) -> str:
    """Highlight every match and color the active match differently, ANSI-aware."""
    if not starts or length <= 0:
        return text
    ordered_starts = tuple(sorted(starts))
    result: list[str] = []
    visible_column = 0
    offset = 0
    next_match = 0
    for match in _ANSI_ESCAPE.finditer(text):
        for character in text[offset : match.start()]:
            while (
                next_match < len(ordered_starts)
                and ordered_starts[next_match] + length <= visible_column
            ):
                next_match += 1
            active = (
                current_start is not None
                and current_start <= visible_column < current_start + length
            )
            matched = (
                next_match < len(ordered_starts)
                and ordered_starts[next_match] <= visible_column
            )
            if active:
                result.extend(
                    (_CURRENT_SEARCH_MATCH_BACKGROUND, character, "\x1b[49m")
                )
            elif matched:
                result.extend((_SEARCH_MATCH_BACKGROUND, character, "\x1b[49m"))
            else:
                result.append(character)
            visible_column += 1
        result.append(match.group())
        offset = match.end()
    for character in text[offset:]:
        while (
            next_match < len(ordered_starts)
            and ordered_starts[next_match] + length <= visible_column
        ):
            next_match += 1
        active = (
            current_start is not None
            and current_start <= visible_column < current_start + length
        )
        matched = (
            next_match < len(ordered_starts)
            and ordered_starts[next_match] <= visible_column
        )
        if active:
            result.extend(
                (_CURRENT_SEARCH_MATCH_BACKGROUND, character, "\x1b[49m")
            )
        elif matched:
            result.extend((_SEARCH_MATCH_BACKGROUND, character, "\x1b[49m"))
        else:
            result.append(character)
        visible_column += 1
    return "".join(result)


def flash_ansi_line(text: str, labels_by_column: dict[int, str]) -> str:
    """Dim a row and show highlighted matches with their jump labels."""
    gray = "\x1b[38;2;160;160;160m"
    highlight = "\x1b[38;2;30;30;30;48;2;255;193;7m"
    result = [gray]
    for column, character in enumerate(strip_ansi(text)):
        label = labels_by_column.get(column)
        if label is None:
            result.append(character)
        else:
            result.extend((highlight, character, f"[{label}]", "\x1b[0m", gray))
    result.append("\x1b[0m")
    return "".join(result)


def clip_ansi(text: str, width: int) -> str:
    """Clip by visible characters while retaining complete ANSI sequences."""
    if width <= 0:
        return ""
    result: list[str] = []
    visible = 0
    offset = 0
    for match in _ANSI_ESCAPE.finditer(text):
        chunk = text[offset : match.start()]
        remaining = width - visible
        if len(chunk) >= remaining:
            result.append(chunk[:remaining])
            result.append("\x1b[0m")
            return "".join(result)
        result.extend((chunk, match.group()))
        visible += len(chunk)
        offset = match.end()
    tail = text[offset:]
    result.append(tail[: width - visible])
    if len(tail) > width - visible:
        result.append("\x1b[0m")
    return "".join(result)


def viewport_start(history: tuple[str, ...], screen: tuple[str, ...]) -> int:
    if len(screen) > len(history):
        raise ValueError("Kitty screen text is longer than its retained history")
    for start in range(len(history) - len(screen), -1, -1):
        if history[start : start + len(screen)] == screen:
            return start
    raise ValueError("Could not align Kitty's visible screen with its retained history")


def viewport_first_row(
    row: int,
    line_count: int,
    visible_rows: int,
    *,
    previous_first: int | None = None,
    previous_visible: int | None = None,
) -> int:
    last_first = max(0, line_count - visible_rows)
    if previous_first is None or previous_visible != visible_rows:
        return max(0, min(row - visible_rows // 2, last_first))

    first = min(max(0, previous_first), last_first)
    if row < first:
        return row
    if row >= first + visible_rows:
        return row - visible_rows + 1
    return first
