"""
Unit tests for the ``line_split_group`` annotation: a group node whose direct
children are the pieces split out of ONE single-line text run (separator
segments, datapoint splits, boundary emoji/link peels, KV value
sub-splits, inline-code peels, image splits) — independent of glued status.
The flag survives only on containers holding at least one direct TEXT/SEGMENT
leaf piece (see MarkdownGrouper._finalize_line_split_groups).
Run with: uv run tests/markdown_line_split_tests.py
"""

from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline.data_point_types import DataPointType
from md2ui.pipeline.markdown_grouper import MarkdownGroupNode, NodeType
from md2ui.pipeline.grouper_line_flow import line_stacks
from md2ui.pipeline.grouper_node_reads import _classification_text


def _find_flagged(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    out = []
    if node.line_split_group:
        out.append(node)
    for c in node.children:
        out.extend(_find_flagged(c))
    return out


def _walk(node: MarkdownGroupNode):
    yield node
    for c in node.children:
        yield from _walk(c)


def _flagged_paths(node: MarkdownGroupNode, path: str = "") -> list[str]:
    out = []
    if node.line_split_group:
        out.append(path or ".")
    for i, c in enumerate(node.children):
        out.extend(_flagged_paths(c, f"{path}.{i}" if path else str(i)))
    return out


def test_lone_line_emoji_peel_flagged():
    # Peel container of a lone line: flagged and NOT glued. The two flags are
    # mutually exclusive — glue means consecutive source lines stuck together,
    # and one line flowed aside has no lines to glue.
    # The separator is what earns the peel (see _split_elements); without it
    # "📂 Folder name" is one prose leaf and there is no container to flag.
    ast = _processed_with_criteria("📂 - Folder name")
    flagged = _find_flagged(ast)
    assert len(flagged) == 1, f"Got {_flagged_paths(ast)}"
    node = flagged[0]
    assert [c.type for c in node.children] == [NodeType.EMOJI, NodeType.SEGMENT]
    assert not node.glued_content_group, "a flowed line is not glued content"
    print("  ✓  '📂 - Folder name' → one flagged, non-glued container")


def test_glued_paragraph_inner_containers_flagged():
    # Two glued lines: the cross-line glued wrapper must NOT be flagged; the
    # per-line split containers (emoji peel / pipe separator) must be.
    ast = _processed_with_criteria("**🗓 - Calendar**\nJan | Feb | Mar")
    flagged = _find_flagged(ast)
    assert len(flagged) == 2, f"Got {_flagged_paths(ast)}"
    peel, seps = flagged
    assert not any(
        f.glued_content_group and len(f.children) == 2 and f is not peel
        for f in flagged
    )
    assert [c.type for c in peel.children] == [NodeType.EMOJI, NodeType.SEGMENT]
    # The `|` is consumed and recorded on the container (## Separators decides
    # whether it is drawn back).
    assert [c.type for c in seps.children] == [
        NodeType.SEGMENT,
        NodeType.SEGMENT,
        NodeType.SEGMENT,
    ], f"Got {[c.type for c in seps.children]}"
    assert seps.separator_chars == ["|", "|"], seps.separator_chars
    # the outer glued paragraph wrapper is not one of the flagged nodes
    glued_wrappers = [f for f in flagged if any(c.children for c in f.children)]
    assert not glued_wrappers, "cross-line glued wrapper must not be flagged"
    print("  ✓  glued '**🗓 - Calendar** / Jan | Feb | Mar' → inner containers flagged")


def test_annotated_time_segment_split_flagged():
    ast = _processed_with_criteria("**9:00 AM - 9:15 AM | Opening Remarks**")
    flagged = _find_flagged(ast)
    assert len(flagged) == 1, f"Got {_flagged_paths(ast)}"
    types = [c.type for c in flagged[0].children]
    assert types == [NodeType.TEXT, NodeType.SEGMENT], f"Got {types}"
    point = flagged[0].children[0].data_points[0]
    assert point["type"] == DataPointType.TIME
    assert point["matched"] == "9:00 AM - 9:15 AM"
    print("  ✓  '**9:00 AM - 9:15 AM | Opening Remarks**' → flagged {text, segment}")


def test_separated_trailing_link_run_flows():
    # The separator earns the peel; the prose stays ONE intact piece and the
    # links are pieces of the same line, so the container flows them together.
    #
    # TWO flagged containers: the outer strip, and the link run inside it. A
    # pure run of elements is flagged like any other, so chips and links get
    # the same alignment and spacing as an identical-looking emoji run.
    ast = _processed_with_criteria(
        "Text followed by 2 links - [↗️](/emoji-link) [↗️ text](/text-link)"
    )
    flagged = _find_flagged(ast)
    assert len(flagged) == 2, f"Got {_flagged_paths(ast)}"
    container = flagged[0]
    assert container.children[0].content == "Text followed by 2 links"
    run = container.children[1]
    assert run.line_split_group and [c.type for c in run.children] == [
        NodeType.LINK,
        NodeType.LINK,
    ], run.to_dict()
    assert NodeType.LINK in [
        c.type for c in _walk(container) if c.type == NodeType.LINK
    ], container.to_dict()
    print("  ✓  'prose - [..] [..]' → intact text + links, flowed")


def test_leading_link_peel_flowed():
    # Leading single-link peel: flat {link, segment} — one line, so it flows.
    ast = _processed_with_criteria(
        "Intro paragraph line\n\n[click](/url) - then more.\n\nOutro paragraph"
    )
    flagged = _find_flagged(ast)
    assert len(flagged) == 1, f"Got {_flagged_paths(ast)}"
    assert [c.type for c in flagged[0].children] == [
        NodeType.LINK,
        NodeType.SEGMENT,
    ], f"Got {[c.type for c in flagged[0].children]}"
    print("  ✓  '[click] - then more.' → flat {link, segment}, flowed")


def test_mixed_peel_flowed_link_inside():
    # Emoji, prose and a link, each explicitly separated: one flowed line.
    ast = _processed_with_criteria("🎉 - Great news for everyone - [more](/x)")
    flagged = _find_flagged(ast)
    assert len(flagged) == 1, f"Got {_flagged_paths(ast)}"
    assert [c.type for c in flagged[0].children] == [
        NodeType.EMOJI,
        NodeType.SEGMENT,
        NodeType.LINK,
    ], f"Got {[(c.type, c.content) for c in flagged[0].children]}"
    print("  ✓  '🎉 - prose - [link]' → flowed {emoji, segment, link}")


# --- prose adjacency stays inline: TEXT-EMOJI / TEXT-LINK ------------------
#
# A run the prose simply runs into is left in the text — a
# text-emoji or a text-link, drawn at the surrounding text size rather than as a
# badge or a button. (Not to be confused with a text-MARKER, which is what an
# unpeeled backtick span becomes.) Nothing is flagged because nothing was split.


def test_prose_leading_emoji_run_is_a_text_emoji():
    ast = _processed_with_criteria("🚀 🎉 Text followed by 2 links")
    assert _find_flagged(ast) == [], _flagged_paths(ast)
    leaves = [n for n in _walk(ast) if not n.children and n.content]
    assert [n.content for n in leaves] == ["🚀 🎉 Text followed by 2 links"], leaves
    print("  ✓  '🚀 🎉 prose' → one leaf, text-emojis")


def test_prose_mixed_trailing_run_stays_inline():
    ast = _processed_with_criteria("Text followed by 2 links ⭐ [↗️ text](/t)")
    assert _find_flagged(ast) == [], _flagged_paths(ast)
    leaves = [n for n in _walk(ast) if not n.children and n.content]
    assert len(leaves) == 1, [n.content for n in leaves]
    print("  ✓  'prose ⭐ [link]' → one leaf, text-emoji + text-link")


def test_prose_trailing_link_run_is_a_text_link():
    ast = _processed_with_criteria(
        "Text followed by 2 links [↗️](/emoji-link) [↗️ text](/text-link)"
    )
    assert _find_flagged(ast) == [], _flagged_paths(ast)
    leaves = [n for n in _walk(ast) if not n.children and n.content]
    assert len(leaves) == 1, [n.content for n in leaves]
    print("  ✓  'prose [..] [..]' → one leaf, text-links")


def test_gate_run_trim_text():
    # Direct unit checks of _classification_text's run trim: whitespace-joined
    # boundary runs trim fully; separator-joined dps break the run (pills keep
    # their inner links for classification, same as the single-dp trim did).
    from md2ui.pipeline.data_point_detector import DataPointDetector

    det = DataPointDetector()
    cases = [
        # Decoration — no separator, so the run trims and bare prose is what the
        # gate classifies.
        (
            "Text followed by 2 links [↗️](/emoji-link) [↗️ text](/text-link)",
            "Text followed by 2 links",
        ),
        ("🚀 🎉 Text followed by 2 links", "Text followed by 2 links"),
        ("Text followed by 2 links ⭐ [↗️ text](/t)", "Text followed by 2 links"),
        # Behind an explicit separator the dp is a SEGMENT, so the line is
        # classified whole. Trimming it would leave the separator standing on
        # its own ("| [B](/b) |", "days -"), read as prose, and skip the split.
        ("[A](/a) | [B](/b) | [C](/c)", "[A](/a) | [B](/b) | [C](/c)"),
        ("days - ⬇", "days - ⬇"),
        ("Latte - [+](/add)", "Latte - [+](/add)"),
        ("⬇ - days", "⬇ - days"),
    ]
    for content, expected in cases:
        got = _classification_text(content, det.detect_all(content))
        assert got == expected, f"{content!r}: got {got!r}, want {expected!r}"
    print("  ✓  _classification_text trims whole boundary runs, keeps separator pills")


def test_separated_boundary_dp_splits_instead_of_stranding_the_separator():
    # "days - ⬇" must not come out as text('days -') + emoji.
    ast = _processed_with_criteria("days - ⬇")
    (row,) = _find_flagged(ast)
    assert [(c.type, c.content) for c in row.children] == [
        (NodeType.SEGMENT, "days"),
        (NodeType.EMOJI, "⬇"),
    ], row.to_dict()
    print("  ✓  'days - ⬇' → segment('days') + emoji, separator consumed")


def test_separator_between_two_peeled_links_is_not_a_node():
    # A separator BETWEEN two peeled links is consumed, not left as a text node.
    ast = _processed_with_criteria("[`⬅️`](/prev) - [`➡️`](/next)")
    types = [n.type for n in _walk(ast) if n.content and n.type == NodeType.TEXT]
    assert types == [], f"a stray separator survived: {ast.to_dict()}"
    print("  ✓  '[a] - [b]' → two links, no stray '-' node")


def test_adjacent_boundary_dp_is_a_text_emoji():
    # The same rule as a backtick span: without a separator the emoji belongs
    # to the sentence and stays in it as a text-emoji, so nothing splits and
    # nothing is flagged. Its separated twin is the test above.
    ast = _processed_with_criteria("⬇ days")
    assert _find_flagged(ast) == [], _flagged_paths(ast)
    leaves = [n for n in _walk(ast) if not n.children and n.content]
    assert [n.content for n in leaves] == ["⬇ days"], leaves
    print("  ✓  '⬇ days' (no separator) is a text-emoji, not a peel")


def test_subsplit_segments_flagged_not_parent():
    # Each item sub-split into {emoji, segment} is flagged; their parent group
    # (children all containers) is NOT. A list, because a second separator on
    # one line splits at the SAME level rather than nesting.
    ast = _processed_with_criteria(
        "- ⭐ - Popular\n- 🚀 - enterpreunership\n- ⚛️ - science"
    )
    flagged = _find_flagged(ast)
    assert len(flagged) == 3, f"Got {_flagged_paths(ast)}"
    for f in flagged:
        assert f.type == NodeType.LIST_ITEM, f"Got {f.type!r}"
        assert [c.type for c in f.children] == [
            NodeType.EMOJI,
            NodeType.SEGMENT,
        ], f"Got {[c.type for c in f.children]}"
    print("  ✓  emoji list → 3 sub-split items flagged, parent not")


def test_comma_list_not_flagged():
    ast = _processed_with_criteria("Cat, Dog, Fish, Snake")
    assert _find_flagged(ast) == [], f"Got {_flagged_paths(ast)}"
    assert [n.content for n in _walk(ast) if n.content] == ["Cat, Dog, Fish, Snake"]
    print("  ✓  a comma list stays one unflagged line")


def test_labelled_comma_list_not_subsplit():
    line = "**Colors Available:** White, Black, Navy, Heather Gray, Olive Green"
    ast = _processed_with_criteria(line)
    assert _find_flagged(ast) == [], f"Got {_flagged_paths(ast)}"
    assert [n.content for n in _walk(ast) if n.content] == [line]
    print("  ✓  a labelled comma list stays one unflagged line")


def test_colon_line_pipe_segments_flagged():
    # ADR-205: the pipes divide the line; the colon and its span stay in the
    # first piece, as written.
    ast = _processed_with_criteria("Server-side language: `cURL` | Stripe CLI | Ruby")
    flagged = _find_flagged(ast)
    assert len(flagged) == 1, f"Got {_flagged_paths(ast)}"
    assert [(c.type, c.content) for c in flagged[0].children] == [
        (NodeType.SEGMENT, "Server-side language: `cURL`"),
        (NodeType.SEGMENT, "Stripe CLI"),
        (NodeType.SEGMENT, "Ruby"),
    ], flagged[0].to_dict()
    print("  ✓  'Server-side language: `cURL` | ...' → one flagged row of segments")


def test_datapoint_peel_with_text_flagged():
    # `⭐⭐⭐⭐⭐ 4.8/5 (2,341 reviews)` is prose — `(2,341 reviews)` survives
    # removing the stars and the ratio, so the line is a sentence and keeps its
    # values inline (ADR-205). Nothing is flagged because nothing is split.
    ast = _processed_with_criteria("⭐⭐⭐⭐⭐ 4.8/5 (2,341 reviews)")
    assert _find_flagged(ast) == [], f"Got {_flagged_paths(ast)}"
    # The control: a line that IS a run still separates. SCORE is
    # annotation-only, so `⭐⭐⭐⭐⭐ 4.8/5` is one leaf too and cannot carry
    # the contrast; a structural peel (EMOJI/LINK) carries it.
    run = _find_flagged(_processed_with_criteria("⭐ [Link](/x)"))
    assert len(run) == 1, f"Got {run!r}"
    print("  ✓  a trailing annotation makes the line prose; a run still splits")


def test_mixed_segmented_flagged():
    ast = _processed_with_criteria("A - [Link](/link) - ⭐ - 5/5 - **Bold**")
    flagged = _find_flagged(ast)
    assert len(flagged) == 1, f"Got {_flagged_paths(ast)}"
    types = [c.type for c in flagged[0].children]
    # `5/5` is a TEXT leaf carrying a RATIO annotation: the type is
    # annotation-only, so the separator cuts the piece out without
    # relabelling it DATAPOINT.
    assert types == [
        NodeType.SEGMENT,
        NodeType.LINK,
        NodeType.EMOJI,
        NodeType.TEXT,
        NodeType.SEGMENT,
    ], f"Got {types}"
    print("  ✓  'A - [Link] - ⭐ - 5/5 - **Bold**' → flagged mixed container")


def test_kv_list_item_not_flagged():
    # list_item container of display pairs (bars): no direct text piece →
    # cleared. Un-split VALUE leaves are never containers → never flagged.
    ast = _processed_with_criteria("- CPU: 40% - RAM: 60% - Disk: 70%")
    (item,) = ast.children
    assert [c.type for c in item.children] == [NodeType.KEY_VALUE] * 3, item.to_dict()
    flagged = _find_flagged(ast)
    assert not flagged, f"Got {_flagged_paths(ast)}"
    print("  ✓  multi-KV list item → nothing flagged")


def test_heading_line_flagged_but_not_its_section():
    """A heading's own line is one source line, so it flows like any other; the
    heading SECTION container (heading + the body under it) never does."""
    ast = _processed_with_criteria("# 🚀 - Launch\n\nbody text")
    flagged = _find_flagged(ast)
    assert len(flagged) == 1, f"Got {_flagged_paths(ast)}"
    heading = flagged[0]
    assert heading.type.startswith("heading"), heading.type
    assert [c.type for c in heading.children] == [
        NodeType.EMOJI,
        NodeType.SEGMENT,
    ], [c.type for c in heading.children]
    # The section that owns the heading AND the body is not one line.
    sections = [
        n for n in _walk(ast) if n.heading_group and not n.type.startswith("heading")
    ]
    assert sections and not any(s.line_split_group for s in sections)
    print("  ✓  '# 🚀 Launch' → heading line flagged, its section not")


def test_heading_with_inline_code_flagged():
    # Separated, so the span is a chip — `### Title `code`` with nothing between
    # them is prose adjacency and stays one leaf (marker), with no line to flow.
    ast = _processed_with_criteria("### Model Distribution - `last 7d`\n\nbody text")
    flagged = _find_flagged(ast)
    assert len(flagged) == 1, f"Got {_flagged_paths(ast)}"
    assert [c.type for c in flagged[0].children] == [
        NodeType.SEGMENT,
        NodeType.INLINE_CODE,
    ], [c.type for c in flagged[0].children]
    print("  ✓  '### Title - `code`' → heading line flagged")


def test_bare_heading_not_flagged():
    # No pieces to flow: the derivation returns before the flag.
    ast = _processed_with_criteria("# Launch\n\nbody text")
    assert not _find_flagged(ast), f"Got {_flagged_paths(ast)}"
    print("  ✓  a bare heading has no line to flow")


def test_image_split_flagged():
    ast = _processed_with_criteria(
        "Intro paragraph line\n\nintro ![img](u.png) outro\n\nOutro paragraph"
    )
    flagged = _find_flagged(ast)
    assert len(flagged) == 1, f"Got {_flagged_paths(ast)}"
    types = [c.type for c in flagged[0].children]
    assert NodeType.IMAGE in types and NodeType.TEXT in types, f"Got {types}"
    print("  ✓  'intro ![img] outro' → image-split container flagged")


def test_cross_line_and_simple_kv_not_flagged():
    ast = _processed_with_criteria("A plain line\nB plain line")
    assert not _find_flagged(ast), f"Got {_flagged_paths(ast)}"
    ast = _processed_with_criteria("Fabric: organic cotton")
    assert not _find_flagged(ast), f"Got {_flagged_paths(ast)}"
    print("  ✓  cross-line glued pair / un-split 'Key: value' → nothing flagged")


def test_serialization_round_trip():
    ast = _processed_with_criteria("Cat | Dog | Fish | Snake")
    d = ast.to_dict()

    def collect(nd, out):
        if "line_split_group" in nd:
            out.append(nd)
        for c in nd.get("children", []):
            collect(c, out)

    emitted = []
    collect(d, emitted)
    assert len(emitted) == 1 and emitted[0]["line_split_group"] is True
    restored = MarkdownGroupNode.from_dict(d)
    assert len(_find_flagged(restored)) == 1
    # unflagged docs emit no key at all
    d2 = _processed_with_criteria("A plain line\nB plain line").to_dict()
    none = []
    collect(d2, none)
    assert not none
    print("  ✓  to_dict emits line_split_group only when true; from_dict round-trips")


def test_heading9_ground_truth():
    # End-to-end over the sample section in tests-hierarchy.md.
    # Expectations are keyed by a distinctive LEAF content (not child index),
    # so samples can be inserted or reordered without breaking this test:
    # for each leaf we assert whether its DIRECT container carries the flag.
    text = open("data/markdown/tests/tests-hierarchy.md").read()
    ast = _processed_with_criteria(text)

    def find_section(node):
        for c in node.children:
            if c.heading_group and any(
                ch.content == "Second level heading 9" for ch in c.children
            ):
                return c
            r = find_section(c)
            if r is not None:
                return r
        return None

    section = find_section(ast)
    assert section is not None, "heading-9 section not found"

    parents = {}  # leaf content -> list of (parent, grandparent)

    def index(node, parent=None, grand=None):
        if not node.children and node.content:
            parents.setdefault(node.content, []).append((parent, grand))
        for c in node.children:
            index(c, node, parent)

    index(section)

    def parent_flagged(leaf_content):
        assert leaf_content in parents, f"leaf {leaf_content!r} not found"
        return parents[leaf_content][0][0].line_split_group

    # Direct container of these pieces must be flagged.
    for leaf in [
        "**Opening Remarks**",  # datapoint + segment split
        "⭐ Popular",  # ` | ` strip segment (emoji stays inline)
        "Stripe CLI",  # ` | ` segments of a colon line
        "Key: value",  # ` - ` segments of a list item
        "**Bold**",  # mixed segmented line
    ]:
        assert parent_flagged(leaf), f"container of {leaf!r} should be flagged"

    # TEXT-EMOJI / TEXT-LINK: none of these carries a separator, so the boundary
    # run is never peeled and the line stays ONE leaf — nothing was split, so
    # there is no container to flag.
    for leaf in [
        # `⭐⭐⭐⭐⭐ 4.8/5 (2,341 reviews)`: the trailing annotation is regular
        # text, so the line is prose and keeps its stars and its ratio inline
        # (ADR-205).
        "⭐⭐⭐⭐⭐ 4.8/5 (2,341 reviews)",
        "📂 Folder name",
        "↗️ +3 points",
        "Rocket launch 🚀",
        "**🗓 Calendar**",
        "Text followed by 1 link [↗️](/emoji-link)",
        "Text followed by 2 links [↗️](/emoji-link) [↗️ text](/text-link)",
        "Cat, Dog, Fish, Snake",
        "Jan • Feb • Mar",  # a dot is text (ADR-205)
        # A colon is text (ADR-205), not a key-value.
        "**Colors Available:** White, Black, Navy, Heather Gray, Olive Green",
        "**Sizes:** S, M, L, XL, XXL, XXXL",
        "Key for a link: [↗️](/emoji-link)",
        "Key for 2 links: [↗️](/emoji-link) [↗️](/emoji-link)",
    ]:
        assert leaf in parents, f"expected {leaf!r} to survive as one leaf"
        assert not parent_flagged(leaf), (
            f"{leaf!r} was not split, so nothing should be flagged"
        )
    assert "2" not in parents, "prose must not be fragmented at the number"

    # NOT flagged: the sub-split segments' parent group, and the bare-prose
    # control line.
    _, strip_parent = parents["🚀 entrepreneurship"][0]
    assert strip_parent is not None and not strip_parent.line_split_group, (
        "the segments' parent group must not be flagged"
    )
    # The bare-prose control line stays an intact, un-contained leaf: at least
    # one 'Text followed by 2 links' leaf sits directly in an unflagged parent.
    bare = [
        (par, g)
        for par, g in parents["Text followed by 2 links"]
        if not par.line_split_group
    ]
    assert bare, "bare prose control should remain outside any flagged container"
    print("  ✓  heading-9 ground truth: per-sample flags match (content-keyed)")


def _cols(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    return [n for n in _walk(node) if n.column_split_group]


def test_empty_heading_marker_does_not_change_its_content():
    # `## ` with nothing after it is a GROUPING device, not a heading: the title
    # leaf is contentless and pruned, so the section collapses onto the line
    # under it. That line must render exactly as it does on its own: no
    # stacking, and no change of emoji kind because of the marker. The kinds
    # are compared to each other rather than to a literal.
    bare = _processed_with_criteria("92 : days - ⬇")
    marked = _processed_with_criteria("## \n92 : days - ⬇")
    (plain_row,) = _find_flagged(bare)
    (section,) = _find_flagged(marked)
    assert [c.type for c in section.children] == [c.type for c in plain_row.children], (
        section.to_dict()
    )
    # The section wrapper IS the flowed row here, and keeps its heading level so
    # the Heading-2 card still paints.
    assert section.heading_group and section.heading_level == 2
    kinds = [n.emoji_kind for n in _walk(marked) if n.type == NodeType.EMOJI]
    bare_kinds = [n.emoji_kind for n in _walk(bare) if n.type == NodeType.EMOJI]
    assert kinds == bare_kinds == ["alone"], marked.to_dict()
    print("  ✓  an empty '## ' groups without changing how its content renders")


def test_titled_section_still_stacks():
    # The veto is on TITLED sections — a section holding a heading leaf plus a
    # body is not one line and must not be flowed.
    ast = _processed_with_criteria("## Title\nbody text here")
    sections = [
        n
        for n in _walk(ast)
        if n.heading_group and any(c.type == "heading2" for c in n.children)
    ]
    assert sections, ast.to_dict()
    assert not any(s.line_split_group for s in sections), ast.to_dict()
    print("  ✓  a titled '## Title' section is untouched")


def test_empty_marker_with_a_multi_line_body_is_untouched():
    # Several lines under the marker: they are not one line, so nothing flows at
    # the section level and each inner line keeps its own container.
    ast = _processed_with_criteria("## \nA - B\nC - D")
    top = [n for n in _walk(ast) if n.heading_group]
    assert top and not any(n.line_split_group for n in top), ast.to_dict()
    inner = _find_flagged(ast)
    assert len(inner) == 2, [n.to_dict() for n in inner]
    print("  ✓  an empty marker over MANY lines flows each line, not the section")


def test_colon_column_container_is_not_line_split():
    # The pieces DO share a source line, so without column_split_group in the
    # `stacks` test they would be flowed along it — the exact opposite of what
    # " : " asks for.
    ast = _processed_with_criteria("A : B")
    (col,) = _cols(ast)
    assert not col.line_split_group, "a column split must never flow"
    assert [c.content for c in col.children] == ["A", "B"], col.to_dict()
    print("  ✓  a colon column container stacks, never flows")


def test_line_stacks_answers_for_each_stacking_kind():
    """`line_stacks` is the extracted rule behind the `stacks` veto, and the
    layout generator reads it too (a stacking piece is as wide as its widest
    child, not the sum). Assert it directly, not only through the flag."""
    colon = _cols(_processed_with_criteria("A : B"))[0]
    assert line_stacks(colon), "a colon column stacks"

    kv = next(
        n
        for n in _walk(_processed_with_criteria("Progress: 60%"))
        if n.type == NodeType.KEY_VALUE
    )
    assert line_stacks(kv), "a display pair stacks"

    titled = next(
        n
        for n in _walk(_processed_with_criteria("## Title\n\nA - B"))
        if n.heading_group and n.children and not n.content
    )
    assert line_stacks(titled), "a titled section stacks"

    flowed = _find_flagged(_processed_with_criteria("A - B - C"))[0]
    assert not line_stacks(flowed), "a separator line flows"
    print("  ✓  line_stacks answers for colon / KV / titled section / flow")


def test_colon_binds_tighter_than_the_separators():
    # "|" / "-" split into columns FIRST; the colon stacks within one.
    ast = _processed_with_criteria("A | B : --- : C | D")
    (row,) = _find_flagged(ast)
    assert [c.content or c.type for c in row.children] == [
        "A",
        NodeType.SEGMENT,
        "D",
    ], row.to_dict()
    (col,) = _cols(ast)
    assert [(c.type, c.content) for c in col.children] == [
        (NodeType.SEGMENT, "B"),
        (NodeType.HORIZONTAL_RULE, "---"),
        (NodeType.SEGMENT, "C"),
    ], col.to_dict()
    print("  ✓  'A | B : --- : C | D' → 3 columns, the middle one stacked")


def test_every_separator_column_can_stack():
    ast = _processed_with_criteria("A : B - C : D")
    cols = _cols(ast)
    assert len(cols) == 2, [c.to_dict() for c in cols]
    assert [[c.content for c in col.children] for col in cols] == [
        ["A", "B"],
        ["C", "D"],
    ]
    print("  ✓  'A : B - C : D' → two columns of two stacked rows")


def test_a_row_of_only_columns_still_flows():
    # Every piece of this line is itself a container, which normally hands the
    # run to the repeated-group GRID, free to re-flow it to a single column
    # (stacked A/B/C/D). A line is a line.
    ast = _processed_with_criteria("A : B - C : D")
    (row,) = _find_flagged(ast)
    assert [c.column_split_group for c in row.children] == [True, True]
    assert not row.column_split_group, "the ROW stacks nothing itself"
    print("  ✓  a line made only of columns keeps its line_split_group")


def test_column_beside_a_leaf_is_a_flowed_row():
    # "a row with a col in the left and a leaf in the right".
    ast = _processed_with_criteria("92 : days - ⬇")
    (row,) = _find_flagged(ast)
    col, leaf = row.children
    assert col.column_split_group and [c.content for c in col.children] == [
        "92",
        "days",
    ], col.to_dict()
    assert leaf.type == NodeType.EMOJI and not leaf.children, leaf.to_dict()
    print("  ✓  '92 : days - ⬇' → row[col(92/days), emoji]")


def test_metric_shape_keeps_the_number_out_of_the_key_slot():
    # The whole point: KV would style `94%` with the Overline `keys` face, the
    # inverse of the reference. As segments the author keeps the hierarchy.
    ast = _processed_with_criteria("## ✔ - 94% : Accuracy")
    (col,) = _cols(ast)
    # `94%` is a TEXT leaf carrying a PERCENTAGE annotation: the type is
    # annotation-only, so the colon stacks the two pieces without relabelling
    # the value DATAPOINT.
    assert [c.type for c in col.children] == [
        NodeType.TEXT,
        NodeType.SEGMENT,
    ], col.to_dict()
    assert not any(n.type == NodeType.KEY for n in _walk(ast)), ast.to_dict()
    print("  ✓  '## ✔ - 94% : Accuracy' stacks as segments, not key/value")


def test_tight_colon_is_text():
    # ADR-205: a tight colon neither stacks nor pairs; the line is as written.
    ast = _processed_with_criteria("Key: value")
    assert not _cols(ast), ast.to_dict()
    assert [(c.type, c.content) for c in ast.children] == [
        (NodeType.TEXT, "Key: value")
    ], ast.to_dict()
    print("  ✓  'Key: value' is one text — neither columns nor a pair")


TESTS = [
    test_empty_heading_marker_does_not_change_its_content,
    test_titled_section_still_stacks,
    test_empty_marker_with_a_multi_line_body_is_untouched,
    test_colon_column_container_is_not_line_split,
    test_line_stacks_answers_for_each_stacking_kind,
    test_colon_binds_tighter_than_the_separators,
    test_every_separator_column_can_stack,
    test_a_row_of_only_columns_still_flows,
    test_column_beside_a_leaf_is_a_flowed_row,
    test_metric_shape_keeps_the_number_out_of_the_key_slot,
    test_tight_colon_is_text,
    test_lone_line_emoji_peel_flagged,
    test_glued_paragraph_inner_containers_flagged,
    test_annotated_time_segment_split_flagged,
    test_separated_trailing_link_run_flows,
    test_leading_link_peel_flowed,
    test_mixed_peel_flowed_link_inside,
    test_prose_leading_emoji_run_is_a_text_emoji,
    test_prose_mixed_trailing_run_stays_inline,
    test_prose_trailing_link_run_is_a_text_link,
    test_gate_run_trim_text,
    test_separated_boundary_dp_splits_instead_of_stranding_the_separator,
    test_separator_between_two_peeled_links_is_not_a_node,
    test_adjacent_boundary_dp_is_a_text_emoji,
    test_subsplit_segments_flagged_not_parent,
    test_comma_list_not_flagged,
    test_labelled_comma_list_not_subsplit,
    test_colon_line_pipe_segments_flagged,
    test_datapoint_peel_with_text_flagged,
    test_mixed_segmented_flagged,
    test_kv_list_item_not_flagged,
    test_heading_line_flagged_but_not_its_section,
    test_heading_with_inline_code_flagged,
    test_bare_heading_not_flagged,
    test_image_split_flagged,
    test_cross_line_and_simple_kv_not_flagged,
    test_serialization_round_trip,
    test_heading9_ground_truth,
]

if __name__ == "__main__":
    print("Markdown Line-Split Annotation Tests")
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
