"""Which data-point types the PIPELINE detects, and why each one is there.

The third table in this cluster. ``detector_vocabulary`` says what a month name
looks like and ``detector_parsers`` says what a match means; this says which
types are worth scanning for at all. ``data_point_detector`` imports all three.

The rule, and ADR-102 is the record: a type is here because something consumes
it. Nothing is here because it might be useful.
"""

from md2ui.pipeline.data_point_types import DataPointType


# The pipeline's scope (ADR-102). Two reasons to be here, no third: a
# ``## Drawing elements`` family consumes the type, or the grouper turns it into
# a node. Everything absent is still DETECTED by ``detect_all`` — it is simply
# not paid for on every leaf of every document.
_DRAWING_TYPES = frozenset(
    {
        # drawn
        DataPointType.DATE,  # ### Dates -> the day chip
        DataPointType.RATIO,  # ### Ratio Bars / ### Unit Ratios
        DataPointType.SCORE,  # ### Unit Ratios (`750/1800 Kcal`)
        DataPointType.PERCENTAGE,  # ### Key Value Bars, ## Charts
        # `## Fixed colors -> ### Datapoints` pins a color by detected type
        # (`render_colors._dp_pin`), so each of these five is read on every leaf.
        DataPointType.CURRENCY,
        DataPointType.NUMBER,
        DataPointType.QUANTITY,
        DataPointType.FILE_SIZE,
        DataPointType.RATE,
        DataPointType.CHANGE,  # ## Fixed colors -> `change up` / `change down`
        # structural: these become NodeType.EMOJI / NodeType.LINK
        DataPointType.EMOJI,
        DataPointType.LINK,
    }
)


# Types that draw NOTHING and are kept anyway, because _remove_overlaps keeps the
# LONGEST match: drop one and a shorter drawing pattern wins the span instead, so
# the pipeline draws something wrong rather than nothing. Each line shows what
# the span becomes without the type (scripts/audit_detector_scope.py measures it):
#
#   url          `?w=1200` in an image URL      -> number 1200
#   measurement  `375°F`                        -> number 375
#   time         `8:00 AM`                      -> ratio 8:00, a PROGRESS BAR
#   range        `~15-20%`                      -> percentage -20%, NEGATIVE
#   dimension    `4032 x 3024`                  -> number 4032 + number 3024
#   ranking      `top 10`                       -> number 10
#   phone        `(555) 123-4567`               -> number 555
#   date_range   `January 12-28, 2026`          -> a DAY CHIP on January 12
#   quarter      `Q3 2024`                      -> number 2024
#   version      `v3.2`                         -> number 2
#   duration     `4 hours 35 minutes`           -> quantity + quantity
#   email        `john.smith@email.com`         -> url `email.com`
#
# EMAIL guards against a KEPT guard rather than a drawing: URL wins the tail
# of an address when EMAIL is not there to claim the whole thing.
#
# Re-run scripts/audit_detector_scope.py before removing any of these. The
# types in neither set (AGE, BLOOD_TYPE, FREQUENCY, IDENTIFIER, ORDINAL,
# STATISTICAL) change no span when dropped, which is why they are left out.
_GUARD_TYPES = frozenset(
    {
        # image     the alt text and the URL of `![alt, with a comma](p.png)`
        #
        # IMAGE is a guard and NOT structural, which is the whole distinction
        # this set exists for. It draws nothing and it never becomes a node by
        # this route -- `_split_images` does that, in the element walk, just
        # ahead of the link peel on each node.
        # It is scanned so the whole `![alt](url)` span is a PROTECTED RANGE
        # while the line is still one leaf, which is what stops the separator
        # and colon splits cutting inside it: the image split runs after
        # those passes.
        DataPointType.IMAGE,
        # drawing_element  `[ ]`, `[x]`, `[65%]` and their `[[..]](url)` forms.
        # The same kind of guard as IMAGE: the node is made after the line has
        # been read (grouper_sliders / grouper_drawing_elements), so the span
        # only has to survive the separator, spring and colon splits whole.
        DataPointType.DRAWING_ELEMENT,
        DataPointType.URL,
        DataPointType.MEASUREMENT,
        DataPointType.TIME,
        DataPointType.RANGE,
        DataPointType.DIMENSION,
        DataPointType.RANKING,
        DataPointType.PHONE,
        DataPointType.DATE_RANGE,
        DataPointType.QUARTER,
        DataPointType.VERSION,
        DataPointType.DURATION,
        DataPointType.EMAIL,
    }
)

_PIPELINE_TYPES = _DRAWING_TYPES | _GUARD_TYPES
