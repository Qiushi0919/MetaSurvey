"""One-shot private real-input build/run, and deterministic read-only verification.
No implicit capture, API retries, credential reads or old artifact replacement.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,re,sys,stat
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.e2e_gateway.builder import build_case,verify_provenance,rawhash,read,PROTOCOL,INPUT_POLICY,SOURCE_POLICY
from experiments.e2e_history_v2.engine import run_diagnostic,digest
ARCHIVE=ROOT.parent/'.p1b-archives/e2e-gateway-v3-20261014'
CODE_PATHS=('tools/e2e_gateway/run.py','tools/e2e_gateway/builder.py','tools/e2e_gateway/capture.py','experiments/e2e_gateway_v3/input-policy.json','docs/e2e-gateway-v3/Source-Policy.json','docs/e2e-gateway-v3/Owner-Authorization.md','config/provider/tushare-monthly-gateway.json','tushare-real-admission/probe.py','tushare-admission/probe.py','experiments/e2e_history_v2/engine.py','experiments/e2e_history_v2/protocol.json','experiments/e2e_pilot_v1/method.json','experiments/e2e_pilot_v1/execution.py','backtest_5y/gateway.py','backtest_5y/economics.py','wave_f/backtest.py')
RUN_ID_RE=re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}')
def pins():return {name:rawhash(ROOT/name) for name in CODE_PATHS}
def validate_dir(p,kind):
 p=Path(p)
 if p.is_symlink() or p.absolute()!=p.resolve():raise ValueError('PRIVATE_PATH_ALIAS_OR_SYMLINK')
 parent=ARCHIVE/'runs' if kind=='run' else ARCHIVE
 if p.parent!=parent:raise ValueError('PRIVATE_SCOPE_PATH_REQUIRED')
 if kind=='run' and not RUN_ID_RE.fullmatch(p.name):raise ValueError('SAFE_RUN_ID_REQUIRED')
 if kind=='capture' and not re.fullmatch(r'capture-[A-Za-z0-9._-]+',p.name):raise ValueError('REGISTERED_CAPTURE_DIRECTORY_REQUIRED')
 if p.exists() and not p.is_dir():raise ValueError('PRIVATE_DIRECTORY_REQUIRED')
 return p

def metadata_file(p,optional=False):
 p=Path(p)
 if p.is_symlink() or p.absolute()!=p.resolve():raise ValueError('METADATA_ALIAS_OR_SYMLINK')
 try:mode=p.lstat().st_mode
 except FileNotFoundError:
  if optional:return None
  raise ValueError('METADATA_FILE_MISSING:'+p.name)
 if not stat.S_ISREG(mode):raise ValueError('METADATA_REGULAR_FILE_REQUIRED:'+p.name)
 return p

def write_exclusive(p,obj):
 with p.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def execute(capture_dir,run_id):
 if not isinstance(run_id,str) or not RUN_ID_RE.fullmatch(run_id):raise ValueError('SAFE_RUN_ID_REQUIRED')
 capture_dir=validate_dir(capture_dir,'capture');directory=validate_dir(ARCHIVE/'runs'/run_id,'run')
 manifest=metadata_file(capture_dir/'Manifest.json',optional=True)
 directory.parent.mkdir(exist_ok=True);directory.mkdir(exist_ok=False)
 at=datetime.now(timezone.utc).isoformat();report,case=build_case(capture_dir,run_id,at)
 write_exclusive(directory/'BuildReport.json',report);result=None
 if case is not None:
  write_exclusive(directory/'Case.json',case)
  result=run_diagnostic(case,provenance_verifier=lambda x:verify_provenance(x,capture_dir))
  write_exclusive(directory/'EngineResult.json',result)
 run={'kind':'HistoricalGatewayDiagnosticRun','version':'3.0.0','run_id':run_id,'recorded_at':at,'capture_dir':str(capture_dir),'input_policy_hash':rawhash(INPUT_POLICY),'protocol_hash':rawhash(PROTOCOL),'source_policy_hash':rawhash(SOURCE_POLICY),'code_pins':pins(),'capture_manifest_hash':rawhash(manifest) if manifest is not None else None,'build_report_hash':rawhash(directory/'BuildReport.json'),'case_hash':rawhash(directory/'Case.json') if case is not None else None,'engine_result_hash':rawhash(directory/'EngineResult.json') if result is not None else None,'status':result['status'] if result is not None else 'SOURCE_OR_INPUT_BLOCKED','engine_called':bool(result and result['engine_called']),'evidence_grade':'RECONSTRUCTED_HISTORY_DIAGNOSTIC','historical_visibility_proven':False,'production_enabled':False,'cost_label':'SIMULATED_COSTS','source_epoch':'COMPATIBLE_GATEWAY_V3','provider_license_status':'OWNER_AUTHORIZED_LOCAL_RECONSTRUCTED_UNVERIFIED_PROVIDER','scope':'FIXED_NINE_CURRENTLY_SELECTED_SAMPLE_NOT_FULL_RESEARCH_VALIDATION'}
 run['content_hash']=digest(run);write_exclusive(directory/'Run.json',run)
 return directory,run

def verify_existing(run_dir):
 directory=validate_dir(run_dir,'run');run=read(metadata_file(directory/'Run.json'));body={k:v for k,v in run.items() if k!='content_hash'}
 if run.get('content_hash')!=digest(body):raise ValueError('RUN_CONTENT_HASH_MISMATCH')
 if type(run.get('engine_called')) is not bool:raise ValueError('RUN_ENGINE_CALLED_BOOLEAN_REQUIRED')
 if run.get('kind')!='HistoricalGatewayDiagnosticRun' or run.get('version')!='3.0.0' or run.get('run_id')!=directory.name:raise ValueError('RUN_IDENTITY_MISMATCH')
 if run.get('code_pins')!=pins():raise ValueError('RUN_CODE_PINS_MISMATCH')
 for key,p in [('input_policy_hash',INPUT_POLICY),('protocol_hash',PROTOCOL),('source_policy_hash',SOURCE_POLICY)]:
  if run.get(key)!=rawhash(p):raise ValueError('RUN_POLICY_HASH_MISMATCH')
 if run.get('evidence_grade')!='RECONSTRUCTED_HISTORY_DIAGNOSTIC' or run.get('historical_visibility_proven') is not False or run.get('production_enabled') is not False:raise ValueError('RUN_BOUNDARY_MISMATCH')
 
 for field,expected in {'source_epoch':'COMPATIBLE_GATEWAY_V3','provider_license_status':'OWNER_AUTHORIZED_LOCAL_RECONSTRUCTED_UNVERIFIED_PROVIDER','cost_label':'SIMULATED_COSTS','scope':'FIXED_NINE_CURRENTLY_SELECTED_SAMPLE_NOT_FULL_RESEARCH_VALIDATION'}.items():
  if run.get(field)!=expected:raise ValueError('RUN_FROZEN_LABEL_MISMATCH:'+field)
 capture_dir=validate_dir(run['capture_dir'],'capture');manifest=metadata_file(capture_dir/'Manifest.json',optional=True)
 report_path=metadata_file(directory/'BuildReport.json')
 case_path=metadata_file(directory/'Case.json',optional=True)
 result_path=metadata_file(directory/'EngineResult.json',optional=True)
 if run['capture_manifest_hash']!=(rawhash(manifest) if manifest is not None else None):raise ValueError('CAPTURE_MANIFEST_CHANGED')
 report,case=build_case(capture_dir,run['run_id'],run['recorded_at'])
 if rawhash(report_path)!=run['build_report_hash'] or read(report_path)!=report:raise ValueError('BUILD_REPORT_RECOMPUTATION_MISMATCH')
 result=None
 if case is not None:
  if case_path is None or rawhash(case_path)!=run['case_hash'] or read(case_path)!=case:raise ValueError('CASE_REBUILD_MISMATCH')
  result=run_diagnostic(case,provenance_verifier=lambda x:verify_provenance(x,capture_dir))
  if result_path is None or rawhash(result_path)!=run['engine_result_hash'] or read(result_path)!=result:raise ValueError('ENGINE_RECOMPUTATION_MISMATCH')
 elif run['case_hash'] is not None or run['engine_result_hash'] is not None or case_path is not None or result_path is not None:raise ValueError('BLOCKED_BUILD_CANNOT_HAVE_FAKE_CASE_OR_RESULT')
 if run['engine_called']!=bool(result and result['engine_called']) or run['status']!=(result['status'] if result else 'SOURCE_OR_INPUT_BLOCKED'):raise ValueError('RUN_STATUS_MISMATCH')
 return {'run':run,'build_report':report,'engine_result':result,'api_matrix':api_matrix(capture_dir)}

def api_matrix(capture_dir):
 from tools.e2e_gateway.capture import plan
 manifest=read(metadata_file(capture_dir/'Manifest.json'))
 rows=[]
 for api,params in plan()[1]:
  entries=[x for x in manifest['sources'] if x['api_name']==api and x['params']==params]
  if len(entries)>1:raise ValueError('API_MATRIX_DUPLICATE')
  if not entries:rows.append({'api_name':api,'params':params,'state':'NOT_CALLED','row_count':None,'min_date':None,'max_date':None});continue
  entry=entries[0];p=capture_dir/entry['path']
  if p.parent!=capture_dir:raise ValueError('API_MATRIX_PATH_SCOPE')
  p=metadata_file(p)
  if rawhash(p)!=entry['sha256']:raise ValueError('API_MATRIX_PIN_MISMATCH')
  item=read(p);records=[dict(zip(item['fields'],v)) for v in item['items']]
  key='cal_date' if api=='trade_cal' else ('trade_date' if api in ('daily','stk_limit','suspend_d','adj_factor') else ('ex_date' if api=='dividend' else None))
  dates=sorted(str(r[key]) for r in records if key and r.get(key))
  rows.append({'api_name':api,'params':params,'state':item['state'],'row_count':len(records),'min_date':dates[0] if dates else None,'max_date':dates[-1] if dates else None,'raw_sha256':item['raw_sha256'],'retrieved_at':item['retrieved_at'],'error_code':item['error_code']})
 return rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--capture-dir',type=Path);p.add_argument('--run-id');p.add_argument('--verify-existing',type=Path);a=p.parse_args()
 if a.verify_existing:r=verify_existing(a.verify_existing);print(json.dumps({'integrity':'RECOMPUTED_FROM_CAPTURE_AND_POLICY','run_id':r['run']['run_id'],'status':r['run']['status'],'engine_called':r['run']['engine_called']}));return
 if not a.capture_dir or not a.run_id:p.error('--capture-dir and --run-id required')
 directory,run=execute(a.capture_dir,a.run_id);print(json.dumps({'run_directory':str(directory),'status':run['status'],'engine_called':run['engine_called']}))
if __name__=='__main__':main()
