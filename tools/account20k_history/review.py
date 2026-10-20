"""Independent stdlib trace reconstruction; reads preserved trials, never runs production engine."""
from tools.account20k_history import run
from tools.account20k_history.independent import audit

def main():
 run.check_code();base,proof=run.source();data=run.read(run.ARCHIVE/'Results.json');lock=run.read(run.ARCHIVE/'CandidateLock.json');reg=run.registration()
 reports=[];selected=set(reg['fixed_candidate_ids']+lock['locked_ids'])
 folders=[]
 for folder in sorted((run.ARCHIVE/'trials').iterdir()):
  x=run.read(folder/'Inputs.json')
  if x['config']['id'] in selected:folders.append((folder,x))
 for folder,x in folders:
  run.guard()
  manifest=run.read(folder/'Manifest.json')
  for name,h in manifest['files'].items():
   if run.sha(folder/name)!=h:raise ValueError('CHANGED_TRIAL')
  case,_=run.derive(base,x['config'],x['window'],x['slippage_bps'],x['at'],x.get('omitted_symbol'))
  result=run.unzipped(folder/'EngineResult.json.gz')
  if run.engine.digest(case)!=x['case_hash']:raise ValueError('CHANGED_INPUT')
  review=audit(case,result,x['config']['parameters']);reports.append(review)
  print(folder.name,review['passed'],len(review['failures']),flush=True)
 out=dict(kind='IndependentAccount20kHistoricalReview',runs=reports,run_count=len(reports),passed=all(r['passed'] for r in reports),assertions=sum(r['arithmetic_assertions'] for r in reports),decisions=sum(r['counts']['decisions'] for r in reports),fills=sum(r['counts']['fills'] for r in reports),unfilled=sum(r['counts']['unfilled'] for r in reports),reconstruction_code_hash=run.sha(run.ROOT/'tools/account20k_history/independent.py'),result_hash=run.sha(run.ARCHIVE/'Results.json'))
 run.write(run.ARCHIVE/'IndependentReview.json',out)
 run.write(run.ROOT/'docs/account20k-history/Independent-Review.json',{**{k:v for k,v in out.items() if k!='runs'},'runs':[dict(run_id=r['run_id'],passed=r['passed'],counts=r['counts'],arithmetic_assertions=r['arithmetic_assertions'],failures=r['failures']) for r in reports]})
 return not out['passed']
if __name__=='__main__':raise SystemExit(main())
