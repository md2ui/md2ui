<!-- Don't parse this as link-->
`[Link](/link)`

<!--TODO: plan text -->
\`escaped\`

<!-- ? -->
***[Text `Chip`](/link)***

<!-- Don't parse this as image -->
`![alt text](photo.jpg)`


<!-- Don't parse this as link-->
This line `[Link](/link)` should be shown as mark text.

<!-- Don't parse this as image -->
This line `![alt text](photo.jpg)` should be shown as mark text.

<!-- Keep marker-->
Key with `backticks` inside: Value

<!-- Keep chip -->
`🫓 Chip as key`: Value

<!-- Chips -->

`Label`

*`Label`*

**`Label`**

***`Label`***

<!-- Emoji + text chips -->

`❤️ Label`

*`❤️ Label`*

**`❤️ Label`**

***`❤️ Label`***

<!-- Emoji chips -->

<!-- Main-->
`❤️`

<!-- Secondary -->
*`❤️`*

<!-- Tertiary -->
**`❤️`**

<!-- Quaternary-->
***`❤️`***


<!-- Sequenced, separate chips -->

`❤️` `Label` `❤️ Label`

*`❤️`* *`Label`* *`❤️ Label`*

**`❤️`** **`Label`** **`❤️ Label`**

***`❤️`*** ***`Label`*** ***`❤️ Label`***


<!-- Text -->


❤️ `Label` ❤️ Label

*❤️ `Label`* ❤️ Label

**❤️ `Label`** ❤️ Label

***❤️ `Label`*** ❤️ Label

<!-- Segmented -->

`❤️` - `Label` - `❤️ Label`

*`❤️`* - *`Label`* - *`❤️ Label`*

**`❤️`** - **`Label`** - **`❤️ Label`**

***`❤️`*** - ***`Label`*** - ***`❤️ Label`***

<!-- Boundaries (peel?)-->
Label inside `text`

*Label inside `text`*

**Label inside `text`**

***Label inside `text`***

Lorem ipsum `dolor sit amet,` `consectetur adipiscing` `elit`. Aenean at efficitur libero, sed cursus`nunc.

Lorem ipsum **dolor** sit ***amet***, `consectetur adipiscing elit`. *`Aenean at efficitur libero`*, sed **`cursus`** *nunc*.

<!-- In headings, single -->

# Heading 1 - `Label`

## Heading 2 - *`Label`*

### Heading 3 - **`Label`**

### Heading 4 - ***`Label`***

<!-- Full style -->

# Label `inside` text

## *Label `inside` text*

### **Label `inside` text**

### ***Label `inside` text***

<!-- mixed style -->

# Label `inside` text

## *Label* `inside` text

### **Label** `inside` text

### ***Label*** `inside` text

<!-- Segmented (explicitly separated)-->

# Label `inside` text

## *Label* - `inside` - text

### **Label** - `inside` - text

### ***Label*** - `inside` - text
