"""
Unit tests for the servers' shared groupings (``session.group_shared``).

The MCP shells read one text several times in one call path — ``show`` for its
issues and for the record of what it sent, a ``mark`` or ``patch`` for its
candidates and for the record of the one kept, an agent's ``check`` then
``preview`` — and group it once, handing every reader the SAME tree.

Pinned here:

  * a text grouped with one kit is the same tree on every ask, and a recorded
    message is the tree ``show`` then reads; another kit groups its own;
  * the trees kept are bounded;
  * the contract that makes sharing safe: every reader on the server path leaves
    a shared tree exactly as the grouper made it. A reader that starts editing
    the tree fails here, before it corrupts the next tool call.

Run with: uv run python tests/serve_grouping_tests.py
"""

import contextlib
import io
import json
from pathlib import Path

from md2ui import session, theme_lint
from md2ui.advice import Reading, reply_issues
from md2ui.digest import digest, theme_at
from md2ui.pipeline.render_actions import action_targets
from md2ui.wire import MessageLog
from md2ui.wire_bars import bars
from md2ui.wire_patch import _outside

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "data/markdown/tests/THEME.md"
DOCS = [
    ROOT / "data/markdown/tests/tests-link-actions.md",
    ROOT / "data/markdown/tests/tests-alignment.md",
]
BARS = (
    "# Build {#build}\n\nElapsed: 40%\n\nFiles: 4/10\n\n- [ ] Ship it\n\n"
    "## Notes\n\nA: [30%]\n\n[Go](agent:go)\n"
)

_KIT: session.GroupingKit | None = None


def _kit() -> session.GroupingKit:
    global _KIT
    if _KIT is None:
        _KIT = session.load_grouping_kit()
    return _KIT


def _dump(ast) -> str:
    return json.dumps(ast.to_dict(), sort_keys=True, default=str)


def test_one_text_is_one_tree_per_kit():
    """The same text and kit give the same tree; what a message log records is
    what ``show`` then reads; another kit groups its own."""
    with contextlib.redirect_stdout(io.StringIO()):
        first = session.group_shared(BARS, _kit())
        assert session.group_shared(BARS, _kit()) is first
        log = MessageLog(_kit())
        log.record("m1", BARS + "\nmore\n")
        recorded = session.group_shared(BARS + "\nmore\n", _kit())
        assert session.group_shared(BARS + "\nmore\n", _kit()) is recorded
        other = session.group_shared(BARS, session.load_grouping_kit())
    assert other is not first and _dump(other) == _dump(first)
    print("  ✓  one text is one tree per kit, shared by the log and its reader")


def test_the_trees_kept_are_bounded():
    with contextlib.redirect_stdout(io.StringIO()):
        oldest = session.group_shared("# Oldest", _kit())
        for n in range(session.SHARED_TREES):
            session.group_shared(f"# Page {n}", _kit())
        assert session.group_shared("# Oldest", _kit()) is not oldest
    print(f"  ✓  at most {session.SHARED_TREES} trees are kept")


def test_the_server_readers_leave_a_shared_tree_unchanged():
    """Every step the servers run over a grouped tree, run over a shared one,
    leaves it as the grouper made it: the read-only contract of group_shared."""
    theme = session.load_theme(THEME)
    contract = theme_lint.answer_contract(THEME)
    texts = [BARS, *(p.read_text() for p in DOCS)]
    with contextlib.redirect_stdout(io.StringIO()):
        for text in texts:
            ast = session.group_shared(text, _kit())
            assert ast is not None
            before = _dump(ast)
            assert before == _dump(session.group_markdown(text, _kit()))
            reply_issues(text, ast, contract, Reading())  # check, show
            Reading().advise(ast.to_dict(), contract)  # preview's notes
            digest(ast, theme_at(THEME))  # show
            action_targets(ast.to_dict())  # actions, the log's targets
            session.prepare(ast, theme)  # layout, preview
            bars(text, _kit())  # feed
            _outside(text, 0, _kit())  # patch
            MessageLog(_kit()).record("m1", text)  # show, mark, patch
            assert _dump(ast) == before, f"a server step edited {text[:30]!r}"
            assert session.group_shared(text, _kit()) is ast
    print("  ✓  the server's readers leave a shared tree unchanged")


TESTS = [
    test_one_text_is_one_tree_per_kit,
    test_the_trees_kept_are_bounded,
    test_the_server_readers_leave_a_shared_tree_unchanged,
]

if __name__ == "__main__":
    print("Serve Grouping Tests")
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
    print(f"All {len(TESTS)} tests passed.")
