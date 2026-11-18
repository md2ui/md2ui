"""A sign written right before a value belongs to it.

`-€200`, `-$5K`, `-1,234` and `-5°C` are found by patterns that know nothing of a
sign, so without this step the minus stays outside the match and the value reads
positive, or a shorter signed pattern (`-$5`) wins and drops the rest. This step
gives the sign back, once, for every pattern, instead of a sign class in each.

What the sign makes of a value is a decision about meaning, not parsing: a signed
amount or count is a change, a signed temperature is still a level.
"""

from decimal import Decimal

from md2ui.pipeline.data_point_types import DataPointType
from md2ui.pipeline.detector_vocabulary import _MINUS


def _signed_value(dp_type, value, sign):
    """What a sign written right before a value makes of it, or None.

    A signed amount or count is a change, what the ``change up|down`` pins
    colour: ``-€200`` reads as ``-$200`` does, with its own currency. A
    temperature is a level, so it keeps its type and takes the sign. Anything
    else declines, and the sign stays outside the match.
    """
    negative = sign in _MINUS
    direction = "decrease" if negative else "increase"
    if dp_type is DataPointType.CURRENCY and isinstance(value, dict):
        amount = Decimal(value["amount"])
        return DataPointType.CHANGE, {
            "value": -amount if negative else amount,
            "currency": value["currency"],
            "direction": direction,
            "type": "currency",
        }
    if dp_type is DataPointType.NUMBER:
        amount = Decimal(value["value"] if isinstance(value, dict) else value)
        return DataPointType.CHANGE, {
            "value": -amount if negative else amount,
            "direction": direction,
            "type": "bare",
        }
    if (
        dp_type is DataPointType.MEASUREMENT
        and isinstance(value, dict)
        and value.get("measurement_type") == "temperature"
        and "alt_value" not in value
    ):
        return dp_type, {
            **value,
            "value": -value["value"] if negative else value["value"],
        }
    return None


def take_sign(result, text):
    """*result* with the sign written right before it, or None."""
    start = result["start"]
    sign = text[start - 1 : start]
    if not sign or sign not in "+" + _MINUS:
        return None
    if start >= 2 and (text[start - 2].isalnum() or text[start - 2] == "_"):
        return None
    signed = _signed_value(result["type"], result["value"], sign)
    if signed is None:
        return None
    return {
        **result,
        "type": signed[0],
        "value": signed[1],
        "matched": sign + result["matched"],
        "start": start - 1,
    }
