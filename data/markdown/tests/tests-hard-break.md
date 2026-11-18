# Hard line breaks

<!-- A trailing backslash breaks the line INSIDE one text: one key-value, whose value draws on two lines. -->
**Address:** 12 Main Street\
Springfield, IL 62701

<!-- A paragraph that wraps on its own, then breaks by hand after "here". -->
A long paragraph that should wrap naturally at the card edge and then break by hand right here\
and continue on its own line.

<!-- A list item continues on its indented line; the next item is still its own. -->
- First item\
  its second line
- Second item

<!-- The break sits inside the second segment; the separator still divides the line. -->
Alpha | Beta\
Gamma

<!-- Breaks chain: one text on three lines. -->
Line one\
Line two\
Line three

<!-- An escaped backslash draws one backslash and breaks nothing. -->
Ends in a backslash \\
The next line is its own text.

<!-- No line to join: the backslash is drawn as written. -->
Before a list\
- a list item

<!-- Two trailing spaces do nothing: these stay two rows. -->
**Order:** 114-9283746  
**Placed:** March 26, 2026  

<!-- A heading continues as a text does: three lines, one level-2 heading. The last line, with nothing to join, draws its backslash. -->
## Heading line 1\
heading line 2\
heading line 3\

<!-- A blank line ends the heading: line 2 draws its backslash and line 3 is its own text. -->
## Heading line 1\
heading line 2\

heading line 3\

<!-- A continued heading's {#id} ends its last line. -->
## Styled heading\
on two lines {#hard-break-1}

Body under the styled heading.
