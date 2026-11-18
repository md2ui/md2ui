"""
Unit tests for the recorded document the window replays (render_picture).

The window records ``draw_document`` once per scene and replays it every frame
through the viewport clip; the picture's R-tree is what culls. Two facts make
that safe, and each is pinned here:

  * culling never drops visible ink — in particular a shadow cast by a box that
    lies OUTSIDE the viewport still reaches into it after a replay, because the
    R-tree bounds each draw by its own blur, not by the box;
  * the recording is reused only while its key holds — the same objects (by
    identity) and the same values (by equality) — and every part of the key,
    including each display toggle the document reads, forces a new recording.

Run with: uv run python tests/render_picture_tests.py
"""

import skia

from md2ui.pipeline.render_picture import DocumentPicture, record, view_state
from md2ui.pipeline.render_settings import VIEW
from md2ui.pipeline.render_shadows import paint_shadows
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import ShadowSpec, Theme
from md2ui.utils.image_cache import ImageCache

# A 200x100 viewport over a document scrolled down by 60px. The card sits at
# document y 170..250, i.e. viewport y 110..190: wholly BELOW the viewport. Its
# outer shadow is moved 50px up and blurred over 40px, so it reaches viewport
# y ~40 — well inside.
_VIEW_W, _VIEW_H = 200, 100
_SCROLL_Y = 60.0
_CARD = skia.Rect.MakeXYWH(40.0, 170.0, 120.0, 80.0)
_SHADOW = ShadowSpec(offset_y=-50.0, radius=40.0, color=0xFF000000)


def _paint_card(canvas: skia.Canvas) -> None:
    paint_shadows(canvas, _CARD, 12.0, [_SHADOW], inner=False)
    canvas.drawRoundRect(_CARD, 12.0, 12.0, skia.Paint(Color=0xFFFFFFFF))


def _frame(paint_document) -> bytes:
    surface = skia.Surface(_VIEW_W, _VIEW_H)
    canvas = surface.getCanvas()
    canvas.clear(0xFFFFFFFF)
    canvas.save()
    canvas.clipRect(skia.Rect.MakeWH(_VIEW_W, _VIEW_H))
    canvas.translate(0.0, -_SCROLL_Y)
    paint_document(canvas)
    canvas.restore()
    return surface.makeImageSnapshot().tobytes()


def test_replay_keeps_a_shadow_cast_from_outside_the_viewport():
    direct = _frame(_paint_card)
    picture = record(_paint_card, _VIEW_W, 400.0)
    replayed = _frame(lambda canvas: canvas.drawPicture(picture))
    blank = _frame(lambda canvas: None)
    assert direct != blank, (
        "the shadow must reach into the viewport, or this proves nothing"
    )
    assert replayed == direct, "the replay culled ink the viewport shows"
    print("  ✓  a shadow cast from outside the viewport survives the replay")


def test_the_same_key_replays_without_recording():
    cache = DocumentPicture()
    scene = object()
    calls = []

    def rec():
        calls.append(1)
        return record(lambda c: None, 10, 10)

    first = cache.get((scene,), (0, "a"), rec)
    second = cache.get((scene,), (0, "a"), rec)
    assert first is second and len(calls) == 1 and cache.recordings == 1
    print("  ✓  the same key replays the cached picture without recording")


def test_each_part_of_the_key_records_again():
    cache = DocumentPicture()

    def rec():
        return record(lambda c: None, 10, 10)

    scene = []
    cache.get((scene,), (0,), rec)
    cache.get((scene,), (1,), rec)  # a value moved: an image landed
    assert cache.recordings == 2
    cache.get(([],), (1,), rec)  # an EQUAL but distinct object: a new scene
    assert cache.recordings == 3
    cache.get(([], object()), (1,), rec)  # the key's shape changed
    assert cache.recordings == 4
    print("  ✓  a new object, an equal-but-distinct one, or a new value records again")


def test_view_state_names_every_toggle_the_document_reads():
    toggles = (
        "wireframe",
        "debug_spacing",
        "debug_padding",
        "text_boxes",
        "placeholder_images",
    )
    for name in toggles:
        before = view_state()
        setattr(VIEW, name, not getattr(VIEW, name))
        try:
            assert view_state() != before, (
                f"flipping {name} must re-record the document"
            )
        finally:
            setattr(VIEW, name, not getattr(VIEW, name))
    # The host's per-node state (pending, an optimistic tick) is painted too.
    before = view_state()
    prev_states = VIEW.node_states
    VIEW.node_states = {"0.1": "pending"}
    try:
        assert view_state() != before, "host node state must re-record the document"
    finally:
        VIEW.node_states = prev_states
    # The pixel ratio decides the size each photo is decoded at.
    before = view_state()
    VIEW.pixel_ratio = 2.0
    try:
        assert view_state() != before, "a new pixel ratio must re-record the document"
    finally:
        VIEW.pixel_ratio = 1.0
    before = view_state()
    VIEW.show_frame = not VIEW.show_frame
    try:
        assert view_state() == before, (
            "the chrome is outside the document; it must not re-record"
        )
    finally:
        VIEW.show_frame = not VIEW.show_frame
    print("  ✓  every document toggle is in the key, and the chrome toggle is not")


def test_document_records_once_per_scene_and_again_when_an_image_lands():
    typeface = skia.Typeface.MakeFromName("Helvetica", skia.FontStyle.Normal())
    fonts = FontSet(typeface, typeface, typeface, typeface, typeface)
    cache, images, theme = DocumentPicture(), ImageCache(), Theme()
    # Held once, as a scene holds them: the key compares these by IDENTITY, so a
    # caller that rebuilt them on every frame would record on every frame.
    boxes: list = []
    sections: list = []
    node_index: dict = {}
    backgrounds: dict = {}

    def get(the_boxes, generation):
        return cache.document(
            the_boxes,
            sections,
            node_index,
            100.0,
            50.0,
            fonts,
            images,
            theme,
            None,
            backgrounds,
            generation,
        )

    first = get(boxes, 0)
    assert get(boxes, 0) is first and cache.recordings == 1, "a replay must not record"
    get(boxes, 1)
    assert cache.recordings == 2, "an image landing must record again"
    get([], 1)
    assert cache.recordings == 3, "a new scene's boxes must record again"
    print("  ✓  document() records once per scene, and again when an image lands")


TESTS = [
    test_replay_keeps_a_shadow_cast_from_outside_the_viewport,
    test_the_same_key_replays_without_recording,
    test_each_part_of_the_key_records_again,
    test_view_state_names_every_toggle_the_document_reads,
    test_document_records_once_per_scene_and_again_when_an_image_lands,
]

if __name__ == "__main__":
    print("Render Picture Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
