"""
Tests for the lifetime of ``LayoutGenerator._block_w_cache``, the Stack-sections width ask.

The window keeps ONE generator for its lifetime and rebuilds with it on every resize and
every reload. A layout depends only on the document, the theme and the width, never on
what the generator laid out before, yet the cache survives a resize, because that is what
it is for: each ask is kept with the width it was offered. It is keyed by ``node_id``, a
POSITION in the tree, so it must not survive a new document or a new theme. Pinned here:

* a generator reused across an id-shifting edit places the edited document exactly as a
  fresh generator does;
* a generator reused through a resize, narrowing and then widening, places every width
  exactly as a fresh generator does;
* the same document and theme keep the cache across widths; a new document or a new
  theme object empties it.

All go through the real pipeline, as the window does. The fixtures are corpus documents
because small hand-written ones grid as repeated sections instead of packing them, and
each test asserts the cache was filled, so a change to a fixture fails loudly instead of
passing without testing anything. A block can ask less when offered less even though it
already fits, which is why no ask is reused at another width.

Run with: uv run tests/block_width_cache_tests.py
"""

from pathlib import Path

from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator

# Its stacked blocks fill the cache, and a leaked cache misplaces its boxes
# after the edit below.
_DOC = Path("data/markdown/tests/tests-image-spacing.md")
_THEME = Path("data/markdown/tests/THEME.md")
# (document, theme) walked through _WALK on one generator.
_RESIZE_DOCS = (
    # Its blocks ask less at 400 than at 600, so a width carried over shows at once.
    (
        Path(
            "data/markdown/tests-render/banking-financial/figma-ai-generated-banking-dashboard/content.md"
        ),
        _THEME,
    ),
    # A THEME.md renders as the Markdown it is, themed by itself.
    (_THEME, _THEME),
)
_WALK = (1280.0, 1013.0, 767.0, 600.0, 400.0, 600.0, 767.0, 1013.0, 1280.0)
# Prepended, it moves every node_id of the document below it.
_EDIT = "## Added first\n\nSome body text here.\n\n"
_KIT: list = []


def _scene(gen: LayoutGenerator, text: str, width: float = 1280.0):
    if not _KIT:
        theme = session.load_theme(_THEME)
        _KIT.extend([session.load_grouping_kit(), theme, session.load_fonts(theme)])
    kit, theme, fonts = _KIT
    grouped = session.group_markdown(text, kit)
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    return session.build_scene(gen, root, index, theme, fonts, width), root, index


def _boxes(scene) -> list[tuple]:
    return [
        (
            round(b.x, 1),
            round(b.y, 1),
            round(b.width, 1),
            round(b.height, 1),
            b.content_id,
        )
        for b in scene.boxes
    ]


def test_a_reload_with_shifted_ids_places_as_a_fresh_generator_does():
    text = _DOC.read_text()
    reused = LayoutGenerator()
    _scene(reused, text)
    assert reused._block_w_cache, f"{_DOC} no longer fills the cache; pick another"
    edited = _EDIT + text
    got = _boxes(_scene(reused, edited)[0])
    want = _boxes(_scene(LayoutGenerator(), edited)[0])
    differ = sum(a != b for a, b in zip(got, want)) + abs(len(got) - len(want))
    assert differ == 0, f"{differ} of {len(want)} boxes placed from stale widths"
    print("  ✓  a reload with shifted ids places as a fresh generator does")


def _prepared(doc: Path, theme_path: Path, theme=None):
    if not _KIT:
        _scene(LayoutGenerator(), "# warm")
    theme = theme or session.load_theme(theme_path)
    grouped = session.group_markdown(doc.read_text(), _KIT[0])
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    return root, index, theme, session.load_fonts(theme)


def test_a_resize_places_as_a_fresh_generator_does():
    for doc, theme_path in _RESIZE_DOCS:
        root, index, theme, fonts = _prepared(doc, theme_path)
        reused = LayoutGenerator()
        for width in _WALK:
            got = _boxes(session.build_scene(reused, root, index, theme, fonts, width))
            fresh = LayoutGenerator()
            want = _boxes(session.build_scene(fresh, root, index, theme, fonts, width))
            assert fresh._block_w_cache, (
                f"{doc} no longer fills the cache; pick another"
            )
            differ = sum(a != b for a, b in zip(got, want)) + abs(len(got) - len(want))
            assert differ == 0, (
                f"{doc} at {width:g}: {differ} of {len(want)} boxes placed from an "
                "earlier width"
            )
    print("  ✓  a resize places as a fresh generator does")


def test_a_new_document_or_theme_empties_the_cache():
    doc, theme_path = _RESIZE_DOCS[0]
    root, index, theme, fonts = _prepared(doc, theme_path)
    gen = LayoutGenerator()
    session.build_scene(gen, root, index, theme, fonts, 600.0)
    cache = gen._block_w_cache
    assert cache, f"{doc} no longer fills the cache; pick another"
    measured = dict(cache)
    session.build_scene(gen, root, index, theme, fonts, 900.0)
    assert gen._block_w_cache is cache, "the same document at a new width dropped it"
    assert all(cache[k] == v for k, v in measured.items()), "an entry was re-measured"
    # The same text grouped again is a new document object.
    root2, index2, _, _ = _prepared(doc, theme_path, theme)
    session.build_scene(gen, root2, index2, theme, fonts, 600.0)
    assert gen._block_w_cache is not cache, "a new document kept the old cache"
    cache = gen._block_w_cache
    # The same file loaded again is a new theme object, as a live theme reload is.
    theme2 = session.load_theme(theme_path)
    session.build_scene(gen, root2, index2, theme2, fonts, 600.0)
    assert gen._block_w_cache is not cache, "a new theme kept the old cache"
    print("  ✓  a new document or theme empties the cache")


TESTS = [
    test_a_reload_with_shifted_ids_places_as_a_fresh_generator_does,
    test_a_resize_places_as_a_fresh_generator_does,
    test_a_new_document_or_theme_empties_the_cache,
]

if __name__ == "__main__":
    print("Block Width Cache Tests")
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
