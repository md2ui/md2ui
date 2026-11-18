---
name: goodbye
description: A closing card when the user ends the conversation or finishes a flow; use for a goodbye or a thank-you, never as a reply to a question.
---
# Goodbye

**Use for:** the last answer, when the user says goodbye or a flow is complete. **Not for:** a confirmation that still offers actions (use a status line and buttons).

```markdown
#### 

+++++

... *👋* ...

... ___Goodbye___ ...

... Have a nice day ...

+++++
```

**Why each marker**
- `#### ` with no title makes the card, and `+++++` gives it room above and below.
- ` ... ` at both ends centres each line.
- The icon is the one the goodbye is about, in the theme's spelling: `guide("theme")`. `___…___` is the Display line, and one short line follows it.
- For a thank-you, the glyph can sit inside the Display line instead, `___👋 Thank you___`, and grow with it.
