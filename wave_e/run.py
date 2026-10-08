"""Exclusive offline diagnostic delivery and deterministic read-only verification."""
import json, os
from pathlib import Path
from .core import ROOT, ARCHIVE, NAMES, canonical, sha, require, objects, private_ref, frozen_context, context_hash
DEST=ARCHIVE/'results/DIAGNOSTIC-G1'
OBJECT_FILES=dict(zip(NAMES,('Backtest-Readiness.json','Diagnostic-Backtest-Result.json','Snapshot-B-Preflight.json','Forward-Paper-Readiness.json')))

def private_write(p,b):
    require(p.is_relative_to(ARCHIVE) and p.resolve()==p and not p.exists(),'WAVE_E_EXCLUSIVE_PATH_INVALID')
    p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with os.fdopen(os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(b)

def projected():
    values,artifacts=objects()
    for v in values:artifacts[OBJECT_FILES[v['contract_name']]]=canonical(v)+b'\n'
    return artifacts

def produce():
    os.umask(0o077);require(not DEST.exists(),'WAVE_E_EPOCH_ALREADY_EXISTS')
    start=context_hash(frozen_context());first=projected();second=projected();require(first==second,'WAVE_E_NONDETERMINISTIC_REPLAY_STOP');require(start==context_hash(frozen_context()),'WAVE_E_PREDECESSOR_OR_SOURCE_MUTATED_STOP')
    refs=[]
    for name,b in sorted(first.items()):
        p=DEST/name;private_write(p,b);refs.append({'name':name,'path':str(p),'sha256':sha(b),'bytes':len(b)})
    proof={'version':'1.0.0','replays':2,'byte_identical':True,'private_artifacts':len(refs),'scenarios':8,'price_treatments':2,'stocks':3,'sessions_each':327,'current_observed_only':True,'historical_visibility_proven':False,'formal_source_admission':'BLOCKED','formal_strategy_evidence':False,'actual_forward_days':0,'productionGate':False,'context_hash_before_after':start}
    p=DEST/'replay-proof.json';b=canonical(proof)+b'\n';private_write(p,b);refs.append({'name':p.name,'path':str(p),'sha256':sha(b),'bytes':len(b)})
    e={'version':'1.0.0','artifacts':refs,'context_hash':start,'productionGate':False};private_write(DEST/'artifact-manifest.json',canonical(e)+b'\n');(ROOT/'docs/wave-e/evidence.json').write_bytes(canonical(e)+b'\n')
    for name in ('Backtest-Readiness.json','Diagnostic-Backtest-Result.json','Snapshot-B-Preflight.json','Forward-Paper-Readiness.json'):(ROOT/'docs/wave-e'/name).write_bytes(first[name])
    print(json.dumps(proof))

def verify_saved():
    actual=projected();e=json.loads((ROOT/'docs/wave-e/evidence.json').read_bytes());require(e['context_hash']==context_hash(frozen_context()),'WAVE_E_SAVED_SOURCE_INVALIDATED')
    require(set(r['name'] for r in e['artifacts'])==set(actual)|{'replay-proof.json'},'WAVE_E_SAVED_INVENTORY_INVALID')
    for r in e['artifacts']:
        require(Path(r['path'])==DEST/r['name'],'WAVE_E_SAVED_PATH_SUBSTITUTED');raw=private_ref(r,DEST)
        if r['name'] in actual:require(raw==actual[r['name']],'WAVE_E_SAVED_REPLAY_CHANGED')
    return {'private_artifacts':len(e['artifacts']),'machine_contracts':4,'scenarios':8,'byte_identical':True,'actual_forward_days':0,'historical_visibility_proven':False,'productionGate':False}
if __name__=='__main__':produce()
