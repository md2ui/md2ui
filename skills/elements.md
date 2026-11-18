---
name: md2ui-elements
description: Chips, links and emoji in md2ui — separation decides whether you get an element at all; an action's weight and place pick its spelling; labels, icon buttons, and what a click does.
---

# Elements: separation makes them, the wrapper styles them

md2ui has three inline **elements** — a chip `` `x` ``, a link `[x](/y)`, and an emoji `⭐` —
and they follow one rule.

## Separate it, or it stays inline text

An element is only drawn as an element when you made it one. It has to **own the line**, be
part of a **run** of elements with nothing else on the line, or be **explicitly separated**
from the prose beside it by ` - `, ` | ` or ` : `. Otherwise it stays inside the
sentence: a chip becomes a text-marker, a link becomes a recolored word run, an emoji stays
a glyph at the surrounding text size.

Those four separators always cut the line — ` : ` stacks the pieces into a column, the others
set them side by side — so separation is a decision you make rather than one the renderer
makes for you — and `\-` `\|` `\:` declines a cut you did not mean
([`structure.md`](structure.md)). A spaced `+++` separates the same way, with blank space
in the gap instead of a character: `⭐ +++ Popular`.

```md
⭐ Popular                  one line of text, small inline star
⭐ - Popular                [BADGE ⭐] Popular
This is the `Label`        one line of text, `Label` as a marker
Draft - `Label`            Draft [CHIP Label]
Read the [docs](/d) here   one line of text, "docs" recolored
Read more - [docs](/d)     Read more [BUTTON docs]
```

**This is the control.** If your icons are rendering as tiny inline glyphs when you wanted
badges, you did not separate them. If a word is turning into a chip when you wanted it to
read as part of the sentence, remove the separator.

Removing the separator is not always available: an element that **owns its line** has nothing
to un-separate. Quote it instead — see the next section.

## Quote an element to keep it text

An element that owns its line becomes a badge, a button or a chip. **Quote it to decline
that** and get the glyph, the link or the code span at the size and font of the text around
it. The quotes are not drawn.

```md
📞                     a badge
"📞"                   a glyph in the text
"[Docs](/docs)"        a link inside prose, still clickable
"`code`"               a marker, not a chip
```

It works anywhere the quoted element starts or ends its line, so a heading keeps its own
font: `# "📞" Contact`. Single quotes do the same job, and an apostrophe is never
mistaken for one — `Alice's 📞` is untouched. Write straight quotes: typographic ones,
`“📞”`, are text and are drawn.

**The style still comes from the wrapper around the quotes**, which is what makes this worth
having: a declined element gets the whole text ladder, not one fixed size.

```md
"📞"         text size        *"📞"*      italic
_"📞"_       Muted            **"📞"**    bold
__"📞"__     Lead             ***"📞"***  bold italic
___"📞"___   Display
```

**Only a bare element is declined, and only at the edge of a line.** `"Ready to go"` is
prose and keeps its quotes; so does `Press "📞" to dial`, where the quotes are
punctuation you typed. That is deliberate — nothing here removes text you wrote.

Use it per instance: `⭐ - "📞"` is a badge and a text glyph on one line. A whole
**run** works too — quote each one, and none of them becomes an element:

```md
⭐ ❤️ 💬               three badges
"⭐" "❤️" "💬"         three glyphs in a row of text
```

## A run needs no separator at all

With nothing but elements on the line, a plain space is enough, and the kinds can mix:

```md
⭐ 🚀 ⚛️                     three badges
[a](/a) [b](/b)             two buttons
`Sale` `New`                two chips
⭐ [Buy](/b) `Sale`          badge, button, chip — in the order you wrote them
```

Any regular text anywhere on the line makes the whole line prose again, so
`` ⭐ `Popular` today `` is a sentence, not a run.

## Aligning a row up and down

The pieces of one line sit on a shared **baseline** by default. End the line with a token
to say otherwise:

```md
14:30 : LHR : London - **short** @tp     short sits at the TOP
14:30 : LHR : London - **short** @ct     centred
14:30 : LHR : London - **short** @bm     at the BOTTOM
14:30 : LHR : London - **short** @bs     baseline — the default, written out
```

It aligns **that line only**, and it outranks the theme's alignment for the level, so reach
for it where one row differs. A line that is not a row ignores
it, and the token is never drawn either way. To write one literally, escape it: `\@ct`.

An **image** joins a run the same way — `![a](a.png) ![b](b.png)` is a strip of two
pictures, `![logo](l.png) [Buy](/b)` a picture beside a button — and a separator between
them is drawn or hidden exactly as it is between chips. Words do not turn its line back
into prose: a picture cannot be drawn at text size, so the words either side of it become
pieces of the row too. See `images.md`.

# Links: an action's place gives its spelling

## An action's weight and place

An action's spelling is the one `guide("theme")` gives its **weight** in its **place**. The
app's contract decides it, and a place it names none for takes the bare `[Label](url)`. md2ui
infers neither: written bare everywhere, every link draws as the main action.

- **The main action**: what the user came to do here, one per place they decide, so the eye
  knows where to start. A run where each card is its own offer, rooms or plans, has one per card.
- **A quieter action**: an alternative to the main one, or one the page is not for: Later,
  Details, Share. What repeats down a run, the same Follow on every item, reads best quieter.
- **A minor action**: a way out or a small step: Skip, Not now, Forgot password.

The places are the foot of a flow, a section or a dialog; inside a card, on each item of a run;
the edge of a row in a list; and the edge of a section's title (See all, Edit). Three links have
a place of their own: **a way in** on every card (Details, Read more), **a link to another
place** (a site map, a footer, a breadcrumb) and **a link inside a sentence**. In the demo
project's spellings, for example; your project's are in `guide("theme")`:

```md
### Harbour room
**[Reserve](agent:reserve?id=4)** ***[Details](agent:details?id=4)***

## Ready to book?
[Sign up](agent:sign-up) *[Later](agent:later)*
```

**Match peers, contrast the rest.** Three delivery options share one spelling, or they read as
one recommendation and two also-rans; Log in beside Sign up is a main and a quieter action. Keep
each role in one spelling.

**An action the user cannot take now is its spelling muted**: `~~…~~` outside every other
wrapper, `~~*[text](url)*~~`, in the same place. `~~` is every element's muted state, with no
strike: `` ~~`Tag`~~ `` a chip, `~~⭐~~` an icon, for what is off, unavailable or not chosen. In a
sentence, `~~text~~` is still struck text.

## Words, an icon, or both

A label is words, a symbol, or both. Words are the default: most main actions, every dialog,
every flow.

- **A symbol alone suits a universal action**, one the glyph names for anyone (like, chat, add,
  play, pause, stop), where the page is not about it: a toolbar, a header, the same action on
  every row. See *Icon buttons*.
- **A symbol and its words** suit a verb whose usual sign backs the words up:
  `[⬆️ Upload a statement](agent:upload)`.
- **The item's own main action keeps its words**, and so does an action no glyph names for
  everyone, even beside icon-only ones.
- **Options of one kind share one form**: suggestions or topics each carry a glyph, or none
  does. An icon is never needed; one you add is the verb's sign, not decoration.
- An icon over its word is `patterns/quick-actions`; a tile over its word, `patterns/shortcuts`.

### An icon INSIDE a button

`⭐ - [Saved](/saved)` is a badge beside a button; `[🔖 Saved](/saved)` is one button with the
icon inside. Lines of these glue into one card and stack, a sidebar or a menu: links to another
place, the page the user is on as the main action. In the demo project's spellings, for example:

```md
[🟧 Dashboard](/dashboard)
[`🎧 My Sessions`](/sessions)
```

When the icon labels a block rather than a button, separate it instead.

### A link's label stays on one line

A label never wraps, so its card is at least as wide: name the action in a word or two. An item
the user opens carries its link one of three ways:

- `[**Under Pressure (feat. David Bowie)**](agent:open?id=7)`: the title is the button, and long
  titles widen the cards, so a run takes fewer columns;
- the title as text over `[Open](agent:open?id=7)`: the title wraps, the action has its name;
- the item's lines inside `[ … ](agent:open?id=7)`: all of it wraps, the whole card the target.

An empty label, `[](https://example.com)`, draws its own Markdown, and `check` flags it; a link
with no words takes an emoji.

## Icon buttons

A link whose label is **only** an emoji is an icon button, in the spelling `guide("theme")`
gives its place. The glyph has to name the action for anyone: like, chat, add, play, pause,
stop. Anywhere else put it inside a labelled button, `[🔖 Save for later](/x)`:
`[🎯](agent:recalibrate)` looks deliberate and tells the user nothing.

It takes its place from the flow; a `...` spring sends it to its row's far edge. As the **first
child of an image card's alt slot** it draws over the photo, the favourite in a media card's
corner ([`images.md`](images.md)).

An icon action with its word has three targets. Over its word, only the button is the target
(the demo project's spelling, for example):

```md
... *[🔖](agent:save?id=4)* ...
... Save ...
```

Both lines inside `[ … ](agent:save?id=4)` are a tile, the glyph a badge over its word, and the
whole tile is the target. `[🔖 Save](agent:save?id=4)` is one button, the icon inside.

## Links side by side, in rows or in columns

Wrapped links back to back run their markers together, and `check` flags each; a space keeps
each its own button: `**[A](/a)** **[B](/b)**`. Bare `[A](/a)[B](/b)` is fine.

Links on one line wrap into rows. One per line, they stack into a list; lists with a blank line
between them stand side by side as columns, a bold line titling each. Links to another place, in
the demo project's spelling for example:

```md
**Company**
[`About`](/about)

**Support**
[`Help`](/help)
```

## What a click does

md2ui never acts on a click: it reports it, and the app decides by the destination. `https://…`
and `mailto:…` open; `/settings` goes to the app's route; `#pricing` scrolls to
`## Pricing {#pricing}`; `agent:<action>?<args>` navigates nowhere and comes back **to you**,
with the label and the message it came from. So write `agent:` only for what you will act on,
one button per answer, named so you will recognise it:
`[Yes](agent:generate-report?format=pdf) *[No](agent:cancel)*`.

**Only `agent:` comes back, and the render cannot tell you**: `[➖](/decrease)` and
`[➖](agent:decrease)` draw the same. A route suits somewhere to go, but a click meant as your
next instruction is lost silently. `actions` marks each offer `sent: true` or `sent: false`
([`verifying.md`](verifying.md)).

**A click costs a whole turn**: a message, your response, the page replaced, however small the
change. **So ask for the destination, not the journey**: offer the likely answers, `1` `2` `5`,
as buttons. A `➖ 1 ➕` stepper of buttons takes nine turns to reach 10, and a wizard is one
question asked once, its answers on it. A slider reports once, when it settles, so prefer one
where it fits ([`dashboards.md`](dashboards.md)).

**One button can collect the whole form**, instead of a turn per tick and drag: marked
`?md2ui.commit=1`, it carries what the user changed from the page you sent.

```md
- [ ] Gift wrap it

[Proceed](agent:proceed?md2ui.commit=1) *[Cancel](agent:cancel)*
```

The press reads `User chose "Proceed": proceed, with "Gift wrap it" ticked`. `md2ui.commit` is
the app's, never your argument: `agent:buy?id=7&md2ui.commit=1` reports `{id: 7}`, and it goes
on the press, never on an option. **Mark only
the button that means keep**: a discard should not hand you values as if confirmed. Forgetting it
costs a turn, but an unintended commit is an order not meant, so it is opt-in; `actions` shows
which commit. The server holds the adjustments, so your wait returns on the press. `showing`
reports a form mid-fill without a turn or a picture
([`verifying.md`](verifying.md)).

**A form's options and counts wait for that press too.** Give each option `md2ui.choice=<name>`,
the chosen one the main variant and the rest `*…*`; ` | ` between them keeps them one
control, drawn as the theme draws it. Its label goes on its own line above: before the first option, it makes that option a
link. A count is a slider between ➖ and ➕, whole numbers from 0; ` - ` there is a separator. Taps
and drags send nothing; the press reports `with size: M`. With no commit press, each tap is a
turn. Tabs that change the page, and actions such as `Book Lyft` or `Book UberX`, stay buttons.

```md
_Size_
[M](agent:pick?size=m&md2ui.choice=size) | *[L](agent:pick?size=l&md2ui.choice=size)*

Quantity: ➖ [2/9] ➕

[Add to bag](agent:add?item=7&md2ui.commit=1)
```

**A whole card can be the button**: a block inside `[ … ](url)` reports that url. The brackets
style nothing, so a state goes on the content: an unavailable card has a `_…_` caption and a
`` ~~`Tag`~~ `` chip saying why. A button inside clicks through to the card's, so give the card
the action. Two glued lines are enough, each keeping its style, and same-shaped cards grid like
any run; a list item works too. A label of one line is a button.

```md
[**Flights CDMX ⇄ Huatulco**
_Edited Oct 4_](agent:open?id=7)
```

**A task box comes back too**: `- [ ]` reports the state asked for, its number among the
document's boxes (`0` first) and its text. `- [[ ]](agent:toggle-task?id=3) Send it` names the
action: `toggle-task`, `id=3`, the state and the text.

**The state is yours to send.** A click changes nothing in your document; the window shows the
tick or the disabled button only until your next response. To keep it, send the response again
with it written in: the choice not taken in `~~ ~~` (it stops reporting), a task `[x]`:
`[Yes](agent:email-report) ~~*[No](agent:cancel)*~~`.

**If your backend offers `mark`, use it instead.** `mark(message_id, x, "checked" | "unchecked" |
"disabled")` changes target `x`, the number the click came with, in place; `"7"` sets a slider
in its range; `mark(message_id, key="Elapsed", value=60)` moves the bar whose key you wrote
(`Files: 3/10`, a `- CPU: 40%` chart row), keeping its spelling. The page keeps its scroll.
`mark` returns a **new message id**, the old one no longer live: carry it forward. Ordinals do
not move; a disabled target keeps its slot.

**Put an action on a button, not on words in a sentence.** A sentence link clicks too, but it
cannot show it was answered, so the user may click again. Keep it for places to go, and give an
action its own button on its own line.

## A value a process changes while the page is shown

**If your backend offers `feed`, a value that a process you run changes costs no turns**: an
order's stage, an arrival time, a step's status. Mark each such value where you draw it, with a
name; a value that will not change while the page is shown stays as you write it. Mark the
value, not the sentence, in at most four words: `arriving around [7:58 PM](feed:arrives)`.
Its first text is the value your data holds now. The same values on another page that stays on
screen while they change, a list of orders or a question about one, may be marked the same way.

- **Text**: `[3:53 PM](feed:arrives)` is drawn as plain text in the emphasis around it:
  `___[3:53 PM](feed:arrives)___` stays a hero number, `_…_` a caption, `**…**` bold. The
  style goes outside the brackets.
- **A chip**: `` [`Preparing`](feed:status) ``, its word changed by the feed. It is not tappable.
- **A button's label**: `[Track · Preparing](agent:track?id=BS-1043&md2ui.feed=track)`; only the
  label changes.
- **A bar or a ratio** stays unmarked, `Progress: 40%`: the feed moves it by its key.

A name is used once on the page, in letters, digits, `-` and `_`. Then
`feed(message_id, slots=["arrives", "status"], values={"status": ["Preparing", "On the way",
"Delivered"]})`, with `keys=["Progress"]` for bars; a chip takes only the words its `values`
declare. It returns a `url` and commands: have the process (a build, a download, a test loop, a
bridge to a service you trust) post the new values, `{"status": "On the way"}` or
`Progress: 60%`, and the line `end` when it is done. The feed ends by itself, and your wait
hears of it only when there is something to do: on `feed_ended` the page keeps the last values,
so answer with the next page or `patch` it. `show` with `keep_feeds` replaces the page without
stopping it. To edit text beside a slot, quote the slot as the page holds it now, or leave its
value to the feed.

## Tabs, a selector, "show more"

A state is yours to keep: on a click, send the page again in the new state. A run of `agent:`
buttons is a tab strip, the chosen tab the main action and the rest quieter, in the spellings for
their place. At a section's foot in the demo project's spellings, for example:
`[Ruby](agent:show-code?lang=ruby) *[Python](agent:show-code?lang=python)*`.

**When every choice has its figure, show them all**, since a tab strip hides the rest: each a key
and its value, the keys the user is not looking at muted.

```md
👟 Steps: ___8,204___
_🛌 Sleep_: ___7h 10m___
```

"Show more" is an action at the heading's edge, and the next page has the rows open:
`` ### More attributes ... [`Expand all`](agent:expand?section=more) `` in the demo project's
spellings, for example.

## A click is the user's turn

Every offer, a button, a task or a slider, comes back as a sentence built from its label, so
name it in the user's words: `[Book the 9:40](agent:book?id=7)` comes back as the user choosing
"Book the 9:40". Answer it or act on it, rather than acknowledging it. Your answer replaces the
page, so it carries everything they still need from the old one.

**An anchor id is a word.** One that ends in a number, `{#featured-card-1}`, also selects a
fixed heading style from the theme, so leave the number off an id that is only a target.

# Emoji

An emoji is one of the three elements, so everything above applies: separation makes it a badge,
and the wrapper picks its size — `guide("theme")` lists which size goes where.

The emoji font, and a badge's shape and surface, are the theme's, set once for the document.

## What the icon does decides how you write it

An icon earns its place when it does a job a word would do worse. Most lines need none. When
one does, the badge is only one of the spellings; pick the spelling by the icon's job:

| the icon… | write | you get | not for |
|---|---|---|---|
| labels the word beside it | `🎧 Listeners: 4,210` · `"📦" - Ships from Lisbon` | a glyph at text size, in the line or in its own column, with no badge behind it | a list that reads clearly without it |
| stands for its item: a tile, a card, a list row | `🛍️ - **Corner Market** …` · `📶` on its own line | a badge | a glyph that only repeats the title's word |
| belongs to the section's one number | `___🔋 82%___` | a glyph at the number's size, beside it | a card with several numbers |
| relates two values, from one to the other | `__Lisbon__ ... 🚆 ... __Porto__` | a badge standing between them; quote it, `"🚆"`, for the glyph alone | a separator between unrelated items |
| gives a whole card's verdict | `✅` on its own line, under the line that says it | a badge | a verdict nobody needs at a glance |
| illustrates an empty or waiting state | the glyph of what is missing, over its title: `📭` an empty inbox, `🛒` an empty cart, in the spelling `guide("theme")` gives an empty state | a badge — `patterns/empty-state.md` | anything with content to show |
| does something | `[▶️](agent:play)` | an icon button — *Icon buttons* | a glyph that needs a word to be clear |
| judges a value | `` `⬆ 12%` `` | a glyph inside the chip, coloured by the theme | a value with no direction |

The number's glyph has two spellings and they mean different things. Inside the tier,
`___🔋 82%___`, it belongs to the number and grows with it. Separated, `🔋 - ___82%___`, it
is the card's badge, drawn as the theme draws badges, beside a Display number.

**One glyph per meaning.** Pick the glyph that names the thing — `🍴` for dining, `⚡` for
utilities — and write it again wherever that meaning comes back. Never vary it for variety,
and never fill a run with one placeholder glyph: the theme colours a run by position whatever
the glyphs are.

## A badge's state is the same spelling, or muted

In a run — tiles, steps, a rating, a set of earned badges — write every item in the same state
the same way, and an item in another state differently. The bare badge is the ordinary one; an
item that is off is the same badge muted:

| state | write |
|---|---|
| ordinary | `💡` |
| off, not yet, unavailable | `~~💡~~` |
| on, current, selected | `💡`, with its emphasis in the text beside it — unless `guide("theme")` declares a spelling for it |

```md
🎬 - **Movie night** : __Running__
🌙 - **Bedtime** : _10:30 PM_
~~🏖️~~ - **Away** : _Off_
```

Where the state has its own glyph — `✅` done, `⭐` against `☆` in a rating — the glyph
carries it, and the wrapper stays the same across the run.

A glyph in the text has no wrapper of its own: it takes the tier of the text it sits in, so
`_📦 Returns_` quiets the glyph with its label — the tab the user is not looking at.

## Where an emoji is drawn

Separation decides whether you get a badge. **Context then decides what it is drawn as**, and
the theme styles each context separately:

| written | drawn as |
|---|---|
| `⭐` alone, in a run, or separated (`Prose - ⭐`) | a **badge** — the wrapper picks its variant |
| `⭐ Popular today` | an inline glyph at text size |
| `"⭐"` | an inline glyph at text size — *Quote an element to keep it text* |
| `[⭐](/x)` · `[⭐ Save](/x)` | inside the button |
| `` `⭐` `` · `` *`⭐`* `` | inside the chip |

## An emoji in the gutter

Where the theme turns on `Emoji aside`, a lone emoji sits beside the **whole group** instead
of on its first line. It needs the emoji to be the group's first or last
child, to be one the document made an element, and the group to be more than one source line.
