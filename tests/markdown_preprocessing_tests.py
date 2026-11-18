"""
Unit tests for MarkdownGrouper preprocessing: preprocess() and to_ast().
Run with: uv run markdown_preprocessing_tests.py
"""

from md2ui.pipeline.markdown_grouper import MarkdownGrouper, MarkdownGroupNode, NodeType

# ---------------------------------------------------------------------------
# Tree-inspection helpers
# ---------------------------------------------------------------------------


def node_shape(node: MarkdownGroupNode) -> dict:
    """Compact representation of a node: label, content (trimmed), child count."""
    return {
        "type": node.type,
        "content": node.content,
        "n_children": len(node.children),
    }


def assert_node(
    node: MarkdownGroupNode,
    label: str,
    content: str = "",
    n_children: int = 0,
    ctx: str = "",
) -> None:
    prefix = f"[{ctx}] " if ctx else ""
    assert node.type == label, f"{prefix}label: got {node.type!r}, expected {label!r}"
    assert node.content == content, (
        f"{prefix}content: got {node.content!r}, expected {content!r}"
    )
    assert len(node.children) == n_children, (
        f"{prefix}n_children: got {len(node.children)}, expected {n_children}"
    )


def ast(text: str) -> MarkdownGroupNode:
    """Build the heading-level AST without running the full pipeline."""
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    return g.ast


def preprocessed(text: str) -> str:
    """Return the text after preprocess() only."""
    g = MarkdownGrouper(text)
    g.preprocess()
    return g.text


# ---------------------------------------------------------------------------
# preprocess() tests
# ---------------------------------------------------------------------------


def test_fenced_code_backticks():
    text = "Before.\n```python\nx = 1\n```\nAfter."
    result = preprocessed(text)
    assert "```" not in result
    assert "x = 1" not in result
    assert "[unsupported element (code block)]" in result
    assert "Before." in result
    assert "After." in result
    print("  ✓  preprocess: fenced code (backticks)")


def test_fenced_code_tildes():
    text = "Before.\n~~~\nsome code\n~~~\nAfter."
    result = preprocessed(text)
    assert "~~~" not in result
    assert "some code" not in result
    assert "[unsupported element (code block)]" in result
    assert "Before." in result
    assert "After." in result
    print("  ✓  preprocess: fenced code (tildes)")


def test_fenced_code_long_fence():
    # 4+ backticks should also be treated as a fence
    text = "````\nsome source\n````\n"
    result = preprocessed(text)
    assert "````" not in result, f"Backticks should be removed, got: {result!r}"
    assert "some source" not in result, f"Fence body should be removed, got: {result!r}"
    assert "[unsupported element (code block)]" in result
    print("  ✓  preprocess: fenced code (4+ backticks)")


def test_indented_code_4_spaces():
    text = "Paragraph.\n\n    indented code\n    more code\n\nAfter."
    result = preprocessed(text)
    assert "    indented code" not in result
    assert "[unsupported element (code block)]" in result
    assert "After." in result
    print("  ✓  preprocess: indented code (4 spaces)")


def test_indented_code_tab():
    text = "Paragraph.\n\n\tindented code\n\nAfter."
    result = preprocessed(text)
    assert "\tindented code" not in result
    assert "[unsupported element (code block)]" in result
    assert "After." in result
    print("  ✓  preprocess: indented code (tab)")


def test_blockquote_single():
    # Blockquotes survive preprocess: the '>' stays so a
    # later pass (_split_blockquote) can parse it into a BLOCKQUOTE node.
    text = "Before.\n> This is a quote.\nAfter."
    result = preprocessed(text)
    assert "> This is a quote." in result
    assert "[unsupported element (blockquote)]" not in result
    assert "Before." in result
    assert "After." in result
    print("  ✓  preprocess: blockquote (single line) survives")


def test_blockquote_multiline():
    text = "> Line one.\n> Line two.\nAfter."
    result = preprocessed(text)
    assert "> Line one." in result
    assert "> Line two." in result
    assert "[unsupported element (blockquote)]" not in result
    assert "After." in result
    print("  ✓  preprocess: blockquote (multi-line) survives")


def test_blockquote_nested():
    # Nested '>>' also survives preprocess untouched; single-level peeling (one
    # '>') happens later in _split_blockquote, leaving the inner '>' literal.
    text = ">> Nested quote.\nAfter."
    result = preprocessed(text)
    assert ">> Nested quote." in result
    assert "[unsupported element (blockquote)]" not in result
    print("  ✓  preprocess: blockquote (nested >>) survives")


def test_multiple_unsupported():
    # Only code blocks are replaced (2); the blockquote body survives. The
    # indented code block is preceded by a blank line so it is a genuine block
    # (an indented run cannot start a code block right after a non-blank line).
    text = (
        "Intro.\n```\nfence_body\n```\n> blockquote_body\n\n    indented_body\nOutro."
    )
    result = preprocessed(text)
    assert "fence_body" not in result, f"Fence body should be removed, got: {result!r}"
    assert "blockquote_body" in result, (
        f"Blockquote body should survive, got: {result!r}"
    )
    assert "indented_body" not in result, (
        f"Indented body should be removed, got: {result!r}"
    )
    assert result.count("[unsupported element") == 2, (
        f"Expected 2 replacements, got {result.count('[unsupported element')}: {result!r}"
    )
    assert "Intro." in result
    assert "Outro." in result
    print("  ✓  preprocess: multiple unsupported elements (blockquote survives)")


def test_indented_code_requires_blank_line():
    # A 4-space run right after a non-blank line is NOT a code block (it cannot
    # interrupt a paragraph / list item) — e.g. a double-digit ordered item whose
    # continuation aligns at 4 spaces. A run after a blank line still is code.
    cont = "10. Item ten\n    - detail line\n"
    r1 = preprocessed(cont)
    assert "detail line" in r1, f"list continuation must survive: {r1!r}"
    assert "[unsupported element" not in r1, f"must not be code: {r1!r}"

    para = "A paragraph line\n    still the paragraph\n"
    r2 = preprocessed(para)
    assert "still the paragraph" in r2 and "[unsupported element" not in r2

    genuine = "Intro.\n\n    real_code_body\n\nOutro."
    r3 = preprocessed(genuine)
    assert "real_code_body" not in r3, f"genuine code block must be replaced: {r3!r}"
    assert r3.count("[unsupported element") == 1
    print("  ✓  preprocess: indented code requires a preceding blank line")


def test_plain_text_unchanged():
    text = "Hello, world.\nSecond line."
    result = preprocessed(text)
    assert result == text
    print("  ✓  preprocess: plain text unchanged")


def test_zero_width_joiner_survives_preprocess():
    # U+200D joins an emoji sequence (👨‍💻 is man + joiner + laptop), so it is
    # kept. The zero-width space, the non-joiner and the BOM are stripped.
    technologist = "\U0001f468\u200d\U0001f4bb"
    assert preprocessed(f"{technologist} Developer") == f"{technologist} Developer"
    assert preprocessed("a\u200bb\u200cc\ufeffd") == "abcd"
    print("  ✓  preprocess: a zero-width joiner survives, other zero-widths go")


def test_inline_code_not_replaced():
    # Single-backtick inline code should NOT be replaced
    text = "Use `print()` to output text."
    result = preprocessed(text)
    assert "`print()`" in result
    print("  ✓  preprocess: inline code not replaced")


# ---------------------------------------------------------------------------
# to_ast() — empty / invalid input
# ---------------------------------------------------------------------------


def test_empty_input():
    root = ast("")
    assert_node(root, "root", content="", n_children=0, ctx="empty input")
    print("  ✓  to_ast: empty input → empty root")


def test_whitespace_only():
    # Use spaces only — tab + chars would match the indented-code regex.
    # Three spaces per line don't match (needs 4 spaces or a tab).
    root = ast("   \n\n   \n")
    assert_node(root, "root", content="", n_children=0, ctx="whitespace only")
    print("  ✓  to_ast: whitespace-only → empty root")


# ---------------------------------------------------------------------------
# to_ast() — no-heading documents
# ---------------------------------------------------------------------------


def test_no_headings_plain():
    root = ast("Just some text.")
    assert root.type == "root"
    assert root.content == "Just some text."
    assert len(root.children) == 0
    print("  ✓  to_ast: no headings → root carries content")


def test_no_headings_multiline():
    root = ast("Line one.\nLine two.\nLine three.")
    assert root.content == "Line one.\nLine two.\nLine three."
    print("  ✓  to_ast: no headings, multiline → content preserved")


def test_underscores_are_an_invisible_break():
    # `___` cuts the document exactly as a rule does — same ordered
    # TEXT/BREAK/TEXT children — but as its own node type, so the renderer
    # paints nothing. It is the level-agnostic sibling of an empty `## `
    # marker: it splits a group in two without opening a section.
    root = ast("Text before.\n\n___\n\nText after.")
    types = [c.type for c in root.children]
    assert types == [
        NodeType.TEXT,
        NodeType.CONTENT_BREAK,
        NodeType.TEXT,
    ], types
    assert root.children[1].content == "___"
    print("  ✓  to_ast: a '___' line → an invisible CONTENT_BREAK child")


def test_a_lone_underscore_is_ordinary_text():
    # `___` needs three. Every shorter underscore
    # spelling already means something else (`_x_` italic, `__x__` /
    # `___x___` display tiers), so a bare `_` is simply a character.
    for src in ("_", "__", "_italic_", "__bold__", "___tier___", "a _ b", "_ x", "x _"):
        root = ast(src)
        found = [
            c
            for c in root.children
            if c.type in (NodeType.CONTENT_BREAK, NodeType.HORIZONTAL_RULE)
        ]
        assert not found, f"{src!r} must not produce a break: {root.to_dict()}"
    # …and a whole-line `___` IS the break, even though `___x___` is a tier.
    (brk,) = [
        c for c in ast("a\n\n___\n\nb").children if c.type == NodeType.CONTENT_BREAK
    ]
    assert brk.content == "___"
    print("  ✓  one or two underscores are text; three on their own line cut")


def test_no_headings_with_hr():
    root = ast("Text before.\n\n---\n\nText after.")
    # No-heading docs segment into ordered TEXT / HR children; the text lives in
    # the children, not root.content. The HR node carries its own marker line.
    assert root.content == ""
    assert len(root.children) == 3
    types = [c.type for c in root.children]
    assert types == [NodeType.TEXT, NodeType.HORIZONTAL_RULE, NodeType.TEXT], types
    assert root.children[0].content == "Text before."
    assert root.children[1].content == "---"
    assert root.children[2].content == "Text after."
    print("  ✓  to_ast: no headings + HR → ordered text/HR/text children")


# ---------------------------------------------------------------------------
# to_ast() — heading structure
# ---------------------------------------------------------------------------


def test_single_heading_no_body():
    root = ast("# My Title")
    assert_node(root, "root", content="", n_children=1)
    group = root.children[0]
    assert_node(group, NodeType.GROUP, content="", n_children=1)
    heading = group.children[0]
    assert_node(heading, "heading1", content="My Title", n_children=0)
    print("  ✓  to_ast: single heading, no body")


def test_single_heading_with_body():
    root = ast("## Section\n\nBody text here.")
    assert_node(root, "root", n_children=1)
    group = root.children[0]
    assert_node(group, NodeType.GROUP, n_children=2)
    assert group.children[0].type == "heading2"
    assert group.children[0].content == "Section"
    assert group.children[1].type == NodeType.TEXT
    assert group.children[1].content == "Body text here."
    print("  ✓  to_ast: single heading + body text")


def test_heading_text_stripped():
    # Leading #s and space must be stripped from heading content
    root = ast("### Hello World")
    heading = root.children[0].children[0]
    assert heading.content == "Hello World", f"Got {heading.content!r}"
    assert heading.type == "heading3"
    print("  ✓  to_ast: heading # prefix stripped")


def test_heading_levels_h1_to_h6():
    lines = "\n".join(f"{'#' * i} H{i}" for i in range(1, 7))
    root = ast(lines)
    # H1 is the outermost; H2–H6 nest inside it
    h1_group = root.children[0]
    assert h1_group.children[0].type == "heading1"
    # H2 should be a child of H1's group
    h2_group = h1_group.children[-1]
    assert h2_group.children[0].type == "heading2"
    print("  ✓  to_ast: heading levels H1–H6")


def test_multiple_headings_same_level():
    text = "# Alpha\n\nBody A.\n\n# Beta\n\nBody B.\n\n# Gamma"
    root = ast(text)
    assert_node(root, "root", n_children=3)
    labels = [c.children[0].content for c in root.children]
    assert labels == ["Alpha", "Beta", "Gamma"], f"Got {labels}"
    print("  ✓  to_ast: multiple H1s → sibling groups")


def test_preamble_before_first_heading():
    text = "Intro text.\n\n# Section One\n\nBody."
    root = ast(text)
    # First child is a text node for the preamble
    assert root.children[0].type == NodeType.TEXT
    assert root.children[0].content == "Intro text."
    # Second child is the heading group
    assert root.children[1].children[0].type == "heading1"
    print("  ✓  to_ast: preamble before first heading")


def test_nested_h1_h2():
    text = "# Top\n\n## Sub A\n\nBody A.\n\n## Sub B\n\nBody B."
    root = ast(text)
    assert_node(root, "root", n_children=1)
    h1_group = root.children[0]
    # Children: heading1 + group(Sub A) + group(Sub B)
    assert h1_group.children[0].type == "heading1"
    assert h1_group.children[1].children[0].type == "heading2"
    assert h1_group.children[1].children[0].content == "Sub A"
    assert h1_group.children[2].children[0].content == "Sub B"
    print("  ✓  to_ast: nested H1 > H2 > H2")


def test_nested_h1_h2_h3():
    text = "# Top\n## Mid\n### Deep\n\nDeep body."
    root = ast(text)
    h1_group = root.children[0]
    h2_group = h1_group.children[1]
    h3_group = h2_group.children[1]
    assert h3_group.children[0].type == "heading3"
    assert h3_group.children[0].content == "Deep"
    assert h3_group.children[1].content == "Deep body."
    print("  ✓  to_ast: nested H1 > H2 > H3")


# ---------------------------------------------------------------------------
# to_ast() — leading-content absorption (run glued directly above a heading)
# ---------------------------------------------------------------------------


def test_absorb_glued_content_above_heading():
    # No blank line between the image line and the heading → absorbed into the
    # heading's group, before the heading node.
    text = "![hero](x.png)\n## Title\nBody.\n[CTA](y)"
    root = ast(text)
    assert_node(root, "root", n_children=1)
    group = root.children[0]
    assert group.children[0].type == NodeType.TEXT
    assert group.children[0].content == "![hero](x.png)"
    assert group.children[1].type == "heading2"
    assert group.children[1].content == "Title"
    print("  ✓  to_ast: glued content above heading absorbed into group")


def test_blank_separated_content_not_absorbed():
    # A blank line between the content and the heading keeps them separate:
    # the image stays in the preamble on root.
    text = "![hero](x.png)\n\n\n## Title\nBody."
    root = ast(text)
    assert root.children[0].type == NodeType.TEXT
    assert root.children[0].content == "![hero](x.png)"
    group = root.children[1]
    assert group.children[0].type == "heading2"
    print("  ✓  to_ast: blank-separated content stays out of group")


def test_glued_run_between_headings_stays_with_first():
    # "First heading absorbs first": content glued straight out of a previous
    # heading is that heading's body and is NOT stolen by the next heading.
    text = "## First\n![hero](x.png)\n## Second\nBody."
    root = ast(text)
    first, second = root.children[0], root.children[1]
    assert first.children[0].content == "First"
    assert first.children[1].type == NodeType.TEXT
    assert first.children[1].content == "![hero](x.png)"
    assert second.children[0].content == "Second"
    assert len(second.children) == 2  # heading + body only
    print("  ✓  to_ast: glued run between headings stays with the first")


def test_doc_start_run_absorbed_by_first_heading():
    # A run at the very start of the document, glued to the first heading,
    # is absorbed; a following same-level heading absorbs nothing.
    text = "![hero](x.png)\n## First\n## Second\nBody."
    root = ast(text)
    first, second = root.children[0], root.children[1]
    assert first.children[0].type == NodeType.TEXT
    assert first.children[0].content == "![hero](x.png)"
    assert first.children[1].content == "First"
    assert second.children[0].content == "Second"
    assert len(second.children) == 2  # heading + body only
    print("  ✓  to_ast: doc-start run absorbed by first heading only")


def test_same_level_resets_nesting():
    # A second H2 should not nest inside the first H2
    text = "# Top\n## A\n## B"
    root = ast(text)
    h1_group = root.children[0]
    child_labels = [
        c.children[0].type for c in h1_group.children if c.type == NodeType.GROUP
    ]
    assert child_labels == ["heading2", "heading2"]
    print("  ✓  to_ast: second H2 resets to sibling of first H2")


def test_body_multiline_joined():
    text = "# Title\n\nLine one.\nLine two.\nLine three."
    root = ast(text)
    body = root.children[0].children[1]
    assert body.type == NodeType.TEXT
    assert body.content == "Line one.\nLine two.\nLine three."
    print("  ✓  to_ast: multiline body joined with newlines")


# ---------------------------------------------------------------------------
# to_ast() — horizontal rules
# ---------------------------------------------------------------------------


def test_each_thematic_break_spelling_has_its_own_job():
    # Markdown's three thematic-break spellings, three meanings. Three
    # characters or more, interior spaces allowed, and each one cuts -- `---`
    # only as a block of its own: written tight between two lines it divides
    # that block instead, and stays in its text until the newline split.
    for markers, expected, gap in (
        (("---", "-----", "- - -"), NodeType.HORIZONTAL_RULE, "\n\n"),
        (("___", "____", "_ _ _"), NodeType.CONTENT_BREAK, "\n"),
        # A section stop leaves no node at all when nothing holds it.
        (("***", "****", "* * *"), None, "\n"),
    ):
        for marker in markers:
            tight = ast(f"Before.\n{marker}\nAfter.")
            if expected == NodeType.HORIZONTAL_RULE:
                assert tight.content == f"Before.\n{marker}\nAfter.", marker
            root = ast(f"Before.{gap}{marker}{gap}After.")
            got = [c.type for c in root.children if c.type != NodeType.TEXT]
            assert got == ([expected] if expected else []), (marker, got)
            # The marker never leaks into the surrounding text either way.
            texts = [c.content for c in root.children if c.type == NodeType.TEXT]
            assert texts == ["Before.", "After."], (marker, texts)
    print("  ✓  to_ast: --- rule / ___ break / *** stop, 3+ chars, spaced")


def test_hr_inside_heading_section():
    text = "# Section\n\nContent.\n\n---\n\nMore content."
    root = ast(text)
    group = root.children[0]
    hr_nodes = [c for c in group.children if c.type == NodeType.HORIZONTAL_RULE]
    assert len(hr_nodes) == 1
    # The HR marker must not leak into any TEXT node's content; the HR node
    # itself legitimately carries its '---' marker line.
    for child in group.children:
        if child.type != NodeType.HORIZONTAL_RULE:
            assert "---" not in child.content
    print("  ✓  to_ast: HR inside heading section")


def test_hr_before_first_heading():
    text = "---\n\n# Section\n\nBody."
    root = ast(text)
    hr_nodes = [c for c in root.children if c.type == NodeType.HORIZONTAL_RULE]
    assert len(hr_nodes) == 1
    print("  ✓  to_ast: HR before first heading → HR child of root")


def test_multiple_hrs():
    text = "Text.\n\n---\n\nMiddle.\n\n---\n\nEnd."
    root = ast(text)
    hr_nodes = [c for c in root.children if c.type == NodeType.HORIZONTAL_RULE]
    assert len(hr_nodes) == 2, f"Expected 2 HRs, got {len(hr_nodes)}"
    print("  ✓  to_ast: multiple HRs in no-heading doc")


# ---------------------------------------------------------------------------
# to_ast() — preprocess integration
# ---------------------------------------------------------------------------


def test_code_block_replaced_before_ast():
    # Even though the code block starts with 4 spaces, to_ast should not
    # treat the placeholder as indented code; heading should still parse.
    text = "# Title\n\n```python\ncode here\n```\n\nBody."
    root = ast(text)
    group = root.children[0]
    body = group.children[1]
    assert "code here" not in body.content
    assert "[unsupported element (code block)]" in body.content
    print("  ✓  to_ast: code block replaced before AST construction")


def test_blockquote_survives_to_ast():
    # to_ast runs preprocess but not _split_blockquote, so the '>' survives into
    # the section body content (it is parsed into a BLOCKQUOTE node later, in
    # process()); it is not replaced with a placeholder.
    text = "# Title\n\n> Quote text\n\nBody."
    root = ast(text)
    group = root.children[0]
    body = group.children[1]
    assert "> Quote text" in body.content
    assert "[unsupported element (blockquote)]" not in body.content
    print("  ✓  to_ast: blockquote survives preprocess (parsed later)")


def _leaves(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    if not node.children:
        return [node]
    return [leaf for c in node.children for leaf in _leaves(c)]


def test_an_escaped_hash_is_text_not_a_heading():
    """CommonMark's ``\\#`` is a literal hash: the line is body text that
    starts with ``# ``, as a paragraph and as a list item alike."""
    from markdown_datapoint_split_tests import _processed_with_criteria

    assert preprocessed("\\# Not a heading") == "\\# Not a heading"
    for text, kind in (
        ("\\# Not a heading", NodeType.TEXT),
        ("- \\# Not a heading\n- A plain item", NodeType.LIST_ITEM),
    ):
        first = _leaves(_processed_with_criteria(text))[0]
        assert (first.type, first.content, first.atx_level) == (
            kind,
            "# Not a heading",
            0,
        ), (text, first.type, first.content, first.atx_level)
    print("  ✓  \\# is text that starts with a hash, never a heading")


def test_an_escaped_angle_is_text_not_a_quote():
    """CommonMark's ``\\>`` is a literal ``>``: a line that starts with one is
    body text, not a blockquote. Mid-line it is the character, as before, and an
    unescaped ``>`` still opens a quote."""
    from markdown_datapoint_split_tests import _processed_with_criteria

    assert preprocessed("\\> Not a quote") == "\\> Not a quote"
    for text, want in (
        ("\\> Not a quote", (NodeType.TEXT, "> Not a quote")),
        ("Price \\> 100", (NodeType.TEXT, "Price > 100")),
        ("> A quote", (NodeType.BLOCKQUOTE, "A quote")),
    ):
        first = _leaves(_processed_with_criteria(text))[0]
        assert (first.type, first.content) == want, (text, first.type, first.content)
    print("  ✓  \\> is text that starts with an angle, never a quote")


def test_a_heading_inside_a_list_item_keeps_its_level():
    """The unescaped twin: an authored ``- # Title`` is still a heading."""
    from markdown_datapoint_split_tests import _processed_with_criteria

    first = _leaves(_processed_with_criteria("- # Title\n- A plain item"))[0]
    assert (first.content, first.atx_level) == ("Title", 1), (
        first.content,
        first.atx_level,
    )
    print("  ✓  - # Title keeps atx_level 1")


def test_a_code_span_keeps_its_backslashes():
    """A code span is literal, as in CommonMark: neither an early escape
    (`` `\\` ``, `` `\\*` ``) nor a late one (`` `a\\-b` ``) works inside it,
    in a text or as a chip of its own; outside one every escape still does,
    and an escaped backtick opens no span."""
    from markdown_datapoint_split_tests import _processed_with_criteria

    for text, want in (
        ("A trailing `\\` here", "A trailing `\\` here"),
        ("`\\` alone", "`\\` alone"),
        ("`a\\-b` and `x\\*y` and \\_star\\_", "`a\\-b` and `x\\*y` and _star_"),
        ("\\`not code\\` and `C:\\path`", "`not code` and `C:\\path`"),
        ("- `a\\-b`\n- `c\\/d`", "a\\-b"),
    ):
        first = _leaves(_processed_with_criteria(text))[0]
        assert first.content == want, (text, first.content, want)
    print("  ✓  a code span keeps its backslashes; escapes outside it resolve")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    test_underscores_are_an_invisible_break,
    test_a_lone_underscore_is_ordinary_text,
    # preprocess
    test_fenced_code_backticks,
    test_fenced_code_tildes,
    test_fenced_code_long_fence,
    test_indented_code_4_spaces,
    test_indented_code_tab,
    test_blockquote_single,
    test_blockquote_multiline,
    test_blockquote_nested,
    test_multiple_unsupported,
    test_indented_code_requires_blank_line,
    test_plain_text_unchanged,
    test_zero_width_joiner_survives_preprocess,
    test_inline_code_not_replaced,
    # to_ast — empty/invalid
    test_empty_input,
    test_whitespace_only,
    # to_ast — no headings
    test_no_headings_plain,
    test_no_headings_multiline,
    test_no_headings_with_hr,
    # to_ast — heading structure
    test_single_heading_no_body,
    test_single_heading_with_body,
    test_heading_text_stripped,
    test_heading_levels_h1_to_h6,
    test_multiple_headings_same_level,
    test_preamble_before_first_heading,
    test_nested_h1_h2,
    test_nested_h1_h2_h3,
    # to_ast — leading-content absorption
    test_absorb_glued_content_above_heading,
    test_blank_separated_content_not_absorbed,
    test_glued_run_between_headings_stays_with_first,
    test_doc_start_run_absorbed_by_first_heading,
    test_same_level_resets_nesting,
    test_body_multiline_joined,
    # to_ast — horizontal rules
    test_each_thematic_break_spelling_has_its_own_job,
    test_hr_inside_heading_section,
    test_hr_before_first_heading,
    test_multiple_hrs,
    # to_ast — preprocess integration
    test_code_block_replaced_before_ast,
    test_blockquote_survives_to_ast,
    test_an_escaped_hash_is_text_not_a_heading,
    test_an_escaped_angle_is_text_not_a_quote,
    test_a_heading_inside_a_list_item_keeps_its_level,
    test_a_code_span_keeps_its_backslashes,
]

if __name__ == "__main__":
    print("Markdown Preprocessing Tests")
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
