"""Exclusive private report epoch and deterministic read-only replay."""
import json
from .core import ROOT,ARCHIVE,canonical,sha,require,load_inputs,assess,reports,comparison,assert_registered
from .probe import private_write
from .report import render_report,render_comparison
DEST=ARCHIVE/'results'/'REPORTS-G4'
def replay():
 ins=load_inputs();xs=assess(ins);rs=reports(xs);comp=comparison(rs);return ins,xs,rs,comp

def projected():
 ins,xs,rs,comp=replay();out={}
 for i,symbol in enumerate(x['symbol'] for x in ins):
  for kind,v in [('input',ins[i]),('assessment',xs[i]),('report',rs[i])]:out[symbol+'.'+kind+'.json']=canonical(v)+b'\n'
  out[symbol+'.report.md']=render_report(rs[i]).encode()
 out['ResearchComparison.json']=canonical(comp)+b'\n';out['ResearchComparison.md']=render_comparison(comp).encode()
 return out

def produce():
 first=projected();second=projected();require(first==second,'WAVE_D_REPLAY_CHANGED');refs=[]
 for name,raw in first.items():
  p=DEST/name;private_write(p,raw);refs.append({'name':name,'path':str(p),'sha256':sha(raw),'bytes':len(raw)})
 proof={'version':'1.0.0','objects':10,'human_reports':4,'replays':2,'equal':True,'formal_source_admission':'BLOCKED','historical_visibility_proven':False,'productionGate':False,'real_cards':0,'orders':0,'model_calls':0,'broker_calls':0}
 p=DEST/'replay-proof.json';raw=canonical(proof)+b'\n';private_write(p,raw);refs.append({'name':p.name,'path':str(p),'sha256':sha(raw),'bytes':len(raw)})
 e={'version':'1.0.0','artifacts':refs,'productionGate':False};private_write(DEST/'artifact-manifest.json',canonical(e)+b'\n');(ROOT/'docs/wave-d/evidence.json').write_bytes(canonical(e)+b'\n');print(json.dumps(proof))

def verify_saved():
 actual=projected();e=json.loads((ROOT/'docs/wave-d/evidence.json').read_bytes())
 for r in e['artifacts']:
  from pathlib import Path
  p=Path(r['path']);require(p.is_relative_to(DEST) and p.resolve()==p and not p.is_symlink() and p.stat().st_mode&0o777==0o600,'WAVE_D_SAVED_PATH_INVALID');raw=p.read_bytes();require(sha(raw)==r['sha256'] and len(raw)==r['bytes'],'WAVE_D_SAVED_MUTATED')
  if r['name'] in actual:require(raw==actual[r['name']],'WAVE_D_SAVED_REPLAY_INVALID')
 require(len(actual)==14 and len(e['artifacts'])==15,'WAVE_D_INVENTORY_INVALID');return {'objects':10,'human_reports':4,'deterministic':True,'productionGate':False}
if __name__=='__main__':produce()
