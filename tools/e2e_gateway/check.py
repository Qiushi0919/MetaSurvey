"""Portable E2E regression runner: synthetic fixtures only; no private data/network."""
from pathlib import Path
import json,os,socket,subprocess,sys,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
 def audit(event,args):
  if event=='open' and isinstance(args[0],(str,bytes)) and any(x in str(args[0]) for x in ('.p1b-archives','/Keychains/','.p1b-owner-signing','.p1b-reviewer-signing')):raise AssertionError('PRIVATE_DATA_FORBIDDEN')
  if event=='socket.connect':raise AssertionError('NETWORK_FORBIDDEN')
 sys.addaudithook(audit)
 suite=unittest.TestSuite([unittest.defaultTestLoader.discover(str(ROOT/'experiments/e2e_history_v2/tests'),top_level_dir=str(ROOT)),unittest.defaultTestLoader.discover(str(ROOT/'tools/e2e_gateway/tests'),top_level_dir=str(ROOT))])
 def ids(s):
  for t in s:
   if isinstance(t,unittest.TestSuite):yield from ids(t)
   else:yield t.id()
 cases=list(ids(suite))
 with (out/'tests.txt').open('w') as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
 git='/opt/homebrew/bin/git' if Path('/opt/homebrew/bin/git').exists() else 'git'
 summary={'suite':'E2E_GATEWAY_V3','scope':'SYNTHETIC_ENGINEERING_NOT_INVESTMENT_VALIDATION','commit':os.getenv('GITHUB_SHA') or subprocess.check_output([git,'rev-parse','HEAD'],text=True).strip(),'platform':sys.platform,'run_url':f"https://github.com/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}" if os.getenv('GITHUB_RUN_ID') else None,'unique_cases':len(set(cases)),'executions':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'passed':r.wasSuccessful() and len(set(cases))==len(cases)==r.testsRun,'case_ids':cases}
 (out/'result.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='case_ids'}));return not summary['passed']
if __name__=='__main__':sys.exit(main())
