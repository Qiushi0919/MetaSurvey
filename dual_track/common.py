"""Closed metadata, exact Decimal math and immutable local artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import re
from functools import wraps
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ('603993.SH', '600312.SH', '603228.SH')
HORIZONS = (1, 5, 10, 20, 40)
ORIGINAL_HASH = '7718b46d2d3f281fe574215ce347caedca8b2355033551774d6febc181067072'
# This new Owner-text artifact was actually persisted before the first reveal.
# Pin its exact bytes; a changed receipt cannot register a replacement v1.
FORWARD_V1_REF = {'path':'/Users/qiushi/投资研究/.p1b-archives/dual-track-20261007/forward-freeze/ForwardPrediction-v1-OWNER_TEXT_IMPORT.json',
                  'bytes':4146,'sha256':'sha256:954569db8402e2e50e66841c1a449523c72f20ff1ce364d6183c4d3c7a018039'}
BOUNDARIES = {'research_only': True, 'non_tradeable': True, 'no_order': True,
              'no_broker': True, 'no_money': True, 'productionGate': False,
              'historical_visibility_proven': False, 'actual_authority': False}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def closed(obj, fields):
    require(type(obj) is dict and set(obj) == set(fields), 'DT_CLOSED_SHAPE')


def canonical(obj):
    # Decimal lexemes are strings. JSON floats never enter our contracts.
    def walk(v):
        require(type(v) in (dict, list, str, int, bool, type(None)), 'DT_JSON_TYPE')
        if type(v) is dict:
            require(all(type(k) is str for k in v), 'DT_JSON_KEY')
            for x in v.values(): walk(x)
        elif type(v) is list:
            for x in v: walk(x)
    walk(obj)
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def ref(path):
    path = Path(path)
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(raw), 'sha256': sha(raw)}


def reopen(reference):
    closed(reference, ('path', 'bytes', 'sha256'))
    p = Path(reference['path'])
    require(p.is_absolute() and not p.is_symlink() and p.is_file(), 'DT_REFERENCE_PATH')
    raw = p.read_bytes()
    require(len(raw) == reference['bytes'] and sha(raw) == reference['sha256'], 'DT_REFERENCE_CHANGED')
    return raw


def write_new(path, obj):
    """Exclusive create, flush and fsync; never overwrite a frozen file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = canonical(obj)
    with p.open('xb') as stream:
        os.chmod(p, 0o600)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(p, 0o400)
    fd = os.open(p.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return ref(p)


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def instant(value):
    require(type(value) is str and (value.endswith('Z') or re.search(r'[+-]\d\d:\d\d$', value)), 'DT_CLOCK_OFFSET')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'DT_CLOCK_OFFSET')
    return result


def day(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), 'DT_DATE')
    require(datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d') == value, 'DT_DATE')
    return value


def decimal(value):
    require(type(value) is str and re.fullmatch(r'-?(?:0|[1-9]\d*)(?:\.\d+)?', value), 'DT_DECIMAL_STRING')
    require(len(value) <= 110, 'DT_DECIMAL_BOUND')
    result = Decimal(value)
    require(result.is_finite() and abs(result) < Decimal('1e30'), 'DT_DECIMAL_BOUND')
    return result


def text(value):
    require(value.is_finite(), 'DT_FINITE')
    return format(value, 'f')


def ratio(a, b):
    with localcontext() as ctx:
        ctx.prec = 80
        return a / b - Decimal(1)


def precision80(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with localcontext() as ctx:
            ctx.prec = 80
            return function(*args, **kwargs)
    return wrapped
