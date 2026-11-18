---
name: md2ui-includes
description: Includes — pages and figures this server builds from live data; when to use one, and how to write its line.
---

# Includes

An include is Markdown this server builds from its own live data. A line holding only
`{{name args}}`, with a blank line before and after, is replaced by it before the user sees
the page, and `check` and `preview` read the replaced page.

- **Use an include for every page or figure it covers,** instead of writing it: what it draws
  comes from the data, so no price, total, status or time passes through you. Never retype a
  figure an include draws, beside it or in its place: a reason says cheaper or sooner; the card
  shows by how much.
- **When an include is the whole answer, your reply is the include line alone.** No sentence
  before it: the page says it already. Add words only when they tell the user something the
  page does not — the answer to their question, why you chose these items.
- **Your own Markdown mixes with includes:** a heading or one sentence above one, a section of
  your own below it, several on one page, each alone on its line.

  ```md
  Rain clears by noon, so the walk fits the afternoon.

  {{forecast city=Lisbon days=3}}

  ## What to bring
  - A light jacket
  ```

- **Args** follow the name as the list shows them: `key=value`, `key="two words"`, or bare
  words such as ids, taken from your tools.
- **Only the includes listed below exist.** Any other name draws nothing, and `check` reports
  it as an error. Inside a sentence, `{{…}}` is text.
- **A request for writing stays writing.** An explanation, advice, a comparison with its
  reasons: write it as these notes say, and use an include only for the items or figures it
  draws.

## This server's includes
