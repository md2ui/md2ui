# DoorDash

<!--      Palette:
       #FFFFFF  page
       #EB1700  DoorDash red — hero band, CTA pills, text links
       #FFF0EC  the pale pink band
       #191919  headings, body, and the footer band
       #FFFFFF  text on red / on dark, via ## Color Replacements -->

<!-- Re-authored 2026-09-27. Each band names its own look with a heading id —
     `# {#split-pink-1}` selects `#### Split pink` — so no band depends on its position
     in a colour cycle any more. -->

## Styling & Spacing

### Root
Background color: #FFFFFF
Padding: 0
<!-- The bands run edge to edge in the reference; the default 1280 cap left white
     strips beside them in a wider window. -->
Max width: 1920
Spacing: 0
Horizontal align: Left
Spacer small: 8
Spacer medium: 16
Spacer large: 48

### Elements
Row spacing: 10
Col spacing: 10
Group spacing: 20
Image distance: 24
Padding: 0

### Heading 1
Padding: 0
Spacing: 0

### Heading 2
Padding: 0
Spacing: 20

### Heading 3
Padding: 16
Spacing: 16

### Heading 6
Padding: 0
Spacing: 14

### Heading 4
Padding: 12
Spacing: 16

### Image Cards
Corner radius: 0
Padding: 72
Horizontal align: Center
Spacer large: 64
Background gradient:
- Ratios:
  - 0.0
  - 1.0
- Colors:
  - #00000066
  - #00000066

### Fixed styles

#### Hero
Background color: #EB1700
Padding top: 24
Padding bottom: 72
Padding left: 40
Padding right: 40
Spacing: 32
Horizontal align: Center

#### Plain
<!-- The three intro cards ({#plain-1}): where the width gives two columns, the
     third sits centred under the pair rather than at the left. -->
Orphan row: Center
Background color: #FFFFFF
Padding top: 72
Padding bottom: 72
Padding left: 40
Padding right: 40
Spacing: 32
Horizontal align: Center

#### Split
Background color: #FFFFFF
Padding top: 72
Padding bottom: 72
Padding left: 40
Padding right: 40
Spacing: 32
Horizontal align: Left
Vertical align: Center

#### Split pink
Background color: #FFF0EC
Padding top: 72
Padding bottom: 72
Padding left: 40
Padding right: 40
Spacing: 32
Horizontal align: Left
Vertical align: Center

#### Gift
Background color: #FFF0EC
Padding top: 72
Padding bottom: 72
Padding left: 40
Padding right: 40
Spacing: 32
Horizontal align: Center

#### Footer
Background color: #191919
Padding top: 56
Padding bottom: 40
Padding left: 40
Padding right: 40
Spacing: 20
Horizontal align: Left

## Text Styles

Heading1
- Font Name: google sans
- Font size: 54
- Font weight: 700
- Font color: #191919

Heading2
- Font Name: google sans
- Font size: 44
- Font weight: 700
- Font color: #191919

Heading6
- Font Name: google sans
- Font size: 15
- Font weight: 700
- Font color: #191919

Heading4
- Font Name: google sans
- Font size: 28
- Font weight: 700
- Font color: #191919

Heading3
- Font Name: google sans
- Font size: 28
- Font weight: 700
- Font color: #191919

Text
- Font Name: google sans
- Font size: 16
- Font weight: 400
- Font color: #191919

Muted
- Font Name: google sans
- Font size: 13
- Font weight: 400
- Font color: #767676

Lead
- Font Name: google sans
- Font size: 17
- Font weight: 700
- Font color: #191919

Display
- Font Name: google sans
- Font size: 46
- Font weight: 700
- Font color: #191919

Labels
- Font Name: google sans
- Font size: 12
- Font weight: 400
- Font color: #767676

<!-- Four button faces, picked by the markdown wrapper (see content-themed.md). -->

<!-- Primary: the red CTA pill. -->
Links
- Font Name: google sans
- Font size: 15
- Font weight: 700
- Font color: #FFFFFF

<!-- Secondary: the white "Sign Up" pill on the red hero. -->
Links Secondary
- Font Name: google sans
- Font size: 15
- Font weight: 700
- Font color: #191919

<!-- Tertiary: plain text — city lists, categories, the whole footer. -->
Links Tertiary
- Font Name: google sans
- Font size: 14
- Font weight: 400
- Font color: #191919

<!-- Quaternary: the address field in the hero. -->
Links Quaternary
- Font Name: google sans
- Font size: 15
- Font weight: 400
- Font color: #494949

<!-- Text: the red "Start earning ➡️" text link under each feature card. -->
Links Text
- Font Name: google sans
- Font size: 15
- Font weight: 700
- Font color: #EB1700

## Links

### Primary
Corner radius: 999
Fill color: #EB1700
Padding top: 13
Padding bottom: 13
Padding left: 24
Padding right: 24
Stroke width: 0

### Secondary
Corner radius: 999
Fill color: #FFFFFF
Padding top: 13
Padding bottom: 13
Padding left: 24
Padding right: 24
Stroke width: 0

### Tertiary
Corner radius: 0
Fill color: #00000000
Padding top: 6
Padding bottom: 6
Padding left: 0
Padding right: 0
Stroke width: 0

### Quaternary
Corner radius: 999
Fill color: #FFFFFF
Padding top: 16
Padding bottom: 16
Padding left: 24
Padding right: 56
Stroke width: 0

### Text
Corner radius: 0
Fill color: #00000000
Padding top: 8
Padding bottom: 8
Padding left: 0
Padding right: 0
Stroke width: 0

### Inline
Text color: #EB1700
Underline: no

## Color Replacements
<!-- The point of this block: no style above knows which band it landed on,
     because the bands are dealt by a rotation. Keying on the color fixes every
     use of it at once.

     On the red hero and the dark footer the near-black text and the red pill
     are both invisible; flip them, and the flipped pill then reads its own
     label color from the white background it just became (the cascade). -->

On background color: #EB1700
- Replacement: #FFFFFF
- Text color: #191919, Replacement: #FFFFFF
- Text color: #767676, Replacement: #FFFFFFCC
- Fill color: #EB1700, Replacement: #FFFFFF

On background color: #191919
- Replacement: #FFFFFF
- Text color: #EB1700, Replacement: #BDBDBD
- Text color: #191919, Replacement: #FFFFFF
- Text color: #767676, Replacement: #A8A8A8
- Fill color: #EB1700, Replacement: #FFFFFF

<!-- A photo behind the text: same problem, one rule. -->
On background color: image
- Replacement: #FFFFFF
- Text color: #191919, Replacement: #FFFFFF

<!-- ...and a pill that just flipped to white needs a dark label again. -->
On background color: #FFFFFF
- Text color: #FFFFFF, Replacement: #191919

## Horizontal Rule
Stroke color: #E0E0E0
Stroke width: 1

## Separators
Dash: hide
Bullet: hide
Bar: hide

## Vertical Rule
Draw: no

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Text
Color: #EB1700

### Link
Color: #EB1700

## Fonts
- assets/fonts/GoogleSans-Regular.ttf
- assets/fonts/GoogleSans-Italic.ttf
- assets/fonts/GoogleSans-Medium.ttf
- assets/fonts/GoogleSans-MediumItalic.ttf
- assets/fonts/GoogleSans-SemiBold.ttf
- assets/fonts/GoogleSans-SemiBoldItalic.ttf
- assets/fonts/GoogleSans-Bold.ttf
- assets/fonts/GoogleSans-BoldItalic.ttf
