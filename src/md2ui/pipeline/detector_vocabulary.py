"""The words the detector knows: month names, currencies, units, emoji.

Neither patterns nor parsing — the tables both of those are written in terms of.
A month name appears twice in this pipeline: once inside the regex that FINDS a
date, and again in the parser that turns the match into a number. Those two must
agree, so the list lives in one place and both import it.

That is the whole reason this is a module. It is a vocabulary, not a stage: it
imports nothing from md2ui and holds no logic.
"""

import re
from decimal import Decimal


EMOJI_NAME_OVERRIDES: dict[str, str] = {
    "➕": "plus addition increase",
    "➖": "minus subtraction decrease",
    "➗": "division divide",
    "✖️": "multiplication multiply",
    "🔼": "increase up arrow",
    "🔽": "decrease down arrow",
    "📈": "growth increase trend",
    "📉": "decline decrease trend",
    # add as you encounter them...
}


# Emoji outside the blocks below, from Unicode's emoji-test.txt (Emoji 16.0),
# kept in step with render_text's copy (tests/emoji_routing_tests.py):
# these are emoji on their own (🀄 🃏 🆗 🈚) ...
_EMOJI_BY_DEFAULT = (
    r"\U0001F004\U0001F0CF\U0001F18E\U0001F191-\U0001F19A\U0001F201\U0001F21A"
    r"\U0001F22F\U0001F232-\U0001F236\U0001F238-\U0001F23A\U0001F250\U0001F251"
)
# ... and these only with U+FE0F after them: bare, they are text (`© 2026`, `™`).
_EMOJI_WITH_SELECTOR = (
    r"\u00A9\u00AE\u203C\u2049\u2122\u2139\u24C2\u2934\u2935\u3030\u303D\u3297"
    r"\u3299\U0001F170\U0001F171\U0001F17E\U0001F17F\U0001F202\U0001F237"
)

# Emoji Unicode ranges, shared with grouper_types._classify_link_content
# (a link label is "pure emoji" if it fullmatch()es EMOJI_CHAR_PATTERN). A run
# holds keycaps and joiners, but never starts or ends with a joiner.
#
# Wider than Unicode's emoji on purpose: the whole Arrows, Block Elements,
# Geometric Shapes, Misc Symbols, Dingbats and Misc Symbols and Arrows blocks are
# md2ui's icon vocabulary. `→` alone is a badge, `[▾](/menu)` an icon button, and
# `▲ ▼ ✓` carry the theme's meanings and pinned colours. Unicode's
# Extended_Pictographic leaves most of them out, so replacing these tables with it
# is a design change, not a cleanup.
_EMOJI_CHAR_RANGES = (
    r"(?!\u200d)(?:[0-9#*]\uFE0F?\u20E3|[" + _EMOJI_WITH_SELECTOR + r"]\uFE0F"
    r"|[" + _EMOJI_BY_DEFAULT + r"\U0001F600-\U0001F64F"  # Emoticons
    r"\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
    r"\U0001F680-\U0001F6FF"  # Transport and Map
    r"\U0001F700-\U0001F77F"  # Alchemical Symbols
    r"\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
    r"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
    r"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    r"\U0001FA00-\U0001FA6F"  # Chess Symbols
    r"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    r"\U00002190-\U000021FF"  # Arrows (↙ ↗ ↕ ↔ ↩ ↪ ↑ ↓ → ←)
    r"\U00002702-\U000027B0"  # Dingbats
    r"\U0000231A-\U0000231B"  # Watch, Hourglass
    r"\U00002328"  # Keyboard
    r"\U000023CF"  # Eject
    r"\U000023E9-\U000023F3"  # Media controls
    r"\U000023F8-\U000023FA"  # Media controls
    r"\U00002580-\U0000259F"  # Block Elements
    r"\U000025A0-\U000025FF"  # Geometric Shapes (▲ ▼ ◆ ● ■ ◇ ○ □ ▶ ◀)
    r"\U00002600-\U000026FF"  # Misc symbols
    r"\U00002700-\U000027BF"  # Dingbats
    r"\U00002B00-\U00002BFF"  # Miscellaneous Symbols and Arrows
    r"\U0000FE00-\U0000FE0F\u200D"  # Variation Selectors, the joiner
    r"\U000E0020-\U000E007F"  # Tags: England, Scotland and Wales are 🏴 + tags
    r"\U0001F1E0-\U0001F1FF])+(?<!\u200d)"  # Flags
)


EMOJI_CHAR_PATTERN = re.compile(_EMOJI_CHAR_RANGES)


_MAGNITUDE_WORDS = r"hundred|thousand|million|billion|trillion"


_MAGNITUDE_MULTIPLIERS = {
    "hundred": Decimal("100"),
    "thousand": Decimal("1000"),
    "million": Decimal("1000000"),
    "billion": Decimal("1000000000"),
    "trillion": Decimal("1000000000000"),
}


_ISO_CURRENCY_CODES = (
    r"USD|EUR|GBP|JPY|MXN|CAD|AUD|CHF|CNY|INR|BRL|KRW|SGD|HKD|NOK|SEK|DKK"
    r"|NZD|ZAR|ARS|COP|TRY|AED|SAR|THB|MYR|IDR|PHP|PLN|CZK|HUF|ILS|QAR"
    r"|KWD|NGN|EGP|TWD|VND|CLP|PEN|PKR"
)


# A written sign. A minus is the ASCII hyphen or the typographic minus U+2212,
# which LLMs write in finance and statistics answers; the parsers test only for
# "+", so either minus reads as negative. The characters themselves, so a parser
# can test membership; the hyphen leads every class built from them, where it is
# literal (after "+" it would open a range).
_MINUS = "-\u2212"
_SIGN = rf"[{_MINUS}+]"


_QUANTITY_UNITS = (
    r"units?|items?|pieces?|kg|g|mg|lb|lbs|oz|km|m|cm|mm|mi|miles?"
    r"|ft|feet|inch|inches|in|l|ml|gal|gallons?|hrs?|hours?|mins?"
    r"|minutes?|secs?|seconds?|days?|weeks?|months?|years?|people|persons?"
    r"|users?|customers?|employees?|transactions?|kcal|sessions?"
    r"|barrels?|bbl|tons?|tonnes?|shares?|sqft|acres?|kwh|mwh|bushels?|points?"
)


_DIMENSION_UNITS = r"cm|mm|m|km|in|inch|inches|ft|feet|px|pixels?|mi|miles?|yd|yards?"


_MONTH_NAMES_LONG = (
    r"January|February|March|April|May|June"
    r"|July|August|September|October|November|December"
)


_MONTH_NAMES_SHORT = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


_ORDINAL_SUFFIX = r"st|nd|rd|th"


# What joins a month or weekday to its day-of-month, and the ONE thing that
# separates a date a reader can see from a date the tool draws as a chip.
#
# A SPACE is how dates are written in prose: "Delivered Jun 5", "Sat 12". A
# DASH is not — nobody writes ``Jun-5`` in a sentence — so it is available as
# the author's request for the chip, and its absence is the per-instance
# opt-out that the spaced spelling never gave anyone. Both spellings are still
# DETECTED as dates, so a date is still one protected span wherever it appears;
# only the drawing is spelled for (grouper_displays._try_leaf_display).
#
# The dash brings its own opt-out with it, because a TIGHT escape declines the
# token it sits in: ``Mon\-15`` is text (see VALUE_ESCAPES).
_DATE_CHIP_JOIN = r"[ \-]"


_CURRENCY_SYMBOLS = r"[$€£¥]"


_RANGE_OP = r"[-–to]+"


# Speed units, shared by the plain rate pattern and the rate RANGE below.
_SPEED_UNITS = r"mph|km/h|kmh|kph|m/s|ft/s"


_MONTH_NAMES = rf"(?:{_MONTH_NAMES_LONG}|{_MONTH_NAMES_SHORT})"


# The weekday half of "Fri, Aug 14". Mirrors _DAY_NAMES in pipeline/grouper_split_criteria.py,
# whose _NON_LIST_COMMA_SPAN already treats that whole span as one unit.
_DAY_NAMES_RE = (
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    r"Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)\.?"
)
_DURATION_UNIT_SECONDS = {
    "w": 604800,
    "week": 604800,
    "d": 86400,
    "day": 86400,
    "h": 3600,
    "hr": 3600,
    "hour": 3600,
    "m": 60,
    "min": 60,
    "minute": 60,
    "s": 1,
    "sec": 1,
    "second": 1,
}


_SYMBOL_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}


_MAGNITUDE = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}
