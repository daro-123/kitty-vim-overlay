import tempfile
import unittest

from kitty_vim_overlay.instance import (
    OVERLAY_PANEL_ID_VAR,
    overlay_panel_id,
    overlay_panel_lock,
)


class VimOverlayPanelTests(unittest.TestCase):
    def test_repeated_entry_is_ignored_until_same_panel_session_exits(self):
        with tempfile.TemporaryDirectory() as runtime_directory:
            with overlay_panel_lock(12345, 10, runtime_directory) as active:
                self.assertTrue(active)
                with overlay_panel_lock(12345, 10, runtime_directory) as repeated:
                    self.assertFalse(repeated)
            with overlay_panel_lock(12345, 10, runtime_directory) as after_exit:
                self.assertTrue(after_exit)

    def test_distinct_panels_in_one_kitty_instance_can_run_together(self):
        with tempfile.TemporaryDirectory() as runtime_directory:
            with overlay_panel_lock(12345, 10, runtime_directory) as first:
                with overlay_panel_lock(12345, 11, runtime_directory) as second:
                    self.assertTrue(first)
                    self.assertTrue(second)

    def test_window_ids_are_scoped_to_the_kitty_instance(self):
        with tempfile.TemporaryDirectory() as runtime_directory:
            with overlay_panel_lock(12345, 10, runtime_directory) as first:
                with overlay_panel_lock(67890, 10, runtime_directory) as second:
                    self.assertTrue(first)
                    self.assertTrue(second)

    def test_first_overlay_uses_its_source_panel_id(self):
        self.assertEqual(overlay_panel_id(10, {}), 10)

    def test_nested_overlay_inherits_the_original_source_panel_id(self):
        self.assertEqual(
            overlay_panel_id(20, {OVERLAY_PANEL_ID_VAR: "10"}),
            10,
        )

    def test_reentry_from_nested_overlay_is_blocked_on_original_panel(self):
        with tempfile.TemporaryDirectory() as runtime_directory:
            with overlay_panel_lock(12345, 10, runtime_directory) as active:
                with overlay_panel_lock(
                    12345,
                    overlay_panel_id(20, {OVERLAY_PANEL_ID_VAR: "10"}),
                    runtime_directory,
                ) as nested:
                    self.assertTrue(active)
                    self.assertFalse(nested)


if __name__ == "__main__":
    unittest.main()
