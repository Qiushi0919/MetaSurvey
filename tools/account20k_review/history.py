"""Read-only independent execution audit for existing 20k trial artifacts.
No production engine is invoked. Source/derive rebuild immutable case inputs;
all economic expectations come from standard-library independent reconstruction.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
from tools.account20k_history import run
from tools.account20k_history.independent import audit


def review_all(output, include_all=False):
    base,proof=run.source();reg=run.registration();results=[]
    for folder in sorted((run.ARCHIVE/'trials').iterdir()):
        if not (folder/'Manifest.json').is_file():continue
        i=run.read(folder/'Inputs.json')
        if not include_all and i['config']['id'] not in reg['fixed_candidate_ids']:continue
        for name,expected in run.read(folder/'Manifest.json')['files'].items():
            if run.sha(folder/name)!=expected:raise ValueError('TRIAL_HASH_CHANGED:'+folder.name+'/'+name)
        c,p=run.derive(base,i['config'],i['window'],i['slippage_bps'],i['at'],i.get('omitted_symbol'))
        if run.engine.digest(c)!=i['case_hash']:raise ValueError('CASE_RECONSTRUCTION_HASH')
        if c['initial_cash_cents']!=2000000:raise ValueError('NOT_20K_ACTUAL_CASE')
        original={m['symbol'] for m in base['universe']};expected=original-({i['omitted_symbol']} if i.get('omitted_symbol') else set())
        if {m['symbol'] for m in c['universe']}!=expected:raise ValueError('LEAVE_ONE_OUT_UNIVERSE')
        if {x['symbol'] for x in c['bars']}!=expected:raise ValueError('LEAVE_ONE_OUT_BARS')
        if any(x['symbol'] not in expected for x in c['actions']):raise ValueError('LEAVE_ONE_OUT_ACTIONS')
        for fee in c['fee_schedule']:
            if fee['commission_rate']!='0.00025' or fee['minimum_commission_cents']!=500 or fee['exchange_included'] is not True or fee['other_included'] is not False:raise ValueError('NEW_ACCOUNT_FEE_ASSUMPTION')
        r=run.unzipped(folder/'EngineResult.json.gz');a=audit(c,r,i['config']['parameters'])
        a.update(trial=folder.name,omitted_symbol=i.get('omitted_symbol'),actual_initial_cash_cents=2000000,checked_at=datetime.now(timezone.utc).isoformat(),inputs_hash=run.sha(folder/'Inputs.json'),manifest_hash=run.sha(folder/'Manifest.json'),independent_source_hash=run.sha(Path(__import__('tools.account20k_history.independent',fromlist=['audit']).__file__)))
        results.append(a)
    summary=dict(kind='Independent20kHistoryExecutionReview',checked_at=datetime.now(timezone.utc).isoformat(),passed=bool(results) and all(x['passed'] for x in results),actual_trials=len(results),unique_run_ids=len({x['run_id'] for x in results}),counts={k:sum(x['counts'][k] for x in results) for k in ['decisions','fills','unfilled','daily']},arithmetic_assertions=sum(x['arithmetic_assertions'] for x in results),leave_one_out_trials=sum(bool(x['omitted_symbol']) for x in results),reports=results,failures=sum(len(x['failures']) for x in results),scope='Actual20k initialcash/risklot/cost recomputation; original restricted real inputs; no productionengine calls',limits=['Historical flat20 dividend-tax convention remains simulated; realtime differentiated-tax engine separate','Not originalPIT/OOS or realbrokerfee certification'])
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:json.dump(summary,f,ensure_ascii=False,indent=2);f.write('\n')
    return {k:v for k,v in summary.items() if k!='reports'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--all',action='store_true');a=p.parse_args();print(json.dumps(review_all(a.output,a.all),ensure_ascii=False))
