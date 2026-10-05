import unittest

from kitty_scrollback_navigator.model import ScrollbackModel


class ScrollbackMovementTests(unittest.TestCase):
    def make_model(self, lines, row=0, column=0, height=3):
        return ScrollbackModel(lines, viewport_height=height, row=row, column=column)

    def test_each_displayed_row_including_wrapped_rows_has_a_position(self):
        model = self.make_model(("first segment", "wrapped continuation", "next line"))
        model.move("j")
        self.assertEqual((model.row, model.column), (1, 0))
        model.move("j")
        self.assertEqual((model.row, model.column), (2, 0))

    def test_horizontal_and_vertical_motion_clamp_to_history_and_line(self):
        model = self.make_model(("abc", "x"), row=0, column=2)
        model.move("l")
        self.assertEqual(model.column, 2)
        model.move("j")
        self.assertEqual((model.row, model.column), (1, 0))
        model.move("k")
        self.assertEqual((model.row, model.column), (0, 0))
        model.move("h")
        self.assertEqual(model.column, 0)

    def test_word_motion_moves_across_words_and_rows(self):
        model = self.make_model(("one two", "three four"))
        model.move("w")
        self.assertEqual((model.row, model.column), (0, 4))
        model.move("w")
        self.assertEqual((model.row, model.column), (1, 0))
        model.move("b")
        self.assertEqual((model.row, model.column), (0, 4))

    def test_movement_stops_at_last_nonblank_row_but_keeps_internal_blank_rows(self):
        model = self.make_model(("first", "", "last", "", ""), row=1)

        model.move("j")
        self.assertEqual(model.row, 2)
        model.move("j")
        self.assertEqual(model.row, 2)
        model.move("GG")
        self.assertEqual(model.row, 2)

        model.move("gg")
        model.move("<C-f>")
        self.assertEqual(model.row, 2)

    def test_initial_cursor_is_clamped_out_of_trailing_blank_rows(self):
        model = self.make_model(("first", "last", "", ""), row=3)
        self.assertEqual(model.row, 1)

    def test_gg_and_GG_jump_to_first_and_last_displayed_rows(self):
        model = self.make_model(("top", "middle", "bottom"), row=1, column=4)

        model.move("gg")
        self.assertEqual((model.row, model.column), (0, 2))
        model.move("GG")
        self.assertEqual((model.row, model.column), (2, 2))

    def test_selection_text_is_inclusive_in_both_directions(self):
        model = self.make_model(("one two", "three"))
        expected = "ne two\nthr"
        self.assertEqual(model.selected_text((0, 1), (1, 2)), expected)
        self.assertEqual(model.selected_text((1, 2), (0, 1)), expected)

    def test_linewise_selection_copies_complete_rows_in_document_order(self):
        model = self.make_model(("first", "middle", "last"))
        self.assertEqual(model.selected_lines(2, 1), "middle\nlast")

    def test_blockwise_selection_keeps_columns_and_pads_short_rows(self):
        model = self.make_model(("abcdef", "xy", "12345"))
        self.assertEqual(
            model.selected_block((0, 2), (2, 4)),
            "cde\n   \n345",
        )

    def test_line_boundaries_select_first_and_last_character(self):
        model = self.make_model(("alpha", "beta"), column=2)
        model.move("$")
        self.assertEqual(model.column, 4)
        model.move("0")
        self.assertEqual(model.column, 0)

    def test_page_and_half_page_steps_clamp_to_history_and_view_height(self):
        model = self.make_model(tuple(f"row {i}" for i in range(10)), height=4)
        model.move("<C-f>")
        self.assertEqual(model.row, 4)
        model.move("<C-d>")
        self.assertEqual(model.row, 6)
        model.move("<C-f>")
        self.assertEqual(model.row, 9)
        model.move("<C-b>")
        self.assertEqual(model.row, 5)
        model.move("<C-u>")
        self.assertEqual(model.row, 3)
        model.move("<C-b>")
        self.assertEqual(model.row, 0)

    def test_pages_clamp_to_short_navigation_view(self):
        model = self.make_model(("only",), height=20)
        model.move("<C-f>")
        self.assertEqual(model.row, 0)
        self.assertEqual(model.page_size, 1)


if __name__ == "__main__":
    unittest.main()
