"""Build read-only derived analysis; no calls to execution, market, or credentials."""
from pathlib import Path
import argparse, json, hashlib
from tools.v3_review.performance import derive_performance
from tools.v3_review.benchmarks import build_benchmarks
from workbench.gateway_reader import CODE_PATHS as ORIGINAL_CODE_PATHS

CODE_PATHS=('tools/v3_review/performance.py','tools/v3_review/benchmarks.py','tools/v3_review/package.py',
            'docs/v3-performance/Benchmark-Protocol.json','docs/v3-performance/Research-Increment.json')
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def encode(obj):return json.dumps(obj,ensure_ascii=False,indent=2).encode()+b'\n'
def derive(case,result,protocol):
    performance=derive_performance(case,result)
    benchmarks=build_benchmarks(case,protocol)
    return {'performance':performance,'benchmarks':benchmarks}
def validate_original(old,run):
    if old.get('kind')!='E2EGatewayRegistry' or old.get('version')!='1.0.0':raise ValueError('ORIGINAL_REGISTRY_VERSION')
    if not isinstance(old.get('code_pins'),dict) or set(old['code_pins'])!=set(ORIGINAL_CODE_PATHS):raise ValueError('ORIGINAL_CODE_SCOPE')
    if (run.get('kind')!='HistoricalGatewayDiagnosticRun' or run.get('version')!='3.0.0'
        or run.get('code_pins')!=old['code_pins'] or run.get('engine_called') is not True
        or run.get('status') not in ('SIMULATED_TRADES','RUN_NO_TRADES')
        or run.get('production_enabled') is not False or run.get('historical_visibility_proven') is not False
        or run.get('evidence_grade')!='RECONSTRUCTED_HISTORY_DIAGNOSTIC'
        or run.get('source_epoch')!='COMPATIBLE_GATEWAY_V3'):
        raise ValueError('ORIGINAL_RUN_CONTRACT')

def build(root,run_dir,output_dir):
    root=Path(root);run_dir=Path(run_dir);output_dir=Path(output_dir)
    old=json.loads((root/'docs/e2e-gateway-v3/Registry.json').read_text())
    if str(run_dir)!=old['run_directory'] or digest((run_dir/'Run.json').read_bytes())!=old['run_sha256']:raise ValueError('ORIGINAL_RUN_MISMATCH')
    rawcase=(run_dir/'Case.json').read_bytes();rawresult=(run_dir/'EngineResult.json').read_bytes()
    run=json.loads((run_dir/'Run.json').read_text())
    validate_original(old,run)
    if run.get('run_id')!=run_dir.name:raise ValueError('ORIGINAL_RUN_ID')
    # Exact original file pins and original source code pins are checked before derivation.
    for path,expected in old['code_pins'].items():
        if digest((root/path).read_bytes())!=expected:raise ValueError('ORIGINAL_CODE_CHANGED:'+path)
    if run['case_hash']!=digest(rawcase) or run['engine_result_hash']!=digest(rawresult):raise ValueError('ORIGINAL_INPUT_CHANGED')
    c,r=json.loads(rawcase),json.loads(rawresult)
    protocol=json.loads((root/'docs/v3-performance/Benchmark-Protocol.json').read_text())
    payload={'kind':'V3PerformancePackage','version':'1.0.0','run_id':c['run_id'],
             'case_hash':digest(rawcase),'engine_result_hash':digest(rawresult),'run_hash':old['run_sha256'],
             'code_pins':{p:digest((root/p).read_bytes()) for p in CODE_PATHS},
             'result_type':'EXPOSED_HISTORY_DIAGNOSTIC_ANALYSIS','production_enabled':False,
             **derive(c,r,protocol)}
    output_dir.mkdir(parents=True,exist_ok=False)
    raw=encode(payload);(output_dir/'Analysis.json').write_bytes(raw)
    registry={'kind':'V3PerformanceRegistry','version':'1.0.0','run_id':c['run_id'],
              'analysis_directory':str(output_dir),'analysis_hash':digest(raw),
              'case_hash':payload['case_hash'],'engine_result_hash':payload['engine_result_hash'],
              'run_hash':old['run_sha256'],'code_pins':payload['code_pins']}
    return registry
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--registry',type=Path,required=True);a=p.parse_args()
    if a.registry.exists():raise SystemExit('REGISTRY_EXISTS_NO_OVERWRITE')
    registry=build(a.root,a.run,a.output);a.registry.write_bytes(encode(registry));print(json.dumps({'run_id':registry['run_id'],'analysis_hash':registry['analysis_hash']}))
