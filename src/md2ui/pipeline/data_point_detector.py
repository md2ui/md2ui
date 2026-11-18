"""
Data Point Detector - Single-pass detection for dates, currencies, percentages, and more.
"""

import re
from datetime import datetime
from decimal import Decimal

# The pattern table below and the parsers it points at are written in the same
# vocabulary -- a month name appears in the regex that FINDS a date and again in
# the parser that reads it -- so both import the tables from one place.
from md2ui.pipeline.detector_vocabulary import (
    _DATE_CHIP_JOIN,
    EMOJI_CHAR_PATTERN,
    _CURRENCY_SYMBOLS,
    _DAY_NAMES_RE,
    _DIMENSION_UNITS,
    _EMOJI_CHAR_RANGES,
    _ISO_CURRENCY_CODES,
    _MAGNITUDE_WORDS,
    _MINUS,
    _MONTH_NAMES,
    _MONTH_NAMES_LONG,
    _MONTH_NAMES_SHORT,
    _ORDINAL_SUFFIX,
    _QUANTITY_UNITS,
    _RANGE_OP,
    _SIGN,
    _SPEED_UNITS,
)

# Public re-exports: EMOJI_CHAR_PATTERN and emoji_to_text live with the
# vocabulary and the parsers, but `data_point_detector` is their address --
# grouper_types and the grouper import them from here. Listed in __all__ below,
# which is what stops ruff reading a re-export as dead.
# The scope sets live in detector_scope for the same reason the vocabulary and
# the parsers live in their own modules: they are a TABLE, read by lookup. They
# are re-exported here because this module is their address (see __all__).
from md2ui.pipeline.data_point_types import DataPointType
from md2ui.pipeline.detector_scope import _PIPELINE_TYPES
from md2ui.pipeline.render_text import LINK_DESTINATION
from md2ui.pipeline.detector_signs import take_sign
from md2ui.pipeline.detector_guards import PatternGuards
from md2ui.pipeline.detector_parsers import (
    emoji_to_text,
    _parse_age_range,
    _parse_age_simple,
    _parse_age_single,
    _parse_blood_type,
    _parse_change_bare,
    _parse_change_currency,
    _parse_change_direction,
    _parse_change_percentage,
    _parse_change_quantity,
    _parse_currency_magnitude,
    _parse_currency_shorthand,
    _parse_currency_trailing_symbol,
    _parse_date_day_only,
    _parse_date_dotted_short_year,
    _parse_date_partial_long,
    _parse_date_partial_short,
    _parse_date_range,
    _parse_date_range_short,
    _parse_date_range_two_endpoints,
    _parse_datetime_comma,
    _parse_datetime_iso,
    _parse_datetime_long_month,
    _parse_datetime_short_month,
    _parse_day_of_week,
    _parse_day_of_week_short,
    _parse_dimension,
    _parse_dimension_per_unit,
    _parse_duration,
    _parse_duration_compound,
    _parse_emoji,
    _parse_file_size,
    _parse_frequency,
    _parse_frequency_every,
    _parse_full_date_with_month_name,
    _parse_identifier,
    _parse_iso_currency,
    _parse_magnitude,
    _parse_markdown_link,
    _parse_measurement_height,
    _parse_measurement_temp,
    _parse_measurement_temp_dual,
    _parse_month_year,
    _parse_ordinal,
    _parse_phone,
    _parse_phone_international,
    _parse_quantity,
    _parse_quarter,
    _parse_range_between,
    _parse_range_currency,
    _parse_range_currency_shared,
    _parse_range_percentage,
    _parse_range_unit,
    _parse_ranking_hash,
    _parse_ranking_place,
    _parse_ranking_top,
    _parse_rate_commodity,
    _parse_rate_generic,
    _parse_rate_percentage,
    _parse_rate_price,
    _parse_rate_speed,
    _parse_rate_speed_range,
    _parse_ratio_colon,
    _parse_ratio_slash,
    _parse_score_fraction,
    _parse_score_grade,
    _parse_score_single_star,
    _parse_score_stars,
    _parse_shorthand_magnitude,
    _parse_signed_percentage,
    _parse_statistical,
    _parse_time_12h,
    _parse_time_24h,
    _parse_time_hours_only,
    _parse_time_range_12h,
    _parse_time_range_24h,
    _parse_unicode_fraction,
    _parse_version,
    _parse_weekday_date,
    _parse_weekday_day,
    _parse_weekday_day_short,
)

__all__ = [
    "DataPointDetector",
    "DataPointType",
    "EMOJI_CHAR_PATTERN",
    "emoji_to_text",
]

_MAGNITUDE_SUFFIX = r"[KMBT]"  # K=thousand, M=million, B=billion, T=trillion


_AMPM = r"AM|PM|am|pm"
_DAY_OF_MONTH = r"(?:3[01]|[12]\d|0?[1-9])"
_RANGE_DASH = r"\s+[-–—]\s+"
# The time half of a comma-spelled datetime: a clock time, or a bare hour that
# carries AM/PM. The bare hour MUST have the meridiem — without it "March 5, 10"
# would read as a timestamp instead of a date beside a count.
_TIME_TAIL = (
    rf"(?:\d{{1,2}}:\d{{2}}(?::\d{{2}})?\s*(?:{_AMPM})?"
    rf"|(?:1[0-2]|0?[1-9])\s*(?:{_AMPM}))"
)


class DataPointDetector:
    """Single-pass detection for multiple data types."""

    def __init__(self):
        self.patterns = []  # (compiled_regex, data_type, parser_func)
        self._register_default_patterns()
        # Built once, in registration order, so overlap resolution inside the
        # narrowed set behaves exactly as it does in the full one.
        self._pipeline_patterns = [
            entry for entry in self.patterns if entry[1] in _PIPELINE_TYPES
        ]

    def _register_default_patterns(self):
        """Register all default patterns for dates, currencies, and percentages."""
        # Datetime patterns (registered first — combined match is longer than separate DATE+TIME)
        self.register(
            rf"\b(?:{_MONTH_NAMES_LONG}) \d{{1,2}}, \d{{4}}\s+at\s+\d{{1,2}}:\d{{2}}\s*(?:{_AMPM})?\b",
            DataPointType.DATE,
            _parse_datetime_long_month,
        )
        self.register(
            rf"\b(?:{_MONTH_NAMES_SHORT})\.? \d{{1,2}}, \d{{4}}\s+at\s+\d{{1,2}}:\d{{2}}\s*(?:{_AMPM})?\b",
            DataPointType.DATE,
            _parse_datetime_short_month,
        )
        self.register(
            rf"\b\d{{4}}-\d{{2}}-\d{{2}}\s+at\s+\d{{1,2}}:\d{{2}}(?::\d{{2}})?\s*(?:{_AMPM})?\b",
            DataPointType.DATE,
            _parse_datetime_iso,
        )
        # ...and the same thing spelled with a COMMA instead of "at"
        # ("February 04, 9:17 PM"). It is one datapoint rather than a DATE and a
        # TIME so its type, value and display treatment stay together.
        # The year is optional here — unlike the three "at" patterns above, whose
        # `_combine_date_time` needs a real date.
        self.register(
            rf"\b{_MONTH_NAMES}\.? \d{{1,2}}(?:{_ORDINAL_SUFFIX})?"
            rf"(?:, \d{{4}})?[,.]\s*{_TIME_TAIL}\b",
            DataPointType.DATE,
            _parse_datetime_comma,
        )
        # A weekday introducing a date ("Fri, Aug 14", "Wednesday, February 5")
        # is one unit too, and the comma-list rule agrees — _NON_LIST_COMMA_SPAN in
        # pipeline/grouper_split_criteria.py carries this very span.
        #
        # The tail must be a MONTH date, never merely another weekday: "Tuesday,
        # Wednesday" is a list of two days, and matching it here would read that
        # list as a date.
        self.register(
            rf"\b{_DAY_NAMES_RE},\s+{_MONTH_NAMES}\.? \d{{1,2}}"
            rf"(?:{_ORDINAL_SUFFIX})?(?:, \d{{4}})?\b",
            DataPointType.DATE,
            _parse_weekday_date,
        )

        # Date patterns - Full dates (with year)
        # The (?<!sep)…(?!sep) guards prevent the date from matching when it's
        # embedded in a hyphenated/slashed/dotted identifier like
        # ORD-2026-02-04-78923. \b alone is insufficient because the date's
        # own separator is a non-word char, so the boundary still matches.
        self.register(
            r"(?<!-)\b\d{4}-\d{2}-\d{2}\b(?!-)",
            DataPointType.DATE,
            lambda m: {
                "datetime": datetime.strptime(m, "%Y-%m-%d"),
                "subtype": "full",
                "has_year": True,
            },
        )
        self.register(
            r"(?<!/)\b\d{2}/\d{2}/\d{4}\b(?!/)",
            DataPointType.DATE,
            lambda m: {
                "datetime": datetime.strptime(m, "%m/%d/%Y"),
                "subtype": "full",
                "has_year": True,
            },
        )
        self.register(
            r"(?<!-)\b\d{1,2}-\d{1,2}-\d{4}\b(?!-)",
            DataPointType.DATE,
            lambda m: {
                "datetime": datetime.strptime(m, "%d-%m-%Y"),
                "subtype": "full",
                "has_year": True,
            },
        )
        self.register(
            rf"\b(?:{_MONTH_NAMES_LONG}) \d{{1,2}}, \d{{4}}\b",
            DataPointType.DATE,
            lambda m: {
                "datetime": datetime.strptime(m, "%B %d, %Y"),
                "subtype": "full",
                "has_year": True,
            },
        )
        self.register(
            rf"\b(?:{_MONTH_NAMES_SHORT}) \d{{1,2}}, \d{{4}}\b",
            DataPointType.DATE,
            lambda m: {
                "datetime": datetime.strptime(m, "%b %d, %Y"),
                "subtype": "full",
                "has_year": True,
            },
        )
        self.register(
            r"(?<!\.)\b\d{2}\.\d{2}\.\d{4}\b(?!\.)",
            DataPointType.DATE,
            lambda m: {
                "datetime": datetime.strptime(m, "%d.%m.%Y"),
                "subtype": "full",
                "has_year": True,
            },
        )

        # Date patterns - Day-first full dates: 20 May 2017, 20th May, 2017, 5 Jan 2024
        self.register(
            rf"\b\d{{1,2}}(?:{_ORDINAL_SUFFIX})? {_MONTH_NAMES}\.?,? \d{{4}}\b",
            DataPointType.DATE,
            _parse_full_date_with_month_name,
        )
        # Month-first full dates without a comma: May 20 2017, May 20th 2017
        self.register(
            rf"\b{_MONTH_NAMES}\.? \d{{1,2}}(?:{_ORDINAL_SUFFIX})? \d{{4}}\b",
            DataPointType.DATE,
            _parse_full_date_with_month_name,
        )
        # Month-first full dates with ordinal + comma: May 20th, 2017
        self.register(
            rf"\b{_MONTH_NAMES}\.? \d{{1,2}}(?:{_ORDINAL_SUFFIX}), \d{{4}}\b",
            DataPointType.DATE,
            _parse_full_date_with_month_name,
        )
        # Day "of" month year: 20th of May 2017, the 20 of May 2017
        self.register(
            rf"\b(?:the )?\d{{1,2}}(?:{_ORDINAL_SUFFIX})? of {_MONTH_NAMES}\.? \d{{4}}\b",
            DataPointType.DATE,
            _parse_full_date_with_month_name,
        )
        # Month + year, no day: May 2017, May, 2017, Jul. 2017
        self.register(
            rf"\b{_MONTH_NAMES}\.?,? \d{{4}}\b",
            DataPointType.DATE,
            _parse_month_year,
        )
        # ISO year-month: 2017-05 (guards mirror the ISO full-date pattern)
        self.register(
            r"(?<!\d)(?<!-)\b\d{4}-\d{2}\b(?!-)(?!\d)",
            DataPointType.DATE,
            _parse_month_year,
        )
        # Numeric month/year: 05/2017, 5/2017 (registered before RATIO to win ties)
        self.register(
            r"(?<!\d)(?<!/)\b\d{1,2}/\d{4}\b(?!/)(?!\d)",
            DataPointType.DATE,
            _parse_month_year,
        )
        # 2-digit-year dotted date: 20.05.17 (registered before VERSION to win ties)
        self.register(
            r"(?<!\d)(?<!\.)\b\d{2}\.\d{2}\.\d{2}\b(?!\.)(?!\d)",
            DataPointType.DATE,
            _parse_date_dotted_short_year,
        )

        # Date patterns - Partial dates (without year)
        self.register(
            rf"\b(?:{_MONTH_NAMES_LONG}){_DATE_CHIP_JOIN}"
            rf"\d{{1,2}}(?:{_ORDINAL_SUFFIX})?\b(?!, \d{{4}})",
            DataPointType.DATE,
            _parse_date_partial_long,
        )
        self.register(
            rf"\b(?:{_MONTH_NAMES_SHORT})\.?{_DATE_CHIP_JOIN}"
            rf"\d{{1,2}}(?:{_ORDINAL_SUFFIX})?\b(?!, \d{{4}})",
            DataPointType.DATE,
            _parse_date_partial_short,
        )
        self.register(
            rf"\bthe \d{{1,2}}(?:{_ORDINAL_SUFFIX})\b",
            DataPointType.DATE,
            _parse_date_day_only,
        )

        # Date patterns - Day of week
        self.register(
            r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
            DataPointType.DATE,
            _parse_day_of_week,
        )
        self.register(
            r"\b(?:Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)\.?\b",
            DataPointType.DATE,
            _parse_day_of_week_short,
        )

        # Weekday + day-of-month combo: "Monday 15", "Mon 15th", "Tue 10"
        self.register(
            rf"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
            rf"{_DATE_CHIP_JOIN}{_DAY_OF_MONTH}(?:{_ORDINAL_SUFFIX})?\b",
            DataPointType.DATE,
            _parse_weekday_day,
        )
        self.register(
            rf"\b(?:Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)\.?"
            rf"{_DATE_CHIP_JOIN}{_DAY_OF_MONTH}(?:{_ORDINAL_SUFFIX})?\b",
            DataPointType.DATE,
            _parse_weekday_day_short,
        )

        # Date range patterns
        self.register(
            rf"\b({_MONTH_NAMES_LONG}) (\d{{1,2}})-(\d{{1,2}}), (\d{{4}})\b",
            DataPointType.DATE_RANGE,
            _parse_date_range,
        )
        self.register(
            rf"\b({_MONTH_NAMES_SHORT}) (\d{{1,2}})-(\d{{1,2}}), (\d{{4}})\b",
            DataPointType.DATE_RANGE,
            _parse_date_range_short,
        )
        # Two-endpoint date range: cross-month or same-month with explicit
        # endpoints, optional per-side year, ASCII/en-dash/em-dash separator.
        # Examples: "Jul 5 - Dec 5", "July 5 – December 5",
        #           "Jul 5, 2025 — Dec 5, 2025".
        self.register(
            rf"\b{_MONTH_NAMES}\.? \d{{1,2}}(?:, \d{{4}})?{_RANGE_DASH}"
            rf"{_MONTH_NAMES}\.? \d{{1,2}}(?:, \d{{4}})?\b",
            DataPointType.DATE_RANGE,
            _parse_date_range_two_endpoints,
        )

        # Currency + shorthand suffix: $50M, €1.2B, £500K, ¥2T
        _sfx = _MAGNITUDE_SUFFIX
        self.register(
            rf"\$\d+(?:\.\d+)?{_sfx}\b",
            DataPointType.CURRENCY,
            lambda m: _parse_currency_shorthand(m, "USD"),
        )
        self.register(
            rf"€\d+(?:\.\d+)?{_sfx}\b",
            DataPointType.CURRENCY,
            lambda m: _parse_currency_shorthand(m, "EUR"),
        )
        self.register(
            rf"£\d+(?:\.\d+)?{_sfx}\b",
            DataPointType.CURRENCY,
            lambda m: _parse_currency_shorthand(m, "GBP"),
        )
        self.register(
            rf"¥\d+(?:\.\d+)?{_sfx}\b",
            DataPointType.CURRENCY,
            lambda m: _parse_currency_shorthand(m, "JPY"),
        )

        # Currency + magnitude: $89 billion, €3.5 million, etc.
        _mag = _MAGNITUDE_WORDS
        self.register(
            rf"\$\d+(?:\.\d+)?\s*(?:{_mag})\b",
            DataPointType.CURRENCY,
            lambda m: _parse_currency_magnitude(m, "USD"),
        )
        self.register(
            rf"€\d+(?:\.\d+)?\s*(?:{_mag})\b",
            DataPointType.CURRENCY,
            lambda m: _parse_currency_magnitude(m, "EUR"),
        )
        self.register(
            rf"£\d+(?:\.\d+)?\s*(?:{_mag})\b",
            DataPointType.CURRENCY,
            lambda m: _parse_currency_magnitude(m, "GBP"),
        )
        self.register(
            rf"¥\d+(?:\.\d+)?\s*(?:{_mag})\b",
            DataPointType.CURRENCY,
            lambda m: _parse_currency_magnitude(m, "JPY"),
        )

        # ISO currency suffix: $85.00 MXN, 85.00 MXN, 1,200.00 MXN
        self.register(
            rf"(?:{_CURRENCY_SYMBOLS})?\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?\s+(?:{_ISO_CURRENCY_CODES})\b",
            DataPointType.CURRENCY,
            _parse_iso_currency,
        )
        # ISO currency prefix: MXN 85.00, USD 1,200.00
        self.register(
            rf"\b(?:{_ISO_CURRENCY_CODES})\s+(?:{_CURRENCY_SYMBOLS})?\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?",
            DataPointType.CURRENCY,
            _parse_iso_currency,
        )
        # Trailing currency symbol: amount followed by a currency symbol, with an
        # optional leading symbol — covers European "2,36 €", "45€" and the
        # dual-symbol "$2.36 €". The trailing symbol decides the currency, so
        # "$2.36 €" → EUR. The (?<![\d.,]) guard stops the amount from starting
        # mid-number (so "2,36 €" matches the whole "2,36", not a partial "36").
        # Registered with the currency group; _remove_overlaps keeps the longest
        # match, so "$2.36 €" wins over the bare "$2.36".
        self.register(
            rf"(?<![\d.,])(?:{_CURRENCY_SYMBOLS})?\d+(?:[.,]\d+)*\s*(?:{_CURRENCY_SYMBOLS})",
            DataPointType.CURRENCY,
            _parse_currency_trailing_symbol,
        )

        # Currency patterns
        self.register(
            r"\$\d{1,3}(?:,\d{3})*(?:\.\d+)?",
            DataPointType.CURRENCY,
            lambda m: {
                "amount": Decimal(m.replace("$", "").replace(",", "")),
                "currency": "USD",
            },
        )
        self.register(
            r"€\d{1,3}(?:\.\d{3})*(?:,\d{2})?",
            DataPointType.CURRENCY,
            lambda m: {
                "amount": Decimal(
                    m.replace("€", "").replace(".", "").replace(",", ".")
                ),
                "currency": "EUR",
            },
        )
        self.register(
            r"£\d{1,3}(?:,\d{3})*(?:\.\d+)?",
            DataPointType.CURRENCY,
            lambda m: {
                "amount": Decimal(m.replace("£", "").replace(",", "")),
                "currency": "GBP",
            },
        )
        self.register(
            r"¥\d{1,3}(?:,\d{3})*",
            DataPointType.CURRENCY,
            lambda m: {
                "amount": Decimal(m.replace("¥", "").replace(",", "")),
                "currency": "JPY",
            },
        )

        # Percentage patterns
        self.register(
            rf"~?[{_MINUS}]?\d+\.\d+%",
            DataPointType.PERCENTAGE,
            _parse_signed_percentage,
        )
        self.register(
            rf"~?[{_MINUS}]?\d+%",
            DataPointType.PERCENTAGE,
            _parse_signed_percentage,
        )
        self.register(
            r"~?\d+(?:\.\d+)?\s*percent\b",
            DataPointType.PERCENTAGE,
            lambda m: Decimal(m.lstrip("~").lower().replace("percent", "").strip()),
        )

        # Integer/count patterns
        self.register(
            r"(?<![$€£¥])\b\d{1,3}(?:,\d{3})+\b",
            DataPointType.NUMBER,
            lambda m: int(m.replace(",", "")),
        )
        # Formatted decimal: 4,783.45 / 1,234,567.89
        self.register(
            r"(?<![$€£¥])\b\d{1,3}(?:,\d{3})+\.\d+\b",
            DataPointType.NUMBER,
            lambda m: {"value": Decimal(m.replace(",", "")), "type": "decimal"},
        )

        # Quantity patterns (value + unit)
        # Magnitude words: 3.7 million, 2 billion, etc.
        self.register(
            rf"(?<![$€£¥,.\d])\b\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?\s*(?:{_MAGNITUDE_WORDS})\b",
            DataPointType.QUANTITY,
            _parse_magnitude,
        )

        # Shorthand magnitude: 2.5B, 500K, 1.2M, 3T
        self.register(
            rf"(?<![$€£¥,.\d])\b\d+(?:\.\d+)?{_MAGNITUDE_SUFFIX}\b",
            DataPointType.QUANTITY,
            _parse_shorthand_magnitude,
        )

        # Common units: 250 units, 100 kg, 50 miles, etc.
        self.register(
            rf"(?<![$€£¥,.\d])\b\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?\s*(?:{_QUANTITY_UNITS})\b",
            DataPointType.QUANTITY,
            _parse_quantity,
        )

        # Ratio patterns: 3:1, 1:100, 50/50
        self.register(r"\b\d+:\d+\b", DataPointType.RATIO, _parse_ratio_colon)
        self.register(
            # A BARE fraction is a ratio; a fraction followed by a word is a
            # SCORE carrying that word as its unit (`750/1800 kcal`,
            # `25/100 progress`). detect_all trims whitespace a pattern
            # swallows, so SCORE's trailing `\s*` cannot decide this by
            # outrunning the pattern by one character; it is stated here.
            r"\b\d+/\d+\b(?!\s*(?:stars?|rating))(?!\s+[A-Za-z])",
            DataPointType.RATIO,
            _parse_ratio_slash,
        )

        # Rate patterns: 60 mph, $15/hour, 5% annual growth
        self.register(
            rf"(?:(?-i:\b[NSEW]{{1,3}})\s+)?"
            rf"(?<![$€£¥,.\d])\b\d+(?:\.\d+)?\s*(?:{_SPEED_UNITS})\b",
            DataPointType.RATE,
            _parse_rate_speed,
        )
        # A speed RANGE — `7-10 mph`, `15-20 km/h`. Without this the plain
        # pattern above matches only the upper bound (`7-10 mph` -> `10 mph`),
        # and the generic unit range claims `15-20 km/h` as `15-20 km` — a
        # speed silently re-typed as a distance. Registered
        # after it because the longest match wins in _remove_overlaps.
        self.register(
            rf"(?:(?-i:\b[NSEW]{{1,3}})\s+)?"
            rf"(?<![$€£¥,.\d])\b\d+(?:\.\d+)?\s*{_RANGE_OP}\s*\d+(?:\.\d+)?\s*(?:{_SPEED_UNITS})\b",
            DataPointType.RATE,
            _parse_rate_speed_range,
        )
        # Price per commodity unit: $2,048/oz, $73.45/barrel, €1,200/kg
        self.register(
            rf"{_CURRENCY_SYMBOLS}\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?/(?:{_QUANTITY_UNITS})\b",
            DataPointType.RATE,
            _parse_rate_commodity,
        )
        self.register(
            r"\$\d+(?:\.\d+)?/(?:hour|hr|day|week|month|year|unit|item)\b",
            DataPointType.RATE,
            _parse_rate_price,
        )
        self.register(
            r"\b\d+(?:\.\d+)?%\s*(?:annual|monthly|daily|weekly|yearly|per\s+(?:year|month|day|week))\b",
            DataPointType.RATE,
            _parse_rate_percentage,
        )
        self.register(
            r"(?<![$€£¥,.\d])\b\d+(?:\.\d+)?\s*(?:per|/)\s*(?:hour|day|week|month|year|second|minute)\b",
            DataPointType.RATE,
            _parse_rate_generic,
        )

        # Score/Rating patterns: 4.5/5 stars, 4.8/5.0, 87/100, Grade A
        self.register(
            r"\b\d+(?:\.\d+)?/\d+(?:\.\d+)?\s*(?:stars?|rating)?\b",
            DataPointType.SCORE,
            _parse_score_fraction,
        )
        self.register(
            r"\b(?:grade|score|rating)\s*[A-F][+-]?\b",
            DataPointType.SCORE,
            _parse_score_grade,
        )
        self.register(
            r"\b[A-F][+-]?\s*(?:grade|rating)\b",
            DataPointType.SCORE,
            _parse_score_grade,
        )
        # Single-star with adjacent decimal: ⭐ 4.9, ★4.9, 4.9⭐, 4.9 ☆
        self.register(
            r"(?:[⭐★☆]\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*[⭐★☆])",
            DataPointType.SCORE,
            _parse_score_single_star,
        )
        # Star-rating patterns: ⭐⭐⭐⭐⭐ (5/5), ⭐⭐⭐⭐☆ (4/5), ★★★☆☆ (3/5)
        self.register(
            r"[⭐★☆]{2,}",
            DataPointType.SCORE,
            _parse_score_stars,
        )

        # Ranking patterns: #1, top 10%, first place, 3rd place
        self.register(r"#\d+\b", DataPointType.RANKING, _parse_ranking_hash)
        self.register(r"\btop\s*\d+%?\b", DataPointType.RANKING, _parse_ranking_top)
        self.register(
            rf"\b(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|\d+(?:{_ORDINAL_SUFFIX}))\s*place\b",
            DataPointType.RANKING,
            _parse_ranking_place,
        )

        # Frequency patterns: twice daily, every 3 months, 5 times per week
        self.register(
            r"\b(?:once|twice|thrice|\d+\s*times?)\s*(?:per|a|each)?\s*(?:day|daily|week|weekly|month|monthly|year|yearly|hour|hourly)\b",
            DataPointType.FREQUENCY,
            _parse_frequency,
        )
        self.register(
            r"\bevery\s*\d*\s*(?:day|week|month|year|hour|minute|second)s?\b",
            DataPointType.FREQUENCY,
            _parse_frequency_every,
        )

        # Measurement patterns: 6 feet, 75 kg, 500 ml, 98.6°F
        # A DUAL-unit reading first — `68°F (20°C)` is one temperature quoted
        # twice, not two. Registered before the single-unit pattern so the
        # longest match wins cleanly in _remove_overlaps.
        self.register(
            r"(?<![$€£¥,.\d])\b\d+(?:\.\d+)?\s*°[FC]\s*\(\s*"
            r"\d+(?:\.\d+)?\s*°[FC]\s*\)",
            DataPointType.MEASUREMENT,
            _parse_measurement_temp_dual,
        )
        self.register(
            r"(?<![$€£¥,.\d])\b\d+(?:\.\d+)?\s*°[FC]?(?![FC\w])",
            DataPointType.MEASUREMENT,
            _parse_measurement_temp,
        )
        self.register(
            r"(?<![$€£¥,.\d])\b\d+\s*(?:feet|foot|ft)\s*(?:\d+\s*(?:inches|inch|in))?\b",
            DataPointType.MEASUREMENT,
            _parse_measurement_height,
        )

        # Time range patterns: 8:00 AM - 9:00 PM, 08:00 - 17:00
        self.register(
            rf"\b\d{{1,2}}:\d{{2}}\s*(?:AM|PM)\s*{_RANGE_OP}\s*\d{{1,2}}:\d{{2}}\s*(?:AM|PM)\b",
            DataPointType.TIME,
            _parse_time_range_12h,
        )
        self.register(
            rf"\b(?:[01]?\d|2[0-3]):[0-5]\d\s*{_RANGE_OP}\s*(?:[01]?\d|2[0-3]):[0-5]\d\b",
            DataPointType.TIME,
            _parse_time_range_24h,
        )

        # Time patterns: 3:00 PM, 14:30, 2:30 PM
        self.register(
            rf"\b\d{{1,2}}:\d{{2}}\s*(?:{_AMPM})\b",
            DataPointType.TIME,
            _parse_time_12h,
        )
        self.register(
            r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\s*(?:hours?)?\b",
            DataPointType.TIME,
            _parse_time_24h,
        )
        # Hours-only 12-hour time: 3 PM, 11 AM, 3pm, 11am
        self.register(
            rf"\b(?:1[0-2]|0?[1-9])\s*(?:{_AMPM})\b",
            DataPointType.TIME,
            _parse_time_hours_only,
        )

        # Duration patterns: 3-year period, 2-week period, 45 minutes
        # COMPOUND first — `4 hours 35 minutes`, `1h 20m`, `2 days 4 hours` are
        # one span, not a DURATION and a QUANTITY. Longest match wins, so this
        # outranks the single below.
        self.register(
            r"(?<![$€£¥,.\d])\b\d+\s*(?:h|hr|hrs|hour|hours|d|day|days|"
            r"m|min|mins|minute|minutes|w|week|weeks)\s+"
            r"\d+\s*(?:h|hr|hrs|hour|hours|m|min|mins|minute|minutes|"
            r"s|sec|secs|second|seconds)\b",
            DataPointType.DURATION,
            _parse_duration_compound,
        )
        self.register(
            r"(?<![$€£¥,.\d])\b\d+[-\s](?:year|month|week|day|hour|minute|second)s?\s*(?:period|long)?\b",
            DataPointType.DURATION,
            _parse_duration,
        )

        # Quarter patterns: Q3 2023, Q1 2024
        self.register(r"\bQ[1-4]\s*\d{4}\b", DataPointType.QUARTER, _parse_quarter)
        self.register(r"\b\d{4}\s*Q[1-4]\b", DataPointType.QUARTER, _parse_quarter)

        # Age patterns: 35 years old, 18-24 age group
        self.register(
            r"(?<![$€£¥,.\d])\b\d+\s*years?\s*old\b",
            DataPointType.AGE,
            _parse_age_single,
        )
        self.register(
            r"(?<![$€£¥,.\d])\b\d+-\d+\s*(?:years?\s*old|age\s*group|age\s*range)\b",
            DataPointType.AGE,
            _parse_age_range,
        )
        self.register(r"\bage\s*\d+\b", DataPointType.AGE, _parse_age_simple)

        # Range patterns: 20-30 units, between $100-$500, $100-$500
        self.register(
            r"\bbetween\s*\$?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:and|-)\s*\$?\d+(?:,\d{3})*(?:\.\d+)?\b",
            DataPointType.RANGE,
            _parse_range_between,
        )
        self.register(
            r"\$\d+(?:,\d{3})*(?:\.\d+)?\s*-\s*\$\d+(?:,\d{3})*(?:\.\d+)?",
            DataPointType.RANGE,
            _parse_range_currency,
        )
        # A currency range that names its symbol ONCE and may share a magnitude
        # suffix across both endpoints — `€180-200M` means €180M to €200M, one
        # span rather than `currency €180` and `quantity 200M`.
        self.register(
            rf"{_CURRENCY_SYMBOLS}\d+(?:,\d{{3}})*(?:\.\d+)?\s*{_RANGE_OP}\s*"
            rf"{_CURRENCY_SYMBOLS}?\d+(?:,\d{{3}})*(?:\.\d+)?\s*[KMBT]\b",
            DataPointType.RANGE,
            _parse_range_currency_shared,
        )
        self.register(
            rf"(?<![$€£¥,.\d])\b\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*(?:{_QUANTITY_UNITS})\b",
            DataPointType.RANGE,
            _parse_range_unit,
        )
        # Percentage range: 15-20%, ~15-20%, 10.5-15.5%
        self.register(
            rf"~?\d+(?:\.\d+)?\s*{_RANGE_OP}\s*\d+(?:\.\d+)?%",
            DataPointType.RANGE,
            _parse_range_percentage,
        )

        # Identifier patterns: Invoice #4567, Case ID 2024-001, Order #123
        self.register(
            r"\b(?:Invoice|Order|Case|Ticket|ID|Ref|Reference|Account|Customer|PO|SKU)\b\s*#?\s*[\w-]+\b",
            DataPointType.IDENTIFIER,
            _parse_identifier,
        )

        # Change patterns: +15% increase, -$200 decrease, up 10%
        # Signed quantity change: +3 points, -5 units
        # (?<!\w) prevents matching signs that are attached to a preceding
        # letter/digit (e.g. the hyphens inside OAX-2024-789456).
        self.register(
            rf"(?<!\w){_SIGN}\d+(?:\.\d+)?\s*(?:{_QUANTITY_UNITS})\b",
            DataPointType.CHANGE,
            _parse_change_quantity,
        )
        self.register(
            rf"(?<!\w){_SIGN}\d+(?:\.\d+)?%\s*(?:increase|decrease|change|growth|decline)?",
            DataPointType.CHANGE,
            _parse_change_percentage,
        )
        self.register(
            rf"(?<!\w){_SIGN}\$\d+(?:,\d{{3}})*(?:\.\d+)?\s*(?:increase|decrease|change)?",
            DataPointType.CHANGE,
            _parse_change_currency,
        )
        self.register(
            r"\b(?:up|down|increased|decreased|grew|fell|rose|dropped)\s*(?:by\s*)?\d+(?:\.\d+)?%?",
            DataPointType.CHANGE,
            _parse_change_direction,
        )
        # Bare signed number: +3, -5, +2.5 (no unit/currency/%)
        # Must be registered after specific patterns so longest-match resolution
        # lets +3%, +3 points, +$3 etc. continue to win via _remove_overlaps.
        self.register(
            rf"(?<!\w){_SIGN}\d+(?:\.\d+)?",
            DataPointType.CHANGE,
            _parse_change_bare,
        )

        # Statistical patterns: mean of 50, average of X, median
        self.register(
            r"\b(?:mean|average|avg|median|mode)\s*(?:of|:)?\s*\$?\d+(?:,\d{3})*(?:\.\d+)?",
            DataPointType.STATISTICAL,
            _parse_statistical,
        )

        # International phone: +CC LocalNumber (+52 951 514 4173, +44 20 7946 0958)
        self.register(
            r"\+(?P<cc>\d{1,3})(?P<sep>[ .\-])(?:(?:\d{2,5})(?P=sep))*(?:\d{2,8})\b",
            DataPointType.PHONE,
            _parse_phone_international,
        )

        # Phone patterns: (555) 123-4567, +1-555-123-4567, 555.123.4567
        self.register(
            r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            DataPointType.PHONE,
            _parse_phone,
        )

        # Email patterns: user@example.com
        self.register(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            DataPointType.EMAIL,
            lambda m: {"address": m.lower()},
        )

        # Markdown image: ``![alt](url)``. The link twin below excludes it with
        # a lookbehind, so the two never contest a span. It is here for the same
        # reason the link is: the match is the PROTECTED RANGE that stops the
        # separator and colon splits cutting inside the alt text or the URL.
        # The parser is the link's, handed the span without its ``!``.
        self.register(
            rf"!\[[^\]]*\]\({LINK_DESTINATION}\)",
            DataPointType.IMAGE,
            lambda m: _parse_markdown_link(m[1:]),
        )

        # Drawing-element token: a task control ``[ ]`` / ``[x]`` or a slider
        # ``[65%]`` / ``[3/10]``, bare or as the linked ``[[x]](url)`` /
        # ``[[65%]](url)``. A guard, like IMAGE just above: grouper_sliders and
        # grouper_drawing_elements make the node, after the separators and
        # springs have read the line, and this span is what stops those passes
        # cutting inside it -- and stops PERCENTAGE claiming the ``65%``, or
        # RATIO claiming the ``3/10``, before the token becomes a node.
        _control = (
            r"[ xX]|(?:100(?:\.0+)?|\d{1,2}(?:\.\d+)?)%|\d{1,4}(?:\.\d+)?/\d{1,4}"
        )
        self.register(
            rf"\[\[(?:{_control})\]\]\((?=[^)]){LINK_DESTINATION}\)"
            rf"|(?<!!)\[(?:{_control})\](?!\()",
            DataPointType.DRAWING_ELEMENT,
            lambda m: {"token": m},
        )

        # Markdown link: ``[label](url)``. Negative lookbehind keeps images
        # (``![alt](url)``) out. Registered before URL so the LINK span (the
        # full ``[label](url)`` match) wins via _remove_overlaps' longest-rule
        # against the URL inside the parens.
        self.register(
            rf"(?<!!)\[[^\]]*\]\((?=[^)]){LINK_DESTINATION}\)",
            DataPointType.LINK,
            _parse_markdown_link,
        )

        # Angle-bracket autolink (``<https://…>``). The match spans the
        # brackets so the whole autolink stays ONE node: the bare-URL pattern
        # below excludes ``<``/``>``, so without this it matches *inside* them
        # and the splitter peels the URL out, leaving stray ``<`` / ``>`` text
        # siblings. Registered first — _remove_overlaps keeps the longest match
        # at a start position, so this wins over the URL inside it. The value
        # carries the bare URL; the renderer draws the label without brackets
        # (an autolink is styled like any link inside text — ### Inline).
        self.register(
            r"<https?://[^\s<>]+>",
            DataPointType.URL,
            lambda m: {"url": m[1:-1], "scheme": m[1:-1].split("://")[0]},
        )

        # URL patterns. The character classes exclude the markdown-link
        # delimiters ``( ) [ ]`` so a URL match cannot run past a link's
        # closing paren into the next ``[label](url)`` when links are
        # concatenated with no spaces (e.g. ``…restaurants/)[Lexington](https://…``).
        # Otherwise one over-long URL match would engulf several links and win
        # _remove_overlaps' longest-match rule, deleting the LINK datapoints.
        self.register(
            r"https?://[^\s<>\"'\[\]()]+",
            DataPointType.URL,
            lambda m: {"url": m, "scheme": m.split("://")[0]},
        )
        self.register(
            r"\b(?:www\.)[^\s\[\]()]+\.[a-z]{2,}(?:/[^\s\[\]()]*)?\b"
            r"|\b[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.(?:com|org|net|io|co|dev|app|ai|edu|gov)\b",
            DataPointType.URL,
            lambda m: {"url": m, "scheme": None},
        )

        # Version patterns: require a version signal — a `v` prefix, a 3rd part,
        # or a `-suffix` — so a bare two-part decimal (a price/rating like
        # `10.08`, `3.9`) is NOT a version; it falls through to the decimal
        # NUMBER pattern below. Matches: v1.2 / v1.2.3 / v1.2-beta, 1.2.3 /
        # 1.2.3-rc, 1.2-beta. ``_parse_version`` handles all these forms.
        self.register(
            r"\b(?:v\d+\.\d+(?:\.\d+)?(?:-[\w.]+)?"
            r"|(?<!,)\d+\.\d+\.\d+(?:-[\w.]+)?"
            r"|(?<!,)\d+\.\d+-[\w.]+)\b",
            DataPointType.VERSION,
            _parse_version,
        )

        # File size patterns: 500 MB, 1.5 GB, 2 TB, 100 KB
        self.register(
            r"(?<![$€£¥,.\d])\b\d+(?:\.\d+)?\s*(?:TB|GB|MB|KB|B|tb|gb|mb|kb|bytes?)\b",
            DataPointType.FILE_SIZE,
            _parse_file_size,
        )

        # Per-unit dimensions: 24 cm × 33 cm, 9.5 in × 13 in, 9.5 in by 13 in
        self.register(
            rf"(?<![$€£¥,.\d])\b\d+(?:\.\d+)?\s*(?:{_DIMENSION_UNITS})\s*(?:[xX×]|\bby\b)\s*\d+(?:\.\d+)?\s*(?:{_DIMENSION_UNITS})\b",
            DataPointType.DIMENSION,
            _parse_dimension_per_unit,
        )

        # Dimension patterns: 1920x1080, 8.5" x 11", 4 x 6 inches
        self.register(
            r'(?<![$€£¥,.\d])\b\d+(?:\.\d+)?\s*["\']?\s*[xX×]\s*\d+(?:\.\d+)?\s*["\']?\s*(?:inches|inch|in|cm|mm|px|pixels?)?\b',
            DataPointType.DIMENSION,
            _parse_dimension,
        )

        # Blood type patterns: A+, B-, O+, AB-
        self.register(
            r"\b(?:AB|A|B|O)[+-]\b",
            DataPointType.BLOOD_TYPE,
            _parse_blood_type,
        )

        # Ordinal patterns: 1st, 2nd, 3rd, 4th, 21st
        self.register(
            rf"(?<![$€£¥,.\d])\b\d+(?:{_ORDINAL_SUFFIX})\b",
            DataPointType.ORDINAL,
            _parse_ordinal,
        )

        # Emoji patterns (Unicode ranges)
        self.register(
            _EMOJI_CHAR_RANGES,
            DataPointType.EMOJI,
            _parse_emoji,
        )

        # Unicode fraction patterns: ¼, ½, ¾, ⅓, ⅔, etc.
        self.register(
            r"[\u00BC-\u00BE\u2150-\u215E]+",
            DataPointType.NUMBER,
            _parse_unicode_fraction,
        )

        # Generic number patterns (registered last as fallback)
        # Decimals: 3.14, 0.5, 100.25
        self.register(
            r"(?<!\w-)\b\d+\.\d+\b(?!-\w)",
            DataPointType.NUMBER,
            lambda m: {"value": Decimal(m), "type": "decimal"},
        )
        # Integers: 42, 100, 7
        # (?<!\w-) / (?!-\w) prevent matching digits that are embedded between
        # word characters via hyphens, e.g. X-2026, 2024-X, X-2024-Y.
        self.register(
            r"(?<!\w-)\b\d+\b(?!-\w)",
            DataPointType.NUMBER,
            lambda m: {"value": int(m), "type": "integer"},
        )

    _MARKER_UNDERSCORES = re.compile(r"_+")

    @staticmethod
    def _blank_marker_underscores(text):
        """*text* with emphasis underscore runs replaced by spaces, same length.

        A run counts as emphasis when whitespace or a string edge touches it on
        at least one side — which is what `___x___`, `_x_` and `__x__` look
        like, and what `snake_case` never does. Length is preserved so the
        caller can keep reporting offsets into the ORIGINAL text.
        """
        out = list(text)
        n = len(text)
        for m in DataPointDetector._MARKER_UNDERSCORES.finditer(text):
            a, b = m.start(), m.end()
            before_free = a == 0 or text[a - 1].isspace()
            after_free = b == n or text[b].isspace()
            if before_free or after_free:
                for i in range(a, b):
                    out[i] = " "
        return "".join(out)

    def register(self, pattern, data_type, parser):
        """
        Register a pattern with its type and parser.

        Args:
            pattern: Regex pattern string.
            data_type: DataPointType enum value.
            parser: Function that takes matched string and returns parsed value.
        """
        self.patterns.append((re.compile(pattern, re.IGNORECASE), data_type, parser))
        # A list just grew: guards proven for it no longer cover every entry.
        self._guards: dict[int, tuple[list, PatternGuards]] = {}

    def detect_all(self, text):
        """
        Single optimized pass detecting all registered patterns.

        The UNSCOPED view: every registered type. Kept for scripts, tests and
        exploration (`scripts/detect_data_points.py`). **The pipeline does not call
        this directly** — see :meth:`detect_pipeline` and ADR-102.

        Args:
            text: String to search for data points.

        Returns:
            List of dicts containing type, matched string, value, and index range.
        """
        return self._scan(text, self.patterns)

    def detect_pipeline(self, text):
        """The pipeline's view: only the types something downstream consumes.

        Two reasons a type is in ``_DRAWING_TYPES``, and there is no third:

        * a ``## Drawing elements`` family reads it — DATE (date chip), RATIO /
          SCORE (ratio + unit-ratio bars and rings), PERCENTAGE (Key Value Bars,
          ``## Charts``), CURRENCY / NUMBER / QUANTITY / FILE_SIZE / RATE
          (``## Fixed colors -> ### Datapoints`` pins a color by type), CHANGE
          (``## Fixed colors`` ``change up|down``);
        * the grouper turns it into a NODE — EMOJI and LINK, which become
          ``NodeType.EMOJI`` / ``NodeType.LINK`` in the element peel.

        ``_GUARD_TYPES`` draw nothing and are scanned only to hold their spans
        (see detector_scope). Everything else draws nothing; it was detected for
        a learned layout that is gone (ADR-701), so the pipeline does not scan
        for it.

        Note what narrowing costs, because it is not free: ``node.data_points``
        is also the sole source of ``_protected_ranges``, the no-cut zones that
        stop a separator scan cutting inside a value. A dropped type takes its
        protection with it. Adding one back is a legitimate answer to a bad cut.
        """
        return self._scan(text, self._pipeline_patterns)

    def _scan(self, text, patterns):
        """Run *patterns* over *text*; shared by both entry points above."""
        # `_` is a regex WORD character, so every `\b`-anchored pattern goes
        # blind inside underscores: `___75°___` would detect nothing while
        # `**75°**` detects the number, so one line would make two trees
        # depending on its emphasis spelling. Scan a copy in which underscore
        # runs acting as MARKERS are
        # blanked — same length, so every offset still refers to `text`.
        # Intra-word underscores (`item_2`, `snake_case`) are left alone: only a
        # run touching whitespace or an edge on one side is emphasis.
        scan = self._blank_marker_underscores(text) if "_" in text else text

        # Only the patterns that can match `scan` run (detector_guards). Keyed
        # on the list's identity, holding the list so its id cannot be reused.
        held = self._guards.get(id(patterns))
        if held is None or held[0] is not patterns:
            held = self._guards[id(patterns)] = (patterns, PatternGuards(patterns))
        results = []
        for regex, data_type, parser in held[1].live(scan):
            for match in regex.finditer(scan):
                # Trim whitespace the pattern happened to swallow, and move the
                # span with it. Several patterns end in `\s*(?:...)?` and so
                # match `'4 hours '`, `'750/1800 '`, `'+$3.25 '`; one trim here
                # keeps `matched`, `start` and `end` consistent so no consumer
                # re-trims before comparing spans (the grouper's no-orphan gate).
                start, end = match.start(), match.end()
                raw = text[start:end]
                if "_" in raw and raw != match.group():
                    continue  # the match crossed a blanked marker; not a value
                raw = match.group()
                lead = len(raw) - len(raw.lstrip())
                trail = len(raw) - len(raw.rstrip())
                matched = raw[lead : len(raw) - trail] if (lead or trail) else raw
                if not matched:
                    continue
                start += lead
                end -= trail
                try:
                    value = parser(matched)
                    results.append(
                        {
                            "type": data_type,
                            "matched": matched,
                            "value": value,
                            "start": start,
                            "end": end,
                            "is_approximate": matched.startswith("~"),
                        }
                    )
                except (ValueError, TypeError):
                    continue

        # A sign written right before an unsigned value belongs to it: `-€200`,
        # `-$5K`, `-1,234`, `-5°C` (not after a word character, as in a range
        # `10-20`). The signed match is longer, so it beats a half-match such
        # as `-$5`; appended last, it loses a tie to a pattern that already
        # read the sign (`-$200`).
        results += [r for r in map(take_sign, results, [text] * len(results)) if r]

        results.sort(key=lambda x: x["start"])

        return self._remove_overlaps(results)

    def _remove_overlaps(self, results):
        """
        Remove overlapping matches, keeping the longest one.

        Time complexity: O(R log R) where R is the number of results.
        Uses a greedy approach with sorting.
        """
        if not results:
            return results

        # Sort by start position, then by length descending (longer matches first)
        sorted_results = sorted(
            results, key=lambda x: (x["start"], -(x["end"] - x["start"]))
        )

        filtered = []
        for current in sorted_results:
            if not filtered:
                filtered.append(current)
                continue

            last = filtered[-1]

            if current["start"] < last["end"]:
                current_len = current["end"] - current["start"]
                last_len = last["end"] - last["start"]
                if current_len > last_len:
                    filtered[-1] = current
            else:
                filtered.append(current)

        return filtered

    def detect_by_type(self, text, data_type):
        """
        Detect only specific types of data points.

        Args:
            text: String to search.
            data_type: DataPointType enum value to filter by.

        Returns:
            List of matching data points.
        """
        all_results = self.detect_all(text)
        return [r for r in all_results if r["type"] == data_type]

    def get_types(self):
        """Return list of registered DataPointType values."""
        return list(set(data_type for _, data_type, _ in self.patterns))
