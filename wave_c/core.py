"""Closed local sandbox loader and registered artifact/version boundary. No network."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
import hashlib, json, re
from wave_b.core import load_inputs as load_wave_b, require_inputs, request_views
from overnight.analysis.inputs import instant_ns
from wave_b.evidence_root import ARCHIVE as WAVE_B_ARCHIVE

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = WAVE_B_ARCHIVE.parent / 'wave-c-20261006'
SYMBOLS = ('603993.SH', '600312.SH', '603228.SH')
APIS = ('stock_basic', 'trade_cal', 'daily', 'dividend', 'adj_factor', 'fina_indicator', 'index_member_all')
_REGISTRY = {}

def require(ok, code):
    if not ok: raise ValueError(code)

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def sha(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()
def digest(value): return sha(canonical(value))
def seal(value): return {**value, 'content_hash': digest(value)}
def ref(value): return {k:value[k] for k in ('object_id','object_version','content_hash')}
def instant(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)',value), 'WAVE_C_CLOCK_INVALID')
    return datetime.fromisoformat(value.replace('Z','+00:00'))
def day(value):
    require(type(value) is str and re.fullmatch(r'\d{8}',value), 'WAVE_C_DATE_INVALID')
    d=datetime.strptime(value,'%Y%m%d').date()
    require(d.strftime('%Y%m%d')==value,'WAVE_C_DATE_INVALID');return d

def checked_file(p, expected=None):
    require(p.resolve()==p and p.is_file() and not p.is_symlink(), 'WAVE_C_PATH_INVALID')
    b=p.read_bytes()
    if expected:require(sha(b)==expected,'WAVE_C_DEPENDENCY_INVALIDATED')
    return b

def frozen_context():
    baseline_p=ROOT/'docs/wave-c/baseline-pins.json';baseline_raw=checked_file(baseline_p);baseline=json.loads(baseline_raw)
    checkpoint_p=ARCHIVE/'start/checkpoint.json';checkpoint_raw=checked_file(checkpoint_p,baseline['checkpoint_sha256']);checkpoint=json.loads(checkpoint_raw)
    require(baseline['tracked_files']==checkpoint['tracked_files'] and len(baseline['tracked_files'])==530 and baseline['allowed_navigation_updates']==['AGENTS.md','README.md','docs/source-of-truth.json'],'WAVE_C_BASELINE_BINDING_INVALID')
    pins=[(ROOT/r['path'],r['sha256']) for r in baseline['tracked_files'] if r['path'] not in baseline['allowed_navigation_updates']]
    release_p=ROOT/'docs/wave-c/release.json';release_raw=checked_file(release_p);release=json.loads(release_raw)
    require(release['version']=='1.0.0-wave-c-sandbox' and release['formal_source_admission']=='BLOCKED' and release['productionGate'] is False,'WAVE_C_RELEASE_PERMISSION_INVALID')
    pins.extend((ROOT/r['path'],r['sha256']) for r in release['code_pins'])
    rules_p=ROOT/'docs/wave-c/rules.json';rules_raw=checked_file(rules_p);rules=json.loads(rules_raw)
    require(rules['symbols']==list(SYMBOLS) and rules['current_observed_only'] is True and rules['historical_visibility_proven'] is False and rules['productionGate'] is False,'WAVE_C_RULE_PERMISSION_INVALID')
    for p,h in pins:checked_file(p,h)
    pins.extend((p,sha(b)) for p,b in [(baseline_p,baseline_raw),(checkpoint_p,checkpoint_raw),(release_p,release_raw),(rules_p,rules_raw)])
    provider_p=ROOT/'docs/wave-c/provider-resolution.json';provider_raw=checked_file(provider_p);provider=json.loads(provider_raw)
    require(provider['state']=='OPEN' and provider['formal_admission']=='BLOCKED' and provider['provider_identity_verified'] is False and provider['license_verified'] is False and provider['transport_integrity_verified'] is False,'WAVE_C_PROVIDER_RESOLUTION_PERMISSION_INVALID')
    pins.append((provider_p,sha(provider_raw)))
    for r in provider['references']:
        if r['status']==200:
            public_path=Path(r['path']);require(public_path.is_relative_to(ARCHIVE/'public-reference'),'WAVE_C_PUBLIC_REFERENCE_PATH_INVALID')
            checked_file(public_path,r['sha256']);pins.append((public_path,r['sha256']))
    return {'rules':rules,'rules_hash':sha(rules_raw),'baseline_hash':sha(baseline_raw),'release_hash':sha(release_raw),'code_hash':digest(release['code_pins']),'pins':pins}

def header(kind,symbol,ctx,identity,retrieval):
    return {'contract_name':'RealResearchSandbox'+kind,'contract_version':'1.0.0','object_id':'sandbox:'+kind.lower()+':'+symbol+':'+identity[7:23],
      'object_version':1,'trace_id':'wave-c:'+identity[7:],'symbol':symbol,'strategy_id':'CORE_40','namespace':'LOCAL_EXPERIMENTAL_REAL_RESEARCH:CORE_40',
      'trust_tier':'LOCAL_EXPERIMENTAL_REAL_RESEARCH','purpose':'LOCAL_EXPERIMENTAL_RESEARCH','provider_id':'TUSHARE_MONTHLY_GATEWAY','source_classification':'OWNER_PROVIDED_MONTHLY_GATEWAY',
      'source_admission':'UNVERIFIED_GATEWAY','formal_source_admission':'BLOCKED','provider_identity_verified':False,'license_verified':False,'transport_integrity_verified':False,
      'historical_visibility_proven':False,'current_observed':True,'decision_cutoff':ctx['rules']['decision_cutoff'],'retrieval_cutoff':retrieval,
      'rules_hash':ctx['rules_hash'],'code_version':'1.0.0-wave-c-sandbox','code_hash':ctx['code_hash'],'source_identity':identity,
      'local_only':True,'cloud_transfer':False,'tradeable':False,'validation_status':'NON_TRADEABLE','can_produce_order':False,'production_eligible':False,'productionGate':False,
      'real_account_settings':'UNSET_REQUIRED','reason_codes':['WAVE_C_UNVERIFIED_GATEWAY','WAVE_C_CURRENT_OBSERVED_ONLY','WAVE_C_NON_TRADEABLE','WAVE_C_UNCALIBRATED'],
      'invalidation_conditions':['RAW_OR_SOURCE_EVIDENCE_CHANGED','FINANCIAL_ACTION_FACTOR_INDUSTRY_VERSION_CHANGED','RULES_CODE_SCHEMA_CHANGED','CUTOFF_OR_NAMESPACE_CHANGED','CALLER_COPY_OR_RESEAL']}

def _context_hash(ctx):
    return digest({**{k:v for k,v in ctx.items() if k!='pins'},'pins':[(str(p),h) for p,h in ctx['pins']]})

def register(*args,**kwargs):raise ValueError('WAVE_C_DIRECT_ISSUE_FORBIDDEN')
def derive(*args,**kwargs):raise ValueError('WAVE_C_DIRECT_ISSUE_FORBIDDEN')

def _identity(ctx,upstream):
    return digest({'upstream':upstream['source_identity'],'rules':ctx['rules_hash'],'release':ctx['release_hash'],'baseline':ctx['baseline_hash'],'cutoff':ctx['rules']['decision_cutoff']})

def _register(value,ctx,upstream,parents=()):
    # Even direct calls to this private helper must reproduce the closed factory's
    # complete content. Caller body, context and authority flags are not trusted.
    actual=frozen_context();require(_context_hash(ctx)==_context_hash(actual),'WAVE_C_CONTEXT_FORGERY_FORBIDDEN')
    require_inputs(upstream);require(upstream['fixture'] is False,'WAVE_C_SYNTHETIC_SOURCE_FORBIDDEN')
    kind=value['contract_name'].removeprefix('RealResearchSandbox');symbol=value['symbol']
    require(symbol in SYMBOLS,'WAVE_C_SYMBOL_CROSSOVER')
    if kind=='Input':
        require(not parents,'WAVE_C_INPUT_PARENTS_FORBIDDEN')
        expected_body,retrieval=_input_body(upstream,symbol,ctx)
    elif kind=='Assessment':
        require(tuple(p['symbol'] for p in parents)==SYMBOLS and all(p['contract_name']=='RealResearchSandboxInput' for p in parents),'WAVE_C_COHORT_OR_NAMESPACE_INVALID')
        for p in parents:assert_registered(p)
        from .research import _assessment_bodies
        expected_body=_assessment_bodies(list(parents))[SYMBOLS.index(symbol)];retrieval=parents[0]['retrieval_cutoff']
    elif kind=='Report':
        require(len(parents)==1 and parents[0]['contract_name']=='RealResearchSandboxAssessment' and parents[0]['symbol']==symbol,'WAVE_C_REPORT_PARENT_INVALID')
        assert_registered(parents[0]);from .report import _report_body
        expected_body=_report_body(parents[0]);retrieval=parents[0]['retrieval_cutoff']
    else:raise ValueError('WAVE_C_ISSUE_KIND_INVALID')
    expected={**header(kind,symbol,ctx,_identity(ctx,upstream),retrieval),'body':expected_body}
    require(canonical(value)==canonical(expected),'WAVE_C_PRODUCER_CONTENT_FORGERY_FORBIDDEN')
    v=seal(expected);snapshot=deepcopy(ctx)
    _REGISTRY[id(v)]={'value':v,'hash':digest(v),'ctx':snapshot,'ctx_hash':_context_hash(snapshot),'upstream':upstream,'parents':parents}
    return v

def assert_registered(value):
    known=_REGISTRY.get(id(value));require(known is not None and known['value'] is value and known['hash']==digest(value),'WAVE_C_UNREGISTERED_OR_MUTATED')
    ctx,upstream,parents=known['ctx'],known['upstream'],known['parents']
    require(_context_hash(ctx)==known['ctx_hash'],'WAVE_C_CONTEXT_MUTATED')
    require_inputs(upstream)
    for p,h in ctx['pins']:checked_file(p,h)
    for parent in parents:assert_registered(parent)
    require(value['symbol'] in SYMBOLS and value['namespace']=='LOCAL_EXPERIMENTAL_REAL_RESEARCH:CORE_40' and value['source_admission']=='UNVERIFIED_GATEWAY' and value['formal_source_admission']=='BLOCKED' and value['historical_visibility_proven'] is False and value['productionGate'] is False,'WAVE_C_AUTHORITY_INVALID')
    return value

def context_for(value):
    assert_registered(value);r=_REGISTRY[id(value)];return deepcopy(r['ctx']),r['upstream']

def parent_for(value):assert_registered(value);return _REGISTRY[id(value)]['parents'][0]

def produce_assessments(inputs):
    from .research import _assessment_bodies
    bodies=_assessment_bodies(inputs);ctx,upstream=context_for(inputs[0]);out=[]
    for i,parent in enumerate(inputs):
        value={**header('Assessment',parent['symbol'],ctx,parent['source_identity'],parent['retrieval_cutoff']),'body':bodies[i]}
        out.append(_register(value,ctx,upstream,tuple(inputs)))
    return out

def produce_reports(assessments):
    from .report import _report_body
    require(type(assessments) is list and tuple(a['symbol'] for a in assessments)==SYMBOLS,'WAVE_C_REPORT_COHORT_INVALID')
    out=[]
    for a in assessments:
        assert_registered(a);ctx,upstream=context_for(a)
        out.append(_register({**header('Report',a['symbol'],ctx,a['source_identity'],a['retrieval_cutoff']),'body':_report_body(a)},ctx,upstream,(a,)))
    return out

def _reason(q,row,cutoff):
    if q['response_blocked']:return 'WHOLE_RESPONSE_DQ_BLOCKED'
    values=row.get('values',row)
    for field in ('ann_date','f_ann_date','imp_ann_date'):
        if values.get(field) not in (None,'') and day(values[field])>instant(q['retrieved_at']).astimezone(ZoneInfo('Asia/Shanghai')).date():return 'FUTURE_PUBLICATION_LITERAL'
    if q['api_name'] in ('daily','adj_factor','trade_cal'):
        d=values.get('trade_date',values.get('cal_date'))
        if not '20250601'<=d<='20261005':return 'OUTSIDE_FROZEN_WINDOW'
        if day(d)>instant(cutoff).astimezone(ZoneInfo('Asia/Shanghai')).date():return 'FUTURE_EVENT_DATE'
    if q['api_name']=='fina_indicator':
        scope=q['date_scope'];period=values.get('end_date')
        if not scope['start']<=period<=scope['end']:return 'REPORT_PERIOD_OUTSIDE_REQUEST'
        if day(period)>instant(q['retrieved_at']).astimezone(ZoneInfo('Asia/Shanghai')).date():return 'FUTURE_REPORT_PERIOD'
    return None

def _input_body(upstream,symbol,ctx):
    views=[q for api in APIS for q in request_views(upstream,api)]
    cutoff=ctx['rules']['decision_cutoff'];instant(cutoff)
    for q in views:
        require(q['available_at']==q['retrieved_at'] and q['published_at'] is None,'WAVE_C_CLOCK_BACKFILL_FORBIDDEN')
        require(instant_ns(q['retrieved_at'])<=instant_ns(cutoff),'WAVE_C_CURRENT_CUTOFF_BEFORE_CAPTURE')
    retrieval=max((q['retrieved_at'] for q in views),key=instant_ns)
    eligible,excluded=[],[]
    for q in views:
        if q['ts_code'] not in (symbol,None):continue
        for n,row in enumerate(q['rows']):
            values=deepcopy(row.get('values',row))
            require(values.get('ts_code',symbol)==symbol,'WAVE_C_SYMBOL_CROSSOVER')
            source_ref={'origin':q['origin'],'scope':q.get('scope','WAVE_B'),'request_id':q['request_id'],'request_fingerprint':q['request_fingerprint'],
                'raw_sha256':q['raw_sha256'],'row_ordinal':row.get('row_ordinal',n),'retrieved_at':q['retrieved_at'],'available_at':q['available_at'],'published_at':q['published_at']}
            reason=_reason(q,row,cutoff)
            if reason:excluded.append({'api_name':q['api_name'],'source_ref':source_ref,'reason_code':reason});continue
            eligible.append({'api_name':q['api_name'],'values':values,'source_ref':source_ref})
    return {'observations':eligible,'excluded':excluded,'upstream_input_hash':digest(upstream),'baseline_hash':ctx['baseline_hash'],'release_hash':ctx['release_hash']},retrieval

def load_real_inputs():
    ctx=frozen_context();upstream=load_wave_b();require_inputs(upstream)
    require(upstream['fixture'] is False,'WAVE_C_SYNTHETIC_SOURCE_FORBIDDEN')
    result=[]
    for symbol in SYMBOLS:
        body,retrieval=_input_body(upstream,symbol,ctx)
        result.append(_register({**header('Input',symbol,ctx,_identity(ctx,upstream),retrieval),'body':body},ctx,upstream))
    return result
