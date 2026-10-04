from __future__ import annotations

from typing import Protocol

from .model import ScrollbackModel


class ScrollbackAdapter(Protocol):
    def scroll_window(self, window_id: int, amount: str) -> None: ...


class ScrollbackSession:
    """Keep local navigation separate from terminal side effects."""

    def __init__(
        self,
        adapter: ScrollbackAdapter,
        *,
        window_id: int,
        model: ScrollbackModel,
        origin_row: int | None = None,
    ) -> None:
        self.adapter = adapter
        self.window_id = window_id
        self.model = model
        self.origin_row = (
            len(model.lines) - 1 if origin_row is None else origin_row
        )

    def move(self, key: str) -> None:
        self.model.move(key)

    def accept(self) -> None:
        delta = self.origin_row - self.model.row
        if delta:
            direction = "l-" if delta > 0 else "l"
            self.adapter.scroll_window(self.window_id, f"{abs(delta)}{direction}")

    def cancel(self) -> None:
        return
