"""Offline readiness producer only. Never reads a credential or starts capture."""
import json,re
from .common import *
from .core import NAMES,payloads,frozen_context
def projected():return {k:canonical(v)+b'\n' for k,v in payloads().items()}
def produce(epoch):
    require(type(epoch) is str and re.fullmatch(r'PREPARATION-G[1-9][0-9]*',epoch),'WH_PREPARATION_EPOCH')
    dest=ARCHIVE/'results'/epoch;require(not dest.exists(),'WH_PREPARATION_EPOCH_EXISTS')
    c=frozen_context();a=projected();b=projected();require(a==b and c==frozen_context(),'WH_PREPARATION_NONDETERMINISTIC')
    refs=[]
    for name,raw in sorted(a.items()):
        p=dest/name;write_private(p,raw);refs.append(dict(ref(p),name=name));(ROOT/'docs/wave-h'/name).write_bytes(raw)
    proof={'version':VERSION,'kind':'OFFLINE_READINESS_REPLAY_PROOF','epoch':epoch,'replays':2,'byte_identical':True,
           'metadata_artifacts':len(NAMES),'context_hash':c['context_hash'],'actual_forward_days':0,'productionGate':False,
           'no_credentials_or_actual_requests':True}
    p=dest/'replay-proof.json';write_private(p,canonical(proof));refs.append(dict(ref(p),name=p.name))
    manifest={'epoch':epoch,'artifacts':refs,'context_hash':c['context_hash'],'productionGate':False}
    write_private(dest/'artifact-manifest.json',canonical(manifest));(ROOT/'docs/wave-h/evidence.json').write_bytes(canonical(manifest));return proof
def verify_saved():
    a=projected();m=json.loads(checked_file(ROOT/'docs/wave-h/evidence.json'))
    require(m['context_hash']==frozen_context()['context_hash'] and set(r['name'] for r in m['artifacts'])==set(a)|{'replay-proof.json'},'WH_SAVED_CONTEXT')
    for r in m['artifacts']:
        require(Path(r['path'])==ARCHIVE/'results'/m['epoch']/r['name'],'WH_SAVED_PATH');raw=reopen({k:r[k] for k in ('path','sha256','bytes')})
        if r['name'] in a:require(raw==a[r['name']]==checked_file(ROOT/'docs/wave-h'/r['name']),'WH_SAVED_REPLAY_DRIFT')
    return {'metadata_artifacts':len(NAMES),'byte_identical':True,'actual_forward_days':0,'productionGate':False}
if __name__=='__main__':
    import sys
    require(len(sys.argv)==2,'WH_EXPLICIT_OFFLINE_EPOCH_REQUIRED');print(json.dumps(produce(sys.argv[1])))
