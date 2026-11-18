# Color rotation — icons cycle, cards do not

<!-- The isolation case (reference.png: four light grey cards, a coloured icon tile
     beside each title). `### Heading 3` states ONE background color, so every card
     paints the same light grey; the emoji badge states four, so only the icon tiles
     cycle. Nothing had to be turned off for that: a single-color list is simply not
     a cycle. Compare at --width 1391 --scale 2. -->

## Fonts
- assets/fonts/DMSans_18pt-Regular.ttf
- assets/fonts/DMSans_18pt-Medium.ttf

## Styling & Spacing

### Root
Max width: 1160
Background color: #FFFFFF
Padding: 23
Spacing: 24

### Elements
Row spacing: 16
Col spacing: 0
Group spacing: 20

### Heading 3
<!-- One color = every card the same. -->
Background color: #FAFAFA
Corner radius: 16
Padding: 16
Spacing: 24
Emoji aside: yes
Vertical align: center
<!-- Each card is its own section, so its tile is always the first badge in it
     (slot 0). Sync hands each card's sibling slot down to its tile instead. -->
Rotate colors: sync

## Text Styles

Text
- Font Name: DM Sans 18pt
- Font size: 16
- Font weight: 400
- Font color: #737373

Lead
- Font Name: DM Sans 18pt
- Font size: 20
- Font weight: 400
- Font color: #09090B

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Primary
Icon size: 20
Padding: 12
Corner radius: 8
Shape: square
Emoji weight: 400
Background color:
- #F5C242
- #F094E8
- #65DAB5
- #4F85F7
<!-- One icon color across all four: the glyph stays black while the tile
     behind it rotates. The two lists are independent even though they share a
     slot. -->
Icon color: #09090B
