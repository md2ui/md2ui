# Color rotation — two independent cycles in one document

<!-- The reset case, and the reason a cycle is scoped to its enclosing section.

     `## Upcoming meetups` holds three `### ` cards that cycle pink → orange →
     green. `## Interested meetups` then holds three list items whose emoji
     badges start again at BLUE, not at the fourth entry of some document-wide
     counter — a new section opens a new cycle.

     Known mismatch with the reference, unrelated to rotation: the icons in the
     upper cards are the same "alone" emoji role as the ones in the list, so
     they take the same badge block. The reference draws them as bare white
     glyphs instead. They each sit alone in their own `### ` section, so they
     all correctly land on slot 0. -->

## Background styles and Spacing

### Root
Background color: #FFFFFF
Padding: 24
Spacing: 24

### Elements
Row spacing: 4
Col spacing: 8
Group spacing: 14
Image distance: 12
Padding: 0

### Heading 1
Padding: 0
Spacing: 20

### Heading 2
Padding: 0
Spacing: 14
<!-- Nothing is switched off here: the emoji cycle below and the card cycle
     coexist because each counts its own channel. -->

### Heading 3
Corner radius: 24
Padding: 18
Spacing: 6
Background color:
- #EC5FBB
- #F0993D
- #47B972

## Text Styles

Text
- Font Name: work sans
- Font size: 14
- Font weight: 400
- Font color: #6B7280

Heading1
- Font Name: work sans
- Font size: 34
- Font weight: 700
- Font color: #1E1B4B

Heading2
- Font Name: work sans
- Font size: 20
- Font weight: 700
- Font color: #1E1B4B

Heading3
- Font Name: work sans
- Font size: 17
- Font weight: 700
- Font color: #FFFFFF

Links
- Font Name: work sans
- Font size: 15
- Font weight: 600
- Font color: #FFFFFF

## Links

### Primary
Corner radius: 12
Fill color: #FFFFFF33
Padding: 10
Stroke width: 0
Emoji shape: square

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Primary
Icon size: 20
Padding: 12
Shape: circle
Background color:
- #DCEBFB
- #F0E1FB
- #FBE0E0
Icon color:
- #3B82F6
- #A855F7
- #E5484D

### Link
Color: #FFFFFF

## Fonts
- assets/fonts/WorkSans-Regular.ttf
- assets/fonts/WorkSans-Medium.ttf
- assets/fonts/WorkSans-SemiBold.ttf
- assets/fonts/WorkSans-Bold.ttf
- assets/fonts/WorkSans-Italic.ttf
