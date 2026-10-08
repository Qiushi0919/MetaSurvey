"""Seven preparation summaries, exclusive private epochs, offline saved validation."""
import os,re
from .common import *
from .core import payloads,frozen_context,NAMES

def private_write(path,raw):
    p=Path(path);require(p.is_relative_to(ARCHIVE) and p.resolve()==p and not p.exists(),'WG_EXCLUSIVE_PATH')
    p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)

def projected():return {n:canonical(v)+b'\n' for n,v in payloads().items()}

def produce(epoch):
    require(type(epoch) is str and re.fullmatch(r'PREPARATION-G[1-9][0-9]*',epoch),'WG_EPOCH')
    dest=ARCHIVE/'results'/epoch;require(not dest.exists(),'WG_EPOCH_EXISTS')
    c=frozen_context();a=projected();b=projected()
    require(a==b and c==frozen_context(),'WG_NONDETERMINISTIC_OR_SOURCE_DRIFT')
    refs=[]
    for name,raw in sorted(a.items()):
        p=dest/name;private_write(p,raw);refs.append(dict(reference(p),name=name))
        (ROOT/'docs/wave-g'/name).write_bytes(raw)
    proof={'version':VERSION,'epoch':epoch,'replays':2,'byte_identical':True,'metadata_artifacts':7,
           'context_hash':c['context_hash'],'diagnostic_replays_already_frozen':2,
           'new_diagnostic_results_produced_by_root':0,'actual_forward_days':0,'productionGate':False}
    p=dest/'replay-proof.json';private_write(p,canonical(proof)+b'\n');refs.append(dict(reference(p),name=p.name))
    manifest={'epoch':epoch,'artifacts':refs,'context_hash':c['context_hash'],'productionGate':False}
    private_write(dest/'artifact-manifest.json',canonical(manifest)+b'\n')
    (ROOT/'docs/wave-g/evidence.json').write_bytes(canonical(manifest)+b'\n');return proof

def verify_saved():
    a=projected();e=json.loads(checked_file(ROOT/'docs/wave-g/evidence.json'))
    require(e['context_hash']==frozen_context()['context_hash'] and re.fullmatch(r'PREPARATION-G[1-9][0-9]*',e['epoch']) and
            set(r['name'] for r in e['artifacts'])==set(a)|{'replay-proof.json'},'WG_SAVED_CONTEXT')
    for r in e['artifacts']:
        require(Path(r['path'])==ARCHIVE/'results'/e['epoch']/r['name'],'WG_SAVED_PATH')
        raw=checked_reference({k:r[k] for k in ('path','sha256','bytes')})
        if r['name'] in a:require(raw==a[r['name']] and raw==checked_file(ROOT/'docs/wave-g'/r['name']),'WG_SAVED_REPLAY_DRIFT')
    return {'metadata_artifacts':7,'byte_identical':True,'actual_forward_days':0,'productionGate':False}

if __name__=='__main__':
    import sys
    require(len(sys.argv)==2,'WG_EXPLICIT_EPOCH_REQUIRED');print(json.dumps(produce(sys.argv[1])))
