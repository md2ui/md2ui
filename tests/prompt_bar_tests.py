"""
Unit tests for the demo window's chrome (ADR-601): the prompt bar, its own
style, and the animation it plays while the agent works.

Pinned here:

  * the editor types, pastes (a line break becomes a space), moves, deletes and
    stops at the wire's prompt size; ``take`` empties it and never returns blanks;
  * while the field has focus every key is the field's, so the window's
    one-letter shortcuts never fire mid-sentence; Enter sends, Esc leaves;
  * while the agent works, typing and Send do nothing. The window blocks itself
    only after sending to a LISTENING agent, and the server's next state wins;
  * before any state arrives, a draft is kept, never sent;
  * each key the field takes says the user is typing, but not Enter, Esc, or a
    key while the agent works; the wire hears it at most once a second;
  * an unsent draft says so each tick through a pause, so a grace waits for a
    reply still being written; an empty field, or one the agent locked, does not;
  * the Send button, the field and the bar are hit where they are drawn;
  * the bar is painted from the window's own ``ChromeStyle``, never THEME.md;
  * the working animation comes from a FILE: the default decodes to its frames,
    loops, and draws; a missing or undecodable file is refused, not a crash;
  * the viewport ends above the bar, so the document never runs under it;
  * what the window sends while nobody listens (``i``) is counted, clicks and
    messages alike, and said in a notice above the bar only once ``i`` has lasted
    two seconds; leaving ``i`` clears it, and nothing is counted outside ``i``;
  * only what waits for an agent is counted: not a click a commit press reports,
    and a click leaves the count when the server releases it (``u``).

Run with: uv run python tests/prompt_bar_tests.py
"""

import tempfile
import time
from pathlib import Path

import glfw
import skia

from md2ui.app_chrome import DEFAULT_ANIMATION, ChromeStyle, WorkingAnimation
from md2ui.app_prompt import (
    NOTICE_DELAY_S,
    PLACEHOLDERS,
    PromptBar,
    PromptText,
    QueuedNotice,
)
from md2ui.pipeline.layout_render import _viewport_metrics
from md2ui.pipeline.render_settings import VIEW
from md2ui.wire import MAX_PROMPT_BYTES
from md2ui.wire_client import Throttle

BAR_H = ChromeStyle().bar_h


def _bar(style: ChromeStyle | None = None) -> PromptBar:
    return PromptBar(skia.Typeface.MakeDefault(), style)


def _canvas(w: int, h: int) -> tuple[skia.Bitmap, skia.Canvas]:
    bitmap = skia.Bitmap()
    bitmap.allocPixels(skia.ImageInfo.MakeN32Premul(w, h))
    bitmap.eraseARGB(0, 0, 0, 0)
    return bitmap, skia.Canvas(bitmap)


def test_the_editor_types_pastes_and_stops_at_the_cap():
    e = PromptText()
    e.insert("Hello world")
    e.move(5)
    e.insert(",")
    assert (e.text, e.caret) == ("Hello, world", 6), (e.text, e.caret)
    e.backspace()
    e.delete()
    assert e.text == "Helloworld", e.text
    e.move(99)
    e.insert("\nagain\n")
    assert e.text == "Helloworld again", e.text
    e.insert("x" * (MAX_PROMPT_BYTES + 50))
    assert len(e.text.encode()) == MAX_PROMPT_BYTES
    assert e.take() and (e.text, e.caret) == ("", 0)
    e.insert("   ")
    assert e.take() == "" and e.text == "   ", "a blank is never sent"
    print("  ✓  the editor: type, paste, move, delete, cap, take")


def test_every_key_is_the_focused_fields():
    bar = _bar()
    bar.focused = True
    bar.sync("l")
    for ch in "Hi":
        assert bar.on_char(ord(ch))
    assert bar.on_key(glfw.KEY_W, 0) == "edit", "the wireframe shortcut is swallowed"
    assert bar.on_key(glfw.KEY_BACKSPACE, 0) == "edit" and bar.editor.text == "H"
    bar.paste = lambda: b"ello\nthere"
    assert bar.on_key(glfw.KEY_V, glfw.MOD_SUPER) == "edit"
    assert bar.editor.text == "Hello there", bar.editor.text
    assert bar.on_key(glfw.KEY_ENTER, 0) == "send"
    assert bar.submit() == "Hello there" and bar.editor.text == ""
    assert bar.on_key(glfw.KEY_ESCAPE, 0) == "blur" and not bar.focused
    assert not bar.on_char(ord("x")), "an unfocused field takes nothing"
    print("  ✓  focused: keys are the field's; Enter sends, Esc leaves")


def test_input_is_blocked_only_while_the_agent_works():
    bar = _bar()
    bar.focused = True
    assert bar.sync("l") and bar.state == "l"
    bar.editor.insert("Next")
    bar.lock_for_reply()
    assert bar.locked
    assert (
        not bar.on_char(ord("x")) and bar.submit() == "" and bar.editor.text == "Next"
    )
    assert not bar.sync("l"), "the server's unchanged state does not undo the lock"
    assert bar.sync("w") and bar.locked
    assert bar.sync("i") and not bar.locked
    bar.lock_for_reply()
    assert not bar.locked, "nobody listens: a self-lock would never end"
    print("  ✓  the lock: working blocks input; idle never self-locks")


def test_nothing_is_sent_before_the_agent_is_heard():
    """A server that never says what the agent is doing may not take prompts at
    all (one from before ADR-601 refuses them): the draft waits in the field."""
    bar = _bar()
    bar.focused = True
    assert bar.state is None and bar.on_char(ord("H")), "a draft may be typed"
    assert bar.submit() == "" and bar.editor.text == "H", "and it stays in the field"
    bar.lock_for_reply()
    assert bar.state is None, "nor does the window lock itself"
    assert bar.sync("i") and bar.submit() == "H", "once a state arrives, it goes"
    print("  ✓  before any state: type, but nothing is sent or lost")


def test_the_parts_are_hit_where_they_are_drawn():
    bar, w, h = _bar(), 800.0, 600.0
    y = h - BAR_H / 2
    assert bar.hit(w - 20, y, w, h) == "send"
    assert bar.hit(100, y, w, h) == "field"
    assert bar.hit(4, y, w, h) == "bar"
    assert bar.hit(100, h - BAR_H - 1, w, h) is None
    print("  ✓  hits: Send, the field, the bar, and nothing above it")


def test_the_bar_is_painted_from_the_windows_own_style():
    bar = _bar(ChromeStyle(bar_bg=0xFF112233))
    bitmap, canvas = _canvas(400, 200)
    for state in PLACEHOLDERS:
        bar.state = state
        bar.draw(canvas, 400, 200)
    assert bitmap.getColor(2, 195) == 0xFF112233, hex(bitmap.getColor(2, 195))
    print("  ✓  the bar paints its ChromeStyle; every state draws")


def test_the_working_animation_comes_from_a_file():
    # The asset is replaceable artwork, so this checks what any of it must
    # do, never its frame count: several frames, each lasting what the file says.
    anim = WorkingAnimation.load(DEFAULT_ANIMATION)
    assert anim is not None and len(anim.frames) > 1, anim
    assert len(anim.durations) == len(anim.frames), anim.durations
    assert abs(anim.period - sum(anim.durations)) < 1e-6, anim.period
    first, later = anim.frame_at(0.0), anim.frame_at(0.3)
    assert first.tobytes() != later.tobytes(), "the frames differ: it moves"
    assert anim.frame_at(anim.period + 0.01) is first, "and it loops"
    bitmap, canvas = _canvas(200, 200)
    anim.draw(canvas, 100, 100, 96, 0.0)
    inked = bitmap.getColor(100, 100 + 36)  # inside the 96 px it is drawn at
    assert (inked >> 24) & 0xFF > 0, hex(inked)
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "not-an-image.webp"
        bad.write_text("hello")
        assert WorkingAnimation.load(bad) is None
        assert WorkingAnimation.load(Path(tmp) / "missing.webp") is None
    print(
        "  ✓  the working animation: decoded from its file, loops, draws; bad files refused"
    )


def test_the_viewport_ends_above_the_bar():
    before = _viewport_metrics(800, 600)
    VIEW.prompt_bar_h = BAR_H
    try:
        after = _viewport_metrics(800, 600)
    finally:
        VIEW.prompt_bar_h = 0.0
    assert after[:3] == before[:3] and after[3] == before[3] - BAR_H, (before, after)
    print("  ✓  the viewport ends above the bar")


def test_a_repeated_state_frame_still_releases_a_self_lock():
    """`lock_for_reply` blocks on send, before the server's `w`. When the event is
    REFUSED there is no `w`, and the server re-states the state it is already in —
    so the bar must act on a frame ARRIVING, not on the value differing."""
    bar = PromptBar(skia.Typeface.MakeDefault())
    assert bar.sync("l", 1) and bar.state == "l"
    bar.lock_for_reply()
    assert bar.locked, "the window blocks itself on send"

    assert not bar.sync("l", 1), "the same frame twice is not an arrival"
    assert bar.locked, "and must not disturb the lock"

    assert bar.sync("l", 2), "the server saying `l` again IS an arrival"
    assert not bar.locked, "which releases the self-lock"
    print("  ✓  a re-sent state releases a window that blocked itself on send")


def test_input_queued_while_nobody_listens_is_said_after_a_moment():
    """In `i` a click turns its button pending and a prompt leaves the field, so
    the notice says they wait for the chat. The short `i` between one wait and
    the next must never flash it, so it shows only once `i` has lasted two
    seconds."""
    notice = QueuedNotice()
    assert notice.text(100.0) is None
    notice.click(0, 10.0)
    assert notice.text(10.0 + NOTICE_DELAY_S - 0.1) is None, "not at once"
    assert notice.text(10.0 + NOTICE_DELAY_S) == (
        "1 click queued — the agent will see it when you say “check md2ui” in the chat"
    ), notice.text(12.0)
    notice.click(1, 13.0)
    notice.message(14.0)
    assert (notice.text(14.0) or "").startswith(
        "2 clicks and 1 message queued — the agent will see them"
    ), notice.text(14.0)
    notice.clear()
    notice.message(20.0)
    notice.message(20.5)
    assert (notice.text(20.0 + NOTICE_DELAY_S) or "").startswith("2 messages queued"), (
        notice
    )

    bar = _bar()
    assert bar.sync("l", 1, now=0.0)
    bar.sent("click", now=0.0)
    assert bar.locked and bar.notice.first is None, "a listening agent hears it"
    assert bar.sync("i", 2, now=1.0) and not bar.locked
    bar.sent("click", now=1.0, x=3)
    bar.sent("message", now=1.5)
    assert not bar.sync("i", 2, now=2.9), "nothing to redraw before the delay"
    assert bar.sync("i", 2, now=3.0), "the notice coming due redraws the bar"
    assert not bar.sync("i", 2, now=3.5), "and only once"
    assert (bar.notice.text(3.0) or "").startswith("1 click and 1 message queued")
    assert bar.sync("l", 3, now=4.0) and bar.notice.text(9.0) is None, "cleared"
    assert bar.sync("i", 4, now=5.0) and bar.notice.text(99.0) is None, "fresh in i"

    w, h = 900, 300
    bitmap, canvas = _canvas(w, h)
    bar.draw(canvas, w, h)
    pill_y = int(h - BAR_H - 8 - 16)
    assert bitmap.getColor(20, pill_y) == 0, "no notice before anything is queued"
    bar.notice.click(0, time.monotonic() - NOTICE_DELAY_S - 1)
    bar.draw(canvas, w, h)
    painted = bitmap.getColor(20, pill_y)
    assert painted >> 24 and (painted >> 16) & 0xFF < 0x30, hex(painted)  # dark pill
    print(
        "  ✓  input queued in i is said above the bar after two seconds, until i ends"
    )


def test_the_field_says_the_user_is_typing_throttled():
    """The grace waits for a user who is typing, so the bar
    reports each key its field takes, and the wire client sends that on at most
    once a period: the first at once, then none until the period has passed."""
    gate = Throttle(1.0)
    said = [t for t in (0.0, 0.3, 0.99, 1.0, 1.5, 2.2, 2.3) if gate.due(t)]
    assert said == [0.0, 1.0, 2.2], said

    keys: list[str] = []
    bar = PromptBar(skia.Typeface.MakeDefault(), typed=lambda: keys.append("k"))
    bar.sync("l", 1)
    bar.focused = True
    assert bar.on_char(ord("a")) and keys == ["k"], keys
    assert bar.on_key(glfw.KEY_BACKSPACE, 0) == "edit" and len(keys) == 2, keys
    assert bar.on_key(glfw.KEY_ENTER, 0) == "send" and len(keys) == 2, keys
    bar.lock_for_reply()
    assert not bar.on_char(ord("b")) and len(keys) == 2, "nothing while it works"
    bar.on_key(glfw.KEY_ESCAPE, 0)
    assert len(keys) == 2, keys
    print("  ✓  the field says the user is typing, and the wire hears it throttled")


def test_an_unsent_draft_keeps_the_user_typing():
    """A pause while composing must not end the grace: the
    loop calls `composing` each tick, and a draft in the field says typing."""
    keys: list[str] = []
    bar = PromptBar(skia.Typeface.MakeDefault(), typed=lambda: keys.append("k"))
    bar.sync("l", 1)
    bar.focused = True
    bar.composing()
    bar.on_char(ord(" "))
    keys.clear()
    bar.composing()
    assert keys == [], "an empty or blank field is not a draft"
    bar.on_char(ord("a"))
    keys.clear()
    bar.composing()
    bar.composing()
    assert keys == ["k", "k"], keys  # the wire's Throttle spaces them
    bar.lock_for_reply()
    bar.composing()
    assert len(keys) == 2, "nothing while the agent works"
    print("  ✓  an unsent draft keeps the user typing through a pause")


def test_only_clicks_an_agent_waits_for_are_counted():
    """In `i`, a click the backend answered, a choice and two count steps, then
    the commit press, must not say "5 clicks queued" when one waits for Claude.
    A choice or a count step a commit press reports is recorded for it (the
    window passes no ordinal), and a click the server releases with `u` was
    answered: neither is counted."""
    bar = _bar()
    assert bar.sync("i", 1, now=0.0)
    bar.sent("click", now=0.0, x=2)  # the backend answers it ...
    bar.sent("click", now=0.5, x=None)  # a choice, then two count steps
    bar.sent("click", now=0.6, x=None)
    bar.sent("click", now=0.7, x=None)
    bar.notice.release([2])  # ... and the server's `u` names it
    assert bar.notice.first is None, "nothing waits: no notice is due"
    bar.sent("click", now=1.0, x=7)  # the commit press
    assert bar.notice.text(1.0 + NOTICE_DELAY_S) == (
        "1 click queued — the agent will see it when you say “check md2ui” in the chat"
    ), bar.notice.text(1.0 + NOTICE_DELAY_S)
    bar.sent("click", now=1.2, x=7)  # pressed again: two clicks on one ordinal
    bar.notice.release([7])
    assert (bar.notice.text(9.0) or "").startswith("1 click queued"), "one at a time"
    print("  ✓  only clicks an agent waits for are counted")


TESTS = [
    test_the_field_says_the_user_is_typing_throttled,
    test_an_unsent_draft_keeps_the_user_typing,
    test_a_repeated_state_frame_still_releases_a_self_lock,
    test_the_editor_types_pastes_and_stops_at_the_cap,
    test_every_key_is_the_focused_fields,
    test_input_is_blocked_only_while_the_agent_works,
    test_nothing_is_sent_before_the_agent_is_heard,
    test_the_parts_are_hit_where_they_are_drawn,
    test_the_bar_is_painted_from_the_windows_own_style,
    test_the_working_animation_comes_from_a_file,
    test_the_viewport_ends_above_the_bar,
    test_input_queued_while_nobody_listens_is_said_after_a_moment,
    test_only_clicks_an_agent_waits_for_are_counted,
]

if __name__ == "__main__":
    print("Prompt Bar Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
