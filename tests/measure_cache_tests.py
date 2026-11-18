"""
Unit tests for the measurement caches the layout generator's trial builds lean on.
Each pins the one fact that makes its cache exact:

  * `_split_emoji_runs`' ASCII fast path — no ASCII character is an emoji, so
    ASCII text is always one plain run;
  * `_measure_word`'s word-width memo — a cached width equals the uncached one,
    the bold/italic faces are keyed apart, and emptying at the cap stays correct;
  * `_explode_words`' memo — every caller gets a fresh list, so one that edits
    its words cannot change what the next caller reads;
  * `_wrap_lines`' interval cache — the greedy wrap gives the same
    lines for every width in ``[lo, hi)``, where ``lo`` is the widest total a
    line accepted and ``hi`` the narrowest total a break rejected. The cached
    lines equal a fresh wrap at every width of a 1 px sweep; the interval is
    tight (just below ``lo`` and at ``hi`` a fresh wrap differs); the key is
    the five faces the wrap reads, so two FontSets sharing them share an entry
    and one differing in a single face (or a different size) never does; and
    emptying at the cap stays correct.

Run with: uv run python tests/measure_cache_tests.py
"""

import dataclasses

import skia
from md2ui.pipeline import render_metrics as RM
from md2ui.pipeline.render_measure import _explode_words
from md2ui.pipeline.render_metrics import (
    _measure_word,
    _measure_word_uncached,
    _wrap_lines,
    _wrap_lines_uncached,
)
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.render_text import _is_emoji_char, _split_emoji_runs

SIZE = 16.0

_REG = skia.Typeface.MakeFromName("Helvetica", skia.FontStyle.Normal())
_BOLD = skia.Typeface.MakeFromName("Helvetica", skia.FontStyle.Bold())
_ITAL = skia.Typeface.MakeFromName("Helvetica", skia.FontStyle.Italic())
_BI = skia.Typeface.MakeFromName("Helvetica", skia.FontStyle.BoldItalic())


_EMOJI = skia.Typeface.MakeFromName("Apple Color Emoji", skia.FontStyle.Normal())


def _fonts() -> FontSet:
    return FontSet(_REG, _BOLD, _ITAL, _BI, None)


def _emoji_fonts() -> FontSet:
    return FontSet(_REG, _BOLD, _ITAL, _BI, None, emoji=_EMOJI)


# Texts for the wrap-cache tests: plain prose, bold/italic spans, glued
# punctuation, a unit wider than most widths, and an emoji.
_WRAP_TEXTS = (
    "The quick brown fox jumps over the lazy dog while the band plays on",
    "Revenue grew **sharply** in the *third* quarter, then ***eased*** off",
    "Open **Settings**. Then choose **Privacy**, and press `Save`.",
    "Supercalifragilisticexpialidocious-and-then-some-more-glued-text short",
    "Launch day 🚀 went well, and the team ⭐ celebrated with cake",
)


def test_no_ascii_character_is_an_emoji():
    assert not any(_is_emoji_char(chr(cp)) for cp in range(128)), (
        "the ASCII fast path in _split_emoji_runs assumes no ASCII emoji"
    )
    text = "Hello, world! 123 #*~"
    assert _split_emoji_runs(text) == [(text, False)]
    # Non-ASCII text still takes the full scan.
    assert _split_emoji_runs("a⭐b") == [("a", False), ("⭐", True), ("b", False)]
    print("  ✓  no ASCII character is an emoji; ASCII text is one plain run")


def test_cached_word_width_matches_uncached():
    fonts = _fonts()
    for word in ("Revenue", "$412M", "(49%)", "naïve", "go⭐"):
        for bold in (False, True):
            for italic in (False, True):
                want = _measure_word_uncached(word, bold, italic, fonts, SIZE)
                assert _measure_word(word, bold, italic, fonts, SIZE) == want
                # The second call is served from the memo, and must agree too.
                assert _measure_word(word, bold, italic, fonts, SIZE) == want
    print("  ✓  cached word widths equal the uncached measurement")


def test_bold_and_regular_are_keyed_apart():
    fonts = _fonts()
    regular = _measure_word("Wide", False, False, fonts, SIZE)
    bold = _measure_word("Wide", True, False, fonts, SIZE)
    assert bold != regular, "bold and regular must not share a cache entry"
    assert bold == _measure_word_uncached("Wide", True, False, fonts, SIZE)
    print("  ✓  bold and regular faces are cached separately")


def test_word_cache_empties_at_its_cap():
    fonts = _fonts()
    saved = RM._WORD_CACHE_MAX
    RM._WORD_CACHE_MAX = 3
    try:
        RM._WORD_WIDTHS.clear()
        RM._WORD_FACES.clear()
        words = [f"word{i}" for i in range(7)]
        for w in words:
            _measure_word(w, False, False, fonts, SIZE)
        assert len(RM._WORD_WIDTHS) <= 3, len(RM._WORD_WIDTHS)
        for w in words:
            assert _measure_word(w, False, False, fonts, SIZE) == (
                _measure_word_uncached(w, False, False, fonts, SIZE)
            )
    finally:
        RM._WORD_CACHE_MAX = saved
    print("  ✓  the word cache empties at its cap and stays correct")


def test_explode_words_returns_a_fresh_list():
    text = "**bold** plain `code`"
    first = _explode_words(text)
    expected = list(first)
    first.append(("intruder", False, False, 0, 0, None))
    first[0] = ("edited", False, False, 0, 0, None)
    second = _explode_words(text)
    assert second == expected, "an edit to one caller's words leaked into the memo"
    assert second is not first
    print("  ✓  _explode_words hands every caller its own list")


def test_cached_wrap_matches_uncached_sweep():
    RM._WRAP_CACHE.clear()
    RM._WRAP_FACES.clear()
    for fonts in (_fonts(), _emoji_fonts()):
        for text in _WRAP_TEXTS:
            words = _explode_words(text)
            for w in range(20, 901):
                want = _wrap_lines_uncached(words, float(w), fonts, SIZE)[0]
                got = _wrap_lines(words, float(w), fonts, SIZE)
                assert got == want, (text, w)
    print("  ✓  cached wraps equal a fresh wrap at every width from 20 to 900 px")


def test_wrap_interval_is_tight():
    fonts = _fonts()
    words = _explode_words(_WRAP_TEXTS[0])
    lines, lo, hi = _wrap_lines_uncached(words, 200.0, fonts, SIZE)
    assert len(lines) >= 3, "the probe needs at least two breaks"
    assert lo <= 200.0 < hi, (lo, hi)
    # Every width inside [lo, hi) gives the same lines ...
    assert _wrap_lines_uncached(words, lo, fonts, SIZE)[0] == lines
    assert _wrap_lines_uncached(words, (lo + hi) / 2, fonts, SIZE)[0] == lines
    # ... and just outside it they differ.
    assert _wrap_lines_uncached(words, lo - 0.5, fonts, SIZE)[0] != lines
    assert _wrap_lines_uncached(words, hi, fonts, SIZE)[0] != lines
    print("  ✓  the wrap interval is tight: lines change below lo and at hi")


def test_wrap_cache_keys_and_cap():
    RM._WRAP_CACHE.clear()
    RM._WRAP_FACES.clear()
    words = _explode_words(_WRAP_TEXTS[1])
    base = _fonts()
    first = _wrap_lines(words, 250.0, base, SIZE)
    # Fresh FontSets carrying the same five faces -- what render_style's
    # dataclasses.replace hands out -- share the entry, whatever else differs.
    for twin in (
        dataclasses.replace(base),
        dataclasses.replace(base, mono=_BOLD, code_block=_ITAL),
    ):
        assert _wrap_lines(words, 250.0, twin, SIZE) is first
    assert len(RM._WRAP_CACHE) == 1, len(RM._WRAP_CACHE)
    # One face changed, or the size, is a new key every time.
    variants = [
        (dataclasses.replace(base, typeface=_BOLD), SIZE),
        (dataclasses.replace(base, bold=_BI), SIZE),
        (dataclasses.replace(base, italic=_BI), SIZE),
        (dataclasses.replace(base, bold_italic=_REG), SIZE),
        (dataclasses.replace(base, emoji=_EMOJI), SIZE),
        (base, 24.0),
    ]
    for i, (fs, size) in enumerate(variants, start=2):
        want = _wrap_lines_uncached(words, 250.0, fs, size)[0]
        assert _wrap_lines(words, 250.0, fs, size) == want, i
        assert len(RM._WRAP_CACHE) == i, (i, len(RM._WRAP_CACHE))
    for face in (_REG, _BOLD, _ITAL, _BI, _EMOJI):
        assert RM._WRAP_FACES[id(face)] is face
    saved = RM._WRAP_CACHE_MAX
    RM._WRAP_CACHE_MAX = 3
    try:
        RM._WRAP_CACHE.clear()
        RM._WRAP_FACES.clear()
        for _ in range(2):
            for text in _WRAP_TEXTS:
                w = _explode_words(text)
                assert (
                    _wrap_lines(w, 180.0, base, SIZE)
                    == (_wrap_lines_uncached(w, 180.0, base, SIZE)[0])
                )
                assert len(RM._WRAP_CACHE) <= 3, len(RM._WRAP_CACHE)
    finally:
        RM._WRAP_CACHE_MAX = saved
    print("  ✓  the wrap cache keys on the five faces and the size; empties at its cap")


TESTS = [
    test_no_ascii_character_is_an_emoji,
    test_cached_word_width_matches_uncached,
    test_bold_and_regular_are_keyed_apart,
    test_word_cache_empties_at_its_cap,
    test_explode_words_returns_a_fresh_list,
    test_cached_wrap_matches_uncached_sweep,
    test_wrap_interval_is_tight,
    test_wrap_cache_keys_and_cap,
]

if __name__ == "__main__":
    print("Measure Cache Tests")
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
