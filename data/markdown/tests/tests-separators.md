<!-- This should be separated -->
one | two | three | four

<!-- This should be separated -->
Prompt | Design | Draw | Build | Publish | Promote | Jam | Present

<!-- Comma list, this should not be separated (Has no structure, each word should start with a cap) and coma lists are harder to classify, use - | or • to separate this kind of data instead -->
cat, dog, fish, snake

<!-- Structured comma list, should be separated -->
Cat, Dog, Fish, Snake

<!-- This should not be separated-->
Hello, `Ask Me` Anything You Need

<!-- This is not officially supported as separator splitter-->
A / B / C / D / 

<!-- This should be separated -->
A - B - C - D

<!-- This should be separated differently, keeping the bullets in text nodes -->
A • B • C • D

<!-- This should not be separated, has no spaces -->
A|B|C|D

<!-- This should not be separated -->
a-b-c-d-d-f-g

<!-- This should be separated keeping the bold labels -->
**Bold one | Bold two | Bold three | Bold four**

<!-- This should be separated keeping the bold labels and plain text -->
**Bold text** - Not bold text

<!-- This should be separated keeping all text-style labels and plain text -->
**A bold** - B regular - *C italic* - `D code`

<!-- This should be separated keeping all text-style labels and plain text -->
**A bold - B bold** -  `*C bold code* - D regular code`

<!-- This should be separated -->
⭐ Popular | 🚀 entrepreneurship | ⚛️ science | 🍎 food | 🪴 lifestyle

<!-- This should be separated keeping the heading context and text-styles -->
# **⭐ Popular** | 🚀 entrepreneurship | ⚛️ science

<!-- A glued colon is text, not a key-value: this stays one line -->
key:value 1, key:value 2, key:value 3

<!--Comma list, splited-->
Beta, Gamma

Beta\, Gamma

<!--K-V Comma list, value splited-->
Alpha: Beta, Gamma

Alpha: Beta\, Gamma

<!--Vertical bars, Comma list, Separator should split first, comma list split last and keep coma list grouped -->
Alpha | Beta, Gamma

Alpha | Beta\, Gamma

<!-- Col separator. Beta, Gamma goes second line, splited-->
Alpha : Beta, Gamma

Alpha : Beta\, Gamma

<!-- Dashes -->

Alpha - Beta, Gamma

Alpha - Beta\, Gamma

Alpha - Beta, Gamma - Delta

Alpha - Beta\, Gamma - Delta

<!--Spring -->

Alpha ... Beta

Alpha ... Beta, Gamma

Alpha ... Beta\, Gamma

Alpha ... Beta, Gamma ... Delta

Alpha ... Beta\, Gamma ... Delta


<!-- content separator -->
___

<!--K-V Datapoint  -->
key:$10,000 | key:$10,000 | key:$10,000

<!-- content separator -->
___

<!---->
450 : ___Project done___ |  35 : ___Happy users___ | 9 : ___Get Awards___ | 6k : ___Cup of coffee___

<!-- content separator -->
___

<!-- A glued colon is text: three segments, none of them a key-value -->
key:value 1 | key:value 2 | key:value 3

3. **Meeting Notes - February 2026.pdf** - February 4, 2026 at 8:15 AM

___

<!-- Display value, then a pill and a muted tail. The tier must not leak into
     what follows: no literal backtick or underscore anywhere -->
👤 Customers: ___1,293___ - `⬇ +36.8%` : _vs last month_

💳 Balance: ___256k___ - `⬆ -36.8%` : _vs last month_

<!-- The same ladder without the key, so the pill and the muted tail separate -->
1,293 - `x` : _vs last month_

___1,293___ - `x` : _vs last month_

K: ___1,293___ - `x` : _vs last month_

<!-- The asterisk spelling of the same line: no tiers, but no debris either -->
***1,293*** - `x` : *vs last month*

<!-- The comma belongs to the date, not to a list, so these separate on the
     separator. All three spellings must agree — the classifier used to call
     only the colon one structured -->
🔴 - **User Research on Web** - Feb 28, 2020.7:00 pm

🔴 | **User Research on Web** | Feb 28, 2020.7:00 pm

🔴 : **User Research on Web** : Feb 28, 2020.7:00 pm

<!-- ...but a real comma list still wins over a stray dash: the "and" keeps it
     prose, so this stays one leaf -->
**Labrador Retriever** - Friendly, outgoing, and active companion

<!-- A spaced colon stacks inside a key-value VALUE too. Here the value never
     reaches a separator split, so the colon is its only structure -->
K: A : B

<!-- ...and here it does: the first segment stacks, the emoji stays alongside.
     The colon used to survive as a literal ': days' leaf -->
K: 92 : days - ⬇

<!-- Starts and ends with `_` but is NOT one wrap: two spans either side of a
     separator, each keeping its own tier -->
_A_ - _B_

<!-- Whole-line wraps that DO propagate, to every segment including the middle -->
***A | B | C***

~~A | B | C~~

`A | B | C`


<!-- Datapoint not split, ok -->

- 🔴 - **User Research on Web** : _Feb 28, 2020.7:00 pm_

<!-- Datapoint not split, ok-->
- 🔴 
  **User Research on Web**
  _Feb 28, 2020.7:00 pm_

<!-- content separator -->
---

💳 Balance: ___256k___ - `⬆ -36.8%` : _vs last month_

<!-- This should be separated as segemnts-->
key:value - plain text - plain text

<!-- Simply remove the colon : -->
_Intro_:
Simply text, not key-value pattern

<!-- Block and text, segment by `|` -->
`⬇ +36.8%` | vs last month

<!-- Mixed segments-->
A - B | C - D

A • B : C • D

A : B • C : D

<!-- This should be separated as k-v segments keeping text style -->
**Yield:** About 60 cookies | **Prep time:** 15 min | **Bake time:** 10 min

<!-- This should be separated as datapoint and text segment keeping text style -->
### **8:00 AM - 9:00 AM | Registration & Breakfast**

<!-- Mixed k-v, datapoint, comma-list and text, all separated  -->
**8. Tacos El Güero**
- **Rating:** 4.5/5
- **Location:** República de Brasil, Centro
- **Cuisine:** Street-style tacos


February 03, 10:26 AM

February 04, 9:17 PM

<!-- This should not split, investigate -->
February 04\, 9:17 PM

Fri, Aug 14 - Sun, Aug 16

Fri, Aug 14 \- Sun, Aug 16

"Fri, Aug 14 - Sun, Aug 16

<!-- -->

---

- 🛍️ - **Netflix Subscription** : February 04, 9:17 PM ... **-$199.00** : Subscription

---

- 🛍️ **Netflix Subscription** : February 04, 9:17 PM ... **-$199.00** : Subscription

---

- 🛍️ - **Netflix Subscription** : February 04\, 9:17 PM ... **-$199.00** : Subscription

---

<!--Comma list-->

One, Two, Three, Four, Five

One\, Two\, Three\, Four\, Five


<!--This should not be separated, since content are inside of quote marks -->
"Mahmoud Ajjour, Aged Nine"

<!--This should not be separated. -->
(Mon-Fri)

<!--This should not be separated, is a datapoint alone (day range) and has no spaces - -->
Mon-Fri

<!-- This should not be separated, is a datapoint alone (quantity) -->
3 points

<!-- This should be separated -->
↗️ +3 points

<!-- This should not be separated -->
(↗️ +3 points)

<!-- This should not be separated, is a datapoint alone, star rating -->
4.8/5.0 ⭐

<!-- This should not be separated, protected by quote marks -->
"11 AM"

<!-- This should not be separated -->
OAX-2024-789456

<!-- This should not be separated -->
__OAX-2024-789456__

<!-- This should not be separated, protected by quote marks -->
(9.5 in × 13 in)

<!-- • separators should be removed -->
[Portfolio](https://alexandrastone.design) • [LinkedIn](https://linkedin.com/in/alexandrastone) • [Dribbble](https://dribbble.com/alexstone)

<!-- This should not be separated, protected by backtick inline code -->
`**A bold code** - B code`

<!-- This should not be separated, protected by single quotes -->
'**A bold code** - B code'

<!-- Should be separated by dash first, then, split emoji-->
🟢 Gained - 🔴 Lost

<!---->
Server-side language: `cURL` | Stripe CLI | Ruby | Python | PHP | Java | Node.js | Go | .NET

<!-- Mixed content segments -->
A - [Link](/link) - ⭐ - 5/5 - **Bold**

<!-- TODO: Include image in segment, it will fail, because the images are separated early.. -->

<!-- -->

8:00 AM \- 9:00 AM

8:00 AM \- 9:00 AM

Fri, Aug 14 - Sun, Aug 16

Fri, Aug 14 \- Sun, Aug 16

<!-- Col - Row syntax -->

<!-- Colon = column split: stacks its pieces, binds TIGHTER than | and - -->
A : B

<!-- | splits into 3 columns; the middle one stacks, `___` drawing a rule -->
A | B : ___ : C | D

<!-- - splits into 2 columns, each stacking -->
A : B - C : D

<!-- Key-value keeps the colon TIGHT to the key — this is still a k-v -->
Key: value

<!-- Key-value as dp-->
Key: 8:00 AM - 9:00 AM

Key: __8:00 AM - 9:00 AM__

<!-- Col syntax as dp-->
_Key_ : __8:00 AM - 9:00 AM__

Key : 8:00 AM - 9:00 AM

<!-- ...and this one is a column split, not a k-v -->
Key : value

92 : days - ⬇

days - ⬇

<!-- Metric shapes: the number stacks over its label -->
## ✔ - 94% : Accuracy

## 92 : days - ⬇

## Heading
92 : days - ⬇

<!-- Heading separator -->
## 
92 : days - ⬇


<!-- Heading separator -->
## 
<!-- Not split: the colon is inside a datapoint, and has no space before it -->
8:00 AM - 9:00 AM

## 

Check-in\: 3 PM \| Check-out\: 11 AM


_Dates_ : Fri, Aug 14 \- Sun, Aug 16

## 


<!-- A THEMATIC BREAK WRITTEN AS A LIST ITEM.

     Behind a list marker all three spellings collapse to a painted RULE: the
     three tools are a top-level distinction, and inside a list what is wanted
     is a divider. The marker itself is not drawn.

     The split follows CommonMark, whose rule is "three or more MATCHING
     characters" and which outranks a list item — so a UNIFORM run is a break
     however much it looks like a bullet (`- ---`, `* ***`, `- - -` keep their
     own spelling's meaning), while a marker followed by a DIFFERENT break
     character is a list item holding a break, and that is what becomes a rule. -->

<!-- Rule, no bullet drawn -->
- a
- ---
- b

<!--TODO: Group spacing here-->

<!-- Rule -->
* a
* ---
* b

***


## 

<!-- Rule -->
1. a
1. ---
1. b

***

## 

<!-- Rule -->
+ a
+ ---
+ b

***


## 

<!-- Rule too: inside a list, not an invisible break -->
- a
- ___
- b

***

## 

<!-- Rule too: inside a list, it does NOT close the section -->
- a
- ***
- b
