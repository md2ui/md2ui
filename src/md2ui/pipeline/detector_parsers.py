"""Turning a match into a value: one parser per data-point type.

Eighty-odd small functions with one shape — given the text a pattern matched,
return the typed value it stands for. A date string becomes a date, "2.5k"
becomes 2500, "B+" becomes a blood type, "$1,200.50" becomes a Decimal.

They are pure and they are leaves: no state, no regexes of their own, nothing
about WHERE in a document the match came from. The patterns that find these
matches, and the registry that pairs each pattern with its parser, stay in
``data_point_detector.py``; the tables both halves are written in terms of are in
``detector_vocabulary.py``.

The protocol: the pattern table passes each as ``_parse_x``, stores it, and
calls it as ``parser(matched_text)``.

One concept, deliberately whole. The available sub-seam is by domain — dates and
times, money and magnitudes, measurements, contact details — which would scatter
a uniform family across files to satisfy a line count. See ``budgets.txt``.
"""

import re
import unicodedata
from datetime import datetime
from decimal import Decimal

from md2ui.pipeline.detector_vocabulary import (
    _DATE_CHIP_JOIN,
    EMOJI_CHAR_PATTERN,
    EMOJI_NAME_OVERRIDES,
    _CURRENCY_SYMBOLS,
    _DAY_NAMES_RE,
    _DIMENSION_UNITS,
    _DURATION_UNIT_SECONDS,
    _ISO_CURRENCY_CODES,
    _MAGNITUDE,
    _MAGNITUDE_MULTIPLIERS,
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
    _SYMBOL_CURRENCY,
)


def emoji_to_text(char: str) -> str:
    if char in EMOJI_NAME_OVERRIDES:
        return EMOJI_NAME_OVERRIDES[char]
    try:
        return unicodedata.name(char, "UNKNOWN").lower()
    except Exception:
        return "UNKNOWN"


def _combine_date_time(dt_date, time_str, period):
    """Combine a parsed date and time string into a datetime result dict."""
    parts = time_str.split(":")
    hour = int(parts[0])
    # A bare hour ("3 PM") carries no colon; it means minute 0.
    minute = int(parts[1]) if len(parts) > 1 else 0
    second = int(parts[2]) if len(parts) > 2 else 0
    if period:
        p = period.upper()
        if p == "PM" and hour != 12:
            hour += 12
        elif p == "AM" and hour == 12:
            hour = 0
    combined = datetime(dt_date.year, dt_date.month, dt_date.day, hour, minute, second)
    return {
        "datetime": combined,
        "date": dt_date,
        "hour": hour,
        "minute": minute,
        "second": second,
        "subtype": "datetime",
        "has_year": True,
    }


def _parse_datetime_comma(matched):
    """Parse a comma-spelled datetime: 'February 04, 9:17 PM', 'Feb 4, 3 PM',
    'February 4, 2026, 4:00 PM'.

    The year is optional, which is why this cannot simply delegate to
    :meth:`_combine_date_time` — that one builds a real ``datetime`` and so
    hardcodes ``has_year``. When the year is there it does delegate; when it
    is not, it degrades to month/day + hour/minute, the same way
    :meth:`_parse_date_range_endpoint` degrades its endpoints.

    ``subtype`` is ``"datetime"`` either way, which also keeps this off the
    date-chip path — that gate wants ``"partial"`` / ``"weekday_day"``, and a
    chip reading "FEBRUARY / 04" while the time renders elsewhere is exactly
    the split this pattern exists to prevent.
    """
    match = re.match(
        rf"({_MONTH_NAMES})\.? (\d{{1,2}})(?:{_ORDINAL_SUFFIX})?"
        rf"(?:, (\d{{4}}))?[,.]\s*"
        rf"(\d{{1,2}}(?::\d{{2}})?(?::\d{{2}})?)\s*(AM|PM|am|pm)?",
        matched,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("Invalid comma datetime")
    month_name, day, year, time_str, period = match.groups()
    month_num = datetime.strptime(month_name[:3], "%b").month
    if year:
        return _combine_date_time(
            datetime(int(year), month_num, int(day)), time_str, period
        )
    # A bare hour ("3 PM") carries no colon; give it minute 0, as
    # _parse_time_hours_only does.
    parts = time_str.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    if period:
        p = period.upper()
        if p == "PM" and hour != 12:
            hour += 12
        elif p == "AM" and hour == 12:
            hour = 0
    return {
        "month": month_num,
        "day": int(day),
        "hour": hour,
        "minute": minute,
        "subtype": "datetime",
        "has_year": False,
    }


def _parse_weekday_date(matched):
    """Parse a weekday-introduced date: 'Fri, Aug 14', 'Wednesday, February 5,
    2026'.

    ``subtype`` is ``"weekday_date"`` rather than ``"partial"`` so this stays
    off the date chip: that gate wants ``partial`` / ``weekday_day``, and a
    chip built from this span would take ``matched.split()[0]`` as its key —
    rendering "FRI," (comma and all) over the day of a date it dropped.
    """
    match = re.match(
        rf"({_DAY_NAMES_RE}),\s+({_MONTH_NAMES})\.? (\d{{1,2}})"
        rf"(?:{_ORDINAL_SUFFIX})?(?:, (\d{{4}}))?",
        matched,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("Invalid weekday date")
    day_name, month_name, day, year = match.groups()
    value = {
        "day_name": day_name.rstrip("."),
        "month": datetime.strptime(month_name[:3], "%b").month,
        "day": int(day),
        "subtype": "weekday_date",
        "has_year": year is not None,
    }
    if year:
        value["year"] = int(year)
    return value


def _parse_datetime_long_month(matched):
    """Parse combined datetime like 'February 3, 2026 at 4:45 PM'."""
    match = re.match(
        rf"((?:{_MONTH_NAMES_LONG}) \d{{1,2}}, \d{{4}})\s+at\s+(\d{{1,2}}:\d{{2}}(?::\d{{2}})?)\s*(AM|PM|am|pm)?",
        matched,
        re.IGNORECASE,
    )
    if match:
        date_str, time_str, period = match.groups()
        dt_date = datetime.strptime(date_str, "%B %d, %Y")
        return _combine_date_time(dt_date, time_str, period)
    raise ValueError("Invalid long-month datetime")


def _parse_datetime_short_month(matched):
    """Parse combined datetime like 'Feb 3, 2026 at 4:45 PM'."""
    match = re.match(
        rf"((?:{_MONTH_NAMES_SHORT})\.? \d{{1,2}}, \d{{4}})\s+at\s+(\d{{1,2}}:\d{{2}}(?::\d{{2}})?)\s*(AM|PM|am|pm)?",
        matched,
        re.IGNORECASE,
    )
    if match:
        date_str, time_str, period = match.groups()
        dt_date = datetime.strptime(date_str.replace(".", ""), "%b %d, %Y")
        return _combine_date_time(dt_date, time_str, period)
    raise ValueError("Invalid short-month datetime")


def _parse_datetime_iso(matched):
    """Parse combined datetime like '2024-01-15 at 14:30' or '2024-01-15 at 4:45 PM'."""
    match = re.match(
        r"(\d{4}-\d{2}-\d{2})\s+at\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*(AM|PM|am|pm)?",
        matched,
        re.IGNORECASE,
    )
    if match:
        date_str, time_str, period = match.groups()
        dt_date = datetime.strptime(date_str, "%Y-%m-%d")
        return _combine_date_time(dt_date, time_str, period)
    raise ValueError("Invalid ISO datetime")


def _parse_date_range(matched):
    """Parse long month date range like 'January 12-28, 2026'."""
    match = re.match(
        rf"({_MONTH_NAMES_LONG}) (\d{{1,2}})-(\d{{1,2}}), (\d{{4}})",
        matched,
        re.IGNORECASE,
    )
    if match:
        month, start_day, end_day, year = match.groups()
        return {
            "start": datetime.strptime(f"{month} {start_day}, {year}", "%B %d, %Y"),
            "end": datetime.strptime(f"{month} {end_day}, {year}", "%B %d, %Y"),
        }
    raise ValueError("Invalid date range")


def _parse_date_range_short(matched):
    """Parse short month date range like 'Jan 12-28, 2026'."""
    match = re.match(
        rf"({_MONTH_NAMES_SHORT}) (\d{{1,2}})-(\d{{1,2}}), (\d{{4}})",
        matched,
        re.IGNORECASE,
    )
    if match:
        month, start_day, end_day, year = match.groups()
        return {
            "start": datetime.strptime(f"{month} {start_day}, {year}", "%b %d, %Y"),
            "end": datetime.strptime(f"{month} {end_day}, {year}", "%b %d, %Y"),
        }
    raise ValueError("Invalid date range")


def _parse_date_range_two_endpoints(matched):
    """Parse two-endpoint date range like 'Jul 5 - Dec 5' or
    'July 5, 2025 – December 5, 2025'."""
    parts = re.split(r"\s+[-–—]\s+", matched, maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Invalid two-endpoint date range")
    start = _parse_date_range_endpoint(parts[0])
    end = _parse_date_range_endpoint(parts[1])
    return {
        "start": start,
        "end": end,
        "has_year": start["has_year"] and end["has_year"],
    }


def _parse_date_range_endpoint(s):
    """Parse one endpoint of a two-endpoint date range."""
    s = s.strip().rstrip(".")
    for fmt, has_year in (
        ("%B %d, %Y", True),
        ("%b %d, %Y", True),
        ("%B %d", False),
        ("%b %d", False),
    ):
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if has_year:
            return {"datetime": dt, "has_year": True}
        return {"month": dt.month, "day": dt.day, "has_year": False}
    raise ValueError(f"Cannot parse date range endpoint: {s!r}")


def _connector(join: str) -> str:
    """``"dash"`` or ``"space"`` — which spelling joined a date to its day.

    The four chip patterns accept both; the display stage draws a chip for the
    dash alone (``Jun-5``), because the spaced spelling is how dates are
    written in ordinary prose and has no way to decline the drawing.
    """
    return "dash" if join == "-" else "space"


def _parse_date_partial_long(matched):
    """Parse partial dates like 'January 15' or 'March 5th'."""
    match = re.match(
        rf"({_MONTH_NAMES_LONG})({_DATE_CHIP_JOIN})(\d{{1,2}})",
        matched,
        re.IGNORECASE,
    )
    if match:
        month_name, join, day = match.groups()
        month_num = datetime.strptime(month_name, "%B").month
        return {
            "month": month_num,
            "day": int(day),
            "subtype": "partial",
            "connector": _connector(join),
            "has_year": False,
        }
    raise ValueError("Invalid partial date")


def _parse_date_partial_short(matched):
    """Parse partial dates like 'Jan 15' or 'Mar 5th'."""
    match = re.match(
        rf"({_MONTH_NAMES_SHORT})\.?({_DATE_CHIP_JOIN})(\d{{1,2}})",
        matched,
        re.IGNORECASE,
    )
    if match:
        month_name, join, day = match.groups()
        month_num = datetime.strptime(month_name[:3], "%b").month
        return {
            "month": month_num,
            "day": int(day),
            "subtype": "partial",
            "connector": _connector(join),
            "has_year": False,
        }
    raise ValueError("Invalid partial date")


def _parse_full_date_with_month_name(matched):
    """Parse full dates with a month name in any common order:
    '20 May 2017', '20 May, 2017', '20th of May 2017',
    'May 20 2017', 'May 20th, 2017', '5 Jan 2024'."""
    s = re.sub(
        rf"(\d{{1,2}})(?:{_ORDINAL_SUFFIX})",
        r"\1",
        matched,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\b(?:the|of)\b", " ", s, flags=re.IGNORECASE)
    s = s.replace(",", " ").replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        return {"datetime": dt, "subtype": "full", "has_year": True}
    raise ValueError("Invalid full date")


def _parse_month_year(matched):
    """Parse month+year with no day: 'May 2017', 'May, 2017', '2017-05', '05/2017'."""
    s = matched.replace(",", " ").strip()
    s = re.sub(r"\s+", " ", s)
    for fmt in ("%B %Y", "%b %Y", "%Y-%m", "%m/%Y"):
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        return {
            "month": dt.month,
            "year": dt.year,
            "subtype": "month_year",
            "has_year": True,
        }
    raise ValueError("Invalid month-year")


def _parse_date_dotted_short_year(matched):
    """Parse 2-digit-year dotted dates like '20.05.17' (D.M.YY)."""
    return {
        "datetime": datetime.strptime(matched, "%d.%m.%y"),
        "subtype": "full",
        "has_year": True,
    }


def _parse_date_day_only(matched):
    """Parse day-only dates like 'the 15th'."""
    match = re.search(r"(\d{1,2})", matched)
    if match:
        return {
            "day": int(match.group(1)),
            "subtype": "day_only",
            "has_year": False,
        }
    raise ValueError("Invalid day-only date")


def _parse_day_of_week(matched):
    """Parse day of week like 'Monday' or 'Friday'."""
    days = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    day_lower = matched.lower()
    return {
        "day_name": matched.capitalize(),
        "day_index": days.index(day_lower),  # 0 = Monday
        "subtype": "day_of_week",
        "has_year": False,
    }


def _parse_day_of_week_short(matched):
    """Parse short day of week like 'Mon' or 'Fri'."""
    day_map = {
        "mon": ("Monday", 0),
        "tue": ("Tuesday", 1),
        "tues": ("Tuesday", 1),
        "wed": ("Wednesday", 2),
        "thu": ("Thursday", 3),
        "thur": ("Thursday", 3),
        "thurs": ("Thursday", 3),
        "fri": ("Friday", 4),
        "sat": ("Saturday", 5),
        "sun": ("Sunday", 6),
    }
    key = matched.lower().rstrip(".")
    if key in day_map:
        day_name, day_index = day_map[key]
        return {
            "day_name": day_name,
            "day_index": day_index,
            "subtype": "day_of_week",
            "has_year": False,
        }
    raise ValueError("Invalid day of week")


def _parse_weekday_day(matched):
    """Parse weekday + day-of-month like 'Monday 15' or 'Friday 3rd'."""
    days = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    match = re.match(rf"(\w+)({_DATE_CHIP_JOIN})(\d{{1,2}})", matched)
    if match:
        day_name, join, day = match.groups()
        return {
            "day_name": day_name.capitalize(),
            "day_index": days.index(day_name.lower()),
            "day": int(day),
            "subtype": "weekday_day",
            "connector": _connector(join),
            "has_year": False,
        }
    raise ValueError("Invalid weekday+day date")


def _parse_weekday_day_short(matched):
    """Parse abbreviated weekday + day-of-month like 'Mon 15' or 'Tue 10'."""
    day_map = {
        "mon": ("Monday", 0),
        "tue": ("Tuesday", 1),
        "tues": ("Tuesday", 1),
        "wed": ("Wednesday", 2),
        "thu": ("Thursday", 3),
        "thur": ("Thursday", 3),
        "thurs": ("Thursday", 3),
        "fri": ("Friday", 4),
        "sat": ("Saturday", 5),
        "sun": ("Sunday", 6),
    }
    match = re.match(rf"(\w+)\.?({_DATE_CHIP_JOIN})(\d{{1,2}})", matched)
    if match:
        abbrev, join, day = match.groups()
        key = abbrev.lower()
        if key in day_map:
            day_name, day_index = day_map[key]
            return {
                "day_name": day_name,
                "day_index": day_index,
                "day": int(day),
                "subtype": "weekday_day",
                "connector": _connector(join),
                "has_year": False,
            }
    raise ValueError("Invalid weekday+day date")


def _parse_magnitude(matched):
    """Parse magnitude quantities like '3.7 million' or '5,000 million'."""
    match = re.match(
        rf"(\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?)\s*({_MAGNITUDE_WORDS})",
        matched,
        re.IGNORECASE,
    )
    if match:
        value_str, unit = match.groups()
        base_value = Decimal(value_str.replace(",", ""))
        multiplier = _MAGNITUDE_MULTIPLIERS[unit.lower()]
        return {
            "value": base_value * multiplier,
            "base_value": base_value,
            "unit": unit.lower(),
        }
    raise ValueError("Invalid magnitude")


def _parse_iso_currency(matched: str) -> dict:
    """Parse ISO currency forms: 'MXN 85.00', '$85.00 MXN', '1,200 USD'."""
    s = matched.strip()
    # Prefix form: CODE<space>[symbol]amount
    m = re.match(
        rf"\b({_ISO_CURRENCY_CODES})\s+{_CURRENCY_SYMBOLS}?(\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?)",
        s,
        re.IGNORECASE,
    )
    if m:
        return {
            "amount": Decimal(m.group(2).replace(",", "")),
            "currency": m.group(1).upper(),
        }
    # Suffix form: [symbol]amount<space>CODE
    m = re.match(
        rf"{_CURRENCY_SYMBOLS}?(\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?)\s+({_ISO_CURRENCY_CODES})\b",
        s,
        re.IGNORECASE,
    )
    if m:
        return {
            "amount": Decimal(m.group(1).replace(",", "")),
            "currency": m.group(2).upper(),
        }
    raise ValueError(f"Could not parse ISO currency: {matched!r}")


def _parse_currency_trailing_symbol(matched: str) -> dict:
    """Parse an amount with a trailing currency symbol: '2,36 €', '45€',
    '$2.36 €', '1.200,50 €', '1,200.50 €'. The trailing symbol decides the
    currency; the decimal separator is inferred so both US ('.' decimal,
    ',' thousands) and European (',' decimal, '.' thousands) forms parse."""
    symbols = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
    s = matched.strip()
    trailing = s[-1]
    digits = re.search(r"\d+(?:[.,]\d+)*", s)
    if not digits:
        raise ValueError(f"Invalid trailing-symbol currency: {matched!r}")
    return {
        "amount": _normalize_amount(digits.group()),
        "currency": symbols.get(trailing, trailing),
    }


def _normalize_amount(num: str) -> Decimal:
    """Convert a number string with mixed '.'/',' grouping to a Decimal.

    Rules: when both separators appear, the rightmost is the decimal point.
    When only ',' appears, it is the decimal point unless it groups exactly
    three trailing digits (then it is a thousands separator). A lone '.' is
    treated as a decimal point; a repeated '.' can only be a thousands
    separator, so every group after the first must be three digits.

    Anything else ('25.12.2021', '1.2.3') is not an amount, and says so with
    ``ValueError`` — the detector's signal for "not this type".
    """
    if "." in num and "," in num:
        if num.rfind(".") > num.rfind(","):
            num = num.replace(",", "")
        else:
            num = num.replace(".", "").replace(",", ".")
    elif "," in num:
        parts = num.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:
            num = num.replace(",", ".")
        else:
            num = num.replace(",", "")
    elif num.count(".") > 1:
        if any(len(group) != 3 for group in num.split(".")[1:]):
            raise ValueError(f"Not an amount: {num!r}")
        num = num.replace(".", "")
    return Decimal(num)


def _parse_currency_magnitude(matched, currency):
    """Parse expressions like '$89 billion' or '£1.2 trillion'."""
    m = re.match(
        rf"[^\d]*(\d+(?:\.\d+)?)\s*({_MAGNITUDE_WORDS})",
        matched,
        re.IGNORECASE,
    )
    if m:
        base, word = m.groups()
        return {
            "amount": Decimal(base) * _MAGNITUDE_MULTIPLIERS[word.lower()],
            "base_value": Decimal(base),
            "magnitude": word.lower(),
            "currency": currency,
        }
    raise ValueError("Invalid currency magnitude")


def _parse_shorthand_magnitude(matched):
    """Parse shorthand like '2.5B', '500K', '1.2M'."""
    _suffix_multipliers = {
        "k": Decimal("1000"),
        "m": Decimal("1000000"),
        "b": Decimal("1000000000"),
        "t": Decimal("1000000000000"),
    }
    m = re.match(r"(\d+(?:\.\d+)?)([KkMmBbTt])\b", matched)
    if m:
        base, suffix = m.groups()
        multiplier = _suffix_multipliers[suffix.lower()]
        return {
            "value": Decimal(base) * multiplier,
            "base_value": Decimal(base),
            "magnitude": suffix.upper(),
        }
    raise ValueError("Invalid shorthand magnitude")


def _parse_currency_shorthand(matched, currency):
    """Parse shorthand currency like '$50M', '€1.2B', '£500K'."""
    _suffix_multipliers = {
        "k": Decimal("1000"),
        "m": Decimal("1000000"),
        "b": Decimal("1000000000"),
        "t": Decimal("1000000000000"),
    }
    m = re.match(r"[^\d]*(\d+(?:\.\d+)?)([KkMmBbTt])\b", matched)
    if m:
        base, suffix = m.groups()
        multiplier = _suffix_multipliers[suffix.lower()]
        return {
            "amount": Decimal(base) * multiplier,
            "base_value": Decimal(base),
            "magnitude": suffix.upper(),
            "currency": currency,
        }
    raise ValueError("Invalid currency shorthand")


def _parse_quantity(matched):
    """Parse quantities with units like '250 units', '100 kg', '5,000 units'."""
    match = re.match(r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(\w+)", matched, re.IGNORECASE)
    if match:
        value_str, unit = match.groups()
        return {
            "value": Decimal(value_str.replace(",", "")),
            "unit": unit.lower(),
        }
    raise ValueError("Invalid quantity")


def _parse_ratio_colon(matched):
    """Parse ratios like '3:1' or '1:100'."""
    parts = matched.split(":")
    return {
        "left": int(parts[0]),
        "right": int(parts[1]),
        "format": "colon",
    }


def _parse_ratio_slash(matched):
    """Parse ratios like '50/50'."""
    parts = matched.split("/")
    return {
        "left": int(parts[0]),
        "right": int(parts[1]),
        "format": "slash",
    }


def _parse_rate_speed(matched):
    """Parse speed rates like '60 mph', '100 km/h' or 'N 2 mph'.

    A compass bearing may introduce the speed (`W 8 mph`); it qualifies the
    reading rather than being a separate value, so it is kept here as
    ``bearing``. NOTE the pattern must stay in step with this parser: a
    raise is SILENT — detect_all drops the match — so a bearing accepted by
    the pattern but rejected here would make the whole rate vanish.
    """
    match = re.match(
        r"(?:([NSEW]{1,3})\s+)?(\d+(?:\.\d+)?)\s*(\w+/?(?:\w+)?)",
        matched,
    )
    if match:
        bearing, value_str, unit = match.groups()
        out = {
            "value": Decimal(value_str),
            "unit": unit.lower(),
            "rate_type": "speed",
        }
        if bearing:
            out["bearing"] = bearing
        return out
    raise ValueError("Invalid speed rate")


def _parse_rate_speed_range(matched):
    """Parse speed ranges like '7-10 mph' or '15-20 km/h'.

    Carries both endpoints, so a renderer can show the span instead of the
    upper bound alone; ``rate_type`` matches _parse_rate_speed so both take
    the same styling.
    """
    match = re.match(
        rf"(?:([NSEW]{{1,3}})\s+)?(\d+(?:\.\d+)?)\s*{_RANGE_OP}\s*"
        rf"(\d+(?:\.\d+)?)\s*({_SPEED_UNITS})",
        matched,
        re.IGNORECASE,
    )
    if match:
        bearing, min_val, max_val, unit = match.groups()
        out = {
            "min": Decimal(min_val),
            "max": Decimal(max_val),
            "unit": unit.lower(),
            "rate_type": "speed",
        }
        if bearing:
            out["bearing"] = bearing
        return out
    raise ValueError("Invalid speed range")


def _parse_rate_commodity(matched):
    """Parse commodity price rates like '$2,048/oz' or '€73.45/barrel'."""
    _symbols = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
    m = re.match(rf"({_CURRENCY_SYMBOLS})(\d[\d,]*)(?:\.(\d+))?/(\w+)", matched)
    if m:
        symbol, integer_part, decimal_part, unit = m.groups()
        amount_str = integer_part.replace(",", "")
        if decimal_part:
            amount_str += "." + decimal_part
        return {
            "value": Decimal(amount_str),
            "currency": _symbols.get(symbol, symbol),
            "per": unit.lower(),
            "rate_type": "price",
        }
    raise ValueError("Invalid commodity rate")


def _parse_rate_price(matched):
    """Parse price rates like '$15/hour'."""
    match = re.match(r"\$(\d+(?:\.\d+)?)/(\w+)", matched, re.IGNORECASE)
    if match:
        value_str, period = match.groups()
        return {
            "value": Decimal(value_str),
            "currency": "USD",
            "per": period.lower(),
            "rate_type": "price",
        }
    raise ValueError("Invalid price rate")


def _parse_rate_percentage(matched):
    """Parse percentage rates like '5% annual growth'."""
    match = re.match(r"(\d+(?:\.\d+)?)%\s*(\w+(?:\s+\w+)?)", matched, re.IGNORECASE)
    if match:
        value_str, period = match.groups()
        return {
            "value": Decimal(value_str),
            "period": period.lower(),
            "rate_type": "percentage",
        }
    raise ValueError("Invalid percentage rate")


def _parse_rate_generic(matched):
    """Parse generic rates like '10 per hour'."""
    match = re.match(r"(\d+(?:\.\d+)?)\s*(?:per|/)\s*(\w+)", matched, re.IGNORECASE)
    if match:
        value_str, period = match.groups()
        return {
            "value": Decimal(value_str),
            "per": period.lower(),
            "rate_type": "generic",
        }
    raise ValueError("Invalid generic rate")


def _parse_score_fraction(matched):
    """Parse scores like '4.5/5 stars' or '87/100'."""
    match = re.match(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\s*(\w*)", matched, re.IGNORECASE)
    if match:
        score, max_score, label = match.groups()
        return {
            "score": Decimal(score),
            "max": Decimal(max_score),
            "label": label.lower() if label else None,
        }
    raise ValueError("Invalid score fraction")


def _parse_score_stars(matched):
    """Parse star ratings like '⭐⭐⭐⭐☆' (4/5) or '⭐⭐⭐⭐⭐' (5/5)."""
    filled = sum(1 for c in matched if c in "⭐★")
    empty = sum(1 for c in matched if c == "☆")
    total = filled + empty
    if filled == 0:
        raise ValueError("Star rating requires at least one filled star")
    return {
        "score": Decimal(filled),
        "max": Decimal(total),
        "label": "stars",
    }


def _parse_score_single_star(matched):
    """Parse a single-star rating like '⭐ 4.9' or '4.9⭐'."""
    glyph = next((c for c in matched if c in "⭐★☆"), "⭐")
    digits = re.search(r"\d+(?:\.\d+)?", matched)
    if not digits:
        raise ValueError("Invalid single-star score")
    return {
        "score": Decimal(digits.group(0)),
        "glyph": glyph,
        "subtype": "single_star",
    }


def _parse_score_grade(matched):
    """Parse letter grades like 'Grade A' or 'A+'."""
    match = re.search(r"([A-F][+-]?)", matched, re.IGNORECASE)
    if match:
        grade = match.group(1).upper()
        return {
            "grade": grade,
            "numeric": _grade_to_numeric(grade),
        }
    raise ValueError("Invalid grade")


def _grade_to_numeric(grade):
    """Convert letter grade to numeric value."""
    base_values = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}
    base = base_values.get(grade[0], 0.0)
    if len(grade) > 1:
        if grade[1] == "+":
            base += 0.3
        elif grade[1] == "-":
            base -= 0.3
    return Decimal(str(base))


def _parse_ranking_hash(matched):
    """Parse rankings like '#1' or '#10'."""
    rank = int(matched[1:])
    return {
        "rank": rank,
        "format": "hash",
    }


def _parse_ranking_top(matched):
    """Parse rankings like 'top 10' or 'top 10%'."""
    match = re.search(r"(\d+)(%?)", matched, re.IGNORECASE)
    if match:
        value, is_percent = match.groups()
        return {
            "value": int(value),
            "is_percentage": bool(is_percent),
            "format": "top",
        }
    raise ValueError("Invalid top ranking")


def _parse_ranking_place(matched):
    """Parse rankings like 'first place' or '3rd place'."""
    ordinal_map = {
        "first": 1,
        "1st": 1,
        "second": 2,
        "2nd": 2,
        "third": 3,
        "3rd": 3,
        "fourth": 4,
        "4th": 4,
        "fifth": 5,
        "5th": 5,
    }
    lower_matched = matched.lower()
    for word, rank in ordinal_map.items():
        if word in lower_matched:
            return {"rank": rank, "format": "place"}

    # Handle numeric ordinals like "10th place"
    match = re.search(rf"(\d+)(?:{_ORDINAL_SUFFIX})", lower_matched)
    if match:
        return {"rank": int(match.group(1)), "format": "place"}

    raise ValueError("Invalid place ranking")


def _parse_frequency(matched):
    """Parse frequencies like 'twice daily' or '3 times per week'."""
    word_to_num = {"once": 1, "twice": 2, "thrice": 3}
    lower_matched = matched.lower()

    # Extract count
    count = None
    for word, num in word_to_num.items():
        if word in lower_matched:
            count = num
            break

    if count is None:
        match = re.search(r"(\d+)\s*times?", lower_matched)
        if match:
            count = int(match.group(1))

    # Extract period
    period = None
    for p in [
        "daily",
        "day",
        "weekly",
        "week",
        "monthly",
        "month",
        "yearly",
        "year",
        "hourly",
        "hour",
    ]:
        if p in lower_matched:
            period = p.rstrip("ly")
            break

    return {
        "count": count or 1,
        "period": period,
    }


def _parse_frequency_every(matched):
    """Parse frequencies like 'every 3 months'."""
    match = re.match(r"every\s*(\d*)\s*(\w+)", matched, re.IGNORECASE)
    if match:
        interval, period = match.groups()
        return {
            "interval": int(interval) if interval else 1,
            "period": period.lower().rstrip("s"),
        }
    raise ValueError("Invalid frequency")


def _parse_measurement_temp_dual(matched):
    """Parse a temperature quoted in two units — '68°F (20°C)'.

    One reading, so it stays one data point: the parenthesised half becomes
    ``alt_value`` / ``alt_unit`` rather than a second, competing datapoint
    that the layout would space away from the first.
    """
    match = re.match(
        r"(\d+(?:\.\d+)?)\s*°([FC])\s*\(\s*(\d+(?:\.\d+)?)\s*°([FC])\s*\)",
        matched,
        re.IGNORECASE,
    )
    if match:
        value, unit, alt_value, alt_unit = match.groups()
        return {
            "value": Decimal(value),
            "unit": unit.upper(),
            "alt_value": Decimal(alt_value),
            "alt_unit": alt_unit.upper(),
            "measurement_type": "temperature",
        }
    raise ValueError("Invalid dual-unit temperature")


def _parse_measurement_temp(matched):
    """Parse temperatures like '98.6°F', '37°C' or a bare '75°'.

    The unit is optional: every other unit is absorbed into its datapoint
    (``75%``, ``75 kg``, ``$412M``, ``75km/h``), and a bare degree sign left
    behind would become an orphan leaf of its own. Raising here would be silent —
    ``detect_all`` swallows the exception and the match is dropped — so the
    pattern and this parser have to agree.
    """
    match = re.match(r"(\d+(?:\.\d+)?)\s*°([FC]?)", matched, re.IGNORECASE)
    if match:
        value, unit = match.groups()
        return {
            "value": Decimal(value),
            "unit": unit.upper(),
            "measurement_type": "temperature",
        }
    raise ValueError("Invalid temperature")


def _parse_measurement_height(matched):
    """Parse heights like '6 feet' or '5 feet 10 inches'."""
    match = re.match(
        r"(\d+)\s*(?:feet|foot|ft)\s*(?:(\d+)\s*(?:inches|inch|in))?",
        matched,
        re.IGNORECASE,
    )
    if match:
        feet, inches = match.groups()
        return {
            "feet": int(feet),
            "inches": int(inches) if inches else 0,
            "total_inches": int(feet) * 12 + (int(inches) if inches else 0),
            "measurement_type": "height",
        }
    raise ValueError("Invalid height")


def _parse_time_12h(matched):
    """Parse 12-hour times like '3:00 PM' or '11:30 am'."""
    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", matched, re.IGNORECASE)
    if match:
        hour, minute, period = match.groups()
        hour = int(hour)
        minute = int(minute)
        hour_24 = hour
        if period.upper() == "PM" and hour != 12:
            hour_24 += 12
        elif period.upper() == "AM" and hour == 12:
            hour_24 = 0
        return {
            "hour": hour_24,
            "minute": minute,
            "subtype": "time_12h",
            "period": period.upper(),
        }
    raise ValueError("Invalid 12h time")


def _parse_time_hours_only(matched):
    """Parse hours-only 12-hour times like '3 PM' or '11 AM'."""
    m = re.match(r"(\d{1,2})\s*(AM|PM)", matched, re.IGNORECASE)
    if m:
        hour, period = m.groups()
        hour = int(hour)
        hour_24 = hour
        if period.upper() == "PM" and hour != 12:
            hour_24 += 12
        elif period.upper() == "AM" and hour == 12:
            hour_24 = 0
        return {
            "hour": hour_24,
            "minute": 0,
            "subtype": "time_12h",
            "period": period.upper(),
        }
    raise ValueError("Invalid hours-only time")


def _parse_time_24h(matched):
    """Parse 24-hour times like '14:30' or '09:15'."""
    match = re.match(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", matched)
    if match:
        hour, minute, second = match.groups()
        return {
            "hour": int(hour),
            "minute": int(minute),
            "second": int(second) if second else 0,
            "subtype": "time_24h",
        }
    raise ValueError("Invalid 24h time")


def _parse_time_range_12h(matched):
    """Parse 12-hour time ranges like '8:00 AM - 5:00 PM'."""
    match = re.match(
        rf"(\d{{1,2}}):(\d{{2}})\s*(AM|PM)\s*{_RANGE_OP}\s*(\d{{1,2}}):(\d{{2}})\s*(AM|PM)",
        matched,
        re.IGNORECASE,
    )
    if match:
        h1, m1, p1, h2, m2, p2 = match.groups()
        # Convert to 24h
        hour1 = int(h1)
        if p1.upper() == "PM" and hour1 != 12:
            hour1 += 12
        elif p1.upper() == "AM" and hour1 == 12:
            hour1 = 0

        hour2 = int(h2)
        if p2.upper() == "PM" and hour2 != 12:
            hour2 += 12
        elif p2.upper() == "AM" and hour2 == 12:
            hour2 = 0

        return {
            "start": {"hour": hour1, "minute": int(m1)},
            "end": {"hour": hour2, "minute": int(m2)},
            "subtype": "time_range",
        }
    raise ValueError("Invalid 12h time range")


def _parse_time_range_24h(matched):
    """Parse 24-hour time ranges like '08:00 - 17:00'."""
    match = re.match(
        rf"(\d{{1,2}}):(\d{{2}})\s*{_RANGE_OP}\s*(\d{{1,2}}):(\d{{2}})",
        matched,
    )
    if match:
        h1, m1, h2, m2 = match.groups()
        return {
            "start": {"hour": int(h1), "minute": int(m1)},
            "end": {"hour": int(h2), "minute": int(m2)},
            "subtype": "time_range",
        }
    raise ValueError("Invalid 24h time range")


def _parse_duration_compound(matched):
    """Parse a compound duration — '4 hours 35 minutes', '1h 20m'.

    Both halves are one span, so they are summed into ``seconds`` and the
    parts kept for rendering.
    """
    parts = re.findall(r"(\d+)\s*([A-Za-z]+)", matched)
    total = 0
    kept = []
    for value, unit in parts:
        key = unit.lower().rstrip("s") or unit.lower()
        secs = _DURATION_UNIT_SECONDS.get(key)
        if secs is None:
            raise ValueError("Invalid compound duration")
        total += int(value) * secs
        kept.append({"value": int(value), "unit": key})
    if len(kept) < 2:
        raise ValueError("Invalid compound duration")
    return {"seconds": total, "parts": kept, "compound": True}


def _parse_duration(matched):
    """Parse durations like '3-year period' or '2 weeks'."""
    match = re.match(r"(\d+)[-\s]*(\w+)", matched, re.IGNORECASE)
    if match:
        value, unit = match.groups()
        unit = unit.lower().rstrip("s")
        if unit == "period" or unit == "long":
            # Find the actual unit
            for u in [
                "year",
                "month",
                "week",
                "day",
                "hour",
                "minute",
                "second",
            ]:
                if u in matched.lower():
                    unit = u
                    break
        return {
            "value": int(value),
            "unit": unit,
        }
    raise ValueError("Invalid duration")


def _parse_quarter(matched):
    """Parse quarters like 'Q3 2023' or '2024 Q1'."""
    match = re.search(r"Q([1-4])\s*(\d{4})|(\d{4})\s*Q([1-4])", matched, re.IGNORECASE)
    if match:
        if match.group(1):
            quarter, year = match.group(1), match.group(2)
        else:
            year, quarter = match.group(3), match.group(4)
        return {
            "quarter": int(quarter),
            "year": int(year),
        }
    raise ValueError("Invalid quarter")


def _parse_age_single(matched):
    """Parse ages like '35 years old'."""
    match = re.match(r"(\d+)\s*years?\s*old", matched, re.IGNORECASE)
    if match:
        return {
            "age": int(match.group(1)),
            "type": "single",
        }
    raise ValueError("Invalid age")


def _parse_age_range(matched):
    """Parse age ranges like '18-24 age group'."""
    match = re.match(r"(\d+)-(\d+)", matched)
    if match:
        return {
            "min_age": int(match.group(1)),
            "max_age": int(match.group(2)),
            "type": "range",
        }
    raise ValueError("Invalid age range")


def _parse_age_simple(matched):
    """Parse simple ages like 'age 35'."""
    match = re.search(r"(\d+)", matched)
    if match:
        return {
            "age": int(match.group(1)),
            "type": "single",
        }
    raise ValueError("Invalid age")


def _parse_range_between(matched):
    """Parse ranges like 'between $100 and $500'."""
    match = re.search(
        r"\$?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:and|-)\s*\$?(\d+(?:,\d{3})*(?:\.\d+)?)",
        matched,
        re.IGNORECASE,
    )
    if match:
        min_val = match.group(1).replace(",", "")
        max_val = match.group(2).replace(",", "")
        is_currency = "$" in matched
        return {
            "min": Decimal(min_val),
            "max": Decimal(max_val),
            "is_currency": is_currency,
        }
    raise ValueError("Invalid between range")


def _parse_range_currency(matched):
    """Parse currency ranges like '$100-$500'."""
    match = re.match(
        r"\$(\d+(?:,\d{3})*(?:\.\d+)?)\s*-\s*\$(\d+(?:,\d{3})*(?:\.\d+)?)",
        matched,
    )
    if match:
        return {
            "min": Decimal(match.group(1).replace(",", "")),
            "max": Decimal(match.group(2).replace(",", "")),
            "currency": "USD",
        }
    raise ValueError("Invalid currency range")


def _parse_range_currency_shared(matched):
    """Parse a currency range with one symbol and a shared magnitude —
    '€180-200M', '$1.2-1.5M'.

    The suffix belongs to BOTH endpoints, which is why the range has to be
    read as a whole: `€180-200M` is €180M to €200M, not €180 to €200M.
    """
    m = re.match(
        rf"({_CURRENCY_SYMBOLS})(\d+(?:,\d{{3}})*(?:\.\d+)?)\s*{_RANGE_OP}\s*"
        rf"{_CURRENCY_SYMBOLS}?(\d+(?:,\d{{3}})*(?:\.\d+)?)\s*([KMBT])",
        matched,
        re.IGNORECASE,
    )
    if not m:
        raise ValueError("Invalid shared-magnitude currency range")
    symbol, lo, hi, mag = m.groups()
    factor = _MAGNITUDE[mag.upper()]
    return {
        "min": Decimal(lo.replace(",", "")) * factor,
        "max": Decimal(hi.replace(",", "")) * factor,
        "currency": _SYMBOL_CURRENCY.get(symbol, "USD"),
        "magnitude": mag.upper(),
    }


def _parse_range_unit(matched):
    """Parse ranges with units like '20-30 units'."""
    match = re.match(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(\w+)", matched)
    if match:
        min_val, max_val, unit = match.groups()
        return {
            "min": Decimal(min_val),
            "max": Decimal(max_val),
            "unit": unit.lower(),
        }
    raise ValueError("Invalid unit range")


def _parse_range_percentage(matched):
    """Parse percentage ranges like '15-20%', '~15-20%', or '10.5 to 15.5%'."""
    match = re.match(rf"~?(\d+(?:\.\d+)?)\s*{_RANGE_OP}\s*(\d+(?:\.\d+)?)%", matched)
    if match:
        min_val, max_val = match.groups()
        return {
            "min": Decimal(min_val),
            "max": Decimal(max_val),
            "unit": "percent",
        }
    raise ValueError("Invalid percentage range")


def _parse_identifier(matched):
    """Parse identifiers like 'Invoice #4567' or 'Case ID 2024-001'."""
    match = re.match(r"(\w+)\s*#?\s*([\w-]+)", matched, re.IGNORECASE)
    if match:
        id_type, id_value = match.groups()
        return {
            "type": id_type.lower(),
            "value": id_value,
        }
    raise ValueError("Invalid identifier")


def _parse_signed_percentage(matched):
    """Parse percentages like '~12%' or '−1.55%': either minus is negative."""
    value = matched.lstrip("~").rstrip("%")
    return Decimal("-" + value[1:] if value[:1] in _MINUS else value)


def _parse_change_percentage(matched):
    """Parse percentage changes like '+15% increase'."""
    match = re.match(rf"({_SIGN})(\d+(?:\.\d+)?)%\s*(\w*)", matched)
    if match:
        sign, value, direction = match.groups()
        return {
            "value": Decimal(value) * (1 if sign == "+" else -1),
            "direction": direction.lower()
            if direction
            else ("increase" if sign == "+" else "decrease"),
            "type": "percentage",
        }
    raise ValueError("Invalid percentage change")


def _parse_change_quantity(matched):
    """Parse signed quantity changes like '+3 points' or '-5 units'."""
    m = re.match(
        rf"({_SIGN})(\d+(?:\.\d+)?)\s*({_QUANTITY_UNITS})",
        matched,
        re.IGNORECASE,
    )
    if m:
        sign, value, unit = m.groups()
        return {
            "value": Decimal(value) * (1 if sign == "+" else -1),
            "unit": unit.lower(),
            "direction": "increase" if sign == "+" else "decrease",
            "type": "quantity",
        }
    raise ValueError("Invalid quantity change")


def _parse_change_currency(matched):
    """Parse currency changes like '-$200 decrease'."""
    match = re.match(rf"({_SIGN})\$(\d+(?:,\d{{3}})*(?:\.\d+)?)\s*(\w*)", matched)
    if match:
        sign, value, direction = match.groups()
        return {
            "value": Decimal(value.replace(",", "")) * (1 if sign == "+" else -1),
            "currency": "USD",
            "direction": direction.lower()
            if direction
            else ("increase" if sign == "+" else "decrease"),
            "type": "currency",
        }
    raise ValueError("Invalid currency change")


def _parse_change_direction(matched):
    """Parse directional changes like 'up 10%' or 'increased by 5'."""
    lower = matched.lower()
    is_positive = any(w in lower for w in ["up", "increased", "grew", "rose"])

    match = re.search(r"(\d+(?:\.\d+)?)\s*(%?)", matched)
    if match:
        value, is_percent = match.groups()
        return {
            "value": Decimal(value) * (1 if is_positive else -1),
            "direction": "increase" if is_positive else "decrease",
            "is_percentage": bool(is_percent),
        }
    raise ValueError("Invalid directional change")


def _parse_change_bare(matched):
    """Parse bare signed number changes like '+3' or '-5'."""
    m = re.match(rf"({_SIGN})(\d+(?:\.\d+)?)", matched)
    if m:
        sign, value = m.groups()
        return {
            "value": Decimal(value) * (1 if sign == "+" else -1),
            "direction": "increase" if sign == "+" else "decrease",
            "type": "bare",
        }
    raise ValueError("Invalid bare change")


def _parse_statistical(matched):
    """Parse statistical values like 'mean of 50' or 'average: $60K'."""
    stat_type = None
    for s in ["mean", "average", "avg", "median", "mode"]:
        if s in matched.lower():
            stat_type = "average" if s == "avg" else s
            break

    match = re.search(
        r"\$?(\d+(?:,\d{3})*(?:\.\d+)?)\s*(K|M|B)?", matched, re.IGNORECASE
    )
    if match:
        value_str, multiplier = match.groups()
        value = Decimal(value_str.replace(",", ""))
        if multiplier:
            mult_map = {"K": 1000, "M": 1000000, "B": 1000000000}
            value *= mult_map.get(multiplier.upper(), 1)
        return {
            "stat_type": stat_type,
            "value": value,
            "is_currency": "$" in matched,
        }
    raise ValueError("Invalid statistical value")


def _parse_phone(matched):
    """Parse phone numbers like '(555) 123-4567' or '+1-555-123-4567'."""
    digits = re.sub(r"\D", "", matched)
    # Format based on length
    if len(digits) == 10:
        formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == "1":
        formatted = f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        formatted = matched
    return {
        "digits": digits,
        "formatted": formatted,
    }


def _parse_phone_international(matched):
    """Parse international phone numbers like '+52 951 514 4173' or '+44-20-7946-0958'."""
    m = re.match(
        r"\+(?P<cc>\d{1,3})(?P<sep>[ .\-])(?:(?:\d{2,5})(?P=sep))*(?:\d{2,8})",
        matched,
    )
    if not m:
        raise ValueError(f"Cannot parse international phone: {matched!r}")

    country_code = m.group("cc")
    digits = re.sub(r"\D", "", matched)

    if not (7 <= len(digits) <= 15):
        raise ValueError(f"Digit count {len(digits)} outside E.164 range: {matched!r}")

    formatted = matched
    if country_code == "1" and len(digits) == 11:
        formatted = f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

    return {
        "digits": digits,
        "country_code": country_code,
        "formatted": formatted,
    }


def _parse_version(matched):
    """Parse version numbers like 'v1.2.3' or '2.0.0-beta'."""
    version_str = matched.lstrip("vV")
    parts = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?(?:-(.+))?", version_str)
    if parts:
        major, minor, patch, prerelease = parts.groups()
        return {
            "major": int(major),
            "minor": int(minor),
            "patch": int(patch) if patch else 0,
            "prerelease": prerelease,
            "string": version_str,
        }
    raise ValueError("Invalid version")


def _parse_file_size(matched):
    """Parse file sizes like '500 MB' or '1.5 GB'."""
    match = re.match(r"(\d+(?:\.\d+)?)\s*(\w+)", matched, re.IGNORECASE)
    if match:
        value, unit = match.groups()
        unit = unit.upper().rstrip("S")  # normalize
        if unit == "BYTE":
            unit = "B"
        multipliers = {
            "B": 1,
            "KB": 1024,
            "MB": 1024**2,
            "GB": 1024**3,
            "TB": 1024**4,
        }
        bytes_value = Decimal(value) * multipliers.get(unit, 1)
        return {
            "value": Decimal(value),
            "unit": unit,
            "bytes": bytes_value,
        }
    raise ValueError("Invalid file size")


def _parse_dimension(matched):
    """Parse dimensions like '1920x1080' or '8.5 x 11 inches'."""
    match = re.match(
        r'(\d+(?:\.\d+)?)\s*["\']?\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["\']?\s*(\w*)',
        matched,
    )
    if match:
        width, height, unit = match.groups()
        return {
            "width": Decimal(width),
            "height": Decimal(height),
            "unit": unit.lower() if unit else None,
        }
    raise ValueError("Invalid dimension")


def _parse_dimension_per_unit(matched):
    """Parse per-unit dimensions like '24 cm × 33 cm' or '9.5 in by 13 in'."""
    m = re.match(
        rf"(\d+(?:\.\d+)?)\s*({_DIMENSION_UNITS})\s*(?:[xX×]|by)\s*(\d+(?:\.\d+)?)\s*({_DIMENSION_UNITS})",
        matched,
        re.IGNORECASE,
    )
    if m:
        w, unit_w, h, _unit_h = m.groups()
        return {
            "width": Decimal(w),
            "height": Decimal(h),
            "unit": unit_w.lower(),
        }
    raise ValueError("Invalid per-unit dimension")


def _parse_blood_type(matched):
    """Parse blood types like 'A+' or 'AB-'."""
    match = re.match(r"(AB|A|B|O)([+-])", matched, re.IGNORECASE)
    if match:
        abo, rh = match.groups()
        return {
            "abo": abo.upper(),
            "rh": "positive" if rh == "+" else "negative",
            "full": f"{abo.upper()}{rh}",
        }
    raise ValueError("Invalid blood type")


def _parse_ordinal(matched):
    """Parse ordinals like '1st', '2nd', '3rd', '4th'."""
    match = re.match(r"(\d+)(st|nd|rd|th)", matched, re.IGNORECASE)
    if match:
        number, suffix = match.groups()
        return {
            "value": int(number),
            "suffix": suffix.lower(),
        }
    raise ValueError("Invalid ordinal")


def _parse_unicode_fraction(matched):
    """Parse Unicode fraction characters like ¼, ½, ¾, ⅓, etc."""
    fraction_map = {
        "¼": ("1/4", Decimal("0.25")),
        "½": ("1/2", Decimal("0.5")),
        "¾": ("3/4", Decimal("0.75")),
        "⅐": ("1/7", Decimal("1") / Decimal("7")),
        "⅑": ("1/9", Decimal("1") / Decimal("9")),
        "⅒": ("1/10", Decimal("0.1")),
        "⅓": ("1/3", Decimal("1") / Decimal("3")),
        "⅔": ("2/3", Decimal("2") / Decimal("3")),
        "⅕": ("1/5", Decimal("0.2")),
        "⅖": ("2/5", Decimal("0.4")),
        "⅗": ("3/5", Decimal("0.6")),
        "⅘": ("4/5", Decimal("0.8")),
        "⅙": ("1/6", Decimal("1") / Decimal("6")),
        "⅚": ("5/6", Decimal("5") / Decimal("6")),
        "⅛": ("1/8", Decimal("0.125")),
        "⅜": ("3/8", Decimal("0.375")),
        "⅝": ("5/8", Decimal("0.625")),
        "⅞": ("7/8", Decimal("0.875")),
    }

    if len(matched) == 1 and matched in fraction_map:
        notation, value = fraction_map[matched]
        return {
            "value": value,
            "notation": notation,
            "char": matched,
            "type": "fraction",
        }

    # Multiple fraction chars
    total = Decimal("0")
    notations = []
    for char in matched:
        if char in fraction_map:
            notation, value = fraction_map[char]
            total += value
            notations.append(notation)
    return {
        "value": total,
        "notation": " + ".join(notations),
        "chars": matched,
        "type": "fraction",
    }


def _parse_markdown_link(matched):
    """Parse a markdown ``[label](url)`` span.

    Splits on the first ``](`` boundary (the only legal one — neither the
    label nor the URL may contain that two-character sequence under the
    regex used to match this span).
    """
    boundary = matched.index("](")
    label = matched[1:boundary]
    url = matched[boundary + 2 : -1]
    value = {"text": label, "url": url, "matched": matched}
    # Persist any emoji found in the label INSIDE the link's value: the
    # detector's overlap rule (longest span wins) discards the nested
    # dp_emoji candidate, so scan the label with the same EMOJI_CHAR_PATTERN
    # and reuse _parse_emoji for the per-char breakdown (identical shape to
    # a standalone dp_emoji's ``emojis`` list). Added only when non-empty so
    # links without emoji keep their exact ``{text, url, matched}`` shape.
    emojis = [
        info
        for m in EMOJI_CHAR_PATTERN.finditer(label)
        for info in _parse_emoji(m.group())["emojis"]
    ]
    if emojis:
        value["emojis"] = emojis
    return value


def _parse_emoji(matched):
    """Parse emoji characters."""
    emojis = list(matched)
    emoji_info = []
    for emoji in emojis:
        emoji_info.append(
            {
                "char": emoji,
                "codepoint": f"U+{ord(emoji):04X}",
            }
        )
    return {
        "emojis": emoji_info,
        "count": len(emojis),
        "text": matched,
    }
