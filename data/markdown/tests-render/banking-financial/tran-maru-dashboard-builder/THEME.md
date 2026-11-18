# Dashboard

<!-- A light-grey page, a title bar with a black "Create"
     pill, round icon buttons and the user's avatar; then two white cards.

     Palette read off the reference:
       #F1F1F1  page
       #FFFFFF  cards, the selected KPI tile
       #F7F7F7  the KPI panel behind the tiles
       #ECECEC  hairlines: panel, dropdowns, round buttons
       #111111  headings, figures, the Create pill
       #6B6B6B  captions
       #E5484D / #FDEEEE  the falling chip
       #16A34A / #ECF8F0  the rising chip -->

## Background styles and Spacing

### Root
Background color: #F1F1F1
Padding: 12
Spacing: 16

### Elements
Row spacing: 10
Col spacing: 12
Group spacing: 28
Image distance: 14
Padding: 0

### Heading 1
<!-- The title bar: no card. -->
Padding: 0
Spacing: 24

### Heading 2
<!-- Overview and Product view: the two white cards. -->
Background color: #FFFFFF
Corner radius: 36
Padding: 44
Spacing: 36
Row spacing: 36

### Heading 3
<!-- An untitled grouping inside a card; the KPI panel paints itself below. -->
Padding: 0
Spacing: 16

### Heading 4
<!-- The KPI tiles: transparent on the panel, unless selected. -->
Padding: 44
Padding left: 64
Corner radius: 30
Spacing: 18

### Fixed styles

#### Kpi panel
<!-- The grey panel the two KPI tiles sit on. -->
Mode: override
Background color: #F7F7F7
Stroke width: 1
Stroke color: #ECECEC
Corner radius: 36
Padding: 10

#### Product card
<!-- Product view: its $10.2m sits faded at the bottom, level with the bars' feet. -->
Mode: override
Vertical align: bottom
##### Display
- Font color: #D4D4D4

#### Selected tile
Mode: override
Background color: #FFFFFF
Outer shadow:
- Offset y: 6
- Color: #0000001A
- Radius: 24

## Text Styles

Heading1
- Font Name: inter 24pt
- Font size: 40
- Font weight: 600
- Font color: #111111

Heading2
- Font Name: inter 24pt
- Font size: 26
- Font weight: 500
- Font color: #111111

Text
- Font Name: inter 18pt
- Font size: 20
- Font weight: 500
- Font color: #222222

Muted
- Font Name: inter 18pt
- Font size: 18
- Font weight: 400
- Font color: #6B6B6B

Lead
- Font Name: inter 24pt
- Font size: 23
- Font weight: 400
- Font color: #111111

Display
- Font Name: inter 28pt
- Font size: 84
- Font weight: 500
- Font color: #111111

Inline Code
- Font Name: inter 18pt
- Font size: 19
- Font weight: 400
- Font color: #3A3A3A

Links
- Font Name: inter 18pt
- Font size: 17
- Font weight: 600
- Font color: #FFFFFF

Links Secondary
- Font Name: inter 18pt
- Font size: 17
- Font weight: 400
- Font color: #222222

Links Tertiary
- Font Name: inter 18pt
- Font size: 19
- Font weight: 400
- Font color: #3A3A3A

## Links

### Primary
<!-- "Create": the black pill. -->
Corner radius: 32
Fill color: #1B1B1B
Padding top: 20
Padding bottom: 20
Padding left: 34
Padding right: 34

### Secondary
<!-- The bell and chat buttons: white circles with a hairline. -->
Fill color: #FFFFFF
Stroke width: 1
Stroke color: #ECECEC
Emoji shape: circle
Padding top: 20
Padding bottom: 20

### Tertiary
<!-- "Last month" / "Last 7 days": the outlined dropdowns. -->
Corner radius: 34
Fill color: #FFFFFF
Stroke width: 2
Stroke color: #E6E6E6
Padding top: 20
Padding bottom: 20
Padding left: 28
Padding right: 24
Emoji gap: 56

## Inline Code
<!-- The change chips; their colours are pinned under ## Fixed colors. -->
Corner radius: 8
Padding top: 5
Padding bottom: 5
Padding left: 12
Padding right: 12
Stroke width: 2

## Fixed colors

### Badges
#### Contains
- ↓: Text color: #E5484D, Fill color: #FDEEEE, Stroke color: #F6CACA
- ↑: Text color: #16A34A, Fill color: #ECF8F0, Stroke color: #C5EBD2

## Separators
Dash: hide
Bullet: hide
Bar: hide

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Text
Color: #222222

## Images

### Placeholders

#### More
<!-- "View all": a white circle holding an arrow. -->
Fill color: #F6F6F6
Text color: #333333
Text size: 30%

## Datapoints

### Emphasis
Enabled: yes

## Charts
Enabled: yes
Bar width: fill
Bar thickness: 64
Bar spacing: 32
Corner radius: 12
Background color: #00000000
Background gradient:
- Colors:
  - #DCDCDC
  - #F4F4F400

### Chart Labels
- Font size: 1
- Font color: #FFFFFF00

### Chart Values
- Font size: 1
- Font color: #FFFFFF00

## Fonts
- assets/fonts/Inter_18pt-Regular.ttf
- assets/fonts/Inter_18pt-Medium.ttf
- assets/fonts/Inter_18pt-SemiBold.ttf
- assets/fonts/Inter_24pt-Regular.ttf
- assets/fonts/Inter_24pt-Medium.ttf
- assets/fonts/Inter_24pt-SemiBold.ttf
- assets/fonts/Inter_28pt-Medium.ttf
