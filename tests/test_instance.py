import tempfile
import unittest

from kitty_scrollback_navigator.instance import navigator_instance_lock


class NavigatorInstanceTests(unittest.TestCase):
    def test_repeated_entry_is_ignored_until_active_session_exits(self):
        with tempfile.TemporaryDirectory() as runtime_directory:
            with navigator_instance_lock(12345, runtime_directory) as active:
                self.assertTrue(active)
                with navigator_instance_lock(12345, runtime_directory) as repeated:
                    self.assertFalse(repeated)
            with navigator_instance_lock(12345, runtime_directory) as after_exit:
                self.assertTrue(after_exit)


if __name__ == "__main__":
    unittest.main()
