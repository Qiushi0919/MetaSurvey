"""Closed Wave E source identity and display registry. No network or live authority."""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import json, re
from wave_c.core import canonical, sha, digest, seal, require, checked_file, SYMBOLS
from overnight.analysis.inputs import instant_ns
from .public import decode, html_text, pdf_identity, allowed_redirect, DOCS

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path('/Users/qiushi/投资研究/.p1b-archives/wave-e-20261006')
PREVIOUS = ARCHIVE.parent / 'wave-d-20261006'
NAMES = ('HistoricalBacktestReadiness', 'DiagnosticBacktestResult', 'SnapshotBPreflight', 'ForwardPaperReadiness')
_REGISTRY = {}

def private_ref(r, base=ARCHIVE):
    require(type(r) is dict and set(r) >= {'path','sha256','bytes'}, 'WAVE_E_REF_SHAPE')
    p=Path(r['path'])
    require(p.is_relative_to(base) and p.resolve()==p and not p.is_symlink() and p.is_file() and p.stat().st_mode&0o777==0o600, 'WAVE_E_PRIVATE_PATH_INVALID')
    b=checked_file(p,r['sha256']);require(len(b)==r['bytes'], 'WAVE_E_REF_SIZE_INVALID');return b

def dependency_key(p):
    if p.is_relative_to(ROOT):return 'GIT:'+p.relative_to(ROOT).as_posix()
    require(p.is_relative_to(ARCHIVE.parent), 'WAVE_E_DEPENDENCY_ROOT_INVALID')
    return 'FIXED_PRIVATE_ARCHIVE:'+p.relative_to(ARCHIVE.parent).as_posix()

def frozen_context():
    bpath=ROOT/'docs/wave-e/baseline-pins.json';bb=checked_file(bpath);baseline=json.loads(bb)
    require(baseline['baseline_commit']=='52f6a608ca46678dbd2b5ab976945bebc2d2345e' and len(baseline['tracked_files'])==616 and baseline['immutable_count']==613 and baseline['allowed_navigation_updates']==['AGENTS.md','README.md','docs/source-of-truth.json'], 'WAVE_E_BASELINE_INVALID')
    cp=private_ref(baseline['checkpoint_ref']);require(json.loads(cp)['tracked_files']==baseline['tracked_files'], 'WAVE_E_BASELINE_UNBOUND')
    pins=[(ROOT/x['path'],x['sha256']) for x in baseline['tracked_files'] if x['path'] not in baseline['allowed_navigation_updates']]
    from wave_d.core import frozen_context as previous_context
    pins.extend(previous_context()['pins'])
    acceptance=json.loads(checked_file(ROOT/'docs/wave-e/baseline-acceptance.json'))
    checkpoint=private_ref(acceptance['previous_delivery_checkpoint'],PREVIOUS)
    require(json.loads(checkpoint)['final_head']==baseline['baseline_commit'] and json.loads(checkpoint)['productionGate'] is False, 'WAVE_E_PREDECESSOR_CHECKPOINT_INVALID')
    pins.append((Path(acceptance['previous_delivery_checkpoint']['path']),sha(checkpoint)))
    evidence=json.loads(checked_file(ROOT/'docs/wave-d/evidence.json'));inputs=[]
    for r in evidence['artifacts']:
        raw=private_ref(r,PREVIOUS);pins.append((Path(r['path']),r['sha256']))
        if r['name'].endswith('.input.json'):
            x=json.loads(raw);require(x['contract_name']=='RealResearchSandboxInput' and x['symbol'] in SYMBOLS and x['namespace']=='LOCAL_EXPERIMENTAL_REAL_RESEARCH:CORE_40' and x['formal_source_admission']=='BLOCKED' and x['historical_visibility_proven'] is False and x['productionGate'] is False,'WAVE_E_INPUT_PROMOTION')
            require(x['content_hash']==digest({k:v for k,v in x.items() if k!='content_hash'}),'WAVE_E_INPUT_SEAL_INVALID');inputs.append(x)
    require(tuple(x['symbol'] for x in inputs)==SYMBOLS,'WAVE_E_INPUT_COHORT_INVALID')
    rp=ROOT/'docs/wave-e/release.json';rb=checked_file(rp);release=json.loads(rb)
    require(release['version']=='1.0.0-wave-e-readiness' and release['productionGate'] is False and release['formal_source_admission']=='BLOCKED','WAVE_E_RELEASE_PROMOTION')
    pins.extend((ROOT/x['path'],x['sha256']) for x in release['code_pins'])
    rulep=ROOT/'docs/wave-e/rules.json';ruleb=checked_file(rulep);rules=json.loads(ruleb)
    require(rules['symbols']==list(SYMBOLS) and rules['namespace']=='LOCAL_ENGINE_DIAGNOSTIC:CORE_40' and rules['current_observed_only'] is True and rules['historical_visibility_proven'] is False and rules['productionGate'] is False and rules['actual_account_parameters']=='30_UNSET_REQUIRED' and rules['actual_forward_days']==0 and rules['strategy']['optimization'] is False and rules['strategy']['financial_features'] is False,'WAVE_E_RULE_PROMOTION')
    pubref=json.loads(checked_file(ROOT/'docs/wave-e/public-ref.json'));public_raw=private_ref(pubref);public=json.loads(public_raw)
    require(public['code_hash']==sha((ROOT/'wave_e/public.py').read_bytes()) and public['authenticated_requests']==0 and public['credential_lookups']==0 and public['historical_visibility_proven'] is False and public['productionGate'] is False and public['public_GET_requests']==22,'WAVE_E_PUBLIC_AUTHORITY_INVALID')
    pins.append((Path(pubref['path']),pubref['sha256']))
    def add(r):
        if r:private_ref(r);pins.append((Path(r['path']),r['sha256']))
    for q in public['references']:
        require(q['request_url'] in DOCS.values() and q['method']=='GET' and q['credentials_attached'] is False and q['available_at']==q['retrieved_at'] and instant_ns(q['retrieved_at'])<=instant_ns(rules['decision_cutoff']) and not q['redirect_location'],'WAVE_E_PUBLIC_REFERENCE_SCOPE')
        for k in ('raw_ref','decoded_ref','text_ref'):add(q[k])
        require(decode(private_ref(q['raw_ref']),q['content_encoding'])==private_ref(q['decoded_ref']) and html_text(private_ref(q['decoded_ref'])).encode()==private_ref(q['text_ref']), 'WAVE_E_PUBLIC_PROJECTION_CHANGED')
    from .public import origins
    require([x['index_fact'] for x in public['documents']]==[x['fact'] for x in origins()],'WAVE_E_SSE_PLAN_CHANGED')
    for d in public['documents']:
        chain=d['redirect_chain'];require(len(chain) in (1,2),'WAVE_E_REDIRECT_CHAIN_INVALID')
        if len(chain)==2:require(allowed_redirect(chain[0]['request_url'],chain[0]['redirect_location'])==chain[1]['request_url'],'WAVE_E_REDIRECT_CHANGED')
        for q in chain:
            require(q['credentials_attached'] is False and q['available_at']==q['retrieved_at'] and instant_ns(q['retrieved_at'])<=instant_ns(rules['decision_cutoff']),'WAVE_E_SSE_CLOCK_OR_AUTH_INVALID')
            add(q['raw_ref']);add(q['decoded_ref'])
            require(decode(private_ref(q['raw_ref']),q['content_encoding'])==private_ref(q['decoded_ref']),'WAVE_E_SSE_DECODE_CHANGED')
        if d['body_verified']:
            text,pages=pdf_identity(private_ref(chain[-1]['decoded_ref']),d['index_fact']);add(d['text_ref']);require(text.encode()==private_ref(d['text_ref']) and pages==d['pages'],'WAVE_E_SSE_BODY_CHANGED')
        else:require(d['text_ref'] is None and d['reason']=='WAVE_E_SSE_DECODED_RESPONSE_NOT_PDF' and not private_ref(chain[-1]['decoded_ref']).startswith(b'%PDF-'),'WAVE_E_SSE_FALSE_FACT')
    pins.extend([(bpath,sha(bb)),(Path(baseline['checkpoint_ref']['path']),sha(cp)),(rp,sha(rb)),(rulep,sha(ruleb))])
    unique={dependency_key(p):(p,h) for p,h in pins}
    for p,h in unique.values():checked_file(p,h)
    identity=digest([(k,h) for k,(p,h) in sorted(unique.items())])
    return {'rules':rules,'rules_hash':sha(ruleb),'code_hash':digest(release['code_pins']),'schema_hash':digest([x for x in release['code_pins'] if x['path'].startswith('contracts/wave-e/')]),'predecessor_hash':sha(checkpoint),'source_identity':identity,'pins':list(unique.values()),'inputs':inputs,'public':public,'retrieval_cutoff':max([q['retrieved_at'] for q in public['references']]+[q['retrieved_at'] for d in public['documents'] for q in d['redirect_chain']],key=instant_ns)}

def context_hash(ctx):
    return digest({k:v for k,v in ctx.items() if k not in ('pins','inputs','public')}|{'pins':[(dependency_key(p),h) for p,h in ctx['pins']]})

def price_series(ctx):
    raw={};factors={};meta=[];cutoff=ctx['rules']['decision_cutoff']
    for x in ctx['inputs']:
        s=x['symbol'];daily={};factor={}
        for o in x['body']['observations']:
            if o['api_name'] not in ('daily','adj_factor'):continue
            v=o['values'];sr=o['source_ref'];day=v['trade_date']
            require(v['ts_code']==s and sr['event_time'] is None and sr['published_at'] is None and sr['available_at']==sr['retrieved_at'] and instant_ns(sr['retrieved_at'])<=instant_ns(cutoff),'WAVE_E_PRICE_CLOCK_OR_SCOPE_INVALID')
            require(re.fullmatch(r'\d{8}',day) and '20250601'<=day<='20260930','WAVE_E_PRICE_WINDOW_INVALID')
            target=daily if o['api_name']=='daily' else factor
            vals={k:v[k] for k in ('open','high','low','close')} if target is daily else {'adj_factor':v['adj_factor']}
            for val in vals.values():require(type(val) is str and re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?',val) and Decimal(val)>0,'WAVE_E_PRICE_VALUE_INVALID')
            if day in target:require(all(Decimal(target[day]['values'][k])==Decimal(t) for k,t in vals.items()),'WAVE_E_CONFLICTING_PRICE_VERSION_BLOCKED');target[day]['refs'].append(deepcopy(sr))
            else:target[day]={'values':vals,'refs':[deepcopy(sr)]}
        require(len(daily)==327 and set(daily)==set(factor),'WAVE_E_PRICE_FACTOR_COVERAGE_INVALID')
        raw[s]=[{'trade_date':d,**daily[d]['values'],'source_ref':{'input_hash':x['content_hash'],'price_treatment':'RAW_UNADJUSTED_OBSERVED','original_refs':daily[d]['refs']}} for d in sorted(daily)]
        factors[s]=factor;meta.append({'symbol':s,'unique_sessions':327,'daily_originals':sum(len(v['refs']) for v in daily.values()),'factor_originals':sum(len(v['refs']) for v in factor.values()),'identical_versions_deduplicated_without_overwrite':True,'input_hash':x['content_hash'],'historical_universe_proven':False})
    require([r['trade_date'] for r in raw[SYMBOLS[0]]]==[r['trade_date'] for r in raw[SYMBOLS[1]]]==[r['trade_date'] for r in raw[SYMBOLS[2]]],'WAVE_E_COHORT_CALENDAR_MISSING')
    adjusted={}
    with localcontext() as c:
        c.prec=100;c.rounding=ROUND_HALF_EVEN
        for s in SYMBOLS:
            anchor_day=raw[s][0]['trade_date'];anchor=factors[s][anchor_day];adjusted[s]=[]
            for row in raw[s]:
                f=factors[s][row['trade_date']];ratio=Decimal(f['values']['adj_factor'])/Decimal(anchor['values']['adj_factor'])
                adjusted[s].append({'trade_date':row['trade_date'],**{k:format(Decimal(row[k])*ratio,'f') for k in ('open','high','low','close')},'source_ref':{'input_hash':row['source_ref']['input_hash'],'price_treatment':'FACTOR_FIRST_ANCHOR_SENSITIVITY_ONLY','raw_original_refs':row['source_ref']['original_refs'],'factor_original_refs':f['refs'],'anchor_factor_refs':anchor['refs'],'anchor_day':anchor_day,'authoritative_adjustment':False,'cash_entitlement':False}})
    return {'RAW_UNADJUSTED_OBSERVED':raw,'FACTOR_FIRST_ANCHOR_SENSITIVITY_ONLY':adjusted},meta

def register(*args,**kwargs):raise ValueError('WAVE_E_DIRECT_ISSUE_FORBIDDEN')
def derive(*args,**kwargs):raise ValueError('WAVE_E_DIRECT_ISSUE_FORBIDDEN')

def objects():
    from .research import build
    ctx=frozen_context();bodies,artifacts=build(ctx);values=[]
    for name in NAMES:
        h={'contract_name':name,'contract_version':'1.0.0','object_version':1,'object_id':'wave-e:'+name+':'+ctx['source_identity'][7:23],'trace_id':'wave-e:'+ctx['source_identity'][7:],'namespace':ctx['rules']['namespace'],'symbols':list(SYMBOLS),'labels':ctx['rules']['labels'],'decision_cutoff':ctx['rules']['decision_cutoff'],'retrieval_cutoff':ctx['retrieval_cutoff'],'timezone':'Asia/Shanghai','source_identity':ctx['source_identity'],'rules_hash':ctx['rules_hash'],'code_hash':ctx['code_hash'],'schema_hash':ctx['schema_hash'],'predecessor_hash':ctx['predecessor_hash'],'source_admission':'UNVERIFIED_GATEWAY','formal_source_admission':'BLOCKED','reason_codes':['NON_PIT_DIAGNOSTIC','NOT_STRATEGY_EVIDENCE','NON_TRADEABLE','LOCAL_ONLY','UNVERIFIED_GATEWAY','NO_HISTORICAL_PIT','UNSET_REQUIRED','UNKNOWN_STATUS','NO_EXECUTION_AUTHORITY','SEPARATE_OWNER_AUTHORIZATION_REQUIRED','ACTUAL_FRESH_SESSION_REQUIRED','REAL_FORWARD_NOT_AUTHORIZED','NO_NATIVE_PROMOTION'],'invalidation_conditions':['PREDECESSOR_SOURCE_RAW_CHANGED','RULE_CODE_SCHEMA_CHANGED','CUTOFF_NAMESPACE_CHANGED','PRIVATE_PATH_SUBSTITUTION','CALLER_COPY_RESEAL','AUTHORITY_PROMOTION'],'body':bodies[name]}
        h.update({k:False for k in ('provider_identity_verified','license_verified','transport_integrity_verified','historical_visibility_proven','cloud_transfer','tradeable','production_eligible','can_produce_order','productionGate')})
        v=seal(h);_REGISTRY[id(v)]={'value':v,'hash':digest(v),'context':context_hash(ctx)};values.append(v)
    return values,artifacts

def assert_registered(value):
    q=_REGISTRY.get(id(value));require(q and q['value'] is value and q['hash']==digest(value),'WAVE_E_UNREGISTERED_OR_MUTATED')
    require(q['context']==context_hash(frozen_context()),'WAVE_E_SOURCE_RULE_CODE_SCHEMA_INVALIDATED');return value

def transition(value,target):
    assert_registered(value);require(target=='LOCAL_DIAGNOSTIC_DISPLAY','WAVE_E_FORMAL_OR_EXECUTION_FORBIDDEN');return value

def run_snapshot_b(*args,**kwargs):raise ValueError('WAVE_E_SNAPSHOT_B_NOT_AUTHORIZED')
