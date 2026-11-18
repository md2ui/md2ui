<!-- Every button and icon-button variant, one per wrapper. `*` `**` `***` are
     the asterisk ladder (Secondary, Tertiary, Quaternary); `_` `__` `___` are
     the small ladder (Quinary, Senary, Septenary), as chips have it (ADR-501).
     Before 2026-10-08 `_` was a synonym of `*`, so each underscore row drew
     exactly like the asterisk row above it.

     This corpus's THEME.md has no `### Quinary`, `### Senary` or
     `### Septenary` block under `## Links`, so the three small variants draw
     as Primary: the dark filled button, not Secondary's light one. That is the
     expected render; a theme that declares the blocks sizes them. -->

[Primary](/x) *[Secondary](/x)* **[Tertiary](/x)** ***[Quaternary](/x)***

_[Quinary](/x)_ __[Senary](/x)__ ___[Septenary](/x)___ [`Text`](/x)

<!-- The muted state composes with the small ladder as with the others. -->
~~[Primary](/x)~~ ~~*[Secondary](/x)*~~ ~~_[Quinary](/x)_~~ ~~___[Septenary](/x)___~~

<!-- Icon buttons take the same wrappers. -->
[⭐](/x) *[⭐](/x)* **[⭐](/x)** ***[⭐](/x)***

_[⭐](/x)_ __[⭐](/x)__ ___[⭐](/x)___

<!-- An emoji badge is not a button: `_⭐_` stays a synonym of `*⭐*`. -->
*⭐* _⭐_
