"""
Which characters md2ui sends to the emoji face: the grouper's emoji pattern
(``detector_vocabulary``) and the renderer's runs (``render_text``) are two copies
of one list, pinned here against Unicode's ``emoji-test.txt`` (Emoji 16.0).

Pinned here:

  * every fully-qualified emoji that is one codepoint is an emoji to both, alone;
  * a character whose emoji form needs U+FE0F (``©️ ™️ ℹ️``) is an emoji to both
    only with it, so ``© 2026`` and ``Acme™`` stay text;
  * England, Scotland and Wales (🏴 + tag characters) are one emoji: one badge
    on their own line, not a badge per tag.

Run with: uv run python tests/emoji_routing_tests.py
"""

import contextlib
import io

from md2ui import session
from md2ui.pipeline.detector_vocabulary import EMOJI_CHAR_PATTERN
from md2ui.pipeline.render_text import _is_emoji_char, _split_emoji_runs
from md2ui.session import repo_root

_TEST_FILE = repo_root() / "assets/icons/source/emoji-test.txt"
ENGLAND = "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f"


def _fully_qualified() -> list[list[int]]:
    return [
        [int(cp, 16) for cp in line.split(";")[0].split()]
        for line in _TEST_FILE.read_text().splitlines()
        if "; fully-qualified" in line
    ]


def _emoji_run(text: str) -> bool:
    return _split_emoji_runs(text) == [(text, True)]


def test_a_one_codepoint_emoji_is_an_emoji_to_both():
    singles = [chr(cps[0]) for cps in _fully_qualified() if len(cps) == 1]
    assert len(singles) > 1000, "fixture drift"
    grouper = [c for c in singles if not EMOJI_CHAR_PATTERN.fullmatch(c)]
    renderer = [c for c in singles if not _is_emoji_char(c)]
    assert grouper == [] and renderer == [], (grouper, renderer)
    print("  ✓  every one-codepoint emoji is an emoji to the grouper and the renderer")


def test_a_text_default_symbol_is_an_emoji_only_with_its_selector():
    bases = {
        chr(cps[0])
        for cps in _fully_qualified()
        if len(cps) == 2 and cps[1] == 0xFE0F and not chr(cps[0]).isascii()
    }
    for c in sorted(bases):
        assert EMOJI_CHAR_PATTERN.fullmatch(c + "️"), c
        assert _emoji_run(c + "️"), c
    bare_text = sorted(c for c in bases if not _is_emoji_char(c))
    assert "©" in bare_text and "™" in bare_text, bare_text
    for c in bare_text:
        assert not EMOJI_CHAR_PATTERN.search(c), c
    runs = _split_emoji_runs("© 2026 Acme™ ℹ Notice")
    assert all(not is_emoji for _, is_emoji in runs), runs
    print("  ✓  ©️ ™️ ℹ️ are emoji with U+FE0F; © 2026 and Acme™ stay text")


def test_a_tag_flag_is_one_emoji():
    assert EMOJI_CHAR_PATTERN.fullmatch(ENGLAND)
    assert _emoji_run(ENGLAND)
    with contextlib.redirect_stdout(io.StringIO()):
        ast = session.group_markdown(ENGLAND + "\n", session.load_grouping_kit())
    assert ast is not None
    leaves = []

    def walk(n):
        if not n.children:
            leaves.append(n)
        for c in n.children:
            walk(c)

    walk(ast)
    assert [(str(n.type), n.content, n.emoji_kind) for n in leaves] == [
        ("emoji", ENGLAND, "alone")
    ], [(n.type, n.content) for n in leaves]
    print("  ✓  🏴 + tags is one emoji, one badge on its own line")


TESTS = [
    test_a_one_codepoint_emoji_is_an_emoji_to_both,
    test_a_text_default_symbol_is_an_emoji_only_with_its_selector,
    test_a_tag_flag_is_one_emoji,
]

if __name__ == "__main__":
    print("Emoji Routing Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}"[:300])
            failed += 1
    print("=" * 50)
    raise SystemExit(1 if failed else 0)
