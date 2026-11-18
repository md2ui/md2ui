# Calendar app

<!-- Reference: calendar-com-calendar-app-design.png. White panels on a pale grey canvas,
Open Sans, a periwinkle accent (#5B7FDB), one tint per calendar.

Chips, as this page uses them:
  `x`      a day number (month grid, week header)
  __`x`__  Work            green           _`x`_    Crossfit Schedule  red
  *`x`*    Sales Meetings  yellow          ***`x`*** Family Events  a dot and text
  **`x`**  Personal        blue            ___`x`___ the selected day
An event chip's calendar colour is a 4px bar on its left edge (an inner shadow). -->

## Fonts
- assets/fonts/OpenSans-Regular.ttf
- assets/fonts/OpenSans-Medium.ttf
- assets/fonts/OpenSans-SemiBold.ttf
- assets/fonts/OpenSans-Bold.ttf

## Styling & Spacing

### Root
Background color: #F3F4F7
Padding: 32
Spacing: 24
Max width: 1440
Stack sections: yes

### Heading 2
Background color: #FFFFFF
Corner radius: 12
Padding: 24
Spacing: 20
Outer shadow:
- Offset y: 2
- Radius: 8
- Color: #1F2A4410

### Heading 3
Padding: 0
Spacing: 12

### Elements
Row spacing: 8
Col spacing: 8
Group row spacing: 16
Group col spacing: 16

### Task Lists
Padding top: 4
Padding bottom: 4

<!-- The agenda rows: a tint and a bar per calendar, in the order the day's events come. -->
### Quotes
Background colors:
- #F1EAFB
- #FCE4E8
- #FDF0CF
- #E6F4D9
- #DDF0FA
Stroke width: 1
Stroke colors:
- #C9B4EE
- #F3B4BE
- #F5D58B
- #BFE1A1
- #A6DAF2
Corner radius: 4
Padding: 12
#### Marker
Bar width: 5
Bar colors:
- #A57FE0
- #EF5A6F
- #F7C95C
- #8CC63F
- #1EA7E1
Space: 10

## Text Styles

Text
- Font Name: Open Sans
- Font size: 13
- Font color: #3B3F4A

Heading2
- Font Name: Open Sans
- Font size: 22
- Font weight: 400
- Font color: #2B2E36

Heading3
- Font Name: Open Sans
- Font size: 11
- Font weight: 700
- Font color: #3B3F4A

Muted
- Font Name: Open Sans
- Font size: 11
- Font color: #9A9EA8

Lead
- Font Name: Open Sans
- Font size: 15
- Font weight: 600

Links Secondary
- Font Name: Open Sans
- Font size: 13
- Font color: #6B7080

Links
- Font Name: Open Sans
- Font size: 18
- Font color: #FFFFFF

Links Text
- Font Name: Open Sans
- Font size: 11
- Font weight: 700
- Font color: #3B3F4A

Inline Code
- Font Name: Open Sans
- Font size: 12
- Font weight: 600
- Font color: #3B3F4A


Inline Code Septenary
- Font size: 12
- Font weight: 700
- Font color: #FFFFFF

## Links
<!-- Bare: the round add button. *x*: the quiet arrows. -->
Corner radius: 20
Padding: 8
Fill color: #5B7FDB
Emoji shape: circle

### Secondary
Fill color: #00000000
Padding: 4

### Text
Fill color: #00000000
Padding: 4

## Inline Code
<!-- Plain: a day number. The event chips carry their calendar's bar on the left edge,
an inner shadow; it is stated per variant, since variant shadows only add to Primary's. -->
Corner radius: 2
Padding: 6
Fill color: #00000000
Disabled fill color: #00000000
Disabled text color: #C2C5CC

### Secondary
Corner radius: 3
Padding top: 6
Padding bottom: 6
Padding left: 12
Padding right: 10
Fill color: #FDF0CF
Inner shadow:
- Offset x: 4
- Offset y: 0
- Radius: 0
- Color: #F7C95C

### Tertiary
Corner radius: 3
Padding top: 6
Padding bottom: 6
Padding left: 12
Padding right: 10
Fill color: #DDF0FA
Disabled fill color: #FFFFFF
Disabled text color: #8A8F99
Disabled stroke color: #1EA7E1
Stroke width: 1
Stroke color: #00000000
Inner shadow:
- Offset x: 4
- Offset y: 0
- Radius: 0
- Color: #1EA7E1

### Quaternary
Padding left: 2
Fill color: #00000000

### Quinary
Corner radius: 3
Padding top: 6
Padding bottom: 6
Padding left: 12
Padding right: 10
Fill color: #FCE4E8
Inner shadow:
- Offset x: 4
- Offset y: 0
- Radius: 0
- Color: #EF5A6F

### Senary
Corner radius: 3
Padding top: 6
Padding bottom: 6
Padding left: 12
Padding right: 10
Fill color: #E6F4D9
Inner shadow:
- Offset x: 4
- Offset y: 0
- Radius: 0
- Color: #8CC63F

### Septenary
Fill color: #5B7FDB

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

## Fixed colors

### Emoji
- 🟣 #A57FE0

## Separators
Dash: hide
Bullet: show

## Drawing elements

### Task controls
Type: checkbox
Size: 18
Padding: 3
Corner radius: 3
Space: 10

### Checked outer
Background colors:
- #8CC63F
- #F7C95C
- #1EA7E1
- #A57FE0
- #EF5A6F
### Checked inner
Background color: #FFFFFF00
### Unchecked outer
Background color: #A57FE0
### Unchecked inner
Background color: #FFFFFF

## Tables

### Table
Merge rows: yes
Background color: #FFFFFF
Corner radius: 0
Row spacing: 0
Col spacing: 0
Stacking cards: yes
Card layout: title

### Header
Background color: #FFFFFF
Padding: 10
- Font name: Open Sans
- Font size: 10
- Font weight: 700
- Font color: #6B7080

### Cells
Background color: #FFFFFF
Stroke width: 1
Stroke color: #ECEDF1
Padding: 8
- Font name: Open Sans
- Font size: 12
- Font color: #3B3F4A

### Card Keys
Key spacing: 6
- Font name: Open Sans
- Font size: 10
- Font color: #9A9EA8
