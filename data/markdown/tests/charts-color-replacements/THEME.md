# Graphic color-replacement gallery

## Background styles and Spacing

### Root
Background color: #ECECEF
Padding: 36
Spacing: 18
Max width: 1180
Centered: yes

### Elements
Row spacing: 10
Col spacing: 10
Group spacing: 14

### Heading 2
Background color: #1C1C1C
Corner radius: 20
Padding: 22
Spacing: 14

### Heading 3
Background color: #FFFFFF
Corner radius: 20
Padding: 22
Spacing: 14

## Text Styles

Text
- Font size: 15
- Font color: #1C1C1C

Heading1
- Font size: 34
- Font weight: bold
- Font color: #1C1C1C

Heading2
- Font size: 20
- Font weight: bold
- Font color: #1C1C1C

Heading3
- Font size: 20
- Font weight: bold
- Font color: #1C1C1C

Labels
- Font size: 12
- Font color: #FFFFFF

## Datapoints

### Ratio Bars
Enabled: yes
Thickness: 12
Text side: right
Corner radius: 6
Background color: #101010
Stroke width: 2
Stroke color: #181818

### Ratio Bar Track
Background color: #202020
Corner radius: 6

### Unit Ratios
Enabled: yes
Style: ring
Show total: no
Show key: yes

### Ring
Thickness: 8
Diameter: 112
Background color: #111111
- Font size: 24
- Font weight: bold
- Font color: #1C1C1C

### Ring Unit
- Font size: 12
- Font color: #1C1C1C

### Ring Track
Background color: #212121

### Dates
Enabled: yes
Fill: split
Corner radius: 14
Padding: 10
Background color: #121212
Stroke width: 2
Stroke color: #191919

### Date Key
Background color: #131313
Padding top: 7
Padding bottom: 7
- Font size: 11
- Font weight: semibold
- Font color: #1C1C1C

### Date Day
Background color: #141414
Padding top: 9
Padding bottom: 9
- Font size: 22
- Font weight: bold
- Font color: #1C1C1C

## Charts
Enabled: yes
Bar thickness: 16
Bar spacing: 8
Corner radius: 8
Background color: #151515
Stroke width: 2
Stroke color: #1A1A1A

### Chart Track
Background color: #222222

### Chart Series Colors
- #151515
- #161616

### Chart Labels
- Font size: 12
- Font color: #1C1C1C

### Chart Values
- Font size: 12
- Font weight: semibold
- Font color: #1C1C1C

## Color Replacements

<!-- All source colors below are intentionally close to the #1C1C1C card.
     The same global section serves every supported graphic painter. -->
On background color: #1C1C1C
- Replacement: #FFFFFF
- Fill color: #101010, Replacement: #FF4A1C
- Fill color: #202020, Replacement: #4A4A4E
- Stroke color: #181818, Replacement: #FFB39F
- Fill color: #111111, Replacement: #CFF33B
- Fill color: #212121, Replacement: #454549
- Fill color: #121212, Replacement: #2C2C2E
- Stroke color: #191919, Replacement: #66666C
- Fill color: #131313, Replacement: #A99FFF
- Fill color: #141414, Replacement: #FFFFFF
- Fill color: #151515, Replacement: #22C55E
- Fill color: #161616, Replacement: #60A5FA
- Fill color: #222222, Replacement: #3A3A3C
- Stroke color: #1A1A1A, Replacement: #86EFAC

<!-- The date base resolves from #121212 to #2C2C2E on the dark card. That
     painted base is then the nearest context for its split regions, so their
     fill replacements belong here rather than on the enclosing card. -->
On background color: #2C2C2E
- Fill color: #131313, Replacement: #A99FFF
- Fill color: #141414, Replacement: #FFFFFF

<!-- On white cards the same date base resolves from #121212 to #F4F4F5. -->
On background color: #F4F4F5
- Fill color: #131313, Replacement: #A99FFF
- Fill color: #141414, Replacement: #FFFFFF

<!-- The resolved split regions become the text backgrounds. -->
On background color: #A99FFF
- Text color: #1C1C1C, Replacement: #1C1C1C

On background color: #FFFFFF
- Text color: #1C1C1C, Replacement: #1C1C1C
- Fill color: #101010, Replacement: #FF4A1C
- Fill color: #202020, Replacement: #D4D4D8
- Stroke color: #181818, Replacement: #C93412
- Fill color: #111111, Replacement: #9FC500
- Fill color: #212121, Replacement: #D4D4D8
- Fill color: #121212, Replacement: #F4F4F5
- Stroke color: #191919, Replacement: #A1A1AA
- Fill color: #131313, Replacement: #A99FFF
- Fill color: #141414, Replacement: #FFFFFF
- Fill color: #151515, Replacement: #16A34A
- Fill color: #161616, Replacement: #3B82F6
- Fill color: #222222, Replacement: #E4E4E7
- Stroke color: #1A1A1A, Replacement: #15803D
