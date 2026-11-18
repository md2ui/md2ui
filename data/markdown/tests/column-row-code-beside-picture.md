<!-- A code block is a surface, not an element: in a `:::` row a `:::0` picture
     keeps its width beside it, and a line wider than the code block clips and
     scrolls (2026-11-12, findings/code-block-floor-measured-as-body-text).
     Before, the code's longest word, measured as body text, took room from the
     picture: 384 -> 269 px at 767. Its twin `-wide` shows it at 1280. -->
![Terminal](https://example.com/terminal.jpg?md2ui.max_width=400&md2ui.aspect_ratio=4:3)
:::0
```console
$ xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
:::1
