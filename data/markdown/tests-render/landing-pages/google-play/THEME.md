# Google Play Console

<!-- developer.android.com/distribute/console, a 1216px CSS page. Render content-themed.md at --width 1216.

     Palette, sampled from the source page:
       #FFFFFF  page
       #F8F9FA  the breadcrumb band
       #D3E3FD  the feature cards           (M3 primary container)
       #000000  hero title, filled CTA
       #202124  titles, links, footer copy
       #3C4043  card body
       #5F6368  footer column titles
       #0B57D0  "Learn More", "Android Studio"
       #DADCE0  the hairlines under the nav and above the footer rows

     Each page band is an untitled `# {#name-1}` heading, so each band carries its
     own padding and alignment as a fixed style; Root has no padding, so the nav,
     the breadcrumb band and the footer can reach the window's edges. -->

## Styling & Spacing

### Root
Background color: #FFFFFF
Padding: 0
Spacing: 0
Max width: 1216

### Elements
Row spacing: 8
Col spacing: 8
Group spacing: 0
Group row spacing: 16

### Heading 1
<!-- The gap between gridded cards inside a band: the band's own fixed style
     does not set it (findings/theme-guide-gaps). -->
Padding: 0
Spacing: 32

### Heading 2
<!-- The two wide feature cards. -->
Background color: #D3E3FD
Corner radius: 24
Padding: 32
Spacing: 24
#### Text
- Font size: 14

### Heading 3
<!-- The three narrow feature cards: their own level, so they find their own column
     count. Padding 24, not 32, or three do not fit. -->
Background color: #D3E3FD
Corner radius: 24
Padding: 24
Spacing: 24
#### Text
- Font size: 14

### Fixed styles

#### Nav
Padding top: 8
Padding bottom: 8
Padding left: 24
Padding right: 24
Vertical align: center
Stroke width: 0
##### Lead
- Font size: 22
- Font weight: 500
- Font color: #202124

#### Crumb
Background color: #F8F9FA
Padding top: 32
Padding bottom: 32
Padding left: 24
Padding right: 24

#### Hero
<!-- The logo's cell: 128 + 160 + 128, which leaves the copy the reference's
     ~610px column, where the title breaks after "Play". -->
Spacer large row: 128
Spacer large col: 32
Vertical align: center
Padding top: 56
Padding bottom: 80
Padding left: 64
Padding right: 64
##### Display
- Font size: 64
- Font weight: 500
- Font color: #000000
##### Text
- Font size: 20
- Font color: #202124

#### Features
<!-- 24 rather than the reference's 64: see the finding on the 10-40 word floor. -->
Padding left: 24
Padding right: 24
Spacing: 80

#### Cta
<!-- Holds the closing title to the reference's two lines. -->
Spacer large row: 250
Spacer large col: 32
Padding top: 120
Padding bottom: 80
Padding left: 64
Padding right: 64
Horizontal align: center
##### Display
- Font size: 40
- Font weight: 500
- Font color: #202124

#### Social
Padding top: 40
Padding bottom: 40
Padding left: 24
Padding right: 24
Horizontal align: center
##### Text
- Font size: 13
- Font color: #202124

#### Sitemap
Padding top: 24
Padding bottom: 24
Spacer large col: 32
Padding left: 24
Padding right: 24

#### Brand
Padding top: 24
Padding bottom: 24
Padding left: 24
Padding right: 24
Vertical align: center

#### Legal
Padding top: 24
Padding bottom: 24
Padding left: 24
Padding right: 24
Vertical align: center
##### Text
- Font size: 13
- Font color: #202124

## Text Styles

Heading1
- Font Name: google sans
- Font size: 64
- Font weight: 500
- Font color: #000000

Heading2
- Font Name: google sans
- Font size: 32
- Font weight: 400
- Font color: #202124

Heading3
- Font Name: google sans
- Font size: 32
- Font weight: 400
- Font color: #202124

Heading6
- Font Name: google sans
- Font size: 13
- Font weight: 500
- Font color: #5F6368

Text
- Font Name: google sans
- Font size: 16
- Font weight: 400
- Font color: #3C4043

Muted
- Font Name: google sans
- Font size: 13
- Font weight: 400
- Font color: #5F6368

Lead
- Font Name: google sans
- Font size: 20
- Font weight: 400
- Font color: #202124

Display
- Font Name: google sans
- Font size: 40
- Font weight: 400
- Font color: #202124

<!-- Primary: the black "Sign in" and "Subscribe" pills. -->
Links
- Font Name: google sans
- Font size: 15
- Font weight: 500
- Font color: #FFFFFF

<!-- Secondary: the outlined "Discover how". -->
Links Secondary
- Font Name: google sans
- Font size: 15
- Font weight: 500
- Font color: #202124

<!-- Tertiary: the grey search field in the nav. -->
Links Tertiary
- Font Name: google sans
- Font size: 15
- Font weight: 400
- Font color: #5F6368

<!-- Quaternary: the blue "Learn More" and "Android Studio". -->
Links Quaternary
- Font Name: google sans
- Font size: 15
- Font weight: 500
- Font color: #0B57D0

<!-- Text: nav and footer links. -->
Links Text
- Font Name: google sans
- Font size: 13
- Font weight: 400
- Font color: #202124

## Links

### Primary
Corner radius: 999
Fill color: #000000
Padding top: 12
Padding bottom: 12
Padding left: 24
Padding right: 24
Stroke width: 0

### Secondary
Corner radius: 999
Fill color: #00000000
Padding top: 12
Padding bottom: 12
Padding left: 24
Padding right: 24
Stroke width: 1.5
Stroke color: #202124

### Tertiary
Corner radius: 6
Fill color: #F1F3F4
Padding top: 8
Padding bottom: 8
Padding left: 12
Padding right: 120
Stroke width: 0

### Quaternary
Corner radius: 0
Fill color: #00000000
Padding top: 12
Padding bottom: 12
Padding left: 16
Padding right: 16
Stroke width: 0

### Text
Corner radius: 0
Fill color: #00000000
Padding top: 3
Padding bottom: 3
Padding left: 0
Padding right: 0
Stroke width: 0

### Inline
Text color: #0B57D0
Underline: no

## Horizontal Rule
Stroke color: #DADCE0
Stroke width: 1

## Separators
Dash: hide
Bullet: hide
Bar: show

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

## Fonts
- assets/fonts/GoogleSans-Regular.ttf
- assets/fonts/GoogleSans-Italic.ttf
- assets/fonts/GoogleSans-Medium.ttf
- assets/fonts/GoogleSans-MediumItalic.ttf
- assets/fonts/GoogleSans-SemiBold.ttf
- assets/fonts/GoogleSans-SemiBoldItalic.ttf
- assets/fonts/GoogleSans-Bold.ttf
- assets/fonts/GoogleSans-BoldItalic.ttf
