# Financial report dashboard

<!-- Matches reference.webp: three cards on a grey page — a tall "Transaction
     History" on the left, "Total Spendings" and "Total Earnings" stacked on the
     right. That mosaic is what `Layout: Bento` is for.

     Palette read off the reference:
       #C9CFD8  page
       #FFFFFF  card
       #5B4FE9  the indigo bars and segments
       #0F1729  headings and values
       #6B7280  body / captions
       #E5484D  the down arrow   #16A34A  the up arrow -->

## Background styles and Spacing

### Root
Background color: #C9CFD8
Padding: 40
Spacing: 0
Horizontal align: Default
<!-- Mondrian mosaic of the top-level sections instead of a plain stack. -->
Layout: Bento

### Elements
Row spacing: 10
Col spacing: 8
Group spacing: 18
Image distance: 12
Padding: 0

### Heading 1
Padding: 0
Spacing: 24

### Heading 2
<!-- One card per `##` section — the three bento cells. -->
Background color: #FFFFFF
Corner radius: 28
Padding: 28
Spacing: 20
Row spacing: 24
Col spacing: 24
Merge rows: no

### Heading 3
<!-- The "Transaction Categories" panel nested inside the first card. -->
Background color: #FFFFFF
Corner radius: 18
Padding: 18
Spacing: 12
Stroke width: 1
Stroke color: #E6E8EE

## Text Styles

Heading2
- Font Name: inter 24pt
- Font size: 26
- Font weight: 700
- Font color: #0F1729

Heading3
- Font Name: inter 18pt
- Font size: 17
- Font weight: 600
- Font color: #0F1729

Text
- Font Name: inter 18pt
- Font size: 14
- Font weight: 400
- Font color: #6B7280

Text Overline
- Font Name: inter 18pt
- Font size: 13
- Font weight: 400
- Font color: #6B7280

Muted
- Font Name: inter 18pt
- Font size: 12
- Font weight: 400
- Font color: #9AA1AE

Lead
- Font Name: inter 18pt
- Font size: 15
- Font weight: 600
- Font color: #0F1729

<!-- Display doubles as the emphasised datapoint value: the big $15,830.32. -->
Display
- Font Name: inter 28pt
- Font size: 40
- Font weight: 700
- Font color: #0F1729

Labels
- Font Name: inter 18pt
- Font size: 11
- Font weight: 400
- Font color: #9AA1AE

Inline Code
- Font Name: inter 18pt
- Font size: 13
- Font weight: 500
- Font color: #0F1729

Links
- Font Name: inter 18pt
- Font size: 13
- Font weight: 500
- Font color: #6B7280

## Links

### Primary
<!-- The card's action icons: a bare glyph, no pill behind it. -->
Corner radius: 8
Fill color: #00000000
Padding: 4
Stroke width: 0

### Text
Fill color: #00000000
Padding: 4

### Inline
Text color: #5B4FE9
Underline: no

## Inline Code
<!-- `This Week ⏷` is the outlined dropdown; the stat chips use the same shape. -->
Corner radius: 10
Padding top: 7
Padding bottom: 7
Padding left: 12
Padding right: 12
Fill color: #FFFFFF
Stroke color: #E6E8EE
Stroke width: 1

## Fixed colors

### Emoji
- ⏷ #E5484D datapoints
- ⬆️ #16A34A datapoints
- ⬇️ #E5484D datapoints

## Horizontal Rule
Stroke color: #E6E8EE
Stroke width: 1

## Separators
Dash: hide
Bullet: show
Bar: hide

## Vertical Rule
Draw: no

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Primary
Icon size: 18
Padding: 8
Background colors:
- #F3F4F8
Corner radius: 10
Shape: square

### Text
Color: #6B7280

## Datapoints

### Dates
<!-- "February 04, 9:17 PM" is a timestamp, not a scheduled day, so the day-chip
     drawing turns a muted caption into a two-line block. Off. -->
Enabled: no

### Key Value Bars
Enabled: yes
Position: below
Thickness: 26
Corner radius: 0
Background color: #5B4FE9

### Key Value Bar Track
Background color: #EEEFF6

### Emphasis
Enabled: yes

## Charts
Enabled: yes
Bar thickness: 26
Bar spacing: 14
Corner radius: 8
Background color: #5B4FE9

### Chart Track
Background color: #F3F4F8

### Chart Labels
- Font size: 12
- Font color: #9AA1AE

### Chart Values
- Font size: 11
- Font weight: 600
- Font color: #0F1729

## Fonts
- assets/fonts/Inter_18pt-Regular.ttf
- assets/fonts/Inter_18pt-Medium.ttf
- assets/fonts/Inter_18pt-SemiBold.ttf
- assets/fonts/Inter_18pt-Bold.ttf
- assets/fonts/Inter_24pt-Regular.ttf
- assets/fonts/Inter_24pt-SemiBold.ttf
- assets/fonts/Inter_24pt-Bold.ttf
- assets/fonts/Inter_28pt-Bold.ttf
