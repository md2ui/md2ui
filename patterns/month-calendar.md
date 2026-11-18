---
name: month-calendar
description: A month of days as this theme's calendar card, with weekdays, weekends, days with events, today and the days outside the month told apart; use for a date picker or a month overview.
---
# Month calendar

**Use for:** one month, when which days are free or busy matters. **Not for:** a list of events (rows), or a single date (write it).

```markdown
## 

__Next Month__ ... __"📅"__ - `September` `2024` @ct

| Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| ~~`26`~~ | ~~`27`~~ | ~~`28`~~ | ~~`29`~~ | ~~`30`~~ | ~~**`31`**~~ | **`1`** |
| `2` | `3` | `4` | `5` | `6` | **`7`** | **`8`** |
| `9` | `10` | `11` | `12` | `13` | **`14`** | **`15`** |
| *`16`* | *`17`* | *`18`* | `19` | ***`20`*** | **`21`** | **`22`** |
| `23` | `24` | `25` | `26` | `27` | **`28`** | **`29`** |
| `30` | ~~`1`~~ | ~~`2`~~ | ~~`3`~~ | ~~`4`~~ | ~~**`5`**~~ | ~~**`6`**~~ |
```

**What the days mean here.** Inside this table, and only here:

| Write | Means |
|---|---|
| `` `9` `` | a weekday |
| `` **`9`** `` | a weekend day |
| `` *`9`* `` | a day with an event |
| `` ***`9`*** `` | today |
| `` ~~`9`~~ `` | a weekday of the month before or after |
| `` ~~**`9`**~~ `` | a weekend day of the month before or after |

**Why each marker**
- Every column is centred (`:-:`), and each day is one chip.
- A day's state is its wrapper, written on that day. A fixed colour would light the same number in every month.
- A day has one spelling: today wins over an event or a weekend. A day outside the month keeps its weekday or weekend spelling, muted.
- ` ... ` puts the title left and the calendar glyph right; `"📅"` is the glyph alone, at text size; `@ct` centres the row.
- `{#dark-1}` on the `##` draws the same calendar on the dark card — `MEANINGS.md`.
