"""Read-only projections with source, file, code and calculation binding."""
from pathlib import Path
import json, subprocess, sys
from decimal import Decimal as D
from tools.long_forward import run, builder
ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT.parent/'.p1b-archives/long-forward-20261015'

def bundle(folder):
 if folder.resolve()!=folder or folder.is_symlink() or folder.parent not in (ARCHIVE/'runs',ARCHIVE/'forward'):raise ValueError('BUNDLE_PATH')
 manifest=run.read(folder/'Bundle.json')
 if manifest['kind']!='LongForwardBundle' or manifest['version']!='1.0.0' or manifest['code_pins']!=run.pins() or manifest['protocol_ref']!=run.sha(builder.PROTOCOL):raise ValueError('BUNDLE_CODE_PROTOCOL')
 if set(manifest['files'])!={p.name for p in folder.iterdir() if p.is_file() and p.name!='Bundle.json'}:raise ValueError('BUNDLE_EXACT_FILES')
 for name,h in manifest['files'].items():
  p=folder/name
  if Path(name).name!=name or p.is_symlink() or not p.is_file() or run.sha(p)!=h:raise ValueError('BUNDLE_FILE_MISMATCH')
 return {n:run.read(folder/n) for n in manifest['files'] if n.endswith('.json')}

def history(folder):
 data=bundle(folder);record=data['Run.json'];report=data['BuildReport.json'];case=data.get('Case.json');result=data.get('EngineResult.json');capture=Path(record['capture_dir'])
 if record.get('kind')!='LongForwardHistoricalRun' or record.get('version')!='1.0.0' or record['run_id']!=folder.name or record['window']!=builder.protocol()['target_window']:raise ValueError('RUN_IDENTITY_WINDOW')
 if record['status']!=(result['status'] if result else 'SOURCE_OR_INPUT_BLOCKED'):raise ValueError('RUN_STATUS')
 if capture.parent!=ARCHIVE or capture.resolve()!=capture:raise ValueError('CAPTURE_SCOPE')
 again,c=builder.build_case(capture,record['run_id'],record['recorded_at'])
 if again!=report or c!=case:raise ValueError('INPUT_REBUILD_MISMATCH')
 if record['engine_called']!=bool(result and result['engine_called']):raise ValueError('ENGINE_STATUS_MISMATCH')
 perf=None
 if result:
  from experiments.long_forward_v1.engine import run_diagnostic
  if run_diagnostic(case,lambda c:builder.verify_provenance(c,capture),builder.protocol())!=result:raise ValueError('ENGINE_REPLAY_MISMATCH')
  if result['input_hash']!=builder.digest(case) or result['content_hash']!=builder.digest({k:v for k,v in result.items() if k!='content_hash'}):raise ValueError('ENGINE_CONTENT_MISMATCH')
  if 'Performance.json' in data:
   from tools.v3_review.performance import derive_performance
   perf=derive_performance(case,result)
   if perf!=data['Performance.json']:raise ValueError('PERFORMANCE_RECALC_MISMATCH')
   if run.yearly(case,result)!=data.get('Yearly.json'):raise ValueError('YEARLY_RECALC_MISMATCH')
  if 'Arithmetic.json' in data:
   from tools.long_forward.independent import audit
   if audit(folder)!=data['Arithmetic.json']:raise ValueError('ARITHMETIC_RECALC_MISMATCH')
  if 'Controls.json' in data:
   from tools.long_forward.benchmarks import build_benchmarks
   if build_benchmarks(case,builder.protocol())!=data['Controls.json']:raise ValueError('CONTROL_RECALC_MISMATCH')
 rows=perf['nav_series'] if perf else []
 exposure=dict(average_exposure_fraction=str(sum(D(r['exposure_fraction']) for r in rows)/len(rows)),maximum_exposure_fraction=str(max(D(r['exposure_fraction']) for r in rows)),exposed_sessions=sum(r['exposure_cents']>0 for r in rows),terminal_cash_cents=rows[-1]['cash_cents']) if rows else None
 overall=dict(perf['summary'],nav_series=rows) if perf and perf['summary'] else None
 return dict(run_id=record['run_id'],status=record['status'],engine_called=record['engine_called'],window=record['window'],overall=overall,yearly=data.get('Yearly.json',[]),controls=data.get('Controls.json',[]),exposure=exposure,errors=report['errors']+(result.get('errors',[]) if result else [])+([data['AnalysisError.json']] if 'AnalysisError.json' in data else []))

def forward(folder):
 if folder.name=='ACTIVE':
  p=run.read(folder/'CURRENT.json');name=p['directory']
  if not run.NAME.fullmatch(name):raise ValueError('FORWARD_POINTER_PATH')
  folder=ARCHIVE/'forward'/name
  if run.sha(folder/'Bundle.json')!=p['bundle_hash']:raise ValueError('FORWARD_POINTER_HASH')
 from tools.long_forward.verify_forward import verify_folder
 data=verify_folder(folder);event=data['Event.json'];state=data.get('State.json');plan=data.get('Plan.json')
 errors=data.get('BuildReport.json',{}).get('errors',[])+event.get('errors',[])
 return dict(strategy_a=dict(status=event['status'],activation=event.get('activation'),plan=plan,settlements=list(state['settled'].values()) if state else [],observed_sessions=sum(r.get('observation_status')=='FROZEN_PLAN_SETTLED' for r in state['result']['daily']) if state else 0,next_execution=plan.get('execution_session') if plan else None,errors=errors),strategy_b=dict(status='NOT_READY',module='KNOWN_CASH_DIVIDEND_NEXT_TWO_SESSIONS_NO_NEW_BUY',reason='Increment scope frozen; announcement completeness, current coverage and separate B ledger not yet admitted. A runs independently. Not Deep Research.'))

def frozen_forward(registry):
 deployment_path=ARCHIVE/'Runtime-Deployment.json'
 if run.sha(deployment_path)!=registry.get('forward_runtime_manifest_ref'):raise ValueError('FROZEN_RUNTIME_MANIFEST_PIN')
 manifest=run.read(deployment_path);directory=ROOT.parent/'metasurvey-forward-frozen-v1'
 if manifest.get('kind')!='FrozenPaperRuntimeDeployment' or manifest['directory']!=str(directory) or directory.resolve()!=directory:raise ValueError('FROZEN_RUNTIME_SCOPE')
 for name,h in manifest['file_pins'].items():
  p=directory/name
  if Path(name).is_absolute() or '..' in Path(name).parts or p.resolve()!=p or p.is_symlink() or run.sha(p)!=h:raise ValueError('FROZEN_RUNTIME_FILE_CHANGED')
 output=subprocess.run([sys.executable,'-B','-m','tools.long_forward.reporting','--forward-summary'],cwd=directory,capture_output=True,text=True,timeout=120,check=True)
 return json.loads(output.stdout)

def verify_dashboard(registry):
 if registry['kind']!='LongForwardRegistry' or registry['version']!='1.0.0' or registry['code_pins']!=run.pins() or registry['protocol_ref']!=run.sha(builder.PROTOCOL) or registry['archive_root']!=str(ARCHIVE):raise ValueError('REGISTRY_BINDING')
 return dict(status='VERIFIED',history=history(ARCHIVE/registry['history_run']) if registry.get('history_run') else None,forward=(frozen_forward(registry) if registry.get('forward_runtime_manifest_ref') else forward(ARCHIVE/registry['forward_state'])) if registry.get('forward_state') else None,integrity='CODE_CONFIG_SOURCE_AND_IMMUTABLE_BUNDLE_REVERIFIED',source='LOCAL_ONLY_NO_RAW_EXPORT')

if __name__=='__main__':
 if sys.argv[1:]!=['--forward-summary']:raise SystemExit('READ_ONLY_FORWARD_SUMMARY_ONLY')
 print(json.dumps(forward(ARCHIVE/'forward/ACTIVE'),ensure_ascii=False))
