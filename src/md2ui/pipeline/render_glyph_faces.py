"""Which font draws each run of a text: the theme's faces first, the system's after.

A theme names its faces, and a document may still hold characters none of them
has -- a ``⏷`` after a label, CJK in a name. Drawn with the theme face those come
out as missing-glyph boxes. Here each run of such characters is given a face that
has them instead: the run's own face if it can, the body face for a symbol the
emoji face lacks, and otherwise the system typeface the platform picks for that
character in the same weight and slant.

Measurement and painting both take their runs from ``font_runs`` and nowhere
else, so a fallback glyph is measured exactly as wide as it is drawn (ADR-400).
Text the theme faces cover comes back as the very runs and fonts it had before
this module existed, so it cannot move by a pixel.

A variation selector a face would draw as its missing-glyph box is left out of
the run here, for the same reason: what is measured is what is painted.

An emoji run is measured with ``render_shaping.run_advance`` and painted with
its ``draw_run``, so a sequence its font draws as one glyph is one glyph in both.
"""

import unicodedata

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_shaping import run_advance
from md2ui.pipeline.render_text import _split_emoji_runs
from md2ui.utils.font_loader import make_font

# The face each character resolves to, keyed by ``(primary face id, secondary face
# id, character)``. ``skia.Typeface`` is unhashable, hence the ids, and
# ``_GLYPH_FACES`` holds every keyed face so no other face can reuse an id (the
# rule ``render_metrics._WORD_FACES`` follows). Emptied when full.
_GLYPH_FACE: dict[tuple, object] = {}
_GLYPH_FACES: dict[int, object] = {}
_GLYPH_CACHE_MAX = 100_000
# Whether a variation selector adds width after the character before it, keyed
# ``(face id, previous character, selector)`` and held like ``_GLYPH_FACE``.
_SELECTOR_BOX: dict[tuple, bool] = {}

_FONT_MGR = skia.FontMgr.RefDefault()
# What the platform answers when no font has the character: its own box glyph.
_NO_FONT_FAMILIES = frozenset({".LastResort", "LastResort"})

# Characters that belong to the glyph before them -- combining marks, joiners,
# variation selectors, skin tones -- stay in that glyph's face. Moved to another
# face on their own they would detach from it.
_JOINING_CATEGORIES = frozenset({"Mn", "Me", "Cf", "Zl", "Zp"})


def _joins_previous(ch: str) -> bool:
    return (
        unicodedata.category(ch) in _JOINING_CATEGORIES
        or 0xFE00 <= ord(ch) <= 0xFE0F
        or 0x1F3FB <= ord(ch) <= 0x1F3FF
    )


def _has_glyph(face: "skia.Typeface", ch: str) -> bool:
    return face.unicharToGlyph(ord(ch)) != 0


def _system_face(ch: str, like: "skia.Typeface") -> "skia.Typeface | None":
    """The platform's face for ``ch``, in ``like``'s weight and slant when its
    family has them; ``None`` when no installed font holds the character."""
    style = like.fontStyle()
    # The platform's own family names, not ``font_loader.family_name``: they are
    # asked of the platform's font manager, which knows its faces by them.
    # An empty language list crashes skia-python's binding.
    found = _FONT_MGR.matchFamilyStyleCharacter(
        like.getFamilyName(), style, ["en"], ord(ch)
    )
    if found is None or found.getFamilyName() in _NO_FONT_FAMILIES:
        return None
    # The character match ignores weight and slant on macOS; ask the family.
    styled = _FONT_MGR.matchFamilyStyle(found.getFamilyName(), style)
    return styled if styled is not None and _has_glyph(styled, ch) else found


def missing_glyphs(text: str, faces: list["skia.Typeface"]) -> list[str]:
    """The characters of *text* that none of *faces* has and no installed font
    holds, in order of first appearance: each one paints as a missing-glyph box
    on this machine. ASCII, whitespace and joining marks are never reported."""
    missing = []
    for ch in dict.fromkeys(text):
        if (
            ch.isascii()
            or ch.isspace()
            or unicodedata.category(ch) in _JOINING_CATEGORIES
        ):
            continue
        if not any(_has_glyph(face, ch) for face in faces) and (
            _system_face(ch, faces[0]) is None
        ):
            missing.append(ch)
    return missing


def _glyph_face(
    ch: str, primary: "skia.Typeface", secondary: "skia.Typeface | None"
) -> "skia.Typeface":
    """The face that draws ``ch``: ``primary`` when it has it, then ``secondary``,
    then the system's match in ``primary``'s style -- and ``primary`` again when
    nothing has it, so a glyph no font holds draws as it always did."""
    key = (id(primary), id(secondary), ch)
    face = _GLYPH_FACE.get(key)
    if face is not None:
        return face
    if _has_glyph(primary, ch):
        face = primary
    elif secondary is not None and _has_glyph(secondary, ch):
        face = secondary
    else:
        face = _system_face(ch, secondary if secondary is not None else primary)
        if face is None:
            face = primary
    if len(_GLYPH_FACE) >= _GLYPH_CACHE_MAX:
        _GLYPH_FACE.clear()
        _SELECTOR_BOX.clear()
        _GLYPH_FACES.clear()
    _GLYPH_FACE[key] = face
    for held in (primary, secondary, face):
        _GLYPH_FACES[id(held)] = held
    return face


def _selector_draws_box(face: "skia.Typeface", prev: str, selector: str) -> bool:
    """Whether ``selector`` after ``prev`` would add width in ``face``.

    A selector has no width of its own. A face with a variation-sequence table
    (Noto Emoji) resolves the pair as one glyph and leaves the selector's slot
    as glyph 0, the missing-glyph box, which is measured and drawn; a face
    without one (OpenMoji) gives the selector its own empty glyph: ``❤️`` is glyphs
    ``[170, 0]`` in Noto Emoji and ``[3943, 25]`` in OpenMoji. Asked as two
    advances, the one question every measuring path
    already asks of a font.
    """
    key = (id(face), prev, selector)
    hit = _SELECTOR_BOX.get(key)
    if hit is None:
        font = make_font(face, 12.0)
        hit = font.measureText(prev + selector) != font.measureText(prev)
        if len(_SELECTOR_BOX) >= _GLYPH_CACHE_MAX:
            _GLYPH_FACE.clear()
            _SELECTOR_BOX.clear()
            _GLYPH_FACES.clear()
        _SELECTOR_BOX[key] = hit
        _GLYPH_FACES[id(face)] = face
    return hit


def _split_by_face(
    run: str, primary: "skia.Typeface", secondary: "skia.Typeface | None"
) -> list[tuple[str, "skia.Typeface"]]:
    """``run`` cut where the face that draws it changes, without the variation
    selectors that face would draw as a box (the glyph keeps its look: the
    selector only picks a presentation, which a one-colour face has one of)."""
    pieces: list[tuple[str, skia.Typeface]] = []
    chars: list[str] = []
    current = None
    for i, ch in enumerate(run):
        if current is not None and _joins_previous(ch):
            if not (
                0xFE00 <= ord(ch) <= 0xFE0F
                and _selector_draws_box(current, run[i - 1], ch)
            ):
                chars.append(ch)
            continue
        face = _glyph_face(ch, primary, secondary)
        if face is not current:
            if current is not None:
                pieces.append(("".join(chars), current))
            chars, current = [], face
        chars.append(ch)
    if current is not None:
        pieces.append(("".join(chars), current))
    return pieces


def font_runs(
    text: str,
    text_font: "skia.Font",
    emoji_tf: "skia.Typeface | None",
    size: float,
) -> list[tuple[str, "skia.Font", bool]]:
    """``[(run, font, is_emoji), ...]``: ``text`` in drawing order, each run with
    the font that measures and paints it.

    ``is_emoji`` says which slot the run came from -- the emoji face's, or the
    text's -- and so which paint it takes; a symbol drawn in a fallback face keeps
    its slot. Without an emoji face every run is text, as before.
    """
    if text.isascii():
        return [(text, text_font, False)]
    text_tf = text_font.getTypeface()
    slots = _split_emoji_runs(text) if emoji_tf is not None else [(text, False)]
    runs: list[tuple[str, skia.Font, bool]] = []
    for run, is_emoji in slots:
        if is_emoji:
            primary, secondary, slot_font = emoji_tf, text_tf, None
        else:
            primary, secondary, slot_font = text_tf, None, text_font
        for piece, face in _split_by_face(run, primary, secondary):
            if face is primary and slot_font is not None:
                font = slot_font
            elif face is text_tf and not is_emoji:
                font = text_font
            else:
                font = make_font(face, size if is_emoji else text_font.getSize())
            runs.append((piece, font, is_emoji))
    return runs


def runs_advance(
    text: str,
    text_font: "skia.Font",
    emoji_tf: "skia.Typeface | None",
    size: float,
) -> float:
    """Width of ``text`` drawn run by run in ``font_runs``' fonts."""
    if text.isascii():
        return text_font.measureText(text)
    return sum(
        run_advance(run, font, is_emoji)
        for run, font, is_emoji in font_runs(text, text_font, emoji_tf, size)
    )


def glyph_runs(
    text: str,
    emoji_tf: "skia.Typeface | None",
    fallback_tf: "skia.Typeface",
    size: float,
) -> list[tuple[str, "skia.Font"]]:
    """``[(run, font), ...]`` for a glyph drawn on its own at ``size`` -- an
    emoji badge, a peeled emoji, a line of code: the emoji face when there is
    one, then ``fallback_tf``, then the system's face for what neither has.

    A glyph the first face has comes back as the one font it always drew in.
    """
    if emoji_tf is None and text.isascii():
        return [(text, make_font(fallback_tf, size))]
    primary = emoji_tf if emoji_tf is not None else fallback_tf
    secondary = fallback_tf if emoji_tf is not None else None
    return [
        (run, make_font(face, size))
        for run, face in _split_by_face(text, primary, secondary)
    ]


def glyph_advance(
    text: str,
    emoji_tf: "skia.Typeface | None",
    fallback_tf: "skia.Typeface",
    size: float,
) -> float:
    """Width of ``text`` drawn in ``glyph_runs``' fonts."""
    return sum(
        run_advance(run, font, emoji_tf is not None)
        for run, font in glyph_runs(text, emoji_tf, fallback_tf, size)
    )
