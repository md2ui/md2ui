"""
Unit tests for image annotations carried in the URL query
(``![alt](photo.jpg?md2ui.shape=circle)``):

  * split_md2ui_params strips the ``md2ui.*`` namespace and nothing else, so a
    CDN's own (possibly signed) query survives byte-for-byte and the annotation
    never reaches the network;
  * sanitize_url_props turns the params into a hint entry, rejecting names
    and values it does not know;
  * the generator honours them, while the run-unified pin still keeps a
    repeated same-kind run visually consistent;
  * ``max_height`` sizes a picture by its height through ONE ratio of its own:
    it excludes ``max_width`` / ``min_width`` and ratio steps (dropped and
    reported), and a run shares the height while each picture keeps its ratio;
  * the retired aside params (``arrangement``, ``aside_ratio``,
    ``content_valign``) change nothing and say what replaced them — a picture
    goes beside text through a ``:::`` row — while a typo still reads unknown.
Run with: uv run image_url_params_tests.py
"""

from layout_bento_tests import _ast, _group, _leaf
from md2ui import session
from md2ui.pipeline.render_hints import (
    render_properties_from,
    sanitize_url_props,
)
from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.utils.image_params import (
    clean_image_url,
    destination_url,
    image_params,
    image_url,
    split_md2ui_params,
)

_ids = iter(range(90_000, 99_000))

_PHOTO = "https://images.example.com/photo-1535713875002"


# ---------------------------------------------------------------------------
# Document helpers
# ---------------------------------------------------------------------------


def _image(params: str = "", query: str = "?q=80&w=1480") -> dict:
    url = _PHOTO + query + params
    return {
        "node_id": f"img{next(_ids)}",
        "type": "image",
        "content": f"![Cover]({url})",
    }


def _card(params: str = "") -> dict:
    return _group(
        _image(params),
        _leaf("Product title of several words here"),
        _leaf("Another supporting line of body text"),
        glued_content_group=True,
    )


def _doc(*params: str):
    """One glued card per *params* entry, as one contiguous repeated run."""
    return _ast(_group(_group(*[_card(p) for p in params])))


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _image_ids(ast):
    return {n.node_id for n in _walk(ast) if n.type == "image"}


def _aside_rows(layout, image_ids):
    """Rows whose 2 cells split an image off from the rest (built asides)."""
    out = []
    for n in _walk(layout):
        if n.type != "row" or len(n.children) != 2:
            continue
        covers = [{x.content_id for x in _walk(c) if x.content_id} for c in n.children]
        img_cells = [i for i, s in enumerate(covers) if s & image_ids]
        if len(img_cells) == 1 and len(covers[img_cells[0]]) == 1:
            out.append(n)
    return out


def _image_props(layout, image_ids):
    """Every image leaf's render_properties, in document order."""
    return [
        n.render_properties or {} for n in _walk(layout) if n.content_id in image_ids
    ]


# ---------------------------------------------------------------------------
# 1. Stripping — the annotation must never reach the network
# ---------------------------------------------------------------------------


def test_cdn_query_survives_byte_for_byte():
    url = f"{_PHOTO}?q=80&w=1480&md2ui.shape=circle"
    clean, params = split_md2ui_params(url)
    assert clean == f"{_PHOTO}?q=80&w=1480", clean
    assert params == {"shape": "circle"}, params
    print("  ✓  md2ui params stripped, the CDN's own query kept byte-for-byte")


def test_signed_query_is_not_re_encoded():
    # parse_qsl + urlencode would rewrite %2F and +, invalidating the signature.
    signed = "X-Amz-Signature=abc%2Fdef+ghi&X-Amz-Expires=900"
    clean, params = split_md2ui_params(f"{_PHOTO}?{signed}&md2ui.max_width=250")
    assert clean == f"{_PHOTO}?{signed}", clean
    assert params == {"max_width": "250"}
    print("  ✓  a signed query is excised textually, never re-encoded")


def test_params_only_query_drops_the_question_mark():
    clean, params = split_md2ui_params(f"{_PHOTO}?md2ui.shape=circle")
    assert clean == _PHOTO, clean
    assert params == {"shape": "circle"}
    # Leading param: the surviving separator is normalised back to "?".
    clean, _ = split_md2ui_params(f"{_PHOTO}?md2ui.shape=circle&q=80")
    assert clean == f"{_PHOTO}?q=80", clean
    print("  ✓  a params-only query leaves no '?'; a leading param renormalises")


def test_second_question_mark_is_accepted():
    # Every sample URL already has a query, so an author pasting "?md2ui.x=y"
    # produces a second '?'. It must work, and must not corrupt what precedes.
    clean, params = split_md2ui_params(f"{_PHOTO}?q=80&w=1480?md2ui.aspect_ratio=4:3")
    assert clean == f"{_PHOTO}?q=80&w=1480", clean
    assert params == {"aspect_ratio": "4:3"}
    print("  ✓  '?' and '&' both introduce a param, at any position")


def test_fragment_and_data_uri_are_untouched():
    clean, params = split_md2ui_params(f"{_PHOTO}.svg?md2ui.shape=circle#icon-star")
    assert clean == f"{_PHOTO}.svg#icon-star", clean
    assert params == {"shape": "circle"}
    # A data: payload may legitimately contain '?' — never touch it.
    data = "data:image/svg+xml,<svg>?md2ui.shape=circle</svg>"
    assert split_md2ui_params(data) == (data, {})
    print("  ✓  an SVG sprite fragment survives; a data: URI is never parsed")


def test_unannotated_url_is_returned_unchanged():
    plain = f"{_PHOTO}?q=80&w=1480"
    assert split_md2ui_params(plain) == (plain, {})
    # "md2ui." in the PATH is not a param either.
    path = "https://x.example/md2ui.png?q=1"
    assert split_md2ui_params(path) == (path, {})
    assert clean_image_url(None) is None
    print("  ✓  a URL with no md2ui param (or one only in its path) is inert")


def test_whitespace_values_are_dropped():
    # _build_fingerprint counts words in a leaf's content; a space inside a
    # param would shift the node's length category.
    _, params = split_md2ui_params(f"{_PHOTO}?md2ui.max_width=%20250")
    assert params == {}, params
    print("  ✓  a whitespace-bearing value is dropped, not honoured")


def test_image_helpers_read_the_markdown_literal():
    content = f"![Cover]({_PHOTO}?q=80&md2ui.aspect_ratio=1:1)"
    assert image_params(content) == {"aspect_ratio": "1:1"}
    # image_url stays RAW so the generator can still see the params.
    assert image_url(content) == f"{_PHOTO}?q=80&md2ui.aspect_ratio=1:1"
    assert clean_image_url(image_url(content)) == f"{_PHOTO}?q=80"
    assert image_params("![Cover](nope.png)") == {}
    print("  ✓  image_params reads the literal; image_url stays raw")


def test_image_url_drops_the_title_and_brackets():
    """A title and ``<…>`` are spelling, not address: the fetch must not ask for
    ``x.png "A title"``. An image card's background is read the same way."""
    url = f"{_PHOTO}?md2ui.aspect_ratio=1:1"
    for dest in (f'{url} "A title"', f"<{url}>", f"<{url}> 'A title'", f"{url} (t)"):
        assert image_url(f"![a]({dest})") == url, dest
        assert image_params(f"![a]({dest})") == {"aspect_ratio": "1:1"}, dest
    assert destination_url("</my file>") == "/my file"
    grouper = MarkdownGrouper(f'![\n## Hero\n\nBody\n]({url} "T")')
    grouper.process(criteria=None, detector=DataPointDetector())
    assert grouper.ast is not None
    (card,) = [n for n in _walk(grouper.ast) if n.card_bg_url]
    assert card.card_bg_url == url, card.card_bg_url
    print("  ✓  image_url and card_bg_url drop a title and <…>")


# ---------------------------------------------------------------------------
# 2. Validation — a URL has no schema, so sanitize_url_props is its validator
# ---------------------------------------------------------------------------


def test_valid_params_become_a_hint_entry():
    props, warnings = sanitize_url_props(
        {
            "aspect_ratio": "4:3",
            "max_width": "250",
            "shape": "circle",
            "content_align": "right",
        }
    )
    assert not warnings, warnings
    assert props["max_width"] == 250 and isinstance(props["max_width"], int)
    # The entry feeds the resolver unchanged.
    render = render_properties_from(props, wide=False)
    assert render.aspect_ratio == "4:3" and render.shape == "circle"
    print("  ✓  valid params resolve through render_properties_from as-is")


def test_wide_twins_resolve():
    props, warnings = sanitize_url_props(
        {
            "aspect_ratio": "1:1",
            "aspect_ratio_wide": "default",
        }
    )
    assert not warnings, warnings
    assert render_properties_from(props, wide=False).aspect_ratio == "1:1"
    assert render_properties_from(props, wide=True).aspect_ratio is None
    print("  ✓  _wide twins (and 'default') work with no extra plumbing")


def test_invalid_params_are_dropped_and_reported():
    props, warnings = sanitize_url_props(
        {
            "shappe": "circle",  # unknown name
            "shape": "square",  # out of enum
            "max_width": "abc",  # not an integer
            "max_width_wide": "0",  # below the minimum
            "arrangement": "aside",  # retired: a ::: row now
            "aside_ratio": "1:2",  # retired with it
            "content_valign": "center",  # retired with it
            "aspect_ratio": "1:1",  # the one good value
        }
    )
    assert props == {"aspect_ratio": "1:1"}, props
    assert len(warnings) == 7, warnings
    print("  ✓  every invalid name/value is dropped and reported, not guessed")


def test_the_retired_aside_params_name_their_replacement_and_change_nothing():
    replacements = {
        "arrangement": "`:::` row",
        "arrangement_wide": "`::: 1 >` row",
        "aside_ratio": "`:::1`",
        "aside_ratio_wide": "`:::1`",
        "content_valign": "`...` line",
        "content_valign_wide": "`...` line",
    }
    for name, replacement in replacements.items():
        props, warnings = sanitize_url_props({name: "aside"})
        assert props == {} and len(warnings) == 1, (name, warnings)
        assert warnings[0].startswith(f"'md2ui.{name}' was removed — "), warnings
        assert replacement in warnings[0], (name, warnings)
    ast = _doc("&md2ui.arrangement=aside&md2ui.aside_ratio=1:4")
    gen = LayoutGenerator()
    layout = gen.generate(ast, 767.0)
    assert not _aside_rows(layout, _image_ids(ast)), "a retired param built an aside"
    assert any("was removed" in d for d in gen.url_diagnostics())
    print("  ✓  the retired aside params name their replacement and change nothing")


def test_a_typo_still_reads_unknown():
    for name in ("aspec_ratio", "aspec_ratio_wide", "arrangment"):
        props, warnings = sanitize_url_props({name: "4:3"})
        assert props == {} and warnings == [f"unknown property 'md2ui.{name}'"], (
            name,
            warnings,
        )
    print("  ✓  a misspelt param is still reported as unknown")


def test_fit_is_authorable_and_has_a_wide_twin():
    """``fit`` is a deliberate choice about one image ("show all of this" vs
    "fill the frame"), resolved per width like every hint."""
    props, warnings = sanitize_url_props({"fit": "contain", "fit_wide": "cover"})
    assert not warnings, warnings
    assert render_properties_from(props, wide=False).fit == "contain"
    assert render_properties_from(props, wide=True).fit == "cover"
    # And an out-of-enum value is refused like any other.
    bad, warns = sanitize_url_props({"fit": "squish"})
    assert bad == {} and "contain|cover" in warns[0], (bad, warns)
    print("  ✓  fit resolves per width and is refused when invalid")


def test_corner_radius_and_bleed_are_authorable():
    """Per-image twins of the THEME.md level keys."""
    props, warnings = sanitize_url_props(
        {"corner_radius": "12", "bleed": "yes", "bleed_wide": "no"}
    )
    assert not warnings, warnings
    assert props["corner_radius"] == 12 and props["bleed"] is True
    assert render_properties_from(props, wide=False).bleed is True
    assert render_properties_from(props, wide=True).bleed is False
    # 0 is an explicit square, not "unset" — that is how one image escapes a
    # rounded level, so it must survive validation.
    assert sanitize_url_props({"corner_radius": "0"})[0] == {"corner_radius": 0}
    # Every spelling a URL might carry.
    for t in ("yes", "true", "1"):
        assert sanitize_url_props({"bleed": t})[0]["bleed"] is True
    for f in ("no", "false", "0"):
        assert sanitize_url_props({"bleed": f})[0]["bleed"] is False
    bad, warns = sanitize_url_props({"corner_radius": "-2", "bleed": "maybe"})
    assert bad == {} and len(warns) == 2, (bad, warns)
    print("  ✓  corner_radius / bleed parse and resolve per width")


def test_aspect_ratio_takes_any_ratio():
    # A URL value is direct input and the renderer parses an arbitrary W:H.
    props, warnings = sanitize_url_props({"aspect_ratio": "2.35:1"})
    assert props == {"aspect_ratio": "2.35:1"} and not warnings
    print("  ✓  an arbitrary W:H aspect ratio is accepted from a URL")


# ---------------------------------------------------------------------------
# 3. Generator — render params reach the image
# ---------------------------------------------------------------------------


def test_no_params_leaves_the_rules_untouched():
    ast = _doc("")
    gen = LayoutGenerator()
    layout = gen.generate(ast, 767.0)
    assert not _aside_rows(layout, _image_ids(ast))
    assert _image_props(layout, _image_ids(ast)) == [{}]
    assert not gen.url_diagnostics()
    print("  ✓  an unannotated document is byte-identical to the rules path")


# ---------------------------------------------------------------------------
# 4. Repeated runs stay visually consistent (the invariant the poll protects)
# ---------------------------------------------------------------------------


def test_one_annotated_member_annotates_the_whole_run():
    # Annotating ONE member of a run is enough.
    ast = _doc("&md2ui.aspect_ratio=4:3", "", "")
    props = _image_props(LayoutGenerator().generate(ast, 767.0), _image_ids(ast))
    assert props == [{"aspect_ratio": "4:3"}] * 3, props
    print("  ✓  annotating one card of three styles all three")


def test_conflicting_params_resolve_uniformly_and_warn():
    ast = _doc(
        "&md2ui.aspect_ratio=4:3",
        "&md2ui.aspect_ratio=1:1",
        "&md2ui.aspect_ratio=1:1",
    )
    gen = LayoutGenerator()
    props = _image_props(gen.generate(ast, 767.0), _image_ids(ast))
    assert len({p.get("aspect_ratio") for p in props}) == 1, props
    assert props[0]["aspect_ratio"] == "1:1", props  # majority wins
    assert any("conflicting" in d for d in gen.url_diagnostics()), gen.url_diagnostics()
    print("  ✓  conflicting params across a run: majority wins, run uniform")


# ---------------------------------------------------------------------------
# 5. max_height — a picture sized by its height
# ---------------------------------------------------------------------------


def test_max_height_with_one_ratio_is_kept():
    props, warnings = sanitize_url_props(
        {"max_height": "36", "aspect_ratio": "7:1", "max_height_wide": "48"}
    )
    assert props == {"max_height": 36, "aspect_ratio": "7:1", "max_height_wide": 48}
    assert warnings == [], warnings
    assert render_properties_from(props, True).max_height == 48
    print("  ✓  max_height with one ratio is authorable, with a _wide twin")


def test_max_height_excludes_the_widths():
    for width in ("max_width", "min_width"):
        props, warnings = sanitize_url_props(
            {"max_height": "36", width: "40", "aspect_ratio": "1:1"}
        )
        assert "max_height" not in props and props[width] == 40, props
        assert any("cannot be used with" in w for w in warnings), warnings
    # A width that only the wide variant carries drops only the wide height.
    props, warnings = sanitize_url_props(
        {"max_height": "36", "aspect_ratio": "7:1", "max_width_wide": "100"}
    )
    assert render_properties_from(props, False).max_height == 36, props
    assert render_properties_from(props, True).max_height is None, props
    assert len(warnings) == 1, warnings
    print("  ✓  max_height beside a width is dropped and reported, per variant")


def test_max_height_needs_one_ratio():
    for params in (
        {"max_height": "36"},
        {"max_height": "36", "aspect_ratio": "7:1,1:1@600"},
    ):
        props, warnings = sanitize_url_props(params)
        assert "max_height" not in props, props
        assert any("needs one aspect_ratio" in w for w in warnings), warnings
    print("  ✓  max_height without one ratio is dropped and reported")


def test_a_run_shares_one_height_and_keeps_each_ratio():
    ast = _doc(
        "&md2ui.max_height=36&md2ui.aspect_ratio=1:1",
        "&md2ui.max_height=36&md2ui.aspect_ratio=7:1",
    )
    gen = LayoutGenerator()
    props = _image_props(gen.generate(ast, 767.0), _image_ids(ast))
    assert props == [
        {"aspect_ratio": "1:1", "max_width": 36},
        {"aspect_ratio": "7:1", "max_width": 252},
    ], props
    assert not gen.url_diagnostics(), gen.url_diagnostics()
    print("  ✓  one height across the run, each picture at its own ratio")


def test_one_annotated_height_sizes_the_whole_run():
    ast = _doc("&md2ui.max_height=36&md2ui.aspect_ratio=4:3", "", "")
    props = _image_props(LayoutGenerator().generate(ast, 767.0), _image_ids(ast))
    assert props == [{"aspect_ratio": "4:3", "max_width": 48}] * 3, props
    print("  ✓  annotating one card's height sizes all three")


def test_height_against_width_in_one_run_is_a_conflict():
    ast = _doc(
        "&md2ui.max_height=36&md2ui.aspect_ratio=1:1",
        "&md2ui.max_width=36&md2ui.aspect_ratio=1:1",
    )
    gen = LayoutGenerator()
    gen.generate(ast, 767.0)
    assert any("conflicting" in d for d in gen.url_diagnostics()), gen.url_diagnostics()
    print("  ✓  a run sized by height and by width reports its conflict")


def test_same_photo_different_params_shares_one_download():
    # Two unrelated nodes on one photo: one fetch identity, distinct hints.
    a = f"{_PHOTO}?q=80&md2ui.shape=circle"
    b = f"{_PHOTO}?q=80&md2ui.aspect_ratio=16:9"
    assert clean_image_url(a) == clean_image_url(b) == f"{_PHOTO}?q=80"
    assert split_md2ui_params(a)[1] != split_md2ui_params(b)[1]
    print("  ✓  one photo, two annotations: one cache key, two hint sets")


def test_list_rows_of_one_shape_share_the_first_rows_params():
    # `- ` rows of one shape are a run like cards, so the first row's params
    # draw every picture.
    circle = "?md2ui.max_width=56&md2ui.aspect_ratio=1:1&md2ui.shape=circle"
    rows = [
        f"- ![{t}]({_PHOTO}{circle if t == 'Eva' else ''}) - **{t}** : "
        f"_Received_ ... +$5.00"
        for t in ("Eva", "Ben", "Marco")
    ]
    ast = session.group_markdown(
        "## Today\n\n" + "\n".join(rows) + "\n", session.load_grouping_kit()
    )
    assert ast is not None
    props = _image_props(LayoutGenerator().generate(ast, 900.0), _image_ids(ast))
    assert len(props) == 3 and all(p == props[0] for p in props), props
    assert props[0].get("shape") == "circle", props
    print("  ✓  `- ` rows of one shape share the first row's params")


TESTS = [
    test_cdn_query_survives_byte_for_byte,
    test_signed_query_is_not_re_encoded,
    test_params_only_query_drops_the_question_mark,
    test_second_question_mark_is_accepted,
    test_fragment_and_data_uri_are_untouched,
    test_unannotated_url_is_returned_unchanged,
    test_whitespace_values_are_dropped,
    test_image_helpers_read_the_markdown_literal,
    test_image_url_drops_the_title_and_brackets,
    test_valid_params_become_a_hint_entry,
    test_wide_twins_resolve,
    test_invalid_params_are_dropped_and_reported,
    test_the_retired_aside_params_name_their_replacement_and_change_nothing,
    test_a_typo_still_reads_unknown,
    test_fit_is_authorable_and_has_a_wide_twin,
    test_corner_radius_and_bleed_are_authorable,
    test_aspect_ratio_takes_any_ratio,
    test_no_params_leaves_the_rules_untouched,
    test_one_annotated_member_annotates_the_whole_run,
    test_list_rows_of_one_shape_share_the_first_rows_params,
    test_conflicting_params_resolve_uniformly_and_warn,
    test_same_photo_different_params_shares_one_download,
    test_max_height_with_one_ratio_is_kept,
    test_max_height_excludes_the_widths,
    test_max_height_needs_one_ratio,
    test_a_run_shares_one_height_and_keeps_each_ratio,
    test_one_annotated_height_sizes_the_whole_run,
    test_height_against_width_in_one_run_is_a_conflict,
]

if __name__ == "__main__":
    print("Image URL Params Tests")
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
