---
name: month-calendar
description: A month of days as a grid, with today, the days that hold events and the days outside the month told apart; use for a date picker or a month overview.
---
# Month calendar

**Use for:** one month, when which days are free or busy matters. **Not for:** a list of events (`agenda`), or a single date (write it).

```markdown
### 

__March__ ... "📅" - `2027` @bs

| Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| ~~`22`~~ | ~~`23`~~ | ~~`24`~~ | ~~`25`~~ | ~~`26`~~ | **`27`** | **`28`** |
| `1` | `2` | *`3`* | `4` | `5` | **`6`** | **`7`** |
| `8` | ***`9`*** | `10` | `11` | *`12`* | **`13`** | **`14`** |
| `15` | `16` | `17` | *`18`* | `19` | **`20`** | **`21`** |
| `22` | `23` | `24` | `25` | `26` | **`27`** | **`28`** |
| `29` | `30` | `31` | ~~`1`~~ | ~~`2`~~ | ~~`3`~~ | ~~`4`~~ |
```

**What the days mean here.** Inside this table, and only here:

| Write | Means |
|---|---|
| `` `9` `` | a weekday |
| `` **`9`** `` | a weekend day |
| `` *`9`* `` | a day with an event |
| `` ***`9`*** `` | today |
| `` ~~`9`~~ `` | a day of the month before or after |

**Why each marker**
- The table centres every column (`:-:`), and each day is one chip.
- A day's state is its wrapper, written on that day. A fixed colour would light the same number in every month.
- Today wins over an event or a weekend: a day has one spelling.
- ` ... ` puts the month left and the year right; `"📅"` is the glyph alone, at text size; `@bs` aligns the row on its baseline.
