from wave_g.common import (require,canonical,sha,digest,seal,keys,hash_value,timestamp,decimal_string,checked_file,blocked,SYMBOLS,UNSET,BASELINE_ROOT)
from pathlib import Path
import json,os
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path('/Users/qiushi/投资研究/.p1b-archives/wave-h-20261007')
VERSION='1.0.0'
FIXED=('config/wave-h/source-exception.v1.json','config/wave-h/authority.pending.json',
       'config/wave-h/snapshot-a-reference.json','docs/wave-h/Interface-Freeze.md',
       'docs/wave-h/baseline-pins.json','docs/wave-h/Contracts-v1.json',
       'docs/wave-h/One-Shot-Activation-Runbook.md','docs/authorizations/P1B-WAVE-H-20261007.md',
       'docs/adr/ADR-034-actual-capture-capabilities-and-forward.md')
def code_manifest():
    paths=sorted([p for p in (ROOT/'wave_h').rglob('*') if p.is_file() and '__pycache__' not in str(p)]+[ROOT/p for p in FIXED if (ROOT/p).is_file()])
    return [{'path':str(p.relative_to(ROOT)),'sha256':sha(checked_file(p)),'bytes':len(checked_file(p))} for p in paths]
def code_hash():return digest(code_manifest())
def locate(path):
    p=Path(path);return ROOT/p.relative_to(BASELINE_ROOT) if p.is_relative_to(BASELINE_ROOT) else p
def ref(path):
    p=Path(path);b=checked_file(p)
    return {'path':str(BASELINE_ROOT/p.relative_to(ROOT) if p.is_relative_to(ROOT) else p),'sha256':sha(b),'bytes':len(b)}
def reopen(r,private=False):
    keys(r,('path','sha256','bytes'));p=locate(r['path'])
    require(p.is_relative_to(ROOT) or p.is_relative_to(ARCHIVE.parent),'WH_REFERENCE_ROOT')
    require(type(r['bytes']) is int and r['bytes']>=0,'WH_REFERENCE_BYTES')
    if private:require(p.is_relative_to(ARCHIVE.parent) and p.is_file() and p.stat().st_mode&0o777==0o600,'WH_PRIVATE_ORIGINAL_REQUIRED')
    b=checked_file(p,r['sha256']);require(len(b)==r['bytes'],'WH_REFERENCE_BYTES_CHANGED');return b
def write_private(path,raw):
    p=Path(path);require(p.is_relative_to(ARCHIVE) and p.resolve()==p and not p.exists(),'WH_EXCLUSIVE_ARCHIVE')
    p.parent.mkdir(mode=0o700,parents=True,exist_ok=True);require(p.parent.stat().st_mode&0o777==0o700,'WH_PRIVATE_DIRECTORY')
    with os.fdopen(os.open(p,os.O_EXCL|os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)
def metadata(kind,body):
    return seal({'version':VERSION,'kind':kind,'body':body,'namespace':'LOCAL_ONLY_NON_TRADEABLE:CORE_40',
        'source_admission':'BLOCKED','historical_visibility_proven':False,'productionGate':False,
        'native_signal_order_broker':False,'live_money_authority':False,'actual_forward_days':0})
def policy():
    p=json.loads(checked_file(ROOT/'config/wave-h/source-exception.v1.json'))
    require(p['version']=='1.0.0' and p['provider_license_transport_verified'] is False and p['productionGate'] is False,'WH_POLICY_PROMOTION')
    return p
def bindings():
    return {'policy_hash':digest(policy()),'strategy_hash':sha(checked_file(ROOT/'docs/wave-f/Frozen-StrategySpec-v1.json')),
        'baseline_hash':sha(checked_file(ROOT/'docs/wave-h/baseline-pins.json')),'code_hash':code_hash()}
