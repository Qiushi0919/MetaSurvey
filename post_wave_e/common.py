"""Strict pure helpers. Evidence shape and a hash confer no admission."""
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import hashlib, json, re
from overnight.analysis.inputs import instant_ns

SYMBOLS = ('603993.SH', '600312.SH', '603228.SH')
VERSION = '1.0.0'
UNSET = 'UNSET_REQUIRED'
def require(ok, reason):
    if not ok: raise ValueError(reason)
def canonical(x):
    def visit(v):
        require(type(v) in (dict,list,str,int,bool,type(None)), 'PREP_NON_JSON_OR_FLOAT')
        if type(v) is dict:
            require(all(type(k) is str for k in v), 'PREP_KEY_TYPE')
            for z in v.values():visit(z)
        elif type(v) is list:
            for z in v:visit(z)
    visit(x)
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def digest(x):return sha(canonical(x))
def seal(x):return dict(x,content_hash=digest(x))
def keys(x,required,optional=()):
    require(type(x) is dict and set(required)<=set(x)<=set(required)|set(optional),'PREP_SHAPE_INVALID')
    canonical(x)
def hash_value(x):
    require(type(x) is str and re.fullmatch(r'sha256:[0-9a-f]{64}',x),'PREP_HASH_INVALID');return x
def timestamp(x):
    require(type(x) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)',x),'PREP_INSTANT_REQUIRED')
    datetime.fromisoformat(x.replace('Z','+00:00'))
    return instant_ns(x)
def decimal_string(x,nonnegative=True):
    require(type(x) is str and re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?',x),'PREP_DECIMAL_REQUIRED')
    v=Decimal(x);require(v.is_finite() and (not nonnegative or v>=0),'PREP_DECIMAL_RANGE');return v
def checked_file(path,expected=None):
    p=Path(path);require(p.is_absolute() and p.resolve()==p and not p.is_symlink() and p.is_file(),'PREP_PATH_INVALID')
    b=p.read_bytes()
    if expected:require(sha(b)==expected,'PREP_DEPENDENCY_INVALIDATED')
    return b
def blocked(reason='SEPARATE_HUMAN_OWNER_AUTHORIZATION_REQUIRED'):
    raise ValueError(reason)
