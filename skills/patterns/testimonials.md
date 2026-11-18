---
name: testimonials
description: What people say about a product or service, a card per quote with its rating and who said it; use for testimonials, endorsements or customer quotes.
---
# Testimonials

**Use for:** 2–6 quotes from named people, each with who they are.
**Not for:** reviews the user reads to decide on a purchase, with dates and a score summary (`reviews`); one quote inside an article, which is a `>` quote.

```markdown
## What teachers say

### 
★★★★★
The lesson plans saved me hours every week, and my students ask for the next one.

![Maria Lopez](https://images.example.com/people/maria-lopez.jpg?md2ui.max_width=40&md2ui.aspect_ratio=1:1&md2ui.shape=circle) - **Maria Lopez** : _Grade 5 teacher_

### 
★★★★☆
Clear, short and easy to adapt. I would like more science units.

![Daniel Kim](https://images.example.com/people/daniel-kim.jpg?md2ui.max_width=40&md2ui.aspect_ratio=1:1&md2ui.shape=circle) - **Daniel Kim** : _Head of science_
```

**Why each marker**
- Each quote is an untitled `### ` card, so the run grids: the quote is the card's subject and needs no title — `structure.md`.
- The stars are written as text, `★★★★☆`: the rating, read before the quote.
- Who said it is the `people` row: a small `1:1` circle at `40`, the name over the role. The person is secondary to the quote, so the picture stays small — `images.md`.
- No button per card: a quote is read, not acted on.
