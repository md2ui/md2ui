# Coda.io

<!-- Written from the 13 reference screenshots in this folder, against skills/
     and THEME_GUIDE.md only. Palette sampled from the references:
       #FBE7CD  peach band (hero, testimonial card, "want to know more")
       #FEF7ED  cream band (templates section, footer)
       #DCF2FE  pale blue band (the Fast Company pull-quote)
       #E85D3C  Coda orange (accent words, logo)
       #1A1A1A  ink            #6E6E73  secondary ink
-->

## Background styles and Spacing

### Root
Background color: #FFFFFF
<!-- 0 so each band can bleed edge to edge; the bands carry their own padding. -->
Padding: 0
Max width: 1280
Centered: yes
Horizontal align: Left
Spacing: 0

### Elements
Row spacing: 14
Col spacing: 12
Group spacing: 28
Image distance: 18
Image spacing: 32
Padding: 0

### Image Cards
Corner radius: 16
Padding: 20

<!-- The page bands. One entry per `# ` section, in document order:
     nav, hero, logos, quote, 4-ways, gallery, AI, packs, templates,
     want-to-know-more, testimonial, pricing, footer. -->
### Heading 1
Spacing: 28
Padding left: 64
Padding right: 64
Padding top: 56
Padding bottom: 56
Background color:
- #FBE7CD
- #FBE7CD
- #FFFFFF
- #DCF2FE
- #FFFFFF
- #FFFFFF
- #FFFFFF
- #FFFFFF
- #FEF7ED
- #FBE7CD
- #FFFFFF
- #FFFFFF
- #FEF7ED

### Heading 2
Padding: 0
Spacing: 20

<!-- The three Coda AI cards: a tinted image band clipped to the card's top
     corners, then a white body. `Image bleed` is what pulls the picture out
     over the card's own padding. -->
### Heading 3
Background color: #FFFFFF
Corner radius: 12
Padding: 20
Spacing: 10
Stroke width: 1
Stroke color: #E6E6E6
Image bleed: yes

<!-- The template rows are `- ` list items, so the row container is the LIST ITEM and the
     rotation is dealt there: the white card goes to the first item, the rest sit on the
     band. `Background colors:` (plural) is the list-level spelling. -->
### Heading 4
Padding: 0
Spacing: 0

### Unordered Lists
Corner radius: 14
Padding top: 16
Padding bottom: 16
Padding left: 18
Padding right: 18
Background colors:
- #FFFFFF
- #00000000
- #00000000
- #00000000

### Heading 5
Padding: 0
Spacing: 12

### Heading 6
Padding: 0
Spacing: 10

<!-- The Huge testimonial: a peach card inset on the white page, selected by
     the `{#testimonial-1}` ID on its band. A fixed style REPLACES the level's
     style, so the padding is restated here. -->
### Fixed styles

#### Screenshot
<!-- Coda's "sticker" frame: a hairline border and a HARD offset shadow.
     `Radius: 0` on the shadow is what makes it solid rather than blurred, and
     `Image bleed` lets the picture reach the frame and take its corners. -->
Background color: #FFFFFF
Corner radius: 12
Padding: 0
Stroke width: 1
Stroke color: #111111
Image bleed: yes
Outer shadow:
- Offset x: 8
- Offset y: 8
- Color: #111111FF
- Radius: 0

#### Testimonial
Background color: #FBE7CD
Corner radius: 28
Padding: 56
Spacing: 24

## Text Styles

Heading1
- Font Name: Work Sans
- Font size: 58
- Font weight: 900
- Font color: #1A1A1A
<!-- Coda sets one phrase of a headline in brand orange. An inline `code` span
     that stays inside the text is a MARKER: it keeps this block's family, size
     and weight and only takes these two colours. Transparent background so the
     phrase is recoloured rather than highlighted. -->
- Marker text color: #E85D3C
- Marker background color: #00000000

Heading2
- Font Name: Work Sans
- Font size: 38
- Font weight: 900
- Font color: #1A1A1A

Heading3
- Font Name: Inter 18pt
- Font size: 19
- Font weight: 700
- Font color: #1A1A1A

Heading4
- Font Name: Inter 18pt
- Font size: 20
- Font weight: 600
- Font color: #1A1A1A

Heading5
- Font Name: Inter 24pt
- Font size: 30
- Font weight: 400
- Font color: #1A1A1A

Heading6
- Font Name: Inter 18pt
- Font size: 15
- Font weight: 500
- Font color: #8A8A8E

Text
- Font Name: Inter 18pt
- Font size: 17
- Font weight: 400
- Font color: #6E6E73

Muted
- Font Name: Inter 18pt
- Font size: 15
- Font weight: 500
- Font color: #8A8A8E

Lead
- Font Name: Work Sans
- Font size: 30
- Font weight: 800
- Font color: #1A1A1A

Display
- Font Name: Inter 24pt
- Font size: 30
- Font weight: 400
- Font color: #1A1A1A

Text Overline
- Font Name: Inter 18pt
- Font size: 13
- Font weight: 500
- Font color: #8A8A8E

Links
- Font Name: Inter 18pt
- Font size: 16
- Font weight: 600
- Font color: #FFFFFF

Links Secondary
- Font Name: Inter 18pt
- Font size: 16
- Font weight: 600
- Font color: #1A1A1A

Links Tertiary
- Font Name: Inter 18pt
- Font size: 16
- Font weight: 500
- Font color: #1A1A1A

Links Text
- Font Name: Inter 18pt
- Font size: 16
- Font weight: 400
- Font color: #1A1A1A

Inline Code Text
- Font Name: Inter 18pt
- Font size: 15
- Font weight: 400
- Font color: #6E6E73

## Links

<!-- Four looks, one per wrapper: the black CTA, the white outlined button,
     the flat nav item, and a plain text link. -->

### Primary
Corner radius: 8
Fill color: #000000
Padding: 16
Stroke width: 0

### Secondary
Corner radius: 8
Fill color: #FFFFFF
Padding: 16
Stroke width: 1
Stroke color: #DEDCD7

### Tertiary
Corner radius: 8
Fill color: #00000000
Padding top: 8
Padding bottom: 8
Padding left: 10
Padding right: 10
Stroke width: 0

### Text
Corner radius: 0
Fill color: #00000000
Padding: 0
Stroke width: 0

## Inline Code
Corner radius: 6
Fill color: #00000000
Padding: 0
Stroke width: 0

## Horizontal Rule
Color: #E7E2D9
Thickness: 1

## Separators
Dash: hide

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

## Fonts
- assets/fonts/WorkSans-Black.ttf
- assets/fonts/WorkSans-ExtraBold.ttf
- assets/fonts/WorkSans-Bold.ttf
- assets/fonts/WorkSans-SemiBold.ttf
- assets/fonts/WorkSans-Medium.ttf
- assets/fonts/WorkSans-Regular.ttf
- assets/fonts/Inter_18pt-Regular.ttf
- assets/fonts/Inter_18pt-Medium.ttf
- assets/fonts/Inter_18pt-SemiBold.ttf
- assets/fonts/Inter_18pt-Bold.ttf
- assets/fonts/Inter_24pt-Regular.ttf
- assets/fonts/Inter_24pt-Medium.ttf

## Color Replacements

On background color: #FBE7CD
- Fill color: #FFFFFF, Replacement: #FFFCF8

On background color: #DCF2FE
- Fill color: #FFFFFF, Replacement: #FFFFFF

## Tables

### Table
Background color: #00000000
Stroke width: 0
Stacking cards: no

### Header
Background color: #00000000
Font size: 1

### Cells
Background color: #00000000
Padding: 8
