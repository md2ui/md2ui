"""The prompt bar's text field as a native macOS control.

The drawn field in :mod:`md2ui.app_prompt` edits text by hand: no selection, no
word or line moves, and no input methods, so an accent composed through one never
arrives. On macOS an ``NSTextField`` laid over the drawn field brings all of that,
with undo, the context menu, spelling and dictation. The bar still draws the
field's box, the Send button and the agent's state; the control only edits.

The control owns the text while it exists. Each change is copied into the bar's
editor, so Send, the byte cap and the "ready" button read one place; when the bar
empties its editor (a message went), :meth:`NativeField.sync` empties the control.

Everywhere else, or when PyObjC or the Cocoa window is missing, :func:`attach`
returns None and the drawn field stays.
"""

from __future__ import annotations

import ctypes
import importlib
import sys
from collections.abc import Callable
from typing import Any

from md2ui.app_prompt import _INSET, PromptBar, PromptText


def field_frame(
    x: float, y: float, w: float, h: float, content_h: float, line_h: float
) -> tuple[float, float, float, float]:
    """The control's Cocoa frame for the drawn field box (*x*, *y*, *w*, *h*, top-left
    origin): inset like the drawn text, one line tall, centred, in a bottom-left
    origin view of height *content_h*."""
    top = y + (h - line_h) / 2
    return x + _INSET, content_h - top - line_h, max(0.0, w - 2 * _INSET), line_h


def capped(text: str) -> str:
    """*text* as the drawn editor would hold it: one line, at most the wire's size."""
    editor = PromptText()
    editor.insert(text)
    return editor.text


class NativeField:
    """An ``NSTextField`` over the bar's field, kept in step with *bar*."""

    def __init__(
        self,
        ns_window,
        bar: PromptBar,
        on_send: Callable[[], None],
        on_change: Callable[[], None],
    ) -> None:
        appkit = _pyobjc("AppKit")
        NSColor, NSFont, NSTextField = appkit.NSColor, appkit.NSFont, appkit.NSTextField

        self.bar, self.on_send, self.on_change = bar, on_send, on_change
        self._window = ns_window
        self._content = ns_window.contentView()
        st = bar.style
        self._font = NSFont.systemFontOfSize_(st.text_size)
        self._line_h = self._font.ascender() - self._font.descender() + 2
        self._colors = {ink: _ns_color(NSColor, ink) for ink in (st.ink, st.muted)}
        self._attributed = appkit.NSAttributedString
        self._placeholder_attrs = {
            appkit.NSFontAttributeName: self._font,
            appkit.NSForegroundColorAttributeName: self._colors[st.muted],
        }
        field = NSTextField.alloc().initWithFrame_(((0, 0), (0, 0)))
        # The bar's colours are fixed and light, so the control is too: in Dark
        # mode its placeholder and caret would be drawn white on the white field.
        field.setAppearance_(
            appkit.NSAppearance.appearanceNamed_("NSAppearanceNameAqua")
        )
        field.setFont_(self._font)
        field.setBezeled_(False)
        field.setBordered_(False)
        field.setDrawsBackground_(False)
        field.setFocusRingType_(appkit.NSFocusRingTypeNone)
        field.cell().setUsesSingleLineMode_(True)
        field.cell().setScrollable_(True)
        self._delegate = _delegate_class().alloc().init()
        self._delegate.owner = self
        field.setDelegate_(self._delegate)
        self._content.addSubview_(field)
        self.field = field
        self._shown: tuple = ()
        bar.native = True

    def sync(self, win_w: float, win_h: float) -> None:
        """Place the control over the drawn field and say what the bar says: the
        placeholder for the agent's state, and no editing while it works."""
        _bar, box, _button = self.bar._boxes(win_w, win_h)
        content_h = self._content.frame().size.height
        frame = field_frame(box.x, box.y, box.w, box.h, content_h, self._line_h)
        locked = self.bar.locked
        placeholder = self.bar.placeholder
        shown = (frame, locked, placeholder)
        if shown != self._shown:
            self._shown = shown
            x, y, w, h = frame
            self.field.setFrame_(((x, y), (w, h)))
            self.field.setEditable_(not locked)
            ink = self.bar.style.muted if locked else self.bar.style.ink
            self.field.setTextColor_(self._colors[ink])
            # In the drawn field's muted ink, not the system's placeholder colour.
            self.field.setPlaceholderAttributedString_(
                self._attributed.alloc().initWithString_attributes_(
                    placeholder, self._placeholder_attrs
                )
            )
        if self.field.stringValue() != self.bar.editor.text:
            self.field.setStringValue_(self.bar.editor.text)
        # Focus is the window's to say: a click on the control never reaches GLFW.
        self.bar.focused = self._has_focus()

    def _has_focus(self) -> bool:
        responder = self._window.firstResponder()
        if responder is None or responder == self._content:
            return False
        return responder == self.field or (
            responder.respondsToSelector_("delegate")
            and responder.delegate() == self.field
        )

    def focus(self) -> None:
        self._window.makeFirstResponder_(self.field)
        self.bar.focused = True

    def blur(self) -> None:
        """Hand the keys back to the window, so its own shortcuts work again."""
        self._window.makeFirstResponder_(self._content)
        self.bar.focused = False

    def changed(self) -> None:
        text = str(self.field.stringValue())
        kept = capped(text)
        if kept != text:
            self.field.setStringValue_(kept)
        self.bar.editor.text, self.bar.editor.caret = kept, len(kept)
        self.bar.took_key()
        self.on_change()

    def editing(self) -> None:
        """Editing began or ended: redraw, so the field's focus stroke follows."""
        self.on_change()


def attach(
    glfw_window,
    bar: PromptBar,
    on_send: Callable[[], None],
    on_change: Callable[[], None],
) -> NativeField | None:
    """A native field over *bar* on macOS, else None (the drawn field stays)."""
    if sys.platform != "darwin":
        return None
    try:
        import glfw

        pointer = glfw.get_cocoa_window(glfw_window)
        ns_window = _pyobjc("objc").objc_object(c_void_p=ctypes.c_void_p(pointer))
        return NativeField(ns_window, bar, on_send, on_change)
    except Exception as exc:  # a missing PyObjC or Cocoa window: draw the field
        print(f"[prompt] native field unavailable, drawing it: {exc}")
        return None


def _ns_color(NSColor, argb: int):
    a, r, g, b = (argb >> 24 & 255, argb >> 16 & 255, argb >> 8 & 255, argb & 255)
    return NSColor.colorWithSRGBRed_green_blue_alpha_(
        r / 255, g / 255, b / 255, a / 255
    )


def _pyobjc(name: str) -> Any:
    """A PyObjC module. Its classes are made at run time, so no checker sees them."""
    return importlib.import_module(name)


_DELEGATE = None


def _delegate_class():
    """The control's delegate, defined once: an Objective-C class name is
    process-wide, and AppKit is imported only when a field is made."""
    global _DELEGATE
    if _DELEGATE is None:
        objc = _pyobjc("objc")

        class MD2UIPromptFieldDelegate(_pyobjc("Foundation").NSObject):
            owner: NativeField

            def controlTextDidChange_(self, _note) -> None:
                self.owner.changed()

            def controlTextDidBeginEditing_(self, _note) -> None:
                self.owner.editing()

            def controlTextDidEndEditing_(self, _note) -> None:
                self.owner.editing()

            @objc.typedSelector(b"Z@:@@:")
            def control_textView_doCommandBySelector_(self, _control, _view, command):
                if command in ("insertNewline:", b"insertNewline:"):
                    self.owner.on_send()
                    self.owner.on_change()  # the sent text leaves the control
                    return True
                if command in ("cancelOperation:", b"cancelOperation:"):
                    self.owner.blur()
                    self.owner.on_change()
                    return True
                return False

        _DELEGATE = MD2UIPromptFieldDelegate
    return _DELEGATE
