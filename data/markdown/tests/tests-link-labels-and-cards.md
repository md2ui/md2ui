# Link labels and cards

<!-- Brackets inside a link's label must balance. Only "b" is a link, to `/c`;
     "[a] text" draws as written. -->
Read [a] text [b](/c) here.

<!-- One balanced pair inside the label is part of it: a link to `/c`. -->
See [a [nested] label](/c) now.

<!-- A link card's destination follows the same grammar as a link's. A bare
     space ends it, so this is no card: the image and the caption draw, with
     the brackets and the destination as text. -->
[![](https://example.com/card.png) Caption
on two lines](/my file)

<!-- Angle brackets carry the space: a card linking to `/my file`. -->
[![](https://example.com/card.png) Caption
on two lines](</my file>)

<!-- An image's title is not part of its URL: the photo loads (a real,
     cached image, so a broken URL would show the placeholder instead). -->
![Titled](https://upload.wikimedia.org/wikipedia/commons/e/e3/Che_ne_saj.jpg "A title")

<!-- The same for an image card's background. -->
![
## Hero

Body text over the background.
](https://upload.wikimedia.org/wikipedia/commons/e/e3/Che_ne_saj.jpg "A title")
