---
name: inbox
description: Unread messages or notifications, sender over subject with the time at the edge; use when summarising what arrived.
---
# Inbox

**Use for:** 3–6 recent messages or alerts, newest first. **Not for:** one message's full text (write prose) or a conversation thread.

```markdown
## Inbox ... `3 unread`

- **Maya Chen** : Draft budget for next quarter ... _9:14 AM_
- **Jordan Lee** : Can we move Thursday's call? ... _8:02 AM_
- **Sam Ortiz** : Photos from the offsite ... _Yesterday_

[Open inbox](agent:open-inbox) *[Mark all read](agent:mark-all-read)*
```

**Why each marker**
- ` : ` stacks the sender over the subject, and ` ... ` sends the time to the edge — `dashboards.md`, `structure.md`.
- `_…_` mutes the time — `text.md`.
- The count in the heading is a chip on a spring: metadata, not a button — `structure.md`.
- Actions are `agent:` buttons below the list, not links in a subject — `elements.md`.
- A subject keeps its commas: a comma is punctuation and never divides a line — `structure.md`.
