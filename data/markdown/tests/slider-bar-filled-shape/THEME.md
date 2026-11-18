# Slider bar filled shape

<!-- The bar's stroke and shadows follow the filled shape, not the full track
(owner decision 2026-10-05). They were once drawn around the whole track and
cut square at the value, leaving the outline open there. -->

## Fonts
- assets/fonts/Inter_18pt-Regular.ttf

## Styling & Spacing

### Root
Background color: #FFFFFF
Padding: 40

## Drawing elements

### Sliders
Enabled: yes
Style: thick
Length: 300
Thickness: 40

### Slider Track
Background color: #DDDDDD

### Slider Bar
Background color: #3366FF
Stroke width: 3
Stroke color: #FF0000
Stroke align: outside
Outer shadow:
- Color: #66000000
- Radius: 6
- Offset x: 4
- Offset y: 4
Inner shadow:
- Color: #66FFFFFF
- Radius: 4
- Offset x: 2
- Offset y: 2
