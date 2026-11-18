---
name: itinerary
description: The legs of an upcoming trip or booking in order, each with its time and a detail; use for travel and reservations.
---
# Itinerary

**Use for:** 2–5 legs of one trip. **Not for:** one day's meetings (`agenda`).

```markdown
## Lisbon trip ... `Confirmed`

- ✈️ **Flight out** : Oct 3 at 8:05 AM ... `Seat 14C`
- 🏨 **Hotel check-in** : Oct 3 at 3:00 PM ... `2 nights`
- ✈️ **Flight home** : Oct 5 at 6:40 PM ... `Seat 9A`

[Add to calendar](agent:add-trip-to-calendar) *[Change a booking](agent:change-booking)*
```

**Why each marker**
- The heading's ` ... ` sends the booking status, a chip, to the right — `structure.md`.
- An emoji with no separator stays an inline glyph in the leg's title — `elements.md`.
- ` : ` stacks the leg over its time, and ` ... ` sends the seat chip right — `dashboards.md`.
- `Oct 3` is a prose date. `Oct-3` would draw a day tile — `structure.md`.
- Bookings change through `agent:` buttons — `elements.md`.
