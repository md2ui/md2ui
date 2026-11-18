---
name: md2ui-verifying
description: Checking an answer before you send it — `check`, `preview`, the one-command render loop, and what the terminal tells you.
---

# Rendering, and iterating fast

Render early. A render answers "did that group the way I meant" in a second, and it is the
cheapest tool you have while writing.

## The loop

```
uv run md2ui render path/to/content.md --width 1280 --out out.png
```

`--width` is the content's width; the page adds the theme's root padding on both sides.

**One command, and it exits.** It groups the Markdown, lays it out and paints it on every run,
so there is no intermediate file to keep in step: a document edit is just a re-run, a second
or two. `THEME.md` is found beside the document; `--theme` picks another.

That is the most useful habit in this file: **iterate by re-rendering.** Try three versions of
a document rather than reasoning about one.

## With a backend's md2ui tools

When the backend offers md2ui's MCP tools instead of a terminal, the loop is the same:

- **`check` before you send.** It names what a render would not put into words: a link that
  reports nothing, an anchor with no heading to scroll to, an action inside a sentence, a
  document that draws nothing, a repeated run of pictures with no ratio, a card whose number
  of buttons breaks its run. An issue with a mechanical fix carries its `line`, the `text` as
  written and every `replacements` spelling: pick the one you meant. `show` returns the same
  issues. A `note` is advice — the same offer shown twice, a run where only some cards are
  tappable: apply it the next time you send the page anyway.
- **`showing` to ask what is on screen.** It returns the live message, the Markdown the server
  holds, and each control — with what the user has asked for and you have not answered yet. Use
  it to check what a control *holds*: a value they settled on, a box they ticked. It is also
  the first thing to call if you did not send the page yourself.
- **`screenshot` for how it looks.** At its default width it costs about 300 tokens and
  shows the layout, the buttons and whether the pictures loaded, so look once after showing a
  new kind of page. Ask for a wider one only to read small text. Pictures load after the
  page, so one missing right after `show` may still be arriving: look again before you
  conclude it failed. A picture cannot be read
  reliably for values, so ask `showing` what a control *holds*.
- **`preview` the part you are unsure of,** before you send it: pass just that section, not
  the page. Its description says whether pictures load where you run. Where they do, check
  that each one shows what you say it shows. Where they draw as placeholders, judge the
  grouping, the layout and the colour, and keep the pictures in: the user's window loads them.
- **`show`'s `digest`** says in a few lines how the page grouped: each section, its runs and
  their shape. Read it before reaching for anything else. **`outline` and `layout`** show the
  whole tree, for when the digest is not enough to see why something grouped.
- **`actions`** lists what your answer offers, and which clicks come back to you. Each is
  `sent: true` or `sent: false` — and that is the only way to catch an action you meant to
  hear about written `/route`, which the app handles and you never see. The two render
  identically.

## The terminal tells you about images

Image params report themselves, which makes them easy to tune. A param that cannot be read
is dropped, never guessed, and the terminal names it:

```
[url] 0.1: 'md2ui.min_width=0' must be >= 1
[url] 0.1: unknown property 'md2ui.colour'
```

Read those lines before trying other values — a typo'd name does nothing at all.

A link reads `md2ui.commit` and `md2ui.choice`, and only on an `agent:` link; `check` names any
other as `link-param`, and it never leaves the link.

## A quick pass on a first render

- [ ] each card holds what you meant (blank lines — [`structure.md`](structure.md))
- [ ] the runs you wanted side by side gridded ([`repetition.md`](repetition.md))
- [ ] symbols render as intended in the configured fonts, with no missing-glyph boxes;
      use ordinary `+` for addition or words such as “up” when a decorative symbol is unavailable
- [ ] the datapoint families claimed what you wanted them to ([`dashboards.md`](dashboards.md))
- [ ] the terminal is clean of refused image params
- [ ] rendered again at the narrowest width it will be read at, and the page still fits it
