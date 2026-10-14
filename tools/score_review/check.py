"""Isolated engineering CI; emits unique case inventory and machine-readable results."""
from pathlib import Path
import argparse, json, os, re, socket, subprocess, sys, unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
def main():
 p=argparse.ArgumentParser();p.add_argument('suite',choices=['scoring','workbench']);p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 summary={'suite':a.suite,'commit':os.getenv('GITHUB_SHA') or subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'run_url':f"https://github.com/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}" if os.getenv('GITHUB_RUN_ID') else None,'scope':'SYNTHETIC_ENGINEERING_ONLY','platform':sys.platform}
 if a.suite=='scoring':
  files=sorted(str(x.relative_to(ROOT)) for x in ROOT.glob('experiments/sector_stock_v*/tests/*.test.mjs'))
  r=subprocess.run([os.getenv('NODE','node'),'--test','--test-reporter=./tools/score_review/reporter.mjs',*files],cwd=ROOT,capture_output=True,text=True);log=r.stdout+r.stderr;(out/'tests.txt').write_text(log)
  events=[json.loads(line) for line in r.stdout.splitlines() if line.startswith('{')];cases=[e['data'] for e in events if e['type'] in ('test:pass','test:fail') and e['data'].get('details',{}).get('type')!='suite']
  ids=[str(Path(x['file']).relative_to(ROOT))+':registered-case-'+str(x['testNumber'])+':'+x['name'] for x in cases];summary.update(unique_cases=len(set(ids)),executions=len(cases),case_ids=ids,passed=r.returncode==0 and bool(cases) and len(ids)==len(set(ids)),identity_basis='file + Node registered testNumber + name; parameterized cases with equal labels remain distinct')

 else:
  original=socket.socket.connect
  def local_only(sock,address):
   if not isinstance(address,tuple) or address[0]!='127.0.0.1': raise AssertionError('ONLY_TEMPORARY_LOOPBACK_TEST_SERVICE_ALLOWED')
   return original(sock,address)
  socket.socket.connect=local_only
  def audit(event,args):
   if event=='open' and isinstance(args[0],(str,bytes)) and any(x in str(args[0]) for x in ('.p1b-archives','.p1b-owner-signing','.p1b-reviewer-signing','/Keychains/')): raise AssertionError('PRIVATE_ARCHIVE_ACCESS_FORBIDDEN_IN_CI')
  sys.addaudithook(audit)
  suite=unittest.defaultTestLoader.discover(str(ROOT/'workbench/tests'))
  def flatten(s):
   for t in s:
    if isinstance(t,unittest.TestSuite): yield from flatten(t)
    else: yield t.id()
  ids=list(flatten(suite))
  with (out/'tests.txt').open('w') as stream:r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
  summary.update(unique_cases=len(set(ids)),executions=r.testsRun,case_ids=ids,failures=len(r.failures),errors=len(r.errors),skips=len(r.skipped),passed=r.wasSuccessful() and len(ids)==len(set(ids))==r.testsRun,network_scope='TEMPORARY_LOOPBACK_ONLY',private_archive_access='DENIED_BY_AUDIT_HOOK')
 (out/'result.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!="case_ids"}));return 0 if summary['passed'] else 1
if __name__=='__main__':sys.exit(main())
