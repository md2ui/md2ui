# Widget board

<!-- Reproduction target: a mosaic of OS-style widget cards on a
     light grey field, alternating white and near-black, orange + lime accents.

     Written fresh (not as an extension of the repo THEME.md) because the widget
     look shares nothing with the reference theme. -->

## Background styles and Spacing

### Root
Background color: #EBEBEB
Padding: 40
Spacing: 16
Layout: Bento
Vertical align: Center
Stack sections: yes
<!-- The reference is a five-column board. Bento aims at ~260px per column, so the
     column count comes from the width available: 1280 gave four, 1600 gives five. -->
Max width: 1600

### Elements
Row spacing: 8
Col spacing: 6
Group spacing: 14
Image distance: 12
Padding: 0

### Heading 2
Corner radius: 28
Padding: 20
Spacing: 16
<!-- The cards ARE the sections, so their own card backgrounds would double-paint. -->
<!-- A section cannot name its own background, so the light/dark sequence of the
     reference has to be spelled out positionally, one entry per `## ` in document
     order. Inserting a card re-deals everything after it. -->
Background color:
- #FFFFFF
- #1C1C1C
- #FFFFFF
- #1C1C1C
- #FFFFFF
- #1C1C1C
- #1C1C1C
- #FFFFFF
- #FFFFFF
- #FFFFFF
- #FFFFFF
- #1C1C1C
- #FFFFFF
- #1C1C1C
- #FFFFFF
<!-- slot 16 = the calendar card, appended last. Appending is safe; INSERTING it
     anywhere else would have re-dealt every card after it. -->
- #1C1C1C
<!-- slot 17 = the second calendar. -->
- #1C1C1C

## Text Styles

Text
- Font Name: Inter 18pt
- Font size: 15
- Font weight: 400
- Font color: #1C1C1C

Heading2
- Font Name: Inter 18pt
- Font size: 1
- Font weight: 400
- Font color: #EBEBEB00

Text Overline
- Font Name: Inter 18pt
- Font size: 13
- Font weight: 400
- Font color: #8A8A8E

Muted
- Font Name: Inter 18pt
- Font size: 13
- Font weight: 400
- Font color: #8A8A8E

Lead
- Font Name: Inter 18pt
- Font size: 20
- Font weight: 600
- Font color: #1C1C1C

Display
- Font Name: Inter 18pt
- Font size: 36
- Font weight: 700
- Font color: #1C1C1C

<!-- Inferred stat tiles (`Duration: 08:21`) now have their OWN typography,
     independent of the `Display` tier used by the authored `___53min___` heroes.
     This is what lets one card carry a 36px hero number and a 17px stat footer;
     before, both drew in `Display` and `### Emphasis` had to be switched off. -->
Key
- Font Name: Inter 18pt
- Font size: 12
- Font weight: 400
- Font color: #8A8A8E

Value
- Font Name: Inter 18pt
- Font size: 17
- Font weight: 600
- Font color: #1C1C1C

Labels
- Font Name: Inter 18pt
- Font size: 12
- Font weight: 400
- Font color: #8A8A8E

Links
- Font Name: Inter 18pt
- Font size: 15
- Font weight: 500
- Font color: #1C1C1C

Inline Code
- Font Name: Inter 18pt
- Font size: 13
- Font weight: 500
- Font color: #1C1C1C

Inline Code Secondary
- Font Name: Inter 18pt
- Font size: 13
- Font weight: 500
- Font color: #1C1C1C

Inline Code Tertiary
- Font Name: Inter 18pt
- Font size: 13
- Font weight: 500
- Font color: #FFFFFF

Inline Code Quaternary
- Font Name: Inter 18pt
- Font size: 13
- Font weight: 500
- Font color: #CFF33B

## Links

### Primary
<!-- the light circular ↗ / ⚙ corner button -->
Corner radius: 22
Fill color: #F2F2F2
Padding: 10
Stroke width: 0
Emoji shape: circle

### Secondary
<!-- the orange transport button (pause / stop) -->
Fill color: #FF4A1C
Emoji shape: circle

### Tertiary
<!-- flat, no pill — the oversized bare arrow on the gate card -->
Fill color: #00000000
Padding: 0

## Inline Code
Corner radius: 20
Padding top: 6
Padding bottom: 6
Padding left: 12
Padding right: 12
Fill color: #F2F2F2
<!-- A `Stroke color` pinned in `## Fixed colors > ### Badges` is inert unless the
     chip style itself carries a width. Transparent here, so only pinned chips
     (the outlined calendar days) actually show a ring. -->
Stroke width: 1
Stroke color: #00000000

<!-- Day STATE authored per cell, as a chip variant, instead of pinned by label.
     The September calendar uses these; August still uses the label pins under
     `## Fixed colors`. One render, both approaches, so the difference is visible. -->
<!-- Day STATE, authored per cell. Four variants is the whole budget:
     `x` default | *x* active | **x** today | ***x*** selected.
     A fifth state — greying the days that belong to the neighbouring month —
     has nowhere to go. -->
### Secondary
Fill color: #CFF33B
### Tertiary
Fill color: #FF4A1C
### Quaternary
Fill color: #00000000
Stroke color: #CFF33B
Stroke width: 1

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Primary
Shape: circle
Size: 22
Padding: 9
Background color: #00000000
Icon color: #1C1C1C

### Text
Color: #1C1C1C

### Link
Color: #FFFFFF

## Tables

<!-- The calendar card. A month grid is a table of one-glyph inline-code chips;
     the per-day states (active / today / selected) are `### Badges` > `#### Exact`
     entries keyed on the day number below. -->

### Table
Merge rows: no
Row spacing: 4
Col spacing: 4
Stacking cards: no

### Header
Background color: #00000000
Padding: 0
- Font Name: Inter 18pt
- Font size: 11
- Font weight: 500
- Font color: #8A8A8E

### Cells
Background color: #00000000
Padding: 0
- Font Name: Inter 18pt
- Font size: 13
- Font color: #FFFFFF

## Fixed colors

### Emoji
- ⚡ #FF4A1C
- 🍃 #22C55E
- ✈️ #0A84FF
- 🎧 #22C55E
- 📶 #FFFFFF
- 📹 #FFFFFF
- 📅 #FFFFFF

### Emoji background
- 📶 #0A84FF
- 📹 #0A84FF

### Badges
#### Exact
- ~4H: Text color: #FFFFFF, Fill color: #22C55E
- -4H: Text color: #FFFFFF, Fill color: #FF4A1C
- 2 min: Text color: #FFFFFF, Fill color: #1C1C1C
- 10m left: Text color: #FF4A1C, Fill color: #00000000
<!-- The day pins that used to live here are GONE. `#### Exact` keys on the chip
     LABEL, so with two calendars every pin fires in both — August's "5,6,7,8 active"
     also lit September's 5,6,7,8. Day state is now authored per cell as a chip
     VARIANT (see `## Inline Code` below), which is local to the cell that wrote it. -->

## Color Replacements

<!-- Everything that makes the near-black cards legible. Nothing in Text Styles,
     Links or Inline Code knows which slot a card was dealt. -->

On background color: #1C1C1C
- Replacement: #FFFFFF
- Text color: #1C1C1C, Replacement: #FFFFFF
- Text color: #8A8A8E, Replacement: #8A8A8E
- Fill color: #1C1C1C, Replacement: #FFFFFF
- Fill color: #E5E5E5, Replacement: #3A3A3C
<!-- `Background color:` is NOT a replacement channel — tried, no effect. A RING's
     arc does follow the Fill rule above (the 300m card draws white on black), but a
     Key Value Bar's fill and track do not, so those two colours have to read on a
     white AND a near-black card by themselves. See FINDINGS.md. -->
- Fill color: #F2F2F2, Replacement: #2C2C2E
- Stroke color: #E5E5E5, Replacement: #3A3A3C

On background color: #FFFFFF
- Text color: #FFFFFF, Replacement: #1C1C1C

<!-- Pale circular link buttons own their icon context. -->
On background color: #F2F2F2
- Text color: #FFFFFF, Replacement: #1C1C1C

<!-- #F2F2F2 pills on a dark card resolve to this surface. Once painted, the
     pill owns its label context; the enclosing card no longer answers for it. -->
On background color: #2C2C2E
- Text color: #1C1C1C, Replacement: #FFFFFF

## Horizontal Rule
Stroke color: #E5E5E5
Stroke width: 1

## Separators
Dash: hide
Bullet: show
Bar: hide

## Content arrangement

### Bento
Heading level: 2

## Datapoints

<!-- Back ON: the stat footers draw in `Text Styles > Key` / `Value` now, so they
     no longer inherit the hero size. -->
### Emphasis
Enabled: yes

<!-- `Aug 12` in "GMT +9 - Aug 12" is detected as a date and drawn as a two-tier
     day chip. The reference wants plain text and there is no per-instance
     opt-out, so the family goes off document-wide. -->
### Dates
Enabled: no

### Ring
Thickness: 4
Diameter: 54
Spacing: 0
Background color: #1C1C1C
- Font Name: Inter 18pt
- Font size: 15
- Font weight: 600
- Font color: #1C1C1C

### Ring Unit
- Font Name: Inter 18pt
- Font size: 13
- Font weight: 400
- Font color: #1C1C1C

### Ring Track
Background color: #E5E5E5

### Unit Ratios
Enabled: yes
Style: ring
Show total: no
Show key: yes

<!-- The thin scrubber/slider bars (Spotify, the two timezone cards).
     `Corner radius: 0` now means SQUARE, consistently with every other fill —
     half the thickness is the pill. -->
### Key Value Bars
Enabled: yes
Thickness: 8
Corner radius: 4
Position: below
<!-- Orange, not the reference's per-card dark/white: this pair is unreachable by
     `## Color Replacements`, so one colour has to survive both card backgrounds. -->
Background color: #FF4A1C

### Key Value Bar Track
Background color: #9A9A9A55
Corner radius: 4

<!-- The charging card's fat lime bar. Choosing a different datapoint FAMILY is
     how a document gets a second bar style: `68/100` is a bare ratio, so it draws
     from Ratio Bars, while `Elapsed: 45%` is a K-V pair and draws from the block
     above. There is no per-instance bar styling. -->
### Ratio Bars
Enabled: yes
Thickness: 34
Corner radius: 10
Text side: left
Background color: #CFF33B

### Ratio Bar Track
Background color: #2C2C2E
Corner radius: 10
Padding: 4

<!-- The WiFi card's toggle — a real control now, from a `- [x]` list item. -->
### Task controls
Enabled: yes
Type: switch
Size: 30
Padding: 3
Space: 10

### Checked outer
Background color: #22C55E
### Checked inner
Background color: #FFFFFF
### Unchecked outer
Background color: #E5E5E5
### Unchecked inner
Background color: #FFFFFF

## Charts
Enabled: yes
Bar width: fill
Bar thickness: 22
Bar spacing: 10
Corner radius: 8
Background color: #FF4A1C

### Chart Track
Background color: #00000000

### Chart <!-- Inferred stat tiles (`Duration: 08:21`) now have their OWN typography,
     independent of the `Display` tier used by the authored `___53min___` heroes.
     This is what lets one card carry a 36px hero number and a 17px stat footer;
     before, both drew in `Display` and `### Emphasis` had to be switched off. -->
Key
- Font Name: Inter 18pt
- Font size: 12
- Font weight: 400
- Font color: #8A8A8E

Value
- Font Name: Inter 18pt
- Font size: 17
- Font weight: 600
- Font color: #1C1C1C

Labels
- Font Name: Inter 18pt
- Font size: 11
- Font color: #8A8A8E

## Fonts
- assets/fonts/Inter_18pt-Regular.ttf
- assets/fonts/Inter_18pt-Medium.ttf
- assets/fonts/Inter_18pt-SemiBold.ttf
- assets/fonts/Inter_18pt-Bold.ttf
- assets/fonts/Inter_18pt-Italic.ttf
