"""Contract C1 for the md2ui-ts port: JSON Schema for the grouping AST.

``GROUPING_AST_SCHEMA`` (JSON Schema draft 2020-12) describes what
``MarkdownGroupNode.to_dict()`` emits, at md2ui commit fee7e02db. It validates
the final tree and the tree after every grouper phase (fields absent early
simply do not appear). The node object is closed
(``additionalProperties: false``), so a new ``to_dict`` key fails validation.

Keeping it current. When ``to_dict`` changes:
  1. add / remove / retype the property in ``_PROPS`` below (``type`` and the
     data-point labels follow ``NodeType`` / ``DataPointType`` by themselves);
  2. re-export the fixtures and run the validation loop over every file;
  3. update the commit id above.
Enums are used only where the source documents a closed vocabulary; everything
else is a plain string. Payload dicts (``datapoint_payload``, ``drawing_element``,
``chart_data``) are typed on their known keys and stay open.
"""

from md2ui.pipeline.data_point_detector import DataPointType
from md2ui.pipeline.grouper_types import (
    _CHIP_UNDERSCORE_VARIANT_BY_LEN,
    _ELEMENT_VARIANT_BY_LEN,
    NodeType,
)

_NULL = {"type": "null"}
_STR = {"type": "string"}
_INT = {"type": "integer"}
_NUM = {"type": "number"}
_BOOL = {"type": "boolean"}
_STRS = {"type": "array", "items": _STR}

# Every NodeType, plus the root and the heading leaves, which are typed by name.
_NODE_TYPES = [t.value for t in NodeType] + ["root"]

_DP_TYPES = [t.value for t in DataPointType]


def _enum(*values: str, nullable: bool = False) -> dict:
    return {"enum": [*values, None] if nullable else list(values)}


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, _NULL]}


def _d(description: str, schema: dict) -> dict:
    return {**schema, "description": description}


# Read from the grouper's wrapper tables, so a variant md2ui can emit is never
# missing here: every element shares the asterisk ladder, chips add the
# underscore one.
_VARIANTS = tuple(_ELEMENT_VARIANT_BY_LEN.values())
_CHIP_VARIANTS = (*_VARIANTS, *_CHIP_UNDERSCORE_VARIANT_BY_LEN.values())
_LENGTHS = ("one_word", "very_short", "short", "medium", "paragraph", "long_paragraph")
_ALIGN = ("left", "center", "right")
_VALIGN = ("top", "center", "bottom")
_WEIGHTS = {"type": "array", "items": {"type": ["number", "null"]}}

_DATA_POINT = {
    "type": "object",
    "description": "One detected data point (the type is the label suffix).",
    "properties": {
        "label": {"enum": [f"dp_{t}" for t in _DP_TYPES]},
        "matched": _d("The matched source text.", _STR),
        "value": _d("Parsed value, JSON-safe (Decimal as float, datetime as ISO).", {}),
        "start": _d("Start offset in the node content.", _INT),
        "end": _d("End offset in the node content.", _INT),
    },
    "required": ["label", "matched", "value", "start", "end"],
    "additionalProperties": False,
}

_FEED_SLOT = {
    "type": "object",
    "description": "One feed slot: the words a feed may replace (grouper_feed_slots).",
    "properties": {
        "name": _d("The slot's name, the one a feed posts to.", _STR),
        "kind": _enum("text", "chip", "label"),
        "start": _d("Start offset in the node content.", _INT),
        "end": _d("End offset in the node content.", _INT),
    },
    "required": ["name", "kind", "start", "end"],
    "additionalProperties": False,
}

_PROPS: dict[str, dict] = {
    "node_id": _d("The node's tree path (a position, not an identity).", _STR),
    "content": _d("The node's text (markdown markers kept on leaves).", _STR),
    "type": _d(
        "NodeType value, root, or heading1..heading6 for heading leaves.",
        {"anyOf": [{"enum": _NODE_TYPES}, {"type": "string", "pattern": "^heading[1-6]$"}]},
    ),
    "fingerprint_hash": _d("Structural fingerprint; null until computed.", _nullable(_INT)),
    "children": _d("Child nodes in document order.", {"type": "array", "items": {"$ref": "#/$defs/node"}}),
    "glued_content_group": _d("This group IS a source-glued segment (a card).", _BOOL),
    "glued_content_id": _d("Shared segment id on each direct child of a glued group.", _INT),
    "line_split_group": _d("Children are the pieces of one source line, laid out aside.", _BOOL),
    "column_split_group": _d("Children are the pieces of a spaced-colon column split.", _BOOL),
    "column_weight": _d("Weight of the cell above a ':::N' divider (Phase 1 only).", _NUM),
    "column_row_group": _d("Children are the cells of a ':::' column row.", _BOOL),
    "column_weights": _d("One weight per cell of a column row; null = unweighted.", _WEIGHTS),
    "column_weights_wide": _d("Per-cell weights in wide space; null = same as column_weights.", _WEIGHTS),
    "column_cuts": _d("Space each cut after a cell applies in; null = both.", {"type": "array", "items": _enum("narrow", "wide", nullable=True)}),
    "valign_group": _d("Children are the regions of a '...' vertical spring split.", _BOOL),
    "authored_valign": _d("Authored vertical alignment of a spring region.", _enum(*_VALIGN)),
    "line_valign": _d("Authored vertical alignment mode of this node's row (@tp/@ct/@bs/@bm).", _STR),
    "align_group": _d("Children are the regions of a horizontal spring split.", _BOOL),
    "authored_align": _d("Authored horizontal alignment of a spring region.", _enum(*_ALIGN)),
    "separator_chars": _d("Row separator characters the children were split at, one per gap.", _STRS),
    "spacer_binds": _d("Which side a spacer closes: prev or next.", _enum("prev", "next")),
    "segmented_run": _d("Children are one ' | ' run of buttons, all options of one choice: drawn as one segmented control.", _BOOL),
    "feed_slots": _d(
        "The feed slots this node draws, each a range of its content.",
        {"type": "array", "items": _FEED_SLOT},
    ),
    "pure_element": _d("Every leaf of this group is a pill (ELEMENT_LEAF_TYPES), at least one.", _BOOL),
    "key_side": _d("Every leaf of this group is a KV key, at least one.", _BOOL),
    "top_heading_level": _d("On the root: the shallowest heading-section level in the document.", _INT),
    "atx_level": _d("On a leaf written as a heading inside another block (`- # Title`): the ATX level; the marker is dropped from content.", _INT),
    "spacer_lead": _d("Spelling of a spacer at the start of this line.", _STR),
    "spacer_trail": _d("Spelling of a spacer at the end of this line.", _STR),
    "spacer_above": _d("Spelling of a spacer written above a row merged into its card: space between the card's top edge and the row.", _STR),
    "spacer_below": _d("Spelling of a spacer written below a row merged into its card: space between the row and the card's bottom edge.", _STR),
    "spacer_beside": _d("The edge spacers were a `:::` cell of their own: they sit beside the box this node paints, never inside it.", _BOOL),
    "source_line_id": _d("Id of the physical source line the leaf came from.", _INT),
    "heading_group": _d("This group is a heading section container.", _BOOL),
    "heading_level": _d("Heading level 1-6 of a heading section.", _nullable(_INT)),
    "heading_id": _d("Trailing '{#id}' heading attribute.", _STR),
    "fixed_style_key": _d("Kebab-case heading id with numeric suffix removed (theme candidate).", _STR),
    "section_style_key": _d("Nearest heading section's fixed-style candidate.", _STR),
    "table_group": _d("This group is a table container.", _BOOL),
    "table_role": _d("Role of a TABLE_CELL.", _enum("header", "body")),
    "table_align": _d("Authored column alignment from the delimiter row.", _enum(*_ALIGN)),
    "datapoint_display": _d(
        "Drawn datapoint element replacing the text rendering.",
        _enum("ratio_bar", "unit_ratio", "kv_percent_bar", "date_chip", "line_chart"),
    ),
    "datapoint_payload": _d(
        "Self-contained payload of datapoint_display (value/max/unit/percent/day...); shape varies.",
        {
            "type": "object",
            "properties": {
                "value": _NUM, "max": _NUM, "unit": _STR, "text": _STR,
                "from_kv": _BOOL, "percent": _NUM, "value_text": _STR,
                "day": _INT, "key": _STR, "subtype": _STR,
            },
            "additionalProperties": True,
        },
    ),  # fmt: skip
    "drawing_element": _d(
        "Non-text visual: 'kind' selects the family, other keys are its payload.",
        {
            "type": "object",
            "properties": {
                "kind": _STR, "checked": _BOOL, "marker": _BOOL, "index": _INT,
                "label": _STR, "decimals": _INT, "max": _NUM, "unit": _STR,
                "value": _NUM, "count": _BOOL,
            },
            "required": ["kind"],
            "additionalProperties": True,
        },
    ),  # fmt: skip
    "text_style": _d("Authored display tier from an underscore wrapper.", _enum("muted", "lead", "display")),
    "chart_group": _d("This group is a chart container.", _BOOL),
    "chart_data": _d(
        "Chart payload: optional series names, unit and labelled rows.",
        {
            "type": "object",
            "properties": {
                "series": _nullable(_STRS),
                "unit": _STR,
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"label": _STR, "values": {"type": "array", "items": _NUM}},
                        "required": ["label", "values"],
                        "additionalProperties": True,
                    },
                },
            },
            "additionalProperties": True,
        },
    ),
    "line_group": _d("This group is several lines on one axis.", _BOOL),
    "line_data": _d(
        "Several lines' payload: each series' name and points, one label per position, the declared unit.",
        {
            "type": "object",
            "properties": {
                "series": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"name": _STR, "points": {"type": "array", "items": {"type": "object"}}},
                        "required": ["name", "points"],
                        "additionalProperties": True,
                    },
                },
                "labels": {"type": "array", "items": _nullable(_STR)},
                "display_unit": _nullable(_STR),
            },
            "additionalProperties": True,
        },
    ),
    "card_bg_url": _d("Background image URL of an IMAGE_CARD.", _STR),
    "link_url": _d("Target of a block-content link wrapping this subtree.", _STR),
    "link_variant": _d("Button style of a LINK node.", _enum("primary", *_CHIP_VARIANTS, "text")),
    "link_label": _d("Display label of a LINK with markers stripped.", _STR),
    "link_is_emoji": _d("LINK label is a pure emoji (forces the circle/square shape).", _BOOL),
    "link_disabled": _d("LINK was wrapped in '~~': disabled state.", _BOOL),
    "link_emphasis": _d("Emphasis wrapper a backtick label displaced.", _enum("italic", "bold", "bold_italic")),
    "emoji_kind": _d("Render role of an EMOJI node.", _enum("heading", "text", "alone")),
    "emoji_variant": _d("Wrapper-length variant of an EMOJI leaf.", _enum(*_VARIANTS)),
    "element_muted": _d("EMOJI or INLINE_CODE leaf wrapped in '~~': muted state.", _BOOL),
    "code_variant": _d("Wrapper-length variant of an INLINE_CODE leaf.", _enum(*_CHIP_VARIANTS)),
    "code_language": _d("Info-string language of a fenced CODE_BLOCK.", _STR),
    "in_key": _d("EMOJI peeled from a key-value key.", _BOOL),
    "emoji_index": _d("Ordinal of the emoji among its EMOJI siblings.", _INT),
    "rotation_index": _d("Slot in the colour rotation cycle of the enclosing section.", _INT),
    "fixed_rotation_index": _d("Rotation slot among headings sharing a fixed-style candidate.", _INT),
    "rotation_chain": _d("Heading levels of enclosing sections, outermost first.", {"type": "array", "items": {"type": ["integer", "string"]}}),
    "text_style_chain": _d("Styling scopes enclosing this node, outermost first, starting with root.", _STRS),
    "rotation_path": _d("Slot each enclosing section took, aligned with rotation_chain.", {"type": "array", "items": _INT}),
    "list_ordinal": _d("Ordinal to DRAW on an ORDERED_ITEM.", _INT),
    "list_number": _d("Number the author wrote on an ORDERED_ITEM.", _INT),
    "list_heading_level": _d("Heading level an ORDERED_ITEM was split out of.", _INT),
    "avg_word_count": _d("Average word count of the fingerprint cluster.", _NUM),
    "text_length_category": _d("Length category of the fingerprint cluster.", _enum(*_LENGTHS)),
    "content_length_category": _d("Length category of this node's own content.", _enum(*_LENGTHS)),
    "child_types": _d("Types of the children.", _STRS),
    "child_type_counts": _d("Count of children per type.", {"type": "object", "additionalProperties": _INT}),
    "data_points": _d("Detected data points in the content.", {"type": "array", "items": {"$ref": "#/$defs/data_point"}}),
}  # fmt: skip

GROUPING_AST_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://md2ui.dev/schemas/grouping-ast.schema.json",
    "title": "md2ui grouping AST",
    "description": (
        "Output of MarkdownGroupNode.to_dict(): the grouper's annotated node "
        "tree, at the final stage or after any phase."
    ),
    "$ref": "#/$defs/node",
    "$defs": {
        "node": {
            "type": "object",
            "properties": _PROPS,
            "required": ["node_id", "content", "type", "fingerprint_hash", "children"],
            "additionalProperties": False,
        },
        "data_point": _DATA_POINT,
    },
}
