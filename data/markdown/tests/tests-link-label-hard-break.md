<!--
A hard break inside a link label (2026-11-08).

A trailing backslash breaks a line inside a link label as it does inside a text,
as CommonMark reads link text. In the sentence the link draws on two lines,
"monthly plan" over "at $9", and the button draws "Monthly plan" with no
backslash; a pill keeps its label on one line (proposals/separators-inside-chips).
Before the fix both drew the backslash on one line ("monthly plan\ at $9",
"Monthly\ plan"), because the label's lines were joined before the break was read.
-->

Pick the [monthly plan\
at $9](agent:choose?plan=basic) today.

[Monthly\
plan](agent:choose?plan=basic) [Yearly](agent:choose?plan=yearly)
