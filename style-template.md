---
name: md2ui-style-template
description: A ready-to-render Markdown document exercising the md2ui constructs verified in the field. Render it against a THEME.md to see what that theme does to each component.
---

# Style template

The current style template is [Daylight](default-theme/content.md), with its [matching theme](default-theme/THEME.md). It integrates the constructs below into a studio and personal dashboard. The specimen below is retained as the earlier reference.

A specimen document. Render it against any `THEME.md` to see how that theme paints each component, and to sanity-check a theme change across everything at once.

**One command** — it groups the Markdown, lays it out and renders it, then exits:

```
uv run md2ui render path/to/content.md --theme THEME.md --width 1280 --out specimen.png
```

Re-run it after any change, to the document or the theme; it takes a second or two. `THEME.md` is auto-discovered next to the document, so `--theme` is optional when it sits in the same folder.

Read the terminal output: `NOT-HONORED-PARAM` and `UNREACHABLE-PARAM` lines name the exact reason an image annotation was refused.

---

**Scope.** The specimen exercises the constructs that have been rendered against a real design. Of-bars and radio buttons are not among them yet — they are marked `TODO` at the end so the gap stays visible.

Everything below the line is the specimen. Copy it into its own `.md`.

---

# Text styles

---

**bold** • **italic** • ***bold-italic***

_Muted \- a caption or a footnote._

__Lead \- a standfirst that introduces the block below it.__

___Display \- a bigger emphasis.___


Plain body text with a **bold** word, an *italic* word, an ***bold italic*** word, and an `inline code` marker sitting.
inside the sentence.

<!--Heading leafs-->

---

# Heading texts

---


# `😃` Heading one text with a **bold** word, an *italic* word, a ***bold italic*** word, and an `inline code` marker sitting.
***

## `😃` Heading two text with a **bold** word, an *italic* word, a ***bold italic*** word, and an `inline code` marker sitting.
***

### `✅` Heading three text with a **bold** word, an *italic* word, a ***bold italic*** word, and an `inline code` marker sitting.
***

#### `✅` Heading four text with a **bold** word, an *italic* word, a ***bold italic*** word, and an `inline code` marker sitting.
***

##### ✅ Heading five text with a **bold** word, an *italic* word, a ***bold italic*** word, and an `inline code` marker sitting.
***

###### ✅ Heading six text with a **bold** word, an *italic* word, a ***bold italic*** word, and an `inline code` marker sitting.
***


<!-- Heading groups -->

# Heading groups

---

# Heading one
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

# Heading one
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

# Heading one
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

---

## Heading two 
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

## Heading two 
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

## Heading two 
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

---

### Heading three
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

### Heading three
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

### Heading three
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

---

#### Heading four
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***


#### Heading four
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***


#### Heading four
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

---

##### Heading five
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

##### Heading five
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

##### Heading five
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

---

###### Heading six
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

###### Heading six
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

###### Heading six
Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.
***

--- 


# Nested groups

## Heading two

---

Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.

[Primary button](/primary) *[Secondary button](/primary)*

### Heading three

---

Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.

**[Tertiary button](/primary)** ***[Quaternary button](/quaternary-button)***

#### Heading four ... `Chip`

---

Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.


##### Heading five

---

Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.


###### Heading six

---

Body copy at the default size, long enough to wrap and show the measure. A sentence or two is what most themes are tuned for.

[`Plain text button`](/plain-text-button)

---


## Card with footer

#### Sub content

Text

---

_Text_

***

This is the footer

## Card with footer

#### Sub content

Text

---

_Text_

***

This is the footer

## Card with footer

#### Sub content

Text

---

_Text_

***

This is the footer


# Key-value groups


Revenue: $129,201.40

Wealth Management: $412M

Available balance: 1,204 items

## Metrics

#### Revenue: \$129,201.40


#### Wealth Management: \$412M


#### Available balance: \$1,204



<!-- A `Key: value` on a HEADING line keeps the value at the heading size and drops the key
     to the size below, from `Heading{N} Overline`. Nothing else in this specimen draws
     those blocks. -->


# Key-values in headings

---

# HEADING 1 KEY: Heading 1 value
***

## HEADING 2 KEY: Heading 2 value
***

### HEADING 3 KEY: Heading 3 value
***

#### HEADING 4 KEY: Heading 4 value
***

##### HEADING 5 KEY: Heading 5 value
***

###### HEADING 6 KEY: Heading 6 value
***

---

_HEADING 1 OVERLINE_
# Heading 1 value
***


_HEADING 2 OVERLINE_
## Heading 2 value
***

_HEADING 3 OVERLINE_
### Heading 3 value
***

---


# Buttons, chips & emojis.

---

## Buttons

##### 

**Main**

[Primary](/primary) *[Secondary](/x)* ~~[Disabled primary](/x)~~ ~~*[Disabled secondary](/x)*~~

[Cancel](/primary) *[Cancel action](/x)*

[Delete](/primary) *[Delete action](/x)*

[OK](/primary) *[OK action](/x)*

[Accept](/primary) *[Accept action](/x)*

[Approve](/primary) *[Approve action](/x)*

##### 

**Medium**

**[Primary](/x)** ***[Secondary](/x)*** ~~**[Disabled primary](/x)**~~ ~~***[Disabled secondary](/x)***~~

**[Cancel](/primary)** ***[Cancel action](/x)***

**[Delete](/primary)** ***[Delete action](/x)***

**[OK](/primary)** ***[OK action](/x)***

**[Accept](/primary)** ***[Accept action](/x)***

**[Approve](/primary)** ***[Approve action](/x)***

##### 

**Small**

_[Primary](/x)_ __[Secondary](/x)__ ~~_[Disabled Primary](/x)_~~ ~~__[Disabled econdary](/x)__~~

_[Cancel](/primary)_ __[Cancel action](/x)__

_[Delete](/primary)_ __[Delete action](/x)__

_[OK](/primary)_ __[OK action](/x)__

_[Accept](/primary)_ __[Accept action](/x)__

_[Approve](/primary)_ __[Approve action](/x)__

##### 

**Extra small**

___[Label](/x)___ ~~___[Disabled](/x)___~~ 

___[Cancel action](/x)___ ___[Delete action](/x)___ 

___[OK action](/x)___ ___[Accept action](/x)___ ___[Approve action](/x)___

---

*Link columns*

**[About](/about)** **[Careers](/careers)** **[Press](/press)** **[Blog](/blog)** **[Help](/help)** **[Contact](/contact)** 
**[Status](/status)** **[Legal](/legal)**

---

##### Plain buttons

[`Regular`](/text)

[`Regular`](/text)

[`Regular`](/text)

[`Regular`](/text)

##### Plain buttons

*[`Italic`](/text)*

*[`Italic`](/text)*

*[`Italic`](/text)*

##### Plain buttons

**[`Bold`](/text)**

**[`Bold`](/text)**

**[`Bold`](/text)**

##### Plain buttons

***[`Bold-italic`](/text)***

***[`Bold-italic`](/text)***

***[`Bold-italic`](/text)***

***

---
<!--👤 Male | 📍 Elshiekh zayed,Giza | 💼 Accountant | 📅 12 Dec 1992 (38 years)-->
**Emoji buttons**

[💬](/chat) [✉](/mail) [📞](/call) [⭐](/star) [❤️](/like) [🤍](/like) [👤](/contact) [➡️](/next)

---

*[💬](/chat)* *[✉](/mail)* *[📞](/call)* *[⭐](/star)* *[❤️](/like)* *[🤍](/like)* *[👤](/contact)* *[➡️](/next)*

---

**[💬](/chat)** **[✉](/mail)** **[📞](/call)** **[⭐](/star)** **[❤️](/like)** **[👤](/contact)** **[➡️](/next)**

---

***[💬](/chat)*** ***[✉](/mail)*** ***[📞](/call)*** ***[⭐](/star)*** ***[❤️](/like)*** ***[👤](/contact)*** ***[➡️](/next)***

---

**Emoji + text buttons**

[💬 Chat](/chat) [✉ Mail](/mail) [📞 Call](/call) [⭐ Star](/star) [❤️ Like](/like) [👤 Contact](/contact) [➡️ Next](/next) [🔒 Lock](/x) [💾 Save](/x) [⬆️ Upload](/x) [⬇️ Download](/x) [Cancel ✕](/x)

---

*[💬 Chat](/chat)* *[✉ Mail](/mail)* *[📞 Call](/call)* *[⭐ Star](/star)* *[❤️ Like](/like)* *[👤 Contact](/contact)* *[➡️ Next](/next)*

---

**[💬 Chat](/chat)** **[✉ Mail](/mail)** **[📞 Call](/call)** **[⭐ Star](/star)** **[❤️ Like](/like)** **[👤 Contact](/contact)** **[➡️ Next](/next)**

---

***[💬 Chat](/chat)*** ***[✉ Mail](/mail)*** ***[📞 Call](/call)*** ***[⭐ Star](/star)*** ***[❤️ Like](/like)*** ***[👤 Contact](/contact)*** ***[➡️ Next](/next)***

___

**Plain text links**

"[About](/about)" • "[Careers](/careers)" • "[Press](/press)" • "[Blog](/blog)" • "[Help](/help)" • "[Contact](/contact)"


---

## Chips

**Primary**

`Draft` `In review` `Shipped` `Archived`

~~`Draft`~~ ~~`In review`~~ ~~`Shipped`~~ ~~`Archived`~~

*`Draft`* *`In review`* *`Shipped`* *`Archived`*

~~*`Draft`*~~ ~~*`In review`*~~ ~~*`Shipped`*~~ ~~*`Archived`*~~

**`Draft`** **`In review`** **`Shipped`** **`Archived`**

~~**`Draft`**~~ ~~**`In review`**~~ ~~**`Shipped`**~~ ~~**`Archived`**~~

***`Draft`*** ***`In review`*** ***`Shipped`*** ***`Archived`***

~~***`Draft`***~~ ~~***`In review`***~~ ~~***`Shipped`***~~ ~~***`Archived`***~~

---

**Secondary**

_`Draft`_

~~_`Draft`_~~

__`Draft`__

~~__`Draft`__~~

___`Draft`___

~~___`Draft`___~~

---

**Emoji**

`⭐` `❤️` `💬` `✉` `📞` `⭐` `❤️` `👤` `➡️`

---

**Plain text markers**

"`Draft`" • "`In review`" • "`Shipped`" • "`Archived`"


## Emoji badges

**Primary**

⭐ ❤️ 💬 ✉ 📞 ⭐ ❤️ 👤 ➡️

---

*⭐* *❤️* *💬* *✉* *📞* *⭐* *❤️* *👤*

---

**Secondary**

**⭐** **❤️** **💬** **✉** **📞** **⭐** **❤️** **👤**

---

***⭐*** ***❤️*** ***💬*** ***✉*** ***📞*** ***⭐*** ***❤️*** ***👤***

---


**Inside buttons**

[⭐](/icon-only) [⭐ Save](/mixed-label)

*[⭐](/icon-only)* *[⭐ Save](/mixed-label)*

**[⭐](/icon-only)** **[⭐ Save](/mixed-label)**

***[⭐](/icon-only)*** ***[⭐ Save](/mixed-label)***

---

⭐ inside a sentence, at text size [link](/x).

---

**Plain text emojis**

"⭐" "❤️" "💬" "✉" "📞" "⭐" "❤️" "👤" "➡️"

_"⭐"_ _"❤️"_ _"💬"_ _"✉"_ _"📞"_ _"⭐"_ _"❤️"_ _"👤"_ _"➡️"_

__"⭐"__ __"❤️"__ __"💬"__ __"✉"__ __"📞"__ __"⭐"__ __"❤️"__ __"👤"__ __"➡️"__

___"⭐"___ ___"❤️"___ ___"💬"___ ___"✉"___ ___"📞"___ ___"⭐"___ ___"❤️"___ ___"👤"___ ___"➡️"___

---
              

# Numbered lists

1. One
2. Two
3. Three
4. Four

## 1. Heading list item

Content

## 2. Heading list item

Content

## 3. Heading list item

Content

## 4. Heading list item

Content

***

### 1. Heading list item

Content

### 2. Heading list item

Content

### 3. Heading list item

Content

### 4. Heading list item

Content

## Heading group

1. One
2. Two
3. Three
4. Four

***

### Heading group

1. One
2. Two
3. Three
4. Four

***

#### Heading group

1. One
2. Two
3. Three
4. Four


# Unordered lists

- One
- Two
- Three
- Four

## Heading group

- One
- Two
- Three
- Four

***

### Heading group

- One
- Two
- Three
- Four

***

#### Heading group

- One
- Two
- Three
- Four

# Task lists

- [ ] One
- [X] Two
- [X] Three
- [ ] Four

# Quote lists

<!-- Consecutive `>` lines are ONE blockquote and share one bar. -->

> A quoted block of two lines
> sharing a single gutter bar.

<!-- Blank lines make each row its own quote, so each gets its own bar. -->

> 4:00 PM - Finish packing

> 6:00 PM - Drop off keys

> 6:30 PM - Leave for airport

# Mixed lists

## 

1. First numbered item
2. Second numbered item
3. Third numbered item


## 

- First bulleted item
- Second bulleted item
- Third bulleted item

## 

> A single-level blockquote, for the gutter marker.
> A single-level blockquote, for the gutter marker.

> A single-level blockquote, for the gutter marker.


## 

- [X] First task item
- [ ]
  Second task item
- [ ] Third task item 🙂
- [X] ... Label
---
<!--This is turned into unordered lists since it loses the `- [ ]` pattern to identify them as task lists-->
- ... [ ] ... Label
- ... [ ] Label

# Marker field guide

_The marker belongs to the background level of the thing it labels._

## 1. Above the section body
<!-- Exercises: an exact Heading 2 marker with Aside: no.
Tip: Heading 2 owns this ordinal independently of lists and the other heading levels. Its text color is replaced against the white Heading 2 surface. -->
This heading's ordinal sits above the section body because its marker declares `Aside: no`.

### 2. First-line baseline
<!-- Exercises: an exact Heading 3 marker with baseline alignment, plus top-aligned bullets, bottom-aligned ordinals and above-body quote bars.
Tip: each nested Marker belongs to its Unordered Lists, Numbered Lists, Quotes or exact Heading N background level. Shapes and bars use Fill color replacements; ordinal text uses Text color replacements. -->
The smaller heading ordinal shares the first text baseline with its heading title.

**Top-aligned shape markers**

- A short reminder stays pinned to the first line.
- A longer reminder wraps through the available card width so the circle remains at the top of the complete item body.

**Bottom-aligned ordinal markers**

1. Review the placement at both the wide and narrow render widths so the item wraps and exposes its bottom edge.
2. Confirm that the second ordinal uses the numbered-list marker rather than inheriting the heading marker above it.

**Bars above quote bodies**

> A quote bar becomes a fixed-length horizontal rule when its marker declares `Aside: no`.


# Separators

## Separators

Alpha - Beta - Gamma

Alpha • Beta • Gamma

Alpha | Beta | Gamma

Key : Value


## Column separators


## Row separators

---

A horizontal rule sits above this line.


## Elements

Two consecutive lines with no blank line between them
are glued into a single card element.

This paragraph is a separate element, because a blank line ended the one above.


# Images

**Wide image**

![Mountain lake postcard](https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1000&q=85&md2ui.aspect_ratio=2.35:1)
_Image credit\: [Luca Bravo](https://unsplash.com/@lucabravo)\, Unsplash [link](https://unsplash.com/photos/brown-house-near-body-of-water-zAjdgNXsMeg)._

## 

![Plain image](https://images.unsplash.com/photo-1551650975-87deedd944c3?q=80&w=1200)

***

**Profile image**

## 

![Circle](https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?q=80?w=1480&md2ui.shape=circle&md2ui.max_width=96)
Photo by:
"[Alex Sprun](https://unsplash.com/photos/man-in-black-button-up-shirt-ZHvM3XIOHoE)"

___

...
## Text beside a picture
The heading rides in cell one and this copy with it, while the picture takes the other half.
[Read more](/more)
...

:::1

![Aside](https://images.unsplash.com/photo-1551650975-87deedd944c3?q=80&w=1200)

:::1


## 

![
## A card with a photo behind it
The alt slot holds real Markdown, so this text is the card's content and the URL is its
background.
+++++
+++++
+++++
[Act now](/act)
](https://images.unsplash.com/photo-1551650975-87deedd944c3?q=80&w=1200)

![
## A second one
Two of them, so the pair grids as a run.
+++++
+++++
+++++
[Act now](/act)
](https://images.unsplash.com/photo-1551650975-87deedd944c3?q=80&w=1200)


***

**Placeholders**

## People

- ![Sara Zane](?md2ui.placeholder=avatar:SZ&md2ui.shape=circle&md2ui.max_width=48) - **Sara Zane** : _Design lead_
- ![Ravi Kumar](?md2ui.placeholder=avatar:RK&md2ui.shape=circle&md2ui.max_width=48) - **Ravi Kumar** : _Engineering_
- ![Ana Ruiz](?md2ui.placeholder=avatar:AR&md2ui.shape=circle&md2ui.max_width=48) - **Ana Ruiz** : _Support_
- ![Guest](?md2ui.placeholder=avatar:👤&md2ui.shape=circle&md2ui.max_width=48) - **Guest** : _No account_

## Companies

- ![Acme](?md2ui.placeholder=brand:A&md2ui.max_width=48&md2ui.aspect_ratio=1:1&md2ui.corner_radius=12) - **Acme** : _Connected_
- ![Northwind](?md2ui.placeholder=brand:N&md2ui.max_width=48&md2ui.aspect_ratio=1:1&md2ui.corner_radius=12) - **Northwind** : _Connected_

## No photo yet

![Product photo](?md2ui.placeholder=media&md2ui.aspect_ratio=3:2)
_A product whose photo has not been taken yet._

## A picture that failed

![Missing photo](/nonexistent/md2ui-missing.png?md2ui.aspect_ratio=3:2)
_Its source did not load, so the theme's broken placeholder draws._

# Drawing components

## Charts & bars

---

Elapsed: 45%

Elapsed: -10%

---

... 64/100 km ...
... _Aug 12_ ...

---

- Mon: 90%
- Tue: 85%
- Wed: 60%
- Thu: 12%
- Fri: -10%

---

Price: $710.14 (Apr 13) → $713.94 → $720.65 → $737.62 (May) → $773.26 → $777.24 (Now)

## Task controls & Sliders

---

An unchecked control
[ ]

___

 A checked control
[x]

<!-- Both states, because a theme's `### Checked *` blocks are never drawn by a
     page that only writes `- [ ]`. -->

---

... "🔊" ...
... [65%] ...
... "🔈" ...

... Effects ...
... [[35%]](agent:set-effects?channel=music) ...

___

## Day chips
Mon-15 - Jun-15 - Mon-15 - Jun-15


## Rows painted by level

<!-- A row written as its own section takes that level's background, so a
     `Background color:` list on the level tints the rows in document order.
     If these three render unpainted, the theme has not given `### Heading 3` a
     background — which is the specimen telling you the template is short a
     capability, not that the construct does not work. -->

### 9:00 AM - Team Standup

### 10:00 AM - 1:1 with Emily

### 12:30 PM - Client Meeting

## Spring placement

Subtotal ... $42.50

... Centred by a spring ...

Label ... [x]


# Tables

## Orders

<!-- Exercises: Header and Cells (zebra Background colors), column alignment, a
chip, a pinned status chip, a signed value and a text link inside cells. At a
narrow width Stacking cards turns each row into a card titled by its first cell
(Card layout: title), with Card Keys naming the other columns. -->

| Order | Customer | Status | Items | Change | Total |
|---|---|:-:|:-:|--:|--:|
| #1042 | Ana Ruiz | `✓ Shipped` | 3 | +12% | $128.40 |
| #1043 | Leo Park | `⏳ Pending` | 1 | -4% | $36.00 |
| #1044 | Mia Chen | `🔄 Packing` | 5 | +30% | $412.95 |
| #1045 | Omar Haddad | `✕ Cancelled` | 2 | -100% | $0.00 |
| #1046 | Sara Lind | `✓ Shipped` | 4 | +8% | "[$219.10](/orders/1046)" |

## Orders on a dark card {#dark-1}

<!-- Exercises: the same table on a dark surface. Header and cell fills are
replaced against the card (Color Replacements on #26262B), and the cell text
then keys on the replaced fill. -->

| Order | Customer | Status | Total |
|---|---|:-:|--:|
| #1042 | Ana Ruiz | `✓ Shipped` | $128.40 |
| #1043 | Leo Park | `⏳ Pending` | $36.00 |
| #1044 | Mia Chen | `🔄 Packing` | $412.95 |
