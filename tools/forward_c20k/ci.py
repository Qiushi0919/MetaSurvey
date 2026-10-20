"""Isolated synthetic checks with exact unique-case accounting."""
from pathlib import Path
import json,os,subprocess,sys,unittest
def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
    def forbid(event,args):
        if event=='open' and isinstance(args[0],(str,bytes)) and any(s in str(args[0]) for s in ('.p1b-archives','/Keychains/')):
            raise AssertionError('PRIVATE_ACCESS_FORBIDDEN')
        if event=='socket.connect':raise AssertionError('NETWORK_FORBIDDEN')
    sys.addaudithook(forbid)
    names=['tools.forward_c20k.check','tools.forward_c20k.test_plan_flow','tools.account20k_history.check','tools.account20k_history.extra_check']
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in names)
    def flatten(s):
        for t in s:
            if isinstance(t,unittest.TestSuite):yield from flatten(t)
            else:yield t.id()
    ids=list(flatten(suite))
    with (out/'tests.txt').open('w') as f:result=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
    summary=dict(suite='ACCOUNT20K_REALTIME_AND_HISTORY',scope='SYNTHETIC_ENGINEERING_NOT_INVESTMENT_VALIDATION',
        commit=os.getenv('GITHUB_SHA') or subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        platform=sys.platform,unique_cases=len(set(ids)),executions=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),
        passed=result.wasSuccessful() and len(set(ids))==len(ids)==result.testsRun,case_ids=ids,
        run_url=f"https://github.com/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}" if os.getenv('GITHUB_RUN_ID') else None)
    (out/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='case_ids'}));return not summary['passed']
if __name__=='__main__':sys.exit(main())
