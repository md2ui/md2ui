"""
Tests that a picture counts no words toward its length category.

A length category is how narrow a column may go before its text has to wrap, so
it must count only what the page draws. A picture's alt text and URL are never
drawn: three cards of a picture, a title and a button grid three across whether
the pictures are described in two words or twelve, or not at all.

The Markdown in a photo card's alt slot IS drawn — it is the card's body — so it
keeps counting like any other text.

Run with: uv run tests/image_word_count_tests.py
"""

from image_min_width_tests import _scene
from markdown_datapoint_split_tests import _processed_with_criteria
from md2ui.pipeline.grouper_text_lengths import drawn_word_count

_PHOTO = "https://example.com/photo.jpg?md2ui.aspect_ratio=4:3"
_LONG_ALT = "{} interface showing a coding task and agent progress inside the app."


def _cards(alt: str) -> str:
    return "".join(
        f"### \n![{alt.format(name)}]({_PHOTO})\n__Codex {name}__\n*[Try it](/t{i})*\n\n"
        for i, name in enumerate(["app", "editor", "terminal"])
    )


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


def _images(root) -> list:
    return [n for n in _walk(root) if n.type == "image"]


def test_an_image_counts_no_words():
    for alt in (_LONG_ALT, "{} app", ""):
        images = _images(_processed_with_criteria(_cards(alt)))
        assert len(images) == 3, images
        for image in images:
            assert image.content_length_category == "one_word", (alt, image)
            assert image.avg_word_count == 0, (alt, image.avg_word_count)
            assert drawn_word_count(image) == 0, (alt, image.content)
    print("  ✓  an image counts no words")


def test_a_card_reads_the_same_length_whatever_its_alt():
    def cards(alt: str) -> list:
        root = _processed_with_criteria(_cards(alt))
        return [
            (n.content_length_category, n.text_length_category, n.avg_word_count)
            for n in _walk(root)
            if any(c.type == "image" for c in n.children)
        ]

    long, short = cards(_LONG_ALT), cards("")
    assert len(long) == 3 and long == short, (long, short)
    print("  ✓  a card reads the same length whatever its alt")


def test_a_photo_cards_alt_slot_keeps_counting():
    body = " ".join(["word"] * 20)
    root = _processed_with_criteria(
        f"![\n## A title\n{body}\n](https://example.com/p.jpg)\n"
    )
    card = next(n for n in _walk(root) if n.type == "image_card")
    assert card.content_length_category == "medium", card.content_length_category
    print("  ✓  a photo card's alt slot keeps counting")


def test_long_alt_text_grids_like_short():
    for width in (1201.0, 900.0):
        rows = {}
        for name, alt in (("long", _LONG_ALT), ("short", "{} app")):
            scene = _scene(_cards(alt), width)
            boxes = [
                b
                for b in scene.boxes
                if (b.render_properties or {}).get("aspect_ratio")
            ]
            rows[name] = (
                len({round(b.y) for b in boxes}),
                [round(b.width) for b in boxes],
            )
        assert rows["long"] == rows["short"] and rows["long"][0] == 1, (width, rows)
    print("  ✓  long alt text grids like short")


TESTS = [
    test_an_image_counts_no_words,
    test_a_card_reads_the_same_length_whatever_its_alt,
    test_a_photo_cards_alt_slot_keeps_counting,
    test_long_alt_text_grids_like_short,
]

if __name__ == "__main__":
    print("Image Word Count Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except AssertionError as e:
            failed += 1
            print(f"  ✗  {test.__name__}: {e}")
    raise SystemExit(1 if failed else 0)
