# ADR-407: Emoji draw as icons from a generated font

**Status:** active
**Domain:** renderer
**Read when:** you want emoji drawn as icons from an icon set, you are editing
`assets/icons/material-design-icons-md2ui.md`, or you are about to map emoji to icons in code.

## Decision

Agents keep writing emoji. A theme that wants icons names
`assets/icons/material-design-icons-md2ui.ttf` as its emoji `Font:`. That font is Material
Symbols Outlined with each icon remapped to the emoji codepoints, built by
`scripts/build_icon_font.py` from an editable table, `assets/icons/material-design-icons-md2ui.md`
(whose header states the mapping rules). The renderer has no emoji-to-icon code; the swap is
entirely in the font.

- **Every emoji draws as an icon.** An emoji with no close icon draws as `square`; no other
  font is mixed in as a fallback.
- **Icons sit in md2ui's emoji box,** so swapping fonts moves no layout.
- **The variable axes are kept,** so a theme sets icon weight, fill, grade and optical size
  with its `Emoji …` keys, and a table row can pin fill where solid against hollow is the
  meaning.

## Reason

- **The renderer already draws emoji from one font.** Measurement and painting share one run
  split (`render_glyph_faces`, ADR-400). A font that answers to the emoji codepoints reaches
  every place emoji are drawn (badges, buttons, chips, prose), with nothing looked up per
  character.
- **The document does not change.** It still holds `⭐`, so the grouper, `check`, MEANINGS.md
  and `## Fixed colors` pins behave as before (ADR-201).
- **Placement is solved once, at build time.** Material draws on a padded square that sits
  above the baseline; swapping in its glyphs at render time drew small, raised icons.
- **One artifact for every client.** md2ui-ts can load the same table as a subset web font.

## Alternatives rejected

- **Swapping codepoints at render time,** with an icon-map theme key and a lookup in the
  face split. It needed a placement rule at the shared measure/paint point, and every client
  would have to repeat the lookup.
- **Matching Google's icon metadata at runtime.** An undocumented endpoint, a network call per
  load, unreviewed first-match results, and renders that change when Google's data changes.
  Tag matching was used once, offline, to draft the table, which was then reviewed.
- **Replacing emoji with ligature names or HTML spans.** The grouper would no longer see the
  emoji, and names would measure as letters.
- **A second emoji font as fallback for unmapped emoji.** Two emoji styles on one page look
  wrong.

## Constraint created

- **Single colour.** Emoji whose meaning is their colour (🟢 🔴, coloured squares, coloured
  hearts) draw in the tint of their context. A theme that needs them apart pins them under
  `## Fixed colors > ### Emoji`.
- **Editing the table means running the script.** `tests/icon_font_tests.py` fails when the
  committed font no longer matches the table.
