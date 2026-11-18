"""
Unit tests for the prompt bar's native field on macOS (``app_native_field``).

Pinned here:
  * the control sits over the drawn field, inset like its text, one line tall and
    centred, in Cocoa's bottom-left coordinates;
  * what the control holds is capped like the drawn editor: one line, at most the
    wire's prompt size;
  * a bar with a native control draws no text of its own;
  * driven in a hidden window: typing reaches the bar's editor, Enter sends and
    empties the control, Esc hands the keys back, and while the agent works the
    control does not edit and shows the working placeholder.

The last needs AppKit; elsewhere it is skipped, as the field is.

Run with: uv run python tests/native_field_tests.py
"""

import sys
import unittest

import glfw
import skia

from md2ui.app_native_field import attach, capped, field_frame
from md2ui.app_prompt import _INSET, PLACEHOLDERS, PromptBar
from md2ui.wire import MAX_PROMPT_BYTES


def test_the_control_sits_over_the_drawn_field():
    # A 40-high field whose top is 500 from the window's top, in a 600-high view.
    x, y, w, h = field_frame(12.0, 500.0, 300.0, 40.0, 600.0, 20.0)
    assert (x, w, h) == (12.0 + _INSET, 300.0 - 2 * _INSET, 20.0)
    assert y == 600.0 - 510.0 - 20.0, "Cocoa counts up from the bottom"
    print("  ✓  the control sits over the drawn field, centred")


def test_the_control_holds_what_the_editor_would():
    assert capped("two\nlines") == "two lines"
    assert len(capped("x" * (MAX_PROMPT_BYTES + 9)).encode()) == MAX_PROMPT_BYTES
    print("  ✓  one line, at most the wire's prompt size")


def test_a_native_bar_draws_no_text():
    def ink(native: bool) -> bytes:
        bar = PromptBar(skia.Typeface.MakeDefault())
        bar.native = native
        bar.editor.insert("hello there")
        bitmap = skia.Bitmap()
        bitmap.allocPixels(skia.ImageInfo.MakeN32Premul(400, 120))
        bitmap.eraseARGB(0, 0, 0, 0)
        bar.draw(skia.Canvas(bitmap), 400, 120)
        return bytes(bitmap.tobytes())

    assert ink(True) != ink(False), "the drawn text is the control's now"
    print("  ✓  a bar with a native control draws no text of its own")


def test_the_control_edits_sends_and_locks():
    if sys.platform != "darwin":
        raise unittest.SkipTest("not macOS: no native field to drive")
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, False)
    window = glfw.create_window(400, 300, "native field", None, None)
    try:
        bar = PromptBar(skia.Typeface.MakeDefault())
        bar.sync("l")
        sent: list[str] = []
        native = attach(window, bar, lambda: sent.append(bar.submit()), lambda: None)
        assert native is not None and bar.native
        native.sync(400, 300)
        native.field.setStringValue_("hola, ¿qué tal?")
        native.changed()
        assert bar.editor.text == "hola, ¿qué tal?"
        delegate = native.field.delegate()
        assert delegate.control_textView_doCommandBySelector_(
            native.field, None, "insertNewline:"
        )
        native.sync(400, 300)
        assert sent == ["hola, ¿qué tal?"] and native.field.stringValue() == ""
        native.focus()
        assert bar.focused
        delegate.control_textView_doCommandBySelector_(
            native.field, None, "cancelOperation:"
        )
        assert not bar.focused, "Esc hands the keys back to the window"
        bar.sync("w", 1)
        native.sync(400, 300)
        assert not native.field.isEditable()
        assert native.field.placeholderAttributedString().string() == PLACEHOLDERS["w"]
        aqua = native.field.effectiveAppearance().name()
        assert aqua == "NSAppearanceNameAqua", f"light whatever the system's: {aqua}"
    finally:
        glfw.destroy_window(window)
    print("  ✓  the control edits, sends, hands keys back and locks")


TESTS = [
    test_the_control_sits_over_the_drawn_field,
    test_the_control_holds_what_the_editor_would,
    test_a_native_bar_draws_no_text,
    test_the_control_edits_sends_and_locks,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
