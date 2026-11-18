"""How long a node's text reads: the words it draws, and the length category
those words fall into.

The grouper's fingerprint pass counts each leaf's words and buckets them; the
layout generator floors a column's width by the bucket and never recounts. So
what counts as a word is decided once, here: only text the page draws. A
picture draws none — its alt text and URL never reach the page — while the
Markdown in a photo card's alt slot is parsed into the card's children and
counts like any other text.
"""

from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType

_TEXT_LENGTH_CATEGORY_ORDER = {
    "one_word": 0,
    "very_short": 1,
    "short": 2,
    "medium": 3,
    "paragraph": 4,
    "long_paragraph": 5,
}


def _word_count_category(wc: float) -> str:
    """Bucket a word count into a text-length category (shared cutoffs)."""
    if wc <= 1:
        return "one_word"
    if wc <= 4:
        return "very_short"
    if wc <= 9:
        return "short"
    if wc <= 40:
        return "medium"
    if wc <= 100:
        return "paragraph"
    return "long_paragraph"


def drawn_word_count(node: MarkdownGroupNode) -> int:
    """The words *node*'s own content draws; a picture draws none."""
    return 0 if node.type == NodeType.IMAGE else len(node.content.split())
