# OpenAI Codex

<!-- openai.com/codex, a 1201px CSS page. Render
     content.md at --width 1201.

     Sampled from the source page:
       #000000  the page
       #1F1F1F  product and testimonial cards
       #C3CEF6 → #8F9CF5 → #4E59B0  the hero's gradient, top to bottom (the capture's
                photo did not load; a gradient stands in for it)
       #FFFFFF  text and the white pill buttons on black
       #A6A6A6  testimonial attribution and footer column titles

     OpenAI Sans is not available; Inter is the nearest grotesque in assets/fonts.
     Text is white everywhere; on the two gradient bands, Color Replacements turn it black. -->

## Styling & Spacing

### Root
Background color: #000000
Padding: 0
Spacing: 0
Max width: 1201

### Elements
Row spacing: 8
Col spacing: 8
Group spacing: 16

### Heading 1
<!-- The gap between gridded cards inside a band comes from here, not from the band's
     fixed style (findings/theme-guide-gaps, claim 1). -->
Padding: 0
Spacing: 24

### Heading 3
<!-- Product and testimonial cards. -->
Background color: #1F1F1F
Corner radius: 6
Padding: 28
Spacing: 16

### Heading 4
<!-- Testimonial cards: the same card as Heading 3, at its own level so the two boards
     find their own column counts. -->
Background color: #1F1F1F
Corner radius: 6
Padding: 28
Spacing: 16

### Fixed styles

#### Nav
Background color: #C3CEF6
Padding top: 14
Padding bottom: 14
Padding left: 32
Padding right: 32
Vertical align: center
##### Lead
- Font size: 22
- Font weight: 600
- Font color: #000000

#### Hero
Background color: #8F9CF5
Background gradient:
- Type: Linear
- Colors:
  - #C3CEF6
  - #A9B6F7
  - #4E59B0
- Parameters:
  - Start: 0.5, 0.0
  - End: 0.5, 1.0
Padding top: 48
Padding bottom: 48
Padding left: 32
Padding right: 32
Horizontal align: center
##### Display
- Font size: 60
- Font weight: 500
- Font color: #000000
##### Text
- Font size: 18
- Font color: #000000

#### Agents
Padding top: 120
Padding bottom: 80
Padding left: 32
Padding right: 32

#### Surfaces
Padding top: 80
Padding bottom: 80
Padding left: 32
Padding right: 32
Spacing: 24

#### Voices
Padding top: 80
Padding bottom: 80
Padding left: 32
Padding right: 32
Spacing: 24

#### Cta
Padding top: 120
Padding bottom: 160
Padding left: 32
Padding right: 32
##### Text
- Font size: 18

#### Footer
Padding top: 40
Padding bottom: 40
Padding left: 32
Padding right: 32

## Text Styles

Text
- Font Name: Inter 18pt
- Font size: 17
- Font weight: 400
- Font color: #FFFFFF

Heading1
- Font Name: Inter 18pt

Heading2
- Font Name: Inter 18pt

Heading4
- Font Name: Inter 18pt

Heading5
- Font Name: Inter 18pt

<!-- Footer column titles. -->
Heading6
- Font Name: Inter 18pt
- Font size: 14
- Font weight: 400
- Font color: #A6A6A6

Text Overline
- Font Name: Inter 18pt

Labels
- Font Name: Inter 18pt

Inline Code
- Font Name: Inter 18pt

Heading3
- Font Name: Inter 18pt
- Font size: 22
- Font weight: 400
- Font color: #FFFFFF

Muted
- Font Name: Inter 18pt
- Font size: 14
- Font weight: 400
- Font color: #A6A6A6

Lead
- Font Name: Inter 18pt
- Font size: 28
- Font weight: 400
- Font color: #FFFFFF

Display
- Font Name: Inter 18pt
- Font size: 48
- Font weight: 500
- Font color: #FFFFFF

<!-- Primary: the black "Download for macOS" and "Try ChatGPT" pills on the gradient. -->
Links
- Font Name: Inter 18pt
- Font size: 15
- Font weight: 500
- Font color: #FFFFFF

<!-- Secondary: the white pills on black. -->
Links Secondary
- Font Name: Inter 18pt
- Font size: 15
- Font weight: 500
- Font color: #000000

<!-- Tertiary: "Log in", a translucent pill on the gradient. -->
Links Tertiary
- Font Name: Inter 18pt
- Font size: 15
- Font weight: 500
- Font color: #000000

<!-- Quaternary: the footer's language pill. -->
Links Quaternary
- Font Name: Inter 18pt
- Font size: 15
- Font weight: 500
- Font color: #FFFFFF

<!-- Text: nav and footer links. -->
Links Text
- Font Name: Inter 18pt
- Font size: 14
- Font weight: 400
- Font color: #FFFFFF

## Links

### Primary
Corner radius: 999
Fill color: #000000
Padding top: 11
Padding bottom: 11
Padding left: 20
Padding right: 20
Stroke width: 0

### Secondary
Corner radius: 999
Fill color: #FFFFFF
Padding top: 11
Padding bottom: 11
Padding left: 20
Padding right: 20
Stroke width: 0

### Tertiary
Corner radius: 999
Fill color: #FFFFFF33
Padding top: 11
Padding bottom: 11
Padding left: 20
Padding right: 20
Stroke width: 0

### Quaternary
<!-- The dark language pill in the footer. -->
Corner radius: 999
Fill color: #2A2A2A
Padding top: 11
Padding bottom: 11
Padding left: 20
Padding right: 20
Stroke width: 0

### Text
Corner radius: 0
Fill color: #00000000
Padding top: 6
Padding bottom: 6
Padding left: 0
Padding right: 16
Stroke width: 0

## Color Replacements

On background color: #C3CEF6
- Text color: #FFFFFF, Replacement: #000000

On background color: #8F9CF5
- Text color: #FFFFFF, Replacement: #000000

## Separators
Dash: hide
Bullet: hide
Bar: hide

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

## Fonts
- assets/fonts/Inter_18pt-Regular.ttf
- assets/fonts/Inter_18pt-Medium.ttf
- assets/fonts/Inter_18pt-SemiBold.ttf
- assets/fonts/Inter_18pt-Bold.ttf
- assets/fonts/Inter_18pt-Italic.ttf
