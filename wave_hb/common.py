import json,os,hashlib
from pathlib import Path
from wave_h.common import canonical,digest,seal,checked_file,reopen,ref,require,hash_value,SYMBOLS,UNSET

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path('/Users/qiushi/投资研究/.p1b-archives/wave-hb-20261007')
FIXED=('docs/authorizations/P1B-H-B-20261007.md','docs/wave-hb/Interface-Freeze.md',
       'docs/wave-hb/baseline-pins.json','docs/wave-hb/Contracts-v1.json',
       'docs/adr/ADR-035-H-B-offline-preflight-and-evidence-cost.md',
       'config/wave-hb/Owner-Trading-Inputs.template.json',
       'config/wave-hb/official-fee-evidence.json','docs/wave-hb/CostModel-v1.json',
       'docs/wave-hb/CostModel-v1.md','docs/wave-hb/Historical-PIT-Blocker-Map.json',
       'docs/wave-hb/Historical-PIT-Blocker-Map.md')
def inventory():
    paths=sorted([p for p in (ROOT/'wave_hb').rglob('*') if p.is_file() and '__pycache__' not in p.parts]+[ROOT/p for p in FIXED])
    return [dict(path=str(p.relative_to(ROOT)),sha256='sha256:'+hashlib.sha256(checked_file(p)).hexdigest(),bytes=p.stat().st_size) for p in paths]
def code_hash():return digest(inventory())
def baseline():
    b=json.loads(checked_file(ROOT/'docs/wave-hb/baseline-pins.json'))
    require(b['baseline_commit']=='331d0cc394cd5808843c4a383dd85cd02508bed8' and len(b['tracked_files'])==860 and b['immutable_count']==857,'HB_BASELINE_INVALID')
    for r in b['tracked_files']:
        if r['path'].removeprefix('/Users/qiushi/投资研究/ashare-trading-v1/') not in b['allowed_navigation_updates']:reopen(r)
    return b
def private(path,value):
    p=Path(path);require(p.is_relative_to(ARCHIVE) and p.resolve()==p and not p.exists(),'HB_EXCLUSIVE_PRIVATE_ARTIFACT')
    p.parent.mkdir(mode=0o700,parents=True,exist_ok=True);require(p.parent.stat().st_mode&0o777==0o700,'HB_PRIVATE_DIRECTORY')
    with os.fdopen(os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(canonical(value)+b'\n')
def metadata(kind,body):
    return seal(dict(version='1.0.0',kind=kind,body=body,namespace='H_B_OFFLINE_PREPARATION',
      is_authority=False,actual_forward_days=0,safe_to_trade=False,productionGate=False,
      historical_visibility_proven=False,native_signal_order_broker=False,cloud_export=False))
