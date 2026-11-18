<!-- Image placeholders with images, and the theme's own defaults (ADR-406). THEME.md
beside this file adds a `#### Pattern` placeholder with an `Image:`, and `#### Missing`
and `#### Broken`, the reserved names that restyle the defaults. Expected: the left-out picture with no name draws the Missing default (cream fill,
picture icon); the failing URL with no name the Broken default (pink fill, warning icon);
the named Pattern placeholder its image cover-fitted over its fill, with "AB" on top; the
avatar its declared look, unchanged by the defaults. -->

## Defaults

### Left out
![Product photo]()
No source, no name: the theme's Missing look.

### Failed URL
![Product photo](https://placeholder.invalid/p/7.jpg)
A URL that fails, no name: the theme's Broken look.

## Named

### Pattern
![Acme Bank](?md2ui.placeholder=pattern:AB)
A placeholder with an image under its text.

### Avatar
![Sara Zane](?md2ui.placeholder=avatar:SZ)
A named placeholder outranks the defaults.
