"""Whitelist-only derived performance reader; preserves V3 source verifier."""
from pathlib import Path
import json
from tools.v3_review.package import CODE_PATHS, derive

ARCHIVE=Path('/Users/qiushi/投资研究/.p1b-archives/v3-performance-20261015')
ORIGINAL=Path('/Users/qiushi/投资研究/.p1b-archives/e2e-gateway-v3-20261014')
def load(reader,gateway,archive=ARCHIVE,original=ORIGINAL):
    from workbench.server import ReadError,digest
    key='performance-registry'
    reg,source=reader.json(key,'V3PerformanceRegistry')
    if gateway.get('status')!='VERIFIED':raise ReadError('PERFORMANCE_UPSTREAM_NOT_VERIFIED',key)
    pins=reg.get('code_pins')
    if not isinstance(pins,dict) or set(pins)!=set(CODE_PATHS):raise ReadError('PERFORMANCE_CODE_SCOPE',key)
    for path,expected in pins.items():
        raw,_=reader.read_path(reader.root/path,reader.root)
        if digest(raw)!=expected:raise ReadError('PERFORMANCE_CODE_CHANGED',path)
    d=Path(reg.get('analysis_directory',''))
    if d.parent!=archive/'runs' or d.name!='V3-REVIEW-01':raise ReadError('PERFORMANCE_PATH_SCOPE',key)
    raw,text=reader.read_path(d/'Analysis.json',archive)
    if digest(raw)!=reg.get('analysis_hash'):raise ReadError('PERFORMANCE_ANALYSIS_HASH',key)
    payload=json.loads(text);run=gateway['run']
    if (payload.get('kind')!='V3PerformancePackage' or payload.get('version')!='1.0.0'
        or payload.get('production_enabled') is not False or payload.get('result_type')!='EXPOSED_HISTORY_DIAGNOSTIC_ANALYSIS'
        or payload.get('code_pins')!=pins):raise ReadError('PERFORMANCE_PACKAGE_BOUNDARY',key)
    for field in ('run_id','case_hash','engine_result_hash'):
        if reg.get(field)!=run.get(field) or payload.get(field)!=reg.get(field):raise ReadError('PERFORMANCE_UPSTREAM_BINDING',key)
    if reg.get('run_hash')!=payload.get('run_hash'):raise ReadError('PERFORMANCE_RUN_BINDING',key)
    old, _=reader.json('gateway-registry','E2EGatewayRegistry')
    if reg['run_hash']!=old['run_sha256']:raise ReadError('PERFORMANCE_RUN_BINDING',key)
    directory=Path(old['run_directory'])
    if directory.parent!=original/'runs':raise ReadError('PERFORMANCE_ORIGINAL_SCOPE',key)
    raw,text=reader.read_path(directory/'Case.json',original)
    if digest(raw)!=reg['case_hash']:raise ReadError('PERFORMANCE_CASE_CHANGED',key)
    case=json.loads(text)
    raw,text=reader.read_path(directory/'EngineResult.json',original)
    if digest(raw)!=reg['engine_result_hash']:raise ReadError('PERFORMANCE_RESULT_CHANGED',key)
    result=json.loads(text)
    if result!=gateway['diagnostic']:raise ReadError('PERFORMANCE_RESULT_UPSTREAM_MISMATCH',key)
    raw,text=reader.read_path(reader.root/'docs/v3-performance/Benchmark-Protocol.json',reader.root)
    checked=derive(case,result,json.loads(text))
    if any(payload.get(k)!=v for k,v in checked.items()):raise ReadError('PERFORMANCE_RECOMPUTATION_MISMATCH',key)
    return {'status':'VERIFIED','run_id':reg['run_id'],'engine_result_hash':reg['engine_result_hash'],
            **checked,'provenance':source,'result_type':payload['result_type']}
