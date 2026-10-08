"""Registered read-only candidate diagnostics; never admission or research authority."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import copy, hashlib, json, re
from overnight.data.dataset import load_verified_dataset, FIELDS
from .primitives import require, canonical, sha, date_literal, clock, safe_body

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT.parent / '.p1b-archives/wave-b-20261006'
SYMBOLS = ('603993.SH', '600312.SH', '603228.SH')
START, END = '20250601', '20261005'
VERSION = '1.0.0-candidate-diagnostic'
_INPUTS, _RESULTS, _OBS, _EVIDENCE, _CODE_INPUTS = {}, {}, {}, {}, {}







def _fixed(value):
    require(value.get('namespace') == 'CORE_40' and value.get('provider_id') == 'TUSHARE_MONTHLY_GATEWAY' and
            value.get('source_classification') == 'OWNER_PROVIDED_MONTHLY_GATEWAY' and
            value.get('state') == 'QUARANTINED' and value.get('source_admission') == 'BLOCKED' and
            value.get('historical_visibility_proven') is False and value.get('productionGate') is False,
            'INPUT_PERMISSION_OR_NAMESPACE_INVALID')

def _register(value):
    _fixed(value); _INPUTS[id(value)] = (value, sha(canonical(value)))
    _CODE_INPUTS[id(value)] = [(p,sha(p.read_bytes())) for p in tuple(ROOT/'wave_b'/n for n in ('core.py','probe.py','primitives.py','evidence_root.py','status.py','action.py','financial.py','industry.py','candidate.py')) if p.exists()]
    return value

def require_inputs(value):
    known = _INPUTS.get(id(value))
    require(known is not None and known[0] is value and known[1] == sha(canonical(value)), 'UNREGISTERED_OR_MUTATED_INPUT')
    for p,h in _CODE_INPUTS[id(value)] + _EVIDENCE.get(id(value),[]):
        require(p.resolve()==p and p.is_file() and not p.is_symlink() and sha(p.read_bytes())==h,'INPUT_SOURCE_OR_CODE_CHANGED')
    _fixed(value); return value

def _base(legacy, new, fixture, identity):
    return _register({'version':VERSION, 'fixture':fixture, 'namespace':'CORE_40',
        'provider_id':'TUSHARE_MONTHLY_GATEWAY', 'source_classification':'OWNER_PROVIDED_MONTHLY_GATEWAY',
        'state':'QUARANTINED','source_admission':'BLOCKED','historical_visibility_proven':False,
        'productionGate':False,'legacy':legacy,'new':new,'source_identity':identity})

def load_inputs():
    from .evidence_root import verify_registered_capture
    manifest = json.loads((ROOT/'docs/wave-b/capture-evidence.json').read_bytes())
    require(set(manifest)=={'version','report','producer_code_pins','source_admission','productionGate'} and
            manifest['source_admission']=='BLOCKED' and manifest['productionGate'] is False, 'CAPTURE_MANIFEST_INVALID')
    for item in manifest['producer_code_pins']:
        p = ROOT/item['path']; require(p.resolve()==p and p.is_file() and not p.is_symlink(), 'CODE_PATH_INVALID')
        require(sha(p.read_bytes())==item['sha256'], 'CAPTURE_CODE_CHANGED')
    report = verify_registered_capture(manifest['report'])
    legacy = load_verified_dataset()
    baseline_path=ROOT/'docs/wave-b/baseline-pins.json'
    baseline_raw=baseline_path.read_bytes();baseline=json.loads(baseline_raw)
    from .evidence_root import ARCHIVE as evidence_archive
    checkpoint_path=evidence_archive/'start/checkpoint.json'
    checkpoint_raw=checkpoint_path.read_bytes();checkpoint=json.loads(checkpoint_raw)
    require(sha(checkpoint_raw)==baseline['checkpoint_sha256'] and
            baseline['tracked_files']==checkpoint['tracked_files'] and
            baseline['allowed_navigation_updates']==checkpoint['allowed_navigation_updates'] and
            len(baseline['tracked_files'])==484 and
            baseline['allowed_navigation_updates']==['AGENTS.md','README.md','docs/source-of-truth.json'], 'BASELINE_ROOT_BINDING_CHANGED')
    release_path=ROOT/'docs/wave-b/release.json';release_raw=release_path.read_bytes();release=json.loads(release_raw)
    require(release['source_admission']=='BLOCKED' and release['productionGate'] is False and release['schema_version']==6,'RELEASE_PERMISSION_INVALID')
    all_rule_refs=[{'path':str(ROOT/r['path']),'sha256':r['sha256']} for r in
        baseline['tracked_files'] if r['path'] not in baseline['allowed_navigation_updates']]
    all_rule_refs += [{'path':str(ROOT/r['path']),'sha256':r['sha256']} for r in release['code_pins']]
    all_rule_refs += [{'path':str(p),'sha256':sha(b)} for p,b in
        [(baseline_path,baseline_raw),(checkpoint_path,checkpoint_raw),(release_path,release_raw)]]
    for r in all_rule_refs:
        p=Path(r['path']);require(p.resolve()==p and not p.is_symlink() and sha(p.read_bytes())==r['sha256'],'SOURCE_RULE_BASELINE_OR_RELEASE_CHANGED')
    identity = sha(canonical({'legacy':sha(canonical(legacy)), 'baseline':sha(baseline_raw),'release':sha(release_raw), 'report':manifest['report']['sha256'],
        'raw':[q['raw_sha256'] for q in report['requests']], 'rules':VERSION,'core_code':sha(Path(__file__).read_bytes()),'primitives_code':sha((ROOT/'wave_b/primitives.py').read_bytes()),'analysis_code':{n:sha((ROOT/'wave_b'/n).read_bytes()) for n in ('evidence_root.py','status.py','action.py','financial.py','industry.py','candidate.py') if (ROOT/'wave_b'/n).exists()}}))
    value=_base(legacy,report['requests'],False,identity)
    old_gate=json.loads((ROOT/'docs/p1b-real-admission/Gate.json').read_bytes())
    refs=old_gate['raw_inventory']+old_gate['probe_report_refs']+[manifest['report'], {'path':str(ROOT/'docs/wave-b/capture-evidence.json'),'sha256':sha((ROOT/'docs/wave-b/capture-evidence.json').read_bytes())}]
    dependency_pins=json.loads((ROOT/'docs/p1b-real-admission/code-provenance.json').read_bytes())['files']
    refs += [{'path':str(ROOT/x['path']),'sha256':x['sha256']} for x in dependency_pins]
    refs += [{'path':str(ROOT/p),'sha256':sha((ROOT/p).read_bytes())} for p in ['overnight/data/dataset.py','tushare-admission/probe.py','docs/overnight/evidence.json']]
    refs += [{'path':q['raw_ref'],'sha256':q['raw_sha256']} for q in report['requests'] if q['raw_ref'] is not None]
    refs += all_rule_refs
    _EVIDENCE[id(value)] = [(Path(x['path']),x['sha256']) for x in refs]
    require_inputs(value);return value

def fixture_inputs(new_requests=None, legacy_requests=None):
    # Every fixture carries explicit provenance even when using an engineering ts_code.
    new = copy.deepcopy(new_requests or [])
    for i, q in enumerate(new):
        require(type(q) is dict and q.get('api_name') in {'stock_basic','stock_st','namechange','suspend_d','dividend','adj_factor','fina_indicator','index_member_all'}, 'FIXTURE_REQUEST_INVALID')
        q.setdefault('request_id', 'SYNTHETIC-' + str(i)); q.setdefault('params',{})
        q.setdefault('ts_code',q['params'].get('ts_code',SYMBOLS[0])); require(q['ts_code'] in SYMBOLS,'SYMBOL_SCOPE_INVALID')
        q['params'].setdefault('ts_code',q['ts_code']); require(q['params']['ts_code']==q['ts_code'],'SYMBOL_SCOPE_INVALID')
        first=q.get('rows',[{}])[0] if q.get('rows') else {}
        q.setdefault('fields',list(first.get('values',first)))
        q.setdefault('date_scope',{'key':None,'start':START,'end':END})
        q.setdefault('retrieved_at','2026-10-06T01:00:00Z');q.setdefault('available_at',q['retrieved_at'])
        q.setdefault('published_at',None);q.setdefault('response_blocked',False);q.setdefault('reason_codes',[])
        clock(q['retrieved_at']); require(q['available_at']==q['retrieved_at'] and q['published_at'] is None,'CLOCK_BACKFILL_FORBIDDEN')
        q.setdefault('raw_sha256',sha(canonical(q.get('rows',[]))));q.setdefault('request_fingerprint',sha(canonical({'fixture':True,'api':q['api_name'],'params':q['params'],'id':q['request_id']})))
        for row in q.get('rows',[]):
            values=row.get('values',row)
            require(values.get('ts_code',q['ts_code'])==q['ts_code'],'SYMBOL_SCOPE_INVALID')
            safe_body(values)
        require(q.get('namespace','CORE_40')=='CORE_40' and all(q.get(k,False) is False for k in
                ['historical_visibility_proven','productionGate','provider_identity_verified','license_verified','transport_integrity_verified']), 'FIXTURE_PERMISSION_INVALID')
    legacy={'fixture':True,'requests':copy.deepcopy(legacy_requests or [])}
    return _base(legacy,new,True,sha(canonical({'fixture':True,'legacy':legacy,'new':new,'rules':VERSION,'core_code':sha(Path(__file__).read_bytes()),'primitives_code':sha((ROOT/'wave_b/primitives.py').read_bytes()),'analysis_code':{n:sha((ROOT/'wave_b'/n).read_bytes()) for n in ('evidence_root.py','status.py','action.py','financial.py','industry.py','candidate.py') if (ROOT/'wave_b'/n).exists()}})))

def request_views(inputs, api, origin='all'):
    require_inputs(inputs);require(origin in ('all','legacy','new'),'ORIGIN_INVALID');out=[]
    if origin in ('all','legacy'):
        for q in inputs['legacy']['requests']:
            if q['api_name']!=api: continue
            item={k:q.get(k) for k in ['request_id','api_name','ts_code','params','scope','date_scope','raw_sha256','request_fingerprint','retrieved_at','available_at','published_at']}
            item.update({'origin':'legacy','fields':list(FIELDS.get(api,())), 'response_blocked':q.get('response_dq')=='BLOCKED',
                'reason_codes':q.get('response_dq_reasons',[]),'rows':[{'row_ordinal':row['row_ordinal'],'values':{k:v['value'] for k,v in row['typed_fields'].items()}} for row in q['rows']]})
            out.append(item)
    if origin in ('all','new'):
        for q in inputs['new']:
            if q['api_name']==api: out.append({**copy.deepcopy(q),'origin':'new'})
    for q in out:
        q['row_count']=len(q.get('rows',[]));q['fixture']=inputs['fixture']
    return out

def observations(inputs,api,origin='all'):
    result=[]
    for q in request_views(inputs,api,origin):
        for n,row in enumerate(q.get('rows',[])):
            values=copy.deepcopy(row.get('values',row))
            item={'values':values,'response_blocked':q['response_blocked'],'fixture':inputs['fixture'],
                'ref':{'origin':q['origin'],'scope':q.get('scope','WAVE_B'),'request_id':q['request_id'],'request_fingerprint':q['request_fingerprint'],
                       'raw_sha256':q['raw_sha256'],'row_ordinal':row.get('row_ordinal',n),'retrieved_at':q['retrieved_at'],
                       'available_at':q['available_at'],'published_at':q['published_at']}}
            _OBS[id(item)]=(item,sha(canonical(item)),inputs);result.append(item)
    return result

def require_cutoff(observation, cutoff):
    known=_OBS.get(id(observation))
    require(known is not None and known[0] is observation and sha(canonical(observation))==known[1],'UNREGISTERED_OR_MUTATED_OBSERVATION')
    require_inputs(known[2])
    require(clock(observation['ref']['available_at'])<=clock(cutoff),'OBSERVATION_NOT_AVAILABLE_AT_CUTOFF')
    return observation

def make_result(inputs,kind,body,code_path):
    require_inputs(inputs);safe_body(body)
    p=Path(code_path);p=p if p.is_absolute() else ROOT/p
    require(p.resolve()==p and p.parent==ROOT/'wave_b' and p.name in {'status.py','action.py','financial.py','industry.py','candidate.py'},'PRODUCER_CODE_PATH_INVALID')
    result={'version':VERSION,'kind':kind,'fixture':inputs['fixture'],'namespace':'CORE_40',
        'provider_id':'TUSHARE_MONTHLY_GATEWAY','source_classification':'OWNER_PROVIDED_MONTHLY_GATEWAY',
        'state':'QUARANTINED','source_admission':'BLOCKED','historical_visibility_proven':False,'productionGate':False,
        'provider_identity_verified':False,'license_verified':False,'transport_integrity_verified':False,
        'input_identity':inputs['source_identity'],'code_hash':sha(p.read_bytes()),'rule_version':VERSION,'body':body}
    result['content_hash']=sha(canonical(result));_RESULTS[id(result)]=(result,result['content_hash'],p,inputs)
    return result

def require_result(result):
    known=_RESULTS.get(id(result));require(known is not None and known[0] is result,'UNREGISTERED_CANDIDATE')
    require_inputs(known[3])
    _fixed(result);require(all(result[k] is False for k in ['provider_identity_verified','license_verified','transport_integrity_verified']),'PROVIDER_SELF_ASSERTION_FORBIDDEN')
    body={k:v for k,v in result.items() if k!='content_hash'}
    require(sha(canonical(body))==known[1]==result['content_hash'] and sha(known[2].read_bytes())==result['code_hash'],'CANDIDATE_VERSION_INVALIDATED')
    return result

def reject_real_consumer(value,consumer):
    require(consumer in {'BrainPacket','ResearchAssessment','ResearchCard','Candidate','Signal'},'CONSUMER_INVALID')
    # No registered Receipt exists in Wave B. All registered candidates are quarantine.
    require_result(value)
    raise ValueError('QUARANTINED_INPUT_NOT_ADMITTED')
