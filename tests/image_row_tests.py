"""
Unit tests for the same-line image RUN: images written side by side on one
source line lay out as a ROW, images on their own lines stay a col.

Two halves, and both are load-bearing.

The GROUPER half is phase order. ``_split_images`` runs after every pass that
reads a whole line, like the link peel it is the twin of; ahead of them, a line
holding an image would reach them already cut and strand its ` - ` or `...` in
a text leaf nothing claims. The separator and spring tests here pin that order.

The GENERATOR half is arrangement: a line group holding an image flows like any
other line group, and ``_line_item_width`` gives an image a width to flow at
(neither measurer sizes one).

An image is the one element cut out of prose without a separator — it cannot be
drawn as text — so ``Text ![img](u.png) text`` arrives as [text, image, text],
and those pieces are a same-line row like any other. Prose too long for one row
wraps piece by piece. To stack a picture, the author gives it its own line.

Run with: uv run tests/image_row_tests.py
"""

from markdown_datapoint_split_tests import _processed_with_criteria
from md2ui.pipeline.layout_generator import LayoutGenerator


def _layout(markdown: str, width: float = 1024.0):
    return LayoutGenerator().generate(_processed_with_criteria(markdown), width)


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


_walk_ast = _walk  # grouper nodes and LayoutNodes both expose .children


def _image_ids(ast) -> set:
    def walk(n):
        if n.type == "image" and n.node_id:
            yield n.node_id
        for c in n.children:
            yield from walk(c)

    return set(walk(ast))


def _kind_holding_images(markdown: str, width: float = 1024.0) -> str:
    """The type of the deepest node whose direct cells are the images."""
    ast = _processed_with_criteria(markdown)
    ids = _image_ids(ast)
    assert len(ids) >= 2, f"fixture needs 2+ images, got {len(ids)}"
    layout = LayoutGenerator().generate(ast, width)
    holders = [
        n
        for n in _walk(layout)
        if len([c for c in n.children if c.content_id in ids]) == len(ids)
    ]
    assert holders, f"no node holds all {len(ids)} images"
    return holders[-1].type


def test_two_same_line_images_make_a_row():
    kind = _kind_holding_images("![Left](one.png) ![Right](two.png)")
    assert kind == "row", f"same-line images must flow, got {kind}"
    print("  ✓  two images on one source line lay out as a row")


def test_two_images_on_their_own_lines_stay_a_col():
    kind = _kind_holding_images("![Left](one.png)\n![Right](two.png)")
    assert kind == "col", f"images on separate lines must stack, got {kind}"
    print("  ✓  images on consecutive lines stay a col")


def test_a_separated_image_pair_flows_with_a_recorded_separator():
    """A ` - ` between two images is consumed like any other line's separator.

    The image split runs after the separator split, so the gap reaches the
    theme as ``separator_chars`` instead of surviving as a literal text leaf
    that nothing can switch off.
    """
    ast = _processed_with_criteria("![Left](one.png) - ![Right](two.png)")
    holder = next(
        n
        for n in _walk_ast(ast)
        if len([c for c in n.children if c.type == "image"]) == 2
    )
    assert holder.separator_chars == ["-"], holder.separator_chars
    assert not [c for c in holder.children if c.type == "text"], "separator left behind"
    assert _kind_holding_images("![Left](one.png) - ![Right](two.png)") == "row"
    print(
        "  ✓  a ` - `-separated image pair flows, separator recorded not drawn as text"
    )


def test_a_spring_centres_an_image_run():
    """`...` reaches an image line, which is only true because the image split
    runs after the spring split. The link twin is the reference shape."""
    for md, what in (
        ("... ![A](a.png) ![B](b.png) ...", "images"),
        ("... [A](/a) [B](/b) ...", "links"),
    ):
        ast = _processed_with_criteria(md)
        aligned = [n for n in _walk_ast(ast) if n.authored_align]
        assert aligned, f"no alignment reached the {what}"
        assert aligned[0].authored_align == "center", (
            f"{what}: got {aligned[0].authored_align}"
        )
        assert not [n for n in _walk_ast(ast) if (n.content or "").strip() == "..."], (
            f"{what}: a spring survived as a literal text leaf"
        )
    print("  ✓  a spring centres an image run, exactly as it does a link run")


def test_an_image_beside_an_element_flows():
    ast = _processed_with_criteria("![Logo](logo.png) [Buy](/buy)")
    layout = LayoutGenerator().generate(ast, 1024.0)
    rows = [n for n in _walk(layout) if n.type == "row" and len(n.children) == 2]
    assert rows, "an image beside a link must flow as a row"
    print("  ✓  an image beside a link flows")


def _piece_ids(ast) -> list:
    """The node ids of the one line group's pieces, in source order."""
    image = next(n for n in _walk_ast(ast) if n.type == "image")
    holder = next(n for n in _walk_ast(ast) if image in n.children)
    return [c.node_id for c in holder.children]


def test_an_image_in_prose_is_a_piece_of_its_line():
    """`_split_images` cuts an image out of prose without a separator — it
    cannot be drawn as text — and the pieces it leaves are a same-line row, the
    same row `Text - ![img] - text` makes."""
    ast = _processed_with_criteria(
        "Text and a image ![img](u.png) inside of the same text."
    )
    ids = _piece_ids(ast)
    assert len(ids) == 3, f"fixture must split into [text, image, text], got {ids}"
    layout = LayoutGenerator().generate(ast, 1024.0)
    rows = [n for n in _walk(layout) if [c.content_id for c in n.children] == ids]
    assert rows and rows[0].type == "row", (
        f"text, image, text must sit in one row, got {[n.type for n in rows]}"
    )
    print("  ✓  an image among words sits in its line as a row")


def test_a_long_line_around_an_image_wraps_piece_by_piece():
    """Prose too long for one row still flows: the short lead shares a row
    with the picture, and the long tail wraps onto the next row."""
    ast = _processed_with_criteria(
        "Lead ![img](u.png) and then a long run of words after the picture that "
        "cannot possibly fit beside it on one narrow row, so it wraps below."
    )
    ids = _piece_ids(ast)
    assert len(ids) == 3, f"fixture must split into [text, image, text], got {ids}"
    layout = LayoutGenerator().generate(ast, 480.0)
    rows = [
        [c.content_id for c in n.children if c.content_id in ids]
        for n in _walk(layout)
        if n.type == "row"
    ]
    assert ids[:2] in rows, f"lead and image must share a row, got {rows}"
    assert ids not in rows, "all three pieces cannot fit one row at 480px"
    print("  ✓  a long line around an image wraps piece by piece")


def test_a_separated_line_flows_with_words_and_an_image():
    """`Word - ![img] - [Buy]` is three pieces the author divided, so it flows
    as `Word - ✅ - [Buy]` does, with the separator recorded between them."""
    ast = _processed_with_criteria("Word - ![img](u.png) - [Buy](/buy)")
    ids = _image_ids(ast)
    layout = LayoutGenerator().generate(ast, 1024.0)
    holders = [n for n in _walk(layout) if any(c.content_id in ids for c in n.children)]
    assert holders and holders[-1].type == "row", [n.type for n in holders]
    print("  ✓  a separated line holding words and an image flows")


def test_a_long_image_run_wraps_when_narrow():
    """`_flow_rows` is a greedy first-fit packer, so a run too long for the
    width wraps onto further rows instead of overflowing."""
    md = " ".join(f"![i{i}](i{i}.png)" for i in range(8))
    wide = _kind_holding_images(md, 1400.0)
    assert wide == "row", f"8 images fit at 1400px, got {wide}"

    ast = _processed_with_criteria(md)
    ids = _image_ids(ast)
    narrow = LayoutGenerator().generate(ast, 320.0)
    rows = [
        n
        for n in _walk(narrow)
        if n.type == "row" and any(c.content_id in ids for c in n.children)
    ]
    assert len(rows) > 1, f"a run must wrap at 320px, got {len(rows)} row(s)"
    assert sum(len(r.children) for r in rows) == len(ids), "every image kept"
    print("  ✓  a long image run wraps onto further rows when narrow")


def test_a_capped_image_flows_at_its_cap():
    """An authored `?md2ui.max_width` is taken literally — the renderer pins a
    capped image to exactly that width, so the generator must measure it there
    or the two disagree about what fits."""
    ast = _processed_with_criteria(
        "![Left](one.png?md2ui.max_width=120) ![Right](two.png)"
    )
    ids = _image_ids(ast)
    layout = LayoutGenerator().generate(ast, 1024.0)
    row = next(
        n
        for n in _walk(layout)
        if n.type == "row" and len([c for c in n.children if c.content_id in ids]) == 2
    )
    assert row.ratios[0] == 120.0, f"capped image measured {row.ratios[0]}, want 120"
    assert row.ratios[1] != 120.0, "the uncapped sibling must keep its own width"
    print("  ✓  a capped image flows at its cap, not at the image floor")


TESTS = [
    test_two_same_line_images_make_a_row,
    test_two_images_on_their_own_lines_stay_a_col,
    test_a_separated_image_pair_flows_with_a_recorded_separator,
    test_a_spring_centres_an_image_run,
    test_an_image_beside_an_element_flows,
    test_an_image_in_prose_is_a_piece_of_its_line,
    test_a_long_line_around_an_image_wraps_piece_by_piece,
    test_a_separated_line_flows_with_words_and_an_image,
    test_a_long_image_run_wraps_when_narrow,
    test_a_capped_image_flows_at_its_cap,
]

if __name__ == "__main__":
    print("Same-Line Image Run Tests")
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
