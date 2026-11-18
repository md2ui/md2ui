"""
Unit tests for the icon aside's structural scope. The gate is node-kind
agnostic — when a theme asks for ``Emoji aside``, every group node is a
candidate, heading sections included — so these check the invariants that
hold: a theme asking everywhere cannot change heading-section nesting, leaf
order or the bento mosaic.
Run with: uv run layout_decision_scope_tests.py
"""

from layout_bento_tests import _ast, _group, _leaf
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.theme import Theme


def aside_theme(theme=None):
    """*theme* (else a default one) asking for an icon gutter on ``### Elements``
    — enough to open the aside gate for the whole document."""
    theme = theme or Theme()
    theme.elements.emoji_aside = True
    return theme


class RecordingGenerator(LayoutGenerator):
    """Records every node the icon aside is consulted on."""

    def __init__(self):
        super().__init__()
        self.consulted = []

    def _decide_group_icon_aside(
        self, node, available_width, parent, in_glued=True, owner_level=0
    ):
        self.consulted.append(node)
        return super()._decide_group_icon_aside(
            node, available_width, parent, in_glued, owner_level
        )


def _doc():
    """h1 section holding glued+leaf-ish h2 sections, each with an inner glued
    content group — both heading slip-through paths the gate must exclude."""
    secs = []
    for i in range(4):
        content = _group(
            _leaf(f"alpha text {i}"),
            _leaf(f"beta text {i}"),
            glued_content_group=True,
        )
        secs.append(
            _group(
                _leaf(f"Heading two {i}", "very_short"),
                content,
                heading_group=True,
                heading_level=2,
                glued_content_group=True,  # heading AND glued: must stay rules
            )
        )
    return _ast(
        _group(
            _group(
                _leaf("Heading one", "very_short"),
                *secs,
                heading_group=True,
                heading_level=1,
            )
        )
    )


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _leaves(n):
    return [x.content_id for x in _walk(n) if x.type == "-"]


def _bento_skeleton(layout):
    """Structural fingerprint of the mosaic: bento nodes + section levels."""
    return [
        (n.type, tuple(n.ratios) if n.bento else None, n.section_level)
        for n in _walk(layout)
        if n.bento or n.section_level is not None
    ]


def _section_trace(layout):
    return [n.section_level for n in _walk(layout) if n.section_level is not None]


def test_the_aside_is_consulted_on_every_group_kind():
    """The gate is node-kind agnostic."""
    gen = RecordingGenerator()
    gen.generate(_doc(), 1280.0, theme=aside_theme())
    assert gen.consulted, "the aside was never consulted at all"
    assert any(n.heading_group for n in gen.consulted), (
        "heading sections must be consulted like any other group"
    )
    assert any(n.glued_content_group and not n.heading_group for n in gen.consulted), (
        "the aside was not consulted on inner content groups"
    )
    print(
        f"  ✓  aside consulted on all {len(gen.consulted)} group(s), "
        "heading sections included"
    )


def test_bento_structure_invariant_with_a_source():
    ast = _doc()
    off = LayoutGenerator()
    off.bento_override = True
    on = RecordingGenerator()
    on.bento_override = True
    for width in (400.0, 1280.0):
        lo = off.generate(ast, width, theme=Theme())
        lm = on.generate(ast, width, theme=aside_theme())
        assert _bento_skeleton(lo) == _bento_skeleton(lm), (
            f"bento skeleton differs with an aside source at {width}px"
        )
        assert _leaves(lo) == _leaves(lm), f"leaf order differs at {width}px"
    # The aside IS consulted on heading sections; what must not change is the
    # mosaic itself — bento owns cell placement, an aside only arranges inside
    # a cell.
    assert any(n.heading_group for n in on.consulted)
    print("  ✓  bento skeleton (spans/sections) identical with a source on/off")


def test_default_structure_invariant_with_a_source():
    ast = _doc()
    lo = LayoutGenerator().generate(ast, 1280.0, theme=Theme())
    lm = RecordingGenerator().generate(ast, 1280.0, theme=aside_theme())
    assert _section_trace(lo) == _section_trace(lm), (
        "heading-section nesting differs with an aside source"
    )
    assert _leaves(lo) == _leaves(lm), "leaf order differs with an aside source"
    print("  ✓  default heading-section nesting identical with a source on/off")


TESTS = [
    test_the_aside_is_consulted_on_every_group_kind,
    test_bento_structure_invariant_with_a_source,
    test_default_structure_invariant_with_a_source,
]

if __name__ == "__main__":
    print("Layout Decision Scope Tests")
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
