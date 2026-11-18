"""Unit tests for ASTPatternAnalyzer._annotate_orphans (orphaned repeated element).

A lone child whose kind_hash matches a kind that sibling groups grid (a repeated
bucket) is flagged ``orphan_grid`` so the layout can render it at the siblings'
card width. Built from hand-set nodes (kind_hash / repeated_children assigned
directly) so no pipeline run is needed.
"""

from md2ui.pipeline.markdown_grouper import MarkdownGroupNode, ASTPatternAnalyzer


def _node(kind, type_="group", children=None):
    n = MarkdownGroupNode("", type_)
    n.kind_hash = kind
    n.children = children or []
    return n


def _section(item_kind, n_items, extra_kind=None):
    """A section group holding *n_items* item-children of *item_kind* (bucketed
    when >=2), optionally an extra child of a different kind."""
    items = [_node(item_kind) for _ in range(n_items)]
    sec = _node(kind=999, children=list(items))
    if extra_kind is not None:
        sec.children.append(_node(extra_kind))
    sec.repeated_children = {12345: items} if n_items >= 2 else {}
    return sec, items


def _run_parent(sections):
    p = _node(kind=1, children=list(sections))
    p.repeated_children = {777: list(sections)}  # the sections are one run
    return p


def test_lone_matching_child_flagged():
    K = 740878
    s1, i1 = _section(K, 3)
    s2, i2 = _section(K, 2)
    s3, i3 = _section(K, 1)  # single product -> orphan
    p = _run_parent([s1, s2, s3])
    ASTPatternAnalyzer(p)._annotate_orphans(p)
    assert i3[0].orphan_grid is True, "lone same-kind child must be flagged"
    # gridded siblings are NOT flagged (count >= 2)
    assert all(not x.orphan_grid for x in i1 + i2)


def test_non_matching_lone_child_not_flagged():
    K = 740878
    s1, i1 = _section(K, 2)
    # a section whose single child is a DIFFERENT kind (e.g. a heading/unique)
    s2, i2 = _section(555, 1)
    p = _run_parent([s1, s2])
    ASTPatternAnalyzer(p)._annotate_orphans(p)
    assert i2[0].orphan_grid is False, "different-kind lone child must NOT be flagged"


def test_extra_child_kind_ignored():
    # A section's extra child of an un-repeated kind is never flagged.
    K = 740878
    s1, i1 = _section(K, 2)
    s3, i3 = _section(K, 1, extra_kind=814492)  # extra = horizontal rule kind
    p = _run_parent([s1, s3])
    ASTPatternAnalyzer(p)._annotate_orphans(p)
    assert i3[0].orphan_grid is True  # the product orphan
    assert s3.children[-1].orphan_grid is False  # the extra child untouched


def test_no_repeated_kind_no_flags():
    # No section grids anything (all single) -> nothing is an orphan.
    s1, i1 = _section(740878, 1)
    s2, i2 = _section(740878, 1)
    p = _run_parent([s1, s2])
    ASTPatternAnalyzer(p)._annotate_orphans(p)
    assert not i1[0].orphan_grid and not i2[0].orphan_grid


TESTS = [
    test_lone_matching_child_flagged,
    test_non_matching_lone_child_not_flagged,
    test_extra_child_kind_ignored,
    test_no_repeated_kind_no_flags,
]

if __name__ == "__main__":
    print("Orphan-Grid Annotation Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
