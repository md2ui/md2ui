---
name: figure-tiles
description: A run of measured details about one thing, each a tile with its name over its figure and unit; use for the readings beyond the few that lead: a trip, a night's sleep, a machine, the weather.
---
# Figure tiles

**Use for:** 4–8 readings of one thing, each worth a glance. **Not for:** the few figures that lead (`kpis`), or attributes that describe what a thing is (`specs`, which this resembles with lighter values).

```markdown
## Trip details

### Distance
___212___ - _km_

### Average speed
___74___ - _km/h_

### Energy used
___31___ - _kWh_

### Driving time
___2:51___

### Charge left
___38%___

### Stops
___1___
```

**Why each marker**
- Each reading is a `###` of its own, so each is a tile, and the run of matching tiles grids — `repetition.md`.
- The figure is the tile's primary field: `___…___`, the Display tier — `text.md`.
- The unit is muted, after ` - `, so the figure stays a bare number beside it.
- A reading with no unit keeps the figure alone; every tile still has the same two lines.
