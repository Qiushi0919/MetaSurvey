"""History-only raw-price successor. Never imported by the frozen Forward runtime."""
from copy import deepcopy
from pathlib import Path
import argparse, importlib.util, json
from tools.long_forward import builder, run
from experiments.long_forward_v1 import engine
ROOT=run.ROOT
PROTOCOL=ROOT/'experiments/long_forward_v1/history-raw-protocol.json'
INPUT_POLICY=ROOT/'experiments/long_forward_v1/history-raw-input-policy.json'

def protocol():
 p=run.read(PROTOCOL)
 if p['input_policy_ref']!=run.sha(INPUT_POLICY) or p['input_method_version']!='HISTORY_RAW_V2' or p['forward']['enabled'] is not False:raise ValueError('HISTORY_RAW_POLICY_BINDING')
 return p

def references(run_at):
 policy=run.read(INPUT_POLICY);mapping={};proofs={}
 for row in policy['official_reference_adjustments']:
  path=run.ARCHIVE/row['source_relative_path'];receipt_path=run.ARCHIVE/row['receipt_relative_path']
  for f in (path,receipt_path):
   if f.resolve()!=f or f.is_symlink() or not f.is_relative_to(run.ARCHIVE/'official-action'):raise ValueError('OFFICIAL_ACTION_PATH')
  if run.sha(path)!=row['source_sha256'] or run.sha(receipt_path)!=row['receipt_sha256']:raise ValueError('OFFICIAL_ACTION_HASH')
  r=run.read(receipt_path)
  if r['url']!=row['source_url'] or r['sha256']!=row['source_sha256'] or r['http_status']!=200 or r['path']!=path.name:raise ValueError('OFFICIAL_ACTION_RECEIPT')
  if not builder.old.clock(r['request_started_at'])<=builder.old.clock(r['retrieved_at'])<=builder.old.clock(run_at):raise ValueError('OFFICIAL_ACTION_CLOCK')
  key=(row['symbol'],row['ex_date']);ref='official-ex-reference:'+':'.join(key)
  if key in mapping:raise ValueError('OFFICIAL_ACTION_DUPLICATE')
  mapping[key]=dict(row,evidence_ref=ref)
  proofs[ref]=dict(source=row['source_url'],source_version=row['source_sha256'],raw_sha256=row['source_sha256'],path=str(path),published_at=None,available_at=r['retrieved_at'],retrieved_at=r['retrieved_at'],printed_date=row['printed_issuer_date'],visibility_assumption='ACTUAL_RETRIEVAL_ONLY; historical ex-date reference reconstruction, NOT_ORIGINAL_PIT')
 return mapping,proofs

def _adapter(p):
 spec=importlib.util.spec_from_file_location('_long_history_raw_v2',ROOT/'tools/long_forward/history_raw_input.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.SOURCE_POLICY=builder.POLICY;module.OWNER=builder.OWNER;module.PROTOCOL=PROTOCOL;module.INPUT_POLICY=INPUT_POLICY
 original_read=module.read;original_hash=module.rawhash
 module.read=lambda path:deepcopy(p) if path==PROTOCOL else original_read(path)
 module.rawhash=lambda path:engine.digest(p) if path==PROTOCOL else original_hash(path)
 return module

def build_case(folder,run_id,run_at,mode='HISTORY'):
 if mode!='HISTORY':raise ValueError('HISTORY_RAW_V2_MODE_ONLY')
 p=protocol();refs,proofs=references(run_at)
 report,case=_adapter(p).build_case(Path(folder),run_id,run_at,mode=mode,reference_adjustments=refs)
 report.update(kind='LongForwardInputBuild',version='2.0.0',mode='HISTORY',source_epoch='LONG_HISTORY_RAW_V2',authorized_purpose='LOCAL_HISTORICAL_DIAGNOSTIC',protocol_hash=run.sha(PROTOCOL),input_policy_hash=run.sha(INPUT_POLICY))
 if case is not None:
  case.update(mode='HISTORY',source_epoch='LONG_HISTORY_RAW_V2',protocol_ref=engine.digest(p),rules=deepcopy(engine.RULES),rules_hash=engine.digest(engine.RULES))
  case['evidence'].update(proofs);report['case_hash']=engine.digest(case)
 return report,case

def verify_provenance(case,folder):
 report,repeated=build_case(folder,case['run_id'],case['run_at'],case['mode'])
 if repeated!=case or not report['status'].startswith('ADMITTED_'):raise ValueError('HISTORY_RAW_V2_REBUILD_MISMATCH')
 return dict(verified=True,case_hash=engine.digest(case),receipt_hash=engine.digest(report),purpose='LOCAL_HISTORICAL_DIAGNOSTIC')

def execute(capture_dir,run_id):
 run.check_freeze()
 if not run.NAME.fullmatch(run_id):raise ValueError('RUN_ID')
 capture_dir=Path(capture_dir)
 if capture_dir.parent!=run.ARCHIVE or capture_dir.resolve()!=capture_dir:raise ValueError('CAPTURE_SCOPE')
 folder=run.ARCHIVE/'runs'/run_id;folder.mkdir(parents=True,exist_ok=False)
 at=run.stamp();result=None
 try:report,case=build_case(capture_dir,run_id,at)
 except (ValueError,KeyError,TypeError,OSError,ArithmeticError) as exc:
  report={'status':'SOURCE_OR_INPUT_BLOCKED','errors':[{'type':type(exc).__name__,'detail':str(exc)}]};case=None
 run.write(folder/'BuildReport.json',report)
 if case is not None:
  run.write(folder/'Case.json',case)
  result=engine.run_diagnostic(case,lambda c:verify_provenance(c,capture_dir),protocol())
  run.write(folder/'EngineResult.json',result)
  if result['engine_called']:
   from tools.v3_review.performance import derive_performance
   from tools.long_forward.benchmarks import build_benchmarks
   from tools.long_forward.independent import audit
   try:
    run.write(folder/'Performance.json',derive_performance(case,result));run.write(folder/'Yearly.json',run.yearly(case,result))
    run.write(folder/'Arithmetic.json',audit(folder));run.write(folder/'Controls.json',build_benchmarks(case,protocol()))
   except (ValueError,KeyError,TypeError,ArithmeticError) as exc:run.write(folder/'AnalysisError.json',dict(error_type=type(exc).__name__,detail=str(exc)))
 record=dict(kind='LongForwardHistoricalRun',version='2.0.0',run_id=run_id,recorded_at=at,capture_dir=str(capture_dir),status=result['status'] if result else 'SOURCE_OR_INPUT_BLOCKED',engine_called=bool(result and result['engine_called']),window=protocol()['target_window'],historical_protocol_ref=run.sha(PROTOCOL),formal_pit=False,untouched_oos=False,cost_label='SIMULATED_COSTS')
 run.write(folder/'Run.json',record);run.seal(folder);return folder,record

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--capture-dir',required=True);p.add_argument('--run-id',required=True);a=p.parse_args();folder,record=execute(a.capture_dir,a.run_id);print(json.dumps({'directory':str(folder),'status':record['status'],'engine_called':record['engine_called']}))
