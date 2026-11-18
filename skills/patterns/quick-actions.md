---
name: quick-actions
description: A row of the few things the user can do now, each an icon button over its word; use for call, message, share or play controls on one item.
---
# Quick actions

**Use for:** two to five actions on the item the answer is about. **Not for:** navigation between pages, or an action that needs its label to be understood (write a button with text).

```markdown
... *[📞](/call)* ...
... Call ...

... *[💬](/message)* ...
... Message ...

... *[🎬](/video)* ...
... Video ...
```

**Why each marker**
- A link whose label is only an emoji is an icon button. The row's actions are peers, each an icon action in one spelling; the main icon action is for the one the user came to do. The spellings are the theme's: `guide("theme")`.
- ` ... ` at both ends centres the button and its word over each other, and the blank lines make each pair one action in a row.
- The word is the label the icon cannot say alone. Keep it to one word.
