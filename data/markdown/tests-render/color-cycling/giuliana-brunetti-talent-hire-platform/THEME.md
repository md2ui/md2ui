# Color rotation — service cards with a tinted block

<!-- Reproduces the Talent Hire cards (compare at --width 662
     --scale 2). Four white `## ` cards on a
     blue-grey gradient; inside each, a `### ` block in one of four pastels, its
     chips in a deeper tint of the same hue. The cards hand their slot down
     (`Rotate colors: sync`), so each block and its chips follow their card. -->

## Fonts
- assets/fonts/DMSans_18pt-Regular.ttf
- assets/fonts/DMSans_18pt-Medium.ttf
- assets/fonts/DMSans_18pt-SemiBold.ttf

## Styling & Spacing

### Root
Background color: #D3D9E7
Background gradient:
- Type: Linear
- Ratios:
  - 0.0
  - 1.0
- Colors:
  - #E0E7F7
  - #C8CDD9
Padding: 40
Spacing: 0

### Elements
Row spacing: 6
Col spacing: 6
Group spacing: 14

### Heading 1
Padding: 0
Spacing: 22

### Heading 2
<!-- The white card. It lends its slot to everything inside it. -->
Background color: #FFFFFF
Corner radius: 12
Padding top: 6
Padding left: 6
Padding right: 6
Padding bottom: 16
Spacing: 16
Stroke width: 1
Stroke color: #FFFFFFB0
Rotate colors: sync
#### Lead
- Font size: 21
- Font weight: 600
- Font color: #0A0C0C

### Heading 3
<!-- The pastel block: one colour per card, in document order. -->
Corner radius: 10
Padding top: 26
Padding bottom: 30
Padding left: 18
Padding right: 18
Spacing: 0
Background colors:
- #E0F3FF
- #FFE1CB
- #E2DBF9
- #D5F6ED

## Text Styles

Text
- Font Name: DM Sans 18pt
- Font size: 17
- Font weight: 400
- Font color: #363938

Heading3
- Font Name: DM Sans 18pt
- Font size: 32
- Font weight: 500
- Font color: #0A0C0C

Lead
- Font Name: DM Sans 18pt
- Font size: 21
- Font weight: 600
- Font color: #0A0C0C

Links
- Font Name: DM Sans 18pt
- Font size: 19
- Font color: #0A0C0C

Inline Code
- Font Name: DM Sans 18pt
- Font size: 14
- Font weight: 400
- Font color: #363938

## Inline Code
<!-- One deeper tint per card; the sync hands each card's chips its slot. -->
Corner radius: 14
Padding top: 7
Padding bottom: 7
Padding left: 10
Padding right: 10
Fill color:
- #C0EAFE
- #FED2B6
- #D4C9FF
- #A5E8D6

## Links

### Primary
<!-- The arrow button at the end of each card. -->
Fill color: #F6F6F6
Corner radius: 6
Padding: 9
Stroke width: 0
Emoji shape: square

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Link
Color: #0A0C0C

## Separators
Dash: hide
Pipe: hide
