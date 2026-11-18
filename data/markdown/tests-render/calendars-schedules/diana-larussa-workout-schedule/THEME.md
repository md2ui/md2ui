# Workout schedule — empty state

<!-- Reproduces the Workout Schedule empty state (compare at
     --width 384 --scale 2). One white card with a big soft shadow on a light grey
     page: a serif title beside a pink Add button, a week strip drawn as a token
     grid (weekday header, a row of day chips, a row of pink dots; the selected day
     is the Secondary chip), a pink icon tile, a serif empty-state line, and a
     weekly-goal bar. -->

## Fonts
- assets/fonts/EBGaramond-Regular.ttf
- assets/fonts/EBGaramond-Medium.ttf
- assets/fonts/Inter_18pt-Regular.ttf
- assets/fonts/Inter_18pt-Medium.ttf
- assets/fonts/Inter_18pt-SemiBold.ttf

## Styling & Spacing

### Root
Background color: #F6F6F6
Padding: 56
Padding top: 34
### Elements
Row spacing: 8
Col spacing: 6
Group spacing: 16

### Heading 1
<!-- The card. -->
Background color: #FFFFFF
Corner radius: 32
Padding top: 34
Padding bottom: 34
Padding left: 34
Padding right: 34
Spacing: 18
Outer shadow:
- Offset y: 24
- Blur: 48
- Color: #0000001A

### Heading 3 
Corner radius: 16
Padding: 10

### Fixed styles

#### Today
Mode: override
Background color: #FCEFFA

## Text Styles

Text
- Font Name: Inter 18pt
- Font size: 12
- Font weight: 400
- Font color: #5E5D6B

Heading1
- Font Name: EB Garamond
- Font size: 30
- Font weight: 400
- Font color: #01000E

Display
- Font Name: EB Garamond
- Font size: 30
- Font weight: 400
- Font color: #01000E

Links
- Font Name: Inter 18pt
- Font size: 13
- Font weight: 500
- Font color: #FFFFFF

Inline Code
- Font Name: Inter 18pt
- Font size: 12
- Font weight: 500
- Font color: #1B1A24

Inline Code Quinary
- Font size: 16
- Font color: #DD70D9

## Links

### Primary
Fill color: #E470D4
Corner radius: 20
Padding top: 12
Padding bottom: 12
Padding left: 16
Padding right: 16
Stroke width: 0

## Inline Code
<!-- A day number: no surface of its own. -->
Fill color: #00000000
Corner radius: 10
Padding top: 3
Padding bottom: 3
Padding left: 7
Padding right: 7

### Secondary
<!-- The selected day. -->
Fill color: #FCEFFA

### Quinary
<!-- The dot under a day. -->
Fill color: #00000000
Padding top: 0
Padding bottom: 0

## Tables

### Table
Merge rows: yes
Background color: #00000000
Stacking cards: no

### Header
Background color: #00000000
Padding: 2
- Font name: Inter 18pt
- Font size: 10
- Font weight: 500
- Font color: #6A6A74

### Cells
Background color: #00000000
Padding: 0

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Primary
<!-- The empty state's icon tile. -->
Icon size: 32
Padding: 18
Corner radius: 18
Shape: square
Background color: #DD6ED6
Icon color: #1B284C
Emoji fill: 1

## Separators
Dash: hide
Pipe: hide

## Drawing elements

### Key Value Bars
Enabled: yes
Position: below
Show key: no
Show value: no
Thickness: 8
Corner radius: 4
Background color: #E070D3

### Key Value Bar Track
Background color: #FCF1FB
Corner radius: 4
