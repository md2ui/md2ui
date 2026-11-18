# Clay

<!-- Claymorphism, after a clay music dashboard design.

     Every clay surface (the panel, cards, tiles, buttons, chips, badges and chart
     bars) takes the same five shadows (the limit is four per kind), in this order:
       outer  a soft violet drop, down and to the left     (x -5, y 5, r 15, 18%)
       inner  a soft white glow on the top and right       (x -3, y 3, r 5)
       inner  a tight, bright white rim on the same edges  (x -2, y 2, r 2)
       inner  a faint neutral shade on the left and bottom (x 6, y -6, r 8, 4% black)
       inner  a tight neutral rim on the same edges        (x 3, y -3, r 2, 8% black)
     The shades are black at low opacity rather than a tint, so one recipe sits on
     every fill: the white panel, the pastel tiles and the violet buttons alike.
     An inner shadow shows on the edges its offset points away from: +x the left,
     -x the right, +y the top, -y the bottom.

     Palette read off the reference:
       #CDB9EC  page              #F8F2F5  the dashboard panel
       #FCF8F9  cards             #3A2C5C  headings and figures    type: Nunito, the reference's rounded sans
       #8B7FA3  captions          #9C7BEA  the violet of buttons and banners
       tiles   #EADFFA #FCDDDD #FCEDCB #DDE6F8   (lavender, pink, butter, sky)
       badges  #A98BF0 #F27F86 #F4B848 #6F9BEA -->

## Background styles and Spacing

### Root
Background color: #CDB9EC
Padding: 28
Spacing: 0

### Elements
Row spacing: 8
Col spacing: 4
Group spacing: 14
Image distance: 14
Padding: 0

### Heading 1
<!-- The dashboard panel itself. -->
Background color: #F8F2F5
Corner radius: 34
Padding: 26
Padding top: 22
Spacing: 18
Row spacing: 18
Col spacing: 18
Outer shadow:
- Offset y: 5
- Offset x: -5
- Color: #8E6CC92E
- Radius: 15
Inner shadow:
- Offset x: -3
- Offset y: 3
- Color: #FFFFFFA0
- Radius: 5
Inner shadow:
- Offset x: -2
- Offset y: 2
- Color: #FFFFFFD9
- Radius: 2
Inner shadow:
- Offset x: 6
- Offset y: -6
- Color: #0000000A
- Radius: 8
Inner shadow:
- Offset x: 3
- Offset y: -3
- Color: #00000014
- Radius: 2

### Heading 2
<!-- The cards. -->
Background color: #FCF8F9
Corner radius: 22
Image corner radius: 10
Padding: 18
Spacing: 12
Row spacing: 18
Col spacing: 14
Outer shadow:
- Offset y: 5
- Offset x: -5
- Color: #8E6CC92E
- Radius: 15
Inner shadow:
- Offset x: -3
- Offset y: 3
- Color: #FFFFFFA0
- Radius: 5
Inner shadow:
- Offset x: -2
- Offset y: 2
- Color: #FFFFFFD9
- Radius: 2
Inner shadow:
- Offset x: 6
- Offset y: -6
- Color: #0000000A
- Radius: 8
Inner shadow:
- Offset x: 3
- Offset y: -3
- Color: #00000014
- Radius: 2

### Heading 3
<!-- The four stat tiles: one pastel each, and their badges follow (sync). -->
Background colors:
- #EADFFA
- #FCDDDD
- #FCEDCB
- #DDE6F8
Rotate colors: sync
Corner radius: 20
Padding: 16
Spacing: 6
Outer shadow:
- Offset y: 5
- Offset x: -5
- Color: #8E6CC92E
- Radius: 15
Inner shadow:
- Offset x: -3
- Offset y: 3
- Color: #FFFFFFA0
- Radius: 5
Inner shadow:
- Offset x: -2
- Offset y: 2
- Color: #FFFFFFD9
- Radius: 2
Inner shadow:
- Offset x: 6
- Offset y: -6
- Color: #0000000A
- Radius: 8
Inner shadow:
- Offset x: 3
- Offset y: -3
- Color: #00000014
- Radius: 2

### Unordered Lists
<!-- Top Genres: each row's dot deals the next genre colour. -->
#### Marker
Shape: circle
Size: 10
Space: 12
Alignment: center
Color:
- #A98BF0
- #F27FA3
- #F5C04A
- #93C77A
- #6F9BEA

### Fixed styles

#### Hero
<!-- "Good Morning, Mia!": a lavender clay slab. It keeps Heading 2's shadows
     (override); the drop is stated here too so it stays the cards' drop. -->
Mode: override
Outer shadow:
- Offset y: 5
- Offset x: -5
- Color: #8E6CC92E
- Radius: 15
Background gradient:
- Colors:
  - #DCCBF6
  - #C8B2EF
Padding: 0
Padding right: 26
Vertical align: center
Image corner radius: 22

#### Mix cover
<!-- Daily Mix: the room photo as the card's surface, the name and button over it. -->
Background image: https://images.unsplash.com/photo-1656848221842-974d8be992ca?w=900&q=80&fm=jpg&fit=crop
Corner radius: 16
Padding: 14
##### Text
- Font color: #FFFFFF
- Font size: 15
- Font weight: 600
##### Muted
- Font color: #F3EDFF

#### Tiles
<!-- The row of stat tiles sits straight on the panel: no card of its own. -->
Background color: #00000000
Padding: 0
Col spacing: 14
Row spacing: 14

#### Banner
<!-- "Discover new music": the violet clay strip at the bottom. -->
Mode: override
Background gradient:
- Colors:
  - #B79BF0
  - #A084E8
Padding: 14
Padding left: 22
Padding right: 22
##### Lead
- Font color: #FFFFFF
- Font size: 19
##### Muted
- Font color: #F3EDFF

## Text Styles

Heading1
- Font Name: nunito
- Font size: 26
- Font weight: 800
- Font color: #3A2C5C

Heading2
- Font Name: nunito
- Font size: 15
- Font weight: 800
- Font color: #3A2C5C

Text
- Font Name: nunito
- Font size: 13
- Font weight: 600
- Font color: #4A3D6B

Muted
- Font Name: nunito
- Font size: 12
- Font weight: 600
- Font color: #8B7FA3

Lead
- Font Name: nunito
- Font size: 23
- Font weight: 800
- Font color: #3A2C5C

Display
- Font Name: nunito
- Font size: 21
- Font weight: 800
- Font color: #3A2C5C

Inline Code
- Font Name: nunito
- Font size: 10
- Font weight: 700
- Font color: #4A3D6B

Links
- Font Name: nunito
- Font size: 14
- Font weight: 700
- Font color: #FFFFFF

Links Secondary
- Font Name: nunito
- Font size: 14
- Font weight: 700
- Font color: #8F6FE6

## Links

### Primary
<!-- A darker fill: its two white rims at half the opacity of the light surfaces'. -->
<!-- "Play Something", "Explore Now": violet clay pills. -->
Corner radius: 20
Fill color: #9C7BEA
Padding top: 9
Padding bottom: 9
Padding left: 20
Padding right: 20
Outer shadow:
- Offset y: 5
- Offset x: -5
- Color: #8E6CC92E
- Radius: 15
Inner shadow:
- Offset x: -3
- Offset y: 3
- Color: #FFFFFF50
- Radius: 5
Inner shadow:
- Offset x: -2
- Offset y: 2
- Color: #FFFFFF6C
- Radius: 2
Inner shadow:
- Offset x: 6
- Offset y: -6
- Color: #0000000A
- Radius: 8
Inner shadow:
- Offset x: 3
- Offset y: -3
- Color: #00000014
- Radius: 2

### Secondary
<!-- The bell and the play buttons: white clay circles, violet glyph. -->
Fill color: #FFFFFF
Emoji shape: circle
Padding: 9
Outer shadow:
- Offset y: 5
- Offset x: -5
- Color: #8E6CC92E
- Radius: 15
Inner shadow:
- Offset x: -3
- Offset y: 3
- Color: #FFFFFFA0
- Radius: 5
Inner shadow:
- Offset x: -2
- Offset y: 2
- Color: #FFFFFFD9
- Radius: 2
Inner shadow:
- Offset x: 6
- Offset y: -6
- Color: #0000000A
- Radius: 8
Inner shadow:
- Offset x: 3
- Offset y: -3
- Color: #00000014
- Radius: 2

### Tertiary
<!-- A darker fill: its two white rims at half the opacity of the light surfaces'. -->
<!-- The profile button: a violet clay circle, white glyph. -->
Fill color: #9C7BEA
Emoji shape: circle
Padding: 9
Outer shadow:
- Offset y: 5
- Offset x: -5
- Color: #8E6CC92E
- Radius: 15
Inner shadow:
- Offset x: -3
- Offset y: 3
- Color: #FFFFFF50
- Radius: 5
Inner shadow:
- Offset x: -2
- Offset y: 2
- Color: #FFFFFF6C
- Radius: 2
Inner shadow:
- Offset x: 6
- Offset y: -6
- Color: #0000000A
- Radius: 8
Inner shadow:
- Offset x: 3
- Offset y: -3
- Color: #00000014
- Radius: 2

## Inline Code
<!-- `This Week 🔽`, `See All`: small white clay chips. -->
Corner radius: 10
Padding top: 4
Padding bottom: 4
Padding left: 9
Padding right: 9
Fill color: #FFFFFF
Stroke width: 1
Stroke color: #EEE4F0
Outer shadow:
- Offset y: 5
- Offset x: -5
- Color: #8E6CC92E
- Radius: 15
Inner shadow:
- Offset x: -3
- Offset y: 3
- Color: #FFFFFFA0
- Radius: 5
Inner shadow:
- Offset x: -2
- Offset y: 2
- Color: #FFFFFFD9
- Radius: 2
Inner shadow:
- Offset x: 6
- Offset y: -6
- Color: #0000000A
- Radius: 8
Inner shadow:
- Offset x: 3
- Offset y: -3
- Color: #00000014
- Radius: 2

## Fixed colors

### Emoji
- ☀️ #F2B33D
- ✨ #F2B33D

### Datapoints
- change up: #3E9A57

## Separators
Dash: hide
Bullet: hide
Bar: hide

## Horizontal Rule
Stroke color: #EFE4EE
Stroke width: 1

## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf
Emoji fill: 1

### Primary
<!-- A darker fill: its two white rims at half the opacity of the light surfaces'. -->
<!-- The tile badges: a square clay chip per tile, its colour synced to the tile. -->
Icon size: 20
Padding: 9
Shape: square
Corner radius: 10
Background colors:
- #A98BF0
- #F27F86
- #F4B848
- #6F9BEA
Icon color: #FFFFFF
Outer shadow:
- Offset y: 5
- Offset x: -5
- Color: #8E6CC92E
- Radius: 15
Inner shadow:
- Offset x: -3
- Offset y: 3
- Color: #FFFFFF50
- Radius: 5
Inner shadow:
- Offset x: -2
- Offset y: 2
- Color: #FFFFFF6C
- Radius: 2
Inner shadow:
- Offset x: 6
- Offset y: -6
- Color: #0000000A
- Radius: 8
Inner shadow:
- Offset x: 3
- Offset y: -3
- Color: #00000014
- Radius: 2

### Text
Color: #F2B33D

## Datapoints

### Emphasis
Enabled: yes

## Charts
Enabled: yes
Value format: 1unit
Bar thickness: 24
Corner radius: 10
<!-- One pastel per day, as the reference. A one-series chart draws only the first
     (see content.md): the list is kept as the test of it. -->
Background color:
- #B9A2EE
- #F4A6B8
- #F6AE6B
- #F7D27A
- #A9D58F
- #8FB8EE
- #B39DE8
<!-- The bars are violet clay like the Primary pills, so they take the pills' two rims. -->
Outer shadow:
- Offset y: 5
- Offset x: -5
- Color: #8E6CC92E
- Radius: 15
Inner shadow:
- Offset x: -3
- Offset y: 3
- Color: #FFFFFFA0
- Radius: 5
Inner shadow:
- Offset x: -2
- Offset y: 2
- Color: #FFFFFFD9
- Radius: 2
Inner shadow:
- Offset x: 6
- Offset y: -6
- Color: #0000000A
- Radius: 8
Inner shadow:
- Offset x: 3
- Offset y: -3
- Color: #00000014
- Radius: 2

### Chart Grid
Axis labels: yes
Ticks: 3
- Font size: 9
- Font color: #6E6487

### Chart Labels
- Font size: 9
- Font color: #6E6487

### Chart Values
- Font size: 1
- Font color: #00000000

## Fonts
- assets/fonts/Nunito-Regular.ttf
- assets/fonts/Nunito-SemiBold.ttf
- assets/fonts/Nunito-Bold.ttf
- assets/fonts/Nunito-ExtraBold.ttf
