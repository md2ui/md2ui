---
name: agenda
description: One day's timed events under a day tile; use when the answer is a schedule.
---
# Agenda

**Use for:** 3–6 events on one day. **Not for:** several days of travel (`itinerary`) or untimed steps (`steps`).

```markdown
## Today ... Mon-15

> 9:00 AM - Team standup

> 11:30 AM - Design review

> 2:00 PM - Client call

> 5:30 PM - Gym

[Add an event](agent:add-event?day=mon-15) *[Reschedule](agent:reschedule-day)*
```

**Why each marker**
- `Mon-15` is detected as a day tile, and ` ... ` in the heading sends it to the right — `dashboards.md`, `structure.md`.
- Each row is its own `>` quote with a blank line between, so each row can take its own bar from the theme — `structure.md`.
- ` - ` pairs the time with the title — `dashboards.md`.
- Keep every row the same `time - title` shape, so the rows read as one list.
- Changes are `agent:` buttons at the section's foot: the main action, then a quieter one, in the theme's spellings — `guide("theme")`.
