import unittest

from kitty_scrollback_navigator.model import ScrollbackModel
from kitty_scrollback_navigator.session import ScrollbackSession


class FakeKittyAdapter:
    def __init__(self, active_window_id):
        self.active_window_id = active_window_id
        self.scroll_calls = []
        self.input_calls = []

    def scroll_window(self, window_id, amount):
        self.scroll_calls.append((window_id, amount))


class ScrollbackSessionTests(unittest.TestCase):
    def make_session(self):
        adapter = FakeKittyAdapter(active_window_id=41)
        model = ScrollbackModel(
            ("row 0", "row 1", "row 2", "row 3", "row 4"),
            viewport_height=3,
            row=4,
        )
        return adapter, ScrollbackSession(adapter, window_id=41, model=model)

    def test_navigation_is_local_until_accept_and_scrolls_captured_window(self):
        adapter, session = self.make_session()
        session.move("k")
        adapter.active_window_id = 99
        self.assertEqual(adapter.scroll_calls, [])
        session.accept()
        self.assertEqual(adapter.scroll_calls, [(41, "1l-")])
        self.assertEqual(adapter.input_calls, [])

    def test_cancel_makes_no_scroll_request_or_shell_input(self):
        adapter, session = self.make_session()
        session.move("k")
        session.cancel()
        self.assertEqual(adapter.scroll_calls, [])
        self.assertEqual(adapter.input_calls, [])

    def test_accept_at_latest_history_position_needs_no_scroll_request(self):
        adapter, session = self.make_session()
        session.accept()
        self.assertEqual(adapter.scroll_calls, [])
        self.assertEqual(adapter.input_calls, [])

    def test_accept_scrolls_relative_to_the_captured_viewport(self):
        adapter = FakeKittyAdapter(active_window_id=41)
        model = ScrollbackModel(
            ("row 0", "row 1", "row 2", "row 3", "row 4"),
            viewport_height=3,
            row=2,
        )
        session = ScrollbackSession(adapter, window_id=41, model=model, origin_row=2)
        session.move("j")
        session.accept()
        self.assertEqual(adapter.scroll_calls, [(41, "1l")])


if __name__ == "__main__":
    unittest.main()
