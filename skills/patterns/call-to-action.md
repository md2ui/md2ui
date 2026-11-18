---
name: call-to-action
description: The closing invitation of a page, the line that earns it and the one action it asks for; use at the end of a landing page or a plan.
---
# Call to action

**Use for:** the last section of a page that makes a case, asking the user to take its main step.
**Not for:** a suggestion beside an answer, with a dismiss (`offer`); a page's opening headline (`hero`); a question with several answers (`choices`).

```markdown
## Ready for your first lesson?
Twelve teachers near you have openings this week, from beginner to grade 8.
[Find a piano teacher](agent:find-teacher?instrument=piano) *[Talk to us first](agent:contact)*
```

**Why each marker**
- The title is the invitation itself, and the line under it is the reason, from the user's own data.
- A project may give the closing call its own section style; its styles, if any, are in `guide("theme")`.
- The main button is the action the page is for, at the section's foot; one quieter alternative may sit beside it.
- No blank lines: the three lines are one group, so the card stays one block.
- Signing up is the button itself: an `agent:` action you complete with your own tools, or an `https:` or `mailto:` link that opens the platform's own sign-up.
