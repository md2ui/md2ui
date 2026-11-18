---
name: reference-list
description: Named fields, each with its type and a line about it, divided by rules; use for API attributes, config options or a glossary.
---
# Reference list

**Use for:** the fields of an object, the options of a command, the terms of a glossary. **Not for:** a few settings with values (`specs`).

```markdown
## The Shipment object

***`id`*** - _string_
Unique identifier for the object.

---

***`email`*** - _nullable string_
The email address the tracking updates go to.

---

***`insured`*** - _boolean_
Whether the shipment carries insurance cover.
```

**What the names mean here.** Inside this list, and only here:

| Write | Means |
|---|---|
| `` ***`id`*** `` | a field's name |

**Why each marker**
- ``***`name`***`` makes the field name a strong chip; ` - ` sets its type beside it, muted with `_…_` — `elements.md`, `text.md`.
- The description is glued under its name, so name and line are one entry — `structure.md`.
- `---` draws the rule between entries, and it keeps them in one column: without it, entries of 10–40 words grid two across — `repetition.md`.
