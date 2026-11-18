---
name: profile
description: One person, artist, album or podcast as the subject, its big picture above its name and a line or two; use for a profile, a contact card or the item the answer is about.
---
# Profile

**Use for:** one someone or one cover the answer is about, such as a contact, an artist or an album. **Not for:** several people in a list, where each picture is small and beside its name (`people`).

```markdown
![Alex Foster](alex.jpg?md2ui.max_width=250&md2ui.aspect_ratio=1:1&md2ui.shape=circle&md2ui.content_align=center)
... **Alex Foster** ...
... alex.foster@mail.example ...
... _CEO at Brightline_ ...
... [📞](agent:call?id=alex) *[✉️](agent:mail?id=alex)* *[💬](agent:message?id=alex)* ...
```

**Why each marker**
- The picture is the subject, so it draws big at `250`, above its text — `images.md`.
- Someone is a `1:1` circle. An album, song or podcast is a `1:1` square: drop `shape` — `images.md`.
- `content_align=center` centres the picture, and a `...` on each side of a line centres that line under it. An artist or an album can stay at the left: drop both — `images.md`, `structure.md`.
- The actions share one line, so they sit side by side: the first the main icon action, the others icon actions, in the theme's spellings — `guide("theme")`.
