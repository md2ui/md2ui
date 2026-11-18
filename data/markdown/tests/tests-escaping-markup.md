<!-- ESCAPES THAT DECLINE A CONSTRUCT, and the ones that cannot.

     Its sibling tests-escaping-values.md covers the escapes that decline a
     READING (`4\/8` is text, not a bar). This file covers the rest: an escape
     that declines a SPLIT, one that keeps a markup character literal, and the
     characters where a backslash does nothing at all.

     The dividing line is WHEN the backslash is resolved. The separator and
     value escapes are resolved LAST (_resolve_escapes, phase 6.17), so every
     scan that needs to see them still can. `\*` is never resolved by the
     grouper: its backslash stays in the text and the drawer resolves it, so
     `\*not italic\*` and `\*\*not bold\*\*` below are drawn with their stars
     (2026-11-08; before, both were drawn italic and bold). Every other
     CommonMark escape is resolved FIRST, in preprocess — which is why the last
     section here does not decline anything: by the time the construct is
     looked for, the escape it was written with is gone. -->

## The five separator escapes

<!-- Each pair is the same line twice: escaped, then not. The escaped one stays
     whole and the backslash is not drawn. -->

Fri, Aug 14 \- Sun, Aug 16

Fri, Aug 14 - Sun, Aug 16

A \| B

A | B

Key\: value

Key: value

Shibuya\, Tokyo

Shibuya, Tokyo

A \... B

A ... B

## Escapes that keep a character literal

\*not italic\*

\*\*not bold\*\*

\#1 in the leaderboard

\- not a list item

- a real list item

\[ ] not a task control

[ ] a real task control

<!-- `\[x]` comes back as the uppercase `[X]`: the protection round-trips the
     token through one spelling. -->

\[x] not a done control

<!-- `@` joined the deferred set when the line valign token was added, so this
     is the newest member of this section rather than of the last one. -->

Subtotal - 92 \@ct

## Non-ASCII characters after a backslash

<!-- CommonMark escapes ASCII punctuation and nothing else. A non-ASCII
     character (a dot, since ADR-205; a long dash) splits nothing, so its
     backslash is ordinary text and IS drawn, as any Markdown renderer draws it. -->

A \• B

A \— B

A \– B

## Constructs the escape cannot reach

<!-- Measured 2026-09-06. Each line below is written as a refusal and is drawn
     as the construct anyway, because preprocess resolved the backslash before
     the scanner looked. They are here so the snapshot shows it the day that
     changes. skills/structure.md already warns authors off `\_`.
     The last line is the exception since 2026-10-06 (batch 14): `#` joined
     the deferred control escapes, so `\# not a heading` stays text, as in
     CommonMark. Re-measured 2026-11-03. -->

\_not muted\_

\`not code\`

\[not a link](/x)

\![not an image](/x.png)

\# not a heading

## Inside a code span

<!-- A code span is literal, as in CommonMark: no escape works inside it, early
     or late, so every backslash below is drawn (2026-11-01; `\` was consumed
     as an escaped backtick and drew empty backticks). -->

A trailing `\` here

`\` alone

`a\-b` and `x\*y` and `p\/q`

Ends in code `z`\
and breaks onto this line
