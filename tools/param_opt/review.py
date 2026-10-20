"""Read-only independent reconstruction of frozen baseline and locked trials."""
import json
from tools.param_opt import run
from tools.param_opt.independent import audit

def main():
 run.check_code();base,proof=run.source();reg=run.registration();lock=run.read(run.ARCHIVE/'CandidateLock.json');reports=[]
 for cid in [reg['baseline_id']]+lock['locked_ids']:
  for win in ('development','selection','check'):
   for bp in ('10','30'):
    folder=run.ARCHIVE/'trials'/f'{cid}-{win}-S{bp}';manifest=run.read(folder/'Manifest.json')
    for name,h in manifest['files'].items():
     if run.sha(folder/name)!=h:raise ValueError('CHANGED_TRIAL')
    x=run.read(folder/'Inputs.json');case,_=run.derive(base,x['config'],x['window'],x['slippage_bps'],x['at'])
    result=run.unzipped(folder/'EngineResult.json.gz')
    if run.engine.digest(case)!=x['case_hash']:raise ValueError('CHANGED_INPUT')
    reviewed=audit(case,result,x['config']['parameters']);reports.append(dict(run_id=case['run_id'],passed=reviewed['passed'],failures=reviewed['failures']))
 out={'independent_reconstruction':True,'runs':reports,'passed':all(x['passed'] for x in reports)};print(json.dumps(out,indent=2));return not out['passed']
if __name__=='__main__':raise SystemExit(main())
