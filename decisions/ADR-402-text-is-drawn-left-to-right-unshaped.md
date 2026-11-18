# ADR-402: Text is drawn left to right, unshaped; emoji sequences are the one exception

**Status:** active
**Domain:** renderer
**Read when:** a document in Arabic, Hebrew, Persian, an Indic script or any other script that
needs shaping or right-to-left order renders as separate letters; an emoji sequence (👨‍💻, a
flag, a skin tone, a keycap) draws as its parts; or you are about to replace `uharfbuzz` with
skia's own shaper.

## Decision

md2ui measures and draws text as runs of glyphs laid left to right. Each character is drawn
in the first face that has it — the theme's face, then a system face in the same weight
(`render_glyph_faces`) — but no run is shaped and no line is reordered. Complex-script shaping
(joining forms, ligatures, mark placement) and the bidirectional algorithm are **out of
scope**. Arabic text draws as its isolated letters in left-to-right order: legible glyphs, not
correct writing. That is the intended limit, not a defect.

**The one exception: emoji sequences.** An emoji run that holds a sequence codepoint (U+200D,
U+20E3, a regional indicator, a skin tone, a tag) is shaped with `uharfbuzz`
(`render_shaping.py`); every other run keeps the unshaped path, byte-identical. HarfBuzz only
picks the glyph ids; the advances come from the same skia font that measures every other run,
so the width measured is the width painted (ADR-400). The grouper keeps U+200D, so a sequence
peels as one badge.

## Reason

The documents md2ui exists for are LLM answers in Latin, CJK and symbol-heavy text; glyph
fallback makes those correct. Shaping a script properly is not a local change: it changes
glyph widths and order, so it must happen at the one point where text is measured and painted
(ADR-400) — every word cache, the line wrapper, inline spans, chips, code blocks and a run's
face selection would move to shaped runs, and right-to-left lines would need their own
alignment and wrapping.

Emoji sequences are different: a joined emoji, a flag or a keycap is one glyph a font makes
only through its ligature table, and without it the emoji comes apart. They are common in
agent answers, and shaping only those runs moves nothing else.

## Alternatives rejected

- **skia's own shaper** (`skia.TextBlob.MakeFromShapedText`). It misses ligatures the fonts
  hold: with OpenMoji, keycaps (`1️⃣`, `#️⃣`) come out as unjoined glyphs zero pixels wide, and
  `❤️‍🔥` as three glyphs. The cause inside skia was not found (the typeface source makes no
  difference and the shaper takes no options). `uharfbuzz` forms every ligature both bundled
  emoji fonts hold. A skia path that falls back to unjoined glyphs was rejected too.

## Constraint created

- Do not file shaping or right-to-left order as a finding; cite this record instead.
- A change that adds shaping for one place only (one drawer, one node type) breaks ADR-400
  and is not a partial fix. The emoji exception is not general shaping: shaping another
  script is a change at the one measure-and-paint point for all text, not an extension of the
  emoji run test.
- Do not drop `uharfbuzz` for skia's shaper without checking that skia forms the OpenMoji
  keycap and fire-heart ligatures.

## Reconsider when

- md2ui is meant to answer in a right-to-left or shaping script. The answer then is a shaping
  engine (HarfBuzz) at the single measure-and-paint point, for every text path at once, and
  emoji runs move onto it.
- A skia release forms the OpenMoji keycap and fire-heart ligatures.
