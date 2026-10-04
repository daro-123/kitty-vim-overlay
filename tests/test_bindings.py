import json
import tempfile
import unittest
from pathlib import Path
from kitty_scrollback_navigator.bindings import (
    DEFAULT_BINDINGS,
    BindingError,
    action_for_key,
    load_bindings,
    load_bindings_file,
)


class BindingConfigurationTests(unittest.TestCase):
    def test_defaults_cover_each_interactive_action(self):
        expected_actions = {
            "move_left", "move_down", "move_up", "move_right",
            "word_forward", "word_backward", "line_start", "line_end",
            "page_down", "page_up", "half_page_down", "half_page_up",
            "search_forward", "search_backward", "repeat_search",
            "reverse_search", "jump_character", "jump_line", "accept", "cancel",
            "visual_mode", "visual_line_mode", "visual_block_mode",
            "yank_selection",
        }
        self.assertEqual(set(DEFAULT_BINDINGS), expected_actions)

    def test_visual_selection_defaults_to_v_and_y(self):
        self.assertEqual(DEFAULT_BINDINGS["visual_mode"], "v")
        self.assertEqual(DEFAULT_BINDINGS["yank_selection"], "y")

    def test_line_and_block_visual_modes_have_vim_bindings(self):
        self.assertEqual(DEFAULT_BINDINGS["visual_line_mode"], "V")
        self.assertEqual(DEFAULT_BINDINGS["visual_block_mode"], "<C-v>")

    def test_documented_configuration_is_a_valid_complete_default_map(self):
        example = Path(__file__).parent.parent / "config/bindings.example.json"
        self.assertEqual(
            load_bindings(example.read_text(encoding="utf-8")),
            DEFAULT_BINDINGS,
        )

    def test_user_configuration_replaces_the_default_map(self):
        configured = dict(DEFAULT_BINDINGS)
        configured["move_down"] = "J"
        loaded = load_bindings(json.dumps(configured))
        self.assertEqual(loaded, configured)
        self.assertNotIn("j", loaded.values())

    def test_remapped_key_resolves_to_its_configured_action(self):
        configured = dict(DEFAULT_BINDINGS)
        configured["move_down"] = "J"
        loaded = load_bindings(json.dumps(configured))
        self.assertEqual(action_for_key("J", loaded), "move_down")
        self.assertIsNone(action_for_key("j", loaded))

    def test_missing_file_uses_defaults_and_existing_file_replaces_them(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bindings.json"
            self.assertEqual(load_bindings_file(path), DEFAULT_BINDINGS)
            configured = dict(DEFAULT_BINDINGS)
            configured["move_down"] = "J"
            path.write_text(json.dumps(configured), encoding="utf-8")
            self.assertEqual(load_bindings_file(path), configured)

    def test_malformed_json_is_rejected(self):
        with self.assertRaises(BindingError):
            load_bindings('{"move_down":')

    def test_unknown_actions_are_rejected(self):
        configured = dict(DEFAULT_BINDINGS)
        configured["move_sideways"] = "x"
        with self.assertRaises(BindingError):
            load_bindings(json.dumps(configured))

    def test_duplicate_key_assignments_are_rejected(self):
        configured = dict(DEFAULT_BINDINGS)
        configured["move_down"] = configured["move_up"]
        with self.assertRaises(BindingError):
            load_bindings(json.dumps(configured))


if __name__ == "__main__":
    unittest.main()
