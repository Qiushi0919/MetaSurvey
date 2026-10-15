"""Private, append-only experiment runs. Capture is always an explicit command."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal as D
import argparse, json, re
from tools.long_forward import builder
from experiments.long_forward_v1 import engine
ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT.parent/'.p1b-archives/long-forward-20261015'
CODE_PATHS=(
 'tools/long_forward/history_raw_input.py','tools/long_forward/history_v2.py',
 'experiments/long_forward_v1/history-raw-input-policy.json','experiments/long_forward_v1/history-raw-protocol.json',
 'tools/long_forward/independent.py','tools/long_forward/verify_forward.py','tools/long_forward/builder.py','tools/long_forward/capture.py','tools/long_forward/forward.py',
 'tools/long_forward/run.py','tools/long_forward/reporting.py','tools/long_forward/runtime.py','tools/long_forward/benchmarks.py',
 'experiments/long_forward_v1/engine.py','experiments/long_forward_v1/protocol.json',
 'tools/e2e_gateway/builder.py','tools/e2e_gateway/capture.py','experiments/e2e_gateway_v3/input-policy.json',
 'experiments/e2e_history_v2/engine.py','experiments/e2e_pilot_v1/execution.py','experiments/e2e_pilot_v1/method.json',
 'tools/v3_review/performance.py','tools/v3_review/benchmarks.py',
 'docs/long-forward/Authorization.md','docs/long-forward/Source-Policy.json',
 'backtest_5y/interface.py','wave_f/common.py','post_wave_e/common.py','overnight/analysis/inputs.py','config/provider/tushare-monthly-gateway.json','backtest_5y/gateway.py','backtest_5y/economics.py','wave_f/backtest.py',
 'tushare-real-admission/probe.py','tushare-admission/probe.py')
NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}')
def stamp():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(p.read_text())
def sha(p):return builder.old.rawhash(p)
def pins():return {n:sha(ROOT/n) for n in CODE_PATHS}
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
 p.chmod(0o600)
def check_freeze():
 f=read(ROOT/'docs/long-forward/Code-Freeze.json')
 if f['code_pins']!=pins():raise ValueError('FROZEN_RUNTIME_CODE_CHANGED')
 return f

def seal(folder):
 write(folder/'Bundle.json',dict(kind='LongForwardBundle',version='1.0.0',created_at=stamp(),
       code_pins=pins(),protocol_ref=sha(builder.PROTOCOL),files={p.name:sha(p) for p in sorted(folder.iterdir()) if p.is_file()}))

def yearly(case,result):
 initial=10000000;out=[]
 for year in sorted({r['session'][:4] for r in result.get('daily',[])}):
  rows=[r for r in result['daily'] if r['session'].startswith(year)];peak=initial;dd=D(0)
  for r in rows:peak=max(peak,r['nav_cents']);dd=max(dd,D(peak-r['nav_cents'])/peak)
  fills=[f for f in result['fills'] if f['session'].startswith(year)]
  out.append(dict(status='PARTIAL_INVALID' if result['status']=='ENGINE_FAILED' else 'COMPLETED',year=year,first_session=rows[0]['session'],last_session=rows[-1]['session'],net_return_fraction=None if result['status']=='ENGINE_FAILED' else str(D(rows[-1]['nav_cents']-initial)/initial),max_drawdown_fraction=None if result['status']=='ENGINE_FAILED' else str(dd),filled_orders=len(fills),fees_cents=sum(f['fees']['total_fee_cents'] for f in fills)))
  initial=rows[-1]['nav_cents']
 return out

def execute(capture_dir,run_id):
 check_freeze()
 if not NAME.fullmatch(run_id):raise ValueError('RUN_ID')
 capture_dir=Path(capture_dir)
 if capture_dir.parent!=ARCHIVE or capture_dir.resolve()!=capture_dir:raise ValueError('CAPTURE_SCOPE')
 folder=ARCHIVE/'runs'/run_id;folder.mkdir(parents=True,exist_ok=False)
 at=stamp();report,case=builder.build_case(capture_dir,run_id,at)
 write(folder/'BuildReport.json',report);result=None
 if case is not None:
  write(folder/'Case.json',case)
  result=engine.run_diagnostic(case,lambda c:builder.verify_provenance(c,capture_dir),builder.protocol())
  write(folder/'EngineResult.json',result)
  if result['engine_called']:
   from tools.v3_review.performance import derive_performance
   from tools.long_forward.benchmarks import build_benchmarks
   try:
    performance=derive_performance(case,result);write(folder/'Performance.json',performance)
    write(folder/'Yearly.json',yearly(case,result))
    from tools.long_forward.independent import audit
    write(folder/'Arithmetic.json',audit(folder))
    write(folder/'Controls.json',build_benchmarks(case,builder.protocol()))
   except (ValueError,KeyError,TypeError,ArithmeticError) as exc:write(folder/'AnalysisError.json',dict(error_type=type(exc).__name__,detail=str(exc)))
 run=dict(kind='LongForwardHistoricalRun',version='1.0.0',run_id=run_id,recorded_at=at,capture_dir=str(capture_dir),status=result['status'] if result else 'SOURCE_OR_INPUT_BLOCKED',engine_called=bool(result and result['engine_called']),window=builder.protocol()['target_window'],formal_pit=False,untouched_oos=False,cost_label='SIMULATED_COSTS')
 write(folder/'Run.json',run);seal(folder);return folder,run

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--capture-dir',required=True);p.add_argument('--run-id',required=True);a=p.parse_args();f,r=execute(a.capture_dir,a.run_id);print(json.dumps({'directory':str(f),'status':r['status'],'engine_called':r['engine_called']}))
