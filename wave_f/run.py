"""Exclusive result epochs, never overwrite earlier failures/results."""
import json, os
from .common import *
from .core import payloads, frozen_context, NAMES

def private_write(path,raw):
    p=Path(path)
    require(p.is_relative_to(ARCHIVE) and p.resolve()==p and not p.exists(), 'WF_EXCLUSIVE_PATH')
    p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),'wb') as f: f.write(raw)

def projected(): return {n:canonical(v)+b'\n' for n,v in payloads().items()}

def produce(epoch):
    require(type(epoch) is str and __import__('re').fullmatch(r'PREPARATION-G[1-9][0-9]*',epoch), 'WF_EPOCH')
    dest=ARCHIVE/'results'/epoch; require(not dest.exists(),'WF_EPOCH_EXISTS')
    before=frozen_context()['context_hash']; a=projected(); b=projected()
    require(a==b and before==frozen_context()['context_hash'],'WF_NONDETERMINISTIC_OR_SOURCE_DRIFT')
    refs=[]
    for name,raw in sorted(a.items()):
        p=dest/name;private_write(p,raw);refs.append({'name':name,'path':str(p),'sha256':sha(raw),'bytes':len(raw)})
        (ROOT/'docs/wave-f'/name).write_bytes(raw)
    proof={'version':VERSION,'epoch':epoch,'replays':2,'byte_identical':True,
           'metadata_artifacts':5,'context_hash':before,'actual_forward_days':0,
           'new_performance_results':0,'productionGate':False}
    p=dest/'replay-proof.json';raw=canonical(proof)+b'\n';private_write(p,raw)
    refs.append({'name':p.name,'path':str(p),'sha256':sha(raw),'bytes':len(raw)})
    manifest={'epoch':epoch,'artifacts':refs,'context_hash':before,'productionGate':False}
    private_write(dest/'artifact-manifest.json',canonical(manifest)+b'\n')
    (ROOT/'docs/wave-f/evidence.json').write_bytes(canonical(manifest)+b'\n')
    return proof

def verify_saved():
    a=projected();e=json.loads(checked_file(ROOT/'docs/wave-f/evidence.json'))
    require(e['context_hash']==frozen_context()['context_hash'] and set(r['name'] for r in e['artifacts'])==set(a)|{'replay-proof.json'},'WF_SAVED_CONTEXT')
    for r in e['artifacts']:
        require(Path(r['path'])==ARCHIVE/'results'/e['epoch']/r['name'],'WF_SAVED_PATH')
        raw=checked_file(r['path'],r['sha256']);require(len(raw)==r['bytes'],'WF_SAVED_SIZE')
        if r['name'] in a: require(raw==a[r['name']] and raw==checked_file(ROOT/'docs/wave-f'/r['name']),'WF_SAVED_REPLAY_DRIFT')
    return {'metadata_artifacts':5,'byte_identical':True,'actual_forward_days':0,'productionGate':False}

if __name__=='__main__':
    import sys
    require(len(sys.argv)==2,'WF_EXPLICIT_EPOCH_REQUIRED')
    print(json.dumps(produce(sys.argv[1])))
