<!--
A floor below the default (2026-11-08).

An authored `min_width` replaces the default image floor (96px) instead of only
raising it. The 110-character chip leaves the picture about 82px at 767px, so
with `min_width=80` the picture stays beside the chip there. Before the fix the
row stacked at 767px, since the fit test read a floor below 96 as 96; with no
floor written it still stacks (tests/image_min_width_tests.py). The window is
two characters wide (109-110), the 16px between the two floors. At 1280px the
row holds either way, and the picture is narrower after the fix: with room to
spare, the lower floor also gives the picture a smaller part of the row.
The picture is a local path, so it draws the placeholder and only its box
matters.
-->

![Photo](photo.jpg?md2ui.min_width=80)
:::
`xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
