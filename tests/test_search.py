import unittest

from kitty_scrollback_navigator.model import ScrollbackModel
from kitty_scrollback_navigator.search import JumpSession, SearchState


class SearchAndJumpTests(unittest.TestCase):
    def make_model(self, lines, row=0, column=0):
        return ScrollbackModel(lines, viewport_height=3, row=row, column=column)
    def test_search_finds_nearest_literal_match_in_each_direction(self):
        lines = ("needle needle", "middle", "needle tail")
        forward_model = self.make_model(lines)
        forward = SearchState(forward_model)
        self.assertTrue(forward.search("needle", "forward"))
        self.assertEqual((forward_model.row, forward_model.column), (0, 7))

        backward_model = self.make_model(lines, row=2, column=8)
        backward = SearchState(backward_model)
        self.assertTrue(backward.search("needle", "backward"))
        self.assertEqual((backward_model.row, backward_model.column), (2, 0))

    def test_search_tracks_all_case_insensitive_matches_and_current_match(self):
        model = self.make_model(("Hit hit", "noise", "HIT"))
        search = SearchState(model)

        self.assertTrue(search.search("hit", "forward", case_sensitive=False))
        self.assertEqual(search.matches, ((0, 0), (0, 4), (2, 0)))
        self.assertEqual(search.current_match, (0, 4))


    def test_match_positions_can_be_limited_to_visible_rows(self):
        search = SearchState(self.make_model(("hit", "noise", "HIT", "hit")))

        self.assertEqual(
            search.match_positions("hit", rows=range(1, 4)),
            ((2, 0), (3, 0)),
        )
    def test_forward_search_is_case_insensitive_by_default(self):
        search = SearchState(self.make_model(("ERROR",)))
        self.assertTrue(search.search("error", "forward"))
        self.assertEqual(search.matches, ((0, 0),))

    def test_backward_search_ignores_case_and_repeat_keeps_that_setting(self):
        model = self.make_model(("ERROR one", "noise", "error two"), row=1)
        search = SearchState(model)

        self.assertTrue(search.search("error", "backward", case_sensitive=False))
        self.assertEqual((model.row, model.column), (0, 0))
        self.assertTrue(search.repeat("forward"))
        self.assertEqual((model.row, model.column), (2, 0))

    def test_n_moves_forward_and_N_backward_after_a_backward_search(self):
        model = self.make_model(("hit", "hit", "hit"))
        search = SearchState(model)
        self.assertTrue(search.search("hit", "backward"))
        self.assertEqual(model.row, 2)
        self.assertTrue(search.repeat("forward"))
        self.assertEqual(model.row, 0)
        self.assertTrue(search.repeat("backward"))
        self.assertEqual(model.row, 2)

    def test_repeat_search_wraps_in_both_directions(self):
        model = self.make_model(("hit", "hit", "hit"))
        search = SearchState(model)

        self.assertTrue(search.search("hit", "forward"))
        self.assertEqual(model.row, 1)
        self.assertTrue(search.repeat("forward"))
        self.assertEqual(model.row, 2)
        self.assertTrue(search.repeat("forward"))
        self.assertEqual(model.row, 0)
        self.assertTrue(search.repeat("backward"))
        self.assertEqual(model.row, 2)

    def test_backward_search_repeats_with_n_and_N(self):
        model = self.make_model(("hit", "hit", "hit"))
        search = SearchState(model)

        self.assertTrue(search.search("hit", "backward"))
        self.assertEqual(model.row, 2)
        self.assertTrue(search.repeat("backward"))
        self.assertEqual(model.row, 1)
        self.assertTrue(search.repeat("forward"))
        self.assertEqual(model.row, 2)


    def test_repeat_uses_strict_column_boundaries_with_multiple_matches_per_row(self):
        model = self.make_model(("x x x",))
        search = SearchState(model)

        self.assertTrue(search.search("x", "forward"))
        self.assertEqual((model.row, model.column), (0, 2))
        self.assertTrue(search.repeat("backward"))
        self.assertEqual((model.row, model.column), (0, 0))
        self.assertTrue(search.repeat("backward"))
        self.assertEqual((model.row, model.column), (0, 4))
    def test_repeat_starts_from_the_current_cursor_after_manual_motion(self):
        model = self.make_model(("hit", "hit", "hit"))
        search = SearchState(model)

        self.assertTrue(search.search("hit", "forward"))
        model.move("j")
        self.assertTrue(search.repeat("forward"))
        self.assertEqual(model.row, 0)

    def test_no_match_preserves_position_and_reports_failure(self):
        model = self.make_model(("first", "second"), row=1, column=2)
        search = SearchState(model)
        self.assertFalse(search.search("absent", "forward"))
        self.assertEqual((model.row, model.column), (1, 2))

    def test_character_targets_are_limited_to_displayed_rows(self):
        model = self.make_model(("x outside", "X first x", "last x"))
        jump = JumpSession(model)

        targets = jump.character_targets("x", range(1, 3))

        self.assertEqual(
            [(target.row, target.column) for target in targets],
            [(1, 0), (1, 8), (2, 5)],
        )
        self.assertEqual(jump.input_label(targets[-1].label), "selected")
        self.assertEqual((model.row, model.column), (2, 5))


    def test_line_targets_exclude_trailing_blank_rows(self):
        model = self.make_model(("first", "last", "", ""))
        jump = JumpSession(model)

        targets = jump.line_targets(range(4))

        self.assertEqual([target.row for target in targets], [0, 1])
    def test_line_labels_are_limited_to_displayed_rows_and_jump_in_place(self):
        model = self.make_model(tuple(f"row {index}" for index in range(50)), row=20)
        jump = JumpSession(model)

        targets = jump.line_targets(range(10, 37))

        self.assertEqual([target.row for target in targets], list(range(10, 37)))
        self.assertTrue(all(target.label.isalpha() for target in targets))
        label = targets[-1].label
        self.assertEqual(jump.input_label(label[0].upper()), "pending")
        self.assertEqual(model.row, 20)
        self.assertEqual(jump.input_label(label.upper()), "selected")
        self.assertEqual((model.row, model.column), (36, 0))


if __name__ == "__main__":
    unittest.main()
