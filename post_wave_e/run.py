"""Exclusive preparation epoch and deterministic offline verification."""
from pathlib import Path
import json,os
from .common import *
from .core import ROOT,ARCHIVE,FILES,objects,frozen_context,context_hash,private_ref
DEST=ARCHIVE/'results/PREPARATION-G3'
def private_write(p,b):
    require(p.is_relative_to(ARCHIVE) and p.resolve()==p and not p.exists(),'PREP_EXCLUSIVE_PATH')
    p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with os.fdopen(os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(b)
def projected():return {FILES[v['contract_name']]:canonical(v)+b'\n' for v in objects()}
def produce():
    require(not DEST.exists(),'PREP_EPOCH_EXISTS');c=context_hash(frozen_context());a=projected();b=projected();require(a==b and c==context_hash(frozen_context()),'PREP_REPLAY_OR_SOURCE_DRIFT')
    refs=[]
    for n,raw in sorted(a.items()):
        p=DEST/n;private_write(p,raw);refs.append({'name':n,'path':str(p),'sha256':sha(raw),'bytes':len(raw)})
        (ROOT/'docs/post-wave-e'/n).write_bytes(raw)
    proof={'version':VERSION,'replays':2,'byte_identical':True,'machine_contracts':8,'actual_forward_days':0,'historical_visibility_proven':False,'productionGate':False,'context_hash':c}
    p=DEST/'replay-proof.json';raw=canonical(proof)+b'\n';private_write(p,raw);refs.append({'name':p.name,'path':str(p),'sha256':sha(raw),'bytes':len(raw)})
    e={'version':VERSION,'artifacts':refs,'context_hash':c,'productionGate':False};private_write(DEST/'artifact-manifest.json',canonical(e)+b'\n');(ROOT/'docs/post-wave-e/evidence.json').write_bytes(canonical(e)+b'\n');return proof
def verify_saved():
    a=projected();e=json.loads(checked_file(ROOT/'docs/post-wave-e/evidence.json'));require(e['context_hash']==context_hash(frozen_context()) and set(r['name'] for r in e['artifacts'])==set(a)|{'replay-proof.json'},'PREP_SAVED_CONTEXT_INVALID')
    for r in e['artifacts']:
        require(Path(r['path'])==DEST/r['name'],'PREP_SAVED_PATH_SUBSTITUTION');raw=private_ref({k:r[k] for k in ('path','sha256','bytes')})
        if r['name'] in a:require(raw==a[r['name']] and raw==checked_file(ROOT/'docs/post-wave-e'/r['name']),'PREP_SAVED_REPLAY_CHANGED')
    return {'machine_contracts':8,'byte_identical':True,'actual_forward_days':0,'productionGate':False}
if __name__=='__main__':print(json.dumps(produce()))
