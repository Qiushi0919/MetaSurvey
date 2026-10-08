"""Frozen lossless parsing and scope primitives for the bounded collector."""
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import hashlib, json, re
from overnight.data.dataset import _safe_text
ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT.parent / '.p1b-archives/wave-b-20261006'
SYMBOLS = ('603993.SH', '600312.SH', '603228.SH')
START, END = '20250601', '20261005'
VERSION = '1.0.0-candidate-diagnostic'

def require(ok, reason):
    if not ok: raise ValueError(reason)

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False, default=lambda x: format(x, 'f') if isinstance(x, Decimal) else (_ for _ in ()).throw(ValueError('TYPE_INVALID'))).encode()

def sha(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()

def date_literal(value):
    if type(value) is not str or re.fullmatch(r'\d{8}', value) is None: return False
    try: datetime.strptime(value, '%Y%m%d'); return True
    except ValueError: return False

def clock(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value), 'CLOCK_INVALID')
    try: return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError: raise ValueError('CLOCK_INVALID') from None

def safe_body(value):
    if type(value) is str:
        _safe_text(value)
        require('ashare-trading-v1/tushare-monthly-gateway' not in value and value != 'stock_api', 'SECRET_REFERENCE_FORBIDDEN')
        require(value not in {'ADMITTED','VERIFIED_FOR_REAL_RESEARCH','REAL_NET_EDGE','REAL_SIZING'}, 'BUSINESS_AUTHORITY_FORBIDDEN')
    elif type(value) is dict:
        for k, v in value.items():
            require(type(k) is str, 'KEY_INVALID')
            require(k.lower() not in {'token', 'password', 'keychain_service', 'keychain_account', 'secret_value'}, 'SECRET_FIELD_FORBIDDEN')
            if k in {'provider_identity_verified','license_verified','transport_integrity_verified','historical_visibility_proven','productionGate','broker_capability_verified'}:
                require(v is False, 'BUSINESS_AUTHORITY_FORBIDDEN')
            safe_body(v)
    elif type(value) in (list, tuple):
        for item in value: safe_body(item)
    else: require(value is None or type(value) in (int, bool, Decimal), 'TYPE_INVALID')
