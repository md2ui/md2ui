---
name: reviews
description: Reviews of one product, a score summary first and then each review with its reviewer, date, rating and text; use for product, stay or app reviews.
---
# Reviews

**Use for:** what buyers or guests said about one thing, read to decide on it.
**Not for:** endorsements chosen to persuade, with no dates or score (`testimonials`); comparing several products (`comparison`).

```markdown
## Reviews

___4.6___
★★★★½
_Based on 212 reviews_

### 
![Sam Ortiz](https://images.example.com/people/sam-ortiz.jpg?md2ui.max_width=40&md2ui.aspect_ratio=1:1&md2ui.shape=circle) - **Sam Ortiz** : _3 days ago_
★★★★☆
**Warm and quiet, even on a full flight**
The fabric stays soft after a dozen washes, and the hood keeps the draft out.

### 
![Lena Fischer](https://images.example.com/people/lena-fischer.jpg?md2ui.max_width=40&md2ui.aspect_ratio=1:1&md2ui.shape=circle) - **Lena Fischer** : _1 week ago_
★★★☆☆
**Good, but runs small**
I ordered my usual size and had to send it back for a larger one.
```

**Why each marker**
- The score leads: `___4.6___` alone on its line is the hero number (around part of a line it is only emphasis); stars and a muted count follow — `text.md`.
- Each review is an untitled `### ` card of the same shape, so the run grids — `repetition.md`.
- The reviewer is the `people` row, a small `40` circle with the name over the date: secondary to the review, so the picture stays small — `images.md`.
- The headline is bold over its text, so it reads first; the rating is text stars, as the source gives it.
