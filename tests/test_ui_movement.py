import importlib
import sys
import types
import unittest
from unittest.mock import patch

from kitty_vim_overlay.bindings import DEFAULT_BINDINGS
from kitty_vim_overlay.model import ScrollbackModel


def load_overlay_module():
    kittens = types.ModuleType("kittens")
    tui = types.ModuleType("kittens.tui")
    handler = types.ModuleType("kittens.tui.handler")
    loop = types.ModuleType("kittens.tui.loop")
    handler.Handler = type(
        "Handler", (), {"atomic_update": staticmethod(lambda function: function)}
    )
    handler.kitten_ui = lambda **kwargs: lambda function: function
    loop.EventType = type("EventType", (), {"PRESS": object(), "RELEASE": object()})
    loop.Loop = type("Loop", (), {})
    kitty_modules = {
        "kittens": kittens,
        "kittens.tui": tui,
        "kittens.tui.handler": handler,
        "kittens.tui.loop": loop,
    }
    with patch.dict(sys.modules, kitty_modules):
        return importlib.import_module("kitty_vim_overlay.kitten")


class NormalModeMovementTests(unittest.TestCase):
    def test_hjkl_text_keys_move_the_model(self):
        overlay_module = load_overlay_module()
        line_a, line_b = "abc", "def"
        model = ScrollbackModel((line_a, line_b), viewport_height=2, column=1)
        with patch.object(overlay_module, "load_bindings_file", return_value=DEFAULT_BINDINGS):
            ui = overlay_module.VimOverlayUI(model, (line_a, line_b))
        ui._draw = lambda: None

        ui.on_text("h")
        self.assertEqual((model.row, model.column), (0, 0))
        ui.on_text("l")
        self.assertEqual((model.row, model.column), (0, 1))
        ui.on_text("j")
        self.assertEqual((model.row, model.column), (1, 1))
        ui.on_text("k")
        self.assertEqual((model.row, model.column), (0, 1))

    def test_counted_word_and_ctrl_arrow_keys_move_the_model(self):
        overlay_module = load_overlay_module()
        line = "one two three four"
        model = ScrollbackModel((line,), viewport_height=1)
        with patch.object(
            overlay_module, "load_bindings_file", return_value=DEFAULT_BINDINGS
        ):
            ui = overlay_module.VimOverlayUI(model, (line,))
        ui._draw = lambda: None

        ui.on_text("2w")
        self.assertEqual(model.column, 8)
        key_event = type(
            "KeyEvent",
            (),
            {
                "type": overlay_module.EventType.PRESS,
                "matches": lambda self, key: key == "ctrl+left",
            },
        )()
        ui.on_key(key_event)
        self.assertEqual(model.column, 4)
