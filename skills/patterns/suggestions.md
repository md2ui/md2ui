---
name: suggestions
description: A few short next steps the user can tap instead of typing, all on one centred line; use for follow-ups, filters or replies after an answer.
---
# Suggestions

**Use for:** three to eight replies of a few words each, any of which the user might send next. **Not for:** options that each need a line of explanation (`choices`), or the one action the page is for (a button).

```markdown
## Your soup, adjusted for 2

... *[Make it vegetarian](agent:adjust-recipe?change=vegetarian)* *[Add a side salad](agent:adjust-recipe?change=side)* *[Shopping list](agent:shopping-list)* *[Swap the oven for a pan](agent:adjust-recipe?change=pan)* *[Freeze the rest](agent:adjust-recipe?change=freeze)* ...
```

**Why each marker**
- All the suggestions are written on one line, so they flow into rows and wrap at any width.
- ` ... ` at both ends centres the run, and each wrapped row stays centred.
- They are peers, each a quieter action the page is not for, in one spelling: the theme's, `guide("theme")`.
- Each is an `agent:` link, so a tap comes back to you as that reply.
