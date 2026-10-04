from __future__ import annotations

import base64
import json
import os
import re
from typing import Callable

from kittens.tui.handler import Handler, kitten_ui
from kittens.tui.loop import EventType, Loop

from .bindings import action_for_key, load_bindings_file
from .instance import navigator_instance_lock
from .model import ScrollbackModel
from .search import JumpSession, JumpTarget, SearchState
from .session import ScrollbackSession
from .snapshot import (
    clip_ansi,
    flash_ansi_line,
    highlight_ansi_column,
    highlight_ansi_matches,
    highlight_ansi_range,
    styled_displayed_rows,
    viewport_first_row,
    viewport_start,
)

_ARROW_ACTIONS = (
    ("left", "move_left"),
    ("down", "move_down"),
    ("up", "move_up"),
    ("right", "move_right"),
)

_PAGE_ACTIONS = (
    ("page_up", "page_up"),
    ("page_down", "page_down"),
)

_JUMP_TRAIL_LENGTHS = (1, 2, 3, 4, 3, 2, 1)


def _windows(tree: list[dict]) -> list[dict]:
    return [
        window
        for os_window in tree
        for tab in os_window.get("tabs", ())
        for window in tab.get("windows", ())
    ]


class KittyAdapter:
    def __init__(self, remote_control: Callable, window_id: int) -> None:
        self.remote_control = remote_control
        self.window_id = window_id

    def get_text(self, extent: str, *, ansi: bool = False) -> str:
        command = [
            "get-text",
            f"--match=id:{self.window_id}",
            f"--extent={extent}",
            "--add-wrap-markers",
        ]
        if ansi:
            command.append("--ansi")
        result = self.remote_control(command, capture_output=True, check=True)
        return result.stdout.decode("utf-8")

    def scroll_window(self, window_id: int, amount: str) -> None:
        if window_id != self.window_id:
            raise ValueError("refusing to scroll a window other than the captured source")
        self.remote_control(
            ["scroll-window", f"--match=id:{self.window_id}", amount],
            check=True,
        )


class NavigatorUI(Handler):
    def __init__(
        self,
        session: ScrollbackSession,
        render_lines: tuple[str, ...],
        unavailable_reason: str | None = None,
    ) -> None:
        self.session = session
        self.model = session.model
        if len(render_lines) != len(self.model.lines):
            raise ValueError("render rows must match the scrollback model")
        self.render_lines = render_lines
        self.search = SearchState(self.model)
        self.jump = JumpSession(self.model)
        self.targets = ()
        self.bindings = load_bindings_file()
        self.mode = "normal"
        self.query = ""
        self.status = unavailable_reason or ""
        self.unavailable_reason = unavailable_reason
        self.accepted = False
        self.viewport_first: int | None = None
        self.visible_rows = 0
        self.flash_character: str | None = None
        self.selection_anchor: tuple[int, int] | None = None
        self.selection_type: str | None = None
        self.selection_column: int | None = None
        self.pending_go: str | None = None
        self.jump_animation_position: tuple[int, int] | None = None
        self.jump_animation_frame: int | None = None
        self.jump_animation_trail: tuple[tuple[int, int], ...] = ()
        self.jump_animation_handle = None

    def initialize(self) -> None:
        self._draw()

    @Handler.atomic_update
    def _draw(self) -> None:
        width = max(1, self.screen_size.cols)
        height = max(1, self.screen_size.rows)
        self.write("\x1b[0m\x1b[H\x1b[2J")
        if self.mode == "visual":
            visual_type = self.selection_type or "character"
            message = (
                f"VISUAL {visual_type} · hjkl/arrows · w/b move · y copy · Esc cancel"
            )
        else:
            message = self.status or (
                f"{self.mode}: {self.query}" if self.mode != "normal" else ""
            )
        if self.mode == "visual" and self.pending_go is not None:
            message += f" · {self.pending_go} pending"
        visible = max(1, height - 1)
        first = viewport_first_row(
            self.model.row,
            len(self.model.lines),
            visible,
            previous_first=self.viewport_first,
            previous_visible=self.visible_rows,
        )
        self.viewport_first = first
        self.visible_rows = visible
        flash_active = (
            self.mode == "jump_character" or self.flash_character is not None
        )
        targets_by_row: dict[int, list[JumpTarget]] = {}
        for target in self.targets:
            targets_by_row.setdefault(target.row, []).append(target)
        searching = self.mode in ("search_forward", "search_backward")
        search_query = self.query if searching else self.search.query or ""
        if searching:
            search_matches = self.search.match_positions(
                search_query,
                case_sensitive=False,
            )
            current_match = None
        else:
            search_matches = self.search.matches
            current_match = self.search.current_match
        search_columns_by_row: dict[int, list[int]] = {}
        for match_row, column in search_matches:
            search_columns_by_row.setdefault(match_row, []).append(column)
        selection_start: tuple[int, int] | None = None
        selection_end: tuple[int, int] | None = None
        if self.selection_anchor is not None:
            endpoint_column = (
                self.selection_column
                if self.selection_type == "block" and self.selection_column is not None
                else self.model.column
            )
            selection_start, selection_end = sorted(
                (self.selection_anchor, (self.model.row, endpoint_column))
            )
        trail_columns_by_row: dict[int, list[int]] = {}
        trail_tip: tuple[int, int] | None = None
        if (
            not flash_active
            and self.jump_animation_frame is not None
            and self.jump_animation_trail
        ):
            trail_length = min(
                _JUMP_TRAIL_LENGTHS[self.jump_animation_frame],
                len(self.jump_animation_trail),
            )
            trail_positions = self.jump_animation_trail[-trail_length:]
            trail_tip = trail_positions[-1]
            for trail_row, column in trail_positions:
                trail_columns_by_row.setdefault(trail_row, []).append(column)
        for row in range(first, min(len(self.model.lines), first + visible)):
            row_targets = targets_by_row.get(row, ())
            line = self.render_lines[row]
            if flash_active:
                labels_by_column = {
                    target.column: target.label for target in row_targets
                }
                line = flash_ansi_line(line, labels_by_column)
                prefix = ""
            else:
                labels = " ".join(target.label for target in row_targets)
                prefix = (f"[{labels}] " if labels else "")[:width]
                row_search_columns = search_columns_by_row.get(row, ())
                if row_search_columns:
                    line = highlight_ansi_matches(
                        line,
                        tuple(row_search_columns),
                        len(search_query),
                        current_match[1]
                        if current_match is not None and current_match[0] == row
                        else None,
                    )
                selected_row = (
                    selection_start is not None
                    and selection_end is not None
                    and selection_start[0] <= row <= selection_end[0]
                )
                if selected_row and self.selection_type == "line":
                    start_column = 0
                    end_column = max(0, len(self.model.lines[row]) - 1)
                    if not self.model.lines[row]:
                        line += " "
                elif selected_row and self.selection_type == "block":
                    start_column, end_column = sorted(
                        (
                            self.selection_anchor[1],
                            endpoint_column,
                        )
                    )
                    missing = end_column + 1 - len(self.model.lines[row])
                    if missing > 0:
                        line += " " * missing
                elif selected_row:
                    start_column = (
                        selection_start[1] if row == selection_start[0] else 0
                    )
                    end_column = (
                        selection_end[1]
                        if row == selection_end[0]
                        else len(self.model.lines[row]) - 1
                    )
                else:
                    start_column = 0
                    end_column = -1
                if selected_row:
                    line = highlight_ansi_range(line, start_column, end_column)
                trail_columns = trail_columns_by_row.get(row)
                if trail_columns:
                    older_columns = tuple(
                        column
                        for column in trail_columns
                        if trail_tip != (row, column)
                    )
                    if older_columns:
                        line = highlight_ansi_matches(
                            line, older_columns, 1, None
                        )
                    if trail_tip is not None and trail_tip[0] == row:
                        line = highlight_ansi_matches(
                            line, (trail_tip[1],), 1, trail_tip[1]
                        )
                if row == self.model.row:
                    cursor_column = min(
                        self.model.column,
                        max(0, len(self.model.lines[row]) - 1),
                    )
                    if (
                        self.jump_animation_position == (
                            row,
                            self.model.column,
                        )
                        and self.jump_animation_frame is not None
                    ):
                        line = highlight_ansi_matches(
                            line, (cursor_column,), 1, cursor_column
                        )
                    elif current_match != (row, self.model.column):
                        line = highlight_ansi_column(line, cursor_column)
            line = clip_ansi(line, width - len(prefix))
            self.print("\x1b[0m" + prefix + line + "\x1b[0m")
        footer = message or (
            "Esc/q exit · / ? search · s/S target · "
            "v/V/C-v select · y copy"
        )
        self.write(footer[:width])

    def on_text(self, text: str, in_bracketed_paste: bool = False) -> None:
        for char in text:
            if self.mode in ("search_forward", "search_backward"):
                self.query += char
                self.status = ""
                self._draw()
            elif self.mode == "jump_label":
                self.query += char
                origin = (self.model.row, self.model.column)
                result = self.jump.input_label(self.query)
                if result == "selected":
                    self._animate_cursor_jump(origin)
                if result == "selected":
                    self.mode = "normal"
                    self.query = ""
                    self.targets = ()
                    self.flash_character = None
                    self.status = ""
                elif result == "pending":
                    self.status = f"Label: {self.query}"
                else:
                    self.query = ""
                    self.status = "No target with that label"
                self._draw()
                if result == "selected":
                    return
            elif self.mode == "jump_character":
                self._set_character_targets(char)
            else:
                code = ord(char)
                key = f"<C-{chr(code + 96)}>" if 1 <= code <= 26 else char
                if self.mode in ("normal", "visual"):
                    self._dispatch_sequence_key(key)
                else:
                    self._dispatch_key(key)


    def _dispatch_sequence_key(self, key: str) -> None:
        pending = self.pending_go
        self.pending_go = None
        if pending is not None:
            self.status = ""
            if key == pending:
                origin = (self.model.row, self.model.column)
                self.model.move("gg" if key == "g" else "GG")
                self._animate_cursor_jump(origin)
                self._draw()
                return
        if key in ("g", "G"):
            self.pending_go = key
            self.status = f"{key} pending"
            self._draw()
            return
        if pending is not None and key != "q" and action_for_key(
            key, self.bindings
        ) is None:
            self._draw()
            return
        self._dispatch_key(key)

    def _clear_pending_go(self) -> None:
        if self.pending_go is not None:
            self.pending_go = None
            self.status = ""

    def on_key(self, key_event) -> None:
        if key_event.type is EventType.RELEASE:
            return
        if key_event.matches("enter"):
            self._clear_pending_go()
            if self.mode in ("normal", "visual"):
                self._dispatch_key(self.bindings["accept"])
            else:
                self._submit()
        elif key_event.matches("escape"):
            self._clear_pending_go()
            if self.mode == "normal":
                self._dispatch_key(self.bindings["cancel"])
            elif self.mode == "visual":
                self.mode = "normal"
                self.selection_anchor = None
                self.selection_type = None
                self.selection_column = None
                self.status = ""
                self._draw()
            else:
                self.mode = "normal"
                self.query = ""
                self.targets = ()
                self.flash_character = None
                self.status = ""
                self._draw()
        elif key_event.matches("backspace"):
            pending_go = self.pending_go is not None
            self._clear_pending_go()
            if self.mode not in ("normal", "visual"):
                self.query = self.query[:-1]
                self.status = ""
                self._draw()
            elif pending_go:
                self._draw()
        elif self.mode in ("normal", "visual"):
            for shortcut, action in _ARROW_ACTIONS:
                if key_event.matches(shortcut):
                    self._clear_pending_go()
                    self._dispatch_key(self.bindings[action])
                    return
            for shortcut, action in _PAGE_ACTIONS:
                if key_event.matches(shortcut):
                    self._clear_pending_go()
                    self._dispatch_key(self.bindings[action])
                    return
            for configured_key in self.bindings.values():
                shortcut = _kitty_shortcut(configured_key)
                if shortcut and key_event.matches(shortcut):
                    self._clear_pending_go()
                    self._dispatch_key(configured_key)
                    return

    def on_eot(self) -> None:
        self._dispatch_key(self.bindings["half_page_down"])

    def on_interrupt(self) -> None:
        self._cancel()

    def _animate_cursor_jump(self, origin: tuple[int, int]) -> None:
        destination = (self.model.row, self.model.column)
        if destination == origin or not hasattr(self, "_tui_loop"):
            return
        self._cancel_cursor_animation()
        row_delta = destination[0] - origin[0]
        column_delta = destination[1] - origin[1]
        steps = max(abs(row_delta), abs(column_delta))
        trail_length = min(max(_JUMP_TRAIL_LENGTHS), steps)
        self.jump_animation_trail = tuple(
            (
                round(origin[0] + row_delta * step / steps),
                round(origin[1] + column_delta * step / steps),
            )
            for step in range(steps - trail_length, steps)
        )
        self.jump_animation_position = destination
        self.jump_animation_frame = 0
        self.jump_animation_handle = self.asyncio_loop.call_later(
            0.08, self._advance_cursor_animation
        )

    def _advance_cursor_animation(self) -> None:
        if self.jump_animation_frame is None:
            return
        if self.jump_animation_frame >= len(_JUMP_TRAIL_LENGTHS) - 1:
            self._cancel_cursor_animation()
        else:
            self.jump_animation_frame += 1
        self._draw()
        if self.jump_animation_frame is not None:
            self.jump_animation_handle = self.asyncio_loop.call_later(
                0.08, self._advance_cursor_animation
            )

    def _cancel_cursor_animation(self) -> None:
        if self.jump_animation_handle is not None:
            self.jump_animation_handle.cancel()
        self.jump_animation_handle = None
        self.jump_animation_position = None
        self.jump_animation_trail = ()
        self.jump_animation_frame = None

    def finalize(self) -> None:
        self._cancel_cursor_animation()

    def _dispatch_key(self, key: str) -> None:
        if key == "q":
            self._cancel()
            return
        action = action_for_key(key, self.bindings)
        if action is None:
            return
        self._cancel_cursor_animation()
        movement = {
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
        }
        if action in movement:
            origin = (self.model.row, self.model.column)
            if self.mode == "visual" and self.selection_type == "block":
                if action in ("move_up", "move_down"):
                    desired_column = (
                        self.selection_column
                        if self.selection_column is not None
                        else self.model.column
                    )
                    self.model.move(movement[action])
                    self.model.column = min(
                        desired_column,
                        max(0, len(self.model.lines[self.model.row]) - 1),
                    )
                    self.selection_column = desired_column
                elif action in ("move_left", "move_right"):
                    desired_column = (
                        self.selection_column
                        if self.selection_column is not None
                        else self.model.column
                    )
                    self.selection_column = max(
                        0,
                        desired_column + (-1 if action == "move_left" else 1),
                    )
                    self.model.column = min(
                        self.selection_column,
                        max(0, len(self.model.lines[self.model.row]) - 1),
                    )
                else:
                    self.model.move(movement[action])
                    self.selection_column = self.model.column
            else:
                self.model.move(movement[action])
            self.status = ""
            viewport_scroll = (
                self.viewport_first is not None
                and self.visible_rows > 0
                and not (
                    self.viewport_first
                    <= self.model.row
                    < self.viewport_first + self.visible_rows
                )
            )
            if action in (
                "page_down",
                "page_up",
                "half_page_down",
                "half_page_up",
            ) or viewport_scroll:
                self._animate_cursor_jump(origin)
        elif action in ("search_forward", "search_backward"):
            self.selection_anchor = None
            self.selection_type = None
            self.selection_column = None
            self.mode = action
            self.query = ""
            self.status = "Enter search text, then press Enter"
        elif action in ("repeat_search", "reverse_search"):
            origin = (self.model.row, self.model.column)
            direction = "backward" if action == "reverse_search" else "forward"
            if not self.search.repeat(direction):
                self.status = (
                    "No previous search" if self.search.query is None else "No search match"
                )
            else:
                self._animate_cursor_jump(origin)
                self.status = ""
        elif action == "jump_character":
            self.selection_anchor = None
            self.selection_type = None
            self.selection_column = None
            self.mode = action
            self.query = ""
            self.status = "Type one character to label its occurrences"
        elif action == "jump_line":
            self.selection_anchor = None
            self.selection_type = None
            self.selection_column = None
            self.targets = self.jump.line_targets(self._visible_row_range())
            self.mode = "jump_label"
            self.query = ""
            self.flash_character = None
            self.status = (
                "Type a displayed line label" if self.targets else "No lines to label"
            )
        elif action in ("visual_mode", "visual_line_mode", "visual_block_mode"):
            selection_type = {
                "visual_mode": "character",
                "visual_line_mode": "line",
                "visual_block_mode": "block",
            }[action]
            if self.mode == "visual" and self.selection_type == selection_type:
                self.mode = "normal"
                self.selection_anchor = None
                self.selection_type = None
                self.selection_column = None
            else:
                if self.mode != "visual":
                    self.selection_anchor = (self.model.row, self.model.column)
                self.mode = "visual"
                self.selection_type = selection_type
                self.selection_column = (
                    self.model.column if selection_type == "block" else None
                )
            self.status = ""
        elif action == "yank_selection":
            if self.mode == "visual" and self.selection_anchor is not None:
                if self.selection_type == "line":
                    selected_text = self.model.selected_lines(
                        self.selection_anchor[0], self.model.row
                    )
                elif self.selection_type == "block":
                    selected_text = self.model.selected_block(
                        self.selection_anchor,
                        (
                            self.model.row,
                            self.selection_column
                            if self.selection_column is not None
                            else self.model.column,
                        ),
                    )
                else:
                    selected_text = self.model.selected_text(
                        self.selection_anchor,
                        (self.model.row, self.model.column),
                    )
                if selected_text or self.selection_type == "line":
                    encoded = base64.b64encode(
                        selected_text.encode("utf-8")
                    ).decode("ascii")
                    self.write(f"\x1b]52;c;{encoded}\x07")
                    self.status = "Copied selection"
                else:
                    self.status = "Nothing to copy"
                self.mode = "normal"
                self.selection_anchor = None
                self.selection_type = None
                self.selection_column = None
        elif action == "accept":
            self._accept()
            return
        elif action == "cancel":
            self._cancel()
            return
        self._draw()

    def _submit(self) -> None:
        if self.mode in ("search_forward", "search_backward"):
            origin = (self.model.row, self.model.column)
            if not self.query:
                self.status = "Search text cannot be empty"
            elif self.search.search(
                self.query,
                "forward" if self.mode == "search_forward" else "backward",
                case_sensitive=False,
            ):
                self._animate_cursor_jump(origin)
                self.status = ""
            else:
                self.status = "No search match"
            self.mode = "normal"
        self._draw()

    def _set_character_targets(self, character: str) -> None:
        self.targets = self.jump.character_targets(
            character,
            self._visible_row_range(),
        )
        self.flash_character = character
        self.mode = "jump_label"
        self.query = ""
        self.status = "Type a displayed label" if self.targets else "No matching character"
        self._draw()

    def _visible_row_range(self) -> range:
        first = self.viewport_first if self.viewport_first is not None else 0
        last = min(len(self.model.lines), first + self.visible_rows)
        return range(first, last)

    def _accept(self) -> None:
        if self.unavailable_reason:
            return
        try:
            self.session.accept()
        except Exception as error:
            self.status = f"Unable to move Kitty viewport: {error}"
            self._draw()
            return
        self.accepted = True
        self.quit_loop(0)

    def _cancel(self) -> None:
        self.session.cancel()
        self.quit_loop(0)


def _kitty_shortcut(key: str) -> str | None:
    if len(key) == 1:
        return key
    match = re.fullmatch(r"<([CAS])-([A-Za-z0-9])>", key)
    if match:
        modifier = {"C": "ctrl", "A": "alt", "S": "shift"}[match.group(1)]
        return f"{modifier}+{match.group(2).lower()}"
    names = {
        "<Enter>": "enter",
        "<Esc>": "escape",
        "<Tab>": "tab",
        "<Backspace>": "backspace",
        "<Delete>": "delete",
        "<Up>": "up",
        "<Down>": "down",
        "<Left>": "left",
        "<Right>": "right",
        "<Home>": "home",
        "<End>": "end",
        "<PageUp>": "page_up",
        "<PageDown>": "page_down",
        "<Insert>": "insert",
    }
    return names.get(key)


def _remote_text() -> tuple[
    int, KittyAdapter, tuple[str, ...], tuple[str, ...], tuple[str, ...], bool, int
]:
    result = main.remote_control(
        ["ls", "--match=state:overlay_parent"], capture_output=True, check=True
    )
    windows = _windows(json.loads(result.stdout))
    if len(windows) != 1:
        raise RuntimeError("Could not identify the Kitty window under this overlay")
    source = windows[0]
    window_id = int(source["id"])
    adapter = KittyAdapter(main.remote_control, window_id)
    history_pairs = styled_displayed_rows(adapter.get_text("all", ansi=True))
    screen_pairs = styled_displayed_rows(adapter.get_text("screen", ansi=True))
    history = tuple(plain for plain, _ in history_pairs)
    render_lines = tuple(styled for _, styled in history_pairs)
    screen = tuple(plain for plain, _ in screen_pairs)
    first_visible = viewport_start(history, screen)
    return (
        window_id,
        adapter,
        history,
        render_lines,
        screen,
        bool(source.get("in_alternate_screen", False)),
        first_visible,
    )


@kitten_ui(allow_remote_control=True)
def main(args: list[str]) -> str:
    with navigator_instance_lock(int(os.environ["KITTY_PID"])) as acquired:
        if not acquired:
            return "already-active"
        window_id, adapter, history, render_lines, screen, alternate, first_visible = (
            _remote_text()
        )
        bottom_row = first_visible + len(screen) - 1
        model = ScrollbackModel(
            history,
            viewport_height=len(screen),
            row=bottom_row,
        )
        session = ScrollbackSession(
            adapter,
            window_id=window_id,
            model=model,
            origin_row=bottom_row,
        )
        ui = NavigatorUI(
            session,
            render_lines,
            "Alternate-screen history is unavailable; press Esc to close"
            if alternate
            else None,
        )
        Loop().loop(ui)
        return "accepted" if ui.accepted else "cancelled"
