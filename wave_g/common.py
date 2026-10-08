"""Immutable helpers reused; hashes/JSON never grant actual authority."""
from post_wave_e.common import (SYMBOLS,UNSET,require,canonical,sha,digest,seal,keys,hash_value,timestamp,decimal_string,checked_file,blocked)
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path('/Users/qiushi/投资研究/.p1b-archives/wave-g-20261007')
BASELINE_ROOT=Path('/Users/qiushi/投资研究/ashare-trading-v1')
VERSION='1.0.0'
NAMESPACE='RETROSPECTIVE_DIAGNOSTIC_ONLY:CORE_40'
def protocol():
    r=json.loads(checked_file(ARCHIVE/'start/Diagnostic-Preregistration-G2.json'))
    raw=checked_file(ROOT/'docs/wave-g/Diagnostic-Protocol-v1.1.json',r['protocol_sha256'])
    p=json.loads(raw)
    require(sha(checked_file(ROOT/p['source_strategy_file']))==r['strategy_sha256'],'WG_STRATEGY_INVALIDATED')
    return p

def reference(path):
    raw=checked_file(path)
    p=Path(path)
    identity=BASELINE_ROOT/p.relative_to(ROOT) if p.is_relative_to(ROOT) else p
    return {'path':str(identity),'sha256':sha(raw),'bytes':len(raw)}

def metadata(kind,body):
    canonical(body)
    return seal({'version':VERSION,'kind':kind,'namespace':NAMESPACE,'body':body,
        'trust':'LOCAL_ONLY_NON_TRADEABLE','historical_visibility_proven':False,
        'source_admission':'BLOCKED','actual_forward_days':0,'productionGate':False,
        'live_authority':False,'native_signal_order_broker':False})

def unavailable(*args,**kwargs):blocked('WG_SEPARATE_HUMAN_ACTIVATION_AUTHORIZATION_REQUIRED')

def locate_reference(path):
    """Git reference identity is stable; reads use calling checkout. Private root fixed."""
    p=Path(path)
    return ROOT/p.relative_to(BASELINE_ROOT) if p.is_relative_to(BASELINE_ROOT) else p

def checked_reference(ref):
    raw=checked_file(locate_reference(ref['path']),ref['sha256'])
    require(len(raw)==ref['bytes'],'WG_DIRECT_REFERENCE_SIZE_CHANGED')
    return raw
