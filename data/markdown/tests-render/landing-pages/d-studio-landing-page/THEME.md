# Color rotation — plan cards

<!-- Four `### ` sections under one `## Featured Plans` cycle through four card
     fills. Three are light and one is black, so the text that reads perfectly
     on the light three is invisible on the black one — and so are the button
     pill and the divider, which are both near-black too. ## Color Replacements
     at the bottom of this file fixes all three, without any of the four cards
     knowing which color it landed on. -->

## Background styles and Spacing

### Root
Background color: #FFFFFF
Padding: 56
Horizontal align: Center
Spacing: 40

### Elements
Row spacing: 6
Col spacing: 6
Group spacing: 16
Image distance: 16
Padding: 0

### Heading 1
Padding: 0
Spacing: 40

### Heading 2
Padding: 0
Spacing: 20

### Heading 3
Corner radius: 24
Padding: 24
Spacing: 12
<!-- Four colors = the cycle. Each `### ` section takes the next one, in
     document order, restarting inside every new `## ` section. -->
Background color:
- #6FDCA6
- #101010
- #C9A7F5
- #EDEF6B

## Text Styles

Text
- Font Name: work sans
- Font size: 14
- Font weight: 400
- Font color: #3F3F46

Heading1
- Font Name: work sans
- Font size: 46
- Font weight: 700
- Font color: #0A0A0A

Heading2
- Font Name: work sans
- Font size: 26
- Font weight: 700
- Font color: #0A0A0A

Heading3
- Font Name: work sans
- Font size: 20
- Font weight: 700
- Font color: #0A0A0A

Muted
- Font Name: work sans
- Font size: 11
- Font weight: 600
- Font color: #52525B

Lead
- Font Name: work sans
- Font size: 17
- Font weight: 400
- Font color: #3F3F46

Display
- Font Name: work sans
- Font size: 30
- Font weight: 700
- Font color: #0A0A0A

Links
- Font Name: work sans
- Font size: 14
- Font weight: 600
- Font color: #FFFFFF

Links Text
- Font Name: work sans
- Font size: 15
- Font weight: 600
- Font color: #0A0A0A

## Links

### Primary
Corner radius: 999
Fill color: #101010
Padding: 14
Stroke width: 0
Emoji shape: square

### Text
Fill color: #FFFFFF00
Padding: 4

## Horizontal Rule
Stroke color: #00000022
Stroke width: 1

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Link
Color: #FFFFFF

## Color Replacements
<!-- The black card is one of four the rotation deals out, so nothing above can
     say "this heading is white" — every swap is keyed on what is actually
     behind the paint. On the other three backgrounds no rule matches and
     nothing changes. -->

On background color: #101010
<!-- The words. -->
- Text color:   #0A0A0A,   Replacement: #FFFFFF
- Text color:   #3F3F46,   Replacement: #D4D4D8
- Text color:   #52525B,   Replacement: #A1A1AA
<!-- The arrow button is a #101010 pill, invisible on a #101010 card: flip it. -->
- Fill color:   #101010,   Replacement: #FFFFFF
<!-- Same for the ___ divider, a near-black hairline on near-black. -->
- Stroke color: #00000022, Replacement: #FFFFFF33

<!-- …and the pill that just flipped is now a background in its own right, so
     its arrow reads its color from here. Nothing had to say "buttons": an
     element that paints a fill hands that fill to its own label. -->
On background color: #FFFFFF
- Text color:   #FFFFFF,   Replacement: #101010

## Fonts
- assets/fonts/WorkSans-Regular.ttf
- assets/fonts/WorkSans-Medium.ttf
- assets/fonts/WorkSans-SemiBold.ttf
- assets/fonts/WorkSans-Bold.ttf
- assets/fonts/WorkSans-Italic.ttf
