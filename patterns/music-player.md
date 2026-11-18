---
name: music-player
description: What is playing now, as this theme's player card with the track over its artist, the progress and the transport controls; use when the answer is about one track playing.
---
# Music player

**Use for:** the one track playing now, with its controls. **Not for:** a track with its own cover art to show (an image card with the cover, `now-playing`), a list of tracks (rows), or anything that is not playing.

```markdown
## {#music-player-1}

**[🎵](agent:open-player)** ... **[📶](agent:output-device)**

___Low Tide Glow___
__The Paper Boats__

Elapsed: 12%

... ***[⏪](agent:previous-track)*** [⏸️](agent:pause) ***[⏩](agent:next-track)*** ...
```

**Why each marker**
- `{#music-player-1}` asks this theme for its player card: a photo background with light text, so the title stays readable — `MEANINGS.md`.
- The two icon buttons at the edges open the player and the output device; ` ... ` pushes them apart — `structure.md`.
- The track is the Display tier over the artist in the Lead tier — `text.md`.
- `Elapsed: 12%` draws the progress bar; the pause button is the main control, the skips quieter beside it — `elements.md`.
