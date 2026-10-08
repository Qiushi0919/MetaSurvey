import json
from .common import ROOT,ARCHIVE,private,canonical,ref,reopen,require,checked_file
from .core import context,payloads,NAMES
def produce(epoch):
    require(type(epoch) is str and epoch in ('FROZEN-G1','FROZEN-G2','FROZEN-G3'),'HB_EPOCH_NOT_BOUNDED')
    out=ARCHIVE/'results'/epoch;require(not out.exists(),'HB_EXCLUSIVE_EPOCH')
    one=payloads();two=payloads()
    require({n:canonical(v) for n,v in one.items()}=={n:canonical(v) for n,v in two.items()},'HB_NONDETERMINISTIC_PROJECTION')
    for n,v in one.items():private(out/n,v)
    proof={'version':'1.0.0','context_hash':context()['context_hash'],'artifacts':len(one),'replays':2,
      'byte_identical':True,'actual_forward_days':0,'actual_enrollment_installed':False,'productionGate':False}
    private(out/'Replay-Proof.json',proof)
    return {'version':'1.0.0','epoch':epoch,'context_hash':context()['context_hash'],
      'artifact_refs':[dict(name=n,**ref(out/n)) for n in NAMES], 'replay_ref':ref(out/'Replay-Proof.json')}
def verify_saved():
    e=json.loads(checked_file(ROOT/'docs/wave-hb/evidence.json'));c=context()
    require(e['context_hash']==c['context_hash'],'HB_SAVED_CONTEXT_DRIFT');expected=payloads()
    require(len(e['artifact_refs'])==6 and {r['name'] for r in e['artifact_refs']}==set(NAMES),'HB_SAVED_ARTIFACTS_INVALID')
    for r in e['artifact_refs']:
        pure={k:r[k] for k in ('path','sha256','bytes')}
        require(reopen(pure)==canonical(expected[r['name']])+b'\n','HB_SAVED_ARTIFACT_CHANGED')
    proof=json.loads(reopen(e['replay_ref']));require(proof['byte_identical'] is True and proof['actual_forward_days']==0 and proof['context_hash']==c['context_hash'],'HB_REPLAY_PROOF_INVALID')
    return {'metadata':6,'context_hash':c['context_hash'],'code_hash':c['code_hash'],'actual_days':0,'productionGate':False}
