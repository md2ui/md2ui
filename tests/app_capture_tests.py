"""
Unit tests for the capture channel (``app_capture``): the agent asks the window
for a screenshot, and the window answers.

The window itself is not launched — the two ends talk through files in a
directory, so the window's half is driven here by hand, which is the point: the
channel is verifiable without a GPU.

Pinned here:

  * a request is seen exactly once, so answering it cannot spin the window's loop,
    and one that arrived while the window was still opening is not lost, nor one
    written in the same clock tick as the last;
  * the answer reaches the asker as PNG bytes, and never as a half-written file;
  * a refusal comes back as ``CaptureError`` carrying the window's reason, and a
    window that says nothing at all times out with a reason of its own — the two
    cases a closed window has to be told apart by;
  * a malformed request is dropped rather than retried, and an unknown mode falls
    back to ``view`` instead of failing the capture.

Run with: uv run python tests/app_capture_tests.py
"""

import os
import tempfile
import threading
from pathlib import Path

import skia

from md2ui.app_capture import CaptureChannel, CaptureError, ask, capture, shrink


def _image(width: int = 4, height: int = 4) -> skia.Image:
    """A tiny CPU image: the channel only encodes, it never draws."""
    surface = skia.Surface.MakeRasterN32Premul(width, height)
    with surface as canvas:
        canvas.clear(skia.ColorRED)
    return surface.makeImageSnapshot()


def _window(directory: Path, respond, ready: threading.Event) -> threading.Thread:
    """The window's half of the loop: poll, answer once, stop."""
    channel = CaptureChannel(directory)

    def run() -> None:
        ready.set()
        for _ in range(500):  # 5 s at the poll below
            request = channel.pending()
            if request is not None:
                respond(channel, request)
                return
            threading.Event().wait(0.01)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_a_request_is_seen_once():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        channel = CaptureChannel(directory)
        assert channel.pending() is None, "nothing asked yet"
        ask(directory, directory / "shot.png", "document")
        first = channel.pending()
        assert first is not None and first.mode == "document", first
        assert first.out == (directory / "shot.png").resolve(), first.out
        assert channel.pending() is None, "the same request came back twice"
    print("  ✓  a request is read once, with its mode and destination")


def test_a_request_that_beat_the_window_is_still_answered():
    """The window takes seconds to open, so the first capture is usually asked
    for before its channel exists; that request must still be answered."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        ask(directory, directory / "shot.png", "view")  # the window is not up yet
        channel = CaptureChannel(directory)  # ... and now it is
        request = channel.pending()
        assert request is not None, "the request that arrived first was lost"
        assert request.out == (directory / "shot.png").resolve(), request.out
    print("  ✓  a request that arrived before the window started is answered")


def test_a_request_in_the_same_clock_tick_is_still_new():
    """Linux stamps mtimes once per kernel tick (1 ms in Docker), so two requests
    written back to back can carry the same mtime; the second must still be
    seen. Pinned here on every platform by giving both the same stamp."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        channel = CaptureChannel(directory)
        ask(directory, directory / "a.png", "view")
        os.utime(directory / "request.json", ns=(10**18, 10**18))
        assert channel.pending() is not None, "the first request was missed"
        ask(directory, directory / "b.png", "document")
        os.utime(directory / "request.json", ns=(10**18, 10**18))
        second = channel.pending()
        assert second is not None, "a request with the last one's mtime was missed"
        assert second.out == (directory / "b.png").resolve(), second.out
    print("  ✓  a request written in the same clock tick as the last is still seen")


def test_the_answer_arrives_as_png():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        ready = threading.Event()
        thread = _window(directory, lambda ch, req: ch.answer(req, _image()), ready)
        ready.wait(2)
        data = capture(directory, directory / "shot.png", "view", 5.0)
        thread.join(timeout=2)
    assert data[:8] == b"\x89PNG\r\n\x1a\n", data[:8]
    assert skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(data)) is not None
    print("  ✓  the capture comes back as decodable PNG bytes")


def test_a_refusal_says_why_and_a_silence_says_so_too():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        ready = threading.Event()
        thread = _window(directory, lambda ch, req: ch.answer(req, None), ready)
        ready.wait(2)
        try:
            capture(directory, directory / "shot.png", "view", 5.0)
            raise AssertionError("a refused capture returned bytes")
        except CaptureError as exc:
            assert "encode" in str(exc), exc
        thread.join(timeout=2)

        # Nobody is watching this directory at all: the window is closed.
        try:
            capture(directory, directory / "quiet.png", "view", 0.2)
            raise AssertionError("an unanswered capture returned bytes")
        except CaptureError as exc:
            assert "did not answer" in str(exc), exc
    print("  ✓  a refusal carries its reason; a silent window times out saying so")


def test_a_bad_request_is_dropped_and_a_bad_mode_falls_back():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        channel = CaptureChannel(directory)
        (directory / "request.json").write_text("{not json")
        assert channel.pending() is None, "a malformed request was acted on"
        assert channel.pending() is None, "a malformed request was retried"

        (directory / "request.json").write_text(
            '{"out": "' + str(directory / "s.png") + '", "mode": "nonsense"}'
        )
        request = channel.pending()
        assert request is not None and request.mode == "view", request

        try:
            ask(directory, directory / "s.png", "nonsense")
            raise AssertionError("the asker sent an unknown mode")
        except CaptureError as exc:
            assert "view" in str(exc), exc
    print("  ✓  a malformed request is dropped once; an unknown mode is refused")


def test_a_look_is_small_unless_asked():
    """An agent pays for a picture by its area, so `screenshot` returns one 480
    px wide unless asked: the layout, the buttons and loaded pictures are still
    plain at that size. A narrower picture, or a width of 0, is left alone."""

    def png(w: int, h: int) -> bytes:
        surface = skia.Surface(w, h)
        surface.getCanvas().clear(skia.ColorWHITE)
        return bytes(surface.makeImageSnapshot().encodeToData())

    def size(data: bytes) -> tuple[int, int]:
        image = skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(data))
        return image.width(), image.height()

    assert size(shrink(png(1000, 500), 480)) == (480, 240)
    narrow = png(300, 200)
    assert shrink(narrow, 480) == narrow
    assert shrink(png(1000, 500), 0) == png(1000, 500)
    print("  ✓  a look is 480 px wide unless asked; narrower pictures are untouched")


TESTS = [
    test_a_request_is_seen_once,
    test_a_request_that_beat_the_window_is_still_answered,
    test_a_request_in_the_same_clock_tick_is_still_new,
    test_the_answer_arrives_as_png,
    test_a_refusal_says_why_and_a_silence_says_so_too,
    test_a_bad_request_is_dropped_and_a_bad_mode_falls_back,
    test_a_look_is_small_unless_asked,
]

if __name__ == "__main__":
    print("App Capture Tests")
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
    print("All app capture tests passed.")
