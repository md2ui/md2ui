"""The ``DataPointType`` enum, alone.

Its own module so ``detector_scope`` can name the types without importing the
detector that imports it. ``data_point_detector`` re-exports it and remains
its address for every caller.
"""

from enum import Enum


class DataPointType(Enum):
    """Enumeration of supported data point types."""

    DATE = "date"
    DATE_RANGE = "date_range"
    TIME = "time"
    DURATION = "duration"
    QUARTER = "quarter"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    NUMBER = "number"
    QUANTITY = "quantity"
    RATIO = "ratio"
    RATE = "rate"
    SCORE = "score"
    RANKING = "ranking"
    FREQUENCY = "frequency"
    MEASUREMENT = "measurement"
    AGE = "age"
    RANGE = "range"
    IDENTIFIER = "identifier"
    CHANGE = "change"
    STATISTICAL = "statistical"
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    VERSION = "version"
    FILE_SIZE = "file_size"
    DIMENSION = "dimension"
    BLOOD_TYPE = "blood_type"
    ORDINAL = "ordinal"
    EMOJI = "emoji"
    LINK = "link"
    IMAGE = "image"
    DRAWING_ELEMENT = "drawing_element"
