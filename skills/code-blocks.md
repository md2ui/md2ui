---
name: md2ui-code-blocks
description: Author fenced and indented code blocks in md2ui, and select syntax highlighting explicitly.
---

# Code blocks

Use a code block when the source itself is part of the answer. md2ui preserves its spaces,
line breaks, Markdown-looking characters, and HTML-looking text as literal code; none of them
become headings, links, comments, datapoints, or other document structure.

## Fence it and name the language

Put the Pygments lexer name immediately after the opening fence:

````md
```python
def greet(name: str) -> str:
    return f"Hello {name}"
```
````

Backtick and tilde fences both work. A class-style info string is accepted too:

````md
~~~{.typescript}
const ready: boolean = true;
~~~
````

md2ui uses the first info-string word and never guesses a language from the source. An absent
or unknown language therefore renders as plain code. This is deliberate: write the language
when syntax colour carries meaning.

A fence may also be the content of a list item:

````md
- ```html
  <!-- This remains literal source -->
  ```
````

Four-space or tab-indented Markdown code blocks work without a language:

```md
    no lexer is selected
    every line uses the plain code colour
```

Inline backticks are different. `` `Draft` `` on its own is a chip, and a backtick span in a
sentence is a text marker; neither is a code block. See [`text.md`](text.md).

The code font, the token colours and the surface are the theme's.

## Layout behavior

Code never wraps. The block fills the width it is given, and a line longer than that is cut at
the block's right edge, which fades out. A long line never widens the page or squeezes the
content around it. A long listing shows its first lines, 20 unless the theme says otherwise, and
fades where it is cut.

Nothing is lost. In the md2ui window a reader scrolls a cut line sideways, and every block has a
copy button that copies its whole source, including the lines below the cut. So write code as it
really is: do not break long lines or shorten a listing to make it fit. A render shows each block
unscrolled, with its cut and fade; that is the block working, not something to fix.

In a `:::` row a code block is a cell like any other. Beside a taller neighbour it takes the
row's height and shows more of its lines.

**A code block with a title** is a heading glued to the fence: the section is the panel, and
its heading the title strip. Leave the copy button off the heading — every block has one unless the theme turns it off:

```md
### Initialize the client
```ruby
client = Parcel::Client.new("pk_test_...")
```
```

Before sending, render one known-language block and one plain block.
