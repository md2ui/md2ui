"""Emoji sequences measured and drawn as the one glyph their font makes of them.

A joined emoji (👨‍💻), a flag (🇺🇸), a skin tone (👍🏽) and a keycap (1️⃣) are
several characters a font draws as one glyph, but only through its ligature
table, which a character-by-character glyph lookup never reads: drawn that way
they come apart into their pieces. HarfBuzz applies the table here.

Only an emoji run is shaped, and only one that holds such a sequence; every
other run is measured and drawn from its characters exactly as before, so it
cannot move by a pixel. The shaper only chooses the glyphs. Their advances come
from the same skia font that measures every other run, so the width measured is
the width drawn (ADR-400).
"""

import re
import struct
from itertools import accumulate

import skia  # type: ignore[import-untyped]

# The compiled module itself: the package re-exports it with ``*``, which the
# type checker cannot see through.
import uharfbuzz._harfbuzz as hb

# What only a ligature joins: the zero-width joiner, the keycap mark, regional
# indicators (a flag is two), skin tones and tag characters (a region's flag).
_SEQUENCE = re.compile(
    "[‍⃣\U0001f1e6-\U0001f1ff\U0001f3fb-\U0001f3ff\U000e0020-\U000e007f]"
)

# The tables that decide which glyph a run becomes: the character map, the
# substitutions (OpenType's, or Apple's for a system face), and what they
# need to be read. A colour face's bitmaps stay out: they are what make it big.
_TABLES = (b"GDEF", b"GSUB", b"avar", b"cmap", b"fvar", b"head", b"maxp", b"morx")

# HarfBuzz fonts and shaped glyphs, keyed by the face's id. Each entry holds
# its face, so no other face can reuse that id while the key lives (the rule
# ``render_glyph_faces._GLYPH_FACES`` follows). Glyphs do not depend on size,
# so one shaping serves every width a layout tries. Emptied together when full.
_HB_FONTS: dict[int, tuple["skia.Typeface", "hb.Font"]] = {}
_SHAPED: dict[tuple[int, str], list[int]] = {}
_SHAPED_MAX = 20_000


def _sfnt(face: "skia.Typeface") -> bytes:
    """The shaping tables of ``face`` as one font file HarfBuzz can read. A face
    gives its tables, not its file -- a weighted face is a clone with none."""
    tables = [
        (tag, data)
        for tag in _TABLES
        if (data := face.getTableData(int.from_bytes(tag, "big")))
    ]
    offset = 12 + 16 * len(tables)
    records, bodies = [], []
    for tag, data in tables:
        records.append(struct.pack(">4sIII", tag, 0, offset, len(data)))
        bodies.append(data + b"\0" * (-len(data) % 4))
        offset += len(bodies[-1])
    header = struct.pack(">IHHHH", 0x00010000, len(tables), 0, 0, 0)
    return header + b"".join(records) + b"".join(bodies)


def _hb_font(face: "skia.Typeface") -> "hb.Font":
    held = _HB_FONTS.get(id(face))
    if held is not None:
        return held[1]
    font = hb.Font(hb.Face(_sfnt(face)))
    # A weighted face shapes at its own weight, should its font vary by one.
    try:
        coords = face.getVariationDesignPosition()
    except RuntimeError:  # a static face has no position to get
        coords = []
    if coords:
        font.set_variations(
            {struct.pack(">I", c.axis).decode("latin-1"): c.value for c in coords}
        )
    _HB_FONTS[id(face)] = (face, font)
    return font


def _shaped(run: str, face: "skia.Typeface") -> list[int] | None:
    """The glyphs ``face`` draws ``run`` as, or ``None`` when the run holds no
    sequence and its characters are its glyphs. Invisible characters a
    ligature did not take -- a joiner, a selector -- are left out."""
    if not _SEQUENCE.search(run):
        return None
    key = (id(face), run)
    glyphs = _SHAPED.get(key)
    if glyphs is not None:
        return glyphs
    if len(_SHAPED) >= _SHAPED_MAX:
        _SHAPED.clear()
        _HB_FONTS.clear()
    buf = hb.Buffer()
    buf.add_str(run)
    buf.guess_segment_properties()
    buf.flags = hb.BufferFlags.REMOVE_DEFAULT_IGNORABLES
    hb.shape(_hb_font(face), buf)
    glyphs = [info.codepoint for info in buf.glyph_infos]
    _SHAPED[key] = glyphs
    return glyphs


def run_advance(run: str, font: "skia.Font", shape: bool) -> float:
    """Width of ``run`` in ``font``; ``shape`` says it is an emoji run."""
    glyphs = _shaped(run, font.getTypeface()) if shape else None
    if glyphs is None:
        return font.measureText(run)
    return sum(font.getWidths(glyphs))


def draw_run(
    canvas: "skia.Canvas",
    run: str,
    x: float,
    y: float,
    font: "skia.Font",
    paint: "skia.Paint",
    shape: bool,
) -> float:
    """Draw ``run`` at ``(x, y)`` as ``run_advance`` measured it; return that."""
    glyphs = _shaped(run, font.getTypeface()) if shape else None
    if glyphs is None:
        canvas.drawString(run, x, y, font, paint)
        return font.measureText(run)
    widths = font.getWidths(glyphs)
    builder = skia.TextBlobBuilder()
    builder.allocRunPosH(font, glyphs, [0.0, *accumulate(widths)][:-1], 0)
    canvas.drawTextBlob(builder.make(), x, y, paint)
    return sum(widths)
