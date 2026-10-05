import tempfile
import unittest

from kitty_vim_overlay.instance import overlay_instance_lock


class VimOverlayInstanceTests(unittest.TestCase):
    def test_repeated_entry_is_ignored_until_active_session_exits(self):
        with tempfile.TemporaryDirectory() as runtime_directory:
            with overlay_instance_lock(12345, runtime_directory) as active:
                self.assertTrue(active)
                with overlay_instance_lock(12345, runtime_directory) as repeated:
                    self.assertFalse(repeated)
            with overlay_instance_lock(12345, runtime_directory) as after_exit:
                self.assertTrue(after_exit)


if __name__ == "__main__":
    unittest.main()
