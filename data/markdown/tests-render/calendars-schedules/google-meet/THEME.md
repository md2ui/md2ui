# Google Meet home

<!-- Reproduces the Meet home screen with no meetings (compare at
     --width 1456 --scale 2). Material 3 on white, in Google Sans: tonal pills
     (a green New, blue secondary containers), a left rail whose selected entry sits
     in a blue pill, a week strip as a token grid with the day selected, a blue
     notice banner, a centred empty state, and a light-blue notification card. -->

## Fonts
- assets/fonts/GoogleSans-Regular.ttf
- assets/fonts/GoogleSans-Medium.ttf
- assets/fonts/GoogleSans-SemiBold.ttf

## Styling & Spacing

### Root
Background color: #FFFFFF
Padding: 24
Padding top: 12
Max width: 1456
Spacing: 18

### Elements
Row spacing: 12
Col spacing: 4
Group spacing: 16

### Heading 2
Padding: 0
Spacing: 8

### Heading 3
Padding: 0
Spacing: 8

### Fixed styles

#### Page
<!-- The rail and the main column, side by side. -->
Padding: 0
Padding top: 16
Spacing: 18

#### Main
Padding: 0
Padding left: 40
Spacing: 18

#### Notice
<!-- "Your meeting is safe". -->
Background color: #D3E3FD
Corner radius: 28
Padding top: 16
Padding bottom: 16
Padding left: 32
Padding right: 16
Vertical align: center

#### Toast
<!-- The notification card. -->
Background color: #C2E7FF
Corner radius: 24
Padding top: 20
Padding bottom: 20
Padding left: 28
Padding right: 20
Vertical align: center
Outer shadow:
- Offset y: 4
- Color: #00000026
- Radius: 12

## Text Styles

Text
- Font Name: Google Sans
- Font size: 15
- Font weight: 400
- Font color: #1F1F1F

Lead
- Font size: 26
- Font weight: 400
- Font color: #1F1F1F

Display
- Font size: 30
- Font weight: 400
- Font color: #1F1F1F

Links
- Font Name: Google Sans
- Font size: 15
- Font weight: 500
- Font color: #0F5223

Links Secondary
- Font size: 15
- Font weight: 500
- Font color: #0B57D0

Links Tertiary
- Font size: 15
- Font weight: 500
- Font color: #FFFFFF

Links Quinary
- Font size: 22
- Font color: #444746

Links Senary
- Font size: 15
- Font weight: 500
- Font color: #1F1F1F

Links Septenary
- Font size: 15
- Font weight: 500
- Font color: #8E918F

Links Text
- Font Name: Google Sans
- Font size: 15
- Font weight: 500
- Font color: #0B57D0

Inline Code
- Font Name: Google Sans
- Font size: 16
- Font weight: 400
- Font color: #1F1F1F

Inline Code Secondary
- Font size: 17
- Font color: #444746

Inline Code Tertiary
- Font color: #041E49

## Links

### Primary
<!-- New: the green tonal button. -->
Fill color: #C4EED0
Corner radius: 24
Padding top: 13
Padding bottom: 13
Padding left: 20
Padding right: 22
Emoji gap: 10
Stroke width: 0

### Secondary
<!-- In-person notes, Upgrade: blue tonal pills. -->
Fill color: #D3E3FD
Corner radius: 24
Padding top: 13
Padding bottom: 13
Padding left: 22
Padding right: 22
Emoji gap: 10

### Tertiary
<!-- Allow notifications: the filled button, with its focus ring. -->
Fill color: #0B57D0
Corner radius: 24
Padding top: 10
Padding bottom: 10
Padding left: 24
Padding right: 24
Stroke width: 3
Stroke color: #FFFFFF
Outer shadow:
- Color: #1F4E8AFF
- Radius: 0
- Spread: 3

### Quinary
<!-- Icon buttons: help, settings, apps, the week arrows. -->
Fill color: #00000000
Padding: 6
Emoji shape: circle

### Senary
<!-- Learn more: the outlined pill. -->
Fill color: #00000000
Stroke width: 1
Stroke color: #747775
Corner radius: 20
Padding top: 8
Padding bottom: 8
Padding left: 16
Padding right: 16

### Septenary
<!-- Join, disabled until a code is typed. -->
Fill color: #1F1F1F14
Corner radius: 24
Padding top: 13
Padding bottom: 13
Padding left: 22
Padding right: 22

### Text
Padding: 6

## Inline Code
<!-- A day number: no surface of its own. -->
Fill color: #00000000
Corner radius: 24
Padding top: 4
Padding bottom: 4
Padding left: 10
Padding right: 10

### Tertiary
<!-- The selected day. -->
Fill color: #C2E7FF

### Secondary
<!-- The code field: a wide grey pill. -->
Fill color: #E9EEF6
Corner radius: 28
Padding top: 14
Padding bottom: 14
Padding left: 22
Padding right: 150

## Tables

### Table
Merge rows: yes
Background color: #00000000
Stacking cards: no

### Header
Background color: #00000000
Padding: 6
- Font name: Google Sans
- Font size: 12
- Font weight: 500
- Font color: #444746

### Cells
Background color: #00000000
Padding: 2

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf

### Primary
Icon size: 26
Padding: 0
Icon color: #444746
Background color: #00000000

### Secondary
<!-- The selected rail entry: its icon in a blue pill. -->
Icon size: 24
Padding top: 6
Padding bottom: 6
Padding left: 20
Padding right: 20
Corner radius: 16
Background color: #C2E7FF
Icon color: #041E49

### Text
Color: #444746

### Link
Color: #444746

## Fixed colors

### Emoji
- 🎥 #FBBC04
- 🛡️ #4285F4
- 📹 #0F5223
- 🎙️ #0B57D0

## Separators
Dash: hide
Pipe: hide

## Images

### Placeholders

#### Avatar
Fill color: #5F6368
Text color: #FFFFFF
Text style: Text

#### Illustration
Fill color: #FFFFFF
Text color: #C4C7C5
Icon: ☕
Icon size: 40%
