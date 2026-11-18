# Daylight — soft surfaces

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
Padding: 40
Spacing: 32
Max width: 1440
<!--Layout: Bento-->
Stack sections: yes

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
<!-- Local role blocks affect only content inside Heading 2 sections. Omitted
roles and omitted properties continue to inherit their outer/global values. -->
#### Text
- Font size: 16
#### Display
- Font color: #25845B
<!-- Rules inside Heading 2 sections use this thicker green paint. -->
#### Horizontal Rule
Stroke color: #91B7A4
Stroke width: 2
<!-- Exact-level example: only numbered Heading 2 nodes receive this marker.
Aside: no places the ordinal above the section body. -->
#### Marker
Number format: (1)
Font name: Inter 18pt
Font size: 18
Font weight: 600
Font color: #B8A0DF
Space: 8
Aside: no

### Heading 3
Background color: #F2F1F5
Corner radius: 20
Padding: 16
Spacing: 10
#### Muted
- Font color: #5C7468
<!-- This closer level changes only rule color and inherits Heading 2 width. -->
#### Horizontal Rule
Stroke color: #E2BF83
<!-- Baseline alignment compares the marker with the first line of the whole
Heading 3 body, rather than merely centering it in a fixed gutter. -->
#### Marker
Number format: 1.
Font name: Inter 18pt
Font size: 15
Font weight: 600
Font color: #91B7A4
Space: 10
Aside: yes
Alignment: baseline
 
### Heading 4
Stroke width: 1
Stroke color: #D8D5E1
Corner radius: 20
Padding: 16
Spacing: 10

### Image Cards
Corner radius: 20
Padding: 16
Spacing: 10
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
Group spacing: 18
Image distance: 10



#### Text
- Font name: Georgia
<!--
#### Marker
Shape: circle
Size: 5
Color: #91B7A4
Space: 10
Aside: yes
Alignment: top-->

### Numbered Lists
#### Marker
Number format: 1.
Space: 10
Font name: Inter 18pt
Font size: 13
Font color: #9AFF1F
Aside: yes
Alignment: bottom

### Unordered Lists
Corner radius: 14
Padding: 12
Background color: #FFFF1F


### Task Lists
Background color: #1F6DFF
Padding: 12
Corner radius: 14

#### Text
- Font weight: 600
<!-- Task rows use the drawn checkbox below. If Task controls are disabled, an
active Task Lists / Marker would override the Unordered Lists marker; with no
Task marker declared, the unordered marker is the fallback. -->

### Quotes
Padding top: 6
Padding bottom: 6
Padding left: 8
#### Text
- Font size: 16
#### Muted
- Font color: #5C7468
#### Marker
Bar width: 3
Bar length: 50
Bar color:
- #B8A0DF
- #91B7A4
- #E2BF83
Space: 10
<!--Aside: no-->

### Fixed styles

#### Calm
Background color: #FDFDFD
Corner radius: 30
Padding: 12
Spacing: 12
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

#### Reflection
Background color: #00CC58
Corner radius: 30
Padding: 24
Spacing: 18
Outer shadow:
- Offset y: 12
- Radius: 28
- Color: #26263310
<!-- Fixed styles are already #### blocks, so their local roles are #####. -->
##### Lead
- Font color: #FFFFFF

#### Reset
Background color: #B3F0D1
Corner radius: 20
Padding: 16
Spacing: 10

#### Learning
Background color: #F2F1F5
Corner radius: 20
Padding: 16
Spacing: 10

#### Afternoon
Background color: #18181B
Corner radius: 20
Padding: 16
Spacing: 10

#### Framed
Background color: #FFFFFF
Corner radius: 16
Padding: 12
Image bleed: yes
Stroke width: 1
Stroke color: #D4DFD9
Outer shadow:
- Offset x: 4
- Offset y: 4
- Radius: 0
- Color: #C7DCD0

## Content arrangement

### Bento
Heading level: 2

## Text Styles

<!-- Global/base typography. Text, Muted, Lead, Display, Key, Value, and Text
Overline can be partially overridden by the local role blocks above. -->

Text
- Font Name: Inter 18pt
- Font size: 15
- Font color: #26262B

Heading1
- Font Name: Inter 18pt
- Font size: 38
- Font weight: 600
- Font color: #202025

Heading2
- Font Name: Inter 18pt
- Font size: 18
- Font weight: 600
- Font color: #26262B
- Marker text color: #25845B
- Marker background color: #00000000

Heading2 Overline
- Font size: 13
- Font color: #7C7C84

Heading3
- Font Name: Inter 18pt
- Font size: 17
- Font weight: 600
- Font color: #26262B

Heading4
- Font Name: Inter 18pt
- Font size: 17
- Font weight: 600
- Font color: #26262B

Muted
- Font size: 13
- Font color: #7C7C84

Lead
- Font size: 20
- Font weight: 600
- Font color: #26262B

Display
- Font size: 44
- Font weight: 600
- Font color: #202025

Key
- Font size: 12
- Font color: #7C7C84

Value
- Font size: 20
- Font weight: 600
- Font color: #26262B

Text Overline
- Font size: 12
- Font color: #7C7C84

Links
- Font size: 14
- Font weight: 600
- Font color: #FFFFFF

Links Secondary
- Font color: #26262B

Links Tertiary
- Font color: #7C7C84

Links Quaternary
- Font color: #25845B

Links Text
- Font color: #25845B

Inline Code
- Font Name: Inter 18pt
- Font size: 11
- Font color: #625780

Inline Code Secondary
- Font color: #25845B

Inline Code Tertiary
- Font color: #8B6340

Inline Code Quaternary
- Font color: #FFFFFF

Code Block
- Font Name: IBM Plex Mono
- Font size: 13
- Font color: #5EE117

## Links
Segmented: yes
Fill color: #26262B
Corner radius: 24
Padding top: 10
Padding bottom: 10
Padding left: 18
Padding right: 18
Emoji shape: circle
Disabled fill color: #EEEEF0
Disabled text color: #96969D
Disabled stroke color: #E2E2E7
<!-- Every button variant inherits this Primary shadow and may add more layers. -->
Outer shadow:
- Offset y: 2
- Color: #15151A1F
- Radius: 6

### Secondary
Fill color: #F2F2F3
Stroke width: 1
Stroke color: #E8E8EC

### Tertiary
Fill color: #00000000

### Quaternary
Fill color: #E5F9EE

### Text
Fill color: #00000000
Padding: 6

### Inline
Text color: #25845B
Underline: yes

## Inline Code
Fill color: #EAE5F6
Corner radius: 12
Padding: 5
<!-- The Primary chip's shared gradient is clipped to its rounded background shape. -->
Background gradient:
- Colors:
  - #F2EEF9
  - #DDD4F1
- Parameters:
  - Start: 0, 0
  - End: 0, 1

### Secondary
Fill color: #E7F4EB

### Tertiary
Fill color: #F8ECDD

### Quaternary
Fill color: #25845B

## Code Blocks
Syntax style: monokai
Background color: #002B0A
Corner radius: 12
Padding: 16
Line spacing: 4

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Primary
Shape: circle
Size: 26
Padding: 9
Icon color: #8870C1
Background color: #F0ECF8
<!-- Every badge variant inherits this Primary shadow and may add more; Shape is preserved. -->
Inner shadow:
- Offset y: 1
- Color: #4E3A7424
- Radius: 4

### Secondary
Shape: circle
Size: 24
Padding: 9
Icon color: #B2843D
Background color: #FBF1DE

### Tertiary
Shape: circle
Size: 24
Padding: 9
Icon color: #25845B
Background color: #E5F9EE

### Quaternary
Shape: circle
Size: 24
Padding: 9
Icon color: #FFFFFF
Background color: #25845B

### Text
Color: #8870C1

### Link
Color: #25845B

### Inline
Color: #625780

## Fixed colors
### Emoji
- ☀️ #D7A139
- 🚶 #9170D6

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
Background color: #00CC58

### Ratio Bar Track
Background color: #E5F9EE
Corner radius: 5

### Task controls
Type: checkbox
Size: 20
Padding: 5
Corner radius: 6
Space: 10

### Checked outer
Background color: #DCEEE2
### Checked inner
Background color: #4F9C6B
### Unchecked outer
Background color: #CFCFD6
### Unchecked inner
Background color: #FDFDFD

### Sliders
Style: thick
Axis: horizontal
Length: 320
Thickness: 85
Corner radius: 43
Circle diameter: 28
Drag bar length: 22
Bar thickness: 3

### Slider Track
Background color: #F8C91C

### Slider Bar
Background color: #FFFFFF

### Slider Handle
Background color: #D8D8D8

### Unit Ratios
Style: ring
Show total: no

### Ring
Diameter: 148
Thickness: 12
Background color: #00CC58
- Font size: 28
- Font weight: 600

### Ring Unit
- Font size: 13
- Font color: #7C7C84

### Ring Track
Background color: #E5F9EE

### Key Value Bars
Thickness: 10
Corner radius: 5
Background color: #00CC58
Position: below
Negative color: #E5484D

### Key Value Bar Track
Background color: #E5F9EE
Corner radius: 5

### Dates
Background color: #F0EDF7
Corner radius: 14
Padding: 12
Spacing: 3

### Date Key
- Font size: 11
- Font color: #8870AD
### Date Day
- Font size: 28
- Font weight: 600
- Font color: #26262B

## Charts
Bar thickness: 18
Bar spacing: 9
Corner radius: 5
Background color: #00CC58
Negative color: #E5484D
Value format: 1 unit

### Chart Track
Background color: #E5F9EE
Corner radius: 5

### Chart Labels
- Font size: 12
- Font color: #7C7C84

### Chart Values
- Font size: 11
- Font color: #25845B

### Chart Grid
Axis labels: yes
Ticks: 4
Horizontal lines: yes
Vertical lines: yes
Line color: #D9E6DE
Line width: 1
Line dash: 4 3
- Font size: 11
- Font color: #7C7C84

### Chart Series Colors
- #00CC58
- #F2A93B
- #3E7BFA
- #E5484D
- #8870AD
- #26262B

### Line Chart
Height: 56
Group height: 112
Line width: 2
Line color: #25845B
Point size: 6

## Tables

### Table
Merge rows: yes
Background color: #FDFDFD
Corner radius: 16
Row spacing: 8
Col spacing: 6
Stacking cards: yes
Card layout: title

### Header
Background color: #E5F9EE
Padding: 8
- Font name: Inter 18pt
- Font size: 12
- Font weight: 600
- Font color: #25845B

### Cells
Background colors:
- #FDFDFD
- #F4F6F5
Corner radius: 12
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
<!-- Solid green panels: text flips to white; primary buttons become white.
The button's resolved white fill then selects its own label rule below. -->
On background color: #00CC58
- Replacement: #FFFFFF
- Fill color: #26262B, Replacement: #FFFFFF

On background color: #FFFFFF
- Text color: #FFFFFF, Replacement: #00CC58

<!-- The mint card inside Make room establishes its own context. Its prose
uses dark green, while a primary button becomes green with a white label. -->
On background color: #B3F0D1
- Replacement: #234B3A
- Fill color: #26262B, Replacement: #00CC58

On background color: #26262B
- Text color: #25845B, Replacement: #FFFFFF

On background color: #18181B
- Replacement: #FFFFFF

<!-- Marker colors use their semantic channel on the surface behind them:
shapes/bars are Fill; ordinals, quote characters and emoji markers are Text. -->
On background color: #FDFDFD
- Fill color: #91B7A4, Replacement: #25845B
- Fill color: #B8A0DF, Replacement: #7B5AAF
- Text color: #B8A0DF, Replacement: #6C4AA5
- Text color: #25845B, Replacement: #15633F

On background color: #F2F1F5
- Fill color: #91B7A4, Replacement: #25845B
- Text color: #91B7A4, Replacement: #25845B
- Text color: #25845B, Replacement: #15633F

On background color: image
- Replacement: #FFFFFF

## Images

### Placeholders

#### Avatar
Fill color:
- #E8F0FE
- #FDE7E9
- #E6F4EA
Text color:
- #1A56DB
- #C81E1E
- #057A55
Text style: Lead
Text size: 40%

#### Brand
Fill color: #111111
Text color: #FFFFFF
Text style: Display
Text size: 32%

#### Media
Fill color: #F2F2F2
Text color: #8A8A8A
Icon: 🖼️
Icon size: 30%
