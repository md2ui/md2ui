# Link destinations

<!-- A destination follows CommonMark. A bare one holds no space, so this is
     not a link: it draws as written, brackets and all. -->
[Spaced](/my file)

<!-- Angle brackets carry a space: a link to `/my file`. -->
[Angled](</my file>)

<!-- A title after the destination, in any of its three quotings: a link to
     `/x`, the title dropped. -->
[Double](/x "Title") [Single](/x 'Title') [Paren](/x (Title))

<!-- Balanced parentheses stay inside the destination: a link to `/x(1)`. -->
[Balanced](/x(1))

<!-- In prose, a rejected link stays text and its label does not run on into
     the next link: only "the good one" is a link. -->
See [the spaced doc](/my file) and [the good one](/c) here.
