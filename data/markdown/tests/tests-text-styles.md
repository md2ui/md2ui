<!--Texts alone-->
***ItalicBold:***
**Bold:**
*Italic:*
~~Strikethrough~~

<!--Paragraph with text style inside-->
Text with a **bold** word in the middle

<!--Paragraph with text style inside-->
Text with an *italic* word in the middle

<!--Paragraph with text style inside-->
Text with a ~~strikethrough~~ word in the middle

<!-- Mixed, single line -->
**Price** ~~$29.99~~ **$19.99** (33% OFF)

<!--TODO: FIX, price,currency pair, check datapoint detector-->
**$2.36 €** ~~$3.59 €~~

<!-- TODO: Check id is fixed (see technical debt) -->
**~420 ppm (2024)**

<!-- Remove colon only, keep style -->
***ItalicBold:***

***ItalicBold more words:***

<!-- Remove colon only, keep style -->
**Bold:**

**Bold more words:**

<!-- Remove colon only, keep style -->
*Italic:*

*Italic more words:*

<!-- Remove colon only, keep style -->
~~Strikethrough:~~

~~Strikethrough more words:~~

<!-- Nested inline styles: the inner emphasis is applied, no literal markers -->
~~**bold text**~~

~~*italic text*~~

~~***bold italic text***~~

<!-- -->
~~__bold text__~~

~~_italic text_~~

~~___bold italic text___~~

<!-- The other direction: emphasis outside, strike inside -->
**~~bold text~~**

*~~italic text~~*

***~~bold italic text~~***

<!-- Strike + inline code marker -->
~~`code text`~~

<!-- Partial: only part of the struck run is emphasized -->
~~**bold part** and plain part~~

<!-- Multi-word: one unbroken rule, spaces struck too -->
~~struck across several words~~

<!-- Inside headings: keep the heading font at heading weight -->
# ~~**bold heading**~~

## ~~*italic heading*~~

### ~~***bold italic heading***~~

<!-- Nested strike key-value: keep both wrappers, remove the colon -->
~~**KeyBoldStrike:**~~ value

~~*KeyItalicStrike:*~~ value

~~***KeyBoldItalicStrike:***~~ value

<!-- Chips -->

`Code text`

<!-- Secondary -->
*`Code text`*

<!-- Tertiary -->
**`Code text`**

<!-- Quaternary -->
***`Code text`***

<!-- Display tiers: a WHOLE line (or whole segment) wrapped in underscores.
     Underscores are CommonMark synonyms for asterisks, so these still read as
     italic / bold / bold-italic in any plain editor. -->

<!-- Muted -->
_Muted text_

<!-- Muted strikethrough -->
~~_$3.59 €_~~

<!-- Lead: bigger than body, not as big as a heading -->
__More important text (not too important like headings)__

<!-- Lead strikethrough -->
~~__More important text (not too important like headings)__~~

<!-- Display: strongest emphasis -->
___A very important and big text___

<!-- Display strikethrough -->
~~___A very important and big text___~~

<!-- Display on a metric outside any key-value context -->
___$12,480.55___

<!-- A run of whole spans on one line: not ONE wrap, so each span becomes its
     own leaf and takes its own tier -->
_High 78_ _Low 56_

<!-- The run may mix tiers: muted then lead -->
_High 78_ __Low 56__

<!-- Three of them -->
_A_ _B_ _C_

<!-- NOT a run: asterisks are not tiers, and every line of this shape spelled
     with `*` is a key-value or a row of link/chip variants that owns its
     wrapper. Stays one leaf -->
*High 78* *Low 56*

<!-- NOT a run: a tight colon means key-value, which owns the line -->
__Key:__ __value__

<!-- NOT a run: the underscores select each chip's variant, not a text tier -->
_`a`_ _`b`_

<!-- NOT a run: same for links -->
_[Muted link](/x)_ _[Other](/y)_

<!-- Muted overline above a display metric -->
_Available balance_
___$12,480.55___

<!-- NOT a tier: mid-sentence underscores stay plain italic / bold -->
Text with an _italic_ word in the middle

Text with a __bold__ word in the middle

<!-- Not ONE wrap — two separate spans, so each takes its own tier as its own
     leaf (see the run cases above) -->
_A_ _B_

<!-- Whole-line wraps that DO propagate to every segment, including the middle
     one. `***` must not be read as `**` + a stray `*` -->
***A | B | C***

~~A | B | C~~

<!-- Segments: each whole segment takes its own tier -->
__Total__ | __$412M__ | __+12%__

_Label one_ - _Label two_ - _Label three_

<!-- Mixed tiers across segments on one line -->
_Overline_ | ___$4,029___ | __per night__

<!-- Tier on a key-value key: beats the Overline key style -->
__Key:__ value

<!-- Tier on a key-value value -->
Key: ___$129,201.40___

<!-- Tier wrapping a datapoint: the tier wins over stat-tile emphasis -->
___$412M___

<!-- Heading wins: keeps the markers, paints bold-italic, no tier -->
# ___Big heading___

<!-- Not a tier: a standalone code element is a pill, its own style wins -->
`_Code text_`

<!-- Not a tier: link variants own the wrapper — this is a Tertiary button -->
_[Muted-looking link](/link)_

<!-- Don't remove colon -->
`Test:`

<!-- Don't remove colon -->
"Test:"

<!-- Don't remove colon -->
(Test:)

<!-- Process as key-value pair, remove colon, keep text style -->
***KeyBoldItalic:*** value

<!-- Process as key-value pair, remove colon, keep text style -->
**KeyBold:** value

<!-- Process as key-value pair, remove colon, keep text style -->
*KeyItalic:* value

<!-- Process as key-value pair, remove colon, keep text style -->
~~KeyStrikethrough:~~ value

<!-- Don't process as key-value pair. And don't remove colon -->
`Test:text`

<!-- Don't process as key-value pair. And don't remove colon -->
"Test:text"

<!-- Don't process as key-value pair. And don't remove colon -->
(Test:text)

<!-- Mixed, key-value -->
**Price:** ~~$29.99~~ **$19.99** (33% OFF)

<!-- key-value & Datapoint-->
*Last updated: February 4, 2026*

<!-- This should be separated keeping the bold labels -->
**Bold one | Bold two | Bold three | Bold four**

<!-- This should be separated keeping the bold labels and plain text -->
**Bold text segment** - Regular text segment

<!-- This should be separated keeping all text-style labels and plain text -->
**A bold segment** - B regular segment - *C italic segment* - `D code segment`

<!-- This should be separated keeping all text-style labels and plain text -->
**A bold segment - B bold segment** - ***C bold italic segment*** - `D italic code segment`

<!-- This should be separated keeping all text-style labels and plain text -->
***C bold italic segment*** - `D line code segment`

<!-- This should be separated keeping all text-style labels and plain text -->
~~**A bold strikethrough segment**~~ - **B bold segment** - ***C bold italic segment*** - `D italic code segment`

<!-- Should not be separated -->
`**A bold code** - B code`

<!-- Should not be separated -->
'**A bold code** - B code'

<!-- Should not be separated -->
"**A bold code** - B code"

<!-- Bold followed by emoji-->
**Sundown café** ⭐


☀️

1

<!---->
___75°___

***75°***

<!---->
___☀️___ 75°

***☀️*** 75°

<!---->
___☀️___ - 75°

***☀️*** - 75°

<!---->
___☀️___

***☀️***

<!---->
___☀️ 75°___

***☀️ 75°***

<!---->
___☀️ - 75°___

***☀️ - 75°***

<!-- Text -->
___☀️ Display text___

***☀️ Bold Italic text***

<!---->
___☀️ - Display text___

***☀️ - Display text***

<!-- Text, Text-->
_High 78_ _Low 56_

*High 78* *Low 56*

<!--Emoji (produced by the datapoint split), datapoint -->
☀️ ___75°___

☀️ **75°**

<!---->
☀️ - ___75°___

☀️ - **75°**

<!---->
___☀️___ 75°

***☀️*** 75°

<!---->
___☀️___ - 75°

***☀️*** - 75°

<!---->
___Display___

***Bold italic***

<!---->
___Display___ ___Display___

***Bold italic*** ***Bold italic***

<!---->
# ☀️ Heading text


<!---->
# ☀️ - Heading text split

<!-- All prose-->

Lorem ipsum dolor sit amet, consectetur adipiscing elit, 75° sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

Lorem *ipsum* dolor sit **amet**, _consectetur_ adipiscing elit, 75° sed do ___eiusmod___ tempor ***incididunt*** ut labore et __dolore__ magna aliqua.

Lorem ___ipsum___

Lorem ***ipsum***


<!-- This should be separated keeping the heading context and text-styles -->
# ***⭐ Popular `heading 1 bold` italic***

# ***⭐ - Popular - `heading 1 bold` - italic***

# **⭐ Popular `heading 1` bold**

# **⭐ - Popular - `heading 1` - bold**

# *⭐ Popular `heading 1` italic*

# *⭐ - Popular - `heading 1` - italic*

# ⭐ Popular `heading 1` regular

# ⭐ - Popular - `heading 1` - regular

***

## ***⭐ Popular `heading 2` bold italic***

## ***⭐ - Popular - `heading 2` - bold italic***

## **⭐ Popular `heading 2` bold**

## **⭐ - Popular - `heading 2` - bold**

## *⭐ Popular `heading 2` italic*

## *⭐ - Popular - `heading 2` - italic*

## ⭐ Popular `heading 2` regular

## ⭐ - Popular - `heading 2` - regular

***

### ***⭐ Popular `heading 3` bold italic***

### ***⭐ - Popular - `heading 3` - bold italic***

### **⭐ Popular `heading 3` bold**

### **⭐ - Popular - `heading 3` - bold**

### *⭐ Popular `heading 3` italic*

### *⭐ - Popular - `heading 3` - italic*

### ⭐ Popular `heading 3` regular

### ⭐ - Popular - `heading 3` - regular

***

# ***⭐ Popular `bold` segment*** | 🚀 entrepreneurship | ⚛️ science

# ***⭐ - Popular - `bold` - segment*** | 🚀 - entrepreneurship | ⚛️ - science

# **⭐ Popular `bold` segment** | 🚀 entrepreneurship | ⚛️ science

# **⭐ - Popular - `bold` - segment** | 🚀 - entrepreneurship | ⚛️ - science

# *⭐ Popular `italic` segment* | 🚀 entrepreneurship | ⚛️ science

# *⭐ - Popular - `italic` - segment* | 🚀 - entrepreneurship | ⚛️ - science

# ⭐ Popular `regular` segment | 🚀 entrepreneurship | ⚛️ science

# ⭐ - Popular - `regular` - segment | 🚀 - entrepreneurship | ⚛️ - science
