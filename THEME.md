# md2ui Default theme

<!-- image-cards.webp inspires the #F6F6F6 canvas, near-white cards,
generous rounding, and two soft shadow layers. Green charts use green.png;
tinted task rows and nested panels borrow from the neighboring references.
All widgets are authored Markdown; links and figures are demo content. -->

## Fonts
- assets/fonts/Inter_18pt-Regular.ttf
- assets/fonts/Inter_18pt-SemiBold.ttf
- assets/fonts/Inter_18pt-Bold.ttf
- assets/fonts/IBMPlexMono-Regular.ttf

## Styling & Spacing

### Root
Background color: #F6F6F6
Padding: 64
Spacing: 32
Max width: 1440
Layout: Auto
<!--Layout: Bento-->
Stack sections: yes
Space small: 32
Space medium: 48
Space large: 62
#### Text
- Marker text color: #00E700

### Heading 1
Padding: 0
Spacing: 24

### Heading 2
Background color: #FDFDFD
Corner radius: 30
Padding: 24
Spacing: 18
Stroke width: 1
Stroke color: #FFFFFF
Outer shadow:
- Offset y: 3
- Radius: 7
- Color: #26263308
Outer shadow:
- Offset y: 16
- Radius: 30
- Color: #26263312

#### Marker
Number format: 1.
Space: 16
Font name: Inter 18pt
Font size: 64
Font color: #00E700
Font weight: 900
Aside: no


### Heading 3
Background color: #47474714
Corner radius: 20
Padding: 16
Spacing: 10

#### Marker
Number format: 1.
Space: 16
Font name: Inter 18pt
Font size: 32
Font color: #00E700
Font weight: 900
Aside: no

### Heading 4
Stroke width: 1
Stroke color: #D8D5E1
Corner radius: 16
Padding: 16
Spacing: 10

### Image Cards
Corner radius: 20
Padding: 16
Spacing: 10
Image card photo band: 3:2
Content valign: bottom
Background gradient:
- Type: Linear
- Colors:
  - #00000000
  - #152621E6
- Parameters:
  - Start: 0, 0.2
  - End: 0, 1

### Elements
Row spacing: 10
Col spacing: 10
<!-- Pictures keep the element gap too: a gallery's strip sits apart from its lead
picture, and its thumbnails apart from each other. -->
Image row spacing: 10
Image col spacing: 10


### Numbered Lists
Corner radius: 14
Padding: 12
Background color: #47474714
<!--Merge rows: yes-->

#### Marker
Number format: 1.
Space: 8
Font name: Inter 18pt
Font size: 14
Font color: #00E700
Font weight: 900
Aside: yes
Alignment: baseline

### Unordered Lists
Corner radius: 14
Padding: 12
Background color: #47474714
<!--Merge rows: yes-->


### Task Lists

Corner radius: 8
Padding: 12
Background color: #47474714
<!--Merge rows: yes-->
Inner shadow:
- Offset x: 1
- Offset y: 1
- Color: #1C1C1E1F
- Radius: 0
Outer shadow:
- Offset x: 1
- Offset y: 1
- Color: #FFFFFF1F
- Radius: 0

### Quotes
#### Marker
Bar width: 3
Bar length: 50
Bar color: #00E700
Space: 12

### Fixed styles

<!-- The section styles every answer can ask for by name: `## Title {#card-1}`. Each is
`Mode: override`, so it keeps the padding and spacing of the heading level it sits on and
changes only what it states. MEANINGS.md says what each is for. -->
#### Card
Padding: 22
Spacing: 14
Corner radius: 22
Background color: #A3F86A
Background gradient:
- Type: Linear
- Colors:
  - #00E70000
  - #00E700
- Parameters:
  - Start: 0.5, 0.0
  - End: 0.5, 1.0
Outer shadow:
- Offset y: 6
- Radius: 18
- Color: #26263312

#### Dark
Mode: override
Background color: #26262B
Stroke width: 0

#### Green
Mode: override
Background color: #00E700
Stroke width: 0

<!--https://unsplash.com/photos/a-blurry-image-of-a-green-and-white-background-iTjW5Q5ic8s-->
#### Music player
Corner radius: 30
Padding: 22
Spacing: 14
Background image: https://images.unsplash.com/photo-1679193559712-ec99ae6a74b9
Outer shadow:
- Offset y: 1
- Color: #1C1C1E0A
- Radius: 2
Outer shadow:
- Offset y: 12
- Color: #1C1C1E12
- Radius: 36
Background gradient:
- Type: Linear
- Colors:
  - #00E70000
  - #00E70064
- Parameters:
  - Start: 0, 0.2
  - End: 0, 1

#### Framed
Mode: override
Image bleed: yes
Stroke width: 2
Stroke color: #26262B
Outer shadow:
- Offset x: 4
- Offset y: 4
- Radius: 0
- Color: #26262B

## Images

### Placeholders

<!-- Colours from emoji-chips-palette.md and the rest of this theme: the avatars take
the chips' palette tints, under the theme's dark text. -->

#### Broken
Fill color: #FF003F19
Text color: #FF003F
Icon: ⛓️‍💥
Icon size: 30%

#### Avatar
Fill color:
- #00E7007F
- #823EE27F
- #00D9F57F
Text color: #26262B
Text style: Lead
Text size: 40%

#### Brand
Fill color: #26262B
Text color: #FFFFFF
Text style: Display
Text size: 32%

#### Media
Fill color: #47474714
Text color: #7C7C84
Icon: 🖼️
Icon size: 30%

## Content arrangement

### Bento
Heading level: 2

## Code Blocks
Syntax style: monokai
Background color: #002B0A
Corner radius: 12
Padding: 16
Line spacing: 4

## Text Styles

<!-- Global/base typography. Text, Muted, Lead, Display, Key, Value, and Text
Overline can be partially overridden by the local role blocks above. -->

Text
- Font Name: Inter 18pt
- Font size: 15
- Font color: #26262B

Heading1
- Font Name: Inter 18pt
- Font size: 48
- Font weight: 600
- Font color: #202025


Heading2
- Font Name: Inter 18pt
- Font size: 32
- Font weight: 600
- Font color: #26262B
- Marker text color: #00E700
- Marker background color: #00000000

Heading2 Overline
- Font size: 13
- Font color: #7C7C84
- Marker text color: #00E700

Heading3
- Font Name: Inter 18pt
- Font size: 24
- Font weight: 600
- Font color: #26262B
- Marker text color: #00E700

Heading4
- Font Name: Inter 18pt
- Font size: 18
- Font weight: 600
- Font color: #26262B
- Marker text color: #00E700

Heading5
- Font Name: Inter 18pt
- Font size: 14
- Font weight: 900
- Font color: #26262B
- Marker text color: #00E700

Heading6
- Font Name: Inter 18pt
- Font size: 10
- Font weight: 700
- Font color: #26262B
- Marker text color: #00E700

Muted
- Font size: 13
- Font color: #7C7C84

Lead
- Font size: 20
- Font weight: 600
- Font color: #26262B

Display
- Font Name: Inter 18pt
- Font size: 42
- Font weight: 900
- Font color: #202025

Key
- Font size: 12
- Font color: #7C7C84

Value
- Font size: 14
- Font weight: 900
- Font color: #26262B

Text Overline
- Font size: 12
- Font color: #7C7C84

Links
- Font size: 16
- Font weight: 900
- Font color: #FFFFFF

Links Secondary
- Font size: 16
- Font weight: 900
- Font color: #26262B

Links Tertiary
- Font size: 14
- Font weight: 900
- Font color: #FFFFFF

Links Quaternary
- Font size: 14
- Font weight: 900
- Font color: #26262B

Links Quinary
- Font size: 12
- Font weight: 900
- Font color: #FFFFFF

Links Senary
- Font size: 12
- Font weight: 900
- Font color: #26262B

Links Septenary
- Font size: 11
- Font weight: 900
- Font color: #26262B

Links Text
- Font color: #474747

Inline Code
- Font Name: Inter 18pt
- Font size: 11
- Font color: #1A1A1A

Inline Code Secondary
- Font color: #FFFFFF

Inline Code Tertiary
- Font color: #FFFFFF

Inline Code Quaternary
- Font color: #1A1A1A

Inline Code Quinary
- Font size: 9

Inline Code Senary
- Font size: 9
- Font color: #FFFFFF

Inline Code Septenary
- Font size: 9
- Font color: #FFFFFF

Code Block
- Font Name: IBM Plex Mono
- Font size: 13
- Font color: #00E700

## Links
Corner radius: 44
Padding top: 16
Padding bottom: 16
Padding left: 24
Padding right: 24
Emoji gap: 10
Emoji shape: circle
Emoji weight: 500
Emoji optical size: auto
Fill color: #26262B
Disabled fill color: #EEEEF0
Disabled text color: #96969D
Disabled stroke color: #E2E2E7
<!-- Every button variant inherits this Primary shadow and may add more layers. -->
Outer shadow:
- Offset y: 2
- Color: #26263312
- Radius: 6

### Secondary
Fill color: #1F1F1F00
Stroke width: 2
Stroke color: #26262B
Disabled fill color: #1F1F1F00

<!-- Sizes follow MEANINGS.md: bare and * are the large main and second
action, ** and *** the medium ones. -->
### Tertiary
Padding top: 10
Padding bottom: 10
Padding left: 14
Padding right: 14
Emoji gap: 4

### Quaternary
Padding top: 10
Padding bottom: 10
Padding left: 14
Padding right: 14
Emoji gap: 4
Fill color: #1F1F1F00
Stroke width: 2
Stroke color: #26262B
Disabled fill color: #1F1F1F00

<!-- The small ladder (MEANINGS.md): _ the main action small, __ a second
action small, ___ an extra-small action. -->
### Quinary
Emoji weight: 600
Corner radius: 8
Padding top: 7
Padding bottom: 7
Padding left: 11
Padding right: 11
Fill color: #474747

### Senary
Emoji weight: 600
Corner radius: 8
Padding top: 7
Padding bottom: 7
Padding left: 11
Padding right: 11
Fill color: #1F1F1F00
Stroke width: 1.5
Stroke color: #474747
Disabled fill color: #1F1F1F00

<!--Extra small-->

### Septenary
Emoji weight: 600
Corner radius: 4
Padding top: 4
Padding bottom: 4
Padding left: 8
Padding right: 8
Fill color: #1F1F1F00
Stroke width: 1.5
Stroke color: #474747
Disabled fill color: #1F1F1F00

### Text
Fill color: #00000000
Padding: 6

### Inline
Text color: #00E700
Underline: yes

## Inline Code
<!-- Fills come from emoji-chips-palette.md. A muted chip is an outline: no fill,
a stroke in its variant's fill colour, and the card's own text colour. The width
is set for every chip; an enabled chip's stroke is transparent. -->
Fill color: #00E7007F
Stroke width: 1
Stroke color: #00000000
Disabled fill color: #00000000
Disabled stroke color: #00E700
Disabled text color: #26262B
Corner radius: 12
Padding: 5
Emoji weight: 500
Emoji optical size: auto

### Secondary
Fill color: #823EE27F
Disabled fill color: #00000000
Disabled stroke color: #823EE2

### Tertiary
Fill color: #4747477F
Disabled fill color: #00000000
Disabled stroke color: #474747

### Quaternary
Fill color: #FF003F7F
Disabled fill color: #00000000
Disabled stroke color: #FF003F

<!-- The small chips: _ `x` _, __ __, ___ ___ are Primary, Secondary and
Tertiary at a compact size (MEANINGS.md). -->
### Quinary
Emoji weight: 600
Corner radius: 8
Padding: 3

### Senary
Emoji weight: 600
Fill color: #823EE27F
Disabled fill color: #00000000
Disabled stroke color: #823EE2
Corner radius: 8
Padding: 3

### Septenary
Emoji weight: 600
Fill color: #4747477F
Disabled fill color: #00000000
Disabled stroke color: #474747
Corner radius: 8
Padding: 3

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf
<!-- Every emoji draws as a Material Symbols icon (assets/icons/). Weights
thin out as badges grow: the large badge at 300, the standard at 400, the
small ones heavier so they hold up beside small text. -->

<!-- Sizes follow MEANINGS.md: bare is the standard icon, * large,
** small, *** extra small. Every variant inherits Primary's shadow. -->

### Primary
Shape: circle
Corner radius: 16
Size: 24
Emoji weight: 300
Emoji optical size: auto
Padding: 12
Icon color: #26262B
Background color: #00E700

### Secondary
Shape: square
Size: 42
Corner radius: 16
Emoji weight: 200
Padding: 12
Icon color: #26262B
Background color: #26262B19

### Tertiary
Size: 20
Emoji weight: 500
Padding: 6
Icon color: #00E700
Background color: #00000000

### Quaternary
Shape: circle
Size: 14
Emoji weight: 600
Padding: 4
Icon color: #26262B
Background color: #26262B19

### Quinary
Shape: circle
Size: 16
Emoji weight: 500
Padding: 9
Icon color: #FFFFFF
Background color: #474747

### Text
Color: #1A1A1A

### Link
Color: #474747

### Inline
Color: #1A1A1A

## Fixed colors

### Badges
#### Contains
- ▲ : Text color: #00E700, Fill color: #00E70019
- ▼ : Text color: #FF003F, Fill color: #FF003F19
- 🟢 : Text color: #00E700, Fill color: #00E7007F 
- 🔴 : Text color: #FF003F, Fill color: #FF003F19
<!-- Each status glyph is also pinned under ### Emoji in its chip's text colour, so the
glyph and the words read as one colour. -->
- ✓: Text color: #00E700, Fill color: #00E70019
- 🔄: Text color: #823EE2, Fill color: #823EE219
- ⏳: Text color: #FF8100, Fill color: #FF810019
- ✕: Text color: #7C7C84, Fill color: #7C7C8419

### Buttons
  #### Exact
  - ❤️ : Text color: #FF003F, Fill color: #26262B
  <!--- Cancel: Text color: #FF003F, Fill color: #FF003F, Stroke color: #FF003F-->
  

  #### Contains
  - Cancel: Text color: #FF003F, Fill color: #FF003F, Stroke color: #FF003F
  - Delete: Text color: #FF003F, Fill color: #FF003F, Stroke color: #FF003F
  - Accept: Text color: #00E700, Fill color: #00E700, Stroke color: #00E700
  - Approve: Text color: #00E700, Fill color: #00E700, Stroke color: #00E700
  - OK: Text color: #00E700, Fill color: #00E700, Stroke color: #00E700
  

### Emoji
<!-- Weather, from emoji-chips-palette.md: warm (sun) to cloud, wet (rain),
storm, cold (snow, ice, wind), then rainbow, night, heat and water. A quoted
emoji is text and paints this glyph colour. A badge is pinned to the same
colour under the Emoji background block, so the glyph pin equals the fill
behind it, is dropped, and the badge glyph falls back to black or white
through the Color Replacements rules. -->
- ☀️ #FF8100
- 🌤️ #FFB600
- ⛅ #FFF200
- 🌥️ #D9FF00
- ☁️ #7AFC00
- 🌫️ #7AFC00
- 🌦️ #00D9F5
- 🌧️ #00AEFF
- ⛈️ #823EE2
- 🌩️ #F83AE2
- 🌨️ #00D9F5
- ❄️ #00D9F5
- 🌪️ #823EE2
- 🌬️ #00D9F5
- 💨 #00D9F5
- 🌈 #F83AE2
- 🌙 #823EE2
- 🌡️ #FF003F
- ☔ #00AEFF
- 💧 #00AEFF
- 🚶 #823EE2
- ✅ #00E700
- ✓ #00E700
- 🔄 #823EE2
- ⏳ #FF8100
- ✕ #7C7C84
- ⚠️ #FF8100
- ❌ #FF003F
- 🛑 #FF003F
- 🔴 #FF003F
- 🟢 #00E700
- ▲ #00E700
- ▼ #FF003F

### Emoji background
- ☀️ #FF8100
- 🌤️ #FFB600
- ⛅ #FFF200
- 🌥️ #D9FF00
- ☁️ #7AFC00
- 🌫️ #7AFC00
- 🌦️ #00D9F5
- 🌧️ #00AEFF
- ⛈️ #823EE2
- 🌩️ #F83AE2
- 🌨️ #00D9F5
- ❄️ #00D9F5
- 🌪️ #823EE2
- 🌬️ #00D9F5
- 💨 #00D9F5
- 🌈 #F83AE2
- 🌙 #823EE2
- 🌡️ #FF003F
- ☔ #00AEFF
- 💧 #00AEFF
-  ✓ #00E700

## Separators
Dash: hide
Pipe: hide

## Horizontal Rule
<!-- Global fallback for rules outside a closer Styling & Spacing declaration. -->
Stroke width: 1
Stroke color: #EAEAEF

## Drawing elements

### Ratio Bars
Thickness: 10
Corner radius: 5
Text side: right
Background color: #00E700

### Ratio Bar Track
Background color: #47474714
Corner radius: 5

### Task controls
Type: switch
Size: 20
Padding: 5
Corner radius: 20
Space: 10

### Checked outer
Background color: #00E700
Inner shadow:
- Offset x: 1
- Offset y: 1
- Color: #1C1C1E1F
- Radius: 0

### Checked inner
Background color: #FDFDFD
Outer shadow:
- Offset x: 1
- Offset y: 1
- Color: #1C1C1E1F
- Radius: 0

### Unchecked outer
Background color: #C9C9C9
Inner shadow:
- Offset x: 1
- Offset y: 1
- Color: #1C1C1E1F
- Radius: 0

### Unchecked inner
Background color: #FDFDFD
Outer shadow:
- Offset x: 1
- Offset y: 1
- Color: #1C1C1E1F
- Radius: 0

### Sliders
Style: thick
Axis: vertical
Length: 250
Thickness: 100
Corner radius: 16
Circle diameter: 28
Drag bar length: 22
Bar thickness: 3

### Slider Track
Padding: 0
Background color: #47474714
Inner shadow:
- Offset x: 1
- Offset y: 1
- Color: #1C1C1E1F
- Radius: 0

### Slider Bar
Background color: #FFFFFFBF
Inner shadow:
- Offset x: 1
- Offset y: 1
- Color: #1C1C1E19
- Radius: 0
- 
### Slider Handle
Background color: #FFFFFF


### Unit Ratios
Style: ring
Show total: no

### Ring
Diameter: 148
Thickness: 8
Background color: #00E700
- Font size: 28
- Font weight: 600

### Ring Unit
- Font size: 13
- Font color: #7C7C84

### Ring Track
Background color: #47474714

### Key Value Bars
Thickness: 8
Corner radius: 5
Background color: #00E700
Position: below

### Key Value Bar Track
Background color: #47474714
Corner radius: 5

### Dates
Background color: #823EE232
Corner radius: 14
Padding: 12
Spacing: 3

### Date Key
- Font size: 11
- Font color: #823EE2
### Date Day
- Font size: 28
- Font weight: 600
- Font color: #1A1A1A

## Charts
Bar thickness: 18
Bar spacing: 10
Bar width: fill
Corner radius: 5
Background color: #00E700
Negative color: #B4B4BB

### Chart Track
Background color: #47474714
Corner radius: 5

### Chart Labels
- Font size: 12
- Font color: #7C7C84

### Chart Values
- Font size: 11
- Font color: #474747

### Line Chart
Height: 56
Line width: 2
Point size: 6
Background gradient:
- Type: Linear
- Colors:
  - #00E70066
  - #00E70008
- Parameters:
  - Start: 0.5, 0
  - End: 0.5, 1

## Tables

### Table
Merge rows: yes
Background color: #FDFDFD00
Corner radius: 0
Row spacing: 8
Col spacing: 6
Stacking cards: yes
Card layout: title

### Header
Background color: #00E7007F
Padding: 8
- Font name: Inter 18pt
- Font size: 12
- Font weight: 600
- Font color: #474747

### Cells
Background colors:
- #FDFDFD
- #F4F6F5
Corner radius: 0
Padding: 8
- Font name: Inter 18pt
- Font size: 14
- Font color: #26262B

### Card Keys
Key spacing: 6
- Font name: Inter 18pt
- Font size: 11
- Font color: #7C7C84

## Color Replacements
<!-- Solid green panels: text takes the default black. Anything filled the panel's own
green (a Primary emoji, a Primary chip) turns black, and its glyph or label turns
green on it. #1A1A1A is that black alone, so the #26262B rules (white) never reach it. -->
On background color: #00E700
- Replacement: #26262B
- Fill color: #00E700, Replacement: #1A1A1A
- Fill color: #00E7007F, Replacement: #1A1A1A

On background color: #1A1A1A
- Replacement: #00E700
<!--- Fill color: #26262B, Replacement: #FFFFFF-->

<!-- A black button turned white keeps a black label. -->
On background color: #FFFFFF
- Text color: #FFFFFF, Replacement: #26262B

On background color: #FF003F
- Replacement: #FFFFFF



<!-- Weather badges (### Emoji background): the glyph is black, white on purple.
Primary, Secondary and Quaternary icons are already #26262B; these catch the
Tertiary (#00E700) and Quinary (#FFFFFF) icons. -->
On background color: #823EE2
- Text color: #26262B, Replacement: #FFFFFF
- Text color: #00E700, Replacement: #FFFFFF

On background color: #FF8100
- Text color: #00E700, Replacement: #26262B
- Text color: #FFFFFF, Replacement: #26262B

On background color: #FFB600
- Text color: #00E700, Replacement: #26262B
- Text color: #FFFFFF, Replacement: #26262B

On background color: #FFF200
- Text color: #00E700, Replacement: #26262B
- Text color: #FFFFFF, Replacement: #26262B

On background color: #D9FF00
- Text color: #00E700, Replacement: #26262B
- Text color: #FFFFFF, Replacement: #26262B

On background color: #7AFC00
- Text color: #00E700, Replacement: #26262B
- Text color: #FFFFFF, Replacement: #26262B

On background color: #00D9F5
- Text color: #00E700, Replacement: #26262B
- Text color: #FFFFFF, Replacement: #26262B

On background color: #00AEFF
- Text color: #00E700, Replacement: #26262B
- Text color: #FFFFFF, Replacement: #26262B

On background color: #F83AE2
- Text color: #00E700, Replacement: #26262B
- Text color: #FFFFFF, Replacement: #26262B

On background color: #FF003F
- Text color: #00E700, Replacement: #26262B
- Text color: #FFFFFF, Replacement: #26262B

On background color: #26262B
- Text color: #474747, Replacement: #FFFFFF

On background color : #FF003F
- Text color: 7C7C84, Replacement: #FFFFFF

<!-- Dark cards: a `###` inside one keeps a translucent white fill instead of the grey
one, and its text turns white with it; primary buttons become white, as on green. -->
On background color: #26262B
- Replacement: #FFFFFF
- Fill color: #47474714, Replacement: #FFFFFF14
- Fill color: #26262B, Replacement: #FFFFFF
- Stroke color: #26262B, Replacement: #FFFFFF

<!-- Tables: the light zebra cells and the pale green header turn translucent
white and green, and their text white, through the surfaces below. -->
- Fill color: #FDFDFD, Replacement: #FFFFFF14
- Fill color: #F4F6F5, Replacement: #FFFFFF0A
- Fill color: #00E7007F, Replacement: #00E70033

On background color: #FFFFFF14
- Replacement: #FFFFFF
- Fill color: #26262B, Replacement: #FFFFFF
- Stroke color: #26262B, Replacement: #FFFFFF

On background color: #FFFFFF0A
- Replacement: #FFFFFF
- Fill color: #26262B, Replacement: #FFFFFF
- Stroke color: #26262B, Replacement: #FFFFFF

On background color: #00E70033
- Replacement: #FFFFFF

On background color: #47474714
- Fill color: #47474714, Replacement: #FFFFFFBF

On background color: #FFFFFFBF
- Fill color: #FFFFFFBF, Replacement: #4747473F

On background color: image
- Replacement: #FFFFFF
- Stroke color: #26262B, Replacement: #FFFFFF
- Fill color: #00E700, Replacement: #26262B

<!-- The music player's photo is pale: its text and outlined buttons stay black. -->
On background color: image Music player
- Replacement: #26262B
- Fill color: #00E700, Replacement: #26262B
