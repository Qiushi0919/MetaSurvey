"""Read-only deterministic verification of pinned quarantine evidence; no secrets/network."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys
from datetime import timedelta,timezone

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = Path('/Users/qiushi/投资研究/.p1b-archives/tushare-real-admission-20261005/captures')
spec = importlib.util.spec_from_file_location('read_only_probe', ROOT/'tushare-real-admission/probe.py')
probe = importlib.util.module_from_spec(spec); sys.modules[spec.name] = probe; spec.loader.exec_module(probe)
sha = lambda b: 'sha256:'+hashlib.sha256(b).hexdigest()

def require(condition, reason):
    if not condition: raise ValueError(reason)

def read_file(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and p.resolve()==p and p.is_relative_to(ARCHIVE), 'RAW_PATH_INVALID')
    require(p.is_file() and not p.is_symlink() and stat.S_IMODE(p.stat().st_mode)==0o600,'RAW_FILE_PERMISSION_INVALID')
    return p.read_bytes()

def verify_report(path):
    report=json.loads(read_file(path))
    template=probe.run_probe(credential=None,run_id='validator-template-not-a-real-observation',persist=False)
    require(set(report)==set(template),'UNKNOWN_REPORT_FIELDS')
    require(report['fixture'] is False and report['report_kind']=='OWNER_AUTHORIZED_QUARANTINE_PROBE','FIXTURE_AS_REAL')
    for key,value in {'version':'1.0.0','provider_id':probe.PROVIDER_ID,'source_classification':probe.SOURCE_CLASSIFICATION,'purpose':probe.PURPOSE,'namespace':'CORE_40','symbols':list(probe.SYMBOLS),'provider_identity_verified':False,'license_verified':False,'historical_visibility_proven':False,'productionGate':False,'mock_transport_attempts':0,'credential_rotation_required':False,'actual_account_tier':15000,'account_tier_evidence':'OWNER_ASSERTION_NOT_ACCOUNT_VERIFIED','owner_asserted_expiration_date':'2026-11-05','expiration_precision':'DATE_ONLY','expiration_instant':'UNSET_REQUIRED','transport':'HTTP_OWNER_ACCEPTED_FOR_PROBE_INTEGRITY_UNVERIFIED'}.items():
        require(report.get(key)==value,'REPORT_SCOPE_OR_AUTHORITY_INVALID')
    require(report['gates']==probe.GATES and report['admission_refs']==template['admission_refs'] and report['cross_cutting']==template['cross_cutting'],'REPORT_GATE_ESCALATION')
    require(report['code_hash']==sha((ROOT/'tushare-real-admission/probe.py').read_bytes()),'CAPTURE_CODE_EPOCH_INVALID')
    require(report['frozen_utility_hash']==sha((ROOT/'tushare-admission/probe.py').read_bytes()),'UTILITY_CODE_EPOCH_INVALID')
    require(report['credential_lookup']['credential_source']=='EXPLICIT_KEYCHAIN','CREDENTIAL_SOURCE_INVALID')
    require(set(report['credential_lookup'])=={'secret_presence','lookup_result','credential_source'},'CREDENTIAL_METADATA_INVALID')
    require((report['credential_lookup']['lookup_result']=='FOUND') is report['credential_lookup']['secret_presence'],'CREDENTIAL_LOOKUP_TUPLE_INVALID')
    probe._safe_run_id(report['run_id'])
    generated=probe._old._validate_clock(report['generated_at']);completed=probe._old._validate_clock(report['completed_at'])
    require(completed>=generated,'COLLECTOR_CLOCK_REVERSED')
    stages={r['scope'] for r in report['requests']}; require(len(stages)==1,'CAPTURE_STAGES_INVALID')
    plan=probe.build_plan(next(iter(stages)))
    require(len(plan)==len(report['requests']),'REQUEST_INVENTORY_INCOMPLETE')
    presence=report['credential_lookup']['secret_presence']
    require(report['status']==('PROBE_COMPLETED_ADMISSION_BLOCKED' if presence else 'BLOCKED_SECRET_NOT_AVAILABLE'),'REPORT_STATUS_INVALID')
    require(type(presence) is bool and report['network_requests']==(len(plan) if presence else 0),'NETWORK_COUNTS_INVALID')
    inventory=[];tables={}
    for request,expected in zip(report['requests'],plan):
        require(all(request.get(k)==v for k,v in expected.public().items()),'CANONICAL_REQUEST_SCOPE_INVALID')
        require(request['request_fingerprint']==probe.request_fingerprint(expected),'REQUEST_FINGERPRINT_INVALID')
        require(request['code_hash']==report['code_hash'] and request['source_classification']==probe.SOURCE_CLASSIFICATION,'REQUEST_CODE_OR_PROVIDER_INVALID')
        require(request['historical_visibility_proven'] is False and request['admission_status']=='BLOCKED','REQUEST_ADMISSION_ESCALATION')
        require(request['published_at'] is None and request['event_time'] is None and request['business_effective_at'] is None,'DATE_ONLY_OR_EVENT_CLOCK_SPOOF')
        if request['raw_ref'] is None:
            require(set(request)==set(template['requests'][0]),'UNKNOWN_REQUEST_FIELDS')
            require(request['raw_sha256'] is None and request['row_count'] is None,'UNBACKED_RAW_CLAIM')
            require(request['status'] in ('BLOCKED','QUARANTINE','BLOCKED_SECRET_NOT_AVAILABLE'),'UNBACKED_PROBE_SUCCESS')
            require(all(request.get(k) is None for k in ('request_started_at','response_completed_at','http_status','provider_code','response_schema','retrieved_at','available_at','observation_event_at','available_at_basis')),'UNBACKED_RESPONSE_OR_CLOCK_CLAIM')
            require(request['dq_status']=='BLOCKED' and request['published_precision']=='UNKNOWN','UNBACKED_DQ_OR_PUBLICATION')
            require(request['provider_msg_classification']=='NOT_QUERIED','UNBACKED_RESPONSE_CLASSIFICATION')
            require(request['reason_codes'] and all(k in probe.SAFE_REASONS or k in ('SECRET_NOT_AVAILABLE','CONTROLLED_CAPTURE_FAILURE') for k in request['reason_codes']),'UNCONTROLLED_FAILURE_REASON')
            continue
        canonical=ARCHIVE/report['run_id']/expected.api_name/(expected.id+'.response.json')
        require(request['raw_ref']==str(canonical),'RAW_REQUEST_LINEAGE_INVALID')
        raw=read_file(canonical)
        require(request['reason_codes']==[] and request['raw_storage_authority']=='OWNER_PROBE_QUARANTINE_ONLY_SUPPLIER_LICENSE_UNVERIFIED','RAW_QUARANTINE_METADATA_INVALID')
        require(sha(raw)==request['raw_sha256'] and len(raw)==request['raw_bytes'],'RAW_BYTES_MUTATED')
        start=probe._old._validate_clock(request['request_started_at']);end=probe._old._validate_clock(request['response_completed_at'])
        require(generated<=start<=end<=completed,'CAPTURE_CLOCK_OUTSIDE_RUN')
        require(all(request[k]==request['response_completed_at'] for k in ('retrieved_at','available_at','observation_event_at')),'COLLECTOR_CLOCK_SPOOF')
        require(request['available_at_basis']=='FIRST_OBSERVED_BY_THIS_COLLECTOR','HISTORICAL_AVAILABILITY_SPOOF')
        analysis=probe.analyze_response(expected,raw,request['response_completed_at'])
        # Implementation announcement is publication evidence, unlike a future ex/pay date.
        # This newer verification epoch supplements the immutable collector's original DQ.
        doc=probe._old.parse_response(raw)
        if isinstance(doc,dict) and isinstance(doc.get('data'),dict):
            fields=doc['data'].get('fields',[]);items=doc['data'].get('items',[])
            if isinstance(fields,list) and isinstance(items,list):
                observed_day=end.astimezone(timezone(timedelta(hours=8))).strftime('%Y%m%d')
                for vector in items:
                    if isinstance(vector,list) and len(vector)==len(fields):
                        row=dict(zip(fields,vector))
                        for field in ('ann_date','f_ann_date','imp_ann_date'):
                            if row.get(field) is not None:
                                require(probe._date(row[field])<=observed_day,'FUTURE_PUBLICATION_DATE')
        require(set(request)==set(template['requests'][0])|set(analysis)|{'raw_bytes','raw_storage_authority'},'UNKNOWN_REQUEST_FIELDS')
        require(all(request.get(k)==v for k,v in analysis.items()),'RAW_ANALYSIS_MUTATED')
        require(request['published_precision']==analysis['publication_precision'],'PUBLICATION_PRECISION_SPOOF')
        state='PROBE_SUCCESS' if request['http_status']==200 and analysis['provider_code']==0 else 'PROBE_RESPONSE_FAILURE'
        if analysis['dq_status']=='BLOCKED':state='QUARANTINE_DQ_OR_API_FAILURE'
        require(request['status']==state,'PROBE_STATUS_SPOOF')
        inventory.append({'path':str(canonical),'sha256':sha(raw)})
        if analysis['provider_code']==0 and analysis['dq_status']=='PASS':
            table=probe._old.parse_response(raw)['data']
            tables[(expected.api_name,dict(expected.params).get('ts_code'))]=[dict(zip(table['fields'],row)) for row in table['items']]
    require(report['categories']==probe._matrix(report['requests']),'REPORT_MATRIX_MUTATED')
    calendar=tables.get(('trade_cal',None))
    open_dates={r['cal_date'] for r in calendar if str(r['is_open'])=='1'} if calendar else None
    for symbol in probe.SYMBOLS:
        bars=tables.get(('daily',symbol));factors=tables.get(('adj_factor',symbol))
        if bars and open_dates is not None: require(all(r['trade_date'] in open_dates for r in bars),'BAR_CALENDAR_MISMATCH')
        if bars and factors:require({r['trade_date'] for r in bars}=={r['trade_date'] for r in factors},'BAR_FACTOR_DATE_MISMATCH')
    return report,inventory

if __name__=='__main__':
    try:
        reports=[];inventory=[]
        for path in sys.argv[1:]:
            r,raw=verify_report(path);reports.append(r);inventory.extend(raw)
        require(len({r['run_id'] for r in reports})==len(reports),'REPORT_REUSE')
        print(json.dumps({'reports':reports,'raw_inventory':inventory},ensure_ascii=False,separators=(',',':')))
    except Exception:
        print(json.dumps({'verification':'FAIL','reason':'CONTROLLED_EVIDENCE_VERIFICATION_FAILURE'}));sys.exit(1)
