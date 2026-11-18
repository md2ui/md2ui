"""
The two colon syntaxes, and the marker families they may be written in.

Markdown gives a colon two jobs, told apart by SPACING:

    Key: value      the colon is TIGHT to its key  -> text, drawn as written,
                    unless a display reads the pair (ADR-205)
    A : B           a space on each side           -> a stacked column

Both are covered end to end here, where the passes meet:

* the key-value split runs on ``_Expires:_ 12/26``, a pair a ratio bar reads,
  whichever marker family wraps the key: the gate ahead of it must answer the
  ``_`` spelling as it answers the ``*``, ``**`` and unmarked twins. ``_x_``
  and ``*x*`` are the same markup, so which one an author reached for may not
  change the tree (ADR-201: styling is not structure);
* on a line holding BOTH colons (``_Expires:_ : 12/26``) the spaced colon cuts
  first and the tight one stays in its piece, so no value starts ``": 12/26"``.

A colon with nothing after it is text too: ``Panelists:`` draws its colon, and
its escaped twin ``Panelists\\:`` draws the same (ADR-205).

Run with: uv run python tests/colon_syntax_tests.py
"""

from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline.grouper_node_reads import _classification_text
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType


SPELLINGS = [
    "Expires: 12/26",
    "*Expires:* 12/26",
    "**Expires:** 12/26",
    "_Expires:_ 12/26",
]


def _find(node: MarkdownGroupNode, node_type: str) -> list[MarkdownGroupNode]:
    out = [node] if node.type == node_type else []
    for c in node.children:
        out.extend(_find(c, node_type))
    return out


def _leaf_texts(node: MarkdownGroupNode) -> list[str]:
    out = [node.content] if node.content and not node.children else []
    for c in node.children:
        out.extend(_leaf_texts(c))
    return out


def _bare(text: str) -> str:
    return text.strip().strip("*_~`").strip()


def test_every_marker_family_reaches_the_key_value_split():
    """The gate may not answer differently for ``_`` than for ``*``."""
    for spelling in SPELLINGS:
        ast = _processed_with_criteria(f"## Card details\n\n{spelling}\n")
        pairs = _find(ast, NodeType.KEY_VALUE)
        assert len(pairs) == 1, f"{spelling!r} produced {len(pairs)} pairs"
        key, value = pairs[0].children
        assert _bare(key.content) == "Expires", f"{spelling!r} key {key.content!r}"
        assert "12/26" in " ".join(_leaf_texts(value)), spelling
    print("  ✓  plain / * / ** / _ all split into key + value")


def test_the_gate_reads_one_marker_family():
    """The direct half of the test above: just the text the gate is handed.
    Underscore runs arrive as their asterisk synonyms."""
    assert _classification_text("_Expires:_ 12/26", []) == "*Expires:* 12/26"
    assert _classification_text("**Bold:** _muted_ 12", []) == "**Bold:** *muted* 12"
    # An intraword underscore is an identifier, not markup (CommonMark), and
    # a whole-content wrap is still dropped rather than translated.
    assert _classification_text("user_id: 12", []) == "user_id: 12"
    assert _classification_text("___$412M___", []) == "$412M"
    print("  ✓  _ runs normalise to * for the gate; snake_case untouched")


def test_a_spaced_colon_still_stacks_instead():
    """The other syntax: ``_Expires_ : 12/26`` is a COLUMN, so it
    stacks two pieces and mints no key-value."""
    ast = _processed_with_criteria("## Card details\n\n_Expires_ : 12/26\n")
    assert _find(ast, NodeType.KEY_VALUE) == []
    columns = [n for n in _find(ast, NodeType.GROUP) if n.column_split_group]
    assert len(columns) == 1, "the spaced colon should fold one column"
    assert [_bare(t) for t in _leaf_texts(columns[0])] == ["Expires", "12/26"]
    print("  ✓  ` : ` still folds a column, and is not a key-value")


def test_both_colons_on_one_line_fold_one_column():
    """The spaced colon outranks the tight one: ``_Expires:_ : 12/26`` and its unmarked
    twins fold a column whose first piece keeps its colon as written, and no
    piece starts with the column colon it was cut at."""
    for spelling in ("_Expires:_ : 12/26", "Expires: : 12/26", "**Expires:** : 12/26"):
        ast = _processed_with_criteria(f"## Card details\n\n{spelling}\n")
        assert _find(ast, NodeType.KEY_VALUE) == [], spelling
        columns = [n for n in _find(ast, NodeType.GROUP) if n.column_split_group]
        assert len(columns) == 1, spelling
        texts = [_bare(t) for t in _leaf_texts(columns[0])]
        assert texts == ["Expires:", "12/26"], f"{spelling}: {texts}"
    print("  ✓  both colons fold one column; the tight colon is drawn")


def test_a_trailing_colon_is_drawn():
    """``Label:`` draws "Label:" in every marker family, and its escaped twin
    draws the same, never the backslash."""
    cases = {
        "Panelists:": "Panelists:",
        "**Panelists:**": "**Panelists:**",
        "Panelists\\:": "Panelists:",
        "**Panelists\\:**": "**Panelists:**",
        "*Panelists\\:*": "*Panelists:*",
        "~~Panelists\\:~~": "~~Panelists:~~",
        "Here is how they stack up:": "Here is how they stack up:",
    }
    for spelling, drawn in cases.items():
        texts = _leaf_texts(_processed_with_criteria(f"{spelling}\n\n- Ana\n- Bo\n"))
        assert texts[0] == drawn, f"{spelling!r}: {texts}"
        assert not any("\\" in t for t in texts), f"{spelling!r}: {texts}"
    print("  ✓  a trailing colon is drawn, escaped or not")


TESTS = [
    test_a_trailing_colon_is_drawn,
    test_every_marker_family_reaches_the_key_value_split,
    test_the_gate_reads_one_marker_family,
    test_a_spaced_colon_still_stacks_instead,
    test_both_colons_on_one_line_fold_one_column,
]


if __name__ == "__main__":
    print("Colon Syntax Tests")
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
