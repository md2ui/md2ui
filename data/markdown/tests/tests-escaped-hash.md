<!-- An escaped hash `\#` is CommonMark's literal `#`: the line is body text
     that starts with `# `, never a heading, wherever the line sits. -->

<!-- A paragraph: text that starts with a hash, not an H1. -->
\# Not a heading, a paragraph that starts with a hash

<!-- A list item: the escaped item is an ordinary item drawn with its hash;
     the authored `- # Title` beside it is still a heading inside its item. -->
- \# Not a heading, an item that starts with a hash
- # A heading inside an item
- A plain item

<!-- In a heading: `## \###` is a level-2 heading whose text starts with
     three hashes. -->
## \### three hashes of text
