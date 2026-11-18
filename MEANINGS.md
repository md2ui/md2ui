# Meanings

What each spelling means with this theme.

- Write only the spellings listed here. Anything not listed, write bare: `` `Tag` ``, `⭐`, `[Label](/x)`.
- A role or a place no row names takes the bare spelling: the primary one.
- `~~…~~` around any listed spelling is its muted state: inactive, unavailable, past.
- A fixed colour belongs to its token everywhere it appears. Never use one to mark a single item.
- A pattern may declare a spelling its own shape needs; one meant everywhere is declared here.
- A month calendar's days take their states from `patterns/month-calendar`: weekday, weekend, event, today, outside the month.

<!-- For theme authors. *Means* says what a spelling is for and where it goes, in words an
agent acts on: never a colour, a size or a measurement. *Size*, where a row has one, is how
the theme should draw it: the theme lint compares it with what THEME.md draws, and agents
never see it. A fixed colour whose *Means* is `decoration` is not shown to agents. -->

## Icons

| Write | Means | Size | Slot |
|---|---|---|---|
| `⭐` | an icon in a label or a list item, or leading a row: who or what it is | standard | icon-label |
| `*⭐*` | the icon a feature, an empty state or a headline is about | large | icon-subject |
| `**⭐**` | an icon in a dense row, beside a caption | small | icon-dense |
| `***⭐***` | an icon inside a compact element | extra small | compact |
| `"⭐"` | the glyph alone, as part of the text around it | | inline |

## Chips

| Write | Means | Size |
|---|---|---|
| `` `Tag` `` | a tag or a status | |
| `` *`Tag`* `` | a second kind of tag on the same item | |
| `` _`Tag`_ `` | a tag in a compact row | small |

## Buttons

| Write | Means | Size | Slot |
|---|---|---|---|
| `[Label](/x)` | the main action, at the foot of a flow, a section or a dialog | | foot-main |
| `*[Label](/x)*` | a quieter action there: an alternative to the main one, or one the page is not for | | foot-quieter |
| `**[Label](/x)**` | the main action inside a card: the one the card is for, on each item of a run (reserve it, add it, join it); a card on its own takes the section's spellings | medium | card-main |
| `***[Label](/x)***` | a quieter action inside a card | medium | card-quieter |
| `_[Label](/x)_` | the main action at the edge of a row in a list | small | row-main |
| `__[Label](/x)__` | a quieter action at the edge of a row | small | row-quieter |
| `___[Label](/x)___` | an action inside a compact element | extra small | compact |
| `` [`Label`](/x) `` | a way in that repeats on every card (details, read more); at the edge of a section's title; a link to another place, in a site map, a footer or a list of links; a minor action | | card-way-in, title-edge, nav, minor |
| `"[Label](/x)"` | a link inside a sentence | | inline |

## Icon buttons

| Write | Means | Size | Slot |
|---|---|---|---|
| `[▶️](/x)` | the main icon action | | foot-main |
| `*[📞](/x)*` | an icon action | | foot-quieter |
| `**[💬](/x)**` | the main icon action inside a card | medium | card-main |
| `***[❤️](/x)***` | an icon action inside a card | medium | card-quieter |
| `_[▶️](/x)_` | the main icon action at the edge of a row | small | row-main |

## Sections

| Write | Means |
|---|---|
| `## {#card-1}` | one object the answer is about, shown as a card of its own: a bank card, a pass, a ticket; on a `###` too; number each one: `{#card-2}`, `{#card-3}`; `patterns/bank-card` shows it |
| `## Title {#green-1}` | a section in the brand colour instead of the plain one: the headline figures, an offer, a tip or a call to act |
| `## Title {#dark-1}` | a section in the dark style instead of the plain one: a player, a live status |
| `## {#music-player-1}` | the track playing now, with its controls; `patterns/music-player` shows it |
| `## Title {#reset-1}` | a pause the answer suggests: a break, a breath, a step away |
| `## Title {#learning-1}` | something to learn on the side: a definition, a short lesson, how something works |
| `## Title {#afternoon-1}` | the later part of a day plan: the afternoon or the evening |
| `### {#framed-1}` | a picture shown as a print: a photo the user keeps, pinned or shared; `patterns/framed-picture` shows it |

## Placeholders

| Write | Means |
|---|---|
| `![Sara Zane](?md2ui.placeholder=avatar:SZ&md2ui.shape=circle&md2ui.max_width=48)` | a person or an account that has no photo: their initials, up to three letters |
| `![Acme](?md2ui.placeholder=brand:A&md2ui.max_width=48&md2ui.aspect_ratio=1:1)` | a company, a service or an app that has no logo: its initial |
| `![Cacaluta Bay](?md2ui.placeholder=media)` | a product, a place or a post that has no photo yet |

## Fixed colours

| Token | Means |
|---|---|
| `▲` in a chip | a rise, good |
| `▼` in a chip | a fall, bad |
| `🔄` in a chip | in progress |
| `⏳` in a chip | pending |
| `✕` in a chip | cancelled |
| `🟢` | a good status: running, online, healthy |
| `🔴` | a bad status: down, offline, failing |
| `✅` | success |
| `⚠️` | a warning |
| `❌` `🛑` | a failure, stop |
| `☀️` `🌤️` `⛅` `🌥️` `☁️` `🌫️` `🌦️` `🌧️` `⛈️` `🌩️` `🌨️` `❄️` `🌬️` `💨` `🌪️` `🌈` `🌙` `🌡️` `☔` `💧` | weather: the condition, temperature or rain it stands for |
| `✓` | done, complete; in a chip too |
| `❤️` on an icon button | a like or a favourite |
| `🚶` | decoration |
| a button whose whole label is `OK`, or whose label contains `Accept` or `Approve` | drawn as confirming |
| a button whose whole label is `Cancel`, or whose label contains `Delete` | drawn as destructive |
