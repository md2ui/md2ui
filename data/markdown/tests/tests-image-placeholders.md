<!-- Named image placeholders (ADR-406). Each picture names a placeholder that
data/markdown/tests/THEME.md declares under ## Images → ### Placeholders, and has no
picture to show: its source left out, or a URL that fails. Expected: avatars draw
initials (and one emoji) in a circle; the brand card its own black fill and white
text; the media box its declared icon; the failed URL its avatar, not the broken
placeholder; the undeclared name today's quiet grey box. -->

## Team

- ![Sara Zane](?md2ui.placeholder=avatar:SZ&md2ui.shape=circle&md2ui.max_width=48) - **Sara Zane** : _Design lead_
- ![Ravi Kumar](?md2ui.placeholder=avatar:RK&md2ui.shape=circle&md2ui.max_width=48) - **Ravi Kumar** : _Engineering_
- ![Guest](?md2ui.placeholder=avatar:👤&md2ui.shape=circle&md2ui.max_width=48) - **Guest** : _No profile yet_

## Partners

### Acme
![Acme Corp](?md2ui.placeholder=brand:AC&md2ui.aspect_ratio=16:9)
Building materials since 1952.

### Product photo
![Product photo](?md2ui.placeholder=media&md2ui.aspect_ratio=16:9)
Coming soon.

### Failed URL
![Sara Zane](https://placeholder.invalid/u/42.jpg?md2ui.placeholder=avatar:SZ&md2ui.aspect_ratio=16:9)
A URL that fails keeps its placeholder.

### Undeclared name
![Sara Zane](?md2ui.placeholder=nobody:SZ&md2ui.aspect_ratio=16:9)
An undeclared name keeps the quiet box.
