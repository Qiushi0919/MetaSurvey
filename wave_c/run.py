"""One-shot private report delivery and read-only deterministic persisted replay."""
import json,os
from .core import ROOT,ARCHIVE,canonical,sha,require,load_real_inputs,assert_registered
from .research import assess_all
from .report import make_reports,render

DEST=ARCHIVE/'results'/'REPORTS-G3'
def replay():
    inputs=load_real_inputs();assessments=assess_all(inputs);reports=make_reports(assessments)
    return inputs,assessments,reports

def projected():
    xs,ys,zs=replay();out={}
    for i,symbol in enumerate(x['symbol'] for x in xs):
        for kind,v in [('input',xs[i]),('assessment',ys[i]),('report',zs[i])]:out[symbol+'.'+kind+'.json']=canonical(v)+b'\n'
        out[symbol+'.report.md']=render(zs[i]).encode()
    for value in xs+ys+zs:assert_registered(value)
    return out

def private_write(path,raw):
    os.umask(0o077);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    require(path.parent.resolve()==path.parent and not path.parent.is_symlink(),'WAVE_C_OUTPUT_PATH_INVALID')
    with path.open('xb') as f:f.write(raw)
    require(path.stat().st_mode&0o777==0o600,'WAVE_C_OUTPUT_PERMISSIONS_INVALID')

def produce():
    first=projected();second=projected();require(first==second,'WAVE_C_REPLAY_CHANGED')
    refs=[]
    for name,raw in first.items():
        path=DEST/name;private_write(path,raw);refs.append({'name':name,'path':str(path),'sha256':sha(raw),'bytes':len(raw)})
    proof={'version':'1.0.0','report_count':3,'objects':9,'human_reports':3,'replays':2,'equal':True,'source_admission':'UNVERIFIED_GATEWAY','formal_source_admission':'BLOCKED','historical_visibility_proven':False,'productionGate':False,'model_calls':0,'broker_calls':0,'real_cards':0,'execution_writes':0}
    raw=canonical(proof)+b'\n';path=DEST/'replay-proof.json';private_write(path,raw);refs.append({'name':path.name,'path':str(path),'sha256':sha(raw),'bytes':len(raw)})
    evidence={'version':'1.0.0','artifacts':refs,'formal_source_admission':'BLOCKED','productionGate':False}
    private_write(DEST/'artifact-manifest.json',canonical(evidence)+b'\n')
    (ROOT/'docs/wave-c/evidence.json').write_bytes(canonical(evidence)+b'\n')
    print(json.dumps(proof))

def verify_saved():
    evidence=json.loads((ROOT/'docs/wave-c/evidence.json').read_bytes());actual=projected();verified=0
    for r in evidence['artifacts']:
        from pathlib import Path
        p=Path(r['path']);require(p.is_relative_to(DEST) and p.resolve()==p and not p.is_symlink() and p.stat().st_mode&0o777==0o600,'WAVE_C_SAVED_PATH_INVALID')
        raw=p.read_bytes();require(len(raw)==r['bytes'] and sha(raw)==r['sha256'],'WAVE_C_SAVED_BYTES_CHANGED')
        if r['name'] in actual:require(raw==actual[r['name']],'WAVE_C_SAVED_REPLAY_INVALIDATED');verified+=1
    require(verified==12 and len(evidence['artifacts'])==13,'WAVE_C_SAVED_INVENTORY_INVALID')
    return {'report_count':3,'replayed_artifacts':verified,'deterministic':True,'formal_source_admission':'BLOCKED','productionGate':False}

if __name__=='__main__':produce()
