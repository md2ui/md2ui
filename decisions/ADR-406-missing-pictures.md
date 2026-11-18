# ADR-406: Missing pictures — a source is a URL, an empty one is left out, a named placeholder stands in

**Status:** active
**Domain:** renderer
**Read when:** an item has no picture in the data, or sits among items that have one; an image
shows initials, an icon or a fill instead of its picture; or you are about to give image
sources a scheme of md2ui's own (`logo:`, `avatar:`, `og:`), give `![alt]()` another meaning,
or add another way to stand in for a missing picture.

## Decision

**An image's source is a URL:** one the data brought, or one a tool, connector or plugin API
returned, through a second request if that is what it takes. md2ui resolves nothing by name
and derives nothing (no logo lookup, no initials from a name). The core note teaches agents
to get the picture from their tools (`skills/README.md`, *Include the pictures*).

**An empty source, `![alt]()`, is a picture the author left out on purpose.** It groups as an
`image`, so the item keeps its picture box and its place in a run, and the run's params,
written on its first picture alone, reach it. Nothing is fetched. It paints a quiet box: the
picture background only, shaped like a picture, with no cross and no label. A picture
therefore has three states, one look each: still loading (the loading placeholder), failed
(the broken placeholder), left out (the quiet box).

**An image may name a placeholder the theme declares** (`?md2ui.placeholder=<name>` or
`<name>:<text>`), painted instead of the default look whenever it has no picture to show; once
a URL's picture loads, the picture wins. It is opt-in per image, declared by name in THEME.md,
and three reserved names restyle md2ui's own three states. It is paint only: no box moves, and
the parameter is not part of a picture's layout kind (`image_params.PAINT_PARAMS`), so runs
and grids are unchanged. The keys are in `THEME_GUIDE.md` §7, *Named placeholders*.

## Reason

- **A reply must read as ordinary Markdown anywhere.** A tool's `https:` URL works in every
  client; an md2ui scheme is a broken image everywhere else. An empty source is valid
  CommonMark and the spelling agents already reach for; `?md2ui.*` params are stripped before
  fetching, and another client shows the alt text.
- **Resolving pictures by name hurt more than it helped.** A resolver missed often (sites
  refusing the request drew initials) and sometimes drew a wrong picture (a product resolving
  to its parent's sign-in icon). Official sources exist, and agents use them once told to.
- **Resolving is cross-site by construction.** A browser client cannot read another site's
  HTML to find its icons or `og:image`, so it would need a fetching proxy, itself an exposure;
  and every viewer's client would tell third parties which brands and emails a page shows.
- **A pictureless item broke its run.** In picture rows an item without a picture is another
  kind of item, so the run ended there and the pictures after it lost the run's crop. Writing
  the picture empty keeps the item the same kind as its neighbours, with no change to what a
  run is (ADR-301).
- **A missing picture is common, and the default looks only say why it is missing.** An author
  wants something that still identifies the item — initials on a colour, as mail and chat
  clients draw them. The author writes that text, like every other value.
- **By name, so agents choose by meaning.** A named placeholder is one declared thing in
  THEME.md with one row in MEANINGS.md (ADR-501), so a theme can offer several (people, brands,
  media). Agents see placeholders only through those rows.
- **A picture the author did not write is never drawn.** An empty source or a placeholder name
  is something the author wrote.

## Alternatives rejected

- **Named image sources** (`logo:<domain>`, `avatar:<email>`, `og:<link>`, resolved by the
  client with initials on a miss). Built and removed, for the reasons above.
- **Keeping the resolver for hand-written pages only.** The cross-site, privacy and
  portability costs fall on every client whoever writes the source, and an author can paste
  the URL.
- **Keeping `og:` only, on a link a tool returned.** Still client-side fetching of another
  site's page; an agent can fetch the page with its own tools and write the URL it finds.
- **A reserved URL for "no picture"** (`![alt](md2ui:no-picture)`). One more spelling to teach
  and forget, an unknown scheme degrades to a broken image in other renderers, and a forgotten
  URL should draw the same box anyway.
- **A real file as the placeholder.** Works only by accident, and a repo path means nothing to
  another client.
- **Reusing the broken placeholder for a left-out picture.** It would read as an error; the
  absence is meant.
- **A scheme or the alt text to carry a placeholder.** A scheme is a broken image elsewhere,
  and the alt text is the picture's name.

## Constraint created

- A forgotten URL draws the same quiet box as a deliberate absence. That is accepted: it is
  honest, and better than drawing the literal Markdown.
- Placeholders apply to Markdown images only: an image card's photo and a theme background
  image keep md2ui's own fallbacks.
- Fixed colours (`## Fixed colors`) and colour replacements do not yet apply to a
  placeholder's fill or text.
- md2ui-ts follows: the same grouping, the same three states.

## Reconsider when

- Image cards need a placeholder for their photo.
- A theme needs a placeholder's colour pinned to a person wherever they appear: that is
  `## Fixed colors` keyed by the text.
