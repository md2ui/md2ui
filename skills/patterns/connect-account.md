---
name: connect-account
description: Why you need an account or a connector, and the ways to give it; use before a task you cannot do until the user signs in.
---
# Connect account

**Use for:** the one sign-in a task is waiting on. **Not for:** asking permission for one action (`confirm`).

```markdown
### Connect your calendar

To find a free hour I need to read your calendar. I never change an event without asking.

[Connect your work calendar](https://accounts.example/connect) *[Use another calendar](agent:connect?provider=other)*

[`Not now`](agent:skip-connect)
```

**Why each marker**
- The body says what you will read and what you will not do, in a sentence.
- The usual way in is the main action; the other way is a quieter one, beside it.
- The way out is a minor action, apart on its own line. The spellings are the theme's: `guide("theme")`.
- An `https:` link opens for the user; an `agent:` link comes back to you — `elements.md`.
