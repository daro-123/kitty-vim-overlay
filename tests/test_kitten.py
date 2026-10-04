import unittest

from kitty_scrollback_navigator.snapshot import (
    clip_ansi,
    displayed_rows,
    flash_ansi_line,
    highlight_ansi_column,
    highlight_ansi_matches,
    highlight_ansi_range,
    strip_ansi,
    styled_displayed_rows,
    viewport_first_row,
    viewport_start,
)


class DisplayRowTests(unittest.TestCase):
    def test_displayed_rows_preserve_wrapped_rows_and_remove_trailing_separator(self):
        self.assertEqual(
            displayed_rows("before\rwrapped-part\r\nnext\n"),
            ("before", "wrapped-part", "next"),
        )

    def test_viewport_alignment_uses_last_matching_history_segment(self):
        history = ("old", "a", "b", "a", "b")
        self.assertEqual(viewport_start(history, ("a", "b")), 3)

    def test_viewport_alignment_fails_when_screen_text_is_not_in_history(self):
        with self.assertRaisesRegex(ValueError, "align"):
            viewport_start(("history",), ("other",))


    def test_styled_rows_preserve_ansi_and_expose_plain_search_text(self):
        styled = "\x1b[34mconfig/\x1b[39m"
        self.assertEqual(styled_displayed_rows(styled), (("config/", styled),))

    def test_highlight_counts_visible_text_not_ansi_sequences(self):
        row = "\x1b[34mred\x1b[39m"
        self.assertEqual(
            highlight_ansi_column(row, 1),
            "\x1b[34mr\x1b[7me\x1b[27md\x1b[39m",
        )

    def test_highlight_range_is_inclusive_and_ansi_aware(self):
        row = "\x1b[34mabcdef\x1b[39m"
        self.assertEqual(
            highlight_ansi_range(row, 1, 3),
            (
                "\x1b[34ma\x1b[7mb\x1b[27m"
                "\x1b[7mc\x1b[27m\x1b[7md\x1b[27mef\x1b[39m"
            ),
        )

    def test_search_highlights_all_matches_and_inverts_the_current_match(self):
        rendered = highlight_ansi_matches("red red", (0, 4), 3, 4)
        self.assertEqual(
            rendered,
            (
                "\x1b[48;2;70;100;140mr\x1b[49m"
                "\x1b[48;2;70;100;140me\x1b[49m"
                "\x1b[48;2;70;100;140md\x1b[49m "
                "\x1b[48;2;255;193;7mr\x1b[49m"
                "\x1b[48;2;255;193;7me\x1b[49m"
                "\x1b[48;2;255;193;7md\x1b[49m"
            ),
        )

    def test_search_highlighting_preserves_ansi_styled_text(self):
        rendered = highlight_ansi_matches(
            "\x1b[34mred red\x1b[39m", (0, 4), 3, 4
        )
        self.assertEqual(strip_ansi(rendered), "red red")
        self.assertEqual(rendered.count("\x1b[48;2;70;100;140m"), 3)
        self.assertEqual(rendered.count("\x1b[48;2;255;193;7m"), 3)
        self.assertNotIn("\x1b[4m", rendered)

    def test_ansi_clipping_does_not_split_control_sequences(self):
        self.assertEqual(clip_ansi("\x1b[34mred\x1b[39m", 2), "\x1b[34mre\x1b[0m")

    def test_flash_dims_text_and_highlights_a_match_with_its_label(self):
        rendered = flash_ansi_line("\x1b[34mtext\x1b[39m", {0: "a"})
        self.assertEqual(strip_ansi(rendered), "t[a]ext")
        self.assertIn("\x1b[38;2;160;160;160m", rendered)
        self.assertIn("\x1b[38;2;30;30;30;48;2;255;193;7m", rendered)
        self.assertIn(
            "t[a]\x1b[0m\x1b[38;2;160;160;160mext",
            rendered,
        )

class ViewportLayoutTests(unittest.TestCase):
    def test_selection_inside_displayed_rows_keeps_viewport_fixed(self):
        self.assertEqual(
            viewport_first_row(16, 50, 10, previous_first=10, previous_visible=10),
            10,
        )

    def test_viewport_moves_only_when_selection_leaves_its_edges(self):
        self.assertEqual(
            viewport_first_row(20, 50, 10, previous_first=10, previous_visible=10),
            11,
        )


if __name__ == "__main__":
    unittest.main()
