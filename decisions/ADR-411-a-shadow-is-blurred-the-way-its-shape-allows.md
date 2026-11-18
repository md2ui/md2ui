# ADR-411: A shadow is blurred the way its shape allows, and a variant's shadows replace Primary's

**Status:** active
**Domain:** renderer
**Read when:** you change how a shadow is painted (`render_shadows.py`), how a button, chip or
badge variant inherits shadows (`theme_model.inherit_shadows`, the variant replay in
`theme.py`), or `SHADOW_MAX_PER_KIND`; or you are asked for more shadow layers, a blur-free
shadow, or a different falloff for small corners.

## Decision

- **A rect or rounded rect is blurred as a rounded rect.** Its shadow clips with `clipRect` /
  `clipRRect` and draws with `drawRRect`, which Skia blurs as one small corner tile stretched to
  size. A rounded rect's inner shadow is drawn as its equivalent, "colour − blur(moved shape)":
  a layer clipped to the shape is filled with the colour and erased with the blurred moved
  rounded rect (`kDstOut`). An oval, a box cut by `within`, an `outline`, and a plain rect's
  inner shadow keep the path blur.
- **There is no small-radius exception.** Every rect and rounded rect takes the rounded-rect
  route, however small its corner.
- **A variant's shadows replace Primary's, kind by kind.** A button, chip or badge variant
  that declares an outer (or inner) shadow replaces Primary's outer (or inner) ones, and
  inherits the kind it declares none of: the rule its colour lists already followed. A
  variant switches a kind off with one transparent layer.
- **Layers per kind are capped** (`SHADOW_MAX_PER_KIND`). One past the cap is dropped, and
  `md2ui check --theme` names the block (`theme_lint.dropped_shadows`).

## Reason

Shadows are painted in the replay (ADR-401), so the window pays for them on every frame. A
path blur costs in proportion to the blurred area, so one soft layer on a page-sized panel
dominated a frame; the rounded-rect blur costs about the same on a badge and on a panel.

The rounded-rect blur's falloff is not the path blur's to the last bit: it differs by a few
levels on the rim, most on the inner rims of small-radius chips over a photo, and is not visible
side by side. `tests/shadow_tests.py` pins the drift against the path blur.

Variants used to inherit by appending to Primary's layers, so a variant's own were silently
lost past the cap, and every stacking case in the corpus was unintended: a small badge casting a
large element's glow, light buttons carrying a coloured pill's rims, a transparent layer meant
to switch an inherited shadow off doing nothing. Replacing per kind fixed all three and made
overflow impossible, so no "whose layers win" rule and no reset key were needed.

The cap sits above the deepest stack any theme uses, and low enough that a stack of inner layers
on a page-sized box stays cheap in the replay.

## Alternatives rejected

- **No blur at all: an analytic rounded-rect shadow as an SkSL shader** (Evan Wallace's). The
  most faithful and the slowest on Skia's CPU backend: the formula runs per pixel of the band,
  so a large soft layer cost more than the path blur it replaced. It wins on a GPU.
- **Gradients sampled from the falloff (a nine-slice of linear and radial gradients).** Not
  built: the only case left to win is an inner layer on a page-sized box, and its corners are an
  approximation.
- **Blurring only an edge band for inner shadows.** Superseded before it was tried: the
  rounded-rect route removed the area cost for the shapes that carry it.
- **Capping after the variant merge**, with a rule for whose layers win: it needed that rule
  and a reset key, and kept the unintended stacking.
- **A small-radius threshold keeping the path blur:** no speed at stake (a small corner is a
  small box), and a corner radius crossing the threshold would change the falloff for no reason
  an author could see.

## Constraint created

- **A change to the rounded-rect route moves pixels** across much of the render snapshot; it is
  explained in its change like any other, against the path-blur reference test.
- **Variant shadow inheritance lives in one function per element kind's path** — the button
  merge calls `inherit_shadows`; the badge and chip replay drops Primary's layers of a kind at
  the variant's first one — and the paths must agree.

## Reconsider when

- md2ui draws on a GPU: the analytic shader becomes the fast route.
- A design needs more layers of a kind than the cap: measure an inner layer on a page-sized
  rounded rect in the replay first.
