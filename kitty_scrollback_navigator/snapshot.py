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
    if not text and column == 0:
        return "\x1b[7m \x1b[27m"
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


def flash_ansi_line(
    text: str,
    labels_by_column: dict[int, str],
    *,
    label_offset: int = 1,
) -> str:
    """Dim a row and overlay jump labels without shifting its existing text."""
    gray = "\x1b[38;2;160;160;160m"
    highlight = "\x1b[38;2;30;30;30;48;2;255;193;7m"
    visible = list(strip_ansi(text))
    highlighted_columns: set[int] = set()
    target_columns = set(labels_by_column)
    for column, label in sorted(labels_by_column.items()):
        marker = f"[{label}]"
        overlay_column = column + label_offset
        end = overlay_column + len(marker)
        while any(
            (
                position in target_columns
                and (label_offset != 0 or position != column)
            )
            or position in highlighted_columns
            for position in range(overlay_column, end)
        ):
            overlay_column += 1
            end += 1
        if end > len(visible):
            visible.extend(" " * (end - len(visible)))
        visible[overlay_column:end] = marker
        highlighted_columns.update(range(overlay_column, end))

    result = [gray]
    highlighted = False
    for column, character in enumerate(visible):
        is_highlighted = column in highlighted_columns
        if is_highlighted and not highlighted:
            result.append(highlight)
        elif highlighted and not is_highlighted:
            result.extend(("\x1b[0m", gray))
        result.append(character)
        highlighted = is_highlighted
    if highlighted:
        result.extend(("\x1b[0m", gray))
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
    if not screen:
        return len(history)

    prefix_lengths = [0] * len(screen)
    prefix_length = 0
    for index in range(1, len(screen)):
        while prefix_length and screen[index] != screen[prefix_length]:
            prefix_length = prefix_lengths[prefix_length - 1]
        if screen[index] == screen[prefix_length]:
            prefix_length += 1
            prefix_lengths[index] = prefix_length

    matched = 0
    last_start: int | None = None
    for index, row in enumerate(history):
        while matched and row != screen[matched]:
            matched = prefix_lengths[matched - 1]
        if row == screen[matched]:
            matched += 1
            if matched == len(screen):
                last_start = index - len(screen) + 1
                matched = prefix_lengths[matched - 1]
    if last_start is not None:
        return last_start
    raise ValueError("Could not align Kitty's visible screen with its retained history")


def last_nonempty_row(rows: tuple[str, ...]) -> int:
    """Return the last row containing visible text, or the final row if blank."""
    for index in range(len(rows) - 1, -1, -1):
        if rows[index].strip():
            return index
    return max(0, len(rows) - 1)


def pad_history_to_viewport(
    rows: tuple[str, ...], viewport_start: int, viewport_height: int
) -> tuple[str, ...]:
    """Retain blank rows through the bottom of the current terminal viewport."""
    required_rows = viewport_start + viewport_height
    return rows + ("",) * max(0, required_rows - len(rows))


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
