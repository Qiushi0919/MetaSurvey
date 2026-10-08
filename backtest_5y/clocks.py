"""Strict source clocks, represented as integer UTC nanoseconds.

Only second precision through nine fractional digits is supported. Unsupported
or unknown offsets fail closed; no floating point or datetime truncation occurs.
This parser verifies syntax, not historical visibility or source authority.
"""
from datetime import date
import re

_EXACT = re.compile(
    r'([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})'
    r'(?:\.([0-9]{1,9}))?(Z|[+-][0-9]{2}:[0-9]{2})')
_EPOCH = date(1970, 1, 1).toordinal()


def source_day(value):
    """Accept only actual calendar dates in the two documented source forms."""
    if type(value) is not str:
        raise ValueError('EVENT_DATE_REQUIRED')
    if re.fullmatch('[0-9]{8}', value):
        value = value[:4] + '-' + value[4:6] + '-' + value[6:]
    if not re.fullmatch('[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError('EVENT_DATE_REQUIRED')
    return date.fromisoformat(value).isoformat()


def exact_clock(value):
    if type(value) is not str or not (match := _EXACT.fullmatch(value)):
        raise ValueError('EXACT_OFFSET_CLOCK_REQUIRED')
    day, hour, minute, second, fraction, offset = match.groups()
    day = date.fromisoformat(day)
    h, m, s = map(int, (hour, minute, second))
    if h > 23 or m > 59 or s > 59:
        raise ValueError('EXACT_CLOCK_COMPONENT_OUT_OF_RANGE')
    if offset == '-00:00':
        raise ValueError('EXACT_CLOCK_UNKNOWN_OFFSET')
    offset_seconds = 0
    if offset != 'Z':
        oh, om = int(offset[1:3]), int(offset[4:6])
        if oh > 23 or om > 59:
            raise ValueError('EXACT_CLOCK_OFFSET_OUT_OF_RANGE')
        offset_seconds = (oh * 60 + om) * 60 * (1 if offset[0] == '+' else -1)
    seconds = (day.toordinal() - _EPOCH) * 86400 + h * 3600 + m * 60 + s - offset_seconds
    return seconds * 1_000_000_000 + int((fraction or '').ljust(9, '0'))
