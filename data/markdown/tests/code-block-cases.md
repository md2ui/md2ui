# Code block cases

Every way a code block can be written, and every way it can be laid out. The captions avoid colons on purpose, since a colon in a sentence reads as a key and value.

## Writing a block

A fence names its language, and the language selects the highlighting.

```python
def greet(name: str) -> str:
    return f"Hello {name}"
```

A tilde fence works the same way.

~~~rust
fn main() {
    println!("hello");
}
~~~

A class-style info string names the language too.

~~~{.typescript}
const ready: boolean = true;
~~~

An unknown language renders as plain code.

```nosuchlanguage
this stays plain text in the code colour
```

A fence without a language renders as plain code.

```
plain code with no language
```

Four-space indentation makes a block without a language.

    indented code
    keeps every line

A fence can be the content of a list item.

- ```html
  <p>Inside a list item</p>
  ```

___

## Source stays literal

Nothing inside a block becomes document structure.

```md
# Not a heading
**Not bold** and [not a link](/nowhere)
<!-- not a comment -->
+++ not a spacer
::: not a column
| not | a table |
- not a list
___
```

Blank lines written at the start and the end are kept.

```

padded above and below

```

Tabs expand to four spaces.

```go
func main() {
	fmt.Println("tab")
}
```

Accented, wide and emoji characters.

```
naïve café, こんにちは 世界, 🚀
```

An empty fence.

```
```

___

## Lexers that once broke

A shell session on one line.

```console
$ gem install rake
```

A shell session on two lines.

```console
$ gem install rake
Successfully installed rake
```

YAML, whose token types no style lists.

```yaml
name: md2ui
features:
  - code blocks
```

___

## Too wide and too tall

A line longer than the block is cut at the right edge, which fades.

```bash
curl https://api.example.com/v1/payments -u "$API_KEY:" -d amount=2000 -d currency=usd -d source=card_example -d description="A payment long enough to run past any card"
```

One unbroken token longer than the block.

```
token_example_0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstu
```

A listing longer than twenty lines is cut after twenty, and the cut fades.

```python
line_01 = 1
line_02 = 2
line_03 = 3
line_04 = 4
line_05 = 5
line_06 = 6
line_07 = 7
line_08 = 8
line_09 = 9
line_10 = 10
line_11 = 11
line_12 = 12
line_13 = 13
line_14 = 14
line_15 = 15
line_16 = 16
line_17 = 17
line_18 = 18
line_19 = 19
line_20 = 20
line_21 = 21
line_22 = 22
line_23 = 23
line_24 = 24
line_25 = 25
```

A listing both too wide and too tall fades on both edges.

```python
row_01 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_02 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_03 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_04 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_05 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_06 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_07 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_08 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_09 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_10 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_11 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_12 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_13 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_14 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_15 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_16 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_17 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_18 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_19 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_20 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_21 = "a line that is long enough to run past the right edge of a narrow block, and further"
row_22 = "a line that is long enough to run past the right edge of a narrow block, and further"
```

___

## In rows

A short block beside a taller paragraph takes the row's height. Each row below is cut from its caption, or the caption would ride in its first cell.

___

```python
ready = True
```
:::1
A paragraph long enough to wrap onto several lines beside the code, so the row is taller than the block and the block has to stretch to meet it, ending where this paragraph ends.
:::1
___

A block cut at twenty lines beside a short neighbour sets the row's height.

___

```python
item_01 = 1
item_02 = 2
item_03 = 3
item_04 = 4
item_05 = 5
item_06 = 6
item_07 = 7
item_08 = 8
item_09 = 9
item_10 = 10
item_11 = 11
item_12 = 12
item_13 = 13
item_14 = 14
item_15 = 15
item_16 = 16
item_17 = 17
item_18 = 18
item_19 = 19
item_20 = 20
item_21 = 21
item_22 = 22
```
:::1
A short neighbour.
:::1
___

Two blocks side by side.

___

```json
{ "left": true }
```
:::1
```json
{ "right": true }
```
:::1
___

## In a card

A section holds a block with its prose, the way an answer explains a snippet.

```bash
uv run md2ui render content.md --width 767 --out render.png
```

The block sits inside the card's padding like any other element.
