---
name: confirm
description: A question before you act, what it will change, and the answers; use when you need the user's go-ahead to send, delete, pay or share.
---
# Confirm

**Use for:** one action you are about to take for the user. **Not for:** choosing between options that each need explaining (`choices`).

```markdown
### Send this reply to Dana?

Thanks, Thursday at 3 works. I'll bring the floor plans.

_To dana@studio.example, from your work account_

[Send](agent:send-reply?id=88) *[Edit first](agent:edit-reply?id=88)* [`Don't send`](agent:discard-reply?id=88)
```

**Why each marker**
- The title is the question, so the answers under it read as replies to it.
- The lines under it are what the action changes, quoted from what you will do.
- The answer you expect is the main action, the alternative a quieter one, the way out a minor action, so the three read in order of weight. Their spellings are the theme's: `guide("theme")`.
- Once answered, `mark` the answers — `elements.md`.
