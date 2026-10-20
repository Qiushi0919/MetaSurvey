"""Synthetic, fully mocked EOD operational-accounting checks; no real task or data I/O."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from copy import deepcopy
import json
from tools.forward_c20k import runtime

def check(times):
    day='2026-10-21';a=dict(cash_cents=2000000,orders={},positions={},fills=[],settlements=[],effective_observation_days=0,nav_cents=2000000,observations={day:dict(plan_hash='sha256:SYNTHETIC_PLAN',cycle_times=[day+'T'+t+':00+08:00' for t in times],errors=[],symbols=['TEST'])})
    receipt=dict(state='BLOCKED',reason='SYNTHETIC_NEXT_PLAN_BLOCKED',close_reconciled=True)
    with patch.object(runtime,'prepare',return_value=receipt),patch.object(runtime,'config',return_value={'members':{'TEST':'S'}}),patch.object(runtime,'save'),patch.object(runtime,'heartbeat'),patch.object(runtime,'checkpoint',side_effect=lambda value,event:value):
        r=runtime.eod(a,day,{})
    return r['settlements'][0]['status'],r['effective_observation_days']

def review():
    complete=[]
    for start,end in [('09:35','11:25'),('13:00','14:45')]:
        dt=datetime.fromisoformat('2026-10-21T'+start)
        while dt.strftime('%H:%M')<=end:complete.append(dt.strftime('%H:%M'));dt+=timedelta(minutes=5)
    cases=[('two_points_are_not_full_observation',['09:35','14:45'],('BLOCKED_OBSERVATION_GAP',0)),('complete_observation_settles_despite_next_plan_failure',complete,('SETTLED',1)),('missing_midday_morning_tail',[x for x in complete if not ('10:55'<=x<='11:25')],('BLOCKED_OBSERVATION_GAP',0)),('missing_afternoon_open',[x for x in complete if not ('13:00'<=x<='13:35')],('BLOCKED_OBSERVATION_GAP',0))]
    checks=[]
    for name,times,expected in cases:
        actual=check(times);checks.append(dict(name=name,actual=actual,expected=expected,passed=actual==expected))
    return dict(kind='IndependentObservationCoverageReview',synthetic=True,at=datetime.now(timezone.utc).isoformat(),passed=all(x['passed'] for x in checks),checks=checks,count=len(checks))
if __name__=='__main__':
    import sys
    r=review();p=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
    print(dict(passed=r['passed'],count=r['count'],failed=[x['name'] for x in r['checks'] if not x['passed']]))
