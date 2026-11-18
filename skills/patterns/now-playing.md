---
name: now-playing
description: What is playing now, its progress, and transport controls that come back to you; use for media or a running timer.
---
# Now playing

**Use for:** one current track, episode or timer. **Not for:** a queue or playlist (`status-list`, `feed`).

```markdown
## Now playing

__Evening Tide__
_The Harbor Lights_ - _Coastal Nights_

Elapsed: 45%

... *[⏮️](agent:previous-track)* [⏸️](agent:pause) *[⏭️](agent:next-track)* ...
```

**Why each marker**
- `__…__` is the Lead-tier title, and `_…_` the Muted line under it. ` - ` splits artist from album; each piece carries its own `_…_`, since a dash inside one styled span reads as part of a name — `text.md`.
- `Elapsed: 45%` on its own draws a progress bar — `dashboards.md`.
- A link whose label is only an emoji is an icon button — `elements/icon-buttons`.
- Pause is the main icon action; the skips are icon actions beside it. Their spellings are the theme's: `guide("theme")`.
- A ` ... ` at each end of the line centres the controls — `structure.md`.
